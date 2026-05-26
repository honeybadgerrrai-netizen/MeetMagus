from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.tenant.models import ContextNote
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/notes", tags=["notes"])

class NoteIn(BaseModel):
    banker_id: int; content: str; source_type: str = "BANKER"
    tagged_company_ids: Optional[str] = None; tagged_person_ids: Optional[str] = None
    is_standing_preference: bool = False

class NoteOut(BaseModel):
    id: int; banker_id: int; content: str; source_type: str
    tagged_company_ids: Optional[str]; tagged_person_ids: Optional[str]
    is_standing_preference: bool; status: str; created_at: datetime
    class Config: from_attributes = True

@router.post("", response_model=NoteOut, status_code=201)
def create_note(payload: NoteIn, db: Session = Depends(get_db)):
    n = ContextNote(**payload.model_dump()); db.add(n); db.commit(); db.refresh(n); return n

@router.get("", response_model=list[NoteOut])
def list_notes(db: Session = Depends(get_db), banker_id: Optional[int] = None,
    company_id: Optional[int] = None, person_id: Optional[int] = None,
    limit: int = Query(default=50, le=200)):
    stmt = select(ContextNote).where(ContextNote.status == "active")
    if banker_id: stmt = stmt.where(ContextNote.banker_id == banker_id)
    if company_id: stmt = stmt.where(ContextNote.tagged_company_ids.contains(str(company_id)))
    if person_id: stmt = stmt.where(ContextNote.tagged_person_ids.contains(str(person_id)))
    return list(db.scalars(stmt.order_by(ContextNote.created_at.desc()).limit(limit)))
