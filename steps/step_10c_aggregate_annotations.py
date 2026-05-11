"""
Step 10c: Aggregate Haiku annotation results into SQLite.
- Reads output/annotation_results/batch_XX_result.json
- Inserts into vote_facets table
- Builds legislator_facet_scores table (sum of facet scores across votes)
- Correlates facet scores with PCA component scores
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"
RESULTS_DIR = OUTPUT_DIR / "annotation_results"

FACETS = [
    "nato_alliance", "ukraine_aid", "israel_aid", "foreign_aid",
    "china_competition", "executive_power", "surveillance_power",
    "war_powers", "defense_spending", "federal_spending",
    "climate_energy", "social_safety_net", "law_enforcement",
    "immigration_enforcement", "antisemitism_civil_rights", "judicial_appointments",
]


def load_results(conn):
    result_files = sorted(RESULTS_DIR.glob("batch_*_result.json"))
    if not result_files:
        print("ERROR: No result files found in output/annotation_results/")
        return 0

    cursor = conn.cursor()
    total = 0
    errors = 0

    for path in result_files:
        try:
            with open(path) as f:
                records = json.load(f)
        except Exception as e:
            print(f"  Failed to parse {path.name}: {e}")
            errors += 1
            continue

        for rec in records:
            vote_id = rec.get("vote_id")
            facets = rec.get("facets", {})
            if not vote_id or not facets:
                continue
            for facet, score in facets.items():
                if facet not in FACETS:
                    continue
                try:
                    score = int(score)
                    if score not in (-1, 0, 1):
                        score = 0
                except (ValueError, TypeError):
                    score = 0
                cursor.execute(
                    "INSERT OR REPLACE INTO vote_facets (vote_id, facet, score) VALUES (?,?,?)",
                    (vote_id, facet, score),
                )
            total += 1

        conn.commit()

    print(f"  Loaded {total} vote annotations from {len(result_files)} files ({errors} parse errors)")
    return total


def build_legislator_profiles(conn):
    """Sum facet scores across all votes each legislator participated in."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legislator_facet_scores (
            bioguide_id TEXT,
            chamber TEXT,
            facet TEXT,
            score_sum INTEGER,
            vote_count INTEGER,
            score_mean REAL,
            PRIMARY KEY (bioguide_id, facet)
        )
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO legislator_facet_scores
            (bioguide_id, chamber, facet, score_sum, vote_count, score_mean)
        SELECT
            vp.bioguide_id,
            l.chamber,
            vf.facet,
            SUM(vp.position * vf.score) as score_sum,
            COUNT(*) as vote_count,
            CAST(SUM(vp.position * vf.score) AS REAL) / COUNT(*) as score_mean
        FROM vote_positions vp
        JOIN vote_facets vf ON vp.vote_id = vf.vote_id
        JOIN votes v ON vp.vote_id = v.vote_id AND v.is_discretionary = 1
        JOIN legislators l ON vp.bioguide_id = l.bioguide_id
        WHERE vf.score != 0
        GROUP BY vp.bioguide_id, l.chamber, vf.facet
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(DISTINCT bioguide_id) FROM legislator_facet_scores")
    n = cursor.fetchone()[0]
    print(f"  Built facet profiles for {n} legislators")
    return n


def correlate_with_pca(conn):
    """Correlate legislator facet scores with PCA component scores."""
    rows = []

    for chamber_name in ["house", "senate"]:
        scores_path = OUTPUT_DIR / f"scores_{chamber_name}.csv"
        if not scores_path.exists():
            continue

        scores_df = pd.read_csv(scores_path)
        labels_path = OUTPUT_DIR / "component_labels.json"
        with open(labels_path) as f:
            labels = json.load(f)[chamber_name]

        pc_cols = [f"pc{j}" for j in range(len(labels))]

        facet_df = pd.read_sql("""
            SELECT bioguide_id, facet, score_mean
            FROM legislator_facet_scores
            WHERE chamber = ?
        """, conn, params=(chamber_name[0],))

        if facet_df.empty:
            continue

        facet_wide = facet_df.pivot(index="bioguide_id", columns="facet", values="score_mean").fillna(0)
        merged = scores_df.merge(facet_wide, on="bioguide_id", how="inner")

        for pc_col in pc_cols:
            comp_idx = int(pc_col[2:])
            comp_label = labels.get(str(comp_idx), pc_col)
            if pc_col not in merged.columns:
                continue
            for facet in FACETS:
                if facet not in merged.columns:
                    continue
                r = np.corrcoef(merged[pc_col].values, merged[facet].values)[0, 1]
                if abs(r) > 0.10:
                    rows.append({
                        "chamber": chamber_name,
                        "component": comp_label,
                        "component_idx": comp_idx,
                        "facet": facet,
                        "pearson_r": round(r, 4),
                    })

    if rows:
        corr_df = pd.DataFrame(rows).sort_values("pearson_r", key=abs, ascending=False)
        corr_df.to_csv(OUTPUT_DIR / "facet_pca_correlations.csv", index=False)
        print(f"  Saved {len(rows)} facet-PCA correlations (|r| > 0.10) to facet_pca_correlations.csv")
    return rows


def main():
    print("Step 10c: Aggregate annotations")
    conn = sqlite3.connect(DB_PATH)

    print("Loading annotation results...")
    total = load_results(conn)
    if total == 0:
        print("No annotations to aggregate.")
        conn.close()
        return

    print("Building legislator facet profiles...")
    build_legislator_profiles(conn)

    print("Correlating with PCA components...")
    rows = correlate_with_pca(conn)

    with open(OUTPUT_DIR / "methodology_log.md", "a") as f:
        f.write(f"\n## {datetime.now().isoformat()} — Step 10: Vote Annotation\n")
        f.write(f"- annotated_votes: {total}\n")
        f.write(f"- facets: {len(FACETS)}\n")
        f.write(f"- facet_pca_correlations_above_0.10: {len(rows)}\n\n")

    conn.close()
    print("Step 10c: OK")


if __name__ == "__main__":
    main()
