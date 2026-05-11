"""
Step 10a: Prep annotation pipeline.
- Adds vote_crs and vote_facets tables to SQLite
- Pulls CRS policy area from Congress.gov for identifiable bills
- Writes vote batches to output/annotation_batches/ for Haiku agents
"""

import json
import re
import sqlite3
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"
BATCHES_DIR = OUTPUT_DIR / "annotation_batches"
BATCHES_DIR.mkdir(parents=True, exist_ok=True)

CONGRESS_API_KEY = "vfc9KrSQm1yKEYN0uj6Cg8ZVVeGpwI1xtHUkb1Wc"
CONGRESS_API = "https://api.congress.gov/v3"
BATCH_SIZE = 50


def add_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vote_crs (
            vote_id TEXT PRIMARY KEY,
            policy_area TEXT,
            bill_type TEXT,
            bill_number TEXT
        );
        CREATE TABLE IF NOT EXISTS vote_facets (
            vote_id TEXT,
            facet TEXT,
            score INTEGER,
            PRIMARY KEY (vote_id, facet)
        );
    """)
    conn.commit()
    print("Tables created.")


def parse_bill_ref(question):
    """Extract (bill_type, bill_number) from a vote question string.
    Returns (None, None) if not identifiable."""
    q = question or ""

    # Direct bill references with congress marker e.g. "H.R. 7888 (118th)"
    patterns = [
        (r"H\.R\.\s*(\d+)", "hr"),
        (r"(?<!\w)S\.\s*(\d+)(?!\w)", "s"),
        (r"H\.J\.Res\.\s*(\d+)", "hjres"),
        (r"S\.J\.Res\.\s*(\d+)", "sjres"),
        (r"H\.Con\.Res\.\s*(\d+)", "hconres"),
        (r"S\.Con\.Res\.\s*(\d+)", "sconres"),
        (r"H\.Res\.\s*(\d+)", "hres"),
        (r"S\.Res\.\s*(\d+)", "sres"),
    ]
    for pattern, bill_type in patterns:
        m = re.search(pattern, q)
        if m:
            return bill_type, m.group(1)
    return None, None


def fetch_policy_area(bill_type, bill_number, cache):
    key = f"{bill_type}/{bill_number}"
    if key in cache:
        return cache[key]
    try:
        url = f"{CONGRESS_API}/bill/118/{bill_type}/{bill_number}"
        r = requests.get(url, params={"api_key": CONGRESS_API_KEY, "format": "json"}, timeout=15)
        if r.status_code == 200:
            policy_area = r.json().get("bill", {}).get("policyArea", {}).get("name", "")
        else:
            policy_area = ""
    except Exception:
        policy_area = ""
    time.sleep(0.1)
    cache[key] = policy_area
    return policy_area


def pull_crs(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT vote_id, question FROM votes")
    votes = cursor.fetchall()

    cache = {}
    updated = 0
    for vote_id, question in votes:
        bill_type, bill_number = parse_bill_ref(question)
        if not bill_type:
            continue
        policy_area = fetch_policy_area(bill_type, bill_number, cache)
        cursor.execute(
            "INSERT OR REPLACE INTO vote_crs (vote_id, policy_area, bill_type, bill_number) VALUES (?,?,?,?)",
            (vote_id, policy_area, bill_type, bill_number),
        )
        updated += 1
        if updated % 50 == 0:
            conn.commit()
            print(f"  CRS: {updated} votes matched, {len(cache)} unique bills fetched")

    conn.commit()
    print(f"  CRS done: {updated} votes matched to bills, {len(cache)} unique bills")
    return updated


def write_batches(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.vote_id, v.chamber, v.category, v.question,
               COALESCE(c.policy_area, '') as policy_area
        FROM votes v
        LEFT JOIN vote_crs c ON v.vote_id = c.vote_id
        WHERE v.is_discretionary = 1
        ORDER BY v.vote_id
    """)
    rows = cursor.fetchall()
    votes = [
        {"vote_id": r[0], "chamber": r[1], "category": r[2],
         "question": r[3], "policy_area": r[4]}
        for r in rows
    ]

    batches = [votes[i:i+BATCH_SIZE] for i in range(0, len(votes), BATCH_SIZE)]
    for i, batch in enumerate(batches):
        path = BATCHES_DIR / f"batch_{i:02d}.json"
        with open(path, "w") as f:
            json.dump(batch, f, indent=2)

    print(f"  Written {len(batches)} batch files ({len(votes)} discretionary votes)")
    return len(batches), len(votes)


def main():
    conn = sqlite3.connect(DB_PATH)
    print("Step 10a: Prep annotation")

    print("Adding tables...")
    add_tables(conn)

    print("Pulling Congress.gov CRS policy areas...")
    pull_crs(conn)

    print("Writing vote batches...")
    n_batches, n_votes = write_batches(conn)

    conn.close()
    print(f"Done. {n_batches} batches ready in output/annotation_batches/")


if __name__ == "__main__":
    main()
