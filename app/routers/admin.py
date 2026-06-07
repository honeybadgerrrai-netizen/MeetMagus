"""Admin seed endpoint — runs demo data load on Railway."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.core.db import GlobalBase, PlatformBase, SessionLocal, engine
from app.models.tenant.models import TenantBase
from app.models.global_schema.entities import Affiliation, Company, CompanyRelationship, Person
from app.models.global_schema.observations import EmployeeObservation, FinancialObservation, InvestorObservation
from app.models.platform.models import FreshnessPolicy, SourceRegistry
from app.models.tenant.models import Alert, Banker, Capability, Contact, ContextNote

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
def seed_database():
    """Seed demo data. Idempotent."""
    db = SessionLocal()
        # Drop and recreate all tables to fix schema drift
        GlobalBase.metadata.drop_all(bind=engine)
    PlatformBase.metadata.drop_all(bind=engine)
    TenantBase.metadata.drop_all(bind=engine)
    GlobalBase.metadata.create_all(bind=engine)
    PlatformBase.metadata.create_all(bind=engine)
    TenantBase.metadata.create_all(bind=engine)
    try:
        db.add_all([
            SourceRegistry(source_id="sec_edgar", display_name="SEC EDGAR", source_type="sec_filing", can_store_raw=True, can_display_to_user=True, reliability_rank=1, dedup_threshold=0.95),
            SourceRegistry(source_id="news_feed", display_name="News Feed", source_type="news", can_store_raw=True, can_display_to_user=True, reliability_rank=4, dedup_threshold=0.90),
            SourceRegistry(source_id="job_board", display_name="Job Boards", source_type="job_board", can_store_raw=False, can_display_to_user=True, reliability_rank=6, dedup_threshold=0.88),
            SourceRegistry(source_id="manual", display_name="Manual Entry", source_type="manual", can_store_raw=True, can_display_to_user=True, reliability_rank=2, dedup_threshold=0.85),
            FreshnessPolicy(observation_type="investor", stale_after_days=1, critical_after_days=4),
            FreshnessPolicy(observation_type="financial", stale_after_days=30),
            FreshnessPolicy(observation_type="employee", stale_after_days=60),
        ])
        db.flush()
        goldfinch = Company(name="Goldfinch Partners", company_type="bank", hq_city="New York", hq_country="USA")
        infoblox = Company(name="Infoblox", company_type="private", hq_city="Santa Clara", hq_country="USA", is_prospect=True, description="DDI cloud leader ~$600M ARR.", employee_count=2700, revenue_usd=600_000_000)
        kestrel = Company(name="Kestrel Aerospace", company_type="public", hq_city="Los Angeles", hq_country="USA", is_prospect=True, ticker="KSTRL", revenue_usd=1_200_000_000)
        vista = Company(name="Vista Equity Partners", company_type="pe_firm", hq_city="Austin", hq_country="USA")
        warburg = Company(name="Warburg Pincus", company_type="pe_firm", hq_city="New York", hq_country="USA")
        cisco = Company(name="Cisco Systems", company_type="public", hq_city="San Jose", hq_country="USA", ticker="CSCO", revenue_usd=57_000_000_000)
        arista = Company(name="Arista Networks", company_type="public", hq_city="Santa Clara", hq_country="USA", ticker="ANET")
        db.add_all([goldfinch, infoblox, kestrel, vista, warburg, cisco, arista])
        db.flush()
        db.add_all([
            CompanyRelationship(source_company_id=vista.id, target_company_id=infoblox.id, relationship_type="invested_in", description="Vista Equity acquired Infoblox in 2016", observed_at=datetime.now(timezone.utc), source="sec_edgar", confidence=1.0),
            CompanyRelationship(source_company_id=warburg.id, target_company_id=infoblox.id, relationship_type="invested_in", description="Warburg Pincus co-invested alongside Vista", observed_at=datetime.now(timezone.utc), source="news_feed", confidence=1.0),
            CompanyRelationship(source_company_id=cisco.id, target_company_id=infoblox.id, relationship_type="competes_with", description="Cisco networking overlap", observed_at=datetime.now(timezone.utc), source="manual", confidence=0.8),
        ])
        db.flush()
        scott = Person(first_name="Scott", last_name="Harrell", email="sharrell@infoblox.com", location_city="Santa Clara", is_prospect=True)
        hoke = Person(first_name="Hoke", last_name="Horne", email="hhorne@infoblox.com", location_city="Santa Clara", is_prospect=True)
        db.add_all([scott, hoke])
        db.flush()
        db.add_all([
            Affiliation(person_id=scott.id, company_id=infoblox.id, role_type="ceo", title="President & CEO", is_current=True, start_date="2023-01-11"),
            Affiliation(person_id=hoke.id, company_id=infoblox.id, role_type="cfo", title="CFO & COO", is_current=True, start_date="2018-02-01"),
        ])
        db.flush()
        now = datetime.now(timezone.utc)
        db.add_all([
            FinancialObservation(company_id=infoblox.id, observed_at=now, source_id="news_feed", confidence=0.85, status="active", signal_type="revenue_signal", headline="Infoblox ARR exceeds $600M", detail="~20% YoY growth."),
            InvestorObservation(company_id=infoblox.id, observed_at=now, source_id="news_feed", confidence=0.95, status="active", signal_type="ownership_change", headline="Vista Equity yr9 + Warburg — exit window opening", detail="Vista acquired 2016. PE avg hold 5-7 yrs.", investor_name="Vista Equity Partners", investor_company_id=vista.id, stake_pct=60.0, is_activist=False),
            EmployeeObservation(company_id=infoblox.id, observed_at=now, source_id="job_board", confidence=0.75, status="active", signal_type="hiring_surge", headline="Infoblox 60+ open sales roles", detail="Revenue acceleration signal.", department="Sales", open_roles_count=63),
            EmployeeObservation(company_id=infoblox.id, observed_at=now, source_id="job_board", confidence=0.70, status="active", signal_type="exec_hire", headline="Revenue Accounting hire (ASC 606)", detail="Audit-readiness signal.", department="Finance"),
        ])
        db.flush()
        banker = Banker(tenant_id="demo", first_name="Sam", last_name="Patel", email="spatel@goldfinch.com", title="Managing Director, Technology", employer_company_id=goldfinch.id)
        db.add(banker)
        db.flush()
        db.add_all([
            Contact(banker_id=banker.id, first_name="Devon", last_name="Cole", email="dcole@kestrel.com", employer_name="Kestrel Aerospace", employer_company_id=kestrel.id, employer_title="SVP Strategy", relationship_score=7, relationship_tier="warm", willingness_to_help="intro", notes="Met at Aspen 2023."),
            Contact(banker_id=banker.id, first_name="Scott", last_name="Harrell", email="sharrell@infoblox.com", employer_name="Infoblox", employer_company_id=infoblox.id, employer_title="CEO", relationship_score=6, relationship_tier="warm", willingness_to_help="intro", linked_person_id=scott.id, notes="Met at JP Morgan TMT 2024."),
            Contact(banker_id=banker.id, first_name="Maria", last_name="Chen", email="mchen@vista.com", employer_name="Vista Equity Partners", employer_company_id=vista.id, employer_title="Principal", relationship_score=8, relationship_tier="close", willingness_to_help="advocate", notes="Stanford MBA classmate."),
        ])
        db.flush()
        db.add_all([
            Capability(banker_id=banker.id, scope="individual", category="sector_coverage", name="Enterprise Software & Cybersecurity M&A", description="15 years covering enterprise software M&A.", sector_focus="Technology", deal_size_min_usd=100_000_000, deal_size_max_usd=5_000_000_000, track_record_count=31),
            Capability(banker_id=banker.id, scope="individual", category="m_and_a_advisory", name="Strategic buyer relationships — Cisco, Arista, Palo Alto", description="Direct corp dev relationships.", sector_focus="Cybersecurity"),
            Capability(banker_id=banker.id, scope="firm", category="sell_side", name="Goldfinch Technology M&A", description="Boutique sell-side advisor.", sector_focus="Technology", firm_company_id=goldfinch.id, track_record_count=47),
        ])
        db.flush()
        db.add_all([
            ContextNote(banker_id=banker.id, source_type="BANKER", content="Scott Harrell strategic-exit oriented.", tagged_company_ids=str(infoblox.id), tagged_person_ids=str(scott.id)),
            ContextNote(banker_id=banker.id, source_type="BANKER", content="Vista evaluating options. Maria Chen confirmed.", tagged_company_ids=f"{infoblox.id},{vista.id}"),
            ContextNote(banker_id=banker.id, source_type="AI", content="Hiring surge = go-to-market acceleration, not IPO prep.", tagged_company_ids=str(infoblox.id)),
        ])
        db.flush()
        db.add(Alert(banker_id=banker.id, trigger_type="investor_signal", title="Vista Equity at Year 9 on Infoblox — Exit Window Now Open", body="Vista acquired Infoblox in 2016. $600M ARR. Warm path: Maria Chen (Vista, score 8) + Scott Harrell (CEO, score 6).", target_company_id=infoblox.id, relevance_score=0.94, status="unread", cited_sources='["sec_edgar:vista_infoblox_2016","job_board:infoblox_2024"]'))
        db.commit()
        return {"status": "seeded", "companies": db.query(Company).count(), "people": db.query(Person).count(), "contacts": db.query(Contact).count(), "capabilities": db.query(Capability).count(), "notes": db.query(ContextNote).count(), "alerts": db.query(Alert).count()}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
