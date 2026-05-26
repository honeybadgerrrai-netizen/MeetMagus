from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.global_schema.observations import (
    MacroObservation, FinancialObservation, InvestorObservation,
    CompetitiveObservation, CustomerObservation, EmployeeObservation,
    PublicMarketObservation, KeyDate
)
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/observations", tags=["observations"])

class ObsIn(BaseModel):
    company_id: int; observed_at: datetime; source_id: str = "manual"
    source_url: Optional[str] = None; confidence: float = 0.8
    headline: str; detail: Optional[str] = None
    signal_type: Optional[str] = None

class ObsOut(BaseModel):
    id: int; company_id: int; observed_at: datetime; source_id: str
    confidence: float; status: str; headline: str; detail: Optional[str]
    created_at: datetime
    class Config: from_attributes = True

OBS_MAP = {
    "macro": MacroObservation, "financial": FinancialObservation,
    "investor": InvestorObservation, "competitive": CompetitiveObservation,
    "customer": CustomerObservation, "employee": EmployeeObservation,
    "public_market": PublicMarketObservation,
}

@router.post("/{obs_type}", response_model=ObsOut, status_code=201)
def create_observation(obs_type: str, payload: ObsIn, db: Session = Depends(get_db)):
    model = OBS_MAP.get(obs_type)
    if not model: raise ValueError(f"Unknown type: {obs_type}")
    data = payload.model_dump()
    if obs_type == "macro": data["trend_name"] = data.pop("headline")
    obs = model(**{k: v for k, v in data.items() if hasattr(model, k)})
    if obs_type == "macro": obs.trend_name = payload.headline
    obs.company_id = payload.company_id; obs.observed_at = payload.observed_at
    obs.source_id = payload.source_id; obs.confidence = payload.confidence
    db.add(obs); db.commit(); db.refresh(obs); return obs

@router.get("/{obs_type}", response_model=list[ObsOut])
def list_observations(obs_type: str, db: Session = Depends(get_db),
    company_id: Optional[int] = None, status: str = "active",
    limit: int = Query(default=50, le=200)):
    model = OBS_MAP.get(obs_type)
    if not model: raise ValueError(f"Unknown type: {obs_type}")
    stmt = select(model).where(model.status == status)
    if company_id: stmt = stmt.where(model.company_id == company_id)
    stmt = stmt.order_by(model.observed_at.desc()).limit(limit)
    return list(db.scalars(stmt))

@router.get("/key-dates/{company_id}")
def get_key_dates(company_id: int, db: Session = Depends(get_db)):
    stmt = select(KeyDate).where(KeyDate.company_id == company_id).where(KeyDate.status == "active")
    return list(db.scalars(stmt.order_by(KeyDate.event_date)))

@router.post("/key-dates", status_code=201)
def create_key_date(payload: dict, db: Session = Depends(get_db)):
    kd = KeyDate(**payload); db.add(kd); db.commit(); db.refresh(kd); return kd
