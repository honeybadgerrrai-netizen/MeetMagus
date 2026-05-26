from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.global_schema.entities import Person, Affiliation
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/people", tags=["people"])

class PersonIn(BaseModel):
    first_name: str; last_name: str
    email: Optional[str] = None; phone: Optional[str] = None
    linkedin_url: Optional[str] = None; location_city: Optional[str] = None
    location_country: Optional[str] = None; is_prospect: bool = False
    notes: Optional[str] = None

class AffiliationIn(BaseModel):
    person_id: int; company_id: int; role_type: str
    title: Optional[str] = None; is_current: bool = True
    start_date: Optional[str] = None; end_date: Optional[str] = None

class AffiliationOut(BaseModel):
    id: int; person_id: int; company_id: int; role_type: str
    title: Optional[str]; is_current: bool
    class Config: from_attributes = True

class PersonOut(BaseModel):
    id: int; first_name: str; last_name: str
    email: Optional[str]; phone: Optional[str]; linkedin_url: Optional[str]
    location_city: Optional[str]; location_country: Optional[str]
    is_prospect: bool; notes: Optional[str]; created_at: datetime
    affiliations: list[AffiliationOut] = []
    class Config: from_attributes = True

@router.post("", response_model=PersonOut, status_code=201)
def create_person(payload: PersonIn, db: Session = Depends(get_db)):
    p = Person(**payload.model_dump()); db.add(p); db.commit(); db.refresh(p); return p

@router.get("", response_model=list[PersonOut])
def list_people(db: Session = Depends(get_db), is_prospect: Optional[bool] = None,
    q: Optional[str] = Query(default=None), limit: int = 50, offset: int = 0):
    stmt = select(Person)
    if is_prospect is not None: stmt = stmt.where(Person.is_prospect.is_(is_prospect))
    if q: stmt = stmt.where(Person.last_name.ilike(f"%{q}%"))
    return list(db.scalars(stmt.order_by(Person.last_name).limit(limit).offset(offset)))

@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db)):
    p = db.get(Person, person_id)
    if not p: raise HTTPException(404)
    return p

@router.post("/affiliations", response_model=AffiliationOut, status_code=201)
def create_affiliation(payload: AffiliationIn, db: Session = Depends(get_db)):
    a = Affiliation(**payload.model_dump()); db.add(a); db.commit(); db.refresh(a); return a

@router.patch("/{person_id}", response_model=PersonOut)
def update_person(person_id: int, payload: PersonIn, db: Session = Depends(get_db)):
    p = db.get(Person, person_id)
    if not p: raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items(): setattr(p, k, v)
    db.commit(); db.refresh(p); return p
