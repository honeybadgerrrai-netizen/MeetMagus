#!/bin/bash
# DealFlow — full pipeline runner
# Runs: schema check → seed → fetch → extract → embed → trigger agent

set -e
cd "$(dirname "$0")/.."

echo "======================================"
echo "  DealFlow Pipeline Runner"
echo "======================================"

# Install deps if needed
echo ""
echo "→ Installing Python dependencies..."
pip3 install -r requirements.txt -q 2>&1 | tail -3

# Check DB connection
echo ""
echo "→ Checking DB connection..."
python3 -c "
import os; from dotenv import load_dotenv; load_dotenv()
import psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT version()\")
print('  Connected:', cur.fetchone()[0][:50])
conn.close()
"

# Create schema (idempotent — safe to run every time)
echo ""
echo "→ Creating/ensuring schema..."
python3 scripts/create_schema.py

# Seed Alkami scenario
echo ""
echo "→ Seeding Alkami scenario..."
python3 -m scripts.alkami_seed

# Fetch recent EDGAR filings (last 7 days)
echo ""
echo "→ Fetching EDGAR filings (last 7 days)..."
python3 -m app.fetchers.edgar 7

# Run extractor
echo ""
echo "→ Running extractor (up to 20 jobs)..."
python3 -m app.workers.extractor --limit 20

# Run embedder
echo ""
echo "→ Running embedder (up to 50 observations)..."
python3 -m app.workers.embedder --limit 50

# Run 13D trigger agent
echo ""
echo "→ Running 13D trigger agent..."
python3 -m app.agents.trigger_13d

# Print all tables
echo ""
echo "→ Printing all table contents..."
python3 scripts/print_tables.py

echo ""
echo "======================================"
echo "  Done!"
echo "======================================"
