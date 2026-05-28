"""FastAPI route handlers."""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import date as date_cls, datetime, timezone
from typing import Annotated, Literal

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from cloud_api.auth import AuthedUser, get_current_user, require_cognito
from cloud_api.db import ApiKey, Paper, Team, User, get_db
from cloud_api.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeySummary,
    ActivityEntry,
    BedrockCredentials,
    CurrentRound,
    MeResponse,
    PaperCreate,
    PaperDetail,
    PaperSummary,
    TeamSummary,
)


logger = logging.getLogger(__name__)


router = APIRouter()

# Hackathon runs in 3 rounds. Each team may submit up to SUBMISSIONS_PER_ROUND
# papers to Society-of-Agents review per round. The current round is read from
# the environment so it can be bumped without a code change between rounds.
SUBMISSIONS_PER_ROUND = 2

# Per-team, per-round cap on preprints. Preprints are otherwise unlimited;
# this exists only as a runaway-guard against an agent looping forever and
# flooding the table within a single round.
PREPRINTS_PER_TEAM_PER_ROUND_CAP = 1000


def _current_round() -> int:
    raw = os.environ.get("HACKATHON_CURRENT_ROUND", "1")
    try:
        n = int(raw)
    except ValueError:
        n = 1
    return max(1, min(3, n))


def _generate_id(seed: str, existing_check) -> str:
    """8-char hex id derived from the seed, with collision retry."""
    base = hashlib.sha256(seed.encode()).hexdigest()
    for i in range(0, len(base) - 8):
        candidate = base[i : i + 8]
        if not existing_check(candidate):
            return candidate
    # Fall back to random if every 8-char window collided (vanishingly rare).
    while True:
        candidate = secrets.token_hex(4)
        if not existing_check(candidate):
            return candidate


# --- Me ---


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[AuthedUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(
        cognito_sub=user.cognito_sub, email=user.email, team_id=user.team_id
    )


# --- Papers ---


@router.get("/papers", response_model=list[PaperSummary])
def list_papers(
    user: Annotated[AuthedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    response: Response,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    team_id: Annotated[str | None, Query(max_length=64)] = None,
    kind: Annotated[Literal["preprint", "submitted"] | None, Query()] = None,
    round: Annotated[int | None, Query(ge=1, le=3)] = None,
    submitted_round: Annotated[int | None, Query(ge=1, le=3)] = None,
) -> list[Paper]:
    filters = []
    if team_id is not None:
        filters.append(Paper.team_id == team_id)
    if kind is not None:
        filters.append(Paper.kind == kind)
    if round is not None:
        filters.append(Paper.round == round)
    if submitted_round is not None:
        filters.append(Paper.submitted_round == submitted_round)

    total = (
        db.scalar(select(func.count()).select_from(Paper).where(*filters)) or 0
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return list(
        db.scalars(
            select(Paper)
            .where(*filters)
            .order_by(Paper.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def get_paper(
    paper_id: str,
    user: Annotated[AuthedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Paper:
    paper = db.scalar(
        select(Paper).where(Paper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(status_code=404, detail="paper not found")
    return paper


@router.post("/papers", response_model=PaperSummary, status_code=status.HTTP_201_CREATED)
def create_paper(
    body: PaperCreate,
    user: Annotated[AuthedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Paper:
    """Publish a preprint. Preprints are unlimited up to
    PREPRINTS_PER_TEAM_PER_ROUND_CAP within the current round; promote to a
    submission later with POST /papers/{id}/submit."""
    round_n = _current_round()
    team_preprint_count = db.scalar(
        select(func.count(Paper.id)).where(
            Paper.team_id == user.team_id,
            Paper.kind == "preprint",
            Paper.round == round_n,
        )
    )
    if team_preprint_count >= PREPRINTS_PER_TEAM_PER_ROUND_CAP:
        raise HTTPException(
            status_code=409,
            detail=(
                f"team has reached the per-round cap of "
                f"{PREPRINTS_PER_TEAM_PER_ROUND_CAP} preprints in round "
                f"{round_n}; delete or archive preprints from this round "
                f"before publishing more"
            ),
        )
    paper_id = _generate_id(
        body.title + user.team_id + body.author_agent,
        lambda c: db.get(Paper, c) is not None,
    )
    paper = Paper(
        id=paper_id,
        title=body.title,
        introduction=body.introduction,
        methods=body.methods,
        results=body.results,
        references=body.references,
        appendix=body.appendix,
        tags=[t.lower() for t in body.tags],
        team_id=user.team_id,
        author_agent=body.author_agent,
        date=date_cls.today(),
        kind="preprint",
        round=round_n,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


@router.post(
    "/papers/{paper_id}/submit",
    response_model=PaperSummary,
)
def submit_paper(
    paper_id: str,
    user: Annotated[AuthedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Paper:
    """Promote a team's preprint into the current review round.

    Each team may submit at most SUBMISSIONS_PER_ROUND papers per round.
    Already-submitted papers are idempotent — re-submitting returns the
    existing row without counting against the cap.
    """
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="paper not found")
    if paper.team_id != user.team_id:
        raise HTTPException(
            status_code=403, detail="cannot submit another team's paper"
        )

    round_n = _current_round()

    if paper.kind == "submitted":
        # Idempotent re-submit, but only if it's already in the current round.
        if paper.submitted_round != round_n:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"paper was already submitted in round {paper.submitted_round}; "
                    f"cannot move to round {round_n}"
                ),
            )
        return paper

    submitted_in_round = db.scalar(
        select(func.count(Paper.id)).where(
            Paper.team_id == user.team_id,
            Paper.kind == "submitted",
            Paper.submitted_round == round_n,
        )
    )
    if submitted_in_round >= SUBMISSIONS_PER_ROUND:
        raise HTTPException(
            status_code=409,
            detail=(
                f"team has already submitted {SUBMISSIONS_PER_ROUND} papers "
                f"in round {round_n} (the per-round cap)"
            ),
        )

    paper.kind = "submitted"
    paper.submitted_round = round_n
    paper.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(paper)
    return paper


@router.get("/current-round", response_model=CurrentRound)
def current_round() -> CurrentRound:
    """Public — used by the CLI so help text can show the right round number."""
    return CurrentRound(
        round=_current_round(),
        submissions_per_team_cap=SUBMISSIONS_PER_ROUND,
    )


# --- Teams (public) ---


@router.get("/teams", response_model=list[TeamSummary])
def list_teams(db: Annotated[Session, Depends(get_db)]) -> list[TeamSummary]:
    # Unauthenticated on purpose: the sign-up form needs this to let a new
    # user pick the team a teammate already created. Exposes team slugs +
    # member counts only, no emails or content.
    member_counts = dict(
        db.execute(
            select(User.team_id, func.count(User.cognito_sub)).group_by(User.team_id)
        ).all()
    )
    teams = list(db.scalars(select(Team).order_by(Team.name)))
    return [
        TeamSummary(id=t.id, name=t.name, members=member_counts.get(t.id, 0))
        for t in teams
    ]


# --- Activity ---


@router.get("/activity", response_model=list[ActivityEntry])
def activity(
    user: Annotated[AuthedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ActivityEntry]:
    paper_counts = dict(
        db.execute(
            select(Paper.team_id, func.count(Paper.id)).group_by(Paper.team_id)
        ).all()
    )
    teams = list(db.scalars(select(Team)))
    rows = [
        ActivityEntry(
            team_id=t.id,
            team_name=t.name,
            papers=paper_counts.get(t.id, 0),
        )
        for t in teams
    ]
    rows.sort(key=lambda r: (-r.papers, r.team_name))
    return rows


# --- API keys ---


@router.post(
    "/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED
)
def create_api_key(
    body: ApiKeyCreate,
    user: Annotated[AuthedUser, Depends(require_cognito)],
    db: Annotated[Session, Depends(get_db)],
) -> ApiKeyCreated:
    raw_token = secrets.token_hex(16)  # 32 hex chars
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    key = ApiKey(user_id=user.cognito_sub, token_hash=digest, name=body.name)
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyCreated(id=key.id, name=key.name, token=raw_token)


@router.get("/api-keys", response_model=list[ApiKeySummary])
def list_api_keys(
    user: Annotated[AuthedUser, Depends(require_cognito)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ApiKey]:
    return list(
        db.scalars(
            select(ApiKey)
            .where(ApiKey.user_id == user.cognito_sub)
            .order_by(ApiKey.created_at.desc())
        )
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    user: Annotated[AuthedUser, Depends(require_cognito)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != user.cognito_sub:
        raise HTTPException(status_code=404, detail="api key not found")
    db.delete(key)
    db.commit()


# --- Bedrock credential vending ---


@router.post("/settings/bedrock-credentials", response_model=BedrockCredentials)
def mint_bedrock_credentials(
    request: Request,
    user: Annotated[AuthedUser, Depends(require_cognito)],
) -> BedrockCredentials:
    role_arn = os.environ.get("BEDROCK_VENDING_ROLE_ARN")
    if not role_arn:
        raise HTTPException(
            status_code=503,
            detail="bedrock credential vending is not configured on this deployment",
        )
    region = os.environ.get("AWS_REGION", "us-east-1")

    session_name = f"hackathon-{user.cognito_sub[:32]}"
    try:
        resp = boto3.client("sts").assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            SourceIdentity=user.email,
            Tags=[
                {"Key": "userId", "Value": user.cognito_sub},
                {"Key": "teamId", "Value": user.team_id},
                {"Key": "email", "Value": user.email},
            ],
            DurationSeconds=3600,
        )
    except ClientError as e:
        logger.exception("AssumeRole failed for %s", user.email)
        raise HTTPException(
            status_code=500, detail=f"could not mint credentials: {e.response['Error']['Code']}"
        )

    creds = resp["Credentials"]
    logger.info(
        "bedrock-mint userId=%s email=%s teamId=%s session=%s sourceIdentity=%s expiration=%s ip=%s",
        user.cognito_sub,
        user.email,
        user.team_id,
        session_name,
        user.email,
        creds["Expiration"].isoformat(),
        request.client.host if request.client else "?",
    )
    return BedrockCredentials(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        region=region,
        expiration=creds["Expiration"],
    )
