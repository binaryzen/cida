# C I D A

Two iterations of the same latent-dimension methodology applied to different domains.

## Iteration 1 — Congressional Interest Dimension Analysis

Principal component analysis on 118th Congress roll-call voting behavior, with external overlays from FEC campaign finance data and CRS policy area classifications.

Results are in [`docs/iteration-1/`](docs/iteration-1/index.html). Open `docs/iteration-1/index.html` in a browser to navigate the multi-page site.

Key finding: House PC3 is orthogonal to both dimensions of DW-NOMINATE (r² < 0.01), suggesting a latent voting dimension not captured by existing two-dimensional models.

## Iteration 2 — Customer Issue Dimension Analysis

NMF topic modelling on a public JIRA ticket corpus for Sourcetree for Windows (2013–2023). Identifies defect families, customer segments, and cross-cutting recommendations from 1,000 unique support tickets.

Data: *JIRA Dataset* by **Cesar Anasco**, published on [Kaggle](https://www.kaggle.com/datasets/cesaranasco/jira-dataset/data) (2023).

Results are in [`docs/iteration-2/`](docs/iteration-2/index.html). Open `docs/iteration-2/index.html` in a browser.

Key findings: 49% of tickets untriaged; a single v3.3.6 UI refresh regression accounts for more community votes than all other defect categories combined; creation-time ticket features have no predictive power for resolution outcome.

## Pipeline

Ten-step Python pipeline in `steps/`. See [CLAUDE.md](CLAUDE.md) for setup and run instructions.

```
step_00  setup         create SQLite schema
step_01  acquire       download GovTrack vote JSON → SQLite
step_02  filter        exclude procedural vote categories
step_03  build_matrix  legislator × vote numpy arrays
step_04  pca           PCA + parallel analysis → scores/loadings
step_05  HITL          human component labeling (manual)
step_06  ssa_geometry  non-metric MDS on PC1+ space
step_07  acquire_fec   FEC bulk download → SQLite
step_08  overlay       correlate PCA scores × FEC industries
step_09  cluster       HDBSCAN clustering + final outputs
step_10  annotate      Haiku policy facet annotation swarm
step_11  validate      DW-NOMINATE comparison + CRS validation
```

Data requirements: `data/votes.db` (not tracked; run step_00 + step_01 to generate). FEC bulk files cached in `data/fec_bulk/` (not tracked).

## Output files

Tracked in `output/`:

| File | Description |
|------|-------------|
| `scores_{house,senate}.csv` | PCA component scores per legislator |
| `loadings_{house,senate}.csv` | Vote loadings per component |
| `nominate_comparison.csv` | Pearson r vs DW-NOMINATE dim1/dim2 |
| `crs_validation.csv` | Pearson r vs CRS policy area mean positions |
| `interest_correlation_table.csv` | Pearson r vs FEC industry receipts |
| `cluster_summary_table.csv` | Cluster composition by party |
| `component_labels.json` | Analyst-assigned component labels |
| `methodology_log.md` | Full pipeline decision log |

Interactive HTML plots (not tracked; regenerate via pipeline) go to `output/*.html`.

## Congress

118th Congress (January 2023 – January 2025). House: 354 legislators × 797 discretionary votes. Senate: 85 legislators × 598 votes.
