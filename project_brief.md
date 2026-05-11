# Congressional Interest Dimension Analysis — Project Brief

## Objective

Build a pipeline that discovers latent interest dimensions in US Congressional voting behavior
beyond party affiliation, then characterizes those dimensions by overlaying financial interest
data (FEC disbursements by industry). The output is a legislator clustering in reduced
dimensional space where cluster identity reflects demonstrated interest alignment rather than
party membership.

This is a stress test of a broader methodology: that latent interest dimensions are discoverable
from institutional decision records using unsupervised structure discovery, and that those
dimensions can be characterized by whose financial interests precede vote alignment patterns.

If a non-party dimension emerges and is interpretable against financial interest data, the
methodology works. If the only recoverable dimension is party, that is also a valid finding.
Either outcome is informative. Do not optimize for a positive result.

---

## Context That Cannot Be Inferred

**Why this specific case:**
This is the cleanest available domain for methodology validation. Vote data is already
structured — no heavy NLP extraction in the core pipeline. Hardware constraint is a laptop.
PCA on a legislator × vote matrix is fast. The output is legible to a general audience.
It validates the hardest methodological question (does dimensionality discovery produce
interpretable structure beyond the obvious axis?) in the least noisy domain before touching
messier data.

**What this is a stress test of:**
A methodology for mapping whose interests are served by institutional decisions, using
documented effects rather than stated purposes. The vote matrix is the decision record.
FEC disbursement data is the financial interest record. The pipeline asks whether financial
interest alignment predicts position in the latent vote space better than party alone.

**The core methodological distinction:**
This is not political science clustering for its own sake. The goal is to demonstrate that
interest-effect tracing produces analytical signal beyond what party affiliation already
explains. Party is a proxy for interest alignment. We are looking for the residual — what
party does not explain — and characterizing what financial interest patterns live in that
residual.

**Abstention is a valid output:**
If the structure does not support interpretation — if the non-party dimensions do not
correlate with any identifiable financial interest pattern — the correct output is to
document that clearly, not to force an interpretation. Calibrated uncertainty is a feature.
Confident noise is the failure mode we are guarding against.

**The alternatives-not-taken dimension:**
Where possible, note which votes had structured alternatives (competing amendments, procedural
options) that were not taken. This is a secondary analysis but captures a methodologically
important signal — what options were available but not chosen is as informative as what was
chosen.

---

## Stack

```
Python 3.11+
jupyterlab
pandas
numpy
scipy
scikit-learn        # PCA
sklearn.manifold    # non-metric MDS for SSA approximation
plotly              # visualization
requests            # API calls
sqlite3             # local data store (stdlib — no install needed)
python-dotenv       # API key management
ollama              # local LLM for interpretation scaffolding only
```

Ollama model: `llama3:8b` — used only at interpretation gates, not in the data pipeline.

Do not introduce cloud inference dependencies. Everything runs locally.

---

## Data Sources

**Primary — GovTrack bulk vote data**
- URL pattern: `https://www.govtrack.us/data/congress/118/votes/`
- Format: JSON, one file per vote, organized by session and chamber
- No API key required
- Target: 118th Congress (2023–2024), both chambers
- Store locally in SQLite before any processing

**Secondary — FEC bulk disbursement data**
- API: `https://api.open.fec.gov/v1/schedules/schedule_b/`
- Requires free API key: https://api.open.fec.gov/developers/
- Target: disbursements to candidate committees, filtered to 118th Congress cycle (2022–2024)
- Industry/category codes are in the FEC data — use them as the interest dimension labels

**Do not** use the ProPublica Congress API as primary source — GovTrack bulk is preferable
for offline operation and avoids rate limits during development.

---

## Pipeline Steps and Success Conditions

### Step 0 — Environment and local data store

Set up project structure, install dependencies, initialize SQLite database schema.

**Success condition:** `python -c "import pandas, numpy, scipy, sklearn, plotly"` exits
cleanly. SQLite database file exists with correct schema. `.env` file present with FEC
API key slot.

---

### Step 1 — Acquire GovTrack vote data

Download all vote JSON files for 118th Congress to local store. Parse into SQLite tables:
- `votes` — vote metadata (date, chamber, category, question, result)
- `vote_positions` — legislator × vote positions (yea, nay, not voting, present)
- `legislators` — member metadata (bioguide_id, name, party, state, chamber)

**Success condition:** SQLite contains > 800 votes for House, > 400 for Senate. Every vote
has associated positions. Legislator table is complete with party affiliation. No network
calls required for any subsequent step.

**Implementation note:** GovTrack JSON structure has a `votes` object with keys `Yea`,
`Nay`, `Not Voting`, `Present` — each containing arrays of member objects with
`id` (bioguide_id) and `display_name`. The vote-level metadata is in the top-level
object: `category`, `question`, `result`, `date`, `chamber`.

---

### Step 2 — Filter to discretionary votes

Remove procedural votes from the analysis matrix. Procedural votes are constrained by
chamber mechanics, not legislator preference — including them adds noise that obscures
interest signal.

**Categories to EXCLUDE** (GovTrack `category` field values):
- `quorum`
- `procedural`
- `leadership`
- `election`

**Categories to INCLUDE:**
- `passage`
- `passage-suspension`
- `amendment`
- `cloture`
- `nomination` (Senate only — confirms interest signal in advice-and-consent decisions)
- `veto-override`

**Document the exclusion count** — how many votes were dropped and what fraction of the
total. This is a methodology transparency requirement, not optional.

**Success condition:** Filtered vote set contains ≥ 300 votes for each chamber. Exclusion
count and rationale are logged. If the filtered set drops below 300, review category
classifications before proceeding — do not silently reduce the analysis scope.

---

### Step 3 — Build legislator × vote matrix

Encode positions as: `1` (yea), `-1` (nay), `0` (not voting, present, or absent).

Build separate matrices for House and Senate — do not combine chambers. Analyze each
independently. The interest dimensions may differ between chambers and combining them
would obscure that.

Handle missing data: legislators who served partial terms will have structural zeros
for votes outside their tenure. Flag these legislators and assess whether their
inclusion distorts the matrix. If a legislator is present for fewer than 50% of
the votes in the filtered set, exclude them and document the exclusion.

**Success condition:** Two numpy arrays — one per chamber. Shape is
`(legislators × votes)`. No NaN values. Partial-tenure exclusions documented.
Verify that the first principal component of each matrix is strongly correlated
with party affiliation before proceeding — this is a sanity check, not the
finding. If the first PC does not correlate with party, something is wrong with
the data pipeline, not an interesting discovery.

---

### Step 4 — PCA structure discovery

Fit PCA on each chamber matrix separately. Produce:
- Full eigenvalue spectrum
- Scree plot (plotly, saved as HTML)
- Parallel analysis to determine how many components exceed chance
- Component loadings for retained components (which votes load most heavily)
- Legislator scores on each retained component

**Retention criteria:** Use parallel analysis as primary criterion. Kaiser (eigenvalue > 1)
as secondary check. Document both. Retain the minimum number of components supported
by parallel analysis — do not retain components because they seem interpretable.

**The party sanity check:** Correlate PC1 scores with a binary party variable
(Democrat=1, Republican=0, Independent=midpoint). If r² < 0.7, something is wrong.
If r² > 0.95, PC1 is entirely party and you need PC2+ to find the signal.
Document this correlation explicitly.

**Success condition:** At least 2 components retained by parallel analysis for each
chamber. At least one component with r² < 0.5 against party affiliation — this is
the non-party dimension the methodology depends on finding. Scree plots saved.
Component loading tables saved (top 20 positive and negative loading votes per
component, with vote descriptions).

---

### Step 5 — HITL: Dimension interpretation

**This step is human-executed. Do not automate the interpretation judgment.**

The pipeline scaffolds this step as follows:

For each retained component, surface to the human:
1. The top 10 positive-loading votes with their descriptions and outcomes
2. The top 10 negative-loading votes with their descriptions and outcomes
3. A candidate dimension name generated by the local LLM (Ollama/llama3:8b)
   based on summarizing the vote descriptions — presented as a suggestion, not a finding

**Ollama prompt template for candidate naming:**
```
These votes load positively on a latent dimension in Congressional voting behavior:
{positive_vote_descriptions}

These votes load negatively on the same dimension:
{negative_vote_descriptions}

In one short phrase, what interest or value distinction might this dimension represent?
Be specific about whose interests are on each side. Do not use party labels.
Respond with only the candidate phrase, no explanation.
```

The human reviews the candidate name and either confirms, modifies, or rejects it.
The confirmed interpretation is stored as metadata on the component and used in
all downstream outputs. If the human cannot interpret a component, label it
`uninterpreted-{n}` and proceed — do not force an interpretation.

**Success condition:** Every retained component has a human-confirmed label or is
explicitly marked uninterpreted. Labels are stored in a config file that downstream
steps read. At least one component has a confirmed non-party interpretation.

---

### Step 6 — SSA geometry

Apply non-metric MDS (scikit-learn `MDS` with `metric=False`) to the correlation
matrix of retained components. This approximates SSA and reveals the geometric
structure of how the components relate to each other.

Target: 2-dimensional solution first. Compute stress (equivalent to coefficient
of alienation). If stress > 0.15, attempt 3-dimensional solution.

Produce a plotly scatter plot of legislators in the reduced space, colored by:
- Party affiliation (sanity check)
- Confirmed component interpretation (the finding)

**Success condition:** Stress < 0.20 for 2D or 3D solution. Plot saved as HTML.
The geometric arrangement does not need to be a clean circumplex — but if one
emerges, document it explicitly. If the arrangement is not interpretable, document
that and proceed to the interest overlay anyway.

---

### Step 7 — Acquire FEC disbursement data

Pull FEC Schedule B disbursements — payments from committees to candidates — for
the 2022 and 2024 cycles, covering the 118th Congress membership.

Match FEC recipients to legislators using FEC candidate IDs. GovTrack legislator
records contain FEC IDs where available — use those as the join key. Where FEC IDs
are missing from GovTrack, attempt name/state match with manual review of ambiguous
cases.

Aggregate disbursements by legislator and by FEC industry/category code. The output
is a legislator × industry matrix of total disbursements received.

**Success condition:** At least 80% of legislators in the vote matrix have matched
FEC records. Unmatched legislators are documented. Industry category distribution
is logged — verify that the industry codes are populated (not all blank) before
proceeding.

---

### Step 8 — Interest overlay

Join the FEC industry disbursement matrix to legislator PCA component scores.

For each retained and interpreted component, compute:
- Correlation of component score with total disbursements per industry category
- Top 5 industry categories most positively correlated with the component
- Top 5 industry categories most negatively correlated with the component

**This is the core methodology validation step.** If component scores correlate
with identifiable industry interest patterns in a direction consistent with the
human interpretation from Step 5, the methodology is producing signal. If
correlations are near zero or inconsistent with the interpretation, document
that as a finding — it may mean the component reflects something other than
financial interest alignment.

Do not threshold correlations to make results look stronger. Report the full
correlation distribution. A weak but consistent signal is more honest and more
interesting than a cherry-picked strong one.

**Success condition:** Correlation analysis complete for all retained components.
Results saved as tables. At least one component shows industry correlations
consistent with its human-assigned interpretation (r > 0.15 counts — this is
a noisy domain). Document any components where correlations are inconsistent
with interpretation — this is a finding about the limits of the methodology.

---

### Step 9 — Clustering and output

Cluster legislators in PCA component space (k-means or HDBSCAN — prefer HDBSCAN
for variable-density clusters, which is likely given the structure of the space).
Do not set k based on intuition — use silhouette score to select k for k-means,
or let HDBSCAN determine clusters automatically.

For each cluster:
- Dominant party composition (but do not label by party)
- Dominant industry interest pattern from FEC overlay
- Representative legislators (those closest to cluster centroid)
- Human-interpretable label based on interest alignment, not party

Produce final output:
- Interactive plotly scatter (legislator points, colored by cluster, hover shows name/party/state)
- Summary table: cluster × party composition × dominant industry interests
- Methodology transparency log: every exclusion decision, interpretation judgment,
  and abstention documented

**Success condition:** Clusters produced with silhouette score > 0.3 or HDBSCAN
produces at least 2 meaningful clusters (not noise). At least one cluster has
meaningful cross-party membership. Final output files saved. Methodology log complete.

---

## Constraints

**Hardware:**
Laptop only. No cloud compute. No GPU required or assumed. Every step must complete
in reasonable time on a mid-range laptop (target: < 5 minutes per step, < 30 minutes
total pipeline runtime excluding data acquisition).

**Data:**
All processing runs against locally stored data after Step 1. No live API calls in
Steps 2–9. If re-running the pipeline, data acquisition should be skippable if the
SQLite database already exists and is populated.

**LLM:**
Ollama with llama3:8b only. Used only in Step 5 for candidate name generation.
Not used in any data pipeline step. Internet connection not required once model
is pulled.

**Interpretation:**
Never automate the human interpretation judgment in Step 5. The system scaffolds
the decision — surfaces the relevant information and generates a candidate — but
the human makes the call. If the pipeline is run in a fully automated mode that
skips Step 5, all downstream outputs must be labeled as uninterpreted and the
final output must include a warning that no human interpretation has been applied.

**Reporting:**
Every exclusion, every threshold choice, every interpretation judgment is logged.
The methodology log is a required output, not optional documentation. A result
with no methodology log is not a valid result.

**Failure handling:**
If any step's success condition is not met, the pipeline stops and surfaces a
clear failure message that identifies which condition failed and what the observed
value was. Do not proceed to downstream steps on a failed upstream step.
Silent degradation is the failure mode we are guarding against.

---

## Output Files

```
/data/
  votes.db                    # SQLite — all acquired data

/output/
  eigenvalue_spectrum_house.html
  eigenvalue_spectrum_senate.html
  pca_space_house.html
  pca_space_senate.html
  ssa_geometry_house.html
  ssa_geometry_senate.html
  clusters_final.html         # interactive, hover-enabled
  cluster_summary_table.csv
  interest_correlation_table.csv
  methodology_log.md          # required output
```

---

## Definition of Demo Success

The pipeline produces at least one non-party latent dimension that:
1. Is retained by parallel analysis (not just interpretable)
2. Has a human-confirmed interpretation
3. Shows industry interest correlations consistent with that interpretation
4. Produces cross-party clustering when legislators are grouped by position on it

If all four conditions are met, the methodology stress test passes and the
case is ready for presentation.

If fewer than four conditions are met, document which conditions passed and
which did not. A partial result is a valid stress test outcome. It identifies
exactly where the methodology needs refinement before the next domain attempt.
