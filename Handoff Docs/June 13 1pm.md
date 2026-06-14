# Meet Magus — Project Handoff Briefing v3
## What It Is
Meet Magus is an AI-powered intelligence platform that keeps relationship-driven professionals permanently attuned to the companies and people they care about — without them having to do any work to stay that way. The advisory coverage and deal execution is grounded on this deep understanding, and all workflows emerge out of this substrate. For e.g., whether to create a pitch deck, or what goes in pitch deck, or if there should be an outreach - be it is a simple text message, email or a proper meeting with a presentation deck, and what goes in the deck, what analysis needs to be created, who the internal team should be, coordinating the workflow among them, how to strategize and design a process, sequencing and timing, etc., are all higher order actions that emerge out of this fundamental understanding of all the constituents (companies and people involved in them).
Starting with investment bankers and M&A advisors. Expanding to healthcare bankers, consultants, staffing firms, and any professional whose value is relationship-based.

That state is built over months of continuous signal collection, not 72 hours of manual research. A bakeoff win for e.g., is one downstream outcome of this, not the product goal.

Working product name: **Meet Magus** | Domain: meetmagus.ai

---
## Multi-Layered Architecture

### Layer 1 — Continuous Signal Collection (Partially built)
Runs automatically, daily, across every company the banker tracks. Stores everything faithfully with no interpretation. All sources feed into the same observation tables regardless of sector.

**What is collected:**
- SEC EDGAR filings (13D/13G, 8-K, Form 4) — built ✅
- News signals (Google News RSS, classified by LLM) — built ✅
- Job postings (Indeed RSS — open roles, department counts, geo expansion, tech bets) — in progress
- Regulatory events (FDA approvals, NDA/BLA filings, CMS decisions) — schema built, fetcher pending
- Clinical trial milestones (ClinicalTrials.gov — first patient dosed, data readouts, phase transitions) — schema built, fetcher pending

**Department taxonomy for hiring signals (updated for healthcare):**
engineering | sales | finance | legal | marketing | product | hr | operations |
medical_affairs | regulatory_affairs | clinical_affairs | market_access | manufacturing | strategy

**Strategic hire detection (titles that always trigger obs_org_events regardless of volume):**
- Head of Investor Relations → IPO preparation signal
- General Counsel → IPO or M&A signal
- Chief Accounting Officer / CAO → IPO preparation signal
- VP of Corporate Development → M&A activity signal
- VP Market Access → drug commercial launch preparation (healthcare)
- Medical Science Liaison surge → new indication launch (healthcare)
- Head of Regulatory Affairs → new drug/device program starting (healthcare)

**Signal calibration by company size:**
What counts as a material hire scales with company size. A CPO hire at a 59-person biotech (Terns Pharmaceuticals) is as significant as a CFO departure at a Fortune 500. Threshold logic adjusts based on employee_count_approx.

### Layer 2 — Pattern Recognition (Not yet built)
Watches Layer 1 data continuously. Detects when something meaningful has changed or crossed a threshold. Does NOT interpret, narrate, or synthesise — it identifies that something worth surfacing has occurred and triggers Layer 3.

Examples of what Layer 2 detects:
- Finance hiring surged from 3 → 22 open roles in 30 days (exit preparation pattern)
- "Head of Investor Relations" title appeared for the first time (IPO signal)
- Competitor received FDA approval for a directly competing drug (competitive threat)
- Activist 13D filed on a company 2 hops from the banker's network
- Clinical trial failure announced (value destruction event)
- First patient dosed in Phase 1 (value creation event for small biotech)

Pattern synthesis (e.g. "what does Infoblox's hiring pattern suggest strategically?") happens at inference time in Layer 3 — not pre-computed and stored. The exception is time-series patterns that require comparing snapshots over months, which are stored as strategic_developments.

### Layer 3 — Always-On Intelligence Surfacing (Not yet built)
Puts Layer 2 signals in front of the banker at the right moment, without them asking. The banker did not request this — it arrived because the system noticed something they would want to know.

Delivery adapts to context:
- 2-sentence push notification at 7am
- One-page briefing if they tap in
- Verbal 90-second summary if they're in the car
- Q&A deep dive if they want more

The system infers the right format from context. The banker never chooses format.

At inference time (when a banker is preparing for a specific interaction), Layer 3 synthesises across all stored Layer 1 signals for that company — job postings, news, EDGAR, regulatory, clinical — into a coherent picture. This synthesis is done on demand, not pre-computed, so it can be tailored to the specific question.

### Layer 4 — Workflow Layer (Not yet built)
Signals become actions. Actions become collaborative. Senior banker says "get Will on this" — system creates workspace, pulls context, notifies team. All collaboration native to the product, never email. Every contribution feeds back into Layer 1.

### Layer 5 — Flywheel
Every interaction feeds back into Layer 1. Dismiss = data. Act = data. "Already know him" = relationship data. "Vista told me they're not looking to exit" = proprietary intelligence.
After 12 months: every relationship, every deal worked, every prospect evaluated, every preference. Not replicable. Not portable. Permanent switching cost.

---
## Target Sectors

### Primary: M&A / Investment Banking
Banks of all sizes: from single person shop to Mid-market advisory firms, boutiques, large banks. Signals that matter: EDGAR filings, executive moves, competitive M&A activity, customer signals, financial signals, hiring patterns indicating exit preparation.

### Expanding: Healthcare Banking
Healthcare bankers advising on biopharma, medical device, and healthcare IT transactions. Additional signals required (and now built into schema):
- **Regulatory events** (FDA approvals, rejections, filings) — often the single most value-moving event for a healthcare company
- **Clinical trial milestones** — for clinical-stage companies, trial progress IS the company's progress
- **Healthcare-specific hiring** — Medical Science Liaisons signal commercial launch; Regulatory Affairs surge signals new program; Market Access hiring signals reimbursement push
- **Healthcare M&A patterns** — program-level asset sales (e.g. Synnovation → Novartis), not just company-level

Real examples validated against actual companies (June 2026):
- Arcellx acquired by Gilead for $7.8B, 192/209 employees laid off post-close — obs_investor + obs_org_events
- Terns Pharmaceuticals first patient dosed in TERN-601 Phase 1 (GLP-1/obesity) — obs_clinical (highest-value signal for this company, invisible without this table)
- Synnovation Therapeutics sold PI3Kα program to Novartis for $2B — obs_financial + obs_competitive
- Gilead posting Medical Science Liaisons across 6 new geographies — obs_headcount + strategic signal
---
## User/Audience Constraints
- Users are 40-70 years old, senior professionals with deep pride in their judgment
- Will not learn a new interface. Will abandon after one bad experience
- UI must feel like a beautifully prepared briefing left on their desk — not an app
- No onboarding wizards, no forms, no dropdowns, no required fields, no settings pages
- Interaction patterns that work: confirm/dismiss (binary, fast), voice reply, short text reaction
- Patterns that kill the product: forms, multi-step workflows, notification badges, feature tours
- Enterprise deployment must support: single-tenant in client's cloud, SOC 2 Type II, full audit trail, SSO, configurable data retention, role-based access, ability to wipe a user's data on departure
---
## What's Built and Deployed
### Architecture — Three Schema Design (Postgres)
| Schema | What lives there |
|---|---|
| `global` | Companies, People, Affiliations, Observations, Intelligence — shared across all tenants |
| `tenant_{id}` | Banker, Contacts, Capabilities, Notes, Alerts, Prospect Tracking — private per customer |
| `platform` | Workflows, Job Queue, Source Registry, Dedup Log, Entity Resolution, Dedup Rules — infrastructure |
### Deployment
| Item | Detail |
|---|---|
| **Live URL** | `https://Meet Magus-production-f0ce.up.railway.app` |
| **API Docs** | `https://Meet Magus-production-f0ce.up.railway.app/docs` |
| **GitHub** | `honeybadgerrrai-netizen/Meet Magus` (main branch, auto-deploy on push) |
| **Hosting** | Railway (agile-upliftment project) |
| **Database** | Railway Postgres (connected via DATABASE_URL env var) |
### Seed Data
- 7 companies including Infoblox, Cisco, Arista, Vista Equity, Warburg Pincus
- 2 people: Scott Harrell (Infoblox CEO), Hoke Horne (CFO)
- 3 contacts for banker Sam Patel including warm path to Infoblox CEO
- 3 capabilities (individual + firm level)
- 3 context notes including AI-extracted hiring signal analysis
- 1 pre-built alert: "Vista Equity at Year 9 on Infoblox — Exit Window Now Open"
**To seed:** Get DATABASE_URL from Railway → Postgres → Variables, then:
```bash
cd ~/Downloads/Meet Magus
DATABASE_URL="postgresql://..." python -m scripts.seed
```
---
## Complete Table Inventory
### Global Schema — Shared Intelligence
**`companies`** — every company in the system (prospects, employers, competitors, PE firms, banks). Name, type, sector, HQ, ticker, revenue, headcount, description, embedding columns. NOTE: `is_prospect` removed — prospect status is tenant-specific, lives in `prospect_tracking`.
**`people`** — every person. Name, contact info, location, embedding columns. NOTE: `is_prospect` removed — same reason.
**`affiliations`** — person ↔ company roles. Role type, title, start/end dates, is_current. Enables one person = CEO of A, board of B, GP at C simultaneously.
**`company_relationships`** — bidirectional typed edges between companies. Types: competes_with, sells_to, invested_in, partners_with, acquired, subsidiary_of, joint_venture. Description, observed_at, source, confidence.
**`sectors`** — first-class sector records with parent/child hierarchy.
**`company_aliases`** — entity resolution. Every variant (GS, Goldman Sachs, Goldman Sachs Group Inc) maps to one canonical company. Status: pending/confirmed/rejected. AI confidence score.
**`person_aliases`** — same for people.
**`key_dates`** — important dates per company as timestamped observations: earnings_release, earnings_call, quiet_period_start/end, fiscal_year_end, quarter_end, annual_shareholder_meeting, proxy_filing, 10k_filing, 10q_filing, board_meeting, lockup_expiry, debt_maturity, regulatory_milestone, banker_conference, budget_cycle_start.
**Nine observation tables** — each a separate table, all sharing the same observation DNA (company_id, observed_at, source_id, confidence, status, embedding). All sectors use the same tables; healthcare-specific signals use obs_regulatory and obs_clinical:

**`obs_macro`** — macro trend signals. trend_name, trend_description, relevance_note, impact_direction (tailwind/headwind/neutral), sector_scope.

**`obs_financial`** — externally observed financial signals. signal_type (revenue_signal, margin_signal, fundraising, burn_signal, valuation, debt_maturity, revenue_mix, program_sale), headline, detail, amount_usd, metric_name/value/unit.

**`obs_investor`** — investor/shareholder/activist signals. signal_type (13d_filing, 13g_filing, insider_buy, insider_sell, institutional_change, activist_letter, board_demand, ownership_change), investor_name, stake_pct, filing_type, is_activist.

**`obs_competitive`** — competitive intelligence. signal_type (product_launch, pricing_change, partnership, acquisition, market_share, win_loss, drug_approval, patent_expiration, clinical_failure), competitor details, product_overlap_note.

**`obs_customer`** — customer relationship signals. signal_type (new_customer, contract_renewal, churn_signal, expansion, reference, formulary_win, formulary_loss, hospital_contract), customer details, contract_value_usd.

**`obs_headcount`** — point-in-time open role / headcount snapshots per department. department values: engineering | sales | finance | legal | marketing | product | hr | operations | medical_affairs | regulatory_affairs | clinical_affairs | market_access | manufacturing | strategy. open_roles_count, headcount_total, headcount_delta. metadata JSONB stores: geo_breakdown, tech_keywords, vertical_signals, seniority_mix. Source: Indeed RSS, LinkedIn, company filings.

**`obs_org_events`** — discrete people events. signal_type (exec_hire, exec_departure, layoff, reorg, strategic_hire, new_division, title_change). person_name, person_title, seniority_level, is_strategic flag, strategic_signal (ipo_prep | ma_signal | new_geo | new_vertical | commercial_launch). Threshold for "strategic" scales with company size — a CPO hire at a 59-person biotech (e.g. Terns Pharmaceuticals) is as material as a CFO departure at a Fortune 500.

**`obs_public_market`** — public companies only. signal_type (analyst_rating, price_target, short_interest, stock_snapshot), analyst_firm, rating, price_target_usd.

**`obs_regulatory`** *(new — healthcare)* — regulatory events from FDA, EMA, CMS, FTC. signal_type (fda_approval, fda_rejection, fda_warning_letter, 510k_clearance, ind_filing, nda_submission, bla_submission, cms_coverage_decision, ema_approval, clinical_hold, breakthrough_designation, fast_track, accelerated_approval). Fields: agency, drug_device_name, indication, decision, application_number. Source: openFDA API (free), EDGAR 8-K, news. Critical for healthcare — an FDA approval can move a company's value by billions overnight; a warning letter can crater it.

**`obs_clinical`** *(new — healthcare)* — clinical trial milestones. signal_type (trial_initiated, first_patient_dosed, enrollment_milestone, enrollment_complete, data_readout, trial_success, trial_failure, phase_transition, trial_pause, trial_termination, abstract_presented). Fields: trial_id (ClinicalTrials.gov NCT number), trial_name, indication, phase, enrollment_count, primary_endpoint, outcome. Source: ClinicalTrials.gov API (free, no key). For clinical-stage companies like Terns Pharmaceuticals or Synnovation Therapeutics, trial milestones are the highest-value signals — invisible to the system without this table.
### Tenant Schema — Per-Customer Private Data
**`bankers`** — the user. tenant_id, name, email, title, employer_company_id.
**`contacts`** — banker's personal network. Name, email, employer info, relationship_score (1-10), relationship_tier (close/warm/acquaintance/cold), willingness_to_help (advocate/intro/reference_only/unknown/no), last_contact_date, notes, linked_person_id (bridge to global.people).
**`capabilities`** — individual and firm-level. scope (individual/firm), category, name, description, sector/geo focus, deal size range, track record count, firm_company_id.
**`capability_events`** — publicly observed deals/announcements substantiating capabilities. event_type (closed_deal/league_table/press_release), headline, deal_size_usd, sector, counterparty_company_id, announced_at, source_url.
**`context_notes`** — free-form timestamped notes. source_type (BANKER/AI), tagged_company_ids, tagged_person_ids, is_standing_preference, embedding columns.
**`alerts`** — agent-generated briefings. trigger_type, title, body, cited_sources (JSON), target_company_id, relevance_score, status (unread/read/acted/dismissed), banker_feedback.
**`prospect_tracking`** — NEW. Replaces is_prospect boolean. Full pipeline journey per entity per banker:
- Stages: no_contact → researching → outreach → intro → engaged → pitching → competing → mandated → executing → closed → dormant → passed → lost
- Fields: banker_id, entity_type (company/person), entity_id, stage, stage_changed_at, owner_banker_id, notes, next_action, next_action_date
**`prospect_stage_history`** — NEW. Append-only log of every stage transition. from_stage, to_stage, changed_by, reason, changed_at. Never lose the journey.
### Platform Schema — Infrastructure
**`source_registry`** — licensing and compliance rules per source. source_id, can_store_raw, can_display_to_user, requires_attribution, retention_days, reliability_rank, dedup_threshold.
**`source_monitors`** — what sources are watched per company. company_id, source_id, fetch_cadence_minutes, last_fetched_at, consecutive_failures.
**`raw_ingestions`** — raw fetched content before extraction. content_hash, extraction_status, expires_at.
**`workflow_definitions`** — agent workflow templates. trigger_type, steps_json, retry_max.
**`workflow_runs`** — one per execution. definition_id, tenant_id, status, trace_id, is_eval.
**`workflow_steps`** — one per step per run. input/output payloads, retry_count, llm_tokens_used, llm_cost_usd.
**`job_queue`** — all async work. job_type (generate_embedding/ingest_source/run_workflow/fan_out_alert), priority (1=highest), tenant_id, payload, status, attempts.
**`llm_budgets`** — per-tenant daily LLM cost limits.
**`freshness_policies`** — staleness thresholds per observation type.
**`dedup_log`** — rejected duplicate signals with similarity score, threshold used, source.
**`dedup_rules`** — NEW. Configurable per observation type: match_fields (JSON), numeric_tolerance, time_window_days, semantic_threshold, novelty_check_enabled, action (reject/merge/flag_for_review).
**`entity_resolution_queue`** — aliases awaiting human confirmation.
---
## Four-Level Deduplication Pipeline
```
Incoming signal
  │
  ├─ Level 1: Content hash match? → reject, log, stop
  │
  ├─ Level 2: Structured field match within time window? → merge (update confidence), log, stop
  │
  ├─ Level 3a: Embedding similarity above threshold? → if NO, write new observation
  │    if YES → continue to 3b
  │
  ├─ Level 3b: LLM material novelty check → YES = write + link related_observation_id
  │                                        → NO = reject, log with reasoning
  │
  └─ Level 4: Temporal decay — same fact becomes "new" again after time_window_days
```
All configurable per observation type via `dedup_rules` table.
---
## Model Configuration
```yaml
# config/models.yaml
providers:
  deepinfra:
    base_url: "https://api.deepinfra.com/v1/openai"
    api_key_env: "DEEPINFRA_API_KEY"
    openai_compatible: true
  fireworks:
    base_url: "https://api.fireworks.ai/inference/v1"
    api_key_env: "FIREWORKS_API_KEY"
    openai_compatible: true
  together:
    base_url: "https://api.together.xyz/v1"
    api_key_env: "TOGETHER_API_KEY"
    openai_compatible: true
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    openai_compatible: true
  self_hosted:
    base_url: "${QWEN_ENDPOINT_URL}"
    api_key_env: "QWEN_API_KEY"
    openai_compatible: true
models:
  extraction:
    description: "Parse raw content into structured observations"
    provider: "deepinfra"
    model: "Qwen/Qwen3-8B"
    max_tokens: 500
    temperature: 0.1
    fallback_provider: "fireworks"
    fallback_model: "accounts/fireworks/models/qwen3-8b-instruct"
  dedup_novelty:
    description: "Level 3b material novelty check"
    provider: "deepinfra"
    model: "Qwen/Qwen3-8B"
    max_tokens: 100
    temperature: 0.0
    fallback_provider: "together"
    fallback_model: "Qwen/Qwen3-8B"
  entity_resolution:
    description: "Suggest alias matches"
    provider: "deepinfra"
    model: "Qwen/Qwen3-8B"
    max_tokens: 200
    temperature: 0.0
    fallback_provider: "openrouter"
    fallback_model: "qwen/qwen3-8b"
  pattern_detection:
    description: "Detect patterns across observations"
    provider: "deepinfra"
    model: "Qwen/Qwen3-32B"
    max_tokens: 1000
    temperature: 0.2
    fallback_provider: "fireworks"
    fallback_model: "accounts/fireworks/models/qwen3-32b-instruct"
  alert_generation:
    description: "Compose banker-facing alert briefings"
    provider: "deepinfra"
    model: "Qwen/Qwen3-32B"
    max_tokens: 2000
    temperature: 0.3
    fallback_provider: "together"
    fallback_model: "Qwen/Qwen3-32B"
  embedding:
    description: "Generate vector embeddings"
    provider: "deepinfra"
    model: "BAAI/bge-large-en-v1.5"
    dimensions: 1024
    fallback_provider: "fireworks"
    fallback_model: "nomic-ai/nomic-embed-text-v1.5"
  agent_reasoning:
    description: "Complex multi-step agent reasoning"
    provider: "deepinfra"
    model: "Qwen/Qwen3-235B-A22B"
    max_tokens: 4000
    temperature: 0.2
    fallback_provider: "together"
    fallback_model: "Qwen/Qwen3-235B-A22B"
defaults:
  retry_max: 3
  retry_delay_seconds: 2
  timeout_seconds: 30
```
### Why this structure
- Every task maps to a specific model size — 8B for cheap high-volume, 32B for quality, 235B for complex reasoning
- Provider and model are both configurable — switch from DeepInfra to Fireworks or self-hosted by changing one line
- All providers expose OpenAI-compatible API — one client interface in application code
- Fallback chain means graceful degradation, never hard failure
- For enterprise single-tenant: change provider to self_hosted, point at vLLM in client's cloud

---
## Architectural Decisions Made
1. **Semantic search**: pgvector in Postgres, day-one requirement for agent queries
2. **Tenant isolation**: Schema-level separation (not RLS, not per-tenant copies)
3. **Ingestion pipeline**: Three layers — fetch, extract, resolve — each independently retriable
4. **Observation confidence**: Source reliability ranking + recency weighting + conflict flagging
5. **Audit trail**: Full provenance on observations, resolutions, notes, agent runs
6. **Soft deletes**: Append-only with status (active/superseded/rejected/deleted) and superseded_by chain
7. **Freshness policies**: Per observation type, enforced at display and agent level
8. **Agent orchestration**: workflow_definitions → workflow_runs → workflow_steps with full step-level audit
9. **Rate limiting**: Job queue with priority, per-tenant LLM budgets
10. **Deduplication**: Four-level system (hash → structured match → embedding similarity → LLM novelty check)
11. **Model routing**: YAML config with provider + model per task, fallback chains, OpenAI-compatible API throughout
12. **Open-source models only**: Qwen family via US-based inference providers (DeepInfra primary). No Alibaba servers. Enterprise: self-hosted via vLLM in client's cloud.
---
## What's Next (Recommended Order)
1. **Run the seed** to populate demo data on Railway Postgres
2. **Build SEC EDGAR fetcher** — 13D/13G filings, 8-K, insider transactions (free API)
3. **Build news fetcher** — headlines via NewsAPI or similar
4. **Build extraction pipeline** — raw content → structured observations via Qwen3-8B on DeepInfra
5. **Build embedding background job** — poll job_queue, generate embeddings, update records
6. **Wire dedup pipeline** — four levels as described
7. **Add semantic search endpoint** — `/search?q=...&banker_id=1`
8. **Build the 13D trigger agent** — the defining use case
9. **Add auth** — JWT or Clerk
10. **Add prospect_tracking and prospect_stage_history tables** to deployed schema
---
## The Defining Use Case
A 13D filing is filed on Acme Corp. A cron job picks it up. An agent knows: (a) Acme is two warm-path hops from banker Sam Patel, (b) Sam has prior experience with the specific activist fund, (c) the filing matches Sam's M&A capability profile. Sam gets an alert: "A 13D was filed on Acme Corp by Bridgepoint Capital, disclosing 6.2% stake with activist intent. You have two warm paths: Devon Cole (score 7) is a board advisor to Acme, and Jane Okafor sits on Acme's audit committee. Your capability record shows you advised on the Bridgepoint/Meridian settlement in 2021. Want me to draft an outreach?" Every sentence cited back to a specific record.
---
## The Company This Is Being Built For
**Tidal Partners** — boutique M&A advisory firm, founded by former Centerview bankers. Led Cisco/Splunk ($28bn) and ServiceNow/Armis ($7.8bn). 30+ employees, Palo Alto/New York/Miami. Senior banker archetype: David Handler — rainmaker, doesn't need hand-holding, needs amplification not education.
---
## Key Files
```
app/
  main.py                              # FastAPI app + router wiring
  core/db.py                           # Engine, session, Base classes
  models/global_schema/
    entities.py                        # Company, Person, Affiliation, CompanyRelationship
    observations.py                    # Seven observation tables + KeyDate
  models/tenant/models.py              # Banker, Contact, Capability, ContextNote, Alert
  models/platform/models.py            # Workflow, JobQueue, SourceRegistry, DedupLog
  routers/
    companies.py / people.py           # Prospect universe CRUD
    observations.py                    # Intelligence layer
    contacts.py / capabilities.py      # Banker network
    notes.py / alerts.py               # Context and alerts
    warm_paths.py                      # The killer feature
    ingestion.py                       # Source registry + resolution queue
scripts/
  seed.py                              # Demo data
config/
  models.yaml                          # LLM provider + model routing (TO BE CREATED)
```
