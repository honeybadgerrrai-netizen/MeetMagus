"""
MeetMagus — BuildOps Seed Data
Adds BuildOps as a prospect company and Anand Sankaralingam as a banker (tenant_1).

Run: python3 -m scripts.buildops_seed
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Check your .env file.")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

engine = create_engine(DATABASE_URL)

def sql(query: str):
    """Wrap in text() and escape % so psycopg2 doesn't treat them as param markers."""
    return text(query.replace("%", "%%"))


def run():
    print("Seeding BuildOps scenario...")

    with Session(engine) as session:

        # ── 1. Company: BuildOps ──────────────────────────────────────────────
        print("  → Inserting BuildOps company...")
        session.execute(sql("""
            INSERT INTO global.companies
                (name, ticker, domain, hq_city, hq_state, hq_country,
                 industry, sub_industry, employee_count_approx,
                 is_public, is_prospect, description)
            VALUES (
                'BuildOps',
                NULL,
                'buildops.com',
                'Santa Monica', 'CA', 'USA',
                'Construction Technology',
                'Field Service Management Software',
                350,
                false,
                true,
                'Cloud-native field service management platform for commercial contractors. '
                'Covers scheduling, dispatching, invoicing, payroll, CRM, and asset tracking. '
                'Series C unicorn ($1B valuation, Mar 2025). $127M raised from Meritech Capital, '
                'BOND, and SE Ventures. ~$97M ARR as of 2025, growing ~88%% YoY. '
                'Founded by Alok Chanani (CEO), Steve Chew (COO/CPO), and Neeraj Mittal.'
            )
            ON CONFLICT (ticker) DO NOTHING;
        """))
        session.commit()

        # ── 2. Banker: Anand Sankaralingam ───────────────────────────────────
        print("  → Inserting banker Anand Sankaralingam...")
        session.execute(sql("""
            INSERT INTO tenant_1.bankers
                (name, email, firm_name, title, tenant_id)
            VALUES (
                'Anand Sankaralingam',
                'anand@tidalpartners.com',
                'Tidal Partners',
                'Partner',
                'tenant_1'
            )
            ON CONFLICT (email) DO NOTHING;
        """))
        session.commit()

        # ── 3. People: Alok Chanani (BuildOps CEO) ───────────────────────────
        print("  → Inserting Alok Chanani...")
        session.execute(sql("""
            INSERT INTO global.people (full_name, linkedin_url, bio)
            VALUES (
                'Alok Chanani',
                'linkedin.com/in/alok-chanani',
                'Co-Founder & CEO of BuildOps. Former US Army officer and Harvard MBA. '
                'Founded BuildOps in 2018 to modernize field service ops for commercial contractors.'
            )
            ON CONFLICT (full_name) DO NOTHING;
        """))
        session.commit()

        # ── 4. Affiliation: Alok Chanani → BuildOps ──────────────────────────
        print("  → Inserting affiliation...")
        session.execute(sql("""
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current, start_date)
            SELECT p.id, c.id, 'Co-Founder & CEO', 'executive', true, '2018-01-01'
            FROM global.people p, global.companies c
            WHERE p.full_name = 'Alok Chanani' AND c.name = 'BuildOps'
            ON CONFLICT (person_id, company_id, title) DO NOTHING;
        """))
        session.commit()

        # ── 5. Observations ───────────────────────────────────────────────────
        print("  → Inserting observations...")

        # obs_financial: Series C / unicorn
        session.execute(sql("""
            INSERT INTO global.obs_financial
                (company_id, signal_type, status, headline, detail,
                 metric_name, metric_value, metric_unit, amount_usd,
                 confidence, source_id, observed_at)
            SELECT c.id,
                'funding_round', 'active',
                'BuildOps raises $127M Series C, hits $1B unicorn valuation',
                'BuildOps closed a $127M Series C in March 2025 led by Meritech Capital with '
                'participation from BOND and SE Ventures. Post-money valuation of $1B. '
                'Total capital raised: $226M across 4 rounds. Company reported ~$97M ARR '
                'as of 2025, up ~88%% YoY from ~$52M in 2024. Rule-of-40 profile '
                'attractive for a strategic acquirer or growth equity recap.',
                'ARR', 97.0, 'M USD', 127000000,
                0.99, 'techcrunch_pressrelease',
                '2025-03-21'
            FROM global.companies c WHERE c.name = 'BuildOps'
            ON CONFLICT DO NOTHING;
        """))

        # obs_competitive: market position
        session.execute(sql("""
            INSERT INTO global.obs_competitive
                (company_id, signal_type, status, headline, detail,
                 confidence, source_id, observed_at)
            SELECT c.id,
                'market_position', 'active',
                'BuildOps leading cloud-native FSM for commercial contractors vs ServiceTitan',
                'BuildOps targets commercial contractors (HVAC, plumbing, electrical) — '
                'a segment underserved by ServiceTitan which skews residential. '
                'Key differentiators: purpose-built for commercial job complexity, '
                'integrated invoicing + payroll, and AI-driven dispatch. '
                'Competes with FieldEdge, Successware, and legacy ERP players. '
                'Meritech and BOND backing signals institutional confidence in '
                'winner-take-most FSM dynamics.',
                0.90, 'analyst_research',
                '2026-01-15'
            FROM global.companies c WHERE c.name = 'BuildOps'
            ON CONFLICT DO NOTHING;
        """))

        # obs_financial: ARR growth trajectory
        session.execute(sql("""
            INSERT INTO global.obs_financial
                (company_id, signal_type, status, headline, detail,
                 metric_name, metric_value, metric_unit, amount_usd,
                 confidence, source_id, observed_at)
            SELECT c.id,
                'revenue_signal', 'active',
                'BuildOps ARR ~$97M (+88%% YoY) — on path to $150M+ by end of 2026',
                'BuildOps grew ARR from $52M (2024) to $97M (2025), an 88%% increase. '
                'At this growth rate, the company is tracking toward $150-180M ARR by '
                'end of 2026. NRR likely strong given commercial contractor stickiness — '
                'once dispatching and payroll are integrated, churn is very low. '
                'Company added Go-to-Market leadership (CRO Greg Gillis, CMO Colin Piper) '
                'in late 2025, signaling a push for accelerated enterprise sales.',
                'ARR', 97.0, 'M USD', NULL,
                0.95, 'getlatka_data',
                '2025-12-01'
            FROM global.companies c WHERE c.name = 'BuildOps'
            ON CONFLICT DO NOTHING;
        """))

        # obs_macro: construction tech M&A tailwinds
        session.execute(sql("""
            INSERT INTO global.obs_macro
                (company_id, signal_type, status, headline, detail,
                 confidence, source_id, observed_at)
            SELECT c.id,
                'sector_trend', 'active',
                'Construction tech consolidation accelerating — PE and strategics hunting FSM assets',
                'The field service management (FSM) sector is seeing rapid consolidation. '
                'Private equity has shown strong appetite for vertical SaaS with sticky '
                'contractor workflows. ServiceTitan went public (Dec 2024, ~$9B market cap), '
                'validating the category. BuildOps at $1B valuation and $97M ARR is a '
                'natural M&A target for: (1) PE buyout / take-private, (2) strategic '
                'acquirer like Trimble, Autodesk, or Oracle, or (3) SPAC/IPO path in '
                '2026-27. Tidal has relevant construction/PropTech pattern recognition.',
                0.85, 'bloomberg',
                '2026-04-01'
            FROM global.companies c WHERE c.name = 'BuildOps'
            ON CONFLICT DO NOTHING;
        """))

        session.commit()

        # ── 6. Contact: Anand → Alok Chanani ─────────────────────────────────
        print("  → Inserting contact relationship...")
        session.execute(sql("""
            INSERT INTO tenant_1.contacts
                (banker_id, person_id, relationship_score, tier,
                 willingness_to_help, how_known, notes)
            SELECT b.id, p.id,
                7, 'tier_2',
                'neutral',
                'Met at Meritech Capital portfolio event, Q4 2025.',
                'Alok is founder-led, commercially sharp. BuildOps is his first company '
                '— likely thinking about liquidity path and strategic options. '
                'He respects bankers who understand the FSM space, not generalists.'
            FROM tenant_1.bankers b, global.people p
            WHERE b.name = 'Anand Sankaralingam' AND p.full_name = 'Alok Chanani'
            ON CONFLICT (banker_id, person_id) DO NOTHING;
        """))
        session.commit()

        # ── 7. Alert for Anand ────────────────────────────────────────────────
        print("  → Inserting alert for Anand...")
        session.execute(sql("""
            INSERT INTO tenant_1.alerts
                (banker_id, trigger_type, title, body,
                 cited_sources, target_company_id, relevance_score, status)
            SELECT b.id,
                'growth_signal',
                'BuildOps hits $97M ARR (+88%% YoY) — Series C closes at $1B valuation',
                'SIGNAL: BuildOps (commercial contractor FSM) closed $127M Series C in '
                'March 2025 at a $1B valuation led by Meritech Capital. ARR is $97M, '
                'growing 88%% YoY. New GTM leadership hired (CRO + CMO) in late 2025, '
                'signaling push toward scale and eventual exit. '
                'PE and strategic acquirers (Trimble, Autodesk, Oracle) are active in '
                'this category post-ServiceTitan IPO. '
                '\n\nWHY THIS MATTERS FOR ANAND: '
                'Tidal has construction/PropTech pattern recognition. '
                'At $97M ARR and growing, BuildOps is approaching a natural inflection '
                'point where a sell-side mandate or growth equity process makes sense. '
                'Anand met Alok Chanani at Meritech portfolio event (Q4 2025) — '
                'warm path exists. Time to re-engage before larger banks circle.',
                '["TechCrunch: BuildOps Series C $127M (Mar 2025)", "GetLatka: BuildOps ARR $97M (2025)"]'::jsonb,
                c.id,
                0.88,
                'unread'
            FROM tenant_1.bankers b, global.companies c
            WHERE b.name = 'Anand Sankaralingam' AND c.name = 'BuildOps'
            ON CONFLICT DO NOTHING;
        """))
        session.commit()

        # ── 8. Context note ───────────────────────────────────────────────────
        print("  → Inserting context note...")
        session.execute(sql("""
            INSERT INTO tenant_1.context_notes
                (banker_id, company_id, person_id, source, note_text)
            SELECT b.id, c.id, p.id,
                'AI',
                'AI SIGNAL: BuildOps fits Tidal''s construction/PropTech franchise. '
                '$97M ARR, 88%% growth, $1B valuation — classic pre-exit vertical SaaS profile. '
                'ServiceTitan IPO at $9B validates the FSM category. BuildOps is the '
                'commercial contractor equivalent and is likely evaluating strategic options. '
                'Meritech and BOND are growth-oriented investors with 5-7yr fund cycles — '
                'both have incentive to explore liquidity. Recommend Anand re-engage Alok '
                'with a market update framing: "The ServiceTitan comp sets a clear public '
                'market benchmark. Here''s how BuildOps looks against it."'
            FROM tenant_1.bankers b, global.companies c, global.people p
            WHERE b.name = 'Anand Sankaralingam'
              AND c.name = 'BuildOps'
              AND p.full_name = 'Alok Chanani'
            ON CONFLICT DO NOTHING;
        """))
        session.commit()

    print("\nVerifying BuildOps data...")
    with Session(engine) as session:
        result = session.execute(sql("""
            SELECT
                (SELECT COUNT(*) FROM global.companies WHERE name = 'BuildOps') AS companies,
                (SELECT COUNT(*) FROM tenant_1.bankers WHERE name = 'Anand Sankaralingam') AS bankers,
                (SELECT COUNT(*) FROM global.obs_financial WHERE company_id = (SELECT id FROM global.companies WHERE name = 'BuildOps')) AS obs_financial,
                (SELECT COUNT(*) FROM global.obs_competitive WHERE company_id = (SELECT id FROM global.companies WHERE name = 'BuildOps')) AS obs_competitive,
                (SELECT COUNT(*) FROM global.obs_macro WHERE company_id = (SELECT id FROM global.companies WHERE name = 'BuildOps')) AS obs_macro,
                (SELECT COUNT(*) FROM tenant_1.alerts WHERE target_company_id = (SELECT id FROM global.companies WHERE name = 'BuildOps')) AS alerts
        """)).fetchone()

        print(f"  ✅ global.companies (BuildOps): {result[0]}")
        print(f"  ✅ tenant_1.bankers (Anand): {result[1]}")
        print(f"  ✅ global.obs_financial: {result[2]}")
        print(f"  ✅ global.obs_competitive: {result[3]}")
        print(f"  ✅ global.obs_macro: {result[4]}")
        print(f"  ✅ tenant_1.alerts (for Anand): {result[5]}")

    print("\nBuildOps seed complete.")


if __name__ == "__main__":
    run()
