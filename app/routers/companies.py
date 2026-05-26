from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.global_schema.entities import Company
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/companies", tags=["companies"])

class CompanyIn(BaseModel):
    name: str
    legal_name: Optional[str] = None
    company_type: str = "private"
    sector_id: Optional[int] = None
    hq_city: Optional[str] = None
    hq_country: Optional[str] = None
    website: Optional[str] = None
    ticker: Optional[str] = None
    is_prospect: bool = False
    description: Optional[str] = None
    employee_count: Optional[int] = None
    revenue_usd: Optional[float] = None

class CompanyOut(BaseModel):
    id: int
    name: str
    legal_name: Optional[str]
    company_type: str
    hq_city: Optional[str]
    hq_country: Optional[str]
    website: Optional[str]
    ticker: Optional[str]
    is_prospect: bool
    description: Optional[str]
    employee_count: Optional[int]
    revenue_usd: Optional[float]
    created_at: datetime
    class Config:
        from_attributes = True

@router.post("", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyIn, db: Session = Depends(get_db)):
    company = Company(**payload.model_dump())
    db.add(company); db.commit(); db.refresh(company)
    return company

@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db), is_prospect: Optional[bool] = None,
    q: Optional[str] = Query(default=None), company_type: Optional[str] = None,
    limit: int = Query(default=50, le=200), offset: int = 0):
    stmt = select(Company)
    if is_prospect is not None: stmt = stmt.where(Company.is_prospect.is_(is_prospect))
    if q: stmt = stmt.where(Company.name.ilike(f"%{q}%"))
    if company_type: stmt = stmt.where(Company.company_type == company_type)
    return list(db.scalars(stmt.order_by(Company.name).limit(limit).offset(offset)))

@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c: raise HTTPException(404, f"Company {company_id} not found")
    return c

@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, payload: CompanyIn, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c: raise HTTPException(404)
    for k, v in payload.model_dump(exclude_unset=True).items(): setattr(c, k, v)
    db.commit(); db.refresh(c); return c

@router.delete("/{company_id}", status_code=204)
def delete_company(company_id: int, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if not c: raise HTTPException(404)
    db.delete(c); db.commit()
