from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.platform.models import SourceRegistry, SourceMonitor, EntityResolutionQueue
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

class SourceIn(BaseModel):
    source_id: str; display_name: str; source_type: str
    can_store_raw: bool = True; can_display_to_user: bool = True
    requires_attribution: bool = False; reliability_rank: int = 5
    dedup_threshold: float = 0.92; retention_days: Optional[int] = None

class MonitorIn(BaseModel):
    company_id: int; source_id: str; fetch_cadence_minutes: int = 60

class ResolutionAction(BaseModel):
    action: str  # confirm | reject
    confirmed_entity_id: Optional[int] = None
    reviewed_by: str = "admin"

@router.post("/sources", status_code=201)
def register_source(payload: SourceIn, db: Session = Depends(get_db)):
    s = SourceRegistry(**payload.model_dump()); db.add(s); db.commit(); db.refresh(s); return s

@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    return list(db.scalars(select(SourceRegistry)))

@router.post("/monitors", status_code=201)
def create_monitor(payload: MonitorIn, db: Session = Depends(get_db)):
    m = SourceMonitor(**payload.model_dump()); db.add(m); db.commit(); db.refresh(m); return m

@router.get("/resolution-queue")
def get_resolution_queue(db: Session = Depends(get_db), status: str = "pending"):
    return list(db.scalars(select(EntityResolutionQueue).where(
        EntityResolutionQueue.status == status).order_by(EntityResolutionQueue.created_at)))

@router.patch("/resolution-queue/{item_id}")
def resolve_entity(item_id: int, payload: ResolutionAction, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    from datetime import datetime, timezone
    item = db.get(EntityResolutionQueue, item_id)
    if not item: raise HTTPException(404)
    item.status = "confirmed" if payload.action == "confirm" else "rejected"
    item.reviewed_by = payload.reviewed_by
    item.reviewed_at = datetime.now(timezone.utc)
    if payload.action == "confirm" and payload.confirmed_entity_id:
        from app.models.global_schema.entities import CompanyAlias, PersonAlias
        if item.entity_type == "company":
            alias = CompanyAlias(company_id=payload.confirmed_entity_id, alias=item.alias,
                confidence_score=item.confidence_score, status="confirmed",
                confirmed_by=payload.reviewed_by, confirmed_at=item.reviewed_at)
            db.add(alias)
        else:
            alias = PersonAlias(person_id=payload.confirmed_entity_id, alias=item.alias,
                confidence_score=item.confidence_score, status="confirmed",
                confirmed_by=payload.reviewed_by, confirmed_at=item.reviewed_at)
            db.add(alias)
    db.commit(); db.refresh(item); return item
