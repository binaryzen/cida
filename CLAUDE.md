# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Congressional Interest Dimension Analysis (CIDA) — a 10-step Python pipeline that discovers latent interest dimensions in US Congressional voting behavior (118th Congress), then characterizes those dimensions by overlaying FEC financial interest data. The goal is to find non-party dimensions and validate whether financial interest alignment predicts position in latent vote space better than party alone.

## Stack

```
Python 3.11+  |  JupyterLab  |  pandas  |  numpy  |  scipy
scikit-learn (PCA + non-metric MDS)  |  plotly  |  requests
sqlite3 (stdlib)  |  python-dotenv  |  ollama (llama3:8b)
```

Ollama is used **only** in Step 5 for candidate label generation. It is never used in the data pipeline.

## Setup

```bash
pip install jupyterlab pandas numpy scipy scikit-learn plotly requests python-dotenv
# Verify:
python -c "import pandas, numpy, scipy, sklearn, plotly"
```

Create `.env` at project root with your FEC API key (free at https://api.open.fec.gov/developers/):
```
FEC_API_KEY=your_key_here
```

Initialize the SQLite database:
```bash
python steps/step_00_setup.py    # creates data/votes.db with schema
```

## Running the Pipeline

Each step is a standalone script. Run sequentially; each step validates its own success condition before exit — the pipeline stops with a clear error if a condition is not met.

```bash
python steps/step_01_acquire_govtrack.py   # downloads GovTrack vote JSON → SQLite
python steps/step_02_filter_votes.py       # excludes procedural categories
python steps/step_03_build_matrix.py       # builds legislator × vote numpy arrays
python steps/step_04_pca.py                # PCA + parallel analysis → HTML plots
# Step 5 is human-executed (see below)
python steps/step_06_ssa_geometry.py       # non-metric MDS → SSA geometry plots
python steps/step_07_acquire_fec.py        # pulls FEC Schedule B disbursements
python steps/step_08_interest_overlay.py   # correlates PCA scores with FEC industries
python steps/step_09_cluster_output.py     # clustering + final outputs
```

If `data/votes.db` is already populated, Step 1 should be skippable (add a check at the top of the script).

## Architecture

### Data Flow

```
GovTrack JSON (HTTP) → SQLite (data/votes.db)
                           ↓
                    Filter → numpy matrices (House / Senate separate)
                           ↓
                         PCA → component scores + loadings
                           ↓
                   Step 5: HITL interpretation (human + Ollama scaffold)
                           ↓
              Non-metric MDS → SSA geometry
                           ↓
FEC API → SQLite ──────────┤
                           ↓
               Interest overlay (correlations)
                           ↓
                  Clustering → final outputs
```

### SQLite Tables (`data/votes.db`)

- `votes` — vote metadata: date, chamber, category, question, result
- `vote_positions` — legislator × vote positions (yea/nay/not voting/present)
- `legislators` — bioguide_id, name, party, state, chamber, fec_candidate_id

### Output Files (`output/`)

| File | Description |
|------|-------------|
| `eigenvalue_spectrum_{house,senate}.html` | Scree plots |
| `pca_space_{house,senate}.html` | Legislator scores in PCA space |
| `ssa_geometry_{house,senate}.html` | Non-metric MDS geometry |
| `clusters_final.html` | Interactive cluster visualization (hover: name/party/state) |
| `cluster_summary_table.csv` | Cluster × party composition × dominant industries |
| `interest_correlation_table.csv` | Component × industry correlations |
| `methodology_log.md` | **Required output** — all exclusions and interpretation decisions |

## Critical Constraints

**Step 5 (HITL) is never automated.** The pipeline surfaces top-loading votes per component and calls Ollama to generate a candidate label, but the human must confirm, modify, or reject every label. If running unattended, all downstream outputs must be marked `uninterpreted` and the final output must include a warning. The confirmed labels are stored in a config file (e.g., `output/component_labels.json`) that Steps 6–9 read.

**Chambers are always analyzed separately.** Never combine House and Senate into a single matrix.

**Failure handling is strict.** If any step's numeric success condition fails (e.g., fewer than 300 filtered votes, legislator match rate below 80%, PC1 r² < 0.7 with party), the step must print the observed value, name the violated condition, and exit non-zero. Do not silently continue.

**No live API calls after Step 1/7.** All steps except data acquisition read only from SQLite.

**Methodology log is a required output**, not optional documentation. Every exclusion count, threshold choice, and interpretation judgment must be written to `output/methodology_log.md` as the pipeline runs.

## Key Thresholds (from spec)

| Check | Threshold |
|-------|-----------|
| Filtered votes per chamber | ≥ 300 |
| PC1 correlation with party (r²) | 0.7 – 0.95 (sanity range) |
| Non-party component (r² with party) | < 0.5 |
| FEC legislator match rate | ≥ 80% |
| SSA stress (2D or 3D) | < 0.20 |
| Clustering silhouette score | > 0.3 |
| Industry correlation "signal" threshold | r > 0.15 |

## Vote Encoding

`1` = Yea, `-1` = Nay, `0` = Not Voting / Present / Absent

Legislators present for fewer than 50% of filtered votes are excluded and documented.

## Vote Categories

**Include:** `passage`, `passage-suspension`, `amendment`, `cloture`, `nomination` (Senate only), `veto-override`

**Exclude:** `quorum`, `procedural`, `leadership`, `election`

## Writing Style

See `tone_steering_general.md` for prose style rules — applies to any generated docs, READMEs, methodology logs, or site copy (e.g. `docs/`).

## Ollama Prompt Template (Step 5)

```
These votes load positively on a latent dimension in Congressional voting behavior:
{positive_vote_descriptions}

These votes load negatively on the same dimension:
{negative_vote_descriptions}

In one short phrase, what interest or value distinction might this dimension represent?
Be specific about whose interests are on each side. Do not use party labels.
Respond with only the candidate phrase, no explanation.
```
