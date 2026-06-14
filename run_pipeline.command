#!/bin/bash
cd "$(dirname "$0")"

echo "======================================"
echo "  MeetMagus Pipeline Runner"
echo "======================================"

echo ""
echo "→ Installing Python dependencies..."
pip3 install -r requirements.txt -q 2>&1 | tail -3

echo ""
echo "→ Creating/ensuring schema..."
python3 scripts/create_schema.py

echo ""
echo "→ Seeding Alkami scenario..."
python3 -m scripts.alkami_seed

echo ""
echo "→ Fetching EDGAR filings (last 7 days)..."
python3 -m app.fetchers.edgar 7

echo ""
echo "→ Running extractor (up to 20 jobs)..."
python3 -m app.workers.extractor --limit 20

echo ""
echo "→ Running embedder (up to 50 observations)..."
python3 -m app.workers.embedder --limit 50

echo ""
echo "→ Running 13D trigger agent..."
python3 -m app.agents.trigger_13d

echo ""
echo "→ Printing all table contents..."
python3 scripts/print_tables.py

echo ""
echo "======================================"
echo "  Done!"
echo "======================================"
