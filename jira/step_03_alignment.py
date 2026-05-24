"""
JIRA Step 3: Topic alignment with categorical parameters
For each categorical field (Priority, Component, Severity, Issue Type,
Resolution group, Outcome), computes:
  - mean NMF topic weight per category (heatmap)
  - Cramer's V between dominant topic and each categorical field
  - incremental outcome variance explained by topics vs categoricals alone
"""

import os, re
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, f_oneway
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("jira/output", exist_ok=True)

# ── 1. Rebuild dataset (same as step_02) ────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

fmt = "%d/%b/%Y %I:%M %p"
raw["created_dt"]  = pd.to_datetime(raw["Created"],  format=fmt, errors="coerce")
raw["resolved_dt"] = pd.to_datetime(raw["Resolved"], format=fmt, errors="coerce")
raw["resolution_hours"] = (raw["resolved_dt"] - raw["created_dt"]).dt.total_seconds() / 3600

NO_ACTION = {"Spam","Invalid","Incorrectly Filed","Duplicate",
             "Not a bug","Cannot Reproduce","Incomplete"}
GENUINE   = {"Fixed","Resolved Locally","Done","Answered"}
_SPAM_RE  = re.compile(r"(?i)(male\s+enhancement|primal\s+beast)")

raw["_spam_fixed"] = (
    raw["Resolution"].isin(GENUINE)
    & raw["Summary"].apply(
        lambda s: len(str(s).strip()) <= 5 or bool(_SPAM_RE.search(str(s)))
    )
)

OUTCOME_LABELS = {
    0: "0-No-action",  1: "1-Hours",  2: "2-Days",
    3: "3-Weeks",      4: "4-Quarters", 5: "5-Years",  6: "6-Never",
}

def _outcome(row):
    res, hrs = row["Resolution"], row["resolution_hours"]
    if (isinstance(res, str) and res in NO_ACTION) or row["_spam_fixed"]: return 0
    if isinstance(res, str) and res in GENUINE:
        if pd.isna(hrs): return None
        if hrs < 24:  return 1
        if hrs < 168: return 2
        if hrs < 720: return 3
        if hrs < 4320:return 4
        return 5
    return 6

raw["outcome"] = raw.apply(_outcome, axis=1)
raw = raw[raw["outcome"].notna()].copy()
raw["outcome"] = raw["outcome"].astype(int)

sev_map = {"Severity 1 - Critical":"Critical","Severity 2 - Major":"Major",
           "Severity 3 - Minor":"Minor","Minor":"Minor","Major":"Major"}
raw["severity_norm"] = raw["Custom field (Symptom Severity)"].map(sev_map).fillna("Unknown")

top_comp = raw["Component/s"].value_counts().nlargest(8).index
raw["component_norm"] = raw["Component/s"].where(
    raw["Component/s"].isin(top_comp), other="Other").fillna("Unknown")

raw["priority_norm"] = raw["Priority"].fillna("Unknown")

# Resolution group: collapse to 4 buckets for readability
def res_group(r):
    if not isinstance(r, str): return "Open"
    if r in NO_ACTION:         return "No-action"
    if r in GENUINE:           return "Resolved"
    return "Open"

raw["res_group"] = raw["Resolution"].apply(res_group)
raw["res_group"] = raw["res_group"].where(
    ~raw["_spam_fixed"], other="No-action")

# ── 2. Rebuild TF-IDF + NMF (same parameters) ───────────────────────────────

_STACK_LINE = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\("
    r"|Version=\d+\.\d+"
    r"|Culture=neutral"
    r"|PublicKeyToken="
    r"|Could\s+not\s+load\s+file\s+or\s+assembly"
    r"|---+\s*(End\s+of|inner)"
    r"|^\s*\w+(\.\w+){3,}Exception[:\s]"
    r"|[A-Za-z]:\\[^\s]{4,}",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)
_TOKEN_NOISE = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b"
)

def clean_text(summary, description):
    desc_lines = str(description).splitlines() if isinstance(description, str) else []
    clean_lines = [ln for ln in desc_lines if not _STACK_LINE.search(ln)]
    text = str(summary) + " " + " ".join(clean_lines)
    return re.sub(r"\s+", " ", _TOKEN_NOISE.sub(" ", text)).lower().strip()

raw["text_clean"] = raw.apply(
    lambda r: clean_text(r["Summary"], r["Description"]), axis=1)

tfidf = TfidfVectorizer(max_features=300, min_df=4, max_df=0.75,
                        sublinear_tf=True, ngram_range=(1,2), stop_words="english")
T = tfidf.fit_transform(raw["text_clean"])
vocab = tfidf.get_feature_names_out()

N_TOPICS = 12
nmf = NMF(n_components=N_TOPICS, random_state=42, max_iter=400, init="nndsvda")
W_scores = nmf.fit_transform(T)          # tickets × topics
H_terms  = nmf.components_              # topics × terms

TOPIC_LABELS = {
    1: "T01 General/version/install",
    2: "T02 Remote/Bitbucket account",
    3: "T03 Git config options",
    4: "T04 File stage/diff view",
    5: "T05 App opening/refresh",
    6: "T06 Branch/push ops",
    7: "T07 Formal bug reports",
    8: "T08 SharpCompress crash",
    9: "T09 Commit/rebase/history",
   10: "T10 Git terminal/LFS",
   11: "T11 Crash/clone",
   12: "T12 Error/pull/log",
}

topic_cols = [f"T{k+1}" for k in range(N_TOPICS)]
scores_df  = pd.DataFrame(W_scores, columns=topic_cols, index=raw.index)

# Add dominant topic
scores_df["dominant"] = [f"T{t+1}" for t in W_scores.argmax(axis=1)]

# ── 3. Helper: Cramer's V ────────────────────────────────────────────────────

def cramers_v(x, y):
    ct   = pd.crosstab(x, y)
    chi2 = chi2_contingency(ct, correction=False)[0]
    n    = ct.to_numpy().sum()
    r, k = ct.shape
    phi2 = max(0, chi2 / n - (r-1)*(k-1)/(n-1))
    rc   = r - (r-1)**2/(n-1)
    kc   = k - (k-1)**2/(n-1)
    return np.sqrt(phi2 / min(rc-1, kc-1)) if min(rc-1, kc-1) > 0 else 0.0

# ── 4. Association: dominant topic vs each categorical ───────────────────────

cat_fields = {
    "Issue Type":    raw["Issue Type"].fillna("Unknown"),
    "Priority":      raw["priority_norm"],
    "Severity":      raw["severity_norm"],
    "Component":     raw["component_norm"],
    "Res. group":    raw["res_group"],
    "Outcome":       raw["outcome"].astype(str),
}

print("Cramer's V — dominant NMF topic vs categorical fields")
print("  (0 = no association, 1 = perfect)")
assoc = {}
for name, series in cat_fields.items():
    v = cramers_v(scores_df["dominant"], series)
    assoc[name] = v
    print(f"  {name:18s}: V={v:.3f}")
print()

# ── 5. Mean topic weight per category level ──────────────────────────────────

def mean_weight_heatmap(groupby_col, series, title, fname):
    tmp = scores_df[topic_cols].copy()
    tmp["group"] = series.values
    means = tmp.groupby("group")[topic_cols].mean()
    # Row-normalise so each category sums to 1 (shows composition, not magnitude)
    means_norm = means.div(means.sum(axis=1), axis=0) * 100

    # Add readable topic labels as column names
    means_norm.columns = [TOPIC_LABELS[int(c[1:])] for c in topic_cols]

    fig = px.imshow(
        means_norm,
        text_auto=".0f",
        color_continuous_scale="Blues",
        title=title,
        labels=dict(x="Topic", y=groupby_col, color="% weight"),
        aspect="auto",
        template="plotly_white",
        width=1100,
        height=max(350, 60 * len(means_norm) + 120),
    )
    fig.update_xaxes(tickangle=30)
    fig.write_html(f"jira/output/{fname}")
    print(f"Wrote: jira/output/{fname}")
    return means_norm

print("=== Mean topic weight (row-normalised %) by categorical field ===\n")

mw_issuetype  = mean_weight_heatmap("Issue Type",  raw["Issue Type"].fillna("Unknown"),
    "Topic Composition by Issue Type",  "align_issuetype.html")
mw_priority   = mean_weight_heatmap("Priority",    raw["priority_norm"],
    "Topic Composition by Priority",    "align_priority.html")
mw_severity   = mean_weight_heatmap("Severity",    raw["severity_norm"],
    "Topic Composition by Severity",    "align_severity.html")
mw_component  = mean_weight_heatmap("Component",   raw["component_norm"],
    "Topic Composition by Component",   "align_component.html")
mw_resgroup   = mean_weight_heatmap("Resolution",  raw["res_group"],
    "Topic Composition by Resolution Group", "align_resgroup.html")
mw_outcome    = mean_weight_heatmap("Outcome",     raw["outcome"].astype(str),
    "Topic Composition by Outcome Ordinal",  "align_outcome.html")

# ── 6. One-way ANOVA: does topic weight differ significantly across categories? ─

print()
print("=== One-way ANOVA: topic weight across category levels ===")
print("(F-stat; p<0.05 means the topic discriminates the category)\n")

for field_name, series in cat_fields.items():
    groups = [scores_df.loc[series == val, topic_cols].values
              for val in series.unique() if (series == val).sum() >= 5]
    print(f"  {field_name}:")
    for k, col in enumerate(topic_cols):
        grp_vals = [g[:, k] for g in groups]
        if len(grp_vals) >= 2:
            F, p = f_oneway(*grp_vals)
            sig = "**" if p < 0.01 else ("*" if p < 0.05 else "  ")
            print(f"    {TOPIC_LABELS[k+1]:35s}  F={F:6.1f}  p={p:.3f} {sig}")
    print()

# ── 7. Incremental R² test ───────────────────────────────────────────────────
# Does adding NMF scores improve prediction of outcome beyond categoricals?

from sklearn.preprocessing import StandardScaler

cat_frames = []
for src, pfx in [("Issue Type","issuetype"),("priority_norm","priority"),
                 ("severity_norm","severity"),("component_norm","component"),
                 ("res_group","res")]:
    cat_frames.append(
        pd.get_dummies(raw[src].fillna("Unknown"), prefix=pfx, dtype=float)
    )
cat_X = pd.concat(cat_frames, axis=1).values
nmf_X = W_scores
y     = raw["outcome"].values.astype(float)

from sklearn.model_selection import cross_val_score

def cv_r2(X, y, alpha=1.0):
    model = Ridge(alpha=alpha)
    scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    return scores.mean(), scores.std()

r2_cat,        std_cat        = cv_r2(cat_X, y)
r2_nmf,        std_nmf        = cv_r2(nmf_X, y)
r2_both,       std_both       = cv_r2(np.hstack([cat_X, nmf_X]), y)

print("=== Incremental R^2 for outcome prediction (5-fold CV, Ridge) ===")
print(f"  Categoricals only : R^2 = {r2_cat:.3f}  (+/-{std_cat:.3f})")
print(f"  NMF topics only   : R^2 = {r2_nmf:.3f}  (+/-{std_nmf:.3f})")
print(f"  Both combined     : R^2 = {r2_both:.3f}  (+/-{std_both:.3f})")
print()

# ── 8. Summary bar: Cramer's V ───────────────────────────────────────────────

fig_assoc = go.Figure(go.Bar(
    x=list(assoc.keys()), y=list(assoc.values()),
    marker_color="#1f77b4",
    text=[f"{v:.3f}" for v in assoc.values()],
    textposition="outside",
))
fig_assoc.update_layout(
    title="Cramer's V: Dominant NMF Topic vs Categorical Parameters",
    yaxis_title="Cramer's V", yaxis_range=[0, 0.8],
    template="plotly_white", width=700, height=420,
)
fig_assoc.write_html("jira/output/cramers_v.html")

# ── 9. Topic × outcome violin ────────────────────────────────────────────────

violin_df = scores_df[topic_cols].copy()
violin_df["outcome"] = raw["outcome"].values
violin_long = violin_df.melt(id_vars="outcome", var_name="topic", value_name="weight")
violin_long["topic_label"] = violin_long["topic"].map(
    {f"T{k+1}": TOPIC_LABELS[k+1] for k in range(N_TOPICS)})

fig_violin = px.violin(
    violin_long[violin_long["weight"] > 0.01],
    x="topic_label", y="outcome", color="topic_label",
    box=True, points=False,
    title="Outcome Distribution per Topic (tickets with topic weight > 0.01)",
    labels={"outcome": "Outcome ordinal", "topic_label": "Topic"},
    template="plotly_white", width=1200, height=500,
)
fig_violin.update_layout(showlegend=False)
fig_violin.update_xaxes(tickangle=30)
fig_violin.write_html("jira/output/topic_outcome_violin.html")

print("Output files written to jira/output/")
print("Done.")
