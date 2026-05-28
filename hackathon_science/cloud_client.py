"""HTTP client for the cloud API.

Read the API base URL + API key from ``~/.hackathon-science/credentials``
(written by `hackathon login`). Each method maps to one endpoint and returns
the parsed JSON.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import toml

CREDENTIALS_PATH = Path.home() / ".hackathon-science" / "credentials"

# Where the cloud API lives when nothing more specific is configured. Used as
# the default for `hackathon login --api-url`. Bump this when the platform
# moves to a new domain.
DEFAULT_API_URL = "https://flagship-hackathon.com"


@dataclass
class Credentials:
    api_url: str
    api_key: str


class NotLoggedInError(RuntimeError):
    pass


def load_credentials() -> Credentials:
    # Env vars override the file so CI can use them without touching $HOME.
    env_url = os.environ.get("HACKATHON_API_URL")
    env_key = os.environ.get("HACKATHON_API_KEY")
    if env_url and env_key:
        return Credentials(api_url=env_url.rstrip("/"), api_key=env_key)

    if not CREDENTIALS_PATH.exists():
        raise NotLoggedInError(
            f"No credentials found at {CREDENTIALS_PATH}. Run `hackathon login` first."
        )
    data = toml.load(CREDENTIALS_PATH)
    try:
        return Credentials(api_url=data["api_url"].rstrip("/"), api_key=data["api_key"])
    except KeyError as e:
        raise NotLoggedInError(f"Credentials file is malformed: missing {e}")


def save_credentials(api_url: str, api_key: str) -> None:
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(
        toml.dumps({"api_url": api_url.rstrip("/"), "api_key": api_key})
    )
    CREDENTIALS_PATH.chmod(0o600)


class CloudClient:
    def __init__(self, creds: Credentials | None = None) -> None:
        creds = creds or load_credentials()
        # The CloudFront distribution exposes the API under /api/*. Accept
        # either form from the user — with or without the /api suffix — so
        # `hackathon login --api-url https://flagship-hackathon.com` Just Works.
        base = creds.api_url.rstrip("/")
        if not base.endswith("/api"):
            base = f"{base}/api"
        self.creds = Credentials(api_url=base, api_key=creds.api_key)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.creds.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.creds.api_url}{path}"

    def _check(self, resp: requests.Response) -> Any:
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise RuntimeError(f"{resp.status_code} {detail}")
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            ctype = resp.headers.get("content-type", "?")
            snippet = resp.text[:200]
            raise RuntimeError(
                f"{resp.status_code} non-JSON response (content-type={ctype}): {snippet}"
            )

    def me(self) -> dict:
        return self._check(self._session.get(self._url("/me"), timeout=15))

    def list_papers(
        self,
        page_size: int = 200,
        team_id: str | None = None,
        kind: str | None = None,
        round: int | None = None,
        submitted_round: int | None = None,
    ) -> list[dict]:
        # /papers is paginated server-side; auto-page through to preserve the
        # historical "give me everything" contract used by the CLI.
        out: list[dict] = []
        offset = 0
        while True:
            params: dict[str, Any] = {"limit": page_size, "offset": offset}
            if team_id is not None:
                params["team_id"] = team_id
            if kind is not None:
                params["kind"] = kind
            if round is not None:
                params["round"] = round
            if submitted_round is not None:
                params["submitted_round"] = submitted_round
            resp = self._session.get(
                self._url("/papers"),
                params=params,
                timeout=30,
            )
            chunk = self._check(resp) or []
            out.extend(chunk)
            if len(chunk) < page_size:
                return out
            offset += page_size

    def web_base(self) -> str:
        """Web origin for paper links (the API URL minus the /api suffix)."""
        return self.creds.api_url.removesuffix("/api")

    def count_papers(
        self,
        team_id: str | None = None,
        kind: str | None = None,
        round: int | None = None,
        submitted_round: int | None = None,
    ) -> int:
        """Return how many papers match the filters, via the X-Total-Count
        header — cheaper than fetching them all just to len() the result."""
        params: dict[str, Any] = {"limit": 1, "offset": 0}
        if team_id is not None:
            params["team_id"] = team_id
        if kind is not None:
            params["kind"] = kind
        if round is not None:
            params["round"] = round
        if submitted_round is not None:
            params["submitted_round"] = submitted_round
        resp = self._session.get(self._url("/papers"), params=params, timeout=15)
        self._check(resp)
        return int(resp.headers.get("X-Total-Count", "0"))

    def get_paper(self, paper_id: str) -> dict:
        return self._check(self._session.get(self._url(f"/papers/{paper_id}"), timeout=15))

    def publish_paper(self, paper: dict) -> dict:
        return self._check(
            self._session.post(self._url("/papers"), json=paper, timeout=30)
        )

    def submit_paper(self, paper_id: str) -> dict:
        return self._check(
            self._session.post(
                self._url(f"/papers/{paper_id}/submit"), timeout=15
            )
        )

    def current_round(self) -> dict:
        return self._check(
            self._session.get(self._url("/current-round"), timeout=10)
        )

    def activity(self) -> list[dict]:
        return self._check(self._session.get(self._url("/activity"), timeout=15))
