"""
JIRA Step 4: Operational narrative
Produces a multi-panel picture of how the org actually operates:
  - Triage funnel (where tickets go)
  - Component health (resolution rate, spam rate, vote weight)
  - Topic × status heatmap (where each topic cluster gets stuck)
  - Ticket volume + topic drift over time
  - Duplicate / high-vote pain-point deep-dive
  - Comment activity distribution
  - Votes distribution by topic
  - Topic co-occurrence (NMF score correlations)
"""

import os, re
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

os.makedirs("jira/output", exist_ok=True)

# ── 1. Load & prepare ────────────────────────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

fmt = "%d/%b/%Y %I:%M %p"
raw["created_dt"]  = pd.to_datetime(raw["Created"],  format=fmt, errors="coerce")
raw["resolved_dt"] = pd.to_datetime(raw["Resolved"], format=fmt, errors="coerce")
raw["resolution_hours"] = (raw["resolved_dt"] - raw["created_dt"]).dt.total_seconds() / 3600

NO_ACTION = {"Spam","Invalid","Incorrectly Filed","Duplicate",
             "Not a bug","Cannot Reproduce","Incomplete"}
GENUINE   = {"Fixed","Resolved Locally","Done","Answered"}
_SPAM_RE  = re.compile(r"(?i)(male\s+enhancement|primal\s+beast|glucotru)")

raw["_spam_fixed"] = (
    raw["Resolution"].isin(GENUINE)
    & raw["Summary"].apply(
        lambda s: len(str(s).strip()) <= 5 or bool(_SPAM_RE.search(str(s)))
    )
)

sev_map = {"Severity 1 - Critical":"Critical","Severity 2 - Major":"Major",
           "Severity 3 - Minor":"Minor","Minor":"Minor","Major":"Major"}
raw["severity_norm"] = raw["Custom field (Symptom Severity)"].map(sev_map).fillna("Unknown")
top_comp = raw["Component/s"].value_counts().nlargest(8).index
raw["component_norm"] = raw["Component/s"].where(
    raw["Component/s"].isin(top_comp), other="Other").fillna("Unknown")
raw["priority_norm"] = raw["Priority"].fillna("Unknown")
raw["comments"]       = pd.to_numeric(raw["Custom field (Comments)"], errors="coerce").fillna(0)
raw["votes"]          = pd.to_numeric(raw["Votes"], errors="coerce").fillna(0)

# Triage category
def triage_cat(row):
    res = row["Resolution"]
    if row["_spam_fixed"] or (isinstance(res, str) and res == "Spam"):
        return "Spam / noise"
    if isinstance(res, str) and res in {"Duplicate"}:
        return "Duplicate"
    if isinstance(res, str) and res in {"Invalid","Incorrectly Filed","Not a bug",
                                         "Cannot Reproduce","Incomplete","Answered"}:
        return "Rejected / unrepro"
    if isinstance(res, str) and res in GENUINE:
        return "Resolved"
    status = row["Status"]
    if status in {"Short Term Backlog","In Progress"}:
        return "Active backlog"
    if status in {"Long Term Backlog","Future Consideration","Under Consideration"}:
        return "Long-term deferred"
    if status in {"Gathering Interest","Gathering Impact"}:
        return "Gathering interest"
    return "Untriaged"

raw["triage_cat"] = raw.apply(triage_cat, axis=1)

# ── 2. Rebuild NMF (same params) ────────────────────────────────────────────

_STACK = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(|Version=\d|Culture=neutral"
    r"|PublicKeyToken=|Could\s+not\s+load\s+file|---+\s*(End|inner)"
    r"|[A-Za-z]:\\[^\s]{4,}",
    re.MULTILINE | re.IGNORECASE,
)
_NOISE = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b"
)

def clean(summary, desc):
    lines = [l for l in str(desc).splitlines() if not _STACK.search(l)]
    text  = str(summary) + " " + " ".join(lines)
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).lower().strip()

raw["text_clean"] = raw.apply(lambda r: clean(r["Summary"], r["Description"]), axis=1)

tfidf = TfidfVectorizer(max_features=300, min_df=4, max_df=0.75,
                        sublinear_tf=True, ngram_range=(1,2), stop_words="english")
T = tfidf.fit_transform(raw["text_clean"])
vocab = tfidf.get_feature_names_out()

N_TOPICS = 12
nmf  = NMF(n_components=N_TOPICS, random_state=42, max_iter=400, init="nndsvda")
W    = nmf.fit_transform(T)
H    = nmf.components_

TOPIC_SHORT = {
    1: "T01 General/install",
    2: "T02 Remote/Bitbucket",
    3: "T03 Git config opts",
    4: "T04 File stage/diff",
    5: "T05 App open/refresh",
    6: "T06 Branch/push",
    7: "T07 Formal bug rpts",
    8: "T08 SharpCompress",
    9: "T09 Commit/history",
   10: "T10 Git terminal/LFS",
   11: "T11 Crash/clone",
   12: "T12 Error/pull/log",
}

topic_cols  = [f"T{k+1}" for k in range(N_TOPICS)]
scores_df   = pd.DataFrame(W, columns=topic_cols, index=raw.index)
scores_df["dominant"] = [TOPIC_SHORT[t+1] for t in W.argmax(axis=1)]
raw["dominant_topic"] = scores_df["dominant"].values

# ── 3. Plot: Triage funnel ───────────────────────────────────────────────────

funnel_order = ["Resolved","Active backlog","Long-term deferred",
                "Gathering interest","Rejected / unrepro","Duplicate",
                "Spam / noise","Untriaged"]
funnel_counts = raw["triage_cat"].value_counts().reindex(funnel_order).fillna(0).astype(int)

fig_funnel = go.Figure(go.Bar(
    x=funnel_counts.values,
    y=funnel_counts.index,
    orientation="h",
    marker_color=["#2ca02c","#98df8a","#aec7e8","#c5b0d5",
                  "#ffbb78","#ff7f0e","#d62728","#7f7f7f"],
    text=funnel_counts.values, textposition="outside",
))
fig_funnel.update_layout(
    title="Ticket Triage Funnel (n=1000)",
    xaxis_title="Tickets", yaxis=dict(autorange="reversed"),
    template="plotly_white", width=750, height=420,
)
fig_funnel.write_html("jira/output/triage_funnel.html")

print("Triage funnel:")
for cat, n in funnel_counts.items():
    print(f"  {cat:28s}: {n:4d}  ({n/10:.1f}%)")
print()

# ── 4. Component health matrix ───────────────────────────────────────────────

comp_stats = (
    raw.groupby("component_norm")
    .agg(
        total        = ("Issue key", "count"),
        resolved     = ("triage_cat", lambda x: (x == "Resolved").sum()),
        spam_noise   = ("triage_cat", lambda x: (x == "Spam / noise").sum()),
        duplicate    = ("triage_cat", lambda x: (x == "Duplicate").sum()),
        untriaged    = ("triage_cat", lambda x: (x == "Untriaged").sum()),
        median_votes = ("votes",     "median"),
        total_votes  = ("votes",     "sum"),
        median_cmt   = ("comments",  "median"),
    )
    .reset_index()
)
comp_stats["resolution_rate_pct"] = (comp_stats["resolved"] / comp_stats["total"] * 100).round(1)
comp_stats["spam_rate_pct"]        = (comp_stats["spam_noise"] / comp_stats["total"] * 100).round(1)
comp_stats["untriaged_rate_pct"]   = (comp_stats["untriaged"] / comp_stats["total"] * 100).round(1)
comp_stats = comp_stats.sort_values("total", ascending=False)

print("Component health:")
print(comp_stats[["component_norm","total","resolution_rate_pct","spam_rate_pct",
                   "untriaged_rate_pct","total_votes","median_cmt"]].to_string(index=False))
print()

fig_comp = make_subplots(rows=1, cols=3,
    subplot_titles=["Resolution rate %", "Spam+noise rate %", "Total votes"])
comps = comp_stats["component_norm"].tolist()

fig_comp.add_trace(go.Bar(y=comps, x=comp_stats["resolution_rate_pct"],
    orientation="h", marker_color="#2ca02c", showlegend=False), row=1, col=1)
fig_comp.add_trace(go.Bar(y=comps, x=comp_stats["spam_rate_pct"],
    orientation="h", marker_color="#d62728", showlegend=False), row=1, col=2)
fig_comp.add_trace(go.Bar(y=comps, x=comp_stats["total_votes"],
    orientation="h", marker_color="#1f77b4", showlegend=False), row=1, col=3)
fig_comp.update_layout(title="Component Health", template="plotly_white",
                       width=1100, height=420)
fig_comp.update_yaxes(autorange="reversed")
fig_comp.write_html("jira/output/component_health.html")

# ── 5. Topic × triage-category heatmap ──────────────────────────────────────

topic_triage = (
    pd.DataFrame({
        "topic": raw["dominant_topic"].values,
        "triage": raw["triage_cat"].values,
    })
    .groupby(["topic","triage"])
    .size().reset_index(name="n")
)
pivot_tt = topic_triage.pivot(index="topic", columns="triage", values="n").fillna(0)
pivot_pct = pivot_tt.div(pivot_tt.sum(axis=1), axis=0) * 100

col_order = [c for c in funnel_order if c in pivot_pct.columns]
pivot_pct = pivot_pct[col_order]

fig_tt = px.imshow(
    pivot_pct, text_auto=".0f",
    color_continuous_scale="RdYlGn",
    title="Topic Disposition: % tickets in each triage category",
    labels=dict(x="Triage category", y="Dominant topic", color="%"),
    aspect="auto", template="plotly_white", width=1000, height=500,
)
fig_tt.update_xaxes(tickangle=25)
fig_tt.write_html("jira/output/topic_triage_heatmap.html")

# ── 6. Topic × status heatmap ────────────────────────────────────────────────

topic_status = (
    pd.DataFrame({"topic": raw["dominant_topic"], "status": raw["Status"]})
    .groupby(["topic","status"]).size().reset_index(name="n")
)
pivot_ts = topic_status.pivot(index="topic", columns="status", values="n").fillna(0)
pivot_ts_pct = pivot_ts.div(pivot_ts.sum(axis=1), axis=0) * 100

fig_ts = px.imshow(
    pivot_ts_pct, text_auto=".0f",
    color_continuous_scale="Blues",
    title="Topic × Status Distribution (%)",
    labels=dict(x="Status", y="Topic", color="%"),
    aspect="auto", template="plotly_white", width=1000, height=500,
)
fig_ts.update_xaxes(tickangle=25)
fig_ts.write_html("jira/output/topic_status_heatmap.html")

# ── 7. Ticket volume + topic drift over time ─────────────────────────────────

raw["year_month"] = raw["created_dt"].dt.to_period("M").astype(str)
valid_time = raw[raw["year_month"].notna() & (raw["year_month"] != "NaT")].copy()

# Keep months with >= 3 tickets
month_counts = valid_time["year_month"].value_counts()
active_months = month_counts[month_counts >= 3].index
valid_time = valid_time[valid_time["year_month"].isin(active_months)]

topic_time = (
    pd.DataFrame({"ym": valid_time["year_month"].values,
                  "topic": valid_time["dominant_topic"].values})
    .groupby(["ym","topic"]).size().reset_index(name="n")
)
total_per_month = topic_time.groupby("ym")["n"].sum().rename("total")
topic_time = topic_time.join(total_per_month, on="ym")
topic_time["pct"] = topic_time["n"] / topic_time["total"] * 100

fig_drift = px.area(
    topic_time.sort_values("ym"),
    x="ym", y="pct", color="topic",
    title="Topic Composition Over Time (% of monthly tickets)",
    labels={"ym": "Month", "pct": "% of tickets", "topic": "Topic"},
    template="plotly_white", width=1100, height=500,
)
fig_drift.update_xaxes(tickangle=45)
fig_drift.write_html("jira/output/topic_drift.html")

# ── 8. Votes + comments by topic ────────────────────────────────────────────

topic_engagement = (
    pd.DataFrame({
        "topic":    raw["dominant_topic"].values,
        "votes":    raw["votes"].values,
        "comments": raw["comments"].values,
    })
    .groupby("topic")
    .agg(
        total_votes    = ("votes",    "sum"),
        median_votes   = ("votes",    "median"),
        pct_voted      = ("votes",    lambda x: (x > 0).mean() * 100),
        total_comments = ("comments", "sum"),
        median_comments= ("comments", "median"),
        max_comments   = ("comments", "max"),
    )
    .reset_index()
    .sort_values("total_votes", ascending=False)
)

print("Topic engagement (votes + comments):")
print(topic_engagement.to_string(index=False))
print()

fig_eng = make_subplots(rows=1, cols=2,
    subplot_titles=["Total votes by dominant topic", "Total comments by dominant topic"])
fig_eng.add_trace(go.Bar(
    y=topic_engagement["topic"], x=topic_engagement["total_votes"],
    orientation="h", marker_color="#ff7f0e", showlegend=False,
), row=1, col=1)
fig_eng.add_trace(go.Bar(
    y=topic_engagement["topic"], x=topic_engagement["total_comments"],
    orientation="h", marker_color="#1f77b4", showlegend=False,
), row=1, col=2)
fig_eng.update_layout(title="Community Engagement by Topic",
    template="plotly_white", width=1050, height=480)
fig_eng.update_yaxes(autorange="reversed")
fig_eng.write_html("jira/output/topic_engagement.html")

# ── 9. High-signal tickets (votes > 5 or comments > 10) ─────────────────────

high_signal = raw[(raw["votes"] > 5) | (raw["comments"] > 10)].copy()
high_signal = high_signal.sort_values(["votes","comments"], ascending=False)

print(f"High-signal tickets (votes>5 or comments>10): {len(high_signal)}")
print()
for _, r in high_signal[["Issue key","votes","comments","Status","dominant_topic","Summary"]].iterrows():
    print(f"  {r['Issue key']}  v={int(r['votes']):2d}  c={int(r['comments']):2d}  "
          f"[{r['Status']}]  {r['dominant_topic']}")
    print(f"    {str(r['Summary'])[:90]}")
print()

# ── 10. Topic co-occurrence (NMF score Pearson correlations) ─────────────────

score_matrix = pd.DataFrame(W, columns=[TOPIC_SHORT[k+1] for k in range(N_TOPICS)])
corr = score_matrix.corr()

fig_corr = px.imshow(
    corr, text_auto=".2f",
    color_continuous_scale="RdBu", color_continuous_midpoint=0,
    zmin=-0.4, zmax=0.4,
    title="NMF Topic Co-occurrence (Pearson r of topic scores)",
    template="plotly_white", width=750, height=680,
)
fig_corr.write_html("jira/output/topic_cooccurrence.html")

# Print notable correlations
print("Notable topic correlations (|r| > 0.08):")
for i in range(N_TOPICS):
    for j in range(i+1, N_TOPICS):
        r = corr.iloc[i, j]
        if abs(r) > 0.08:
            sign = "+" if r > 0 else "-"
            print(f"  {sign}{abs(r):.3f}  {TOPIC_SHORT[i+1]}  <->  {TOPIC_SHORT[j+1]}")

print()
print("Wrote HTML files to jira/output/")
print("Done.")
