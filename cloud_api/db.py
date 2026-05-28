"""SQLAlchemy setup and ORM models."""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Generator

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


def _database_url() -> str:
    user = os.environ["DB_USERNAME"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ["DB_HOST"]
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


engine = create_engine(_database_url(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- ORM models ---


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug, same as name
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    papers: Mapped[list["Paper"]] = relationship(back_populates="team")
    users: Mapped[list["User"]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"

    # Cognito's `sub` claim is the stable user id. We don't allocate our own.
    cognito_sub: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    team: Mapped["Team"] = relationship(back_populates="users")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.cognito_sub", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    introduction: Mapped[str] = mapped_column(Text, nullable=False)
    methods: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[str] = mapped_column(Text, nullable=False, default="")
    appendix: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    team_id: Mapped[str] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False
    )
    author_agent: Mapped[str] = mapped_column(String(128), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # "preprint" (default) or "submitted". Preprints are unlimited; teams
    # promote up to 3 preprints per round into "submitted" for Society-of-Agents
    # review.
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="preprint", server_default="preprint"
    )
    # The hackathon round this paper was created in. Used to enforce the
    # per-team, per-round preprint cap.
    round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    submitted_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    team: Mapped["Team"] = relationship(back_populates="papers")


def _migrate_papers_schema() -> None:
    """Idempotent fix-up for `papers` schema drift from the original v1 columns.

    `Base.metadata.create_all` only adds missing *tables*, not missing columns,
    so a deploy that renamed/added columns leaves earlier prod tables broken.
    """
    with engine.begin() as conn:
        exists = conn.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'papers')"
            )
        )
        if not exists:
            return

        cols = set(
            conn.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'papers'"
                )
            ).all()
        )

        if "abstract" in cols and "introduction" not in cols:
            conn.execute(text("ALTER TABLE papers RENAME COLUMN abstract TO introduction"))
        elif "introduction" not in cols:
            conn.execute(
                text("ALTER TABLE papers ADD COLUMN introduction TEXT NOT NULL DEFAULT ''")
            )
        if "references" not in cols:
            conn.execute(
                text('ALTER TABLE papers ADD COLUMN "references" TEXT NOT NULL DEFAULT \'\'')
            )
        if "appendix" not in cols:
            conn.execute(
                text("ALTER TABLE papers ADD COLUMN appendix TEXT NOT NULL DEFAULT ''")
            )
        if "kind" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE papers ADD COLUMN kind VARCHAR(16) NOT NULL "
                    "DEFAULT 'preprint'"
                )
            )
        if "round" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE papers ADD COLUMN round INTEGER NOT NULL DEFAULT 1"
                )
            )
        if "submitted_round" not in cols:
            conn.execute(text("ALTER TABLE papers ADD COLUMN submitted_round INTEGER"))
        if "submitted_at" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE papers ADD COLUMN submitted_at TIMESTAMP WITH TIME ZONE"
                )
            )


def init_db() -> None:
    """Create all tables. Called from the FastAPI lifespan on first boot.

    For v1 simplicity we use create_all rather than Alembic migrations.
    Schema is additive-only so this is safe across restarts; once we have
    user data we can introduce Alembic without losing anything.
    """
    Base.metadata.create_all(bind=engine)
    _migrate_papers_schema()
