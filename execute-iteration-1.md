# execute-iteration-1.md

## Scope

Steps covered by this iteration: **0, 1, 2, 3, 4, 5 (code only), 6, 7, 8, 9**

Step 5 **execution** is excluded — only its scaffolding script is written. Steps 6–9
run with automatically-generated `uninterpreted-N` labels and are re-runnable after
the human completes Step 5.

### Iteration 1 decisions (from Q&A, 2026-05-10)
- **FEC skipped**: Steps 7–9 are written but NOT executed this iteration. FEC API key not yet available.
- **ollama**: Installed and ready; include in requirements.txt and step_05 as-is.
- **FEC industry field**: TBD — pause before executing Step 7 to align on `committee_type_full` vs alternative. Step 7 is written with `committee_type_full` as the placeholder; add a `# TODO: confirm industry field` comment at the aggregation point.
- **Execution this iteration**: Steps 0 → 1 → 2 → 3 → 4 → 6 (sequential). Steps 5, 7, 8, 9 written only.

---

## Delegation Model

- **Haiku**: Write all individual scripts (straightforward, well-specified code)
- **Sonnet (me)**: Coordinate rounds, execute scripts, handle kickbacks, verify outputs

If Haiku encounters anything not covered by this spec, it writes a kickback report and
stops — it does not make judgment calls or fill in gaps with defaults.

---

## Pre-Decided Technical Choices

All choices below are final. Haiku must not deviate from them.

### Repository layout (to be created)
```
cida/
  .env                              # FEC_API_KEY=your_key_here (template)
  requirements.txt
  steps/
    step_00_setup.py
    step_01_acquire_govtrack.py
    step_02_filter_votes.py
    step_03_build_matrix.py
    step_04_pca.py
    step_05_hitl.py                 # scaffolding only, not executed here
    step_06_ssa.py
    step_07_acquire_fec.py
    step_08_interest_overlay.py
    step_09_cluster_output.py
  data/
    votes.db                        # created by step_00
  output/
    methodology_log.md              # created by step_00, appended by each step
    component_labels.json           # created by step_04
```

### requirements.txt (exact content)
```
jupyterlab
pandas
numpy
scipy
scikit-learn>=1.3.0
plotly
requests
python-dotenv
pyyaml
ollama
```
`scikit-learn>=1.3.0` is required because `sklearn.cluster.HDBSCAN` first appeared in 1.3.
`pyyaml` is needed for the congress-legislators YAML in Step 1.
`ollama` is the Python SDK for the local model in Step 5.

### Script conventions
- Every script is standalone: `python steps/step_NN_name.py`
- All scripts import at top, no inline imports
- Every script writes `output/step_NN_status.json` before exit:
  ```json
  { "step": N, "name": "Step Name", "status": "ok|failed|kickback",
    "message": "...", "values": { "key": value } }
  ```
  On `failed` or `kickback`: write the file, then `sys.exit(1)`
- Every script appends to `output/methodology_log.md` (never overwrites):
  ```
  ## 2024-01-15T10:30:00 — Step N: Name
  - key: value
  ```
- Use `pathlib.Path` for all file operations; create parent directories with `mkdir(parents=True, exist_ok=True)`

### Vote encoding (integer)
| Position string | Encoded value |
|---|---|
| `Yea` or `Aye` | `1` |
| `Nay` or `No` | `-1` |
| `Not Voting` | `0` |
| `Present` | `0` |
| Absent (not in any list) | `0` |

### SQLite schema (exact DDL — applied in step_00)
```sql
CREATE TABLE IF NOT EXISTS votes (
    vote_id        TEXT    PRIMARY KEY,
    year           INTEGER NOT NULL,
    chamber        TEXT    NOT NULL CHECK(chamber IN ('h','s')),
    category       TEXT,
    question       TEXT,
    result         TEXT,
    date           TEXT,
    is_discretionary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vote_positions (
    vote_id        TEXT    NOT NULL REFERENCES votes(vote_id),
    bioguide_id    TEXT    NOT NULL,
    position       INTEGER NOT NULL CHECK(position IN (-1, 0, 1)),
    PRIMARY KEY (vote_id, bioguide_id)
);

CREATE TABLE IF NOT EXISTS legislators (
    bioguide_id       TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    party             TEXT,
    state             TEXT,
    chamber           TEXT CHECK(chamber IN ('h','s')),
    fec_candidate_id  TEXT
);

CREATE TABLE IF NOT EXISTS fec_disbursements (
    transaction_id         TEXT PRIMARY KEY,
    cycle                  INTEGER NOT NULL,
    recipient_candidate_id TEXT,
    committee_id           TEXT NOT NULL,
    disbursement_amount    REAL,
    disbursement_date      TEXT
);

CREATE TABLE IF NOT EXISTS fec_committees (
    committee_id        TEXT PRIMARY KEY,
    committee_name      TEXT,
    committee_type      TEXT,
    committee_type_full TEXT,
    org_type            TEXT,
    org_type_full       TEXT
);
```

### GovTrack URL structure
```
Year directory listing: https://www.govtrack.us/data/congress/118/votes/{year}/
Vote data file:         https://www.govtrack.us/data/congress/118/votes/{year}/{vote_id}/data.json
```
- `year` values: `2023`, `2024`
- Vote IDs extracted from directory HTML using: `re.findall(r'href="([hs]\d+)/"', html)`
- Request config: `requests.get(url, timeout=30)`, `time.sleep(0.1)` after every request
- On any HTTP error for an individual vote: log the vote_id and error code to methodology log, skip it, continue — do NOT abort
- Idempotency: skip vote if `vote_id` already present in `votes` table

### GovTrack vote JSON structure
```json
{
  "category": "passage",
  "question": "On Passage",
  "result": "Passed",
  "date": "2023-01-09T14:00:00-05:00",
  "chamber": "h",
  "votes": {
    "Yea":        [{"id": "B001234", "display_name": "Smith (D-NY)"}],
    "Nay":        [...],
    "Not Voting": [...],
    "Present":    [...]
  }
}
```
- `chamber` field: `"h"` = House, `"s"` = Senate
- `votes` keys that may appear: `"Yea"`, `"Aye"`, `"Nay"`, `"No"`, `"Not Voting"`, `"Present"`
- Member `"id"` field = bioguide_id

### Legislators data source (Step 1)
URL: `https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml`

YAML structure per legislator:
```yaml
- id:
    bioguide: A000370
    fec:
      - H4NC12164
  name:
    official_full: "Alma S. Adams"
    first: Alma
    last: Adams
  terms:
    - type: rep         # 'rep' → chamber 'h', 'sen' → chamber 's'
      start: "2023-01-03"
      end: "2025-01-03"
      party: Democrat
      state: NC
```

Extraction rules:
- `display_name`: use `name.official_full` if present, else `"{name.first} {name.last}"`
- `chamber`: from most recent term (highest `start` date): `'rep'` → `'h'`, `'sen'` → `'s'`
- `party`: from most recent term
- `state`: from most recent term
- `fec_candidate_id`: first element of `id.fec` list if non-empty, else `NULL`
- **Filter**: include only legislators whose most recent term has `start >= "2021-01-03"` AND (`end` field absent OR `end >= "2023-01-03"`)

### Parallel analysis algorithm (Step 4)
```python
def parallel_analysis(X_scaled, n_iter=1000, percentile=95, random_state=42):
    n_samples, n_features = X_scaled.shape
    n_components = min(n_samples - 1, n_features)
    rng = np.random.RandomState(random_state)
    rand_eigenvalues = np.zeros((n_iter, n_components))
    for i in range(n_iter):
        R = rng.randn(n_samples, n_features)
        R = (R - R.mean(axis=0)) / (R.std(axis=0) + 1e-10)
        pca_r = PCA(n_components=n_components)
        pca_r.fit(R)
        rand_eigenvalues[i] = pca_r.explained_variance_
    return np.percentile(rand_eigenvalues, percentile, axis=0)
```
Retain component `i` if `actual_eigenvalues[i] > parallel_thresholds[i]`.

### MDS dissimilarity metric (Step 6)
Use pairwise Pearson correlation distance between legislators, computed as:
```python
from scipy.spatial.distance import pdist, squareform
scores_array  # shape: (n_legislators, n_retained_components)
dist_matrix = squareform(pdist(scores_array, metric='correlation'))
# 'correlation' gives 1 - pearson_r; clip to [0, 2] to handle float noise
dist_matrix = np.clip(dist_matrix, 0, 2)
```
Apply `MDS(n_components=2, metric=False, dissimilarity='precomputed', n_init=10, max_iter=1000, random_state=42)`.

Kruskal stress: `np.sqrt(mds.stress_ / np.sum(dist_matrix**2))`
- If Kruskal stress > 0.15: retry with `n_components=3`
- If still > 0.20: log warning in methodology log, proceed anyway (valid finding)

### FEC industry proxy
Use `committee_type_full` from `fec_committees` table as the industry dimension.
This is populated from the FEC API committee endpoint (see Step 7 spec).
Example values: `"Corporate PAC"`, `"Labor Organization"`, `"Non-Connected PAC"`, `"Party"`, etc.
Use `log1p(disbursement_amount)` before computing correlations (Step 8) to handle skew.

### FEC API pagination
```python
params = {
    "api_key": api_key,
    "two_year_transaction_period": cycle,
    "recipient_candidate_id": fec_id,
    "per_page": 100,
    "sort": "disbursement_date",
    "sort_hide_null": True,
}
while True:
    resp = requests.get("https://api.open.fec.gov/v1/schedules/schedule_b/",
                        params=params, timeout=30)
    data = resp.json()
    results = data.get("results", [])
    if not results:
        break
    # ... process results ...
    last = data.get("pagination", {}).get("last_indexes")
    if not last:
        break
    params["last_index"] = last["last_index"]
    params["last_disbursement_date"] = last["last_disbursement_date"]
    time.sleep(0.05)
```

### Clustering parameters (Step 9)
- HDBSCAN first: `min_cluster_size = max(5, n_legislators // 20)`, `min_samples = 3`
- Meaningful clusters = labels where `label != -1`, count of unique such labels ≥ 2
- k-means fallback: try `k` in `range(2, 9)`, pick `k` with highest silhouette score; use `KMeans(n_clusters=k, random_state=42, n_init=10)`
- "Minority party" threshold: at least 10% of a cluster must be the non-dominant party

### Kickback protocol
When Haiku cannot proceed:
1. Write `output/step_NN_kickback.md`:
   ```markdown
   # Kickback — Step NN: Name
   **Condition**: What threshold/structure was expected
   **Observed**: What was actually found
   **Values**: { relevant counts and measurements }
   **Suggestion**: If obvious — otherwise omit
   ```
2. Write `output/step_NN_status.json` with `"status": "kickback"`
3. Print `KICKBACK: <reason>` to stdout
4. `sys.exit(1)`

Haiku must NOT: proceed past a kickback, silently change thresholds, assume data structure variations.

---

## Code-Writing Round (all Haiku, all concurrent)

All 10 scripts can be written in parallel because none depends on another script's
output at write time. Spawn all agents simultaneously.

| Agent | Writes | Complexity |
|---|---|---|
| H-00 | `requirements.txt` + `steps/step_00_setup.py` | Low |
| H-01 | `steps/step_01_acquire_govtrack.py` | High — see full spec |
| H-02 | `steps/step_02_filter_votes.py` | Low |
| H-03 | `steps/step_03_build_matrix.py` | Medium |
| H-04 | `steps/step_04_pca.py` | High — parallel analysis, plots |
| H-05 | `steps/step_05_hitl.py` | Medium — Ollama, interactive |
| H-06 | `steps/step_06_ssa.py` | Medium — MDS, plots |
| H-07 | `steps/step_07_acquire_fec.py` | High — API pagination, matching |
| H-08 | `steps/step_08_interest_overlay.py` | Medium — join + correlations |
| H-09 | `steps/step_09_cluster_output.py` | Medium — clustering + final plots |

---

## Execution Sequence

Dependencies shown as arrows. Steps with no common ancestor can run concurrently.

```
pip install -r requirements.txt
      │
step_00 (create DB + dirs)
      │
step_01 (GovTrack download) ──────────────────────────────────┐
      │                                                         │
step_02 (filter votes)                                   step_07 (FEC) ← requires FEC_API_KEY
      │
step_03 (build matrices)
      │
step_04 (PCA + parallel analysis)
      │                  │
step_06 (SSA/MDS)    step_08 (interest overlay) ← waits for step_07 too
                         │
                    step_09 (clustering + final output)
```

Note: step_07 can start as soon as step_01 finishes (legislators table is populated).
Steps 06 and 07 can run concurrently after step_04 and step_01 respectively.
Step 08 must wait for BOTH step_04 and step_07.

---

## Detailed Script Specifications

### step_00_setup.py

**Purpose**: Create `data/` and `output/` dirs, apply SQLite schema, write `.env` template, initialize methodology log.

**Inputs**: None

**Outputs**:
- `data/votes.db` (all tables created)
- `output/methodology_log.md` (header only)
- `.env` (only if not already present — never overwrite existing)

**Logic**:
```python
# 1. mkdir data/ output/ steps/ (exist_ok)
# 2. Connect to data/votes.db, apply full DDL from schema spec above
# 3. If .env does not exist: write "FEC_API_KEY=your_key_here\n"
# 4. If output/methodology_log.md does not exist:
#    write "# CIDA Methodology Log\n\n"
# 5. Append Step 0 entry to methodology log
# 6. Write output/step_00_status.json
# 7. Print "Step 0: OK"
```

**Success condition**: All tables exist in DB, `output/methodology_log.md` exists.

---

### step_01_acquire_govtrack.py

**⚠️ Data source change (discovered during execution):** The GovTrack bulk file server (`/data/congress/118/votes/`) returned 404 as of 2025. Switched to GovTrack API v2.

New approach (two-pass API):
- Pass 1: `GET /api/v2/vote?congress=118` — all vote metadata (congress=118 filter works, ~1,700 votes, paginate with offset)
- Pass 2: For each vote's `created` datetime, `GET /api/v2/vote_voter?created=DATETIME&limit=700` — returns all voter records with `person.bioguideid`, `option.key` (`"+"` = Yea→1, `"-"` = Nay→-1, else→0), and the full vote object embedded. Group by `vote.link` to handle same-timestamp votes.

**Purpose**: Populate all three SQLite tables from GovTrack API v2 + congress-legislators YAML.

**Inputs**: Internet (one-time)

**Outputs**:
- `legislators` table populated
- `votes` table populated
- `vote_positions` table populated
- `output/step_01_status.json`
- Appended methodology log entry

**Logic**:

Part A — legislators:
```python
import yaml, requests, sqlite3, time

YAML_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml"

# Download with 3 retries, 2s backoff
# Parse YAML → list of legislator dicts
# For each legislator:
#   Sort terms by 'start' descending; most_recent = terms[0]
#   Filter: most_recent['start'] >= '2021-01-03'
#          AND (no 'end' key OR most_recent['end'] >= '2023-01-03')
#   Extract fields per spec above
#   INSERT OR REPLACE into legislators
```

Part B — votes:
```python
YEARS = [2023, 2024]
BASE = "https://www.govtrack.us/data/congress/118/votes"

for year in YEARS:
    html = requests.get(f"{BASE}/{year}/", timeout=30).text
    time.sleep(0.1)
    vote_ids = re.findall(r'href="([hs]\d+)/"', html)
    # vote_id stored in DB as f"{year}/{raw_id}", e.g. "2023/h1"
    for raw_id in vote_ids:
        db_vote_id = f"{year}/{raw_id}"
        if already_in_db(db_vote_id):
            continue
        url = f"{BASE}/{year}/{raw_id}/data.json"
        resp = requests.get(url, timeout=30)
        time.sleep(0.1)
        if resp.status_code != 200:
            log_skip(db_vote_id, resp.status_code)
            continue
        data = resp.json()
        # INSERT into votes: vote_id=db_vote_id, year, chamber, category, question, result, date
        # For each position key → encode → INSERT into vote_positions
```

**Success conditions**:
- House votes (chamber='h') in `votes` table: > 800 → FAILED if not met
- Senate votes (chamber='s') in `votes` table: > 400 → FAILED if not met
- Legislators in table: > 400 → FAILED if not met
- Print actual counts

---

### step_02_filter_votes.py

**Purpose**: Set `is_discretionary=1` on qualifying votes. Verify minimum counts.

**Inputs**: `data/votes.db`

**Outputs**: Updated `votes.is_discretionary` column; methodology log entry; status JSON

**Logic**:
```sql
-- Reset first (idempotency)
UPDATE votes SET is_discretionary = 0;

-- Non-nomination inclusion
UPDATE votes SET is_discretionary = 1
WHERE category IN ('passage','passage-suspension','amendment','cloture','veto-override');

-- Nomination: Senate only
UPDATE votes SET is_discretionary = 1
WHERE category = 'nomination' AND chamber = 's';
```
Log: total per chamber, excluded per chamber, included per chamber, exclusion fraction.

**Success conditions**:
- House discretionary votes (chamber='h', is_discretionary=1): ≥ 300
- Senate discretionary votes (chamber='s', is_discretionary=1): ≥ 300
- If either < 300: FAILED (per brief: "review category classifications before proceeding")

---

### step_03_build_matrix.py

**Purpose**: Build legislator × vote numpy arrays; exclude low-coverage legislators.

**Inputs**: `data/votes.db`

**Outputs**:
- `output/matrix_house.npy` — shape (n_legislators, n_votes)
- `output/matrix_senate.npy`
- `output/legislators_house.csv` — columns: `bioguide_id, display_name, party, state, row_idx`
- `output/legislators_senate.csv`
- `output/votes_house.csv` — columns: `vote_id, category, question, date, col_idx`
- `output/votes_senate.csv`

**Logic**:
```python
for chamber in ['h', 's']:
    # 1. Get all discretionary vote_ids for chamber (ordered by date)
    # 2. Get all legislators for chamber from legislators table
    # 3. Build dict: bioguide_id → row index
    # 4. Build dict: vote_id → col index
    # 5. Initialize matrix: np.zeros((n_legs, n_votes), dtype=np.int8)
    # 6. Fill matrix from vote_positions WHERE vote_id IN discretionary_votes
    # 7. Compute coverage per legislator:
    #    coverage[i] = count of non-zero values in row i / n_votes
    #    Exclude rows where coverage < 0.50
    #    Document excluded legislators (bioguide_id, display_name, coverage)
    # 8. Re-index remaining legislators, save arrays + CSVs
```

**Success conditions**:
- House matrix: n_legislators ≥ 100, n_votes ≥ 300, no NaN
- Senate matrix: n_legislators ≥ 40, n_votes ≥ 300, no NaN
- Kickback if these are not met

---

### step_04_pca.py

**Purpose**: PCA + parallel analysis per chamber; sanity checks; plots; component labels placeholder.

**Inputs**:
- `output/matrix_{chamber}.npy`
- `output/legislators_{chamber}.csv`
- `output/votes_{chamber}.csv`

**Outputs**:
- `output/eigenvalue_spectrum_{chamber}.html`
- `output/pca_space_{chamber}.html`
- `output/loadings_{chamber}.csv` — columns: `component_idx, direction, vote_id, loading, question, category, date`
- `output/scores_{chamber}.csv` — columns: `bioguide_id, display_name, party, state, pc0, pc1, ...`
  (only retained component columns; column names are `pc0`, `pc1`, etc.)
- `output/component_labels.json` (created/overwritten at end of step)

**Logic per chamber**:
```python
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

X = np.load(f"output/matrix_{chamber}.npy").astype(float)
X_scaled = StandardScaler().fit_transform(X)  # scale votes (columns), not legislators

pca = PCA(random_state=42)
pca.fit(X_scaled)
eigenvalues = pca.explained_variance_

thresholds = parallel_analysis(X_scaled, n_iter=1000, percentile=95, random_state=42)
retained = [i for i in range(len(thresholds)) if eigenvalues[i] > thresholds[i]]
# Must retain at least 2 → KICKBACK if fewer

# Sanity check: PC1 vs party
leg_df = pd.read_csv(f"output/legislators_{chamber}.csv")
scores_all = pca.transform(X_scaled)
pc1_scores = scores_all[:, 0]
party_binary = leg_df['party'].map({'Democrat': 1, 'Republican': 0}).fillna(0.5)
r2 = np.corrcoef(pc1_scores, party_binary)[0, 1] ** 2
# r2 < 0.7 → KICKBACK; r2 > 0.95 → log warning only

# Scree plot: line chart of eigenvalues + parallel thresholds, vertical line at last retained
# Mark retained vs not retained

# Loadings: for each retained component, top 20 positive + top 20 negative loading votes
# Join vote descriptions from votes_{chamber}.csv

# Scores CSV: retained components only (pc0, pc1, ...)

# PCA space plot: scatter pc0 vs pc1, color='party', hover='display_name + state'
```

**component_labels.json** (exact format):
```json
{
  "warning": "No human interpretation applied — all labels are automated placeholders",
  "automated": true,
  "house": {"0": "uninterpreted-0", "1": "uninterpreted-1"},
  "senate": {"0": "uninterpreted-0", "1": "uninterpreted-1"}
}
```
Keys in `house`/`senate` dicts are string indices matching retained component count.

**Kickback conditions**:
- Retained components < 2 for either chamber
- PC1 r² with party < 0.70 for either chamber (write specific r² value in kickback)

**Success conditions**:
- ≥ 2 retained components per chamber
- PC1 r² in [0.70, 0.99] for both chambers
- All output files saved

---

### step_05_hitl.py (scaffolding only — NOT executed in iteration 1)

**Purpose**: Interactive human review of PCA components with Ollama candidate naming.

**Inputs**:
- `output/loadings_{chamber}.csv`
- `output/component_labels.json`
- Local ollama with `llama3:8b` pulled

**Outputs**:
- `output/component_labels.json` (overwritten with human-confirmed labels)

**Logic**:
```python
import ollama

PROMPT_TEMPLATE = """These votes load positively on a latent dimension in Congressional voting behavior:
{positive}

These votes load negatively on the same dimension:
{negative}

In one short phrase, what interest or value distinction might this dimension represent?
Be specific about whose interests are on each side. Do not use party labels.
Respond with only the candidate phrase, no explanation."""

for chamber in ['house', 'senate']:
    for comp_idx in retained_indices:
        # Print top 10 positive loading votes (question + category)
        # Print top 10 negative loading votes
        response = ollama.generate(model='llama3:8b', prompt=PROMPT_TEMPLATE.format(...))
        candidate = response['response'].strip()
        print(f"Candidate label: {candidate}")
        human_input = input("Accept [Enter], modify, or 'skip': ").strip()
        if human_input == '':
            label = candidate
        elif human_input.lower() == 'skip':
            label = f"uninterpreted-{comp_idx}"
        else:
            label = human_input
        labels[chamber][str(comp_idx)] = label

# Write updated component_labels.json (remove "automated": true, "warning" key)
```

Note: this script intentionally blocks on stdin. Run interactively only.

---

### step_06_ssa.py

**Purpose**: Non-metric MDS on legislator pairwise distances in component space.

**Inputs**:
- `output/scores_{chamber}.csv`
- `output/component_labels.json`

**Outputs**:
- `output/ssa_geometry_{chamber}.html` (2D or 3D depending on stress)

**Logic per chamber**:
```python
from sklearn.manifold import MDS
from scipy.spatial.distance import pdist, squareform

scores_df = pd.read_csv(f"output/scores_{chamber}.csv")
labels_json = json.load(open("output/component_labels.json"))
pc_cols = [f"pc{i}" for i in range(len(labels_json[chamber]))]
X = scores_df[pc_cols].values

dist_matrix = squareform(pdist(X, metric='correlation'))
dist_matrix = np.clip(dist_matrix, 0, 2)

mds = MDS(n_components=2, metric=False, dissimilarity='precomputed',
          n_init=10, max_iter=1000, random_state=42)
coords = mds.fit_transform(dist_matrix)
kruskal = np.sqrt(mds.stress_ / np.sum(dist_matrix**2))

if kruskal > 0.15:
    mds3 = MDS(n_components=3, metric=False, dissimilarity='precomputed',
               n_init=10, max_iter=1000, random_state=42)
    coords = mds3.fit_transform(dist_matrix)
    kruskal = np.sqrt(mds3.stress_ / np.sum(dist_matrix**2))
    dims = 3
else:
    dims = 2

# Plot: color by party (for party sanity), hover: display_name + party + state
# 2D: px.scatter; 3D: px.scatter_3d
# Save HTML
```

**Success condition**: Kruskal stress < 0.20. If not, log warning but do not kickback.

---

### step_07_acquire_fec.py

**Purpose**: Download FEC Schedule B disbursements for each legislator.

**Inputs**:
- `.env` (FEC_API_KEY required — exit cleanly if missing/placeholder)
- `data/votes.db` (legislators table for FEC candidate IDs)
- `output/legislators_house.csv` + `output/legislators_senate.csv` (to compute match rate)

**Outputs**:
- `fec_disbursements` table populated
- `fec_committees` table populated

**Logic**:
```python
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("FEC_API_KEY", "")
if not api_key or api_key == "your_key_here":
    print("ERROR: Set FEC_API_KEY in .env before running step_07")
    sys.exit(1)

# 1. Load all legislators with non-null fec_candidate_id from DB
# 2. committee_type_cache = {}  (avoid redundant API calls)
# 3. For each (fec_id, legislator) x each cycle in [2022, 2024]:
#    - paginate Schedule B API per spec above
#    - collect transactions: transaction_id, committee_id, disbursement_amount, disbursement_date
# 4. For each unique committee_id seen:
#    if not in cache:
#      GET https://api.open.fec.gov/v1/committee/{committee_id}/?api_key=...
#      extract: committee_type, committee_type_full, org_type, org_type_full, name
#      INSERT OR REPLACE into fec_committees; cache it; sleep 0.1s
# 5. INSERT OR IGNORE all disbursements into fec_disbursements
# 6. Compute match rate:
#    legislators_in_matrices = union of bioguide_ids in both legislators_{chamber}.csv files
#    join with legislators table to get fec_candidate_ids
#    matched = count of legislators_in_matrices that have ≥ 1 row in fec_disbursements
#    match_rate = matched / len(legislators_in_matrices)
#    if match_rate < 0.80: KICKBACK with match_rate value + list of unmatched bioguide_ids
```

**Kickback condition**: Match rate < 0.80

---

### step_08_interest_overlay.py

**Purpose**: Correlate PCA component scores with FEC industry disbursements.

**Inputs**:
- `data/votes.db` (fec_disbursements, fec_committees, legislators)
- `output/scores_{chamber}.csv`
- `output/component_labels.json`

**Outputs**:
- `output/interest_correlation_table.csv` — columns: `chamber, component_idx, component_label, industry_type, pearson_r, p_value`
- `output/interest_correlation_heatmap_{chamber}.html`

**Logic per chamber**:
```python
from scipy.stats import pearsonr

# 1. Load scores_df; get pc_cols from component_labels.json
# 2. SQL query: aggregate disbursements by (recipient_candidate_id, committee_type_full)
#    SELECT l.bioguide_id,
#           fc.committee_type_full AS industry,
#           SUM(fd.disbursement_amount) AS total_amount
#    FROM fec_disbursements fd
#    JOIN fec_committees fc ON fd.committee_id = fc.committee_id
#    JOIN legislators l ON fd.recipient_candidate_id = l.fec_candidate_id
#    WHERE l.chamber = '{chamber}'
#    GROUP BY l.bioguide_id, fc.committee_type_full
# 3. Pivot to DataFrame: rows=bioguide_id, cols=industry, fill 0
# 4. Apply log1p to all industry columns
# 5. Join to scores_df on bioguide_id (inner join — only matched legislators)
# 6. For each pc_col x each industry col: pearsonr → (r, p)
# 7. Record top/bottom 5 per component in log
```

**Success condition**: Analysis completes. If all |r| < 0.15 across all components and industries, log warning (not a failure — valid finding per brief).

---

### step_09_cluster_output.py

**Purpose**: Cluster legislators in PCA space; produce final visualizations and summary tables.

**Inputs**:
- `output/scores_{chamber}.csv`
- `output/component_labels.json`
- `output/interest_correlation_table.csv`
- `data/votes.db` (for legislator names/party/state)

**Outputs**:
- `output/clusters_final.html`
- `output/cluster_summary_table.csv` — columns: `chamber, cluster_id, n_legislators, n_democrat, n_republican, n_independent, pct_minority_party, dominant_industry, dominant_r, representative_legislators`
- `output/methodology_log.md` (appended — silhouette score, cluster counts, method used)

**Logic per chamber**:
```python
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.metrics import silhouette_score

X = scores_df[pc_cols].values
n_legs = len(X)

# Try HDBSCAN
hdb = HDBSCAN(min_cluster_size=max(5, n_legs // 20), min_samples=3)
labels_hdb = hdb.fit_predict(X)
n_meaningful = len(set(labels_hdb) - {-1})

if n_meaningful >= 2:
    labels = labels_hdb
    method = "HDBSCAN"
    non_noise = labels != -1
    if non_noise.sum() > 1:
        sil = silhouette_score(X[non_noise], labels[non_noise])
    else:
        sil = 0.0
else:
    # k-means fallback
    best_k, best_sil, best_labels = 2, -1, None
    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        lbl = km.fit_predict(X)
        s = silhouette_score(X, lbl)
        if s > best_sil:
            best_k, best_sil, best_labels = k, s, lbl
    labels = best_labels
    method = f"KMeans(k={best_k})"
    sil = best_sil
```

**Success conditions**:
- Silhouette score ≥ 0.3 OR at least 2 meaningful HDBSCAN clusters
- At least 1 cluster with ≥ 10% minority-party members
- If silhouette < 0.3 and using k-means: log warning but continue (not a kickback)

**Final combined plot** (`clusters_final.html`):
- Use MDS coords from `output/ssa_geometry_{chamber}.html` if available, else PCA pc0/pc1
- Actually: re-read MDS is not saved as data, only as HTML. Use PCA pc0/pc1 for cluster plot.
- Combined plot: one subplot per chamber or single plot with chamber as symbol shape
- Color by cluster_id, hover text: `f"{display_name} | {party} | {state}"`

---

## Execution Readiness Checklist

Before running the execution sequence, verify:
- [ ] Python 3.11+ active (`python --version`)
- [ ] FEC API key obtained and placed in `.env` (free at https://api.open.fec.gov/developers/)
- [ ] ollama installed and `llama3:8b` pulled (only required for Step 5, which runs interactively later)
- [ ] Internet available (Steps 1 and 7 only)

Steps 0–4 and 6 run without FEC API key. FEC key only blocks Step 7 and downstream.

---

## Open Question Before Execution

**FEC data semantics**: The brief says "Schedule B disbursements — payments from committees to candidates."
In FEC data, Schedule B is disbursements *made by* a committee. Querying it with
`recipient_candidate_id` gives us money flowing from PACs/parties to candidates,
with the paying committee's `committee_type_full` as the industry proxy.
This is what the plan implements. If you intended a different FEC endpoint or a
different industry categorization (e.g., OpenSecrets industry sectors), say so
before Step 7 runs.
