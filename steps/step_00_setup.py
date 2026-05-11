import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"

def setup():
    """Create project directories, apply SQLite schema, initialize configs."""
    try:
        # Step 1: Create directories
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (ROOT / "steps").mkdir(parents=True, exist_ok=True)

        # Step 2: Connect to DB and create tables
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # Create votes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                vote_id          TEXT    PRIMARY KEY,
                year             INTEGER NOT NULL,
                chamber          TEXT    NOT NULL CHECK(chamber IN ('h','s')),
                category         TEXT,
                question         TEXT,
                result           TEXT,
                date             TEXT,
                is_discretionary INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Create vote_positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vote_positions (
                vote_id      TEXT    NOT NULL REFERENCES votes(vote_id),
                bioguide_id  TEXT    NOT NULL,
                position     INTEGER NOT NULL CHECK(position IN (-1, 0, 1)),
                PRIMARY KEY (vote_id, bioguide_id)
            )
        """)

        # Create legislators table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS legislators (
                bioguide_id      TEXT PRIMARY KEY,
                display_name     TEXT NOT NULL,
                party            TEXT,
                state            TEXT,
                chamber          TEXT CHECK(chamber IN ('h','s')),
                fec_candidate_id TEXT
            )
        """)

        # Create fec_disbursements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fec_disbursements (
                transaction_id         TEXT PRIMARY KEY,
                cycle                  INTEGER NOT NULL,
                recipient_candidate_id TEXT,
                committee_id           TEXT NOT NULL,
                disbursement_amount    REAL,
                disbursement_date      TEXT
            )
        """)

        # Create fec_committees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fec_committees (
                committee_id        TEXT PRIMARY KEY,
                committee_name      TEXT,
                committee_type      TEXT,
                committee_type_full TEXT,
                org_type            TEXT,
                org_type_full       TEXT
            )
        """)

        conn.commit()
        conn.close()

        # Step 3: Write .env template if missing
        env_file = ROOT / ".env"
        if not env_file.exists():
            env_file.write_text("FEC_API_KEY=your_key_here\n")

        # Step 4: Initialize methodology log if missing
        methodology_log = OUTPUT_DIR / "methodology_log.md"
        if not methodology_log.exists():
            methodology_log.write_text("# CIDA Methodology Log\n\n")

        # Step 5: Append Step 0 methodology entry
        log_entry = f"## {datetime.now().isoformat()} — Step 0: Setup\n- db_created: true\n- tables_created: 5\n\n"
        methodology_log.write_text(methodology_log.read_text() + log_entry)

        # Step 6: Write step_00_status.json
        status_data = {
            "step": 0,
            "name": "Setup",
            "status": "ok",
            "message": "Project setup complete",
            "values": {
                "db": str(DB_PATH),
                "tables": 5
            }
        }
        status_file = OUTPUT_DIR / "step_00_status.json"
        status_file.write_text(json.dumps(status_data, indent=2))

        # Step 7: Print success message
        print("Step 0: OK")

    except Exception as e:
        # Write failed status and exit
        status_data = {
            "step": 0,
            "name": "Setup",
            "status": "failed",
            "message": str(e),
            "values": {}
        }
        status_file = OUTPUT_DIR / "step_00_status.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status_data, indent=2))
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    setup()
