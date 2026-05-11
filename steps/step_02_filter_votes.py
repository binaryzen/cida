import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"
METHODOLOGY_LOG_PATH = OUTPUT_DIR / "methodology_log.md"
STATUS_PATH = OUTPUT_DIR / "step_02_status.json"


def write_status(status: str, message: str, values: dict = None):
    """Write the step status JSON file."""
    status_data = {
        "step": 2,
        "name": "Filter Votes",
        "status": status,
        "message": message,
        "values": values or {}
    }
    with open(STATUS_PATH, "w") as f:
        json.dump(status_data, f, indent=2)


def main():
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Step 1: Reset for idempotency
        cursor.execute("UPDATE votes SET is_discretionary = 0;")

        # Step 2a: Include passage, passage-suspension, amendment, cloture, veto-override for both chambers
        cursor.execute("""
            UPDATE votes SET is_discretionary = 1
            WHERE category IN ('passage','passage-suspension','amendment','cloture','veto-override');
        """)

        # Step 2b: Include nominations for Senate ONLY
        cursor.execute("""
            UPDATE votes SET is_discretionary = 1
            WHERE category = 'nomination' AND chamber = 's';
        """)

        conn.commit()

        # Step 3: Query counts for methodology log
        # House counts
        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='h'")
        house_total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='h' AND is_discretionary=0")
        house_excluded = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='h' AND is_discretionary=1")
        house_included = cursor.fetchone()[0]

        house_exclusion_pct = (house_excluded / house_total * 100) if house_total > 0 else 0.0

        # Senate counts
        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='s'")
        senate_total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='s' AND is_discretionary=0")
        senate_excluded = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='s' AND is_discretionary=1")
        senate_included = cursor.fetchone()[0]

        senate_exclusion_pct = (senate_excluded / senate_total * 100) if senate_total > 0 else 0.0

        conn.close()

        # Step 4: Check success conditions
        if house_included < 300:
            error_msg = f"FAILED: house discretionary votes = {house_included}, need >= 300"
            print(error_msg)
            write_status("failed", error_msg)
            sys.exit(1)

        if senate_included < 300:
            error_msg = f"FAILED: senate discretionary votes = {senate_included}, need >= 300"
            print(error_msg)
            write_status("failed", error_msg)
            sys.exit(1)

        # Step 5: Append to methodology log
        log_entry = (
            f"## {datetime.now().isoformat()} — Step 2: Filter Votes\n"
            f"- house_total: {house_total}\n"
            f"- house_excluded: {house_excluded}\n"
            f"- house_included: {house_included}\n"
            f"- house_exclusion_pct: {house_exclusion_pct:.2f}\n"
            f"- senate_total: {senate_total}\n"
            f"- senate_excluded: {senate_excluded}\n"
            f"- senate_included: {senate_included}\n"
            f"- senate_exclusion_pct: {senate_exclusion_pct:.2f}\n\n"
        )

        with open(METHODOLOGY_LOG_PATH, "a") as f:
            f.write(log_entry)

        # Step 6: Write status JSON
        values = {
            "house_total": house_total,
            "house_excluded": house_excluded,
            "house_included": house_included,
            "house_exclusion_pct": round(house_exclusion_pct, 2),
            "senate_total": senate_total,
            "senate_excluded": senate_excluded,
            "senate_included": senate_included,
            "senate_exclusion_pct": round(senate_exclusion_pct, 2)
        }
        write_status("ok", "Votes filtered successfully", values)

        # Step 7: Print success message
        print(f"Step 2: OK — House {house_included} / Senate {senate_included} discretionary votes")

    except Exception as e:
        error_msg = f"Error in step_02_filter_votes: {str(e)}"
        print(error_msg)
        write_status("failed", error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
