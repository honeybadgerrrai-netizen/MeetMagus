"""Intelligence layer: separate observation tables per category."""
from __future__ import annotations
import os
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import GlobalBase

IS_PG = not os.getenv("DATABASE_URL", "sqlite").startswith("sqlite")
GLOBAL = {"schema": "global"} if IS_PG else {}
PK = "global.companies" if IS_PG else "companies"
PP = "global.people" if IS_PG else "people"

class ObsMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    raw_ingestion_id: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    superseded_by: Mapped[int | None] = mapped_column(Integer)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedup_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class MacroObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_macro"
    __table_args__ = GLOBAL
    trend_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trend_description: Mapped[str | None] = mapped_column(Text)
    relevance_note: Mapped[str | None] = mapped_column(Text)
    impact_direction: Mapped[str | None] = mapped_column(String(20))
    sector_scope: Mapped[str | None] = mapped_column(String(120))
    @property
    def headline(self): return self.trend_name

class FinancialObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_financial"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    amount_usd: Mapped[float | None] = mapped_column(Float)
    metric_name: Mapped[str | None] = mapped_column(String(100))
    metric_value: Mapped[float | None] = mapped_column(Float)
    metric_unit: Mapped[str | None] = mapped_column(String(50))

class InvestorObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_investor"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    investor_name: Mapped[str | None] = mapped_column(String(255))
    investor_company_id: Mapped[int | None] = mapped_column(Integer)
    stake_pct: Mapped[float | None] = mapped_column(Float)
    filing_type: Mapped[str | None] = mapped_column(String(20))
    is_activist: Mapped[bool] = mapped_column(Boolean, default=False)

class CompetitiveObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_competitive"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    competitor_company_id: Mapped[int | None] = mapped_column(Integer)
    product_overlap_note: Mapped[str | None] = mapped_column(Text)

class CustomerObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_customer"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    customer_company_id: Mapped[int | None] = mapped_column(Integer)
    contract_value_usd: Mapped[float | None] = mapped_column(Float)

class EmployeeObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_employee"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(120))
    headcount_total: Mapped[int | None] = mapped_column(Integer)
    headcount_delta: Mapped[int | None] = mapped_column(Integer)
    open_roles_count: Mapped[int | None] = mapped_column(Integer)
    person_id: Mapped[int | None] = mapped_column(Integer)

class PublicMarketObservation(GlobalBase, ObsMixin):
    __tablename__ = "obs_public_market"
    __table_args__ = GLOBAL
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    analyst_firm: Mapped[str | None] = mapped_column(String(255))
    analyst_name: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[str | None] = mapped_column(String(50))
    price_target_usd: Mapped[float | None] = mapped_column(Float)
    stock_price_usd: Mapped[float | None] = mapped_column(Float)
    short_interest_pct: Mapped[float | None] = mapped_column(Float)
    metric_name: Mapped[str | None] = mapped_column(String(100))
    metric_value: Mapped[float | None] = mapped_column(Float)

class KeyDate(GlobalBase):
    __tablename__ = "key_dates"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_date: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="active")
    superseded_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
