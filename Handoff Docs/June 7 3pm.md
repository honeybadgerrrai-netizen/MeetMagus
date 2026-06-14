# Meet Magus (DealFlow) — Project Handoff Briefing v3

## What It Is
Meet Magus is an AI-powered intelligence and preparation platform for relationship-driven professionals — starting with investment bankers and M&A advisors. The product makes senior dealmakers sharper, better prepared, and more likely to win — without getting in their way. It doesn't build pitch decks or deliverables. It builds the person — their knowledge, their context, their pattern recognition.

**"Deals are won before you walk in."**

The product expands to consultants, staffing firms, and any professional whose value is relationship-based.

**Brand:** Meet Magus | **Domain:** meetmagus.ai | **Landing Page:** Live on Cloudflare Pages

---

## Target Market

### Primary: Mid-Market Advisory Firms (Launch Market)
- 5-15 person shops doing $20-250M deals
- Founder is the rainmaker, analyst, pitch builder, and relationship manager simultaneously
- Deals are inbound through referrals → competitive bakeoff to win the mandate
- Pain: founder has 72 hours to prepare, no team to delegate to, running 5-10 deals at once
- Product IS the team they can't afford to hire
- Thousands of these firms exist — TAM is massive
- Simple buying process: one founder decides, 30-minute demo, credit card
- **Pricing: $400/user/month**

### Secondary: Elite Boutiques (Expansion Market)
- 15-50 person firms like Tidal Partners, Allied Advisors
- Same referral-driven, bakeoff model but with junior team support
- Product amplifies senior banker and accelerates junior team prep
- **Pricing: $500-800/user/month**

### Tertiary: Large Banks and PE Firms (Enterprise)
- 200+ professionals, proactive coverage model
- Enterprise sales cycle, single-tenant deployment, custom compliance
- **Pricing: $200-300/user/month at 500+ seats, $1.5-2M/year contracts**

### Unit Economics
- Gross margin: 82-88% depending on scale
- At 50 users: $20K/month revenue, ~$3K cost, ~85% GM
- At 200 users: $80K/month revenue, ~$15K cost, ~82% GM
- At 1,000 users: $400K/month revenue, ~$50K cost, ~88% GM
- Cost scales sub-linearly — global intelligence layer collected once, served to all tenants

---

## Five-Layer Product Architecture

### Layer 1 — Data Layer (Built)
Three-schema Postgres. External ingestion plus banker-contributed context. Stores everything, thinks nothing.

### Layer 2 — Pattern Engine (Not yet built)
Detects patterns a human would miss. Converts them into signals worth surfacing. Scores every signal against relevance to each specific banker. Event-driven for urgent triggers (13D filings, executive departures). Batch for daily preparation (hiring trends, macro shifts).

### Layer 3 — Interactive Experience Layer (Not yet built)
Delivery and data acquisition fused into one surface. NOT a dashboard. A two-way conversation where consuming intelligence and contributing intelligence are the same activity. The banker never feels like they're "inputting data."

**Two modes, same product:**
- **Proactive mode** (large banks): "Here's what you should be paying attention to today." Signal-forward, daily cadence, monitoring-oriented.
- **Reactive mode** (boutiques, mid-market): "A deal just landed — here's everything you need to know to win it." Briefing-forward, on-demand, preparation-oriented.

Same data. Same pattern engine. Same flywheel. Different trigger, different packaging.

Delivery adapts to context automatically — push notification, written briefing, verbal summary, Q&A deep dive, pre-meeting prep package. Banker never chooses format. System infers from context.

### Layer 4 — Workflow Layer (Not yet built)
Signals become actions. Actions become collaborative. Senior banker says "get Will on this" — system creates workspace, pre-loads context, notifies team.

Senior banker interface: concise, reactive, decision-oriented (briefing surface).
Junior banker interface: analytical, collaborative, production-oriented (workspace).
Same data layer underneath. Different experience on top.

All collaboration native — never email. Every contribution feeds back into Layer 1.

### Layer 5 — Flywheel
Every interaction feeds back into Layer 1. Dismiss = data. Act = data. "Already know him" = relationship data. "Vista told me they're not looking to exit" = proprietary intelligence.

For mid-market advisors, the flywheel is especially critical: the banker IS the primary data source for private companies with no public filings. The system organizes, remembers, and surfaces their own knowledge at the right time.

After 12 months: every relationship, every deal worked, every prospect evaluated, every preference. Not replicable. Not portable. Permanent switching cost.

---

## User/Audience Constraints

- Users are 40-70 years old, senior professionals with deep pride in their judgment
- Will not learn a new interface. Will abandon after one bad experience
- UI must feel like a beautifully prepared briefing — not an app
- No onboarding wizards, no forms, no dropdowns, no required fields, no settings pages
- Interaction patterns that work: confirm/dismiss (binary, fast), voice reply, short text reaction
- Patterns that kill: forms, multi-step workflows, notification badges, feature tours
- The product doesn't build pitch decks or deliverables — it builds the person's knowledge, context, and pattern recognition
- Enterprise deployment: single-tenant in client's cloud, SOC 2 Type II, full audit trail, SSO, configurable data retention, role-based access

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
| **Live URL** | `https://dealflow-production-f0ce.up.railway.app` |
| **API Docs** | `https://dealflow-production-f0ce.up.railway.app/docs` |
| **GitHub** | `honeybadgerrrai-netizen/dealflow` (main branch, auto-deploy on push) |
| **Hosting** | Railway (agile-upliftment project) |
| **Database** | Railway Postgres (connected via DATABASE_URL env var) |
| **Landing Page** | meetmagus.ai on Cloudflare Pages |
| **Email** | jobs@meetmagus.ai via Cloudflare Email Routing → Gmail |

### Seed Data
- 7 companies including Infoblox, Cisco, Arista, Vista Equity, Warburg Pincus
- 2 people: Scott Harrell (Infoblox CEO), Hoke Horne (CFO)
- 3 contacts for banker Sam Patel including warm path to Infoblox CEO
- 3 capabilities (individual + firm level)
- 3 context notes including AI-extracted hiring signal analysis
- 1 pre-built alert: "Vista Equity at Year 9 on Infoblox — Exit Window Now Open"

**To seed:** Get DATABASE_URL from Railway → Postgres → Variables, then:
```bash
cd ~/Downloads/dealflow
DATABASE_URL="postgresql://..." python -m scripts.seed
```

---

## Complete Table Inventory

### Global Schema — Shared Intelligence

**`companies`** — every company (prospects, employers, competitors, PE firms, banks). Name, type, sector, HQ, ticker, revenue, headcount, description, embedding columns. NOTE: no `is_prospect` flag — prospect status is tenant-specific, lives in `prospect_tracking`.

**`people`** — every person. Name, contact info, location, embedding columns. NOTE: no `is_prospect` flag — same reason.

**`affiliations`** — person ↔ company roles. Role type, title, start/end dates, is_current. One person = CEO of A, board of B, GP at C simultaneously.

**`company_relationships`** — bidirectional typed edges between companies. Types: competes_with, sells_to, invested_in, partners_with, acquired, subsidiary_of, joint_venture. Description, observed_at, source, confidence.

**`sectors`** — first-class sector records with parent/child hierarchy.

**`company_aliases`** — entity resolution. Every variant maps to one canonical company. Status: pending/confirmed/rejected.

**`person_aliases`** — same for people.

**`key_dates`** — important dates per company as timestamped observations: earnings, quiet periods, fiscal calendar, debt maturities, lockups, board meetings, banker conferences, regulatory milestones, budget cycle.

**Seven observation tables** — each separate, all sharing the same observation DNA (company_id, observed_at, source_id, confidence, status, superseded_by, embedding, dedup_score, related_observation_id):

**`obs_macro`** — macro trend signals. trend_name, description, relevance_note, impact_direction (tailwind/headwind/neutral), sector_scope.

**`obs_financial`** — financial signals. signal_type (revenue_signal, margin_signal, fundraising, burn_signal, valuation, debt_maturity, revenue_mix), headline, detail, amount_usd, metric_name/value/unit.

**`obs_investor`** — investor/shareholder/activist signals. signal_type (13d_filing, 13g_filing, insider_buy, insider_sell, institutional_change, activist_letter, board_demand, ownership_change), investor_name, investor_company_id, stake_pct, filing_type, is_activist.

**`obs_competitive`** — competitive intelligence. signal_type (product_launch, pricing_change, partnership, acquisition, market_share, win_loss), competitor_company_id, product_overlap_note.

**`obs_customer`** — customer relationship signals. signal_type (new_customer, contract_renewal, churn_signal, expansion, reference), customer_company_id, contract_value_usd.

**`obs_employee`** — employee/hiring signals. signal_type (headcount_snapshot, hiring_surge, layoff, exec_hire, exec_departure, dept_trend, org_change), department, headcount_total/delta, open_roles_count, person_id.

**`obs_public_market`** — public companies only. signal_type (analyst_rating, price_target, consensus_estimate, short_interest, institutional_change, insider_transaction, stock_snapshot), analyst data, ratings, price targets, market metrics.

### Tenant Schema — Per-Customer Private Data

**`bankers`** — the user. tenant_id, name, email, title, employer_company_id.

**`contacts`** — banker's personal network. relationship_score (1-10), relationship_tier (close/warm/acquaintance/cold), willingness_to_help (advocate/intro/reference_only/unknown/no), last_contact_date, notes, linked_person_id (bridge to global.people).

**`capabilities`** — individual and firm-level. scope, category, name, description, sector/geo focus, deal size range, track record count.

**`capability_events`** — publicly observed deals/announcements substantiating capabilities. event_type (closed_deal/league_table/press_release), headline, deal_size_usd, counterparty_company_id.

**`context_notes`** — free-form timestamped notes. source_type (BANKER/AI), tagged_company_ids, tagged_person_ids, is_standing_preference, embedding columns.

**`alerts`** — agent-generated briefings. trigger_type, title, body, cited_sources (JSON), target_company_id, relevance_score, status (unread/read/acted/dismissed), banker_feedback.

**`prospect_tracking`** — full pipeline journey per entity per banker. Replaces is_prospect boolean.
- Stages: no_contact → researching → outreach → intro → engaged → pitching → competing → mandated → executing → closed → dormant → passed → lost
- Fields: banker_id, entity_type (company/person), entity_id, stage, stage_changed_at, owner_banker_id, notes, next_action, next_action_date
- Each stage implies different signals the system should surface
- next_action_date triggers system preparation ("You have a follow-up tomorrow — here's what changed since your last meeting")

**`prospect_stage_history`** — append-only log of every stage transition. from_stage, to_stage, changed_by, reason, changed_at. Full journey preserved.

### Platform Schema — Infrastructure

**`source_registry`** — licensing/compliance rules per source. can_store_raw, can_display_to_user, requires_attribution, retention_days, reliability_rank, dedup_threshold.

**`source_monitors`** — what sources are watched per company. fetch_cadence_minutes, last_fetched_at, consecutive_failures.

**`raw_ingestions`** — raw fetched content before extraction. content_hash, extraction_status, expires_at.

**`workflow_definitions`** — agent workflow templates. trigger_type, steps_json, retry_max.

**`workflow_runs`** — one per execution. definition_id, tenant_id, status, trace_id, is_eval.

**`workflow_steps`** — one per step per run. input/output payloads, retry_count, llm_tokens_used, llm_cost_usd.

**`job_queue`** — all async work. job_type, priority (1=highest), tenant_id, payload, status, attempts.

**`llm_budgets`** — per-tenant daily LLM cost limits.

**`freshness_policies`** — staleness thresholds per observation type.

**`dedup_log`** — rejected duplicate signals with similarity score, threshold, source, rejection level, LLM reasoning.

**`dedup_rules`** — configurable per observation type: match_fields (JSON), numeric_tolerance, time_window_days, semantic_threshold, novelty_check_enabled, action (reject/merge/flag_for_review).

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

Configurable per observation type via `dedup_rules` table.

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

### Why open-source Qwen on US infrastructure
- US banks will never approve data flowing to Alibaba servers
- DeepInfra hosts Qwen on US bare-metal infrastructure, OpenAI-compatible API
- Cheapest per-token for Qwen3-32B: $0.08/$0.28 per million tokens
- Total LLM cost at 2M companies: ~$6/day ($180/month)
- For enterprise single-tenant: switch provider to self_hosted, point at vLLM in client's cloud — one config line change

---

## Cost Estimates at Scale (2M Companies)

### Signal Volume
- Tier 1 (10K active prospects): ~7,000 signals/day
- Tier 2 (75K ecosystem): ~11,000 signals/day
- Tier 3 (1.9M universe, trigger-only): ~1,000 signals/day
- Total raw: ~19,000/day → ~8,000-10,000 net new after dedup

### Monthly Costs
| Category | Monthly cost |
|---|---|
| Data collection (feeds, APIs, providers) | $10,000-15,000 |
| LLM processing (DeepInfra, Qwen mix) | ~$180 |
| Storage (Postgres + vectors) | $50-500 |
| Infrastructure (compute) | $500-2,000 |
| **Total** | **$15,000-20,000/month** |

---

## Architectural Decisions Made

1. Semantic search: pgvector in Postgres, day-one requirement
2. Tenant isolation: Schema-level separation (not RLS, not per-tenant copies)
3. Ingestion pipeline: Three layers — fetch, extract, resolve — independently retriable
4. Observation confidence: Source reliability ranking + recency weighting + conflict flagging
5. Audit trail: Full provenance on observations, resolutions, notes, agent runs
6. Soft deletes: Append-only with status and superseded_by chain
7. Freshness policies: Per observation type, enforced at display and agent level
8. Agent orchestration: workflow_definitions → runs → steps with step-level audit
9. Rate limiting: Job queue with priority, per-tenant LLM budgets
10. Deduplication: Four-level system (hash → structured → embedding → LLM novelty)
11. Model routing: YAML config with provider + model per task, fallback chains
12. Open-source models only: Qwen via US-based inference (DeepInfra). Enterprise: self-hosted vLLM
13. Prospect tracking: Pipeline journey (no_contact → mandated → closed) replaces boolean is_prospect, lives in tenant schema not global
14. Company relationships: Bidirectional edges, not separate competitor/customer tables
15. Product scope: Builds the person's knowledge, not deliverables. No pitch deck generation.

---

## Defining Use Cases

### Use Case 1: The Bakeoff (Primary — Mid-Market and Boutique)
A referral comes in. The founder has 72 hours. The system already knows the company — its financials, competitors, hiring signals, investor situation, buyer universe. The founder says "prepare me for Acme Corp" and gets: company intelligence, competitive landscape, comparable transactions, warm paths, and their own prior experience with similar deals. They walk in as the most prepared person in the room. The knowledge wins the mandate, not a pitch deck.

### Use Case 2: The 13D Alert (Secondary — Proactive Monitoring)
A 13D filing is filed on Acme Corp. A cron job picks it up. An agent knows: (a) Acme is two warm-path hops from the banker, (b) the banker has prior experience with the specific activist fund, (c) the filing matches their M&A capability. The banker gets a cited briefing with warm paths and a suggested next action.

### Use Case 3: Portfolio Monitoring (Future — PE Firms)
A PE firm with 30 portfolio companies tracks each through the same intelligence layer. Hiring signals, competitive moves, customer churn flagged before the CEO's quarterly update. Exit readiness detection using the IPO-readiness hiring pattern (SailPoint/Cerebras template).

---

## The Company Context

Built alongside **Tidal Partners** as the reference customer archetype — boutique M&A advisory, founded by former Centerview bankers. Led Cisco/Splunk ($28bn) and ServiceNow/Armis ($7.8bn). Also informed by conversations with **Allied Advisors** (alliedadvisers.com) — referral-driven, all inbound, competitive bakeoffs.

The senior banker archetype: David Handler — rainmaker, doesn't need hand-holding, needs amplification not education. The product amplifies expertise, it doesn't replace it.

---

## What's Next (Recommended Order)

1. **Run the seed** on Railway Postgres
2. **Build SEC EDGAR fetcher** — 13D/13G filings, 8-K, insider transactions (free API)
3. **Build news fetcher** — headlines via NewsAPI or similar
4. **Build extraction pipeline** — raw content → structured observations via Qwen3-8B on DeepInfra
5. **Build embedding background job** — poll job_queue, generate embeddings
6. **Wire dedup pipeline** — four levels as described
7. **Add semantic search endpoint** — `/search?q=...&banker_id=1`
8. **Build the bakeoff prep endpoint** — "prepare me for company X" → full briefing
9. **Add prospect_tracking and prospect_stage_history tables** to deployed schema
10. **Add auth** — JWT or Clerk
11. **Build the 13D trigger agent**

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

---

## Hiring

**Founding Engineer Intern** — JD posted at jobs@meetmagus.ai. Looking for: architectural instincts, full-stack with backend depth (Python/FastAPI/Postgres), product taste, client presence. Working directly with founder.

---

## Schema Review Fixes (Architect Review — v3.1)

### Changes Made Based on External Architecture Review

---

**1. Source Registry — Already Exists (Rename for Clarity)**
`platform.source_registry` covers this. Columns: source_id, source_type (sec_filing | linkedin | news | web_crawl | manual | third_party_feed), display_name, base_url, reliability_rank, dedup_threshold, can_store_raw, can_display_to_user, requires_attribution, retention_days. No structural change needed — documentation clarified.

---

**2. Tenants Table — Add to Platform Schema**

New table to make multi-tenancy explicit and support billing/admin:

```
platform.tenants
  tenant_id           TEXT PRIMARY KEY  (e.g. "tidal_partners")
  name                TEXT NOT NULL
  tier                TEXT              (boutique | mid_market | enterprise)
  status              TEXT              (active | suspended | offboarded)
  seat_count          INTEGER
  price_per_seat_usd  FLOAT
  created_at          TIMESTAMPTZ
  offboarded_at       TIMESTAMPTZ
```

Tenant schemas are named `tenant_{tenant_id}`. This table is the registry of all provisioned tenant schemas.

---

**3. Split obs_employee into Two Tables**

obs_employee conflated point-in-time metrics (time-series queries) with discrete events (recency queries). Split into:

**`obs_headcount`** — point-in-time snapshots, supports time-series analysis (growth rate over 90 days, department trends):
```
obs_headcount (global schema)
  [standard obs DNA columns]
  department              TEXT          (total | engineering | sales | finance | legal | ops | product)
  headcount_total         INTEGER
  headcount_delta         INTEGER       (vs prior snapshot)
  open_roles_count        INTEGER
  source_detail           TEXT          (linkedin_estimate | company_filing | job_board_inference)
```

**`obs_org_events`** — discrete events, supports recency queries (most recent exec departures, recent layoffs):
```
obs_org_events (global schema)
  [standard obs DNA columns]
  event_type              TEXT          (exec_hire | exec_departure | layoff | reorg | new_division | title_change)
  headline                TEXT NOT NULL
  detail                  TEXT
  person_id               INTEGER       FK global.people — for exec events
  department_affected     TEXT
  headcount_impact        INTEGER       — for layoffs
  seniority_level         TEXT          (c_suite | vp | director | manager)
```

---

**4. company_relationships — Directionality Convention**

Renamed columns with explicit subject/object convention. company_a is ALWAYS the subject:

```
company_relationships
  source_company_id → renamed: company_a_id    (the subject: A acquired B, A invested in B)
  target_company_id → renamed: company_b_id    (the object)
  relationship_type                             (see below)
  is_symmetric        BOOLEAN                  (true for competes_with, partners_with; false for acquired, invested_in, subsidiary_of)
```

Relationship types and directionality:
| Type | Symmetric | Convention |
|---|---|---|
| competes_with | YES | Insert once, query both directions |
| partners_with | YES | Insert once, query both directions |
| sells_to | NO | A sells to B |
| buys_from | NO | A buys from B |
| invested_in | NO | A invested in B |
| acquired | NO | A acquired B |
| subsidiary_of | NO | A is subsidiary of B |
| joint_venture | YES | Insert once |

For symmetric relationships: only one row inserted, queries use `WHERE company_a_id = X OR company_b_id = X`. For non-symmetric: direction matters, only one canonical direction stored.

---

**5. Signal Lifecycle — Explicit Status Enum**

All obs tables now use a defined status enum (enforced at application layer):

```
unverified      — ingested but not yet validated against a second source
verified        — confirmed by at least one additional source or high-reliability source
superseded      — replaced by newer/better data (the record itself was correct, just outdated)
retracted       — found to be incorrect (different from superseded — this was wrong)
pending_review  — flagged for human review (e.g. conflict between sources)
```

`superseded_by` INTEGER — points to the newer observation that replaced this one (for superseded records).
`retracted_reason` TEXT — why the signal was retracted (for retracted records).

---

**6. Macro Trend → Company Links Table**

Restoring the `macro_company_links` junction table that was designed but lost between iterations:

```
global.macro_company_links
  id
  obs_macro_id        INTEGER     FK global.obs_macro.id
  company_id          INTEGER     FK global.companies.id
  relevance_note      TEXT        — why this macro trend is relevant to this specific company
  impact_direction    TEXT        (tailwind | headwind | neutral | mixed)
  impact_magnitude    TEXT        (high | medium | low)
  created_at          TIMESTAMPTZ
  created_by          TEXT        (BANKER | AI | system)
```

This lets the same macro observation (e.g. "Rising interest rates compressing SaaS multiples") link to multiple companies with company-specific impact annotations. A rising rate environment is a headwind for Infoblox (valuation compression) but different for a cash-rich strategic acquirer.

---

**7. Embedding Input Specification**

Defining exactly what text is embedded per table — critical for vector search quality consistency:

| Table | Embedding Input |
|---|---|
| `companies` | `name + " " + description + " " + industry` |
| `people` | `first_name + " " + last_name + " " + current_title + " " + employer_name` |
| `obs_macro` | `trend_name + ": " + trend_description + ". Relevance: " + relevance_note` |
| `obs_financial` | `headline + ". " + detail` |
| `obs_investor` | `headline + ". Investor: " + investor_name + ". " + detail` |
| `obs_competitive` | `headline + ". " + detail + ". Product overlap: " + product_overlap_note` |
| `obs_customer` | `headline + ". " + detail` |
| `obs_headcount` | `"Headcount signal for " + department + ": " + headline + ". " + detail` |
| `obs_org_events` | `event_type + ": " + headline + ". " + detail` |
| `obs_public_market` | `headline + ". Analyst: " + analyst_firm + ". " + detail` |
| `context_notes` | `content` (full text of the note) |
| `alerts` | `title + ". " + body` |

Embedding input is constructed at write time in the application layer before the embedding API call. Stored in `embedding_input_hash` (SHA256 of the input text) so re-embedding can be skipped if the input hasn't changed.

New column on all embeddable tables:
```
embedding_input_hash    TEXT    — SHA256 of the text that was embedded. Detect staleness after model upgrades.
```

---

**8. Alias Resolution Audit Trail**

Adding audit columns to `company_aliases` and `person_aliases`:

```
resolved_by         TEXT        — identity of who/what resolved (e.g. "user:david_handler" | "ml_model:qwen3-32b" | "rule:ticker_match")
resolved_at         TIMESTAMPTZ
resolution_method   TEXT        (human | ml_model | rule_based)
resolution_notes    TEXT        — optional context on why this merge was confirmed or rejected
```

---

**9. signal_feed — New Append-Only Cross-Signal Query Table**

The most important structural addition from the review. The "show me everything at this company in the last 30 days" query is a core product query. Hitting seven obs tables with UNION ALL is unacceptable at scale.

Solution: an append-only `signal_feed` table written synchronously whenever any observation is written to any obs table. Same transaction — if the obs write fails, the signal_feed write fails. If signal_feed write fails, roll back both.

```
global.signal_feed
  id                  BIGSERIAL PRIMARY KEY
  company_id          INTEGER NOT NULL        index
  obs_type            TEXT NOT NULL           (macro | financial | investor | competitive | customer | headcount | org_event | public_market)
  obs_id              INTEGER NOT NULL        — FK to the source obs table record
  signal_type         TEXT                    — denormalized from source record
  headline            TEXT NOT NULL           — denormalized for fast display without joining back
  observed_at         TIMESTAMPTZ NOT NULL    index
  source_id           TEXT                    — denormalized
  confidence          FLOAT
  status              TEXT                    index
  created_at          TIMESTAMPTZ             index
```

**Query patterns this enables:**

```sql
-- Everything at Infoblox in the last 30 days, ordered by recency
SELECT * FROM global.signal_feed
WHERE company_id = 2
AND observed_at > NOW() - INTERVAL '30 days'
AND status = 'verified'
ORDER BY observed_at DESC;

-- All investor signals across all prospect companies for banker 1
SELECT sf.* FROM global.signal_feed sf
JOIN tenant_tidal.prospect_tracking pt ON sf.company_id = pt.entity_id
WHERE sf.obs_type = 'investor'
AND pt.banker_id = 1
AND pt.stage NOT IN ('passed', 'lost')
ORDER BY sf.observed_at DESC;
```

For detail on any row: join back to the source table using `obs_type` + `obs_id`. signal_feed never holds full detail — just enough to answer "what happened recently" efficiently.

---

### Summary of Schema Changes

| Change | Impact | Priority |
|---|---|---|
| Add `platform.tenants` table | Explicit multi-tenancy registry | Medium |
| Split `obs_employee` → `obs_headcount` + `obs_org_events` | Cleaner query patterns | High |
| Enforce directionality on `company_relationships` | Prevent duplicate/wrong-direction edges | High |
| Define signal status enum (unverified/verified/superseded/retracted) | Consistent lifecycle management | High |
| Restore `macro_company_links` junction table | Company-specific macro impact tracking | Medium |
| Define embedding input per table | Vector search quality consistency | High |
| Add `embedding_input_hash` column to all embeddable tables | Detect stale embeddings after model upgrade | Medium |
| Add audit columns to alias tables | Resolution provenance | Medium |
| Add `signal_feed` append-only table | Core product query performance | High |

---

## Strategic Intelligence Layer — Layer 1 and Layer 2 Updates

### Layer 1 Addition — strategic_developments Table

New first-class object in global schema. Written by the Pattern Engine (Layer 2). Read by the Experience Layer (Layer 3). Persists synthesized strategic conclusions with cited evidence, versioning, and status tracking.

```sql
global.strategic_developments
  id                    BIGSERIAL PRIMARY KEY
  company_id            INTEGER NOT NULL          -- FK global.companies.id, index
  title                 TEXT NOT NULL             -- "Management shifting from growth to profitability"
  narrative             TEXT NOT NULL             -- 2-3 paragraph synthesis with evidence
  development_type      TEXT NOT NULL             -- strategy_shift | competitive_threat |
                                                  -- exit_preparation | leadership_change |
                                                  -- market_expansion | financial_inflection |
                                                  -- ownership_change | product_pivot
  supporting_obs_ids    JSONB                     -- array of {obs_type, obs_id} pairs
  supporting_signal_ids JSONB                     -- array of signal_feed ids
  confidence            FLOAT                     -- 0-1, how strong is the evidence
  first_detected_at     TIMESTAMPTZ               -- when pattern first emerged
  last_updated_at       TIMESTAMPTZ               -- when narrative last refreshed
  status                TEXT                      -- emerging | established | resolved | reversed
  generated_by          TEXT                      -- ai | human | both
  reviewed_by           TEXT                      -- who validated it
  reviewed_at           TIMESTAMPTZ
  embedding_json        TEXT                      -- for semantic search
  embedding_model       TEXT
  embedding_input_hash  TEXT
  created_at            TIMESTAMPTZ DEFAULT NOW()
```

Also: `strategic_developments` added as a valid obs_type in `signal_feed` so it surfaces alongside raw observations in the cross-signal query.

---

### Layer 2 Update — Pattern Engine

The Pattern Engine now has two explicit outputs:

**Output A — Signals (existing)**
Individual pattern detections written to signal_feed, triggering alerts per banker based on relevance scoring. Event-driven for urgent types (investor/activist), batch for everything else.

**Output B — Strategic Developments (new)**
Synthesized conclusions drawn from clusters of signals over time. Written to strategic_developments. Not triggered by a single event — they emerge from accumulated evidence across multiple observation types over days and weeks.

**Two distinct processes:**

**Process 1 — Signal Detection (existing)**
- Trigger: new observation written
- Action: score relevance per banker, fan out alerts, write to signal_feed
- Latency: near real-time for urgent types, batch for others
- Model: pattern_detection task → Qwen/Qwen3-32B

**Process 2 — Narrative Synthesis (new)**
- Trigger: nightly batch per Tier 1 and Tier 2 company
- Model: agent_reasoning task → Qwen/Qwen3-235B-A22B (most complex reasoning task in the system)
- Steps:
  1. Pull all active observations for the company across all obs tables from the last 90 days
  2. Pull existing strategic_developments for the company
  3. Reason across six analytical domains: Business, Financial, People, Events, Relationships, Signals
  4. Determine: update existing development? Create new one? Mark one resolved or reversed?
  5. Write or update strategic_developments record with narrative, cited obs_ids, confidence, status
  6. Write to signal_feed if new or materially updated development

The six-domain framework (Business, Financial, People, Events, Relationships, Signals) structures the LLM reasoning prompt — organizing evidence the way an advisor thinks, not the way the database is organized.

**What strategic_developments look like in practice:**
- "Infoblox is preparing for an exit — Vista at year 9, revenue accounting hire, sales acceleration without IPO infrastructure"
- "Microsoft is making a serious push into DDI — three product announcements and 200 engineering hires in the last 6 months"
- "Kestrel Aerospace leadership is in transition — CFO departure signals board-level pressure"

These are the conclusions a banker gets paid to identify. The Pattern Engine surfaces them automatically from the evidence, before the banker has to ask.
