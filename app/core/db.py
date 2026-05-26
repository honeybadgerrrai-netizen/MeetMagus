"""Database engine, session, and multi-schema base classes.

Schema layout:
  global   — Company, Person, Affiliations, Observations, Intelligence
  tenant_X — Banker, Contacts, Notes, Alerts, Capabilities (one per customer)
  platform — Workflows, JobQueue, Budgets, SourceRegistry (infrastructure)
"""
from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dealflow.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class GlobalBase(DeclarativeBase):
    """Base for all global-schema models."""


class PlatformBase(DeclarativeBase):
    """Base for platform-schema infrastructure models."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_tenant_session(tenant_id: str) -> Generator[Session, None, None]:
    """Session scoped to a specific tenant schema."""
    db = SessionLocal()
    try:
        if not DATABASE_URL.startswith("sqlite"):
            db.execute(text(f"SET search_path TO tenant_{tenant_id}, global, platform, public"))
        yield db
    finally:
        db.close()


def create_schemas(db: Session) -> None:
    """Create global and platform schemas (Postgres only)."""
    if DATABASE_URL.startswith("sqlite"):
        return
    for schema in ["global", "platform"]:
        db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    db.commit()


def create_tenant_schema(tenant_id: str) -> None:
    """Provision a new tenant schema."""
    with SessionLocal() as db:
        if not DATABASE_URL.startswith("sqlite"):
            db.execute(text(f"CREATE SCHEMA IF NOT EXISTS tenant_{tenant_id}"))
            db.commit()
