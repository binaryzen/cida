"""
Step 8: Interest Overlay — Join PCA component scores with FEC disbursement data.

Computes Pearson correlations between component scores and industry disbursement
patterns per legislator, producing correlation tables and heatmaps.
"""

import sqlite3
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime
from scipy.stats import pearsonr
import plotly.express as px

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"


def load_component_labels():
    """Load component labels from component_labels.json."""
    labels_path = OUTPUT_DIR / "component_labels.json"
    if not labels_path.exists():
        print(f"ERROR: {labels_path} not found")
        sys.exit(1)
    with open(labels_path, 'r') as f:
        return json.load(f)


def fetch_fec_disbursements(chamber_code):
    """
    Aggregate FEC Schedule A receipts per legislator per industry (entity_type_desc).
    chamber_code: 'h' for house, 's' for senate
    """
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT fr.bioguide_id,
           fr.industry,
           SUM(fr.total_amount) AS total_amount
    FROM fec_receipts fr
    JOIN legislators l ON fr.bioguide_id = l.bioguide_id
    WHERE l.chamber = ?
    GROUP BY fr.bioguide_id, fr.industry
    """
    df = pd.read_sql_query(query, conn, params=(chamber_code,))
    conn.close()
    return df


def log_message(message):
    """Append message to methodology log."""
    log_path = OUTPUT_DIR / "methodology_log.md"
    timestamp = datetime.now().isoformat()
    with open(log_path, 'a') as f:
        f.write(f"\n**{timestamp}** — {message}")


def process_chamber(chamber_name, chamber_code, labels_json):
    """
    Process one chamber: compute correlations between PCA scores and FEC disbursements.
    Returns list of correlation records.
    """
    # Load scores
    scores_path = OUTPUT_DIR / f"scores_{chamber_name}.csv"
    if not scores_path.exists():
        print(f"WARNING: {scores_path} not found, skipping {chamber_name}")
        return []

    scores_df = pd.read_csv(scores_path)
    if 'bioguide_id' not in scores_df.columns:
        print(f"WARNING: bioguide_id not in scores_{chamber_name}.csv, skipping")
        return []

    # Determine component columns
    labels = labels_json.get(chamber_name, {})
    pc_cols = [f"pc{j}" for j in range(len(labels))]

    # Fetch FEC disbursements
    fec_df = fetch_fec_disbursements(chamber_code)
    if fec_df.empty:
        print(f"WARNING: No FEC disbursements for {chamber_name}")
        return []

    # Pivot to wide format
    industry_df = fec_df.pivot(
        index='bioguide_id',
        columns='industry',
        values='total_amount'
    ).fillna(0)

    # Apply log transformation
    industry_df = np.log1p(industry_df)

    # Merge scores with industry data
    merged = scores_df.merge(industry_df.reset_index(), on='bioguide_id', how='inner')

    if len(merged) < 10:
        print(f"WARNING: Only {len(merged)} legislators with both scores and FEC data for {chamber_name}")
        return []

    print(f"Processing {chamber_name}: {len(merged)} legislators")

    # Compute correlations
    correlations = []
    for j, pc_col in enumerate(pc_cols):
        for industry_col in industry_df.columns:
            x = merged[pc_col].values
            y = merged[industry_col].values

            if len(x) < 5:
                continue

            r, p = pearsonr(x, y)
            import math
            if math.isnan(r):
                continue
            correlations.append({
                'chamber': chamber_name,
                'component_idx': j,
                'component_label': labels.get(str(j), f'PC{j}'),
                'industry_type': industry_col,
                'pearson_r': r,
                'p_value': p
            })

    # Create heatmap: top 10 industries by |r| per component
    if correlations:
        corr_df = pd.DataFrame(correlations)

        # For each component, get top 10 industries by |r|
        heatmap_data = []
        for j in pc_cols:
            comp_corrs = corr_df[corr_df['component_idx'] == int(j[2:])].copy()
            if not comp_corrs.empty:
                comp_corrs['abs_r'] = comp_corrs['pearson_r'].abs()
                top_industries = comp_corrs.nlargest(10, 'abs_r')
                heatmap_data.append(top_industries)

        if heatmap_data:
            heatmap_df = pd.concat(heatmap_data, ignore_index=True)
            pivot_data = heatmap_df.pivot(
                index='industry_type',
                columns='component_idx',
                values='pearson_r'
            )

            if not pivot_data.empty:
                fig = px.imshow(
                    pivot_data,
                    title=f"PCA Component — Industry Disbursement Correlations ({chamber_name.capitalize()})",
                    labels=dict(x="Component Index", y="Industry Type", color="Pearson r"),
                    color_continuous_scale="RdBu",
                    origin="lower",
                    aspect="auto"
                )
                heatmap_path = OUTPUT_DIR / f"interest_correlation_heatmap_{chamber_name}.html"
                fig.write_html(heatmap_path)
                print(f"Saved heatmap: {heatmap_path}")

    # Log top 5 positive and negative correlations per component
    if correlations:
        corr_df = pd.DataFrame(correlations)
        for j in range(len(labels)):
            comp_corrs = corr_df[corr_df['component_idx'] == j].sort_values('pearson_r')

            # Top 5 negative
            if len(comp_corrs) > 0:
                top_neg = comp_corrs.head(5)
                for _, row in top_neg.iterrows():
                    log_message(
                        f"{chamber_name.upper()} PC{row['component_idx']} "
                        f"({row['component_label']}) — {row['industry_type']}: r={row['pearson_r']:.3f}, p={row['p_value']:.4f}"
                    )

            # Top 5 positive
            if len(comp_corrs) > 0:
                top_pos = comp_corrs.tail(5)
                for _, row in top_pos.iterrows():
                    log_message(
                        f"{chamber_name.upper()} PC{row['component_idx']} "
                        f"({row['component_label']}) — {row['industry_type']}: r={row['pearson_r']:.3f}, p={row['p_value']:.4f}"
                    )

    return correlations


def main():
    """Main entry point."""
    try:
        print("Step 8: Interest Overlay")

        # Load component labels
        labels_json = load_component_labels()
        print(f"Loaded component labels: {list(labels_json.keys())}")

        # Process both chambers
        all_correlations = []
        for chamber_name, chamber_code in [('house', 'h'), ('senate', 's')]:
            correlations = process_chamber(chamber_name, chamber_code, labels_json)
            all_correlations.extend(correlations)

        if not all_correlations:
            print("WARNING: No correlations computed")
            log_message("Step 8: No correlations computed — insufficient data")
            status = {"n_correlations": 0, "max_abs_r": 0.0}
        else:
            # Save correlation table
            corr_table = pd.DataFrame(all_correlations)
            output_path = OUTPUT_DIR / "interest_correlation_table.csv"
            corr_table.to_csv(output_path, index=False)
            print(f"Saved correlation table: {output_path}")

            # Check for weak signal
            max_abs_r = corr_table['pearson_r'].abs().max()
            n_correlations = len(corr_table)

            if max_abs_r < 0.15:
                msg = (
                    "WARNING: all correlations < 0.15 — weak or no industry signal found (valid finding)"
                )
                print(msg)
                log_message(msg)

            status = {"n_correlations": n_correlations, "max_abs_r": float(max_abs_r)}

        # Write status
        status_path = OUTPUT_DIR / "step_08_status.json"
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)
        print(f"Saved status: {status_path}")

        log_message("Step 8: OK")
        print("Step 8: OK")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        status = {"failed": str(e)}
        status_path = OUTPUT_DIR / "step_08_status.json"
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)
        log_message(f"Step 8: FAILED — {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
