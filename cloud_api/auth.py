"""Authentication: Cognito JWT verification + API-key fallback.

Two credential types resolve to the same `AuthedUser`:

- **Cognito JWT** (`Authorization: Bearer <id_token>`) — used by the SPA.
  Verified locally against the user pool's JWKS, so no Cognito round-trip
  per request.
- **API key** (`Authorization: Bearer <hex>`) — used by the team CLI.
  Looked up by SHA-256 hash in the `api_keys` table.

Both paths return the same shape so route handlers don't need to care.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwk, jwt
from jose.utils import base64url_decode
from sqlalchemy.orm import Session

from cloud_api import db as dbmod
from cloud_api.db import ApiKey, Team, User, get_db


# JWT looks like a base64url-encoded 3-part dot-separated string. API keys
# are 32 raw hex chars (16 bytes from secrets.token_hex). We disambiguate
# by shape so we never query Postgres with a JWT or hit Cognito with a key.
_HEX_TOKEN_RE = re.compile(r"^[0-9a-f]{32,}$")


def _slugify_team(raw: str) -> str:
    """Mirror of slugify() in ui/src/auth.tsx. Lowercase, alphanumeric +
    single hyphens, no leading/trailing hyphen. Used to canonicalise the
    custom:team_name claim so legacy users (registered before slugify
    landed) resolve to the same team id new users get."""
    s = re.sub(r"[^a-z0-9]+", "-", raw.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s


@dataclass
class AuthedUser:
    cognito_sub: str
    email: str
    team_id: str


@lru_cache(maxsize=1)
def _jwks() -> dict[str, dict]:
    """Fetch and cache the user pool's JWKS. Process-lifetime cache: keys
    rotate rarely, and the worst case is a 401 after a key roll that fixes
    itself on next process restart."""
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    region = os.environ["AWS_REGION"]
    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    return {key["kid"]: key for key in resp.json()["keys"]}


def _verify_cognito_jwt(token: str) -> dict:
    """Verify an id_token from the SPA. Returns the decoded claims.

    Raises HTTPException(401) on any failure.
    """
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    client_id = os.environ["COGNITO_CLIENT_ID"]
    region = os.environ["AWS_REGION"]
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    try:
        headers = jwt.get_unverified_headers(token)
        kid = headers["kid"]
        key_data = _jwks().get(kid)
        if not key_data:
            # JWKS may have rotated since process start; flush and retry once.
            _jwks.cache_clear()
            key_data = _jwks().get(kid)
        if not key_data:
            raise ValueError(f"unknown kid {kid}")

        public_key = jwk.construct(key_data)
        message, encoded_sig = token.rsplit(".", 1)
        decoded_sig = base64url_decode(encoded_sig.encode())
        if not public_key.verify(message.encode(), decoded_sig):
            raise ValueError("signature mismatch")

        claims = jwt.get_unverified_claims(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {e}",
        )

    # Manual claim checks (jose's audience check is finicky with id_tokens).
    now = datetime.now(timezone.utc).timestamp()
    if claims.get("exp", 0) < now:
        raise HTTPException(status_code=401, detail="token expired")
    if claims.get("iss") != issuer:
        raise HTTPException(status_code=401, detail="wrong issuer")
    # Cognito id_tokens use `aud`; access_tokens use `client_id`. SPA flow
    # ships id_tokens, but we accept either.
    aud = claims.get("aud") or claims.get("client_id")
    if aud != client_id:
        raise HTTPException(status_code=401, detail="wrong audience")
    if claims.get("token_use") not in ("id", "access"):
        raise HTTPException(status_code=401, detail="wrong token_use")

    return claims


def _hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ensure_user(db: Session, claims: dict) -> AuthedUser:
    """Bring the User row in line with what Cognito says.

    Called on every JWT auth so that newly-signed-up users get a DB row
    without an explicit /signup flow. The team is read from the
    `custom:team_name` attribute set at sign-up; if missing, we 400 — the
    SPA should never send a token from a user who skipped that field.
    """
    sub = claims["sub"]
    email = claims["email"]
    raw_team_name = claims.get("custom:team_name")
    if not raw_team_name:
        raise HTTPException(
            status_code=400,
            detail="user has no team -- sign-up did not include custom:team_name",
        )
    # Slugify on read. The SPA already does this at sign-up, but the
    # custom:team_name attribute is immutable in the user pool, so legacy
    # accounts (registered before slugify landed) still send non-slug
    # values. Canonicalising here keeps all team data keyed on the slug.
    team_id = _slugify_team(raw_team_name)
    if not team_id:
        raise HTTPException(
            status_code=400,
            detail=f"custom:team_name {raw_team_name!r} slugifies to empty",
        )

    team = db.get(Team, team_id) or Team(id=team_id, name=team_id)
    if team not in db:
        db.add(team)

    user = db.get(User, sub)
    if user is None:
        user = User(cognito_sub=sub, email=email, team_id=team.id)
        db.add(user)
    elif user.team_id != team.id:
        user.team_id = team.id
    db.commit()

    return AuthedUser(cognito_sub=sub, email=email, team_id=team.id)


def _user_from_api_key(db: Session, token: str) -> AuthedUser:
    digest = _hash_api_key(token)
    key = db.query(ApiKey).filter(ApiKey.token_hash == digest).one_or_none()
    if key is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    user = key.user
    return AuthedUser(
        cognito_sub=user.cognito_sub, email=user.email, team_id=user.team_id
    )


def _local_dev_user(db: Session) -> AuthedUser:
    """Auto-provision a fixed local-dev team + user. Only used when
    LOCAL_DEV=1; never reachable in production."""
    team_id = os.environ.get("LOCAL_DEV_TEAM", "local-team")
    sub = os.environ.get("LOCAL_DEV_SUB", "local-dev-user")
    email = os.environ.get("LOCAL_DEV_EMAIL", "dev@localhost")
    if db.get(Team, team_id) is None:
        db.add(Team(id=team_id, name=team_id))
    if db.get(User, sub) is None:
        db.add(User(cognito_sub=sub, email=email, team_id=team_id))
    db.commit()
    return AuthedUser(cognito_sub=sub, email=email, team_id=team_id)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthedUser:
    if os.environ.get("LOCAL_DEV") == "1":
        return _local_dev_user(db)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    # Hex token = API key. JWT = Cognito.
    if _HEX_TOKEN_RE.match(token):
        return _user_from_api_key(db, token)
    claims = _verify_cognito_jwt(token)
    return _ensure_user(db, claims)


def require_cognito(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthedUser:
    """Like get_current_user but rejects API keys — used for management
    endpoints (e.g. /api-keys) where we don't want a CLI key to mint more
    CLI keys."""
    if os.environ.get("LOCAL_DEV") == "1":
        return _local_dev_user(db)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if _HEX_TOKEN_RE.match(token):
        raise HTTPException(
            status_code=403, detail="this endpoint requires a Cognito session, not an API key"
        )
    claims = _verify_cognito_jwt(token)
    return _ensure_user(db, claims)
