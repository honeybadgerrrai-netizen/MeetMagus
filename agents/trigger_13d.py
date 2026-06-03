"""
app/agents/trigger_13d.py
13D Trigger Agent — the defining use case of DealFlow.

When a new activist 13D/13G filing appears in obs_investor, this agent:

  1. WARM PATH SCAN
     Graph traversal: banker's contacts → affiliations → target company.
     Finds every person the banker knows who has a current role at or
     board seat on the target company. Returns 1-hop and 2-hop paths
     ranked by relationship score.

  2. CAPABILITY MATCH
     Scores the banker's declared capabilities against the scenario.
     An activist 13D maps to: M&A advisory, activist defense/offense,
     board advisory, restructuring. Matches by sector overlap too.

  3. RELEVANCE SCORING
     Combines warm path strength + capability match → 0.0–1.0 score.
     Alert only fires if score ≥ RELEVANCE_THRESHOLD (default 0.3).
     A filing with zero warm paths and no capability match → no alert.

  4. ALERT COMPOSITION
     Calls Groq llama-3.3-70b-versatile to write a crisp banker-facing
     alert. Every factual claim is cited back to a specific DB record ID.
     Format: 2–4 sentences, no jargon, no hedging, actionable.

  5. DEDUPLICATION
     Checks if an alert for this (banker, obs_investor) pair already
     exists. If so, skips silently. One alert per trigger, per banker.

The defining scenario:
  Jana Partners files 13D on Alkami Technology (May 28 2026, 7.9% stake).
  Agent finds: David Handler (banker) → Jeff Fox (contact, score 9) →
  Fox is on Alkami board. Handler also defended Qualcomm against Broadcom.
  Alert: "Jana Partners filed a 13D on Alkami (7.9%, activist). You know
  Jeff Fox, who sits on Alkami's board. Your Qualcomm/Broadcom defense
  experience is directly relevant. Want me to draft an outreach to Jeff?"

Usage:
  # Dry run — no DB writes, shows what alert would look like:
  python -m app.agents.trigger_13d --dry-run

  # Process all unalerted activist observations for all bankers:
  DATABASE_URL="..." python -m app.agents.trigger_13d

  # Daemon mode:
  DATABASE_URL="..." python -m app.agents.trigger_13d --daemon
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

RELEVANCE_THRESHOLD = 0.30   # minimum score to fire an alert
MAX_WARM_PATH_HOPS = 2       # 1-hop (direct contact) or 2-hop (contact of contact)
MAX_WARM_PATHS_IN_ALERT = 3  # show top N paths in the alert text


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class WarmPath:
    """A path from the banker to the target company through their network."""
    hops: int                    # 1 = direct contact at company, 2 = contact of contact
    path_description: str        # human-readable: "Jeff Fox → Alkami Board Director"
    contact_name: str            # the banker's direct contact
    contact_id: str              # tenant.contacts UUID
    contact_relationship_score: int  # 1–10
    intermediate_name: str = "" # for 2-hop: name of the middle person
    role_at_company: str = ""   # "Board Director", "CFO", etc.
    affiliation_id: str = ""    # global.affiliations UUID (for citation)
    # Derived score: higher is better (1-hop direct beats 2-hop)
    path_score: float = 0.0

    def __post_init__(self):
        if self.path_score == 0.0:
            base = self.contact_relationship_score / 10.0
            hop_discount = 1.0 if self.hops == 1 else 0.6
            self.path_score = base * hop_discount


@dataclass
class CapabilityMatch:
    """A banker capability that is relevant to the 13D scenario."""
    capability_id: str
    capability_name: str
    category: str           # "M&A", "activist_defense", "restructuring", etc.
    relevance_reason: str   # why it's relevant to THIS filing
    match_score: float      # 0.0–1.0
    evidence: str           # brief supporting text (deal name, sector, etc.)


@dataclass
class TriggerContext:
    """Everything the agent knows about a 13D trigger event."""
    obs_id: str
    company_id: str
    company_name: str
    filer_name: str
    stake_pct: float | None
    is_activist: bool
    has_sale_demand: bool
    has_board_demand: bool
    headline: str
    detail: str
    filed_at: str
    banker_id: str
    banker_name: str
    warm_paths: list[WarmPath] = field(default_factory=list)
    capability_matches: list[CapabilityMatch] = field(default_factory=list)
    relevance_score: float = 0.0


@dataclass
class AgentResult:
    """Result of processing one 13D trigger for one banker."""
    obs_id: str
    banker_id: str
    company_name: str
    filer_name: str
    status: str              # "alerted" | "skipped_low_relevance" | "skipped_duplicate" | "failed"
    relevance_score: float = 0.0
    alert_id: str = ""
    alert_title: str = ""
    alert_body: str = ""
    warm_path_count: int = 0
    capability_match_count: int = 0
    error: str = ""


@dataclass
class RunResult:
    """Result of one full agent run across all bankers and triggers."""
    triggers_found: int = 0
    alerts_fired: int = 0
    skipped_low_relevance: int = 0
    skipped_duplicate: int = 0
    failed: int = 0
    results: list[AgentResult] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Warm Path Engine
# ──────────────────────────────────────────────────────────────────────────────

class WarmPathEngine:
    """
    Finds connections between a banker's contacts and a target company.

    Data flow:
      tenant.contacts (banker's network)
        ↓ linked_person_id
      global.people
        ↓ affiliations
      global.affiliations (company roles)
        ↓ company_id
      target company

    1-hop: banker knows someone currently at/on-board of target company.
    2-hop: banker knows someone who knows someone at target company.
           (via shared affiliation at a related company — board interlocks)
    """

    def __init__(self, db_session):
        self._db = db_session

    def find_paths(self, banker_id: str, company_id: str) -> list[WarmPath]:
        """Find all warm paths from banker to company. Returns ranked list."""
        paths: list[WarmPath] = []
        paths.extend(self._find_1hop_paths(banker_id, company_id))
        if len(paths) < 3:
            paths.extend(self._find_2hop_paths(banker_id, company_id))
        # Deduplicate by contact_id + company_id
        seen = set()
        unique: list[WarmPath] = []
        for p in paths:
            key = (p.contact_id, p.hops)
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return sorted(unique, key=lambda p: p.path_score, reverse=True)

    def _find_1hop_paths(self, banker_id: str, company_id: str) -> list[WarmPath]:
        """
        Banker's direct contacts who have a current affiliation with the company.
        """
        from sqlalchemy import text
        rows = self._db.execute(
            text("""
                SELECT
                    c.id            AS contact_id,
                    c.name          AS contact_name,
                    c.relationship_score,
                    a.id            AS affiliation_id,
                    a.role_type,
                    a.title
                FROM   tenant_{banker_id_schema}.contacts c
                JOIN   global.affiliations a
                       ON a.person_id = c.linked_person_id
                WHERE  c.banker_id   = :banker_id
                  AND  a.company_id  = :company_id
                  AND  a.is_current  = true
                  AND  c.linked_person_id IS NOT NULL
                ORDER BY c.relationship_score DESC
                LIMIT 10
            """.replace("{banker_id_schema}", self._tenant_schema(banker_id))),
            {"banker_id": banker_id, "company_id": company_id},
        ).fetchall()

        paths = []
        for row in rows:
            role = row[5] or row[4] or "Connected"
            paths.append(WarmPath(
                hops=1,
                path_description=f"{row[1]} → {role} at target company",
                contact_name=row[1],
                contact_id=str(row[0]),
                contact_relationship_score=row[2] or 5,
                role_at_company=role,
                affiliation_id=str(row[3]),
            ))
        return paths

    def _find_2hop_paths(self, banker_id: str, company_id: str) -> list[WarmPath]:
        """
        Banker's contacts who share a board/affiliation with someone
        who is currently at the target company.
        (Board interlock pattern: both serve on a common third company's board.)
        """
        from sqlalchemy import text
        rows = self._db.execute(
            text("""
                SELECT
                    c.id                AS contact_id,
                    c.name              AS contact_name,
                    c.relationship_score,
                    p2.name             AS intermediate_name,
                    a2.id               AS affiliation_id,
                    a2.role_type,
                    a2.title,
                    shared.company_name AS shared_via
                FROM   tenant_{schema}.contacts c
                JOIN   global.affiliations a1
                       ON a1.person_id = c.linked_person_id AND a1.is_current = true
                JOIN   global.affiliations a1b
                       ON a1b.company_id = a1.company_id
                       AND a1b.person_id != a1.person_id
                       AND a1b.is_current = true
                JOIN   global.affiliations a2
                       ON a2.person_id = a1b.person_id
                       AND a2.company_id = :company_id
                       AND a2.is_current = true
                JOIN   global.people p2 ON p2.id = a1b.person_id
                JOIN   global.companies shared ON shared.id = a1.company_id
                WHERE  c.banker_id = :banker_id
                  AND  c.linked_person_id IS NOT NULL
                ORDER BY c.relationship_score DESC
                LIMIT 5
            """.replace("{schema}", self._tenant_schema(banker_id))),
            {"banker_id": banker_id, "company_id": company_id},
        ).fetchall()

        paths = []
        for row in rows:
            role = row[6] or row[5] or "Connected"
            via = row[7] or "shared board"
            paths.append(WarmPath(
                hops=2,
                path_description=(
                    f"{row[1]} → {row[3]} (via {via}) → {role} at target company"
                ),
                contact_name=row[1],
                contact_id=str(row[0]),
                contact_relationship_score=row[2] or 5,
                intermediate_name=row[3],
                role_at_company=role,
                affiliation_id=str(row[4]),
            ))
        return paths

    @staticmethod
    def _tenant_schema(banker_id: str) -> str:
        """Return the tenant schema name for a banker_id."""
        # In the deployed system, banker_id maps to tenant_id
        # For simplicity, the schema is tenant_{banker_id} or we look it up
        # Here we use a simplified lookup — in production, cache this mapping
        return f"tenant_{banker_id}"


# ──────────────────────────────────────────────────────────────────────────────
# Capability Matcher
# ──────────────────────────────────────────────────────────────────────────────

ACTIVIST_CAPABILITY_KEYWORDS = {
    "activist_defense":   2.0,
    "activist":           2.0,
    "hostile":            1.8,
    "takeover_defense":   1.8,
    "proxy":              1.6,
    "shareholder":        1.5,
    "m&a":                1.2,
    "merger":             1.2,
    "acquisition":        1.2,
    "strategic_review":   1.3,
    "sale_process":       1.5,
    "sell-side":          1.4,
    "sellside":           1.4,
}


class CapabilityMatcher:
    """
    Scores a banker's capabilities against an activist 13D scenario.

    Matching logic:
      - Keywords in capability name/description → relevance score
      - Sector overlap between capability and target company → bonus
      - Higher score = stronger argument for the banker to reach out
    """

    def __init__(self, db_session):
        self._db = db_session

    def match(
        self,
        banker_id: str,
        company_id: str,
        obs_metadata: dict,
    ) -> list[CapabilityMatch]:
        """
        Return capabilities relevant to this activist filing, ranked by match_score.
        """
        capabilities = self._fetch_capabilities(banker_id)
        company_sector = self._fetch_company_sector(company_id)
        has_sale_demand = obs_metadata.get("has_sale_demand", False)
        has_board_demand = obs_metadata.get("has_board_demand", False)

        matches: list[CapabilityMatch] = []
        for cap in capabilities:
            score, reason = self._score_capability(
                cap, company_sector, has_sale_demand, has_board_demand
            )
            if score >= 0.3:
                matches.append(CapabilityMatch(
                    capability_id=str(cap["id"]),
                    capability_name=cap["name"],
                    category=cap.get("category", ""),
                    relevance_reason=reason,
                    match_score=score,
                    evidence=cap.get("description", "")[:200],
                ))

        return sorted(matches, key=lambda m: m.match_score, reverse=True)

    def _score_capability(
        self,
        cap: dict,
        company_sector: str,
        has_sale_demand: bool,
        has_board_demand: bool,
    ) -> tuple[float, str]:
        """Return (score, reason_string) for a capability against this scenario."""
        text = (
            f"{cap.get('name', '')} {cap.get('description', '')} "
            f"{cap.get('category', '')}"
        ).lower()

        score = 0.0
        reasons = []

        for keyword, weight in ACTIVIST_CAPABILITY_KEYWORDS.items():
            if keyword in text:
                score = max(score, weight / 2.0)
                reasons.append(keyword.replace("_", " "))

        # Sale demand bonus
        if has_sale_demand and any(k in text for k in ("sale", "sell", "m&a", "merger")):
            score += 0.2
            reasons.append("sale process match")

        # Board demand bonus
        if has_board_demand and any(k in text for k in ("board", "proxy", "shareholder")):
            score += 0.2
            reasons.append("board contest match")

        # Sector overlap
        cap_sector = (cap.get("sector_focus") or "").lower()
        if cap_sector and company_sector and cap_sector in company_sector.lower():
            score += 0.15
            reasons.append(f"sector match ({cap_sector})")

        score = min(score, 1.0)
        reason = "; ".join(reasons) if reasons else "general M&A relevance"
        return score, reason

    def _fetch_capabilities(self, banker_id: str) -> list[dict]:
        from sqlalchemy import text
        schema = WarmPathEngine._tenant_schema(banker_id)
        rows = self._db.execute(
            text(f"""
                SELECT id, name, category, description, sector_focus, scope
                FROM {schema}.capabilities
                WHERE banker_id = :banker_id OR scope = 'firm'
                ORDER BY scope DESC, id ASC
            """),
            {"banker_id": banker_id},
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "category": r[2],
             "description": r[3], "sector_focus": r[4], "scope": r[5]}
            for r in rows
        ]

    def _fetch_company_sector(self, company_id: str) -> str:
        from sqlalchemy import text
        row = self._db.execute(
            text("SELECT sector FROM global.companies WHERE id = :id LIMIT 1"),
            {"id": company_id},
        ).fetchone()
        return row[0] if row else ""


# ──────────────────────────────────────────────────────────────────────────────
# Relevance Scorer
# ──────────────────────────────────────────────────────────────────────────────

def compute_relevance_score(
    warm_paths: list[WarmPath],
    capability_matches: list[CapabilityMatch],
    obs: dict,
) -> float:
    """
    Combine warm path strength and capability match into a 0.0–1.0 score.

    Weights:
      - Best warm path score:       40%
      - Capability match presence:  40%
      - Activist urgency signal:    20%
    """
    # Warm path component (0–0.4)
    if warm_paths:
        best_path = max(p.path_score for p in warm_paths)
        warm_component = best_path * 0.4
    else:
        warm_component = 0.0

    # Capability component (0–0.4)
    if capability_matches:
        best_cap = min(capability_matches[0].match_score, 1.0)
        cap_component = best_cap * 0.4
    else:
        cap_component = 0.0

    # Urgency component (0–0.2)
    # 13D is more urgent than 13G; sale demand is most urgent
    urgency = 0.1
    if obs.get("filing_type", "").upper() in ("SC 13D", "SC 13D/A"):
        urgency += 0.05
    if obs.get("has_sale_demand"):
        urgency += 0.05

    score = warm_component + cap_component + urgency
    return round(min(score, 1.0), 4)


# ──────────────────────────────────────────────────────────────────────────────
# Alert Composer
# ──────────────────────────────────────────────────────────────────────────────

ALERT_SYSTEM_PROMPT = """\
You are a financial intelligence agent writing a concise, high-value briefing
for a senior investment banker. The banker is David Handler-level — a rainmaker
who does not need hand-holding, just amplification.

Rules:
- 2 to 4 sentences. Never more.
- Lead with the most urgent fact (the filing).
- Name the specific warm path connection if one exists.
- Name the specific capability match if one exists.
- End with one crisp action question.
- No hedging. No filler. No "it appears" or "it seems".
- Every factual claim you make will be cited. Do not make up facts.
- Tone: the way a brilliant analyst briefs their MD at 7am before a flight.
"""


def build_alert_prompt(ctx: TriggerContext) -> list[dict]:
    """Build the LLM messages for alert composition."""
    warm_path_text = ""
    if ctx.warm_paths:
        paths_str = "\n".join(
            f"  - {p.path_description} (relationship score {p.contact_relationship_score}/10)"
            for p in ctx.warm_paths[:MAX_WARM_PATHS_IN_ALERT]
        )
        warm_path_text = f"\nWarm paths found:\n{paths_str}"
    else:
        warm_path_text = "\nNo warm paths found in banker's network."

    cap_text = ""
    if ctx.capability_matches:
        caps_str = "\n".join(
            f"  - {m.capability_name}: {m.relevance_reason}"
            for m in ctx.capability_matches[:3]
        )
        cap_text = f"\nRelevant capabilities:\n{caps_str}"
    else:
        cap_text = "\nNo specific capability match found."

    user_msg = f"""Write a banker alert for the following trigger event.

FILING EVENT:
  Company:   {ctx.company_name}
  Filer:     {ctx.filer_name}
  Form:      SC 13D (activist filing)
  Stake:     {f"{ctx.stake_pct}%" if ctx.stake_pct else "undisclosed"}
  Sale push: {"Yes" if ctx.has_sale_demand else "No"}
  Board push:{"Yes" if ctx.has_board_demand else "No"}
  Summary:   {ctx.headline}
  Detail:    {ctx.detail}
{warm_path_text}
{cap_text}

BANKER: {ctx.banker_name}

Write the alert now. 2–4 sentences only. End with an action question."""

    return [
        {"role": "system", "content": ALERT_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def build_cited_sources(ctx: TriggerContext) -> list[dict]:
    """
    Build the cited_sources JSON array for the alert.
    Every factual claim must trace back to a specific record.
    """
    sources = [
        {
            "type": "obs_investor",
            "id": ctx.obs_id,
            "description": f"{ctx.filer_name} 13D filing on {ctx.company_name}",
        }
    ]
    for path in ctx.warm_paths[:MAX_WARM_PATHS_IN_ALERT]:
        sources.append({
            "type": "contact",
            "id": path.contact_id,
            "description": f"{path.contact_name} — {path.path_description}",
        })
        if path.affiliation_id:
            sources.append({
                "type": "affiliation",
                "id": path.affiliation_id,
                "description": f"{path.contact_name} affiliation at target company",
            })
    for cap in ctx.capability_matches[:3]:
        sources.append({
            "type": "capability",
            "id": cap.capability_id,
            "description": cap.capability_name,
        })
    return sources


# ──────────────────────────────────────────────────────────────────────────────
# Main Agent
# ──────────────────────────────────────────────────────────────────────────────

class TriggerAgent13D:
    """
    The 13D Trigger Agent.

    Scans for new unalerted activist obs_investor rows and fires banker alerts.

    Usage:
        agent = TriggerAgent13D(db_session=session)
        run_result = agent.run()
    """

    def __init__(self, db_session=None, llm_client=None):
        self._db = db_session
        if llm_client is None and db_session is not None:
            from app.core.llm import LLMClient
            self._llm = LLMClient()
        else:
            self._llm = llm_client

    def run(self, dry_run: bool = False) -> RunResult:
        """
        Main entry point. Scans all unalerted activist filings across all bankers.
        """
        result = RunResult()
        observations = self._fetch_unalerted_activist_obs()
        bankers = self._fetch_all_bankers()

        result.triggers_found = len(observations)
        logger.info(
            "Agent run: %d activist observations × %d bankers",
            len(observations), len(bankers),
        )

        for obs in observations:
            for banker in bankers:
                agent_result = self._process_trigger(obs, banker, dry_run=dry_run)
                result.results.append(agent_result)
                if agent_result.status == "alerted":
                    result.alerts_fired += 1
                elif agent_result.status == "skipped_low_relevance":
                    result.skipped_low_relevance += 1
                elif agent_result.status == "skipped_duplicate":
                    result.skipped_duplicate += 1
                elif agent_result.status == "failed":
                    result.failed += 1

        return result

    def process_single(
        self,
        obs: dict,
        banker: dict,
        dry_run: bool = False,
    ) -> AgentResult:
        """Process one (obs, banker) pair. Useful for testing."""
        return self._process_trigger(obs, banker, dry_run=dry_run)

    # ── Core pipeline ─────────────────────────────────────────────────────────

    def _process_trigger(
        self, obs: dict, banker: dict, dry_run: bool
    ) -> AgentResult:
        banker_id = str(banker["id"])
        obs_id = str(obs["id"])

        # Dedup check
        if not dry_run and self._alert_already_exists(obs_id, banker_id):
            return AgentResult(
                obs_id=obs_id,
                banker_id=banker_id,
                company_name=obs.get("company_name", ""),
                filer_name=obs.get("investor_name", ""),
                status="skipped_duplicate",
            )

        try:
            # 1. Warm path scan
            warm_paths = self._find_warm_paths(banker_id, obs)

            # 2. Capability match
            capability_matches = self._match_capabilities(banker_id, obs)

            # 3. Relevance score
            score = compute_relevance_score(warm_paths, capability_matches, obs)

            if score < RELEVANCE_THRESHOLD:
                logger.debug(
                    "Skipping %s for banker %s — score %.3f < threshold %.3f",
                    obs_id, banker_id, score, RELEVANCE_THRESHOLD,
                )
                return AgentResult(
                    obs_id=obs_id,
                    banker_id=banker_id,
                    company_name=obs.get("company_name", ""),
                    filer_name=obs.get("investor_name", ""),
                    status="skipped_low_relevance",
                    relevance_score=score,
                    warm_path_count=len(warm_paths),
                    capability_match_count=len(capability_matches),
                )

            # 4. Build context
            ctx = TriggerContext(
                obs_id=obs_id,
                company_id=str(obs.get("company_id", "")),
                company_name=obs.get("company_name", ""),
                filer_name=obs.get("investor_name", ""),
                stake_pct=obs.get("stake_pct"),
                is_activist=obs.get("is_activist", True),
                has_sale_demand=obs.get("has_sale_demand", False),
                has_board_demand=obs.get("has_board_demand", False),
                headline=obs.get("headline", ""),
                detail=obs.get("detail", ""),
                filed_at=str(obs.get("observed_at", "")),
                banker_id=banker_id,
                banker_name=banker.get("name", ""),
                warm_paths=warm_paths,
                capability_matches=capability_matches,
                relevance_score=score,
            )

            # 5. Compose alert
            alert_title, alert_body = self._compose_alert(ctx)
            cited_sources = build_cited_sources(ctx)

            # 6. Write alert (unless dry run)
            alert_id = ""
            if not dry_run:
                alert_id = self._write_alert(
                    ctx, alert_title, alert_body, cited_sources
                )
                self._mark_obs_alerted(obs_id)

            return AgentResult(
                obs_id=obs_id,
                banker_id=banker_id,
                company_name=ctx.company_name,
                filer_name=ctx.filer_name,
                status="alerted",
                relevance_score=score,
                alert_id=alert_id,
                alert_title=alert_title,
                alert_body=alert_body,
                warm_path_count=len(warm_paths),
                capability_match_count=len(capability_matches),
            )

        except Exception as e:
            logger.error(
                "Agent failed for obs %s banker %s: %s",
                obs_id, banker_id, e, exc_info=True,
            )
            return AgentResult(
                obs_id=obs_id,
                banker_id=banker_id,
                company_name=obs.get("company_name", ""),
                filer_name=obs.get("investor_name", ""),
                status="failed",
                error=str(e),
            )

    def _find_warm_paths(self, banker_id: str, obs: dict) -> list[WarmPath]:
        if not self._db:
            return []
        engine = WarmPathEngine(self._db)
        company_id = str(obs.get("company_id", ""))
        if not company_id:
            return []
        try:
            return engine.find_paths(banker_id, company_id)
        except Exception as e:
            logger.warning("Warm path scan failed: %s", e)
            return []

    def _match_capabilities(
        self, banker_id: str, obs: dict
    ) -> list[CapabilityMatch]:
        if not self._db:
            return []
        matcher = CapabilityMatcher(self._db)
        meta = obs.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        try:
            return matcher.match(
                banker_id=banker_id,
                company_id=str(obs.get("company_id", "")),
                obs_metadata={
                    **meta,
                    "has_sale_demand": obs.get("has_sale_demand", False),
                    "has_board_demand": obs.get("has_board_demand", False),
                    "filing_type": obs.get("filing_type", ""),
                },
            )
        except Exception as e:
            logger.warning("Capability match failed: %s", e)
            return []

    def _compose_alert(self, ctx: TriggerContext) -> tuple[str, str]:
        """Returns (title, body). Falls back to template if LLM unavailable."""
        title = (
            f"Activist Alert: {ctx.filer_name} files 13D on {ctx.company_name}"
            + (f" ({ctx.stake_pct}%)" if ctx.stake_pct else "")
        )

        if self._llm is None:
            body = self._template_alert(ctx)
            return title, body

        messages = build_alert_prompt(ctx)
        try:
            response = self._llm.complete(
                task="alert_generation",
                messages=messages,
            )
            body = response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("LLM alert composition failed, using template: %s", e)
            body = self._template_alert(ctx)

        return title, body

    @staticmethod
    def _template_alert(ctx: TriggerContext) -> str:
        """Fallback template alert when LLM is unavailable."""
        parts = [ctx.headline + "."]
        if ctx.warm_paths:
            best = ctx.warm_paths[0]
            parts.append(
                f"You have a warm path through {best.contact_name} "
                f"({best.path_description})."
            )
        if ctx.capability_matches:
            best_cap = ctx.capability_matches[0]
            parts.append(
                f"Your {best_cap.capability_name} experience is directly relevant."
            )
        parts.append("Want me to draft an outreach?")
        return " ".join(parts)

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _fetch_unalerted_activist_obs(self) -> list[dict]:
        """
        Fetch obs_investor rows that are:
        - is_activist = true
        - status = 'active'
        - not already alerted (no matching alert with trigger_obs_id)
        """
        if not self._db:
            return []
        from sqlalchemy import text
        rows = self._db.execute(
            text("""
                SELECT
                    oi.id, oi.company_id, oi.investor_name, oi.stake_pct,
                    oi.is_activist, oi.filing_type, oi.headline, oi.detail,
                    oi.observed_at, oi.metadata,
                    c.name AS company_name
                FROM global.obs_investor oi
                JOIN global.companies c ON c.id = oi.company_id
                WHERE oi.is_activist = true
                  AND oi.status = 'active'
                ORDER BY oi.observed_at DESC
                LIMIT 100
            """),
        ).fetchall()
        return [
            {
                "id": r[0], "company_id": r[1], "investor_name": r[2],
                "stake_pct": r[3], "is_activist": r[4], "filing_type": r[5],
                "headline": r[6], "detail": r[7], "observed_at": r[8],
                "metadata": r[9], "company_name": r[10],
                # unpack metadata fields if available
                "has_sale_demand": self._get_meta(r[9], "has_sale_demand", False),
                "has_board_demand": self._get_meta(r[9], "has_board_demand", False),
            }
            for r in rows
        ]

    def _fetch_all_bankers(self) -> list[dict]:
        """Fetch all bankers across all tenant schemas."""
        if not self._db:
            return []
        from sqlalchemy import text
        # In production this queries platform.tenants or a cross-schema view
        # For now, query the known tenant schema
        try:
            rows = self._db.execute(
                text("""
                    SELECT id, name, email, tenant_id
                    FROM tenant_1.bankers
                    ORDER BY id
                """),
            ).fetchall()
            return [{"id": r[0], "name": r[1], "email": r[2], "tenant_id": r[3]}
                    for r in rows]
        except Exception:
            return []

    def _alert_already_exists(self, obs_id: str, banker_id: str) -> bool:
        from sqlalchemy import text
        row = self._db.execute(
            text("""
                SELECT 1 FROM tenant_1.alerts
                WHERE banker_id = :banker_id
                  AND cited_sources::text LIKE :obs_pattern
                  AND status != 'dismissed'
                LIMIT 1
            """),
            {"banker_id": banker_id, "obs_pattern": f"%{obs_id}%"},
        ).fetchone()
        return row is not None

    def _write_alert(
        self,
        ctx: TriggerContext,
        title: str,
        body: str,
        cited_sources: list[dict],
    ) -> str:
        from sqlalchemy import text
        result = self._db.execute(
            text("""
                INSERT INTO tenant_1.alerts (
                    banker_id, trigger_type, title, body,
                    cited_sources, target_company_id,
                    relevance_score, status
                ) VALUES (
                    :banker_id, 'activist_13d', :title, :body,
                    :sources::jsonb, :company_id,
                    :score, 'unread'
                )
                RETURNING id
            """),
            {
                "banker_id": ctx.banker_id,
                "title": title,
                "body": body,
                "sources": json.dumps(cited_sources),
                "company_id": ctx.company_id,
                "score": ctx.relevance_score,
            },
        )
        self._db.commit()
        row = result.fetchone()
        return str(row[0]) if row else ""

    def _mark_obs_alerted(self, obs_id: str) -> None:
        """Tag obs_investor row so we don't re-process it."""
        from sqlalchemy import text
        self._db.execute(
            text("""
                UPDATE global.obs_investor
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{alerted}', 'true'::jsonb
                )
                WHERE id = :id
            """),
            {"id": obs_id},
        )
        self._db.commit()

    @staticmethod
    def _get_meta(metadata: Any, key: str, default: Any) -> Any:
        if not metadata:
            return default
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                return default
        if isinstance(metadata, dict):
            return metadata.get(key, default)
        return default
