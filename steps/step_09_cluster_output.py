#!/usr/bin/env python3
"""
Step 09: Cluster Legislators in PCA Space
Performs HDBSCAN or K-Means clustering on PCA components and produces visualizations.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.subplots as sp
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"
DB_PATH = ROOT / "data" / "votes.db"


def log_methodology(message: str):
    """Append message to methodology_log.md"""
    log_path = OUTPUT_DIR / "methodology_log.md"
    timestamp = datetime.now().isoformat()
    with open(log_path, "a") as f:
        f.write(f"\n**Step 09 [{timestamp}]**: {message}")


def write_status_failure(error_msg: str):
    """Write failure status and exit"""
    status = {
        "step": 9,
        "status": "failed",
        "error": error_msg,
        "timestamp": datetime.now().isoformat(),
    }
    with open(OUTPUT_DIR / "step_09_status.json", "w") as f:
        json.dump(status, f, indent=2)
    print(f"ERROR: {error_msg}", file=sys.stderr)
    sys.exit(1)


def cluster_chamber(chamber_name: str, scores_df: pd.DataFrame, pc_cols: list) -> tuple:
    """
    Cluster a chamber's legislators using HDBSCAN or K-Means.
    Returns: (labels, method, silhouette_score)
    """
    X = scores_df[pc_cols].values
    n_legs = len(X)

    # Try HDBSCAN first
    min_cluster_size = max(5, n_legs // 20)
    hdb = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=3)
    hdb_labels = hdb.fit_predict(X)
    n_meaningful = len(set(hdb_labels) - {-1})

    if n_meaningful >= 2:
        labels = hdb_labels
        method = f"HDBSCAN(min_cluster_size={min_cluster_size})"
        non_noise_mask = labels != -1
        if non_noise_mask.sum() > 1:
            sil = silhouette_score(X[non_noise_mask], labels[non_noise_mask])
        else:
            sil = 0.0
    else:
        # K-means fallback
        best_k, best_sil, best_labels = 2, -1.0, None
        for k in range(2, 9):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            lbl = km.fit_predict(X)
            s = silhouette_score(X, lbl)
            if s > best_sil:
                best_k, best_sil, best_labels = k, s, lbl
        labels = best_labels
        method = f"KMeans(k={best_k})"
        sil = best_sil

        if sil < 0.3:
            msg = f"{chamber_name} silhouette = {sil:.3f} < 0.3 (k-means fallback)"
            print(f"WARNING: {msg}")
            log_methodology(msg)

    log_methodology(f"{chamber_name}: {method}, silhouette={sil:.3f}")
    return labels, method, sil


def get_cluster_summary(
    chamber_name: str,
    scores_df: pd.DataFrame,
    labels: np.ndarray,
    X: np.ndarray,
) -> list:
    """
    Compute summary statistics for each cluster.
    Returns list of summary dictionaries.
    """
    summaries = []

    # Load interest correlation data if available
    dominant_industry_map = {}
    dominant_r_map = {}
    corr_path = OUTPUT_DIR / "interest_correlation_table.csv"
    if corr_path.exists():
        corr_df = pd.read_csv(corr_path)
        chamber_corr = corr_df[corr_df["chamber"] == chamber_name]
        chamber_corr = chamber_corr.dropna(subset=["pearson_r"])
        if not chamber_corr.empty:
            max_row = chamber_corr.loc[chamber_corr["pearson_r"].abs().idxmax()]
            dominant_industry_map[chamber_name] = max_row["industry_type"]
            dominant_r_map[chamber_name] = round(max_row["pearson_r"], 3)

    for cluster_id in sorted(set(labels)):
        # Skip HDBSCAN noise points
        if cluster_id == -1:
            continue

        cluster_mask = labels == cluster_id
        cluster_data = scores_df[cluster_mask]

        n_total = cluster_mask.sum()
        n_dem = (cluster_data["party"] == "Democrat").sum()
        n_rep = (cluster_data["party"] == "Republican").sum()
        n_ind = n_total - n_dem - n_rep

        dominant = "Democrat" if n_dem > n_rep else "Republican"
        pct_minority = (n_total - max(n_dem, n_rep)) / n_total if n_total > 0 else 0

        # Find 3 legislators closest to cluster centroid
        centroid = X[cluster_mask].mean(axis=0)
        dists = np.linalg.norm(X[cluster_mask] - centroid, axis=1)
        top3_idx = np.argsort(dists)[:3]
        reps = cluster_data.iloc[top3_idx]["display_name"].tolist()

        summary = {
            "chamber": chamber_name,
            "cluster_id": int(cluster_id),
            "n_legislators": int(n_total),
            "n_democrat": int(n_dem),
            "n_republican": int(n_rep),
            "n_independent": int(n_ind),
            "dominant_party": dominant,
            "pct_minority_party": round(pct_minority, 3),
            "dominant_industry": dominant_industry_map.get(chamber_name, "N/A"),
            "dominant_industry_r": dominant_r_map.get(chamber_name, None),
            "representative_legislators": "; ".join(reps),
        }
        summaries.append(summary)

    return summaries


def main():
    try:
        # Load component labels
        labels_path = OUTPUT_DIR / "component_labels.json"
        if not labels_path.exists():
            write_status_failure(f"component_labels.json not found at {labels_path}")

        with open(labels_path) as f:
            labels_json = json.load(f)

        all_summaries = []
        chamber_results = {}

        for chamber_name in ["house", "senate"]:
            # Load scores
            scores_path = OUTPUT_DIR / f"scores_{chamber_name}.csv"
            if not scores_path.exists():
                write_status_failure(f"scores_{chamber_name}.csv not found")

            scores_df = pd.read_csv(scores_path)

            # Get PCA column names
            if chamber_name not in labels_json:
                write_status_failure(f"Chamber {chamber_name} not in component_labels.json")

            pc_cols = [f"pc{j}" for j in range(len(labels_json[chamber_name]))]

            # Validate columns exist
            missing = set(pc_cols) - set(scores_df.columns)
            if missing:
                write_status_failure(f"Missing columns for {chamber_name}: {missing}")

            X = scores_df[pc_cols].values
            n_legs = len(X)

            # Cluster
            labels, method, sil = cluster_chamber(chamber_name, scores_df, pc_cols)

            # Add cluster_id to dataframe
            scores_df = scores_df.copy()
            scores_df["cluster_id"] = labels

            # Get summary statistics
            summaries = get_cluster_summary(chamber_name, scores_df, labels, X)
            all_summaries.extend(summaries)

            # Create PCA scatter plot
            fig = px.scatter(
                scores_df,
                x="pc0",
                y="pc1",
                color=scores_df["cluster_id"].astype(str),
                hover_name="display_name",
                hover_data=["party", "state"],
                title=f"Clusters — {chamber_name.title()} (method: {method}, sil: {sil:.3f})",
                symbol="party",
                labels={"pc0": labels_json[chamber_name]["0"], "pc1": labels_json[chamber_name]["1"]},
            )
            fig.update_layout(height=600, width=900)

            pca_path = OUTPUT_DIR / f"pca_space_{chamber_name}.html"
            fig.write_html(str(pca_path))

            # Store for combined visualization
            scores_df["chamber"] = chamber_name
            chamber_results[chamber_name] = (scores_df, method, sil)

        # Save cluster summary table
        summary_df = pd.DataFrame(all_summaries)
        summary_path = OUTPUT_DIR / "cluster_summary_table.csv"
        summary_df.to_csv(summary_path, index=False)

        # Create combined clusters_final.html
        combined_dfs = []
        for chamber_name in ["house", "senate"]:
            scores_df, _, _ = chamber_results[chamber_name]
            combined_dfs.append(scores_df)

        combined_df = pd.concat(combined_dfs, ignore_index=True)
        combined_df["cluster_id_str"] = combined_df["cluster_id"].astype(str)

        fig_combined = px.scatter(
            combined_df,
            x="pc0",
            y="pc1",
            color="cluster_id_str",
            symbol="chamber",
            hover_name="display_name",
            hover_data=["party", "state", "chamber"],
            title="CIDA Final Clusters — House and Senate",
            labels={"cluster_id_str": "Cluster", "chamber": "Chamber"},
        )
        fig_combined.update_layout(height=700, width=1000)
        fig_combined.write_html(str(OUTPUT_DIR / "clusters_final.html"))

        # Check quality and cross-party membership
        has_cross_party = any(
            row["pct_minority_party"] >= 0.10 for row in all_summaries
        )
        if not has_cross_party:
            msg = "No cluster has >= 10% minority-party membership"
            print(f"WARNING: {msg}")
            log_methodology(msg)

        # Write final status
        status = {
            "step": 9,
            "status": "ok",
            "chambers": {},
            "timestamp": datetime.now().isoformat(),
        }

        for chamber_name in ["house", "senate"]:
            _, method, sil = chamber_results[chamber_name]
            status["chambers"][chamber_name] = {
                "method": method,
                "silhouette": round(sil, 3),
                "n_clusters": len(
                    [s for s in all_summaries if s["chamber"] == chamber_name]
                ),
            }

        with open(OUTPUT_DIR / "step_09_status.json", "w") as f:
            json.dump(status, f, indent=2)

        print("Step 9: OK")

    except Exception as e:
        write_status_failure(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
