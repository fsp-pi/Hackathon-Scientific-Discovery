"""Pydantic request/response schemas. Wire format for the SPA and CLI."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Papers ---


class PaperBase(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    introduction: str = Field(min_length=1)
    methods: str = Field(min_length=1)
    results: str = Field(min_length=1)
    references: str = Field(default="")
    appendix: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class PaperCreate(PaperBase):
    author_agent: str = Field(min_length=1, max_length=128)


class PaperSummary(BaseModel):
    id: str
    title: str
    introduction: str
    tags: list[str]
    team_id: str
    author_agent: str
    date: date
    created_at: datetime
    kind: str = "preprint"  # "preprint" or "submitted"
    round: int = 1  # round the paper was created in
    submitted_round: int | None = None

    class Config:
        from_attributes = True


class PaperDetail(PaperSummary):
    methods: str
    results: str
    references: str
    appendix: str


class CurrentRound(BaseModel):
    round: int
    submissions_per_team_cap: int


# --- Teams / activity ---


class ActivityEntry(BaseModel):
    team_id: str
    team_name: str
    papers: int


class TeamSummary(BaseModel):
    id: str
    name: str
    members: int


# --- Me ---


class MeResponse(BaseModel):
    cognito_sub: str
    email: str
    team_id: str


# --- API keys ---


class ApiKeyCreate(BaseModel):
    name: str = Field(default="", max_length=255)


class ApiKeyCreated(BaseModel):
    """Returned exactly once; the raw token is never stored."""

    id: int
    name: str
    token: str  # raw token — show to user, then forget


class ApiKeySummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_used_at: datetime | None

    class Config:
        from_attributes = True


# --- Bedrock credential vending ---


class BedrockCredentials(BaseModel):
    """1-hour STS credentials minted via AssumeRole. Returned exactly once."""

    access_key_id: str
    secret_access_key: str
    session_token: str
    region: str
    expiration: datetime
