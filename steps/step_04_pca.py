import numpy as np
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"


def parallel_analysis(X_scaled, n_iter=1000, percentile=95, random_state=42):
    """Perform parallel analysis to determine number of significant components."""
    n_samples, n_features = X_scaled.shape
    n_components = min(n_samples - 1, n_features)
    rng = np.random.RandomState(random_state)
    rand_eigenvalues = np.zeros((n_iter, n_components))
    for i in range(n_iter):
        R = rng.randn(n_samples, n_features)
        R = (R - R.mean(axis=0)) / (R.std(axis=0) + 1e-10)
        pca_r = PCA(n_components=n_components)
        pca_r.fit(R)
        rand_eigenvalues[i, :len(pca_r.explained_variance_)] = pca_r.explained_variance_
    return np.percentile(rand_eigenvalues, percentile, axis=0)


def process_chamber(chamber_name):
    """Process PCA for a single chamber."""
    print(f"\n{'='*60}")
    print(f"Processing {chamber_name.upper()}")
    print(f"{'='*60}")

    # Load data
    print(f"Loading data for {chamber_name}...")
    X = np.load(OUTPUT_DIR / f"matrix_{chamber_name}.npy").astype(float)
    leg_df = pd.read_csv(OUTPUT_DIR / f"legislators_{chamber_name}.csv")
    votes_df = pd.read_csv(OUTPUT_DIR / f"votes_{chamber_name}.csv")

    # Scale
    print(f"Scaling data...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit PCA
    print(f"Fitting PCA...")
    pca = PCA(random_state=42)
    pca.fit(X_scaled)
    eigenvalues = pca.explained_variance_

    # Run parallel analysis
    print(f"Running parallel analysis for {chamber_name} (1000 iterations)...")
    thresholds = parallel_analysis(X_scaled)

    # Determine retained components
    retained_indices = [i for i in range(len(thresholds)) if eigenvalues[i] > thresholds[i]]
    n_retained = len(retained_indices)

    print(f"Retained {n_retained} components")

    # KICKBACK if too few components
    if n_retained < 2:
        kickback_data = {
            "Condition": "retained_components >= 2",
            "Observed": n_retained,
            "Chamber": chamber_name
        }
        with open(OUTPUT_DIR / "step_04_kickback.md", "w") as f:
            f.write(f"# PCA Failure: Insufficient Components\n\n")
            f.write(f"Chamber: {chamber_name}\n\n")
            f.write(f"Requirement: At least 2 retained components (parallel analysis)\n\n")
            f.write(f"Observed: {n_retained} component(s)\n\n")
            f.write(f"Data:\n```json\n{json.dumps(kickback_data, indent=2)}\n```\n")
        with open(OUTPUT_DIR / "step_04_status.json", "w") as f:
            json.dump({"status": "kickback", "reason": "insufficient_retained_components"}, f, indent=2)
        print(f"KICKBACK: insufficient retained components ({n_retained} < 2)")
        sys.exit(1)

    # PC1 party sanity check
    print(f"Performing PC1 party sanity check...")
    scores_all = pca.transform(X_scaled)
    pc1_scores = scores_all[:, 0]
    party_map = {'Democrat': 1.0, 'Republican': 0.0}
    party_binary = leg_df['party'].map(party_map).fillna(0.5).values
    corr_matrix = np.corrcoef(pc1_scores, party_binary)
    r = corr_matrix[0, 1]
    r2 = r ** 2

    print(f"PC1-party R²: {r2:.4f}")

    # KICKBACK if r2 too low
    if r2 < 0.70:
        kickback_data = {
            "Condition": "pc1_party_r2 >= 0.70",
            "Observed": round(r2, 4),
            "Chamber": chamber_name
        }
        with open(OUTPUT_DIR / "step_04_kickback.md", "w") as f:
            f.write(f"# PCA Failure: Weak PC1-Party Correlation\n\n")
            f.write(f"Chamber: {chamber_name}\n\n")
            f.write(f"Requirement: PC1 party-correlation R² >= 0.70\n\n")
            f.write(f"Observed: R² = {r2:.4f}\n\n")
            f.write(f"Data:\n```json\n{json.dumps(kickback_data, indent=2)}\n```\n")
        with open(OUTPUT_DIR / "step_04_status.json", "w") as f:
            json.dump({"status": "kickback", "reason": "weak_pc1_party_correlation"}, f, indent=2)
        print(f"KICKBACK: weak PC1-party correlation (R²={r2:.4f} < 0.70)")
        sys.exit(1)

    # Warn if r2 too high
    if r2 > 0.95:
        print(f"WARNING: {chamber_name} PC1 r²={r2:.3f} > 0.95 — first component is almost entirely party")

    # Create scree plot
    print(f"Creating scree plot...")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(eigenvalues))),
        y=eigenvalues,
        mode='lines+markers',
        name='Actual',
        line=dict(color='blue'),
        marker=dict(size=4)
    ))
    fig.add_trace(go.Scatter(
        x=list(range(len(thresholds))),
        y=thresholds,
        mode='lines+markers',
        name='Parallel Analysis (95th pct)',
        line=dict(color='red'),
        marker=dict(size=4)
    ))
    # Add vertical line at last retained component
    if len(retained_indices) > 0:
        last_retained = max(retained_indices)
        fig.add_vline(x=last_retained, line_dash="dash", line_color="green",
                      annotation_text=f"Retained: {n_retained}")
    fig.update_layout(
        title=f"Eigenvalue Spectrum — {chamber_name.title()}",
        xaxis_title="Component",
        yaxis_title="Eigenvalue",
        hovermode='x unified',
        template='plotly_white'
    )
    fig.write_html(OUTPUT_DIR / f"eigenvalue_spectrum_{chamber_name}.html")
    print(f"Saved: eigenvalue_spectrum_{chamber_name}.html")

    # Component loadings
    print(f"Computing component loadings...")
    loadings_list = []
    for comp_idx in retained_indices:
        loading_vec = pca.components_[comp_idx]
        votes_with_loading = votes_df.copy()
        votes_with_loading['loading'] = loading_vec

        # Top 20 positive
        top20_pos = votes_with_loading.nlargest(20, 'loading')
        top20_pos['direction'] = 'pos'
        top20_pos['component_idx'] = comp_idx

        # Top 20 negative
        top20_neg = votes_with_loading.nsmallest(20, 'loading')
        top20_neg['direction'] = 'neg'
        top20_neg['component_idx'] = comp_idx

        loadings_list.append(top20_pos)
        loadings_list.append(top20_neg)

    loadings_df = pd.concat(loadings_list, ignore_index=True)
    # Select and reorder columns
    if 'question' in loadings_df.columns and 'category' in loadings_df.columns and 'date' in loadings_df.columns:
        loadings_df = loadings_df[['component_idx', 'direction', 'vote_id', 'loading', 'question', 'category', 'date']]
    else:
        # Fallback if columns differ
        cols = ['component_idx', 'direction', 'vote_id', 'loading']
        cols.extend([c for c in loadings_df.columns if c not in cols])
        loadings_df = loadings_df[cols[:7]]  # Keep first 7 columns

    loadings_df.to_csv(OUTPUT_DIR / f"loadings_{chamber_name}.csv", index=False)
    print(f"Saved: loadings_{chamber_name}.csv")

    # Component scores
    print(f"Computing component scores...")
    retained_scores = scores_all[:, retained_indices]
    scores_df = leg_df[['bioguide_id', 'display_name', 'party', 'state']].copy()
    for j, comp_idx in enumerate(retained_indices):
        scores_df[f'pc{j}'] = retained_scores[:, j]

    scores_df.to_csv(OUTPUT_DIR / f"scores_{chamber_name}.csv", index=False)
    print(f"Saved: scores_{chamber_name}.csv")

    # PCA space plot
    print(f"Creating PCA space plot...")
    if n_retained >= 2:
        plot_df = scores_df.copy()
        plot_df['pc0'] = retained_scores[:, 0]
        plot_df['pc1'] = retained_scores[:, 1]

        fig = px.scatter(
            plot_df,
            x='pc0',
            y='pc1',
            color='party',
            hover_data=['display_name', 'state'],
            title=f"PCA Space — {chamber_name.title()}",
            labels={'pc0': 'PC0', 'pc1': 'PC1'},
            template='plotly_white'
        )
        fig.write_html(OUTPUT_DIR / f"pca_space_{chamber_name}.html")
        print(f"Saved: pca_space_{chamber_name}.html")

    # Log to methodology log
    log_entry = (
        f"## {datetime.now().isoformat()} — Step 4: PCA ({chamber_name})\n"
        f"- {chamber_name}_retained_components: {n_retained}\n"
        f"- {chamber_name}_pc1_party_r2: {round(r2, 4)}\n"
        f"- {chamber_name}_eigenvalue_1: {round(eigenvalues[0], 4)}\n"
        f"- {chamber_name}_retained_indices: {retained_indices}\n\n"
    )
    with open(OUTPUT_DIR / "methodology_log.md", "a") as f:
        f.write(log_entry)

    return n_retained, r2


def main():
    """Main entry point."""
    print("Step 4: PCA with Parallel Analysis")

    results = {}

    # Process both chambers
    for chamber_name in ['house', 'senate']:
        n_retained, r2 = process_chamber(chamber_name)
        results[chamber_name] = {'n_retained': n_retained, 'r2': r2}

    # Write component labels
    print(f"\nWriting component labels...")
    labels = {
        "warning": "No human interpretation applied — all labels are automated placeholders",
        "automated": True,
        "house": {str(j): f"uninterpreted-{j}" for j in range(results['house']['n_retained'])},
        "senate": {str(j): f"uninterpreted-{j}" for j in range(results['senate']['n_retained'])}
    }
    with open(OUTPUT_DIR / "component_labels.json", "w") as f:
        json.dump(labels, f, indent=2)
    print(f"Saved: component_labels.json")

    # Write status
    status = {
        "status": "ok",
        "house_retained": results['house']['n_retained'],
        "senate_retained": results['senate']['n_retained'],
        "house_pc1_r2": round(results['house']['r2'], 4),
        "senate_pc1_r2": round(results['senate']['r2'], 4)
    }
    with open(OUTPUT_DIR / "step_04_status.json", "w") as f:
        json.dump(status, f, indent=2)
    print(f"Saved: step_04_status.json")

    print("\nStep 4: OK")


if __name__ == "__main__":
    main()
