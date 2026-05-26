from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.tenant.models import Capability, CapabilityEvent
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/capabilities", tags=["capabilities"])

class CapabilityIn(BaseModel):
    banker_id: int; scope: str = "individual"; category: str
    name: str; description: Optional[str] = None
    sector_focus: Optional[str] = None; geo_focus: Optional[str] = None
    deal_size_min_usd: Optional[float] = None; deal_size_max_usd: Optional[float] = None
    track_record_count: Optional[int] = None; firm_company_id: Optional[int] = None

class CapabilityOut(BaseModel):
    id: int; banker_id: int; scope: str; category: str; name: str
    description: Optional[str]; sector_focus: Optional[str]; geo_focus: Optional[str]
    deal_size_min_usd: Optional[float]; deal_size_max_usd: Optional[float]
    track_record_count: Optional[int]; created_at: datetime
    class Config: from_attributes = True

class EventIn(BaseModel):
    capability_id: int; event_type: str; headline: str
    description: Optional[str] = None; deal_size_usd: Optional[float] = None
    sector: Optional[str] = None; announced_at: Optional[str] = None
    source_url: Optional[str] = None

@router.post("", response_model=CapabilityOut, status_code=201)
def create_capability(payload: CapabilityIn, db: Session = Depends(get_db)):
    c = Capability(**payload.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@router.get("", response_model=list[CapabilityOut])
def list_capabilities(db: Session = Depends(get_db), banker_id: Optional[int] = None, scope: Optional[str] = None):
    stmt = select(Capability)
    if banker_id: stmt = stmt.where(Capability.banker_id == banker_id)
    if scope: stmt = stmt.where(Capability.scope == scope)
    return list(db.scalars(stmt))

@router.post("/events", status_code=201)
def add_event(payload: EventIn, db: Session = Depends(get_db)):
    e = CapabilityEvent(**payload.model_dump()); db.add(e); db.commit(); db.refresh(e); return e

@router.get("/{cap_id}/events")
def list_events(cap_id: int, db: Session = Depends(get_db)):
    return list(db.scalars(select(CapabilityEvent).where(CapabilityEvent.capability_id == cap_id)))
