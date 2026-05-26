"""Seed with realistic demo data."""
import sys; sys.path.insert(0, '/home/claude/dealflow')
from app.core.db import GlobalBase, PlatformBase, engine, SessionLocal
from app.models.global_schema.entities import Company, Person, Affiliation, CompanyRelationship
from app.models.global_schema.observations import FinancialObservation, InvestorObservation, EmployeeObservation
from app.models.tenant.models import TenantBase, Banker, Contact, Capability, ContextNote, Alert
from app.models.platform.models import SourceRegistry, FreshnessPolicy
from datetime import datetime, timezone

def run():
    GlobalBase.metadata.create_all(bind=engine)
    PlatformBase.metadata.create_all(bind=engine)
    TenantBase.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Sources
        sources = [
            SourceRegistry(source_id="sec_edgar", display_name="SEC EDGAR", source_type="sec_filing",
                can_store_raw=True, can_display_to_user=True, reliability_rank=1, dedup_threshold=0.95),
            SourceRegistry(source_id="news_feed", display_name="News Feed", source_type="news",
                can_store_raw=True, can_display_to_user=True, reliability_rank=4, dedup_threshold=0.90),
            SourceRegistry(source_id="job_board", display_name="Job Boards", source_type="job_board",
                can_store_raw=False, can_display_to_user=True, reliability_rank=6, dedup_threshold=0.88),
            SourceRegistry(source_id="manual", display_name="Manual Entry", source_type="manual",
                can_store_raw=True, can_display_to_user=True, reliability_rank=2, dedup_threshold=0.85),
        ]
        db.add_all(sources)

        # Freshness policies
        policies = [
            FreshnessPolicy(observation_type="investor", stale_after_days=1, critical_after_days=4),
            FreshnessPolicy(observation_type="financial", stale_after_days=30),
            FreshnessPolicy(observation_type="employee", stale_after_days=60),
            FreshnessPolicy(observation_type="macro", stale_after_days=30),
            FreshnessPolicy(observation_type="competitive", stale_after_days=14),
        ]
        db.add_all(policies)
        db.flush()

        # Companies
        goldfinch = Company(name="Goldfinch Partners", company_type="bank", hq_city="New York", hq_country="USA")
        infoblox = Company(name="Infoblox", company_type="private", hq_city="Santa Clara",
            hq_country="USA", is_prospect=True, ticker=None,
            description="Leader in cloud networking and security (DDI). ~$600M ARR, ~20% growth, ~30% EBITDA margin.",
            employee_count=2700, revenue_usd=600_000_000)
        kestrel = Company(name="Kestrel Aerospace", company_type="public", hq_city="Los Angeles",
            hq_country="USA", is_prospect=True, ticker="KSTRL", revenue_usd=1_200_000_000)
        vista = Company(name="Vista Equity Partners", company_type="pe_firm", hq_city="Austin", hq_country="USA")
        warburg = Company(name="Warburg Pincus", company_type="pe_firm", hq_city="New York", hq_country="USA")
        cisco = Company(name="Cisco Systems", company_type="public", hq_city="San Jose",
            hq_country="USA", ticker="CSCO", revenue_usd=57_000_000_000)
        arista = Company(name="Arista Networks", company_type="public", hq_city="Santa Clara",
            hq_country="USA", ticker="ANET")
        db.add_all([goldfinch, infoblox, kestrel, vista, warburg, cisco, arista])
        db.flush()

        # Company relationships
        rels = [
            CompanyRelationship(source_company_id=vista.id, target_company_id=infoblox.id,
                relationship_type="invested_in", description="Vista Equity acquired Infoblox in 2016",
                observed_at=datetime.now(timezone.utc), source="sec_edgar", confidence=1.0),
            CompanyRelationship(source_company_id=warburg.id, target_company_id=infoblox.id,
                relationship_type="invested_in", description="Warburg Pincus co-invested alongside Vista",
                observed_at=datetime.now(timezone.utc), source="news_feed", confidence=1.0),
            CompanyRelationship(source_company_id=cisco.id, target_company_id=infoblox.id,
                relationship_type="competes_with", description="Cisco ThousandEyes and networking overlap",
                observed_at=datetime.now(timezone.utc), source="manual", confidence=0.8),
        ]
        db.add_all(rels)
        db.flush()

        # People
        scott = Person(first_name="Scott", last_name="Harrell", email="sharrell@infoblox.com",
            location_city="Santa Clara", is_prospect=True)
        hoke = Person(first_name="Hoke", last_name="Horne", email="hhorne@infoblox.com",
            location_city="Santa Clara", is_prospect=True)
        db.add_all([scott, hoke])
        db.flush()

        affs = [
            Affiliation(person_id=scott.id, company_id=infoblox.id, role_type="ceo",
                title="President & CEO", is_current=True, start_date="2023-01-11"),
            Affiliation(person_id=hoke.id, company_id=infoblox.id, role_type="cfo",
                title="CFO & COO", is_current=True, start_date="2018-02-01"),
        ]
        db.add_all(affs)
        db.flush()

        # Observations on Infoblox
        now = datetime.now(timezone.utc)
        obs = [
            FinancialObservation(company_id=infoblox.id, observed_at=now, source_id="news_feed",
                confidence=0.85, status="active",
                signal_type="revenue_signal", headline="Infoblox ARR exceeds $600M, ~20% YoY growth",
                detail="Per industry reports and company communications, Infoblox has crossed $600M ARR with sustained ~20% growth driven by DDI cloud transition and Threat Defense expansion."),
            InvestorObservation(company_id=infoblox.id, observed_at=now, source_id="news_feed",
                confidence=0.95, status="active",
                signal_type="ownership_change", headline="Vista Equity (yr 9) + Warburg Pincus co-investors — exit window opening",
                detail="Vista acquired Infoblox in 2016 (~9 years). Average PE hold is 5-7 years. Exit pressure building.",
                investor_name="Vista Equity Partners", investor_company_id=vista.id,
                stake_pct=60.0, is_activist=False),
            EmployeeObservation(company_id=infoblox.id, observed_at=now, source_id="job_board",
                confidence=0.75, status="active",
                signal_type="hiring_surge", headline="Infoblox heavily hiring in Sales (60+ open roles) — go-to-market acceleration",
                detail="Job board analysis shows 60+ open sales roles vs <5 in R&D, signaling revenue acceleration focus not product investment.",
                department="Sales", open_roles_count=63),
            EmployeeObservation(company_id=infoblox.id, observed_at=now, source_id="job_board",
                confidence=0.70, status="active",
                signal_type="exec_hire", headline="Infoblox hired Manager of Revenue Accounting (ASC 606 expert, Big Four background)",
                detail="Revenue accounting hire with deep ASC 606 expertise is audit-readiness signal — consistent with pre-transaction preparation.",
                department="Finance"),
        ]
        db.add_all(obs)
        db.flush()

        # Banker (the user)
        banker = Banker(tenant_id="demo", first_name="Sam", last_name="Patel",
            email="spatel@goldfinch.com", title="Managing Director, Technology",
            employer_company_id=goldfinch.id)
        db.add(banker); db.flush()

        # Contacts
        contacts = [
            Contact(banker_id=banker.id, first_name="Devon", last_name="Cole",
                email="dcole@kestrel.com", employer_name="Kestrel Aerospace",
                employer_company_id=kestrel.id, employer_title="SVP Strategy",
                relationship_score=7, relationship_tier="warm", willingness_to_help="intro",
                notes="Met at Aspen 2023. Happy to intro to their CFO."),
            Contact(banker_id=banker.id, first_name="Scott", last_name="Harrell",
                email="sharrell@infoblox.com", employer_name="Infoblox",
                employer_company_id=infoblox.id, employer_title="CEO",
                relationship_score=6, relationship_tier="warm", willingness_to_help="intro",
                linked_person_id=scott.id,
                notes="Met at JP Morgan TMT Conference 2024. Good conversation on strategic options."),
            Contact(banker_id=banker.id, first_name="Maria", last_name="Chen",
                email="mchen@vista.com", employer_name="Vista Equity Partners",
                employer_company_id=vista.id, employer_title="Principal",
                relationship_score=8, relationship_tier="close", willingness_to_help="advocate",
                notes="Stanford MBA classmate. Will take my call. Key path into Vista portfolio decisions."),
        ]
        db.add_all(contacts); db.flush()

        # Capabilities
        caps = [
            Capability(banker_id=banker.id, scope="individual", category="sector_coverage",
                name="Enterprise Software & Cybersecurity M&A",
                description="15 years covering enterprise software and cybersecurity M&A. Specialist in sponsor-backed exits.",
                sector_focus="Technology", deal_size_min_usd=100_000_000,
                deal_size_max_usd=5_000_000_000, track_record_count=31),
            Capability(banker_id=banker.id, scope="individual", category="m_and_a_advisory",
                name="Strategic buyer relationships — Cisco, Arista, Palo Alto, CrowdStrike",
                description="Direct relationships with corp dev at major network security acquirers.",
                sector_focus="Cybersecurity"),
            Capability(banker_id=banker.id, scope="firm", category="sell_side",
                name="Goldfinch Technology M&A — sell-side advisor",
                description="Boutique positioning: undivided attention, deep strategic ecosystem knowledge, no cross-sell agenda.",
                sector_focus="Technology", firm_company_id=goldfinch.id,
                track_record_count=47),
        ]
        db.add_all(caps); db.flush()

        # Context notes
        notes = [
            ContextNote(banker_id=banker.id, source_type="BANKER",
                content="Infoblox CEO Scott Harrell is strategic-exit oriented. Background at Cisco makes him receptive to strategic buyer conversations. Not wedded to IPO narrative.",
                tagged_company_ids=str(infoblox.id), tagged_person_ids=str(scott.id)),
            ContextNote(banker_id=banker.id, source_type="BANKER",
                content="Vista Equity typically runs dual-track (strategic + sponsor-to-sponsor) when they exit. Maria Chen confirmed Vista is 'evaluating options' for the Infoblox position.",
                tagged_company_ids=f"{infoblox.id},{vista.id}"),
            ContextNote(banker_id=banker.id, source_type="AI",
                content="Hiring signal analysis: Infoblox sales hiring surge (60+ open roles) indicates go-to-market acceleration. Combined with no IR/public company infrastructure hires, signals strategic exit not IPO.",
                tagged_company_ids=str(infoblox.id), ai_source_id="job_board"),
        ]
        db.add_all(notes); db.flush()

        # Sample alert
        alert = Alert(banker_id=banker.id, trigger_type="investor_signal",
            title="Vista Equity at Year 9 on Infoblox — Exit Window Now Open",
            body="""ALERT: Infoblox exit window analysis

Vista Equity Partners acquired Infoblox in 2016 (9 years ago). Warburg Pincus co-invested. Average PE hold period is 5-7 years — this position is overdue for an exit event.

KEY SIGNALS:
• ~$600M ARR, ~20% growth, ~30% EBITDA margins — strong exit profile
• 60+ open sales roles — revenue acceleration before a process
• Revenue accounting hire (ASC 606/Big Four) — financial housekeeping signal
• No IPO infrastructure hires — IPO market also wrong venue (AI-only appetite)

YOUR WARM PATH:
• Maria Chen (Vista Principal, score 8/10, advocate) — direct path to Vista's decision-makers
• Scott Harrell (CEO, score 6/10, intro-willing) — receptive to strategic discussion

YOUR CAPABILITY MATCH:
• Direct relationships with Cisco and Arista corp dev (most likely strategic buyers)
• 31 closed enterprise software M&A transactions
• Boutique positioning = no conflict, undivided attention

RECOMMENDED ACTION: Call Maria Chen first to gauge Vista's timeline, then request a meeting with Scott Harrell for a capabilities presentation.""",
            target_company_id=infoblox.id, relevance_score=0.94, status="unread",
            cited_sources='["sec_edgar:vista_infoblox_2016", "job_board:infoblox_2024", "news_feed:infoblox_arr"]')
        db.add(alert)
        db.commit()

        print(f"Seeded: {db.query(Company).count()} companies, {db.query(Person).count()} people")
        print(f"        {db.query(Contact).count()} contacts, {db.query(Capability).count()} capabilities")
        print(f"        {db.query(Alert).count()} alert, {db.query(ContextNote).count()} notes")
    finally:
        db.close()

if __name__ == "__main__":
    run()
