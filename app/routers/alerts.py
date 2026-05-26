from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.tenant.models import Alert
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/alerts", tags=["alerts"])

class AlertOut(BaseModel):
    id: int; banker_id: int; trigger_type: str; title: str; body: str
    target_company_id: Optional[int]; relevance_score: Optional[float]
    status: str; banker_feedback: Optional[str]; created_at: datetime
    class Config: from_attributes = True

class FeedbackIn(BaseModel):
    feedback: str  # acted | dismissed | wrong

@router.get("", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db), banker_id: Optional[int] = None,
    status: Optional[str] = None, limit: int = Query(default=20, le=100)):
    stmt = select(Alert)
    if banker_id: stmt = stmt.where(Alert.banker_id == banker_id)
    if status: stmt = stmt.where(Alert.status == status)
    return list(db.scalars(stmt.order_by(Alert.created_at.desc()).limit(limit)))

@router.patch("/{alert_id}/feedback", response_model=AlertOut)
def submit_feedback(alert_id: int, payload: FeedbackIn, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    from datetime import timezone
    a = db.get(Alert, alert_id)
    if not a: raise HTTPException(404)
    a.banker_feedback = payload.feedback
    a.status = "acted" if payload.feedback == "acted" else "dismissed"
    a.feedback_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(a); return a
