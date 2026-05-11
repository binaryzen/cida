import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import sys

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"


def log_methodology(entry_text):
    """Append to methodology log."""
    log_path = OUTPUT_DIR / "methodology_log.md"
    with open(log_path, "a") as f:
        f.write(entry_text)


def write_status(status, details=None):
    """Write status JSON and exit on failure."""
    status_data = {"status": status}
    if details:
        status_data.update(details)

    with open(OUTPUT_DIR / "step_03_status.json", "w") as f:
        json.dump(status_data, f, indent=2)

    if status == "failed":
        print(json.dumps(status_data, indent=2))
        sys.exit(1)


def build_chamber_matrix(chamber, chamber_name):
    """Build matrix for a single chamber."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Get discretionary votes ordered by date
    cursor.execute(
        """
        SELECT vote_id, category, question, date FROM votes
        WHERE chamber=? AND is_discretionary=1
        ORDER BY date ASC
        """,
        (chamber,)
    )
    votes = cursor.fetchall()
    vote_ids = [row["vote_id"] for row in votes]
    n_votes = len(vote_ids)

    if n_votes == 0:
        conn.close()
        return None, f"No discretionary votes found for chamber {chamber}"

    # Step 2: Get all legislators for this chamber
    cursor.execute(
        """
        SELECT bioguide_id, display_name, party, state FROM legislators
        WHERE chamber=?
        """,
        (chamber,)
    )
    legislators = cursor.fetchall()
    bioguide_ids = [row["bioguide_id"] for row in legislators]
    n_legs = len(bioguide_ids)

    if n_legs == 0:
        conn.close()
        return None, f"No legislators found for chamber {chamber}"

    # Step 3: Get all vote positions for these votes
    # Build parameterized query for vote_id IN (...)
    placeholders = ",".join(["?" for _ in vote_ids])
    cursor.execute(
        f"""
        SELECT vote_id, bioguide_id, position FROM vote_positions
        WHERE vote_id IN ({placeholders})
        """,
        vote_ids
    )
    positions = cursor.fetchall()
    conn.close()

    # Step 4: Build matrix
    vote_id_to_col = {vote_id: i for i, vote_id in enumerate(vote_ids)}
    bioguide_to_row = {bio: i for i, bio in enumerate(bioguide_ids)}

    # position is already stored as integer (1, -1, 0) in the DB
    matrix = np.zeros((n_legs, n_votes), dtype=np.int8)
    for pos_row in positions:
        vote_id = pos_row["vote_id"]
        bioguide_id = pos_row["bioguide_id"]
        position = pos_row["position"]

        if vote_id in vote_id_to_col and bioguide_id in bioguide_to_row:
            col = vote_id_to_col[vote_id]
            row = bioguide_to_row[bioguide_id]
            matrix[row, col] = position

    # Step 5: Compute coverage and exclude low-coverage legislators
    coverage = np.sum(matrix != 0, axis=1) / n_votes
    included_mask = coverage >= 0.50

    excluded_legislators = []
    for i, (bio, leg_row) in enumerate(zip(bioguide_ids, legislators)):
        if not included_mask[i]:
            excluded_legislators.append({
                "bioguide_id": bio,
                "display_name": leg_row["display_name"],
                "coverage": float(coverage[i])
            })

    # Step 6: Filter matrix and re-index
    matrix_filtered = matrix[included_mask, :]
    included_bioguide_ids = [bio for bio, inc in zip(bioguide_ids, included_mask) if inc]
    included_legislators = [leg for leg, inc in zip(legislators, included_mask) if inc]

    bioguide_to_row_filtered = {bio: i for i, bio in enumerate(included_bioguide_ids)}
    n_legs_filtered = len(included_bioguide_ids)

    # Step 7: Verify no NaN
    try:
        assert not np.isnan(matrix_filtered.astype(float)).any()
    except AssertionError:
        return None, f"NaN values found in {chamber_name} matrix"

    # Verify shape is sane
    if matrix_filtered.shape[0] == 0 or matrix_filtered.shape[1] == 0:
        return None, f"Empty matrix for {chamber_name} after filtering"

    # Step 8: Save outputs
    np.save(OUTPUT_DIR / f"matrix_{chamber_name}.npy", matrix_filtered)

    # Save legislators CSV
    legs_df = pd.DataFrame([
        {
            "bioguide_id": leg["bioguide_id"],
            "display_name": leg["display_name"],
            "party": leg["party"],
            "state": leg["state"],
            "row_idx": bioguide_to_row_filtered[leg["bioguide_id"]]
        }
        for leg in included_legislators
    ])
    legs_df.to_csv(OUTPUT_DIR / f"legislators_{chamber_name}.csv", index=False)

    # Save votes CSV
    votes_df = pd.DataFrame([
        {
            "vote_id": vote["vote_id"],
            "category": vote["category"],
            "question": vote["question"],
            "date": vote["date"],
            "col_idx": vote_id_to_col[vote["vote_id"]]
        }
        for vote in votes
    ])
    votes_df.to_csv(OUTPUT_DIR / f"votes_{chamber_name}.csv", index=False)

    return {
        "n_legs": n_legs_filtered,
        "n_votes": n_votes,
        "n_excluded": len(excluded_legislators),
        "matrix_shape": matrix_filtered.shape,
        "excluded": excluded_legislators
    }, None


def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # Process each chamber
    for chamber, chamber_name in [("h", "house"), ("s", "senate")]:
        result, error = build_chamber_matrix(chamber, chamber_name)

        if error:
            write_status("failed", {"error": error, "chamber": chamber_name})

        results[chamber_name] = result

    # Check kickback conditions
    house_result = results["house"]
    senate_result = results["senate"]

    if house_result["n_legs"] < 100 or house_result["n_votes"] < 300:
        write_status("failed", {
            "error": "House matrix dimensions below threshold",
            "house_n_legislators": house_result["n_legs"],
            "house_n_votes": house_result["n_votes"]
        })

    if senate_result["n_legs"] < 40 or senate_result["n_votes"] < 300:
        write_status("failed", {
            "error": "Senate matrix dimensions below threshold",
            "senate_n_legislators": senate_result["n_legs"],
            "senate_n_votes": senate_result["n_votes"]
        })

    # Build methodology log entry
    log_entry = f"""## {datetime.now().isoformat()} — Step 3: Build Matrix
- house_n_legislators: {house_result['n_legs']}
- house_n_votes: {house_result['n_votes']}
- house_excluded_legislators: {house_result['n_excluded']}
- house_matrix_shape: {house_result['matrix_shape'][0]}x{house_result['matrix_shape'][1]}
- senate_n_legislators: {senate_result['n_legs']}
- senate_n_votes: {senate_result['n_votes']}
- senate_excluded_legislators: {senate_result['n_excluded']}
- senate_matrix_shape: {senate_result['matrix_shape'][0]}x{senate_result['matrix_shape'][1]}

"""

    log_methodology(log_entry)

    # Write status
    status_data = {
        "status": "ok",
        "house_shape": f"{house_result['matrix_shape'][0]}x{house_result['matrix_shape'][1]}",
        "senate_shape": f"{senate_result['matrix_shape'][0]}x{senate_result['matrix_shape'][1]}"
    }
    write_status("ok", status_data)

    # Print success message
    print(f"Step 3: OK — House matrix {status_data['house_shape']}, Senate matrix {status_data['senate_shape']}")


if __name__ == "__main__":
    main()
