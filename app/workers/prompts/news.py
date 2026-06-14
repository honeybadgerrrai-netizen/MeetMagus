"""
app/workers/prompts/news.py
LLM prompts for classifying and extracting signals from news articles.

A news article can map to any of these obs tables:
  obs_financial    — revenue, earnings, fundraising, valuation, debt
  obs_competitive  — product launches, acquisitions, pricing, partnerships
  obs_customer     — new customer wins, contract renewals, churn signals
  obs_org_events   — exec hires/departures, layoffs, reorgs, strategic hires
  obs_investor     — large stake disclosures, activist news (beyond SEC filings)
  obs_macro        — macro trends affecting a sector
  obs_regulatory   — FDA approvals/rejections, 510(k), NDA/BLA, CMS decisions (healthcare)
  obs_clinical     — clinical trial milestones: first patient dosed, data readouts, phase transitions
  irrelevant       — PR fluff, opinion, unrelated content → discard

The LLM returns a single JSON object with a top-level obs_type field
that tells the pipeline which table to write to.
"""

from __future__ import annotations


SYSTEM_NEWS = """\
You are a financial intelligence extraction engine for an investment banking platform.

Your job: read a news headline and summary about a specific company, then:
1. Decide what TYPE of business signal it is (or if it's irrelevant noise)
2. Extract the key structured facts from it

You must return ONLY valid JSON. No markdown, no explanation, no extra text.

Signal type guide:
- financial:   earnings, revenue, guidance, fundraising, valuation, debt, burn rate, program sale
- competitive: product launch, pricing change, acquisition, partnership, market share, win/loss,
               competitor drug approval (directly threatens this company's market)
- customer:    new customer win, contract, renewal, churn, formulary win/loss, hospital system contract
- org_event:   exec hire, exec departure, layoff, reorg, new division, title change,
               strategic hire (Head of IR = IPO signal; General Counsel = IPO/M&A signal;
               Medical Science Liaison = new drug launch; VP Market Access = commercial preparation)
- investor:    large shareholder news, activist campaigns (beyond what SEC filings cover)
- macro:       industry-wide trend affecting this company's sector
- regulatory:  FDA approval, FDA rejection, FDA warning letter, 510(k) clearance, IND filing,
               NDA/BLA submission, CMS coverage decision, EMA approval, clinical hold,
               breakthrough designation, fast track, accelerated approval
- clinical:    clinical trial initiation, first patient dosed, enrollment milestone,
               enrollment complete, data readout (positive/negative/mixed), trial failure,
               trial success, phase transition (Phase 1→2, Phase 2→3), trial pause/termination
- irrelevant:  opinion pieces, awards, rankings, generic industry news with no specific signal

Be strict about "irrelevant" — most press releases and puff pieces should be discarded.
Only extract signals a senior banker would actually care about.
For healthcare companies, regulatory and clinical signals are often the MOST important — prioritise them.
"""


def build_news_extraction_messages(
    company_name: str,
    headline: str,
    summary: str,
    source: str,
    published_date: str,
) -> list[dict]:
    """
    Build LLM messages to classify one news article and extract its signal.

    Returns OpenAI-format message list.
    The expected JSON response schema is defined inline in the prompt.
    """

    user_prompt = f"""\
Analyze this news article about {company_name}.

Company: {company_name}
Source: {source}
Date: {published_date}
Headline: {headline}
Summary: {summary}

Return a JSON object with exactly these fields:

{{
  "obs_type": "<financial | competitive | customer | org_event | investor | macro | regulatory | clinical | irrelevant>",
  "signal_type": "<specific signal, see below>",
  "headline": "<rewritten 1-sentence headline, max 120 chars, factual only>",
  "detail": "<2-3 sentences with the key facts a banker needs to know>",
  "confidence": <0.0–1.0 — how confident are you this is a real signal vs noise>,
  "is_about_subject_company": <true if {company_name} is the subject, false if only mentioned>,

  "financial": {{
    "signal_type": "<revenue_signal | margin_signal | fundraising | burn_signal | valuation | debt_maturity | revenue_mix | earnings>",
    "metric_name": "<e.g. ARR, revenue, EBITDA — or null>",
    "metric_value": <numeric value or null>,
    "metric_unit": "<USD_millions, percent, etc. — or null>",
    "amount_usd": <total dollar amount as float or null>
  }},

  "competitive": {{
    "signal_type": "<product_launch | pricing_change | acquisition | partnership | market_share | win_loss>",
    "competitor_name": "<name of competitor or acquiree — or null>",
    "product_name": "<product or offering name — or null>",
    "product_overlap_note": "<how this overlaps with {company_name}'s market — or null>",
    "deal_value_usd": <deal value as float or null>
  }},

  "customer": {{
    "signal_type": "<new_customer | contract_renewal | churn_signal | expansion | reference>",
    "customer_name": "<name of customer — or null>",
    "contract_value_usd": <contract value or null>,
    "contract_duration_years": <years or null>
  }},

  "org_event": {{
    "signal_type": "<exec_hire | exec_departure | layoff | reorg | new_division | title_change>",
    "person_name": "<name of executive — or null>",
    "person_title": "<their role — or null>",
    "department_affected": "<department or null>",
    "headcount_impact": <number of people affected or null>
  }},

  "investor": {{
    "signal_type": "<activist_campaign | large_stake | stake_increase | stake_decrease | proxy_fight>",
    "investor_name": "<name of investor or fund — or null>",
    "stake_pct": <ownership percentage as float or null>
  }},

  "macro": {{
    "trend_name": "<short name for the macro trend — or null>",
    "impact_direction": "<tailwind | headwind | neutral>",
    "relevance_note": "<why this macro trend affects {company_name} — or null>"
  }},

  "regulatory": {{
    "signal_type": "<fda_approval | fda_rejection | fda_warning_letter | 510k_clearance | ind_filing | nda_submission | bla_submission | cms_coverage_decision | ema_approval | clinical_hold | breakthrough_designation | fast_track | accelerated_approval>",
    "agency": "<FDA | EMA | CMS | FTC | PMDA — or null>",
    "drug_device_name": "<name of the drug, biologic, or device — or null>",
    "indication": "<disease or condition being treated — or null>",
    "decision": "<approved | rejected | pending | withdrawn | filed — or null>",
    "application_number": "<NDA/BLA/510(k)/IND number if mentioned — or null>"
  }},

  "clinical": {{
    "signal_type": "<trial_initiated | first_patient_dosed | enrollment_milestone | enrollment_complete | data_readout | trial_success | trial_failure | phase_transition | trial_pause | trial_termination | abstract_presented>",
    "trial_id": "<ClinicalTrials.gov NCT number if mentioned — or null>",
    "trial_name": "<drug or program name — or null>",
    "indication": "<disease or condition — or null>",
    "phase": "<Phase 1 | Phase 1/2 | Phase 2 | Phase 3 | Phase 4 — or null>",
    "outcome": "<positive | negative | mixed | pending — or null, only for data readouts>",
    "enrollment_count": <number of patients if mentioned or null>
  }}
}}

Rules:
- Set obs_type to "irrelevant" for: awards, rankings, generic market commentary, opinion
- Set is_about_subject_company to false if {company_name} is only briefly mentioned
- Only populate the section matching obs_type; set other sections' fields to null
- confidence below 0.5 should usually be obs_type = "irrelevant"
- If obs_type is "irrelevant", still return the full JSON structure with nulls
"""

    return [
        {"role": "system", "content": SYSTEM_NEWS},
        {"role": "user", "content": user_prompt},
    ]
