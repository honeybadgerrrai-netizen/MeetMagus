"""
app/workers/prompts/edgar.py
Extraction prompts for SEC EDGAR filings.

Each function returns a list of OpenAI-format messages ready to pass to LLMClient.
The LLM is instructed to return valid JSON matching the target observation schema.

Observation types by form:
  SC 13D / SC 13D/A  →  obs_investor  (activist, large stake)
  SC 13G / SC 13G/A  →  obs_investor  (passive, large stake)
  4                  →  obs_investor  (insider_buy / insider_sell)
  8-K / 8-K/A        →  obs_financial | obs_competitive | obs_employee
                        (classified by item number in the filing)
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────────────
# 13D / 13G  →  obs_investor
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_13D = """\
You are a financial data extraction engine for an investment banking intelligence system.
Your job is to parse SEC 13D and 13G filings and return structured JSON.
Return ONLY valid JSON. No markdown, no explanation, no extra text.
"""

def build_13d_messages(
    form_type: str,
    company_name: str,
    filer_name: str,
    raw_text: str,
) -> list[dict]:
    """
    Build extraction messages for SC 13D / SC 13G filings.
    Target table: obs_investor
    """
    is_activist_hint = (
        "SC 13D filings typically indicate activist or strategic intent. "
        "SC 13G filings typically indicate passive investment."
    ) if "13D" in form_type else (
        "SC 13G filings typically indicate passive investment, not activist intent."
    )

    user_prompt = f"""\
Extract structured data from this SEC {form_type} filing.

Subject company: {company_name}
Filer (investor): {filer_name}
Form type: {form_type}
{is_activist_hint}

Filing content:
---
{raw_text[:3000]}
---

Return a JSON object with exactly these fields:

{{
  "signal_type": "<one of: 13d_filing, 13g_filing, insider_buy, insider_sell, ownership_change, activist_letter, board_demand>",
  "investor_name": "<full legal name of the investor/filer>",
  "stake_pct": <ownership percentage as a float, e.g. 7.9, or null if not found>,
  "shares_held": <number of shares as integer, or null>,
  "is_activist": <true if 13D or if activist intent stated, false otherwise>,
  "filing_type": "<the SEC form type, e.g. SC 13D>",
  "headline": "<one sentence summarizing the filing, max 120 chars>",
  "detail": "<2-3 sentences with key facts: stake size, stated purpose, any demands or plans>",
  "purpose_of_transaction": "<investor's stated purpose from Item 4, or null>",
  "has_board_demand": <true if filing mentions seeking board seats, false otherwise>,
  "has_sale_demand": <true if filing mentions pushing for sale/merger of the company, false otherwise>
}}

If a field cannot be determined from the text, use null.
"""
    return [
        {"role": "system", "content": SYSTEM_13D},
        {"role": "user", "content": user_prompt},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Form 4 (insider transactions)  →  obs_investor
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_FORM4 = """\
You are a financial data extraction engine. Parse SEC Form 4 insider transaction filings.
Return ONLY valid JSON. No markdown, no explanation.
"""

def build_form4_messages(
    company_name: str,
    filer_name: str,
    raw_text: str,
) -> list[dict]:
    user_prompt = f"""\
Extract structured data from this SEC Form 4 insider transaction filing.

Subject company: {company_name}
Insider (filer): {filer_name}

Filing content:
---
{raw_text[:2000]}
---

Return a JSON object with exactly these fields:

{{
  "signal_type": "<insider_buy or insider_sell>",
  "investor_name": "<full name of the insider>",
  "insider_title": "<their role, e.g. CEO, Director, CFO, or null>",
  "transaction_type": "<P for purchase, S for sale>",
  "shares_transacted": <number of shares as integer, or null>,
  "price_per_share": <price as float, or null>,
  "total_value_usd": <total transaction value in USD as float, or null>,
  "shares_owned_after": <shares owned after transaction as integer, or null>,
  "headline": "<one sentence, e.g. 'CEO John Smith purchased 50,000 shares at $24.50'>",
  "detail": "<2 sentences with context: role, transaction size, ownership after>"
}}

If a field cannot be determined, use null.
"""
    return [
        {"role": "system", "content": SYSTEM_FORM4},
        {"role": "user", "content": user_prompt},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# 8-K  →  obs_financial | obs_competitive | obs_employee
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_8K = """\
You are a financial data extraction engine. Parse SEC 8-K filings.
Classify the filing by its primary event type and extract structured data.
Return ONLY valid JSON. No markdown, no explanation.
"""

def build_8k_messages(
    company_name: str,
    raw_text: str,
) -> list[dict]:
    """
    8-K filings can cover many event types. We first classify, then extract.
    The 'observation_type' field tells the extractor which table to write to.
    """
    user_prompt = f"""\
Extract structured data from this SEC 8-K filing.

Subject company: {company_name}

Filing content:
---
{raw_text[:3000]}
---

First, classify the primary event. Then extract the relevant fields.

Return a JSON object with exactly these fields:

{{
  "observation_type": "<one of: financial, competitive, employee, other>",
  "event_category": "<brief category, e.g. earnings_guidance, acquisition, executive_departure, restructuring>",
  "headline": "<one sentence summarizing the key event, max 120 chars>",
  "detail": "<2-3 sentences with key facts>",
  "financial": {{
    "signal_type": "<revenue_signal, margin_signal, fundraising, burn_signal, valuation, debt_maturity or null>",
    "metric_name": "<e.g. revenue, EBITDA, ARR, or null>",
    "metric_value": <numeric value or null>,
    "metric_unit": "<e.g. USD_millions, percent, or null>",
    "amount_usd": <total dollar amount as float, or null>
  }},
  "competitive": {{
    "signal_type": "<acquisition, product_launch, partnership, pricing_change or null>",
    "counterparty_name": "<name of acquired/partner company or null>",
    "deal_value_usd": <deal value as float, or null>
  }},
  "employee": {{
    "signal_type": "<exec_hire, exec_departure, layoff, org_change or null>",
    "person_name": "<name of executive or null>",
    "person_title": "<their role or null>",
    "department": "<affected department or null>"
  }}
}}

Populate only the section matching observation_type. Set other sections to null values.
"""
    return [
        {"role": "system", "content": SYSTEM_8K},
        {"role": "user", "content": user_prompt},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Router — pick the right prompt builder by form type
# ──────────────────────────────────────────────────────────────────────────────

def build_extraction_messages(
    form_type: str,
    company_name: str,
    filer_name: str,
    raw_text: str,
) -> tuple[list[dict], str]:
    """
    Returns (messages, target_observation_type) for the given form type.
    target_observation_type is one of: investor, financial, competitive, employee
    """
    ft = form_type.upper().strip()

    if ft in ("SC 13D", "SC 13D/A"):
        return build_13d_messages(ft, company_name, filer_name, raw_text), "investor"

    if ft in ("SC 13G", "SC 13G/A"):
        return build_13d_messages(ft, company_name, filer_name, raw_text), "investor"

    if ft == "4":
        return build_form4_messages(company_name, filer_name, raw_text), "investor"

    if ft in ("8-K", "8-K/A"):
        return build_8k_messages(company_name, raw_text), "8k_classified"

    # Fallback — generic extraction, classify as financial
    fallback = [
        {"role": "system", "content": "Extract key facts from this SEC filing as JSON."},
        {"role": "user", "content": f"Form: {form_type}\nCompany: {company_name}\n\n{raw_text[:2000]}"},
    ]
    return fallback, "financial"
