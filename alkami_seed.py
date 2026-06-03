"""
Alkami Technology — DealFlow Seed Script
Scenario: Prospect = Alkami (ALKT), Banker = David Handler (Tidal Partners)
Warm path: David Handler ↔ Jeff Fox via shared Penn Entertainment board seat

Run: DATABASE_URL="postgresql://..." python -m scripts.alkami_seed
"""

import os
from datetime import date, datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dealflow_dev.db")
engine = create_engine(DATABASE_URL)

def now():
    return datetime.now(timezone.utc)

def seed():
    with Session(engine) as session:
        print("🌱 Seeding Alkami scenario...")

        # ──────────────────────────────────────────
        # COMPANIES
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.companies
                (name, ticker, domain, hq_city, hq_state, hq_country,
                 industry, sub_industry, employee_count_approx,
                 is_public, is_prospect, description, created_at, updated_at)
            VALUES
            -- Prospect
            ('Alkami Technology', 'ALKT', 'alkami.com', 'Plano', 'TX', 'USA',
             'Financial Technology', 'Digital Banking Software', 2800,
             true, true,
             'Cloud-based digital banking platform for credit unions and community/regional banks. '
             '301 FI clients, 22.4M users, $493M ARR (Q1 2026). '
             'Acquired MANTL (account onboarding) for $400M in Feb 2025.',
             now(), now()),

            -- Activist investor
            ('Jana Partners', NULL, 'janapartners.com', 'New York', 'NY', 'USA',
             'Asset Management', 'Activist Hedge Fund', 50,
             false, false,
             'Activist hedge fund. Holds 5.1% stake + 2.8% swap in Alkami (ALKT). '
             'Pushing to restart strategic sale process as of May 2026.',
             now(), now()),

            -- Large shareholder / early backer
            ('General Atlantic', NULL, 'generalatlantic.com', 'New York', 'NY', 'USA',
             'Private Equity', 'Growth Equity', 400,
             false, false,
             'Largest single Alkami shareholder at ~18.7M shares (18%). Early growth-equity backer.',
             now(), now()),

            -- Competitor 1
            ('Fiserv', 'FI', 'fiserv.com', 'Milwaukee', 'WI', 'USA',
             'Financial Technology', 'Core Banking & Payments', 40000,
             true, false,
             'Largest fintech infrastructure provider. Competes via Architect digital banking suite.',
             now(), now()),

            -- Competitor 2
            ('FIS', 'FIS', 'fisglobal.com', 'Jacksonville', 'FL', 'USA',
             'Financial Technology', 'Core Banking & Payments', 55000,
             true, false,
             'Global fintech and banking solutions. Competes in digital banking for FIs.',
             now(), now()),

            -- Acquiree (Alkami deal)
            ('MANTL', NULL, 'mantl.com', 'New York', 'NY', 'USA',
             'Financial Technology', 'Account Opening & Onboarding', 150,
             false, false,
             'Acquired by Alkami for $400M in Feb 2025. Account opening and onboarding platform for FIs.',
             now(), now()),

            -- Penn Entertainment (connects Handler ↔ Fox)
            ('Penn Entertainment', 'PENN', 'pennentertainment.com', 'Wyomissing', 'PA', 'USA',
             'Gaming & Hospitality', 'Casino & Sports Betting', 20000,
             true, false,
             'Regional gaming company. Board includes David Handler (Tidal Partners) '
             'and Jeff Fox (Alkami director) — the warm-path nexus.',
             now(), now()),

            -- Banker employer
            ('Tidal Partners', NULL, 'tidalpartners.com', 'Palo Alto', 'CA', 'USA',
             'Investment Banking', 'M&A Advisory Boutique', 35,
             false, false,
             'Next-gen M&A boutique founded Aug 2022 by David Handler and David Neequaye (ex-Centerview). '
             'Sole advisor on Cisco/Splunk ($28B, 2023) and ServiceNow/Armis ($7.75B, Dec 2025). '
             'Deep enterprise software and cloud tech franchise.',
             now(), now())
            ON CONFLICT (ticker) DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # COMPANY RELATIONSHIPS
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.company_relationships
                (company_a_id, company_b_id, relationship_type, notes, created_at)
            SELECT a.id, b.id, 'competes_with', 'Both compete for digital banking contracts at community/regional FIs', now()
            FROM global.companies a, global.companies b
            WHERE a.ticker = 'ALKT' AND b.ticker = 'FI'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.company_relationships
                (company_a_id, company_b_id, relationship_type, notes, created_at)
            SELECT a.id, b.id, 'competes_with', 'Both compete for digital banking contracts at community/regional FIs', now()
            FROM global.companies a, global.companies b
            WHERE a.ticker = 'ALKT' AND b.ticker = 'FIS'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.company_relationships
                (company_a_id, company_b_id, relationship_type, notes, created_at)
            SELECT a.id, b.id, 'acquired', 'Alkami acquired MANTL for $400M enterprise value, Feb 2025', now()
            FROM global.companies a, global.companies b
            WHERE a.ticker = 'ALKT' AND b.name = 'MANTL'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.company_relationships
                (company_a_id, company_b_id, relationship_type, notes, created_at)
            SELECT a.id, b.id, 'invested_in', 'General Atlantic holds ~18% of Alkami (18.7M shares), early growth equity backer', now()
            FROM global.companies a, global.companies b
            WHERE a.name = 'General Atlantic' AND b.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # PEOPLE
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.people
                (full_name, email, linkedin_url, bio, created_at, updated_at)
            VALUES
            ('Jeff Fox', NULL, 'linkedin.com/in/jeff-fox',
             'CEO & Founder, Circumference Group LLC. Former CEO of Endurance International Group, '
             'Convergys Corp, and held senior roles at Alltel. Began career in investment banking '
             'at Merrill Lynch and Stephens Inc. Board: Alkami Technology (ALKT), '
             'Penn Entertainment (PENN), Westrock Coffee (WEST), Resources Connection (RGP). '
             'Duke University, BA Economics.',
             now(), now()),

            ('Alex Shootman', NULL, 'linkedin.com/in/alex-shootman',
             'CEO of Alkami Technology. Former CEO of Workfront (acquired by Adobe). '
             'Joined Alkami 2020. Overseeing growth from ~$100M to $440M+ ARR.',
             now(), now()),

            ('David Handler', NULL, 'linkedin.com/in/david-handler-1886751a',
             'Co-Founder and Managing Partner, Tidal Partners. 30+ years tech M&A banking. '
             'Built Centerview tech advisory group (2008-2022). Sole advisor on Cisco/Splunk ($28B), '
             'ServiceNow/Armis ($7.75B). Board member, Penn Entertainment (PENN). '
             'Deep relationships across enterprise software, cloud, semiconductors.',
             now(), now()),

            ('David Neequaye', NULL, 'linkedin.com/in/david-neequaye',
             'Co-Founder and Managing Partner, Tidal Partners. Former Centerview. '
             'Co-leads Tidal alongside David Handler.',
             now(), now()),

            ('Anand Sankaralingam', NULL, NULL,
             'Managing Director, Tidal Partners (joined Jan 2025). '
             'Enterprise software and AI focus. Brings additional capacity to growing franchise.',
             now(), now())
            ON CONFLICT (full_name) DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # AFFILIATIONS
        # ──────────────────────────────────────────
        session.execute(text("""
            -- Jeff Fox @ Alkami board
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'Board Director (Class I)', 'board', true,
                   '2026-01-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'Jeff Fox' AND c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            -- Jeff Fox @ Penn Entertainment board
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'Board Director', 'board', true,
                   '2022-01-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'Jeff Fox' AND c.ticker = 'PENN'
            ON CONFLICT DO NOTHING;

            -- Jeff Fox @ Circumference Group
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'CEO & Founder', 'executive', true,
                   '2014-01-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'Jeff Fox' AND c.name = 'Penn Entertainment'
            ON CONFLICT DO NOTHING;

            -- Alex Shootman @ Alkami CEO
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'Chief Executive Officer', 'executive', true,
                   '2020-01-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'Alex Shootman' AND c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            -- David Handler @ Tidal Partners
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'Co-Founder & Managing Partner', 'executive', true,
                   '2022-08-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'David Handler' AND c.name = 'Tidal Partners'
            ON CONFLICT DO NOTHING;

            -- David Handler @ Penn Entertainment board (THE WARM PATH NEXUS)
            INSERT INTO global.affiliations
                (person_id, company_id, title, role_type, is_current,
                 start_date, end_date, created_at)
            SELECT p.id, c.id, 'Board Director', 'board', true,
                   '2021-01-01', NULL, now()
            FROM global.people p, global.companies c
            WHERE p.full_name = 'David Handler' AND c.ticker = 'PENN'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # BANKER (TENANT)
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO tenant_1.bankers
                (full_name, email, firm_name, title, created_at, updated_at)
            VALUES
            ('David Handler', 'dhandler@tidalpartners.com', 'Tidal Partners',
             'Co-Founder & Managing Partner', now(), now())
            ON CONFLICT (email) DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # CONTACTS (banker's network)
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO tenant_1.contacts
                (banker_id, person_id, relationship_score, tier,
                 willingness_to_help, how_known, last_interaction_date, notes, created_at)
            SELECT b.id, p.id, 9, 'tier_1', 'advocate',
                   'Shared board at Penn Entertainment (PENN) since 2021. '
                   'Regular board meeting contact, 2-4x per year. Strong collegial relationship.',
                   '2026-03-15', 'Jeff has banker DNA (Merrill Lynch start). Understands the advisory world.',
                   now()
            FROM tenant_1.bankers b, global.people p
            WHERE b.full_name = 'David Handler' AND p.full_name = 'Jeff Fox'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # CAPABILITIES (banker + firm)
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO tenant_1.capabilities
                (banker_id, capability_type, description, evidence_deal, evidence_date,
                 deal_size_usd, counterparty, role, created_at)
            VALUES
            -- Individual capabilities
            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'individual', 'Large-cap tech M&A sell-side / buy-side advisory',
             'Cisco / Splunk acquisition', '2023-09-21',
             28000000000, 'Cisco Systems',
             'Sole financial advisor to Cisco', now()),

            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'individual', 'Enterprise software and AI platform M&A',
             'ServiceNow / Armis acquisition', '2025-12-01',
             7750000000, 'ServiceNow',
             'Lead financial advisor to ServiceNow', now()),

            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'individual', 'Security software M&A',
             'Cisco / AppDynamics acquisition (prior at Centerview)', '2017-01-24',
             3700000000, 'Cisco Systems',
             'Financial advisor', now()),

            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'individual', 'Fintech and digital infrastructure M&A',
             'Cisco / NDS Group acquisition (prior at Centerview)', '2012-05-01',
             5000000000, 'Cisco Systems',
             'Financial advisor', now()),

            -- Firm-level capabilities
            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'firm', 'Convertible notes advisory for high-growth tech',
             'Fastly $180M upsized convertible senior notes', '2025-12-01',
             180000000, 'Fastly',
             'Financial advisor to Fastly', now()),

            ((SELECT id FROM tenant_1.bankers WHERE full_name = 'David Handler'),
             'firm', 'Large convertible notes and strategic financing',
             'Bloom Energy $2.5B convertible senior notes', '2025-11-01',
             2500000000, 'Bloom Energy',
             'Financial advisor to Bloom Energy', now())
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # OBSERVATIONS — INVESTOR/SHAREHOLDER
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.obs_investor
                (company_id, investor_name, investor_type, stake_pct,
                 event_type, event_description, confidence, source,
                 observed_at, created_at)
            SELECT c.id,
                'Jana Partners', 'activist_hedge_fund', 7.9,
                '13d_filing',
                'Jana Partners disclosed 5.1% direct stake plus 2.8% swap exposure in Alkami (ALKT), '
                'totaling ~7.9% economic interest. Filed Schedule 13D. Jana is pushing management '
                'to restart a strategic sale process after an initial exploration reportedly stalled. '
                'Jana views Alkami as undervalued and an attractive target for PE or a strategic acquirer. '
                'Bloomberg reported May 28, 2026 that Jana is renewing this pressure.',
                0.98, 'SEC_EDGAR_13D + Bloomberg',
                '2026-05-28', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.obs_investor
                (company_id, investor_name, investor_type, stake_pct,
                 event_type, event_description, confidence, source,
                 observed_at, created_at)
            SELECT c.id,
                'General Atlantic', 'growth_equity_pe', 18.0,
                'large_existing_holder',
                'General Atlantic holds 18.73M shares (~18% of ALKT), making them the largest '
                'single institutional shareholder. As an early growth-equity backer, GA would likely '
                'support a strategic transaction that returns capital. Their continued hold after IPO '
                'suggests alignment with long-term value creation thesis.',
                0.95, 'SEC_13F + WallStreetZen',
                '2025-12-31', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # OBSERVATIONS — FINANCIAL
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.obs_financial
                (company_id, period, period_type, revenue_usd, revenue_growth_pct,
                 gross_margin_pct, ebitda_usd, arr_usd, notes,
                 confidence, source, observed_at, created_at)
            SELECT c.id,
                '2025-12-31', 'annual',
                443600000, 32.9,
                57.2, 59100000, 480300000,
                'FY2025 results. GAAP net loss $47.7M (not yet GAAP profitable). '
                'ARR grew 35% YoY. 301 FI clients. 22.4M digital banking users (+2.4M). '
                'Rule of 45 and 70% gross margin targeted by 2030.',
                0.99, 'SEC_8K_earnings',
                '2026-02-27', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.obs_financial
                (company_id, period, period_type, revenue_usd, revenue_growth_pct,
                 gross_margin_pct, ebitda_usd, arr_usd, notes,
                 confidence, source, observed_at, created_at)
            SELECT c.id,
                '2026-03-31', 'quarterly',
                126100000, 28.9,
                58.6, 22300000, 493600000,
                'Q1 2026 results. ARR $493.6M (+22% YoY). Company also announced $100M share buyback. '
                'Gross margin expanding toward 70% target. EBITDA margin expanding ~300bps/year.',
                0.99, 'SEC_8K_earnings',
                '2026-04-29', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # OBSERVATIONS — COMPETITIVE
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.obs_competitive
                (company_id, event_type, event_description,
                 related_company, confidence, source, observed_at, created_at)
            SELECT c.id,
                'acquisition',
                'Alkami acquired MANTL (account opening and onboarding platform) for $400M enterprise value, '
                'announced Feb 27, 2025. Strategic rationale: extend beyond digital banking UX into '
                'the full new-customer journey — account opening, onboarding, low-cost deposit acquisition. '
                'Positions Alkami to compete more directly with megabanks and large fintechs. '
                'This integration is still being digested operationally.',
                'MANTL', 0.99, 'SEC_8K + press release',
                '2025-02-27', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.obs_competitive
                (company_id, event_type, event_description,
                 related_company, confidence, source, observed_at, created_at)
            SELECT c.id,
                'market_position',
                'Alkami holds strong position in credit union and community/regional bank digital banking — '
                'a market dominated by legacy providers Fiserv (Architect) and FIS. Alkami''s cloud-native '
                'platform and 35% ARR growth signal share gains. High switching costs (core-system integration, '
                'user retraining) create durable revenue once landed. 301 clients with avg ~75K users each '
                'suggests mid-market FI concentration — meaningful upsell opportunity as these FIs grow.',
                'Fiserv / FIS / NCR Voyix', 0.90, 'analyst_research + earnings',
                '2026-05-01', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # OBSERVATIONS — EMPLOYEE/HIRING
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.obs_employee
                (company_id, signal_type, signal_description,
                 confidence, source, observed_at, created_at)
            SELECT c.id,
                'active_hiring',
                'Alkami is actively hiring across engineering, product, and go-to-market as of early 2026. '
                'No layoff signals observed. Post-MANTL integration headcount growth expected in onboarding '
                'and account-opening product lines. ~2,800 employees total. '
                'Continued hiring is consistent with a company investing in growth, not distress.',
                0.80, 'Zippia + LinkedIn job postings',
                '2026-01-15', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # OBSERVATIONS — MACRO
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.obs_macro
                (company_id, theme, description,
                 confidence, source, observed_at, created_at)
            SELECT c.id,
                'fintech_consolidation',
                'The digital banking infrastructure market is consolidating. Large incumbents (Fiserv, FIS) '
                'face cloud-native challengers. PE has shown appetite for SaaS fintech with high ARR, '
                'sticky FI relationships, and visible growth — exactly Alkami''s profile. '
                'Recent activist pressure from Jana Partners and a reported prior sale exploration '
                'signal the board and major shareholders are open to a transaction.',
                0.85, 'Bloomberg + Crowdfund Insider + Seeking Alpha',
                '2026-05-28', now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # KEY DATES
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO global.key_dates
                (company_id, date_type, date_value, description, created_at)
            SELECT c.id, 'earnings', '2026-07-29',
                'Q2 2026 earnings expected (est. ~90 days after Q1 on Apr 29)',
                now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;

            INSERT INTO global.key_dates
                (company_id, date_type, date_value, description, created_at)
            SELECT c.id, 'activist_deadline', '2026-06-30',
                'Jana Partners 13D filed May 2026. Activist pressure window typically peaks '
                'in 60-90 days following disclosure. Monitor for board response or sale announcement.',
                now()
            FROM global.companies c WHERE c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # CONTEXT NOTES (banker's private notes)
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO tenant_1.context_notes
                (banker_id, company_id, person_id, source, note_text, created_at)
            SELECT b.id, NULL, p.id, 'BANKER',
                'Jeff and I have been on the Penn board together since early 2021. '
                'He''s thoughtful, commercial, and has banker instincts — started at Merrill. '
                'He''d be a credible path into any Alkami process. I should reach out before '
                'someone else does — Jana news just broke yesterday (May 28).',
                now()
            FROM tenant_1.bankers b, global.people p
            WHERE b.full_name = 'David Handler' AND p.full_name = 'Jeff Fox'
            ON CONFLICT DO NOTHING;

            INSERT INTO tenant_1.context_notes
                (banker_id, company_id, person_id, source, note_text, created_at)
            SELECT b.id, c.id, NULL, 'AI',
                'AI SIGNAL: Alkami fits Tidal''s core franchise (enterprise SaaS, $500M+ ARR, '
                'high-growth, cloud-native). Tidal advised both buyer and target sides in similar '
                'profiles: ServiceNow/Armis ($7.75B SaaS), Cisco/Splunk ($28B infrastructure SaaS). '
                'If Alkami runs a process, Tidal has the pattern recognition and the relationships to '
                'be credible as sell-side advisor. Key risk: Alkami may already have retained a bank.',
                now()
            FROM tenant_1.bankers b, global.companies c
            WHERE b.full_name = 'David Handler' AND c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        # ──────────────────────────────────────────
        # WARM PATH
        # ──────────────────────────────────────────
        # (Warm paths are computed, not stored directly — but we document
        #  the contact->company linkage so the engine can traverse it)
        # Contact: Jeff Fox (score 9, advocate) → Alkami board director
        # The warm_paths engine will find: Handler knows Fox (score 9),
        # Fox sits on Alkami board → 1-hop warm path to prospect.

        # ──────────────────────────────────────────
        # ALERT — agent-generated
        # ──────────────────────────────────────────
        session.execute(text("""
            INSERT INTO tenant_1.alerts
                (banker_id, company_id, alert_type, headline, body,
                 cited_sources, priority, created_at)
            SELECT b.id, c.id,
                '13d_filing',
                'Jana Partners reboots Alkami sale push — your Penn board colleague Jeff Fox is on their board',
                E'SIGNAL: Jana Partners (5.1% + 2.8% swap = ~7.9% economic interest) filed a 13D on '
                'Alkami Technology (ALKT) and is publicly pushing the company to restart a strategic sale '
                'process. Bloomberg reported this yesterday, May 28, 2026.\n\n'
                'YOUR WARM PATH:\n'
                '• Jeff Fox (Alkami Class I director, term to 2028) is your Penn Entertainment board '
                'colleague — score 9/10, advocate. Last board meeting contact: March 2026.\n'
                '• Jeff started his career in investment banking (Merrill Lynch, Stephens) and will '
                'understand the advisory angle immediately.\n\n'
                'ALKAMI SNAPSHOT:\n'
                '• $493M ARR (+22% YoY), $126M Q1 revenue (+29%), 301 FI clients, 22.4M users\n'
                '• MANTL acquisition ($400M, Feb 2025) still being integrated\n'
                '• General Atlantic holds 18% — likely supportive of a transaction\n'
                '• No GAAP profitability yet (net loss $47.7M in 2025) — creates valuation tension\n\n'
                'TIDAL FIT:\n'
                'Alkami''s profile (cloud SaaS, $500M ARR, enterprise clients, activist-driven process) '
                'maps directly to Tidal''s wins. You have no sector conflict currently.\n\n'
                'SUGGESTED ACTION: Reach out to Jeff through your Penn board channel before a process '
                'is formally retained. Want me to draft an outreach note?',
                ARRAY[
                    'Bloomberg: Jana Said to Push Fintech Alkami to Reboot Sales Process (2026-05-28)',
                    'SEC Schedule 13D: Jana Partners 5.1% + 2.8% swap (Apr 2026)',
                    'Alkami Q1 2026 8-K (2026-04-29)',
                    'Penn Entertainment proxy: David Handler and Jeff Fox board bios'
                ],
                'high',
                '2026-05-29'
            FROM tenant_1.bankers b, global.companies c
            WHERE b.full_name = 'David Handler' AND c.ticker = 'ALKT'
            ON CONFLICT DO NOTHING;
        """))

        session.commit()
        print("✅ Alkami scenario seeded successfully.")
        print("")
        print("Entities created:")
        print("  Companies:     Alkami, Jana Partners, General Atlantic, Fiserv, FIS, MANTL, Penn Entertainment, Tidal Partners")
        print("  People:        Jeff Fox, Alex Shootman, David Handler, David Neequaye, Anand Sankaralingam")
        print("  Affiliations:  Fox→ALKT board, Fox→PENN board, Handler→PENN board, Shootman→ALKT CEO, Handler→Tidal")
        print("  Observations:")
        print("    Investor:    Jana 13D (7.9%), General Atlantic 18%")
        print("    Financial:   FY2025 ($443M rev, $480M ARR) + Q1 2026 ($126M rev, $493M ARR)")
        print("    Competitive: MANTL acquisition, market position vs Fiserv/FIS")
        print("    Employee:    Active hiring signal")
        print("    Macro:       Fintech consolidation + activist pressure")
        print("  Key Dates:     Q2 earnings (est. Jul 29), activist window deadline (Jun 30)")
        print("  Warm Path:     Handler → Fox (score 9, Penn board) → Alkami board")
        print("  Alert:         Jana 13D + warm path to Jeff Fox + Tidal fit analysis")

if __name__ == "__main__":
    seed()
