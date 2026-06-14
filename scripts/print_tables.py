#!/usr/bin/env python3
"""Print all rows from all tables in the Railway Postgres DB."""
import os, sys
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    sys.exit("DATABASE_URL not set")

try:
    import psycopg2
except ImportError:
    sys.exit("pip install psycopg2-binary")

conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("""
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema NOT IN ('pg_catalog','information_schema')
    ORDER BY table_schema, table_name
""")
tables = cur.fetchall()

print("=== ALL TABLES ===")
for schema, table in tables:
    print(f"  {schema}.{table}")

for schema, table in tables:
    cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
    count = cur.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"{schema}.{table}  ({count} rows)")
    print("=" * 60)
    if count == 0:
        print("  (empty)")
        continue
    limit = 20 if count <= 20 else 5
    cur.execute(f'SELECT * FROM "{schema}"."{table}" LIMIT {limit}')
    cols = [d[0] for d in cur.description]
    if count > 20:
        print(f"  (showing {limit} of {count})")
    print(f"  Columns: {cols}")
    for row in cur.fetchall():
        for col, val in zip(cols, row):
            v = str(val)
            if len(v) > 300:
                v = v[:300] + "..."
            print(f"    {col}: {v}")
        print()

cur.close()
conn.close()
print("\nDone.")
