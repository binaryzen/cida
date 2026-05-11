import numpy as np
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
from sklearn.manifold import MDS
from scipy.spatial.distance import pdist, squareform
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "output"

def main():
    """Apply non-metric MDS to legislator pairwise distances in PCA component space."""

    try:
        status = {}
        log_entries = []

        for chamber_name in ['house', 'senate']:
            print(f"Processing {chamber_name}...", flush=True)

            # 1. Load scores and labels
            scores_path = OUTPUT_DIR / f"scores_{chamber_name}.csv"
            labels_path = OUTPUT_DIR / "component_labels.json"

            if not scores_path.exists():
                raise FileNotFoundError(f"Scores file not found: {scores_path}")
            if not labels_path.exists():
                raise FileNotFoundError(f"Labels file not found: {labels_path}")

            scores_df = pd.read_csv(scores_path)
            with open(labels_path, 'r') as f:
                labels_json = json.load(f)

            # Determine PC columns — skip pc0 (party-alignment) for SSA
            all_pc_cols = [f"pc{j}" for j in range(len(labels_json[chamber_name]))]
            pc_cols = all_pc_cols[1:]  # drop party dimension
            X = scores_df[pc_cols].values  # shape: (n_legislators, n_non_party_components)

            # 2. Compute pairwise distance matrix using Euclidean distance
            # Correlation distance is inappropriate for orthogonal PCA components —
            # it normalizes out magnitude, producing near-uniform distances and a circular MDS artifact.
            dist_flat = pdist(X, metric='euclidean')
            dist_matrix = squareform(dist_flat)

            # 3. Try 2D non-metric MDS
            mds2 = MDS(n_components=2, metric=False, dissimilarity='precomputed',
                       n_init=10, max_iter=1000, random_state=42)
            coords2 = mds2.fit_transform(dist_matrix)
            kruskal2 = np.sqrt(mds2.stress_ / (np.sum(dist_matrix**2) + 1e-10))

            dims = 2
            coords = coords2
            final_kruskal = kruskal2
            stress_warning = "no"

            if kruskal2 > 0.15:
                # Try 3D MDS
                mds3 = MDS(n_components=3, metric=False, dissimilarity='precomputed',
                           n_init=10, max_iter=1000, random_state=42)
                coords3 = mds3.fit_transform(dist_matrix)
                kruskal3 = np.sqrt(mds3.stress_ / (np.sum(dist_matrix**2) + 1e-10))

                if kruskal3 <= 0.20:
                    coords = coords3
                    final_kruskal = kruskal3
                    dims = 3
                else:
                    # Use 3D anyway with warning
                    coords = coords3
                    final_kruskal = kruskal3
                    dims = 3
                    stress_warning = "yes"

            # 4. Create plotly visualization
            df = scores_df.copy()
            df['dim1'] = coords[:, 0]
            df['dim2'] = coords[:, 1]

            if dims == 3:
                df['dim3'] = coords[:, 2]
                fig = px.scatter_3d(df, x='dim1', y='dim2', z='dim3', color='party',
                                   hover_name='display_name',
                                   hover_data=['party', 'state'],
                                   title=f"SSA Geometry ({chamber_name.title()}) — 3D, Kruskal: {final_kruskal:.3f}")
            else:
                fig = px.scatter(df, x='dim1', y='dim2', color='party',
                                hover_name='display_name',
                                hover_data=['party', 'state'],
                                title=f"SSA Geometry ({chamber_name.title()}) — Kruskal stress: {final_kruskal:.3f}",
                                labels={'dim1': 'MDS Dimension 1', 'dim2': 'MDS Dimension 2'})

            fig.write_html(str(OUTPUT_DIR / f"ssa_geometry_{chamber_name}.html"))

            # 5. Log results
            status[chamber_name] = {
                "mds_dims": dims,
                "kruskal_stress": round(final_kruskal, 4),
                "stress_warning": stress_warning
            }

            log_entries.append(
                f"- {chamber_name}_mds_dims: {dims}\n"
                f"- {chamber_name}_kruskal_stress: {round(final_kruskal, 4)}\n"
                f"- {chamber_name}_stress_warning: {stress_warning}"
            )

        # Append to methodology log
        methodology_log_path = OUTPUT_DIR / "methodology_log.md"
        with open(methodology_log_path, 'a') as f:
            f.write(f"## {datetime.now().isoformat()} — Step 6: SSA Geometry\n")
            for entry in log_entries:
                f.write(entry + "\n")
            f.write("\n")

        # Write step_06_status.json
        status_path = OUTPUT_DIR / "step_06_status.json"
        with open(status_path, 'w') as f:
            json.dump(status, f, indent=2)

        # Print summary
        house_stress = status['house']['kruskal_stress']
        senate_stress = status['senate']['kruskal_stress']
        print(f"Step 6: OK — House stress {house_stress:.3f}, Senate stress {senate_stress:.3f}", flush=True)

        return 0

    except Exception as e:
        print(f"Step 6 failed: {e}", file=sys.stderr, flush=True)

        # Write failed status
        status_path = OUTPUT_DIR / "step_06_status.json"
        with open(status_path, 'w') as f:
            json.dump({"error": str(e)}, f, indent=2)

        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
