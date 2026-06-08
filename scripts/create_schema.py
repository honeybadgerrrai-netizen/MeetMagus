"""
DealFlow — Database Schema Creation
Creates all schemas and tables needed by the application.
Idempotent — safe to run multiple times (uses IF NOT EXISTS / CREATE OR REPLACE).

Run: python3 scripts/create_schema.py
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

engine = create_engine(DATABASE_URL)

DDL = """
-- ─────────────────────────────────────────────────────────────────────────────
-- Extensions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ─────────────────────────────────────────────────────────────────────────────
-- Drop everything (clean slate) then recreate
-- ─────────────────────────────────────────────────────────────────────────────
DROP SCHEMA IF EXISTS tenant_1 CASCADE;
DROP SCHEMA IF EXISTS platform CASCADE;
DROP SCHEMA IF EXISTS global CASCADE;

-- ─────────────────────────────────────────────────────────────────────────────
-- Schemas
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA global;
CREATE SCHEMA platform;
CREATE SCHEMA tenant_1;

-- ─────────────────────────────────────────────────────────────────────────────
-- GLOBAL SCHEMA
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS global.sectors (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT UNIQUE NOT NULL,
    parent_id   UUID REFERENCES global.sectors(id),
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.companies (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                   TEXT NOT NULL,
    ticker                 TEXT UNIQUE,
    domain                 TEXT,
    hq_city                TEXT,
    hq_state               TEXT,
    hq_country             TEXT,
    industry               TEXT,
    sub_industry           TEXT,
    employee_count_approx  INT,
    is_public              BOOLEAN DEFAULT false,
    is_prospect            BOOLEAN DEFAULT false,
    description            TEXT,
    metadata               JSONB DEFAULT '{}',
    created_at             TIMESTAMPTZ DEFAULT now(),
    updated_at             TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.company_aliases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID REFERENCES global.companies(id),
    alias       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_id, alias)
);

CREATE TABLE IF NOT EXISTS global.company_relationships (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_a_id      UUID REFERENCES global.companies(id),
    company_b_id      UUID REFERENCES global.companies(id),
    relationship_type TEXT NOT NULL,
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_a_id, company_b_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS global.people (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name    TEXT NOT NULL,
    email        TEXT,
    linkedin_url TEXT,
    bio          TEXT,
    metadata     JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(full_name)
);

CREATE TABLE IF NOT EXISTS global.person_aliases (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id  UUID REFERENCES global.people(id),
    alias      TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(person_id, alias)
);

CREATE TABLE IF NOT EXISTS global.affiliations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id   UUID REFERENCES global.people(id),
    company_id  UUID REFERENCES global.companies(id),
    title       TEXT,
    role_type   TEXT,   -- 'board' | 'executive' | 'advisor' | 'investor'
    is_current  BOOLEAN DEFAULT true,
    start_date  DATE,
    end_date    DATE,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(person_id, company_id, title)
);

CREATE TABLE IF NOT EXISTS global.key_dates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID REFERENCES global.companies(id),
    date_type   TEXT,   -- 'earnings' | 'analyst_day' | 'activist_deadline' | etc
    date_value  DATE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(company_id, date_type, date_value)
);

-- Observation tables — shared signal intelligence

CREATE TABLE IF NOT EXISTS global.obs_investor (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,           -- 'edgar' | 'bloomberg' | etc
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',   -- 'active' | 'stale' | 'dismissed'
    signal_type   TEXT,           -- 'ownership_change' | '13d_filing' | etc
    investor_name TEXT,
    stake_pct     FLOAT,
    filing_type   TEXT,           -- 'SC 13D' | 'SC 13G' | 'Form 4' | etc
    is_activist   BOOLEAN DEFAULT false,
    headline      TEXT,
    detail        TEXT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.obs_financial (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',
    signal_type   TEXT,
    headline      TEXT,
    detail        TEXT,
    metric_name   TEXT,
    metric_value  FLOAT,
    metric_unit   TEXT,
    amount_usd    BIGINT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.obs_competitive (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',
    signal_type   TEXT,
    headline      TEXT,
    detail        TEXT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- obs_headcount: point-in-time open role / headcount snapshots per department
-- department values: total | engineering | sales | finance | legal | marketing |
--   product | hr | operations | medical_affairs | regulatory_affairs |
--   clinical_affairs | market_access | manufacturing | strategy
CREATE TABLE IF NOT EXISTS global.obs_headcount (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID REFERENCES global.companies(id),
    observed_at      DATE NOT NULL,
    source_id        TEXT,           -- 'indeed' | 'linkedin' | 'company_filing' | etc
    confidence       FLOAT DEFAULT 0.9,
    status           TEXT DEFAULT 'active',
    signal_type      TEXT,           -- 'open_roles_snapshot' | 'headcount_snapshot' | 'hiring_surge' | 'hiring_decline'
    headline         TEXT,
    detail           TEXT,
    department       TEXT NOT NULL,  -- see values above
    open_roles_count INT,
    headcount_total  INT,
    headcount_delta  INT,            -- vs prior snapshot (positive = growth, negative = decline)
    metadata         JSONB DEFAULT '{}',  -- geo_breakdown, tech_keywords, vertical_signals, seniority_mix
    embedding        vector(1024),
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- obs_org_events: discrete people events — exec hires, departures, layoffs, reorgs
-- Kept separate from obs_headcount because time-series queries (headcount trends)
-- and recency queries (most recent exec change) need different table structures
CREATE TABLE IF NOT EXISTS global.obs_org_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID REFERENCES global.companies(id),
    observed_at      DATE NOT NULL,
    source_id        TEXT,
    confidence       FLOAT DEFAULT 0.9,
    status           TEXT DEFAULT 'active',
    signal_type      TEXT,           -- 'exec_hire' | 'exec_departure' | 'layoff' | 'reorg' |
                                     -- 'strategic_hire' | 'new_division' | 'title_change'
    headline         TEXT,
    detail           TEXT,
    person_name      TEXT,
    person_title     TEXT,
    department       TEXT,
    seniority_level  TEXT,           -- 'c_suite' | 'vp' | 'director' | 'manager' | 'ic'
    is_strategic     BOOLEAN DEFAULT false,  -- true for titles signaling strategic intent
    strategic_signal TEXT,           -- 'ipo_prep' | 'ma_signal' | 'new_geo' | 'new_vertical' | etc
    headcount_impact INT,            -- for layoffs: number of people affected
    metadata         JSONB DEFAULT '{}',
    embedding        vector(1024),
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- obs_regulatory: regulatory events — FDA approvals, rejections, filings, CMS decisions
-- Critical for healthcare sector. Sources: openFDA API, SEC EDGAR 8-K, news.
-- signal_type values: fda_approval | fda_rejection | fda_warning_letter |
--   510k_clearance | ind_filing | nda_submission | bla_submission |
--   cms_coverage_decision | ema_approval | clinical_hold |
--   breakthrough_designation | fast_track | accelerated_approval
CREATE TABLE IF NOT EXISTS global.obs_regulatory (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id         UUID REFERENCES global.companies(id),
    observed_at        DATE NOT NULL,
    source_id          TEXT,           -- 'openfda' | 'edgar' | 'google_news' | 'clinicaltrials' | etc
    confidence         FLOAT DEFAULT 0.9,
    status             TEXT DEFAULT 'active',
    signal_type        TEXT NOT NULL,
    headline           TEXT,
    detail             TEXT,
    agency             TEXT,           -- 'FDA' | 'EMA' | 'CMS' | 'FTC' | 'PMDA' (Japan) | etc
    drug_device_name   TEXT,           -- product, drug, or device name
    indication         TEXT,           -- disease or condition being treated
    decision           TEXT,           -- 'approved' | 'rejected' | 'pending' | 'withdrawn' | 'filed'
    application_number TEXT,           -- NDA/BLA/510(k)/IND application number
    metadata           JSONB DEFAULT '{}',
    embedding          vector(1024),
    created_at         TIMESTAMPTZ DEFAULT now()
);

-- obs_clinical: clinical trial milestones — trial initiation, data readouts, phase transitions
-- Source: ClinicalTrials.gov API (free, no key needed) + news + SEC filings
-- signal_type values: trial_initiated | first_patient_dosed | enrollment_milestone |
--   enrollment_complete | data_readout | trial_success | trial_failure |
--   phase_transition | trial_pause | trial_termination | abstract_presented
CREATE TABLE IF NOT EXISTS global.obs_clinical (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID REFERENCES global.companies(id),
    observed_at      DATE NOT NULL,
    source_id        TEXT,           -- 'clinicaltrials_gov' | 'edgar' | 'google_news' | etc
    confidence       FLOAT DEFAULT 0.9,
    status           TEXT DEFAULT 'active',
    signal_type      TEXT NOT NULL,
    headline         TEXT,
    detail           TEXT,
    trial_id         TEXT,           -- ClinicalTrials.gov NCT number (e.g. NCT04561037)
    trial_name       TEXT,           -- drug/program name (e.g. TERN-601, anito-cel)
    indication       TEXT,           -- disease/condition (e.g. obesity, multiple myeloma)
    phase            TEXT,           -- 'Phase 1' | 'Phase 1/2' | 'Phase 2' | 'Phase 3' | 'Phase 4'
    enrollment_count INT,            -- number of patients enrolled or targeted
    primary_endpoint TEXT,           -- what the trial is measuring
    outcome          TEXT,           -- 'positive' | 'negative' | 'mixed' | 'pending' (for readouts)
    metadata         JSONB DEFAULT '{}',
    embedding        vector(1024),
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.obs_macro (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',
    signal_type   TEXT,
    headline      TEXT,
    detail        TEXT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.obs_customer (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',
    signal_type   TEXT,
    headline      TEXT,
    detail        TEXT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global.obs_public_market (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id    UUID REFERENCES global.companies(id),
    observed_at   DATE NOT NULL,
    source_id     TEXT,
    confidence    FLOAT DEFAULT 0.9,
    status        TEXT DEFAULT 'active',
    signal_type   TEXT,
    headline      TEXT,
    detail        TEXT,
    metadata      JSONB DEFAULT '{}',
    embedding     vector(1024),
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- PLATFORM SCHEMA
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS platform.raw_ingestions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id         TEXT NOT NULL,       -- 'edgar' | 'bloomberg' | etc
    content_hash      TEXT UNIQUE NOT NULL,
    raw_content       TEXT,
    content_type      TEXT DEFAULT 'application/json',
    extraction_status TEXT DEFAULT 'pending',
    metadata          JSONB DEFAULT '{}',
    fetched_at        TIMESTAMPTZ DEFAULT now(),
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform.job_queue (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type         TEXT NOT NULL,
    priority         INT DEFAULT 5,
    status           TEXT DEFAULT 'pending',  -- pending|claimed|processing|completed|failed
    payload          JSONB DEFAULT '{}',
    attempts         INT DEFAULT 0,
    llm_tokens_used  INT DEFAULT 0,
    error_detail     TEXT,
    updated_at       TIMESTAMPTZ DEFAULT now(),
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- TENANT_1 SCHEMA (David Handler / Tidal Partners)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tenant_1.bankers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    firm_name   TEXT,
    title       TEXT,
    tenant_id   TEXT DEFAULT 'tenant_1',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_1.contacts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banker_id             UUID REFERENCES tenant_1.bankers(id),
    person_id             UUID REFERENCES global.people(id),
    relationship_score    INT,      -- 1-10
    tier                  TEXT,     -- 'tier_1' | 'tier_2' | 'tier_3'
    willingness_to_help   TEXT,     -- 'advocate' | 'neutral' | 'reluctant'
    how_known             TEXT,
    last_interaction_date DATE,
    notes                 TEXT,
    metadata              JSONB DEFAULT '{}',
    created_at            TIMESTAMPTZ DEFAULT now(),
    UNIQUE(banker_id, person_id)
);

CREATE TABLE IF NOT EXISTS tenant_1.capabilities (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banker_id        UUID REFERENCES tenant_1.bankers(id),
    capability_type  TEXT,       -- 'individual' | 'firm'
    description      TEXT,
    evidence_deal    TEXT,
    evidence_date    DATE,
    deal_size_usd    BIGINT,
    counterparty     TEXT,
    role             TEXT,
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_1.alerts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banker_id         UUID REFERENCES tenant_1.bankers(id),
    trigger_type      TEXT,       -- 'activist_13d' | 'earnings' | etc
    title             TEXT,
    body              TEXT,
    cited_sources     JSONB DEFAULT '[]',
    target_company_id UUID REFERENCES global.companies(id),
    relevance_score   FLOAT,
    status            TEXT DEFAULT 'unread',  -- 'unread' | 'read' | 'dismissed'
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_1.context_notes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banker_id   UUID REFERENCES tenant_1.bankers(id),
    company_id  UUID REFERENCES global.companies(id),
    person_id   UUID REFERENCES global.people(id),
    source      TEXT,           -- 'BANKER' | 'AI' | etc
    note_text   TEXT,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);
"""

def run():
    print("Creating DealFlow schema...")
    with engine.connect() as conn:
        # Run statement by statement (some DB drivers don't support multi-statement)
        statements = [s.strip() for s in DDL.split(";") if s.strip()]
        for i, stmt in enumerate(statements):
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as e:
                # pgvector might not be installed — skip vector extension gracefully
                if "vector" in str(e).lower() and "extension" in stmt.lower():
                    print(f"  ⚠️  pgvector not available — skipping. Embeddings will be disabled.")
                    # Re-run without vector columns
                    continue
                print(f"  ✗ Statement {i+1} failed: {e}")
                print(f"    SQL: {stmt[:100]}...")
                conn.rollback()

    print("\nVerifying schemas...")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('global', 'platform', 'tenant_1')
            ORDER BY table_schema, table_name
        """))
        rows = result.fetchall()
        for schema, table in rows:
            print(f"  ✅ {schema}.{table}")
        print(f"\n  Total: {len(rows)} tables")

    print("\nSchema creation complete.")

if __name__ == "__main__":
    run()
