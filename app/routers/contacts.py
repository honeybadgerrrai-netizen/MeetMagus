from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.tenant.models import Contact, Banker
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/contacts", tags=["contacts"])

class ContactIn(BaseModel):
    banker_id: int; first_name: str; last_name: str
    email: Optional[str] = None; phone: Optional[str] = None
    employer_name: Optional[str] = None; employer_company_id: Optional[int] = None
    employer_title: Optional[str] = None
    relationship_score: int = 5; relationship_tier: str = "acquaintance"
    willingness_to_help: str = "unknown"; notes: Optional[str] = None
    linked_person_id: Optional[int] = None

class ContactOut(BaseModel):
    id: int; banker_id: int; first_name: str; last_name: str
    email: Optional[str]; employer_name: Optional[str]; employer_title: Optional[str]
    relationship_score: int; relationship_tier: str; willingness_to_help: str
    notes: Optional[str]; linked_person_id: Optional[int]; created_at: datetime
    class Config: from_attributes = True

@router.post("", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactIn, db: Session = Depends(get_db)):
    c = Contact(**payload.model_dump()); db.add(c); db.commit(); db.refresh(c); return c

@router.get("", response_model=list[ContactOut])
def list_contacts(db: Session = Depends(get_db), banker_id: Optional[int] = None,
    min_score: Optional[int] = None, tier: Optional[str] = None,
    limit: int = Query(default=50, le=200)):
    stmt = select(Contact)
    if banker_id: stmt = stmt.where(Contact.banker_id == banker_id)
    if min_score: stmt = stmt.where(Contact.relationship_score >= min_score)
    if tier: stmt = stmt.where(Contact.relationship_tier == tier)
    return list(db.scalars(stmt.order_by(Contact.relationship_score.desc()).limit(limit)))

@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c: raise HTTPException(404)
    return c

@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, payload: ContactIn, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c: raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items(): setattr(c, k, v)
    db.commit(); db.refresh(c); return c

@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    c = db.get(Contact, contact_id)
    if not c: raise HTTPException(404)
    db.delete(c); db.commit()
