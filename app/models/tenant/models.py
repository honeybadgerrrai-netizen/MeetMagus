"""Tenant-specific models.

These are defined without schema= so they work in SQLite.
In Postgres, the session search_path is set to tenant_{id} at connection time.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float,
    ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class TenantBase(DeclarativeBase):
    """Separate base per tenant (same class, different schema via search_path)."""


class RelationshipTier(str, enum.Enum):
    CLOSE = "close"
    WARM = "warm"
    ACQUAINTANCE = "acquaintance"
    COLD = "cold"


class WillingnessToHelp(str, enum.Enum):
    ADVOCATE = "advocate"
    INTRO = "intro"
    REFERENCE_ONLY = "reference_only"
    UNKNOWN = "unknown"
    NO = "no"


class CapabilityScope(str, enum.Enum):
    INDIVIDUAL = "individual"
    FIRM = "firm"


class CapabilityCategory(str, enum.Enum):
    M_AND_A_ADVISORY = "m_and_a_advisory"
    SELL_SIDE = "sell_side"
    BUY_SIDE = "buy_side"
    ECM = "ecm"
    DCM = "dcm"
    LEVERAGED_FINANCE = "leveraged_finance"
    RESTRUCTURING = "restructuring"
    PRIVATE_PLACEMENT = "private_placement"
    FAIRNESS_OPINION = "fairness_opinion"
    SECTOR_COVERAGE = "sector_coverage"
    GEO_COVERAGE = "geo_coverage"
    OTHER = "other"


class Banker(TenantBase):
    __tablename__ = "bankers"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    employer_company_id: Mapped[int | None] = mapped_column(Integer)  # global.companies.id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contacts: Mapped[list["Contact"]] = relationship(back_populates="banker", cascade="all, delete-orphan")
    capabilities: Mapped[list["Capability"]] = relationship(back_populates="banker", cascade="all, delete-orphan")
    context_notes: Mapped[list["ContextNote"]] = relationship(back_populates="banker", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="banker", cascade="all, delete-orphan")


class Contact(TenantBase):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("relationship_score >= 1 AND relationship_score <= 10", name="ck_score_range"),
        Index("ix_contacts_banker_tier", "banker_id", "relationship_tier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    banker_id: Mapped[int] = mapped_column(ForeignKey("bankers.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    employer_name: Mapped[str | None] = mapped_column(String(255))
    employer_company_id: Mapped[int | None] = mapped_column(Integer)  # global.companies.id
    employer_title: Mapped[str | None] = mapped_column(String(255))
    relationship_score: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    relationship_tier: Mapped[str] = mapped_column(String(20), default="acquaintance", nullable=False)
    willingness_to_help: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_contact_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    linked_person_id: Mapped[int | None] = mapped_column(Integer, index=True)  # global.people.id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    banker: Mapped[Banker] = relationship(back_populates="contacts")


class Capability(TenantBase):
    __tablename__ = "capabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    banker_id: Mapped[int] = mapped_column(ForeignKey("bankers.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # individual | firm
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sector_focus: Mapped[str | None] = mapped_column(String(120))
    geo_focus: Mapped[str | None] = mapped_column(String(120))
    deal_size_min_usd: Mapped[float | None] = mapped_column(Float)
    deal_size_max_usd: Mapped[float | None] = mapped_column(Float)
    track_record_count: Mapped[int | None] = mapped_column(Integer)
    # For firm-level capabilities: which company
    firm_company_id: Mapped[int | None] = mapped_column(Integer)  # global.companies.id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    banker: Mapped[Banker] = relationship(back_populates="capabilities")
    events: Mapped[list["CapabilityEvent"]] = relationship(back_populates="capability", cascade="all, delete-orphan")


class CapabilityEvent(TenantBase):
    """Publicly observed deal or announcement that substantiates a capability."""
    __tablename__ = "capability_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # closed_deal | league_table | press_release
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deal_size_usd: Mapped[float | None] = mapped_column(Float)
    sector: Mapped[str | None] = mapped_column(String(120))
    counterparty_company_id: Mapped[int | None] = mapped_column(Integer)  # global.companies.id
    announced_at: Mapped[str | None] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    capability: Mapped[Capability] = relationship(back_populates="events")


class ContextNote(TenantBase):
    """Free-form banker notes, tagged to companies and/or people."""
    __tablename__ = "context_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    banker_id: Mapped[int] = mapped_column(ForeignKey("bankers.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False, default="BANKER")  # BANKER | AI
    ai_source_id: Mapped[str | None] = mapped_column(String(100))  # if AI: which ingestion source
    is_standing_preference: Mapped[bool] = mapped_column(Boolean, default=False)
    # Tags — stored as comma-separated IDs for SQLite compat; use junction table in Postgres
    tagged_company_ids: Mapped[str | None] = mapped_column(Text)  # "1,2,3"
    tagged_person_ids: Mapped[str | None] = mapped_column(Text)   # "4,5"
    embedding_json: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    banker: Mapped[Banker] = relationship(back_populates="context_notes")


class Alert(TenantBase):
    """Agent-generated alert for a banker."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    banker_id: Mapped[int] = mapped_column(ForeignKey("bankers.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_run_id: Mapped[int | None] = mapped_column(Integer)  # platform.workflow_runs.id
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 13d_filing | debt_maturity | etc
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # full agent briefing
    cited_sources: Mapped[str | None] = mapped_column(Text)  # JSON array of source refs
    target_company_id: Mapped[int | None] = mapped_column(Integer)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="unread")  # unread | read | acted | dismissed
    banker_feedback: Mapped[str | None] = mapped_column(String(20))  # acted | dismissed | wrong
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    banker: Mapped[Banker] = relationship(back_populates="alerts")
