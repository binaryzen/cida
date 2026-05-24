"""
JIRA Ticket Dimension Analysis — Step 2: PCA vs NMF comparison
Cleans stack trace boilerplate from ticket text, then runs:
  - PCA on scaled (TF-IDF + categoricals + temporal)
  - NMF on TF-IDF only (pure topic model; requires non-negative input)
Writes comparison plots to jira/output/.
"""

import os, re
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA, NMF
from sklearn.feature_extraction.text import TfidfVectorizer
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("jira/output", exist_ok=True)

# ── 1. Load & deduplicate ────────────────────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

fmt = "%d/%b/%Y %I:%M %p"
raw["created_dt"]  = pd.to_datetime(raw["Created"],  format=fmt, errors="coerce")
raw["resolved_dt"] = pd.to_datetime(raw["Resolved"], format=fmt, errors="coerce")
raw["resolution_hours"] = (raw["resolved_dt"] - raw["created_dt"]).dt.total_seconds() / 3600

# ── 2. Outcome ordinal (same as step 01) ────────────────────────────────────

NO_ACTION = {"Spam", "Invalid", "Incorrectly Filed", "Duplicate",
             "Not a bug", "Cannot Reproduce", "Incomplete"}
GENUINE   = {"Fixed", "Resolved Locally", "Done", "Answered"}
_SPAM_RE  = re.compile(r"(?i)(male\s+enhancement|primal\s+beast)")

raw["_spam_fixed"] = (
    raw["Resolution"].isin(GENUINE)
    & raw["Summary"].apply(
        lambda s: len(str(s).strip()) <= 5 or bool(_SPAM_RE.search(str(s)))
    )
)

OUTCOME_LABELS = {
    0: "0-No-action disposal",
    1: "1-Hours (<24h)",
    2: "2-Days (1–7d)",
    3: "3-Weeks (1–4w)",
    4: "4-Quarters (1–6mo)",
    5: "5-Years / long-tail",
    6: "6-Never / ignored",
}
COLOR_MAP = {
    "0-No-action disposal": "#9467bd",
    "1-Hours (<24h)":       "#2ca02c",
    "2-Days (1–7d)":        "#98df8a",
    "3-Weeks (1–4w)":       "#ffbb78",
    "4-Quarters (1–6mo)":   "#ff7f0e",
    "5-Years / long-tail":  "#d62728",
    "6-Never / ignored":    "#aec7e8",
}

def _outcome(row):
    res, hrs = row["Resolution"], row["resolution_hours"]
    if (isinstance(res, str) and res in NO_ACTION) or row["_spam_fixed"]:
        return 0
    if isinstance(res, str) and res in GENUINE:
        if pd.isna(hrs): return None
        if hrs < 24:       return 1
        if hrs < 168:      return 2
        if hrs < 720:      return 3
        if hrs < 4320:     return 4
        return 5
    return 6

raw["outcome"] = raw.apply(_outcome, axis=1)
raw = raw[raw["outcome"].notna()].copy()
raw["outcome"] = raw["outcome"].astype(int)
raw["outcome_label"] = raw["outcome"].map(OUTCOME_LABELS)

# ── 3. Stack-trace-aware text cleaning ──────────────────────────────────────

# Patterns that signal a stack-trace or assembly-binding line
_STACK_LINE = re.compile(
    r"""
    ^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(   # stack frame:  at Foo.Bar.Baz(
    | Version=\d+\.\d+                   # assembly version
    | Culture=neutral                    # assembly culture
    | PublicKeyToken=                    # assembly token
    | Could\s+not\s+load\s+file\s+or\s+assembly
    | ---+\s*(End\s+of|inner)           # inner-exception divider
    | ^\s*\w+(\.\w+){3,}Exception[:\s]  # deep-namespaced exception class
    | [A-Za-z]:\\[^\s]{4,}              # Windows absolute path
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# General token noise (applied after line removal)
_TOKEN_NOISE = re.compile(
    r"https?://\S+"           # URLs
    r"|!\S+!"                 # JIRA image macros  !filename.png!
    r"|\{[^}]*\}"             # JIRA markup blocks  {code} {noformat}
    r"|[^\w\s]"               # punctuation
    r"|\b\d[\d.]*\d\b"        # version numbers / pure numbers
    r"|\b[a-f0-9]{6,}\b"      # hex strings
)


def clean_text(summary, description):
    # Combine; strip stack-trace lines from description only
    desc_lines = str(description).splitlines() if isinstance(description, str) else []
    clean_lines = [ln for ln in desc_lines if not _STACK_LINE.search(ln)]
    text = str(summary) + " " + " ".join(clean_lines)
    text = _TOKEN_NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).lower().strip()
    return text


raw["text_clean"] = raw.apply(
    lambda r: clean_text(r["Summary"], r["Description"]), axis=1
)

# Quick sanity: top unigrams before vs after
print("Sample cleaned text (first ticket):")
print(" ", raw["text_clean"].iloc[0][:300])
print()

# ── 4. TF-IDF ────────────────────────────────────────────────────────────────

tfidf = TfidfVectorizer(
    max_features=300,
    min_df=4,
    max_df=0.75,
    sublinear_tf=True,
    ngram_range=(1, 2),
    stop_words="english",
)
T = tfidf.fit_transform(raw["text_clean"])          # sparse (n_tickets × n_terms)
vocab  = tfidf.get_feature_names_out()
T_dense = T.toarray()
print(f"TF-IDF matrix: {T_dense.shape}  (tickets × terms)")

# ── 5. Categorical + temporal features (for PCA) ────────────────────────────

sev_map = {"Severity 1 - Critical": "Critical", "Severity 2 - Major": "Major",
           "Severity 3 - Minor": "Minor", "Minor": "Minor", "Major": "Major"}
raw["severity_norm"]   = raw["Custom field (Symptom Severity)"].map(sev_map).fillna("Unknown")
top_comp = raw["Component/s"].value_counts().nlargest(8).index
raw["component_norm"]  = raw["Component/s"].where(
    raw["Component/s"].isin(top_comp), other="Other").fillna("Unknown")

cat_frames = []
for src, pfx in [("Issue Type", "issuetype"), ("Priority", "priority"),
                 ("severity_norm", "severity"), ("component_norm", "component")]:
    cat_frames.append(pd.get_dummies(raw[src].fillna("Unknown"), prefix=pfx, dtype=float))
cat_df = pd.concat(cat_frames, axis=1)

export_date = raw["created_dt"].max()
raw["age_days"]           = (export_date - raw["created_dt"]).dt.days
raw["created_dow"]        = raw["created_dt"].dt.dayofweek
raw["created_mon"]        = raw["created_dt"].dt.month
raw["first_response_dt"]  = pd.to_datetime(
    raw["Custom field (Date of First Response)"], errors="coerce")
raw["first_response_hrs"] = (
    (raw["first_response_dt"] - raw["created_dt"]).dt.total_seconds() / 3600
).fillna(lambda s: s.median())
raw["has_first_response"] = raw["Custom field (Date of First Response)"].notna().astype(float)
# fill median properly
fr = (raw["first_response_dt"] - raw["created_dt"]).dt.total_seconds() / 3600
raw["first_response_hrs"] = fr.fillna(fr.median())

temporal_df = raw[["age_days", "created_dow", "created_mon",
                    "first_response_hrs", "has_first_response"]]

# ── 6. PCA ───────────────────────────────────────────────────────────────────

tfidf_cat_df = pd.concat(
    [cat_df.reset_index(drop=True),
     temporal_df.reset_index(drop=True),
     pd.DataFrame(T_dense, columns=[f"t_{v}" for v in vocab])],
    axis=1,
)
feat_names_pca = tfidf_cat_df.columns.tolist()

X_pca = StandardScaler().fit_transform(tfidf_cat_df)

pca = PCA(n_components=50, random_state=42)
pca_scores = pca.fit_transform(X_pca)

# Parallel analysis for significance cutoff
N_PERM = 100
rng = np.random.default_rng(42)
perm_ev = np.zeros((N_PERM, 50))
for p in range(N_PERM):
    Xs = np.apply_along_axis(rng.permutation, 0, X_pca)
    perm_ev[p] = PCA(n_components=50, random_state=0).fit(Xs).explained_variance_
pa95 = np.percentile(perm_ev, 95, axis=0)
n_sig_pca = int(np.sum(pca.explained_variance_ > pa95))
print(f"PCA: {n_sig_pca} significant components (parallel analysis 95th pct)")

print("PCA explained variance (first 12):")
cumvar = np.cumsum(pca.explained_variance_ratio_)
for i in range(12):
    print(f"  PC{i+1:2d}: ev={pca.explained_variance_[i]:.3f}  "
          f"var={pca.explained_variance_ratio_[i]*100:.1f}%  "
          f"cum={cumvar[i]*100:.1f}%  "
          f"r_outcome={np.corrcoef(pca_scores[:,i], raw['outcome'])[0,1]:+.3f}")
print()

# ── 7. NMF ───────────────────────────────────────────────────────────────────

N_TOPICS = 12   # fixed; NMF has no parallel-analysis equivalent

nmf = NMF(n_components=N_TOPICS, random_state=42, max_iter=400, init="nndsvda")
nmf_scores = nmf.fit_transform(T)          # (n_tickets × n_topics)  non-negative
W = nmf.components_                        # (n_topics × n_terms)

print(f"NMF: {N_TOPICS} topics on TF-IDF matrix")
print(f"Reconstruction error: {nmf.reconstruction_err_:.4f}")
print("NMF topic–outcome correlations:")
for k in range(N_TOPICS):
    r = np.corrcoef(nmf_scores[:, k], raw["outcome"])[0, 1]
    print(f"  Topic {k+1:2d}: r={r:+.3f}")
print()

# ── 8. Shared helper ─────────────────────────────────────────────────────────

def top_terms(weights, vocab, n=12):
    idx = np.argsort(weights)[::-1][:n]
    return [(vocab[i], float(weights[i])) for i in idx]

# ── 9. Print interpretations ─────────────────────────────────────────────────

print("=" * 60)
print("PCA top loadings (first 8 significant components)")
print("=" * 60)
for pc in range(min(8, n_sig_pca)):
    pos = np.argsort(pca.components_[pc])[::-1][:8]
    neg = np.argsort(pca.components_[pc])[:8]
    r   = np.corrcoef(pca_scores[:, pc], raw["outcome"])[0, 1]
    print(f"\nPC{pc+1} (var={pca.explained_variance_ratio_[pc]*100:.1f}%  r={r:+.3f})")
    print("  + " + "  ".join(f"{feat_names_pca[i]}({pca.components_[pc,i]:+.3f})" for i in pos))
    print("  - " + "  ".join(f"{feat_names_pca[i]}({pca.components_[pc,i]:+.3f})" for i in neg))

print()
print("=" * 60)
print("NMF topics — top terms")
print("=" * 60)
for k in range(N_TOPICS):
    terms = top_terms(W[k], vocab)
    r     = np.corrcoef(nmf_scores[:, k], raw["outcome"])[0, 1]
    n_tickets = int((nmf_scores[:, k] > 0.01).sum())
    print(f"\nTopic {k+1:2d}  (r={r:+.3f}  n~{n_tickets})")
    print("  " + "  |  ".join(f"{t} ({w:.3f})" for t, w in terms[:8]))

# ── 10. Plots ────────────────────────────────────────────────────────────────

outcome_label = raw["outcome_label"].values
issue_key     = raw["Issue key"].values
summary_txt   = raw["Summary"].values

# Helper: build hover-ready DataFrame
def score_frame(scores, prefix, n_cols=10):
    d = {f"{prefix}{i+1}": scores[:, i] for i in range(min(n_cols, scores.shape[1]))}
    d["outcome_label"] = outcome_label
    d["issue_key"]     = issue_key
    d["summary"]       = summary_txt
    d["priority"]      = raw["Priority"].fillna("Unknown").values
    d["component"]     = raw["component_norm"].values
    return pd.DataFrame(d)

pca_df = score_frame(pca_scores, "PC")
nmf_df = score_frame(nmf_scores, "T")

# — 10a. Scree + PA threshold —
fig_scree = go.Figure()
x = list(range(1, 21))
fig_scree.add_trace(go.Scatter(x=x, y=pca.explained_variance_[:20],
    mode="lines+markers", name="Observed", line=dict(color="#1f77b4", width=2)))
fig_scree.add_trace(go.Scatter(x=x, y=pa95[:20],
    mode="lines", name="PA 95th pct", line=dict(color="#d62728", dash="dash")))
fig_scree.update_layout(title="Scree Plot with Parallel Analysis Threshold (cleaned text)",
    xaxis_title="Component", yaxis_title="Eigenvalue",
    template="plotly_white", width=800, height=420)
fig_scree.write_html("jira/output/scree_clean.html")

# — 10b. PCA scatter PC1 vs PC2 —
fig_pca12 = px.scatter(pca_df, x="PC1", y="PC2", color="outcome_label",
    color_discrete_map=COLOR_MAP,
    hover_data={"issue_key": True, "summary": True, "priority": True, "component": True},
    title="PCA (cleaned) — PC1 vs PC2", template="plotly_white", width=900, height=620)
fig_pca12.write_html("jira/output/pca_clean_pc1_pc2.html")

# — 10c. NMF scatter T1 vs T2 —
fig_nmf12 = px.scatter(nmf_df, x="T1", y="T2", color="outcome_label",
    color_discrete_map=COLOR_MAP,
    hover_data={"issue_key": True, "summary": True, "priority": True, "component": True},
    title="NMF — Topic 1 vs Topic 2", template="plotly_white", width=900, height=620)
fig_nmf12.write_html("jira/output/nmf_t1_t2.html")

# — 10d. Outcome correlation bar chart: PCA vs NMF —
pca_r  = [np.corrcoef(pca_scores[:, i], raw["outcome"])[0, 1] for i in range(min(12, n_sig_pca))]
nmf_r  = [np.corrcoef(nmf_scores[:, k], raw["outcome"])[0, 1] for k in range(N_TOPICS)]

fig_corr = make_subplots(rows=1, cols=2,
    subplot_titles=["PCA components vs outcome", "NMF topics vs outcome"])

fig_corr.add_trace(go.Bar(
    x=[f"PC{i+1}" for i in range(len(pca_r))], y=pca_r,
    marker_color=["#d62728" if r < 0 else "#1f77b4" for r in pca_r],
    name="PCA"), row=1, col=1)
fig_corr.add_trace(go.Bar(
    x=[f"T{k+1}" for k in range(len(nmf_r))], y=nmf_r,
    marker_color=["#d62728" if r < 0 else "#1f77b4" for r in nmf_r],
    name="NMF"), row=1, col=2)
fig_corr.update_layout(title="Correlation with Outcome Ordinal: PCA vs NMF",
    template="plotly_white", width=1100, height=420, showlegend=False)
fig_corr.update_yaxes(title_text="r", range=[-0.5, 0.5])
fig_corr.write_html("jira/output/outcome_corr_comparison.html")

# — 10e. NMF topic heatmap (outcome × topic membership) —
# Assign each ticket its dominant NMF topic
dominant_topic = nmf_scores.argmax(axis=1)
nmf_df["dominant_topic"] = [f"T{t+1}" for t in dominant_topic]

topic_outcome = (
    nmf_df.groupby(["dominant_topic", "outcome_label"], observed=True)
    .size().reset_index(name="count")
)
# Pivot to matrix for heatmap
pivot = topic_outcome.pivot(index="dominant_topic", columns="outcome_label", values="count").fillna(0)
# Normalise rows to proportions
pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

fig_heat = px.imshow(
    pivot_pct,
    text_auto=".0f",
    color_continuous_scale="Blues",
    title="NMF: Dominant Topic × Outcome Distribution (%)",
    labels=dict(x="Outcome", y="Dominant Topic", color="%"),
    aspect="auto",
    template="plotly_white",
    width=900, height=480,
)
fig_heat.write_html("jira/output/nmf_topic_outcome_heatmap.html")

# — 10f. PCA loadings for first 8 sig components —
N_SHOW = 12
load_rows = []
for pc in range(min(8, n_sig_pca)):
    top_idx = np.argsort(np.abs(pca.components_[pc]))[::-1][:N_SHOW]
    for fi in top_idx:
        load_rows.append({"PC": f"PC{pc+1}", "feature": feat_names_pca[fi],
                          "loading": pca.components_[pc, fi]})
load_df = pd.DataFrame(load_rows)
fig_loads = px.bar(load_df, x="loading", y="feature", color="loading",
    facet_col="PC", facet_col_wrap=4,
    color_continuous_scale="RdBu", color_continuous_midpoint=0,
    title="PCA (cleaned): Top Feature Loadings",
    template="plotly_white", height=420 * ((min(8, n_sig_pca) + 3) // 4))
fig_loads.update_yaxes(matches=None, showticklabels=True)
fig_loads.write_html("jira/output/pca_clean_loadings.html")

# — 10g. NMF topic term bars —
nmf_rows = []
for k in range(N_TOPICS):
    for term, weight in top_terms(W[k], vocab, n=12):
        r = np.corrcoef(nmf_scores[:, k], raw["outcome"])[0, 1]
        nmf_rows.append({"Topic": f"T{k+1} (r={r:+.2f})", "term": term, "weight": weight})
nmf_load_df = pd.DataFrame(nmf_rows)
fig_nmf_loads = px.bar(nmf_load_df, x="weight", y="term", color="weight",
    facet_col="Topic", facet_col_wrap=4,
    color_continuous_scale="Blues",
    title="NMF: Top Terms per Topic",
    template="plotly_white", height=420 * ((N_TOPICS + 3) // 4))
fig_nmf_loads.update_yaxes(matches=None, showticklabels=True)
fig_nmf_loads.write_html("jira/output/nmf_topic_terms.html")

print("\nOutput files:")
for f in sorted(os.listdir("jira/output")):
    if f.endswith(".html"):
        print(f"  jira/output/{f}")
print("\nDone.")
