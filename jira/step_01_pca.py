"""
JIRA Ticket Dimension Analysis — Step 1: PCA
Builds a feature matrix from GFG_FINAL.csv (TF-IDF on text + one-hot
categoricals), runs PCA with parallel analysis, and writes interactive
HTML plots to jira/output/.
"""

import os, re
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("jira/output", exist_ok=True)

# ── 1. Load & deduplicate ────────────────────────────────────────────────────

df = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()
print(f"Unique tickets: {len(raw)}")

# ── 2. Outcome ordinal ───────────────────────────────────────────────────────

fmt = "%d/%b/%Y %I:%M %p"
raw["created_dt"]  = pd.to_datetime(raw["Created"],  format=fmt, errors="coerce")
raw["resolved_dt"] = pd.to_datetime(raw["Resolved"], format=fmt, errors="coerce")
raw["resolution_hours"] = (raw["resolved_dt"] - raw["created_dt"]).dt.total_seconds() / 3600

NO_ACTION = {
    "Spam", "Invalid", "Incorrectly Filed", "Duplicate",
    "Not a bug", "Cannot Reproduce", "Incomplete",
}
GENUINE = {"Fixed", "Resolved Locally", "Done", "Answered"}

_SPAM_RE = re.compile(r"(?i)(male\s+enhancement|primal\s+beast)", re.IGNORECASE)

def _is_spam_summary(s):
    if not isinstance(s, str):
        return False
    s = s.strip()
    return len(s) <= 5 or bool(_SPAM_RE.search(s))

raw["_spam_fixed"] = (
    raw["Resolution"].isin(GENUINE) & raw["Summary"].apply(_is_spam_summary)
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

def _outcome(row):
    res = row["Resolution"]
    hrs = row["resolution_hours"]
    if (isinstance(res, str) and res in NO_ACTION) or row["_spam_fixed"]:
        return 0
    if isinstance(res, str) and res in GENUINE:
        if pd.isna(hrs):
            return None
        if hrs < 24:       return 1
        if hrs < 24 * 7:   return 2
        if hrs < 24 * 30:  return 3
        if hrs < 24 * 180: return 4
        return 5
    return 6

raw["outcome"] = raw.apply(_outcome, axis=1)
raw = raw[raw["outcome"].notna()].copy()
raw["outcome"] = raw["outcome"].astype(int)
print(f"Tickets after dropping null outcomes: {len(raw)}")
print(raw["outcome"].value_counts().sort_index().rename(OUTCOME_LABELS).to_string())
print()

# ── 3. Feature engineering ───────────────────────────────────────────────────

# 3a. Categorical one-hot
# Normalise Symptom Severity naming variants
sev_map = {
    "Severity 1 - Critical": "Critical",
    "Severity 2 - Major":    "Major",
    "Severity 3 - Minor":    "Minor",
    "Minor": "Minor",
    "Major": "Major",
}
raw["severity_norm"] = raw["Custom field (Symptom Severity)"].map(sev_map).fillna("Unknown")

# Top components only; bucket rare ones
top_components = raw["Component/s"].value_counts().nlargest(8).index
raw["component_norm"] = raw["Component/s"].where(
    raw["Component/s"].isin(top_components), other="Other"
).fillna("Unknown")

cat_cols = {
    "Issue Type":       "issuetype",
    "Priority":         "priority",
    "severity_norm":    "severity",
    "component_norm":   "component",
}

cat_frames = []
for src, prefix in cat_cols.items():
    dummies = pd.get_dummies(
        raw[src].fillna("Unknown"),
        prefix=prefix,
        dtype=float,
    )
    cat_frames.append(dummies)

cat_df = pd.concat(cat_frames, axis=1)
print(f"Categorical features: {cat_df.shape[1]}")

# 3b. Temporal features
export_date = raw["created_dt"].max()
raw["age_days"]    = (export_date - raw["created_dt"]).dt.days
raw["created_dow"] = raw["created_dt"].dt.dayofweek          # 0=Mon
raw["created_mon"] = raw["created_dt"].dt.month

# Date of first response lag (hours) — NaN → -1 sentinel then impute with median
raw["first_response_dt"] = pd.to_datetime(
    raw["Custom field (Date of First Response)"], errors="coerce"
)
raw["first_response_hrs"] = (
    (raw["first_response_dt"] - raw["created_dt"]).dt.total_seconds() / 3600
)
fr_median = raw["first_response_hrs"].median()
raw["first_response_hrs"] = raw["first_response_hrs"].fillna(fr_median)
raw["has_first_response"]  = raw["Custom field (Date of First Response)"].notna().astype(float)

temporal_df = raw[["age_days", "created_dow", "created_mon",
                    "first_response_hrs", "has_first_response"]].copy()
print(f"Temporal features: {temporal_df.shape[1]}")

# 3c. TF-IDF on Summary + Description
def clean_text(s):
    if not isinstance(s, str):
        return ""
    s = re.sub(r"https?://\S+",        " ", s)   # URLs
    s = re.sub(r"!\S+!",               " ", s)   # JIRA image macros
    s = re.sub(r"\{[^}]+\}",           " ", s)   # JIRA markup blocks
    s = re.sub(r"[^\w\s]",             " ", s)   # punctuation
    s = re.sub(r"\b\d+\b",             " ", s)   # bare numbers
    s = s.lower().strip()
    return s

EXTRA_STOP = {
    "sourcetree", "jira", "hi", "hello", "thanks", "thank", "please",
    "would", "could", "should", "using", "used", "use", "like", "also",
    "one", "two", "get", "got", "see", "seem", "seems", "still",
    "http", "https", "com", "www",
}

raw["text"] = raw["Summary"].apply(clean_text) + " " + raw["Description"].apply(clean_text)

tfidf = TfidfVectorizer(
    max_features=250,
    min_df=4,
    max_df=0.75,
    sublinear_tf=True,
    ngram_range=(1, 2),
    stop_words="english",
)
tfidf_matrix = tfidf.fit_transform(raw["text"])
tfidf_df = pd.DataFrame(
    tfidf_matrix.toarray(),
    columns=[f"tfidf_{t}" for t in tfidf.get_feature_names_out()],
    index=raw.index,
)
print(f"TF-IDF features: {tfidf_df.shape[1]}")

# 3d. Combine
feature_df = pd.concat([cat_df, temporal_df, tfidf_df], axis=1)
print(f"Total features before scaling: {feature_df.shape[1]}")
print()

# ── 4. Scale & PCA ───────────────────────────────────────────────────────────

scaler  = StandardScaler()
X_scaled = scaler.fit_transform(feature_df)

pca = PCA(n_components=min(50, feature_df.shape[1]))
scores = pca.fit_transform(X_scaled)
loadings = pca.components_  # shape (n_components, n_features)

print(f"PCA explained variance (first 15 PCs):")
cumvar = np.cumsum(pca.explained_variance_ratio_)
for i in range(15):
    ev = pca.explained_variance_[i]
    pct = pca.explained_variance_ratio_[i] * 100
    print(f"  PC{i+1:2d}: eigenvalue={ev:.3f}  var={pct:.1f}%  cum={cumvar[i]*100:.1f}%")
print()

# ── 5. Parallel analysis (permutation-based significance) ───────────────────

N_PERM = 100
rng = np.random.default_rng(42)
perm_eigenvalues = np.zeros((N_PERM, pca.n_components_))

X_perm = X_scaled.copy()
for p in range(N_PERM):
    X_shuffled = np.apply_along_axis(rng.permutation, 0, X_perm)
    pca_perm = PCA(n_components=pca.n_components_)
    pca_perm.fit(X_shuffled)
    perm_eigenvalues[p] = pca_perm.explained_variance_

pa_threshold = np.percentile(perm_eigenvalues, 95, axis=0)
n_sig = int(np.sum(pca.explained_variance_ > pa_threshold))
print(f"Parallel analysis: {n_sig} significant components (eigenvalue > 95th-pct random)")
print()

# ── 6. Plots ─────────────────────────────────────────────────────────────────

feature_names = feature_df.columns.tolist()
outcome_color = raw["outcome"].map(OUTCOME_LABELS)

# — 6a. Scree plot with PA threshold —
fig_scree = go.Figure()
x_range = list(range(1, 21))

fig_scree.add_trace(go.Scatter(
    x=x_range, y=pca.explained_variance_[:20],
    mode="lines+markers", name="Observed eigenvalues",
    line=dict(color="#1f77b4", width=2),
    marker=dict(size=6),
))
fig_scree.add_trace(go.Scatter(
    x=x_range, y=pa_threshold[:20],
    mode="lines", name="PA 95th-pct threshold",
    line=dict(color="#d62728", dash="dash"),
))
fig_scree.update_layout(
    title="Eigenvalue Spectrum with Parallel Analysis Threshold",
    xaxis_title="Component", yaxis_title="Eigenvalue",
    template="plotly_white", width=800, height=450,
)
fig_scree.write_html("jira/output/scree_plot.html")
print("Wrote: jira/output/scree_plot.html")

# — 6b. PC1 vs PC2 coloured by outcome —
scores_df = pd.DataFrame(scores[:, :10], columns=[f"PC{i+1}" for i in range(10)], index=raw.index)
scores_df["outcome_label"] = outcome_color.values
scores_df["issue_key"]     = raw["Issue key"].values
scores_df["summary"]       = raw["Summary"].values
scores_df["resolution"]    = raw["Resolution"].fillna("(open)").values
scores_df["priority"]      = raw["Priority"].fillna("Unknown").values
scores_df["component"]     = raw["component_norm"].values

COLOR_MAP = {
    "0-No-action disposal": "#9467bd",
    "1-Hours (<24h)":       "#2ca02c",
    "2-Days (1–7d)":        "#98df8a",
    "3-Weeks (1–4w)":       "#ffbb78",
    "4-Quarters (1–6mo)":   "#ff7f0e",
    "5-Years / long-tail":  "#d62728",
    "6-Never / ignored":    "#aec7e8",
}

fig_12 = px.scatter(
    scores_df, x="PC1", y="PC2",
    color="outcome_label",
    color_discrete_map=COLOR_MAP,
    hover_data={"issue_key": True, "summary": True,
                "resolution": True, "priority": True, "component": True},
    title="PCA Space — PC1 vs PC2 (coloured by outcome)",
    template="plotly_white", width=900, height=650,
)
fig_12.write_html("jira/output/pca_pc1_pc2.html")
print("Wrote: jira/output/pca_pc1_pc2.html")

# — 6c. PC1 vs PC3 —
fig_13 = px.scatter(
    scores_df, x="PC1", y="PC3",
    color="outcome_label",
    color_discrete_map=COLOR_MAP,
    hover_data={"issue_key": True, "summary": True,
                "resolution": True, "priority": True, "component": True},
    title="PCA Space — PC1 vs PC3 (coloured by outcome)",
    template="plotly_white", width=900, height=650,
)
fig_13.write_html("jira/output/pca_pc1_pc3.html")
print("Wrote: jira/output/pca_pc1_pc3.html")

# — 6d. Top loadings per component —
N_SHOW = 15
loading_rows = []
for pc_i in range(min(n_sig, 10)):
    top_idx    = np.argsort(np.abs(loadings[pc_i]))[::-1][:N_SHOW]
    for rank, fi in enumerate(top_idx):
        loading_rows.append({
            "PC": f"PC{pc_i+1}",
            "feature": feature_names[fi],
            "loading": loadings[pc_i, fi],
            "abs_loading": abs(loadings[pc_i, fi]),
            "rank": rank + 1,
        })

load_df = pd.DataFrame(loading_rows)

fig_loads = px.bar(
    load_df, x="loading", y="feature", color="loading",
    facet_col="PC", facet_col_wrap=3,
    color_continuous_scale="RdBu",
    color_continuous_midpoint=0,
    title=f"Top {N_SHOW} Feature Loadings per Significant Component",
    template="plotly_white", height=400 * ((min(n_sig, 10) + 2) // 3),
)
fig_loads.update_yaxes(matches=None, showticklabels=True)
fig_loads.write_html("jira/output/pca_loadings.html")
print("Wrote: jira/output/pca_loadings.html")

# — 6e. Outcome distribution across PC1 quartiles —
scores_df["PC1_quartile"] = pd.qcut(scores_df["PC1"], q=4,
                                     labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"])
quartile_dist = (
    scores_df.groupby(["PC1_quartile", "outcome_label"], observed=True)
    .size().reset_index(name="count")
)
fig_qdist = px.bar(
    quartile_dist, x="PC1_quartile", y="count", color="outcome_label",
    color_discrete_map=COLOR_MAP, barmode="stack",
    title="Outcome Distribution by PC1 Quartile",
    template="plotly_white", width=750, height=450,
)
fig_qdist.write_html("jira/output/pc1_outcome_quartiles.html")
print("Wrote: jira/output/pc1_outcome_quartiles.html")

# ── 7. Save scores + metadata ────────────────────────────────────────────────

export_cols = (
    ["Issue key", "Summary", "Issue Type", "Priority", "Resolution",
     "component_norm", "severity_norm", "outcome", "resolution_hours"]
    + [f"PC{i+1}" for i in range(min(10, pca.n_components_))]
)

out_df = pd.concat([
    raw[["Issue key", "Summary", "Issue Type", "Priority", "Resolution",
         "component_norm", "severity_norm", "outcome", "resolution_hours"]].reset_index(drop=True),
    scores_df[[f"PC{i+1}" for i in range(min(10, pca.n_components_))]].reset_index(drop=True),
], axis=1)

out_df.to_csv("jira/output/pca_scores.csv", index=False)
print("Wrote: jira/output/pca_scores.csv")

print()
print("Done.")
