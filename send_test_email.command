#!/bin/bash
cd "$(dirname "$0")"
echo "→ Installing dependencies..."
pip3 install sendgrid certifi -q
# Fix macOS SSL cert issue
export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())" 2>/dev/null || echo "")
export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
echo "→ Sending MeetMagus test email via SendGrid..."
python3 -c "
import sys
sys.path.insert(0, '.')
from app.notifications.email import send_alert_email

result = send_alert_email(
    to_email='honeybadgerrrai@gmail.com',
    to_name='Anand',
    alert_title='Jana Partners reboots Alkami sale push — your Penn board colleague Jeff Fox is on their board',
    alert_body='''Jana Partners (5.1% + 2.8% swap = ~7.9% economic interest) filed a new 13D on Alkami Technology (ALKT) and is publicly pushing the company to restart a strategic sale process. Bloomberg reported this May 28, 2026.

YOUR WARM PATH: Jeff Fox is a Class I Alkami director (term to 2028) and you share a board seat at Penn Entertainment (PENN). He has banker instincts — started at Merrill Lynch. Last interaction: March 2026. Relationship score: 9/10.

ALKAMI FINANCIALS: \$444M revenue (+33% YoY), \$493M ARR (+22% YoY), 301 FI clients, \$100M buyback announced Q1 2026. Rule of 45 target by 2030.''',
    trigger_type='activist_13d',
    company_name='Alkami Technology',
    company_ticker='ALKT',
    relevance_score=0.85,
)
print('  Status:', result.get('status'))
print('  HTTP:', result.get('status_code'))
if result.get('error'):
    print('  Error:', result.get('error'))
"
echo "Done!"
