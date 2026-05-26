from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.tenant.models import Contact
from app.models.global_schema.entities import Affiliation

router = APIRouter(prefix="/warm-paths", tags=["warm-paths"])

@router.get("/to-company/{company_id}")
def warm_paths_to_company(company_id: int, db: Session = Depends(get_db),
    banker_id: int = Query(...), min_score: int = Query(default=1, ge=1, le=10),
    only_willing: bool = False):
    affiliated_ids = [
        r[0] for r in db.execute(
            select(Affiliation.person_id).where(
                Affiliation.company_id == company_id, Affiliation.is_current == True
            )
        ).fetchall()
    ]
    stmt = select(Contact).where(
        Contact.banker_id == banker_id,
        Contact.relationship_score >= min_score
    ).where(
        (Contact.employer_company_id == company_id) |
        (Contact.linked_person_id.in_(affiliated_ids) if affiliated_ids else False)
    )
    if only_willing:
        stmt = stmt.where(Contact.willingness_to_help.in_(["advocate", "intro"]))
    results = list(db.scalars(stmt.order_by(Contact.relationship_score.desc())))
    return [{"id": c.id, "name": f"{c.first_name} {c.last_name}",
             "employer": c.employer_name, "score": c.relationship_score,
             "tier": c.relationship_tier, "willingness": c.willingness_to_help,
             "path_type": "employer" if c.employer_company_id == company_id else "affiliation"
             } for c in results]
