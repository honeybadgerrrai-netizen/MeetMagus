"""DealFlow Backend — Investment Banker Intelligence Platform.

Three schema layers:
  global   → companies, people, affiliations, observations, intelligence
  tenant_X → banker, contacts, notes, alerts, capabilities
  platform → workflows, job queue, source registry, budgets

Run: uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.models.global_schema.entities  # noqa: registers with GlobalBase
import app.models.global_schema.observations  # noqa
import app.models.platform.models  # noqa: registers with PlatformBase
import app.models.tenant.models  # noqa
from app.core.db import GlobalBase, PlatformBase, SessionLocal, engine
from app.models.tenant.models import TenantBase
from app.routers import (
    admin, alerts, capabilities, companies, contacts,
    ingestion, notes, observations, people, warm_paths,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bootstrap schemas and tables on startup
    with SessionLocal() as db:
        try:
            db.execute(text("CREATE SCHEMA IF NOT EXISTS global"))
            db.execute(text("CREATE SCHEMA IF NOT EXISTS platform"))
            db.commit()
        except Exception:
            db.rollback()

    GlobalBase.metadata.create_all(bind=engine)
    PlatformBase.metadata.create_all(bind=engine)
    TenantBase.metadata.create_all(bind=engine)  # for SQLite dev
    yield


app = FastAPI(
    title="DealFlow",
    description=(
        "Investment banker intelligence platform. "
        "Tracks prospects, networks, capabilities, and AI-ingested company intelligence."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/schema", tags=["meta"])
def schema_overview():
    return {
        "global": ["companies", "people", "affiliations", "company_relationships",
                   "sectors", "company_aliases", "person_aliases",
                   "obs_macro", "obs_financial", "obs_investor", "obs_competitive",
                   "obs_customer", "obs_employee", "obs_public_market", "key_dates"],
        "tenant": ["bankers", "contacts", "capabilities", "capability_events",
                   "context_notes", "alerts"],
        "platform": ["source_registry", "source_monitors", "raw_ingestions",
                     "workflow_definitions", "workflow_runs", "workflow_steps",
                     "job_queue", "llm_budgets", "freshness_policies",
                     "dedup_log", "entity_resolution_queue"],
    }


# Global prospect universe
app.include_router(companies.router)
app.include_router(people.router)
app.include_router(observations.router)

# Tenant network
app.include_router(contacts.router)
app.include_router(capabilities.router)
app.include_router(notes.router)
app.include_router(alerts.router)
app.include_router(warm_paths.router)

# Admin
app.include_router(admin.router)

# Ingestion
app.include_router(ingestion.router)
