#!/bin/bash
cd "$(dirname "$0")"
echo "→ Seeding BuildOps + Anand Sankaralingam..."
python3 -m scripts.buildops_seed
echo ""
echo "→ Printing BuildOps tables..."
python3 -c "
import os; from dotenv import load_dotenv; load_dotenv()
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

print('=== global.companies (BuildOps) ===')
cur.execute(\"SELECT name, domain, hq_city, industry, is_prospect, description FROM global.companies WHERE name = 'BuildOps'\")
for row in cur.fetchall(): print(' ', row)

print()
print('=== tenant_1.bankers (Anand) ===')
cur.execute(\"SELECT name, email, title FROM tenant_1.bankers WHERE name = 'Anand Sankaralingam'\")
for row in cur.fetchall(): print(' ', row)

print()
print('=== tenant_1.alerts (Anand/BuildOps) ===')
cur.execute(\"SELECT title, relevance_score, status FROM tenant_1.alerts a JOIN global.companies c ON a.target_company_id = c.id WHERE c.name = 'BuildOps'\")
for row in cur.fetchall(): print(' ', row)

print()
print('=== obs counts for BuildOps ===')
for t in ['obs_financial','obs_competitive','obs_macro']:
    cur.execute(f\"SELECT COUNT(*) FROM global.{t} WHERE company_id = (SELECT id FROM global.companies WHERE name = 'BuildOps')\")
    print(f'  {t}:', cur.fetchone()[0])

conn.close()
"
echo ""
echo "Done!"
