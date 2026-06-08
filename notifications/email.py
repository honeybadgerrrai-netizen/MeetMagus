"""
DealFlow — Email Notifications via SendGrid

Usage:
    from app.notifications.email import send_alert_email

    send_alert_email(
        to_email="david@tidalpartners.com",
        to_name="David Handler",
        alert=alert_row,           # tenant_1.alerts row (dict or ORM obj)
        company_name="Alkami Technology",
        company_ticker="ALKT",
    )

Requires:
    SENDGRID_API_KEY in .env
    SENDGRID_FROM_EMAIL in .env  (e.g. intelligence@dealflow.ai)
    SENDGRID_FROM_NAME in .env   (e.g. DealFlow Intelligence)
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

log = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass


# ── Config ─────────────────────────────────────────────────────────────────────

SENDGRID_API_KEY   = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL         = os.environ.get("SENDGRID_FROM_EMAIL", "intelligence@dealflow.ai")
FROM_NAME          = os.environ.get("SENDGRID_FROM_NAME", "DealFlow Intelligence")
REPLY_TO_EMAIL     = os.environ.get("SENDGRID_REPLY_TO", "honeybadgerrrai@gmail.com")


# ── Badge / color helpers ──────────────────────────────────────────────────────

TRIGGER_META = {
    "activist_13d":   {"label": "Activist 13D",   "bg": "#FEE2E2", "color": "#991B1B", "banner_bg": "#FEF2F2", "banner_border": "#FECACA", "banner_text": "#7F1D1D"},
    "growth_signal":  {"label": "Growth Signal",  "bg": "#D1FAE5", "color": "#065F46", "banner_bg": "#ECFDF5", "banner_border": "#6EE7B7", "banner_text": "#064E3B"},
    "earnings":       {"label": "Earnings",       "bg": "#FEF3C7", "color": "#92400E", "banner_bg": "#FFFBEB", "banner_border": "#FCD34D", "banner_text": "#78350F"},
    "market_move":    {"label": "Market Move",    "bg": "#DBEAFE", "color": "#1E40AF", "banner_bg": "#EFF6FF", "banner_border": "#93C5FD", "banner_text": "#1E3A8A"},
}

def _trigger_meta(trigger_type: str) -> dict:
    return TRIGGER_META.get(trigger_type, {
        "label": trigger_type.replace("_", " ").title(),
        "bg": "#E0E7FF", "color": "#3730A3",
        "banner_bg": "#EEF2FF", "banner_border": "#C7D2FE", "banner_text": "#312E81",
    })


# ── HTML template ──────────────────────────────────────────────────────────────

def _build_html(
    banker_name: str,
    alert_title: str,
    alert_body: str,
    trigger_type: str,
    company_name: str,
    company_ticker: Optional[str],
    relevance_score: float,
    to_email: str,
    date_str: str,
) -> str:
    m = _trigger_meta(trigger_type)
    badge_label = m["label"]
    ticker_str = f" · {company_ticker}" if company_ticker else ""
    score_pct = int(relevance_score * 100) if relevance_score else 0
    first_name = banker_name.split()[0] if banker_name else "there"

    # Convert alert body newlines to <br> + paragraph breaks
    body_html = ""
    for para in alert_body.strip().split("\n\n"):
        lines = para.strip().replace("\n", "<br>")
        if lines:
            body_html += f'<p style="color:#374151;font-size:13px;line-height:1.75;margin:0 0 14px;font-family:Arial,sans-serif">{lines}</p>\n'

    # Reply buttons (mailto: links — works in every email client)
    reply_a = f"mailto:{to_email}?subject=Re: {alert_title} [A]&body=A) Yes, I know this contact well."
    reply_b = f"mailto:{to_email}?subject=Re: {alert_title} [B]&body=B) Somewhat familiar — need more context."
    reply_c = f"mailto:{to_email}?subject=Re: {alert_title} [C]&body=C) Not familiar — please draft an outreach note."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{alert_title}</title>
</head>
<body style="margin:0;padding:0;background:#F3F4F6;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F3F4F6;padding:32px 16px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #E5E7EB">

  <!-- Header -->
  <tr>
    <td style="background:#0F3D82;padding:16px 28px">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td>
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#7B9FE8;margin-right:8px;vertical-align:middle"></span>
          <span style="color:rgba(255,255,255,0.92);font-size:12px;font-weight:700;letter-spacing:0.07em;text-transform:uppercase;vertical-align:middle">DealFlow Intelligence</span>
        </td>
        <td align="right">
          <span style="color:rgba(255,255,255,0.45);font-size:11px">{date_str}</span>
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- Alert banner -->
  <tr>
    <td style="background:{m['banner_bg']};border-bottom:1px solid {m['banner_border']};padding:10px 28px">
      <span style="display:inline-block;background:{m['bg']};color:{m['color']};font-size:10px;font-weight:700;letter-spacing:0.07em;text-transform:uppercase;padding:2px 10px;border-radius:20px;margin-right:8px">{badge_label}</span>
      <span style="color:{m['banner_text']};font-size:12px;font-weight:500">{company_name}{ticker_str} &middot; Relevance {score_pct}%</span>
    </td>
  </tr>

  <!-- Body -->
  <tr>
    <td style="padding:24px 28px">
      <p style="color:#6B7280;font-size:13px;margin:0 0 14px;font-family:Arial,sans-serif">{first_name},</p>
      <p style="color:#111827;font-size:16px;font-weight:700;line-height:1.4;margin:0 0 16px;font-family:Arial,sans-serif">{alert_title}</p>

      {body_html}

      <!-- Divider -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0">
        <tr><td style="border-top:1px solid #F3F4F6;height:1px"></td></tr>
      </table>

      <!-- Reply question -->
      <p style="font-size:13px;font-weight:700;color:#111827;margin:0 0 8px;font-family:Arial,sans-serif">How well do you know the key contact here?</p>
      <p style="font-size:12px;color:#6B7280;margin:0 0 16px;font-family:Arial,sans-serif">Click a reply below &mdash; DealFlow will follow up based on your answer.</p>

      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding-right:8px">
            <a href="{reply_a}" style="display:inline-block;padding:8px 18px;border-radius:20px;border:1.5px solid #6366F1;background:#ffffff;color:#4F46E5;font-size:12px;font-weight:700;text-decoration:none;font-family:Arial,sans-serif">A &nbsp; Yes, know them well</a>
          </td>
          <td style="padding-right:8px">
            <a href="{reply_b}" style="display:inline-block;padding:8px 18px;border-radius:20px;border:1.5px solid #D1D5DB;background:#ffffff;color:#374151;font-size:12px;font-weight:700;text-decoration:none;font-family:Arial,sans-serif">B &nbsp; Somewhat</a>
          </td>
          <td>
            <a href="{reply_c}" style="display:inline-block;padding:8px 18px;border-radius:20px;border:1.5px solid #D1D5DB;background:#ffffff;color:#374151;font-size:12px;font-weight:700;text-decoration:none;font-family:Arial,sans-serif">C &nbsp; Draft outreach</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#F9FAFB;border-top:1px solid #F3F4F6;padding:14px 28px">
      <p style="font-size:11px;color:#6B7280;font-weight:700;margin:0 0 3px;font-family:Arial,sans-serif">DealFlow Intelligence &middot; context saved automatically</p>
      <p style="font-size:11px;color:#9CA3AF;margin:0;font-family:Arial,sans-serif">Banker: {banker_name} &middot; Confidence: {relevance_score:.2f} &middot; <a href="mailto:{to_email}?subject=Unsubscribe" style="color:#9CA3AF">Unsubscribe</a></p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── Plain-text fallback ────────────────────────────────────────────────────────

def _build_text(
    banker_name: str,
    alert_title: str,
    alert_body: str,
    company_name: str,
    company_ticker: Optional[str],
) -> str:
    first_name = banker_name.split()[0] if banker_name else "there"
    ticker_str = f" ({company_ticker})" if company_ticker else ""
    return f"""{first_name},

{alert_title}

Company: {company_name}{ticker_str}

{alert_body}

---
DealFlow Intelligence
Reply A) I know this contact well
Reply B) Somewhat familiar
Reply C) Draft an outreach note for me
"""


# ── Public send function ───────────────────────────────────────────────────────

def send_alert_email(
    to_email: str,
    to_name: str,
    alert_title: str,
    alert_body: str,
    trigger_type: str,
    company_name: str,
    company_ticker: Optional[str] = None,
    relevance_score: float = 0.8,
    dry_run: bool = False,
) -> dict:
    """
    Send a DealFlow intelligence alert email via SendGrid.

    Returns:
        {"status": "sent", "status_code": 202}  on success
        {"status": "dry_run", "html": "..."}     when dry_run=True
        {"status": "error", "error": "..."}      on failure
    """
    if not SENDGRID_API_KEY and not dry_run:
        raise RuntimeError("SENDGRID_API_KEY not set. Add it to .env")

    date_str = datetime.utcnow().strftime("%a %b %-d, %Y")

    html = _build_html(
        banker_name=to_name,
        alert_title=alert_title,
        alert_body=alert_body,
        trigger_type=trigger_type,
        company_name=company_name,
        company_ticker=company_ticker,
        relevance_score=relevance_score,
        to_email=to_email,
        date_str=date_str,
    )
    text = _build_text(
        banker_name=to_name,
        alert_title=alert_title,
        alert_body=alert_body,
        company_name=company_name,
        company_ticker=company_ticker,
    )

    if dry_run:
        log.info(f"[DRY RUN] Would send '{alert_title}' to {to_email}")
        return {"status": "dry_run", "html": html, "text": text}

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)

        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=alert_title,
        )
        message.reply_to = Email(REPLY_TO_EMAIL)
        message.add_content(Content("text/plain", text))
        message.add_content(Content("text/html", html))

        response = sg.send(message)
        log.info(f"Email sent to {to_email} — status {response.status_code}")
        return {"status": "sent", "status_code": response.status_code}

    except Exception as e:
        log.error(f"Failed to send email to {to_email}: {e}")
        return {"status": "error", "error": str(e)}


# ── Convenience: send all unread alerts for a banker ─────────────────────────

def send_unread_alerts(banker_email: str, db_url: Optional[str] = None) -> list[dict]:
    """
    Fetch all unread alerts for a banker and send each one.
    Marks alerts as 'read' after sending.

    Usage:
        from app.notifications.email import send_unread_alerts
        results = send_unread_alerts("david@tidalpartners.com")
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    url = db_url or os.environ.get("DATABASE_URL")
    engine = create_engine(url)

    results = []
    with Session(engine) as session:
        rows = session.execute(text("""
            SELECT
                a.id,
                a.trigger_type,
                a.title,
                a.body,
                a.relevance_score,
                b.name   AS banker_name,
                b.email  AS banker_email,
                c.name   AS company_name,
                c.ticker AS company_ticker
            FROM tenant_1.alerts a
            JOIN tenant_1.bankers b ON b.id = a.banker_id
            LEFT JOIN global.companies c ON c.id = a.target_company_id
            WHERE b.email = :email
              AND a.status = 'unread'
            ORDER BY a.created_at DESC
        """), {"email": banker_email}).fetchall()

        for row in rows:
            result = send_alert_email(
                to_email=row.banker_email,
                to_name=row.banker_name,
                alert_title=row.title,
                alert_body=row.body,
                trigger_type=row.trigger_type,
                company_name=row.company_name or "Unknown",
                company_ticker=row.company_ticker,
                relevance_score=row.relevance_score or 0.8,
            )
            result["alert_id"] = str(row.id)
            result["title"] = row.title
            results.append(result)

            if result["status"] == "sent":
                session.execute(
                    text("UPDATE tenant_1.alerts SET status = 'read' WHERE id = :id"),
                    {"id": row.id}
                )
                session.commit()

    return results


# ── CLI entrypoint ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    email_arg = sys.argv[1] if len(sys.argv) > 1 else "honeybadgerrrai@gmail.com"
    dry = "--dry-run" in sys.argv

    print(f"Sending unread alerts to {email_arg} {'[DRY RUN]' if dry else ''}...")

    if dry:
        # Quick dry-run demo with hardcoded data
        result = send_alert_email(
            to_email=email_arg,
            to_name="David Handler",
            alert_title="Jana Partners reboots Alkami sale push — your Penn board colleague Jeff Fox is on their board",
            alert_body=(
                "Jana Partners (5.1%% + 2.8%% swap = ~7.9%% economic interest) filed a new 13D on Alkami Technology (ALKT) "
                "and is publicly pushing the company to restart a strategic sale process. Bloomberg reported this May 28, 2026.\n\n"
                "YOUR WARM PATH: Jeff Fox is a Class I Alkami director (term to 2028) and you share a board seat at Penn Entertainment (PENN). "
                "He has banker instincts — started at Merrill Lynch. Last interaction: March 2026.\n\n"
                "ALKAMI FINANCIALS: $444M revenue (+33%% YoY), $493M ARR, 301 FI clients, $100M buyback announced Q1 2026."
            ),
            trigger_type="activist_13d",
            company_name="Alkami Technology",
            company_ticker="ALKT",
            relevance_score=0.85,
            dry_run=True,
        )
        # Save preview HTML
        preview_path = Path(__file__).parent.parent.parent / "dealflow_email_preview.html"
        preview_path.write_text(result["html"])
        print(f"  Preview saved → {preview_path}")
        print("  Status: dry_run ✓")
    else:
        results = send_unread_alerts(email_arg)
        for r in results:
            print(f"  [{r['status']}] {r.get('title', '')[:60]}")
        print(f"\n  Total: {len(results)} alert(s) processed")
