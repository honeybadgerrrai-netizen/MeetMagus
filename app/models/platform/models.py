"""Platform infrastructure models."""
from __future__ import annotations
import os
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import PlatformBase

IS_PG = not os.getenv("DATABASE_URL", "sqlite").startswith("sqlite")
PLAT = {"schema": "platform"} if IS_PG else {}

class SourceRegistry(PlatformBase):
    __tablename__ = "source_registry"
    __table_args__ = PLAT
    source_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    can_store_raw: Mapped[bool] = mapped_column(Boolean, default=True)
    can_display_to_user: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_attribution: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int | None] = mapped_column(Integer)
    reliability_rank: Mapped[int] = mapped_column(Integer, default=5)
    dedup_threshold: Mapped[float] = mapped_column(Float, default=0.92)
    notes: Mapped[str | None] = mapped_column(Text)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SourceMonitor(PlatformBase):
    __tablename__ = "source_monitors"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_cadence_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class RawIngestion(PlatformBase):
    __tablename__ = "raw_ingestions"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(50))
    raw_content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    fetch_status: Mapped[str] = mapped_column(String(20), default="success")
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")
    extraction_run_id: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class WorkflowDefinition(PlatformBase):
    __tablename__ = "workflow_definitions"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    steps_json: Mapped[str] = mapped_column(Text, nullable=False)
    retry_max: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class WorkflowRun(PlatformBase):
    __tablename__ = "workflow_runs"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    definition_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(50), index=True)
    trigger_payload: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), index=True)
    is_eval: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class WorkflowStep(PlatformBase):
    __tablename__ = "workflow_steps"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input_payload: Mapped[str | None] = mapped_column(Text)
    output_payload: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer)
    llm_cost_usd: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class JobQueue(PlatformBase):
    __tablename__ = "job_queue"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    tenant_id: Mapped[str | None] = mapped_column(String(50), index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class LLMBudget(PlatformBase):
    __tablename__ = "llm_budgets"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    daily_limit_usd: Mapped[float] = mapped_column(Float, default=10.0)
    consumed_today_usd: Mapped[float] = mapped_column(Float, default=0.0)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class FreshnessPolicy(PlatformBase):
    __tablename__ = "freshness_policies"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    observation_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    stale_after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    critical_after_days: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class DedupLog(PlatformBase):
    __tablename__ = "dedup_log"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    incoming_content: Mapped[str] = mapped_column(Text)
    matched_observation_id: Mapped[int | None] = mapped_column(Integer)
    similarity_score: Mapped[float] = mapped_column(Float)
    threshold_used: Mapped[float] = mapped_column(Float)
    source_id: Mapped[str | None] = mapped_column(String(100))
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EntityResolutionQueue(PlatformBase):
    __tablename__ = "entity_resolution_queue"
    __table_args__ = PLAT
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_entity_id: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(255))
    context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
