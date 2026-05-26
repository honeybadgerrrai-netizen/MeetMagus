"""Global schema: Company, Person, Affiliation, CompanyRelationship, Sector."""
from __future__ import annotations
import enum, os
from datetime import datetime
from sqlalchemy import (Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import GlobalBase

IS_PG = not os.getenv("DATABASE_URL", "sqlite").startswith("sqlite")
GLOBAL = {"schema": "global"} if IS_PG else {}
PK = "global.companies" if IS_PG else "companies"
PP = "global.people" if IS_PG else "people"
SS = "global.sectors" if IS_PG else "sectors"

class Sector(GlobalBase):
    __tablename__ = "sectors"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    parent_sector_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SS}.id"))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    companies: Mapped[list["Company"]] = relationship(back_populates="sector")

class Company(GlobalBase):
    __tablename__ = "companies"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    company_type: Mapped[str] = mapped_column(String(30), default="private", nullable=False)
    sector_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SS}.id"))
    sub_industry: Mapped[str | None] = mapped_column(String(120))
    hq_city: Mapped[str | None] = mapped_column(String(120))
    hq_country: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(255))
    ticker: Mapped[str | None] = mapped_column(String(16), index=True)
    is_prospect: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    employee_count: Mapped[int | None] = mapped_column(Integer)
    revenue_usd: Mapped[float | None] = mapped_column(Float)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    sector: Mapped["Sector | None"] = relationship(back_populates="companies")
    affiliations: Mapped[list["Affiliation"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    aliases: Mapped[list["CompanyAlias"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    relationships_as_source: Mapped[list["CompanyRelationship"]] = relationship(
        back_populates="source_company", foreign_keys="CompanyRelationship.source_company_id", cascade="all, delete-orphan")

class CompanyAlias(GlobalBase):
    __tablename__ = "company_aliases"
    __table_args__ = (UniqueConstraint("alias", name="uq_company_alias"), GLOBAL) if IS_PG else (UniqueConstraint("alias", name="uq_company_alias"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey(f"{PK}.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[str | None] = mapped_column(String(255))
    confirmed_by: Mapped[str | None] = mapped_column(String(255))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    company: Mapped[Company] = relationship(back_populates="aliases")

class Person(GlobalBase):
    __tablename__ = "people"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64))
    linkedin_url: Mapped[str | None] = mapped_column(String(255))
    location_city: Mapped[str | None] = mapped_column(String(120))
    location_country: Mapped[str | None] = mapped_column(String(120))
    is_prospect: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    affiliations: Mapped[list["Affiliation"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    aliases: Mapped[list["PersonAlias"]] = relationship(back_populates="person", cascade="all, delete-orphan")

class PersonAlias(GlobalBase):
    __tablename__ = "person_aliases"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{PP}.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    source: Mapped[str | None] = mapped_column(String(255))
    confirmed_by: Mapped[str | None] = mapped_column(String(255))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person: Mapped[Person] = relationship(back_populates="aliases")

class Affiliation(GlobalBase):
    __tablename__ = "affiliations"
    __table_args__ = (Index("ix_aff_company_role_current", "company_id", "role_type", "is_current"), GLOBAL) if IS_PG else (Index("ix_aff_company_role_current", "company_id", "role_type", "is_current"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey(f"{PP}.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[int] = mapped_column(ForeignKey(f"{PK}.id", ondelete="CASCADE"), nullable=False)
    role_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    person: Mapped[Person] = relationship(back_populates="affiliations")
    company: Mapped[Company] = relationship(back_populates="affiliations")

class CompanyRelationship(GlobalBase):
    __tablename__ = "company_relationships"
    __table_args__ = GLOBAL
    id: Mapped[int] = mapped_column(primary_key=True)
    source_company_id: Mapped[int] = mapped_column(ForeignKey(f"{PK}.id", ondelete="CASCADE"), nullable=False)
    target_company_id: Mapped[int] = mapped_column(ForeignKey(f"{PK}.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_company: Mapped[Company] = relationship(back_populates="relationships_as_source", foreign_keys=[source_company_id])
    target_company: Mapped["Company"] = relationship(foreign_keys=[target_company_id])
