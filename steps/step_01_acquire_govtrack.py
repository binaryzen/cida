import sqlite3
import requests
import yaml
import time
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"

YAML_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"
GOVTRACK_API = "https://www.govtrack.us/api/v2"

OUTPUT_DIR.mkdir(exist_ok=True)
DB_PATH.parent.mkdir(exist_ok=True)


def _get(url, params=None, timeout=30, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            time.sleep(0.12)
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def acquire_legislators():
    print("Part A: Acquiring legislators...")
    for attempt in range(3):
        try:
            resp = requests.get(YAML_URL, timeout=30)
            resp.raise_for_status()
            time.sleep(0.1)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

    data = yaml.safe_load(resp.text)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    count = 0

    for record in data:
        if not record.get("terms"):
            continue
        most_recent = max(record["terms"], key=lambda t: t["start"])
        start = most_recent.get("start", "")
        end = most_recent.get("end")
        if start < "2021-01-03":
            continue
        if end and end < "2023-01-03":
            continue

        bioguide_id = record.get("id", {}).get("bioguide")
        if not bioguide_id:
            continue

        name = record.get("name", {})
        display_name = name.get("official_full") or f"{name.get('first','')} {name.get('last','')}".strip()
        party = most_recent.get("party")
        state = most_recent.get("state")
        chamber = "h" if most_recent.get("type") == "rep" else "s"
        fec_ids = record.get("id", {}).get("fec", [])
        fec_candidate_id = fec_ids[0] if fec_ids else None

        cursor.execute(
            "INSERT OR REPLACE INTO legislators "
            "(bioguide_id, display_name, party, state, chamber, fec_candidate_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (bioguide_id, display_name, party, state, chamber, fec_candidate_id),
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"  Loaded {count} legislators")
    return count


def acquire_votes():
    """
    Two-pass API approach (GovTrack bulk file server is gone as of 2025):
      Pass 1: vote?congress=118  → vote metadata (category, question, etc.)
      Pass 2: vote_voter?created=DATETIME → per-legislator positions for each vote
    """
    print("Part B: Acquiring votes via GovTrack API...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Pass 1: collect all vote metadata ---
    # GovTrack API hard-limits offset <= 1000, so use quarterly date ranges
    # (max 319 votes per quarter for 118th Congress — verified).
    DATE_RANGES = [
        ("2023-01-01", "2023-04-01"),
        ("2023-04-01", "2023-07-01"),
        ("2023-07-01", "2023-10-01"),
        ("2023-10-01", "2024-01-01"),
        ("2024-01-01", "2024-04-01"),
        ("2024-04-01", "2024-07-01"),
        ("2024-07-01", "2024-10-01"),
        ("2024-10-01", "2025-01-10"),
    ]
    print("  Pass 1: downloading vote metadata (8 quarterly ranges)...")
    all_votes = []
    for start_dt, end_dt in DATE_RANGES:
        offset = 0
        limit = 300
        while True:
            data = _get(f"{GOVTRACK_API}/vote", params={
                "congress": 118,
                "created__gte": start_dt,
                "created__lt": end_dt,
                "limit": limit,
                "offset": offset,
            })
            batch = data.get("objects", [])
            if not batch:
                break
            all_votes.extend(batch)
            q_total = data.get("meta", {}).get("total_count", 0)
            if len(batch) < limit or offset + limit >= q_total:
                break
            offset += limit
        print(f"    {start_dt}–{end_dt}: {data.get('meta',{}).get('total_count',0)} votes")

    print(f"  Total votes from API: {len(all_votes)}")

    # Parse each vote and insert into DB
    # vote_id format: "{session}/{vote_code}"  e.g. "2023/h1"
    vote_by_created = defaultdict(list)  # created_dt → [vote_meta, ...]
    vote_id_map = {}  # link → vote_id

    skipped = 0
    for v in all_votes:
        link = v.get("link", "")
        created = v.get("created", "")
        # Extract session and vote_code from link
        # link = "https://www.govtrack.us/congress/votes/118-2023/h1"
        try:
            parts = link.rstrip("/").split("/")
            congress_session = parts[-2]  # "118-2023"
            vote_code = parts[-1]         # "h1"
            session = congress_session.split("-")[1]   # "2023"
            vote_id = f"{session}/{vote_code}"
        except Exception:
            skipped += 1
            continue

        chamber_raw = v.get("chamber", "")
        chamber = "h" if chamber_raw == "house" else "s"
        try:
            year = int(session)
        except Exception:
            year = 0

        cursor.execute(
            "INSERT OR IGNORE INTO votes "
            "(vote_id, year, chamber, category, question, result, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                vote_id, year, chamber,
                v.get("category", ""),
                v.get("question", ""),
                v.get("result", ""),
                created,
            ),
        )
        vote_id_map[link] = vote_id

        if created:
            vote_by_created[created].append((vote_id, link, chamber))

    conn.commit()

    # --- Pass 2: per-vote positions ---
    print(f"  Pass 2: downloading voter positions for {len(vote_by_created)} unique timestamps...")

    option_to_pos = {"+": 1, "-": -1}
    total_positions = 0
    processed_votes = 0

    for created_dt, vote_entries in vote_by_created.items():
        # Fetch all voters at this exact timestamp (may span multiple votes if same minute)
        try:
            data = _get(f"{GOVTRACK_API}/vote_voter", params={
                "created": created_dt, "limit": 700
            })
        except Exception as e:
            with open(OUTPUT_DIR / "methodology_log.md", "a") as f:
                f.write(f"Skipped voters for {created_dt}: {e}\n")
            continue

        voters = data.get("objects", [])

        # Group voters by the vote link embedded in each voter record
        grouped = defaultdict(list)
        for voter in voters:
            vote_obj = voter.get("vote", {})
            v_link = vote_obj.get("link", "") if isinstance(vote_obj, dict) else ""
            bioguide = voter.get("person", {}).get("bioguideid", "")
            option_key = voter.get("option", {}).get("key", "")
            position = option_to_pos.get(option_key, 0)
            if bioguide and v_link:
                grouped[v_link].append((bioguide, position))

        for v_link, positions in grouped.items():
            vid = vote_id_map.get(v_link)
            if not vid:
                continue
            cursor.executemany(
                "INSERT OR IGNORE INTO vote_positions (vote_id, bioguide_id, position) VALUES (?, ?, ?)",
                [(vid, bio, pos) for bio, pos in positions],
            )
            total_positions += len(positions)

        processed_votes += len(vote_entries)
        conn.commit()

        if processed_votes % 100 == 0:
            print(f"    processed {processed_votes}/{len(vote_by_created)} timestamps, {total_positions} positions so far")

    conn.close()
    print(f"  Done. {total_positions} vote positions stored.")
    return skipped, total_positions


def get_counts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM legislators")
    n_leg = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='h'")
    n_house = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM votes WHERE chamber='s'")
    n_senate = cursor.fetchone()[0]
    conn.close()
    return n_leg, n_house, n_senate


def main():
    try:
        leg_count = acquire_legislators()
        skipped, total_pos = acquire_votes()
        leg_count, house_votes, senate_votes = get_counts()

        print(f"\nResults:")
        print(f"  Legislators: {leg_count}")
        print(f"  House votes: {house_votes}")
        print(f"  Senate votes: {senate_votes}")
        print(f"  Total positions: {total_pos}")
        print(f"  Vote metadata skipped: {skipped}")

        status = "ok"
        message = "All data acquired successfully"
        if leg_count <= 400:
            status = "failed"
            message = f"Insufficient legislators: {leg_count} (need > 400)"
        elif house_votes <= 800:
            status = "failed"
            message = f"Insufficient house votes: {house_votes} (need > 800)"
        elif senate_votes <= 400:
            status = "failed"
            message = f"Insufficient senate votes: {senate_votes} (need > 400)"

        log_entry = (
            f"## {datetime.now().isoformat()} — Step 1: Acquire GovTrack\n"
            f"- legislators: {leg_count}\n"
            f"- house_votes: {house_votes}\n"
            f"- senate_votes: {senate_votes}\n"
            f"- total_positions: {total_pos}\n"
            f"- status: {status}\n\n"
        )
        with open(OUTPUT_DIR / "methodology_log.md", "a") as f:
            f.write(log_entry)

        status_data = {
            "step": 1, "name": "Acquire GovTrack", "status": status,
            "message": message,
            "values": {
                "legislators": leg_count,
                "house_votes": house_votes,
                "senate_votes": senate_votes,
                "total_positions": total_pos,
            },
        }
        with open(OUTPUT_DIR / "step_01_status.json", "w") as f:
            json.dump(status_data, f, indent=2)

        if status == "failed":
            print(f"\nERROR: {message}")
            sys.exit(1)
        print(f"\nSUCCESS: {message}")

    except Exception as e:
        status_data = {
            "step": 1, "name": "Acquire GovTrack",
            "status": "failed", "message": str(e), "values": {},
        }
        with open(OUTPUT_DIR / "step_01_status.json", "w") as f:
            json.dump(status_data, f, indent=2)
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
