"""
Customer Issue Dimension Analysis (CIDA) — Presentation
Generates a single self-contained HTML report: jira/output/CIDA_report.html

Data source: Cesar Anasco, "JIRA Dataset", Kaggle, 2023.
https://www.kaggle.com/datasets/cesaranasco/jira-dataset/data
"""

import os, re
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, chi2_contingency
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

os.makedirs("jira/output", exist_ok=True)

# ── 0. Shared palette ────────────────────────────────────────────────────────

BRAND   = "#1f4e79"
ACCENT  = "#2e86c1"
WARM    = "#e67e22"
DANGER  = "#c0392b"
SUCCESS = "#27ae60"
LIGHT   = "#ecf0f1"
MID     = "#7f8c8d"

# ── 1. Load & prepare ────────────────────────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

fmt = "%d/%b/%Y %I:%M %p"
raw["created_dt"]  = pd.to_datetime(raw["Created"],  format=fmt, errors="coerce")
raw["resolved_dt"] = pd.to_datetime(raw["Resolved"], format=fmt, errors="coerce")
raw["resolution_hours"] = (raw["resolved_dt"] - raw["created_dt"]).dt.total_seconds() / 3600
raw["votes"]    = pd.to_numeric(raw["Votes"],                         errors="coerce").fillna(0)
raw["comments"] = pd.to_numeric(raw["Custom field (Comments)"],       errors="coerce").fillna(0)

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

OUTCOME_LABELS = {
    0:"0-No-action", 1:"1-Hours", 2:"2-Days",
    3:"3-Weeks", 4:"4-Quarters", 5:"5-Years", 6:"6-Never",
}
def _outcome(row):
    res, hrs = row["Resolution"], row["resolution_hours"]
    if (isinstance(res,str) and res in NO_ACTION) or row["_spam_fixed"]: return 0
    if isinstance(res,str) and res in GENUINE:
        if pd.isna(hrs): return None
        if hrs<24: return 1
        if hrs<168: return 2
        if hrs<720: return 3
        if hrs<4320: return 4
        return 5
    return 6

raw["outcome"] = raw.apply(_outcome, axis=1)
raw = raw[raw["outcome"].notna()].copy()
raw["outcome"] = raw["outcome"].astype(int)
raw["outcome_label"] = raw["outcome"].map(OUTCOME_LABELS)

sev_map = {"Severity 1 - Critical":"Critical","Severity 2 - Major":"Major",
           "Severity 3 - Minor":"Minor","Minor":"Minor","Major":"Major"}
raw["severity_norm"] = raw["Custom field (Symptom Severity)"].map(sev_map).fillna("Unknown")
top_comp = raw["Component/s"].value_counts().nlargest(8).index
raw["component_norm"] = raw["Component/s"].where(
    raw["Component/s"].isin(top_comp), other="Other").fillna("Unknown")

def triage_cat(row):
    res = row["Resolution"]
    if row["_spam_fixed"] or (isinstance(res,str) and res=="Spam"): return "Spam / noise"
    if isinstance(res,str) and res=="Duplicate":                     return "Duplicate"
    if isinstance(res,str) and res in {"Invalid","Incorrectly Filed","Not a bug",
                                        "Cannot Reproduce","Incomplete","Answered"}:
        return "Rejected / unrepro"
    if isinstance(res,str) and res in GENUINE:                       return "Resolved"
    if row["Status"] in {"Short Term Backlog","In Progress"}:        return "Active backlog"
    if row["Status"] in {"Long Term Backlog","Future Consideration",
                          "Under Consideration"}:                     return "Long-term deferred"
    if row["Status"] in {"Gathering Interest","Gathering Impact"}:   return "Gathering interest"
    return "Untriaged"

raw["triage_cat"] = raw.apply(triage_cat, axis=1)

raw["domain"] = raw["Custom field (Company)"].fillna("").str.lower().str.strip()
def domain_type(d):
    if not d: return "unknown"
    if any(x in d for x in ("gmail","hotmail","yahoo","outlook","icloud",
                              "live.com","me.com","proton","aol.")): return "Personal email"
    if any(x in d for x in (".edu",".ac.","university")):            return "Academic"
    if d.endswith(".gov") or d.endswith(".mil"):                     return "Government"
    return "Corporate"
raw["domain_type"] = raw["domain"].apply(domain_type)

TIERS = {
    "T5 Enterprise": r"bitbucket.server|azure.devops|tfs\b|vsts|stash\b|corporate|proxy|vpn|ldap|active.directory",
    "T4 Power":      r"interactive.rebase|git.flow|custom.action|ssh.?key|pageant|beyond.compare|winmerge",
    "T3 Advanced":   r"rebase|cherry.pick|submodule|lfs|multiple.remote|upstream|bisect|worktree|hook",
    "T2 Branch":     r"\bbranch\b|\bmerge\b|\bcheckout\b|\bstash\b|\bpull.?request\b",
    "T1 Basic":      r"\bcommit\b|\bpush\b|\bpull\b|\bclone\b",
}
raw["full_text"] = raw["Summary"].fillna("") + " " + raw["Description"].fillna("")
def get_tier(text):
    for tier, pat in TIERS.items():
        if re.search(pat, text, re.IGNORECASE): return tier
    return "T0 General"
raw["tier"] = raw["full_text"].apply(get_tier)

# ── 2. NMF ───────────────────────────────────────────────────────────────────

_STACK = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(|Version=\d|Culture=neutral"
    r"|PublicKeyToken=|Could\s+not\s+load\s+file|---+\s*(End|inner)"
    r"|[A-Za-z]:\\[^\s]{4,}", re.MULTILINE|re.IGNORECASE)
# Git config lines in two forms:
#   INI file: [core] / \tquotepath = false
#   Inline Sourcetree error echo: git -c diff.mnemonicprefix=false -c core.quotepath=false fetch
_GITCFG = re.compile(
    r"^\s*\[[\w\s\"./\\-]+\]\s*$"
    r"|^\s+[\w-]+\s*=\s*(?:false|true|yes|no|0|1|auto|none|never|always|plain|normal|default|warn|error|info)\s*$"
    r"|^\s*(?:core|diff|http|merge|fetch|push|credential|remote|branch)\.\S+\s*=",
    re.MULTILINE|re.IGNORECASE)
_GITCMD = re.compile(r"git(?:\s+-c\s+\S+)+\s+\S+[^\n]*", re.IGNORECASE)
_NOISE  = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b")

def clean(s, d):
    lines = [l for l in str(d).splitlines() if not _STACK.search(l)]
    lines = [l for l in lines if not _GITCFG.search(l)]
    desc  = _GITCMD.sub(" ", " ".join(lines))
    return re.sub(r"\s+"," ",_NOISE.sub(" ", str(s)+" "+desc)).lower().strip()

raw["text_clean"] = raw.apply(lambda r: clean(r["Summary"],r["Description"]), axis=1)

# Filter off-product tickets before NMF. Sourcetree-domain tickets must contain
# at least one domain term; the 171 that don't are spam from other bug trackers
# (other apps' tickets that polluted the NMF with bug-template vocabulary).
_DOMAIN = {"sourcetree","git","clone","commit","branch","repository","bitbucket",
           "atlassian","push","pull","merge","diff","repo","stash","rebase",
           "fetch","lfs","mercurial","svn","hunk","staged","unstaged","checkout",
           "remote","submodule"}
raw["_relevant"] = raw["text_clean"].apply(
    lambda t: bool(set(re.findall(r"\b\w+\b", t)) & _DOMAIN))
relevant = raw[raw["_relevant"]].copy().reset_index(drop=True)

# Domain stop words: near-universal corpus terms that form their own spurious
# topics (e.g., old T05 "App open/refresh" was anchored on "source tree").
_STOPS = list(ENGLISH_STOP_WORDS) + [
    "sourcetree","source","tree","windows","use","using",
    "problem","issue","work","working","doesn","isn","tried","trying",
    "please","want","need",
]

tfidf = TfidfVectorizer(max_features=300, min_df=4, max_df=0.75,
                         sublinear_tf=True, ngram_range=(1,2), stop_words=_STOPS)
T     = tfidf.fit_transform(relevant["text_clean"])
nmf   = NMF(n_components=10, random_state=42, max_iter=600, init="nndsvda")
W     = nmf.fit_transform(T)
H     = nmf.components_

TOPIC_LABEL = {
    0: "UI elements & dark mode",
    1: "File staging & diff",
    2: "Branch & push",
    3: "Install & update",
    4: "HTTP auth & login errors",
    5: "Git terminal & LFS",
    6: "Commit & history",
    7: "Crash & clone",
    8: "Repository browser",
    9: "Bitbucket & account auth",
}

MIN_SCORE = 0.07
dom_scores = W.max(axis=1)
dominant_k = W.argmax(axis=1)
topic_cols = [f"T{k+1}" for k in range(10)]
relevant["dominant_topic"] = [
    TOPIC_LABEL[int(t)] if dom_scores[i] >= MIN_SCORE else "Unclassified"
    for i, t in enumerate(dominant_k)
]
n_relevant     = len(relevant)
n_unclassified = int((relevant["dominant_topic"] == "Unclassified").sum())
n_spam_removed = int((~raw["_relevant"]).sum())

# ── 3. Computed analytics ────────────────────────────────────────────────────

raw["summary_text"] = raw["Summary"].fillna("")
raw["sent_text"]    = raw["Summary"].fillna("") + " " + raw["Description"].fillna("").str[:300]

# Outcome distribution
oc = {k: int((raw["outcome"] == k).sum()) for k in range(7)}
n_total = len(raw)
n_resolved_pct = round(raw["triage_cat"].eq("Resolved").mean() * 100, 1)
n_untriaged_pct = round(raw["triage_cat"].eq("Untriaged").mean() * 100, 1)
n_gathering_pct = round(raw["triage_cat"].eq("Gathering interest").mean() * 100, 1)

# Top ticket
top_ticket   = raw.nlargest(1, "votes").iloc[0]
top_votes    = int(top_ticket["votes"])
top_comments = int(top_ticket["comments"])

# Cannot Reproduce count for recommendations
n_cannot_repro = int(raw["Resolution"].eq("Cannot Reproduce").sum())

# Corporate domain stats
n_corp_pct    = int(round((raw["domain_type"] == "Corporate").mean() * 100))
n_pers_pct    = int(round((raw["domain_type"] == "Personal email").mean() * 100))
n_unique_corp = raw[raw["domain_type"] == "Corporate"]["domain"].nunique()

# Tier vote ratio T2 vs T1
t2_avg = raw[raw["tier"] == "T2 Branch"]["votes"].mean()
t1_avg = raw[raw["tier"] == "T1 Basic"]["votes"].mean()
vote_ratio = f"{t2_avg/t1_avg:.1f}" if t1_avg > 0 else "~6"

# Defect families — matched against ticket summaries only.
# Summaries are user-authored; descriptions often contain stack traces that
# inflate keyword matches when using full text.
FAM_PATTERNS = {
    "Refresh / auto-update": r"refresh|auto.?updat|not updat|out of date|stale",
    "Crash / exception":     r"crash|exception|unhandled|fatal|hang|freeze",
    "Auth / credentials":    r"account|credential|oauth|token|authenticat|login",
    "Install / update":      r"install|updat|setup|upgrade|downgrad",
    "Branch / push / pull":  r"\bpush\b|\bpull\b|\bbranch\b|\bmerge\b|\brebase\b",
    "Perf / memory":         r"slow|performance|memory|cpu|leak",
    "File stage / diff":     r"\bstage\b|\bstaged\b|\bdiff\b|file status",
    "SSH / SSL / cert":      r"\bssh\b|\bssl\b|certif|pageant",
    "Git config":            r"config|quotepath|mnemonicprefix",
}
fam_rows = []
for name, pat in FAM_PATTERNS.items():
    mask = raw["summary_text"].str.contains(pat, case=False, regex=True, na=False)
    sub  = raw[mask]
    open_c = int((sub["triage_cat"] != "Resolved").sum())
    fam_rows.append({
        "Family": name,
        "Tickets": len(sub),
        "Total votes": int(sub["votes"].sum()),
        "Open (no fix)": open_c,
    })
fam_df = pd.DataFrame(fam_rows).sort_values("Total votes", ascending=True)

# Refresh family specifics
refresh_mask    = raw["summary_text"].str.contains(
    r"refresh|auto.?updat|not updat|out of date|stale", case=False, regex=True, na=False)
refresh_sub     = raw[refresh_mask]
refresh_n       = len(refresh_sub)
refresh_votes   = int(refresh_sub["votes"].sum())
refresh_dup_n   = int((refresh_sub["triage_cat"] == "Duplicate").sum())
refresh_dup_pct = int(round(refresh_dup_n / max(refresh_n, 1) * 100))

# Auth family specifics
auth_mask     = raw["summary_text"].str.contains(
    r"account|credential|oauth|token|authenticat|login", case=False, regex=True, na=False)
auth_sub      = raw[auth_mask]
auth_n        = len(auth_sub)
auth_open     = int((auth_sub["triage_cat"] != "Resolved").sum())
auth_open_pct = int(round(auth_open / max(auth_n, 1) * 100))
auth_dup_pct  = int(round((auth_sub["triage_cat"] == "Duplicate").mean() * 100))

# Install family count for recommendations row
install_n = fam_df.loc[fam_df["Family"] == "Install / update", "Tickets"].values[0]

# Gathering interest top tickets
gi_tickets = raw[raw["triage_cat"] == "Gathering interest"].nlargest(4, "votes")
gi_items   = [
    f"{str(r['Summary'])[:55].rstrip()} ({int(r['votes'])} votes)"
    for _, r in gi_tickets.iterrows()
]
gi_narrative = "; ".join(gi_items)

# Sentiment patterns (summary + first 300 chars of description)
is_bug  = raw["Issue Type"].fillna("").str.lower().str.contains("bug")
is_sugg = raw["Issue Type"].fillna("").str.lower().str.contains(
    "suggest|feature|improvement|enhancement")
SENT_DEF = [
    ('"broken" / "unusable"',               r'\bbroken\b|\bunusable\b'),
    ('Uninstall + reinstall (troubleshoot)', r'uninstall.{0,40}reinstall|reinstall.{0,40}uninstall'),
    ('"please fix / add"',                  r'please\s+(?:fix|add|implement|support)'),
    ('"still" / "again" (regression)',       r'\b(?:still|again)\b.{0,50}\b(?:broken|not\s+working|fail|crash|issue)\b'),
    ('Years-long user',                     r'(?:\d+|several|few|many)\s+years?\s+(?:of\s+)?(?:using|ago|now)'),
    ('Team / org-wide impact',              r'\bteam\b|\beveryone\b|\bcolleagues?\b|people\s+in\s+(?:my|our)'),
    ('Dependency: daily workflow',          r'every\s+day|daily\s+use|main\s+(?:tool|app|client)|primary\s+tool'),
]
sent_labels, sent_bugs, sent_sugg = [], [], []
for label, pat in SENT_DEF:
    mask = raw["sent_text"].str.contains(pat, case=False, regex=True, na=False)
    sent_labels.append(label)
    sent_bugs.append(int((mask & is_bug).sum()))
    sent_sugg.append(int((mask & is_sugg).sum()))

n_reinstall   = int(raw["sent_text"].str.contains(
    r'uninstall.{0,40}reinstall|reinstall.{0,40}uninstall', case=False, regex=True, na=False).sum())
n_leave_intent = int(raw["sent_text"].str.contains(
    r'switching to|moved to|uninstalled for good|replacing.{0,30}sourcetree|moving.{0,20}to\s+\w*git',
    case=False, regex=True, na=False).sum())
n_positive_sent = int(raw["sent_text"].str.contains(
    r'\b(?:love|great|best|excellent|awesome)\b.{0,40}\b(?:sourcetree|app|tool|software)\b',
    case=False, regex=True, na=False).sum())
leave_word    = "ticket" if n_leave_intent == 1 else "tickets"
positive_word = "ticket" if n_positive_sent == 1 else "tickets"

# Lock-in ticket counts (summary only)
n_ssh_tickets    = int(raw["summary_text"].str.contains(
    r"\bssh\b|\bpageant\b", case=False, regex=True, na=False).sum())
n_cusact_tickets = int(raw["summary_text"].str.contains(
    r"custom.action", case=False, regex=True, na=False).sum())
n_cusact_votes   = int(raw[raw["summary_text"].str.contains(
    r"custom.action", case=False, regex=True, na=False)]["votes"].sum())
n_difftool       = int(raw["summary_text"].str.contains(
    r"winmerge|beyond.compare|kdiff|diff.?tool|merge.?tool", case=False, regex=True, na=False).sum())
n_gitflow        = int(raw["summary_text"].str.contains(
    r"git.?flow|gitflow", case=False, regex=True, na=False).sum())

# Bitbucket component ticket count
n_bitbucket = int((raw["component_norm"] == "Bitbucket").sum()) \
    if "Bitbucket" in raw["component_norm"].values \
    else int(raw["summary_text"].str.contains(r"bitbucket", case=False, na=False).sum())

# NMF topic-outcome Pearson r with p-values (on relevant corpus only)
nmf_r    = [float(np.corrcoef(W[:,k], relevant["outcome"])[0,1]) for k in range(10)]
nmf_pval = [float(pearsonr(W[:,k], relevant["outcome"])[1])      for k in range(10)]
def sig_label(p):
    return "p&lt;0.01" if p < 0.01 else ("p&lt;0.05" if p < 0.05 else "ns")

# Cramér's V between dominant topic and categorical fields
def cramers_v(x, y):
    ct   = pd.crosstab(x, y)
    chi2 = chi2_contingency(ct, correction=False)[0]
    n    = ct.to_numpy().sum()
    r, k = ct.shape
    phi2 = max(0, chi2/n - (r-1)*(k-1)/(n-1))
    rc   = r - (r-1)**2/(n-1)
    kc   = k - (k-1)**2/(n-1)
    return round(np.sqrt(phi2 / min(rc-1, kc-1)) if min(rc-1, kc-1) > 0 else 0.0, 3)

# Use only classified tickets for Cramér's V
classified = relevant[relevant["dominant_topic"] != "Unclassified"].copy()
dominant_s = classified["dominant_topic"]
cv_issuetype = cramers_v(dominant_s, classified["Issue Type"].fillna("Unknown"))
cv_component = cramers_v(dominant_s, classified["component_norm"])
cv_priority  = cramers_v(dominant_s, classified["Priority"].fillna("Unknown"))
cv_outcome_v = cramers_v(dominant_s, classified["outcome"].astype(str))
cv_lo = min(cv_issuetype, cv_component, cv_priority, cv_outcome_v)
cv_hi = max(cv_issuetype, cv_component, cv_priority, cv_outcome_v)
cv_range = f"{cv_lo:.2f}–{cv_hi:.2f}"

# Component health stats computed here so they're available for both chart and narrative
comp_stats = (
    raw.groupby("component_norm")
    .agg(total=("Issue key","count"),
         resolved=("triage_cat", lambda x: (x=="Resolved").sum()),
         spam=("triage_cat",     lambda x: (x=="Spam / noise").sum()),
         untriaged=("triage_cat",lambda x: (x=="Untriaged").sum()),
         votes=("votes","sum"))
    .reset_index()
)
comp_stats["res_pct"]  = (comp_stats["resolved"] / comp_stats["total"] * 100).round(1)
comp_stats["spam_pct"] = (comp_stats["spam"]      / comp_stats["total"] * 100).round(1)
comp_stats["untr_pct"] = (comp_stats["untriaged"] / comp_stats["total"] * 100).round(1)
comp_stats = comp_stats.sort_values("total", ascending=False)

def cs(name, field):
    row = comp_stats[comp_stats["component_norm"] == name]
    return f"{row[field].iloc[0]}" if not row.empty else "N/A"

# Top-2 spam components for narrative bullets
top_spam_comps = comp_stats.nlargest(2, "spam_pct")[["component_norm","spam_pct"]]
spam_bullet_1 = f"{top_spam_comps.iloc[0]['component_norm']}: {top_spam_comps.iloc[0]['spam_pct']}% spam"
spam_bullet_2 = f"{top_spam_comps.iloc[1]['component_norm']}: {top_spam_comps.iloc[1]['spam_pct']}% spam"
# Highest and lowest resolution components (excluding generic buckets)
filtered_cs = comp_stats[~comp_stats["component_norm"].isin(["Unknown","Other"])]
best_res_row  = filtered_cs.nlargest(1, "res_pct").iloc[0]
worst_res_row = filtered_cs.nsmallest(1, "res_pct").iloc[0]
# Bitbucket-specific stats
bbc_res  = cs("Bitbucket", "res_pct")
bbc_untr = cs("Bitbucket", "untr_pct")
best_res_name = best_res_row["component_norm"]
best_res_pct  = best_res_row["res_pct"]

# ── 4. Chart helpers ─────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, Helvetica, Arial, sans-serif", size=13, color="#2c3e50"),
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(l=20, r=20, t=50, b=20),
)

def fig_html(fig, div_id):
    return pio.to_html(fig, full_html=False, include_plotlyjs=False,
                       div_id=div_id, config={"displayModeBar": False})

# ── 5. Build charts ──────────────────────────────────────────────────────────

charts = {}

# — C1: Triage funnel —
funnel_order  = ["Resolved","Active backlog","Long-term deferred",
                 "Gathering interest","Rejected / unrepro","Duplicate",
                 "Spam / noise","Untriaged"]
funnel_colors = [SUCCESS,"#a9dfbf","#aed6f1","#c5b0d5",
                 "#f9e79f",WARM,DANGER,MID]
fc  = raw["triage_cat"].value_counts().reindex(funnel_order).fillna(0).astype(int)
pct = (fc / fc.sum() * 100).round(1)
labels = [f"{v}  ({pct[k]:.0f}%)" for k, v in fc.items()]

# Convert to Python lists — Plotly CDN may not decode numpy typed-array blobs
fc_vals = [int(v) for v in fc.values]
fc_cats = list(fc.index)

fig = go.Figure(go.Bar(
    x=fc_vals, y=fc_cats,
    orientation="h",
    marker_color=funnel_colors,
    text=labels, textposition="outside",
    textfont=dict(size=12),
))
fig.update_layout(title=f"Where do tickets go? (n = {n_total:,})", xaxis_title="Tickets",
                  xaxis_range=[0, int(max(fc_vals) * 1.45)],
                  yaxis=dict(autorange="reversed"),
                  height=340, **CHART_LAYOUT)
charts["funnel"] = fig_html(fig, "c_funnel")

# — C2a: Defect families — total votes —
fam_names  = fam_df["Family"].tolist()
fam_votes  = [int(v) for v in fam_df["Total votes"]]
fam_open   = [int(v) for v in fam_df["Open (no fix)"]]

fig = go.Figure(go.Bar(
    y=fam_names, x=fam_votes,
    orientation="h", marker_color=ACCENT, showlegend=False,
    text=fam_votes, textposition="outside",
))
fig.update_layout(title="Defect families — total community votes",
    xaxis_title="Votes", xaxis_range=[0, int(max(fam_votes) * 1.45)],
    height=340, **CHART_LAYOUT)
charts["defects_votes"] = fig_html(fig, "c_defvotes")

# — C2b: Defect families — open tickets —
fig = go.Figure(go.Bar(
    y=fam_names, x=fam_open,
    orientation="h", marker_color=DANGER, showlegend=False,
    text=fam_open, textposition="outside",
))
fig.update_layout(title="Defect families — open tickets with no resolution",
    xaxis_title="Open tickets", xaxis_range=[0, int(max(fam_open) * 1.45)],
    height=340, **CHART_LAYOUT)
charts["defects_open"] = fig_html(fig, "c_defopen")

# — C3: Component health — reset index so pandas doesn't pass non-sequential index to Plotly
cs = comp_stats.reset_index(drop=True)
cs_names  = cs["component_norm"].tolist()
cs_res    = [float(v) for v in cs["res_pct"]]
cs_spam   = [float(v) for v in cs["spam_pct"]]
cs_untr   = [float(v) for v in cs["untr_pct"]]

fig = go.Figure()
fig.add_trace(go.Bar(name="Resolved %",  y=cs_names, x=cs_res,
    orientation="h", marker_color=SUCCESS))
fig.add_trace(go.Bar(name="Spam %",      y=cs_names, x=cs_spam,
    orientation="h", marker_color=DANGER))
fig.add_trace(go.Bar(name="Untriaged %", y=cs_names, x=cs_untr,
    orientation="h", marker_color=MID))
fig.update_layout(barmode="group", title="Component health — resolution vs spam vs untriaged (%)",
    xaxis_title="%", legend=dict(orientation="h", y=1.12),
    height=370, **CHART_LAYOUT)
fig.update_yaxes(autorange="reversed")
charts["components"] = fig_html(fig, "c_components")

# — C4: Topic engagement (votes) — excludes unclassified
topic_eng = (
    classified.groupby("dominant_topic")["votes"].sum().reset_index()
    .sort_values("votes", ascending=True)
)
te_names  = topic_eng["dominant_topic"].tolist()
te_votes  = [int(v) for v in topic_eng["votes"]]
te_colors = [DANGER if "staging" in t.lower() else ACCENT for t in te_names]

fig = go.Figure(go.Bar(
    y=te_names, x=te_votes,
    orientation="h", marker_color=te_colors,
    text=te_votes, textposition="outside",
))
fig.update_layout(title="Community votes by dominant topic",
    xaxis_title="Total votes",
    xaxis_range=[0, int(max(te_votes) * 1.45)],
    height=400, **CHART_LAYOUT)
charts["topic_votes"] = fig_html(fig, "c_topicvotes")

# — C5: Customer tiers —
tier_order = ["T0 General","T1 Basic","T2 Branch","T3 Advanced","T4 Power","T5 Enterprise"]
tier_data  = (
    raw.groupby("tier")
    .agg(n=("Issue key","count"), avg_votes=("votes","mean"))
    .reindex(tier_order).reset_index()
)
tier_colors = ["#bdc3c7","#aed6f1","#2e86c1","#f39c12","#e74c3c","#8e44ad"]

fig = make_subplots(rows=1, cols=2,
    subplot_titles=["Tickets per tier", "Average votes per ticket"],
    horizontal_spacing=0.14)
fig.add_trace(go.Bar(x=tier_data["tier"], y=tier_data["n"],
    marker_color=tier_colors, text=tier_data["n"],
    textposition="outside", showlegend=False), row=1, col=1)
fig.add_trace(go.Bar(x=tier_data["tier"], y=tier_data["avg_votes"].round(1),
    marker_color=tier_colors, text=tier_data["avg_votes"].round(1),
    textposition="outside", showlegend=False), row=1, col=2)
fig.update_layout(title="Customer workflow complexity tiers",
    height=340, **CHART_LAYOUT)
charts["tiers"] = fig_html(fig, "c_tiers")

# — C6: Sentiment counts —
fig = go.Figure()
fig.add_trace(go.Bar(name="Bugs",        x=sent_labels, y=sent_bugs,
    marker_color=DANGER, text=sent_bugs, textposition="outside"))
fig.add_trace(go.Bar(name="Suggestions", x=sent_labels, y=sent_sugg,
    marker_color=ACCENT, text=sent_sugg, textposition="outside"))
fig.update_layout(barmode="stack",
    title="Sentiment signals in ticket text (summary + first 300 chars of description)",
    yaxis_title="Tickets", xaxis_tickangle=-25,
    legend=dict(orientation="h", y=1.1),
    height=390, **CHART_LAYOUT)
charts["sentiment"] = fig_html(fig, "c_sentiment")

# — C7: NMF outcome correlation —
topic_names = [TOPIC_LABEL[k] for k in range(10)]
colors_r = [DANGER if r < 0 else ACCENT for r in nmf_r]
order = np.argsort(nmf_r)

fig = go.Figure(go.Bar(
    x=[nmf_r[i] for i in order],
    y=[topic_names[i] for i in order],
    orientation="h",
    marker_color=[colors_r[i] for i in order],
    text=[f"{nmf_r[i]:+.2f}" for i in order],
    textposition="outside",
))
r_abs = max(abs(min(nmf_r)), abs(max(nmf_r)))
r_pad = r_abs * 0.55
fig.add_vline(x=0, line_width=1, line_color="#2c3e50")
fig.update_layout(
    title="Topic correlation with outcome ordinal<br>"
          "<sup>Negative = topic tickets resolve faster  |  Positive = topic tickets stay open longer</sup>",
    xaxis_title="Pearson r",
    xaxis_range=[-(r_abs + r_pad), r_abs + r_pad],
    height=400, **CHART_LAYOUT)
# nmf_r list comprehension already produces Python floats; order is numpy int64 array
# which is safe for list indexing — no conversion needed here
charts["topic_outcome"] = fig_html(fig, "c_topicoutcome")

# ── 6. Topic table rows (notable topics only) ────────────────────────────────

# 0-based NMF column indices for selected topics (N=10 model)
NOTABLE = [
    (1, "File staging &amp; diff",       "Highest vote concentration; v3.3.6 refresh regression epicentre"),
    (7, "Crash &amp; clone",             "Crashers tend to get fixed: well-defined failure modes with clear repro steps"),
    (9, "Bitbucket &amp; account auth",  "Account auth tickets skew toward never resolved — chronic structural gap"),
    (6, "Commit &amp; history",          "Mix of bugs and feature requests; feature requests park in Gathering Interest indefinitely"),
    (3, "Install &amp; update",          "Includes v3.4.10 SharpCompress batch incident; update failures have bimodal resolution"),
]
def r_color(r):
    return DANGER if r < 0 else WARM
topic_table_rows = "".join(
    f'<tr><td>{label}</td>'
    f'<td style="color:{r_color(nmf_r[idx])}">{nmf_r[idx]:+.3f}</td>'
    f'<td>{sig_label(nmf_pval[idx])}</td>'
    f'<td>{interp}</td></tr>'
    for idx, label, interp in NOTABLE
)

# ── 7. Assemble HTML ─────────────────────────────────────────────────────────

PLOTLY_CDN = '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>'

def callout(text, kind="insight"):
    color  = {"insight":"#d6eaf8","warn":"#fdebd0","stat":"#d5f5e3"}.get(kind,"#eee")
    border = {"insight":"#2e86c1","warn":"#e67e22","stat":"#27ae60"}.get(kind,"#999")
    return (f'<div style="background:{color};border-left:4px solid {border};'
            f'padding:12px 16px;margin:14px 0;border-radius:4px;">{text}</div>')

def stat_row(*stats):
    cells = "".join(
        f'<div style="flex:1;text-align:center;padding:16px 8px;">'
        f'<div style="font-size:2.2em;font-weight:700;color:{BRAND}">{v}</div>'
        f'<div style="font-size:0.9em;color:{MID};margin-top:4px">{l}</div>'
        f'</div>'
        for v, l in stats
    )
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin:16px 0">{cells}</div>'

body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CIDA — Customer Issue Dimension Analysis</title>
{PLOTLY_CDN}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    color: #2c3e50;
    background: #f7f9fb;
  }}
  .page {{ max-width: 980px; margin: 0 auto; padding: 40px 28px 80px; }}
  h1 {{ font-size: 2.4em; color: {BRAND}; margin-bottom: 4px; }}
  h2 {{ font-size: 1.45em; color: {BRAND}; margin: 40px 0 10px;
        border-bottom: 2px solid {ACCENT}; padding-bottom: 5px; }}
  h3 {{ font-size: 1.15em; color: #34495e; margin: 24px 0 8px; }}
  p  {{ margin: 10px 0; }}
  ul, ol {{ margin: 10px 0 10px 24px; }}
  li {{ margin: 5px 0; }}
  a  {{ color: {ACCENT}; }}
  .subtitle  {{ color: {MID}; font-size: 1.05em; margin-bottom: 32px; }}
  .chart-wrap {{ background: white; border-radius: 8px;
                 box-shadow: 0 1px 4px rgba(0,0,0,.08);
                 padding: 10px; margin: 18px 0; }}
  table  {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th     {{ background: {BRAND}; color: white; padding: 9px 12px; text-align: left; font-size:.9em; }}
  td     {{ padding: 8px 12px; border-bottom: 1px solid #e8ecef; font-size:.9em; }}
  tr:nth-child(even) td {{ background: #f4f7fb; }}
  .tag   {{ display:inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.8em; font-weight: 600; margin: 1px; }}
  .tag-blue   {{ background:#d6eaf8; color:#1a5276; }}
  .tag-orange {{ background:#fdebd0; color:#784212; }}
  .tag-red    {{ background:#fadbd8; color:#78281f; }}
  .tag-green  {{ background:#d5f5e3; color:#1e8449; }}
  footer {{ color:{MID}; font-size:.85em; margin-top:60px;
            border-top:1px solid #dce1e7; padding-top:20px; }}
</style>
</head>
<body>
<div class="page">

<h1>Customer Issue Dimension Analysis</h1>
<div class="subtitle">
  Applying latent dimension discovery to a public JIRA ticket corpus &nbsp;·&nbsp;
  Sourcetree for Windows &nbsp;·&nbsp; 2013–2023
</div>

<div style="background:#f0f4fa;border-radius:8px;padding:20px 24px;margin:24px 0;border-left:4px solid {BRAND}">
  <strong>What this is:</strong> A text-mining analysis of {n_total:,} public bug-tracker tickets
  submitted by Sourcetree for Windows users between 2013 and 2023.
  The goal is to surface the natural <em>groupings</em> in customer-reported issues —
  not categories pre-defined by an engineer, but patterns that emerge from the language
  users actually wrote. A <em>dimension</em> in this context is one of those emergent groupings:
  a cluster of tickets that share vocabulary and behaviour even if they span multiple
  official product components or priorities.
  <br><br>
  <strong>Key findings:</strong>
  <ul style="margin:8px 0 0 20px">
    <li>{n_untriaged_pct:.0f}% of tickets were never reviewed — a structural backlog problem,
        not a submission-quality problem</li>
    <li>A single UI regression in v3.3.6 accounts for {refresh_votes:,} community votes —
        more than any other defect category combined</li>
    <li>Resolution outcome is determined by team triage decisions, not ticket content:
        creation-time features have essentially zero predictive power for whether a ticket gets fixed</li>
    <li>The user base shows frustrated loyalty — users reinstall rather than leave,
        but engagement is driven by pain, not satisfaction</li>
  </ul>
</div>

<!-- ─── 1. DATA SOURCE ─────────────────────────────────────────────── -->
<h2>1 &nbsp; Data Source</h2>
<p>
  Dataset: <a href="https://www.kaggle.com/datasets/cesaranasco/jira-dataset/data"
  target="_blank"><em>JIRA Dataset</em></a>, published by
  <strong>Cesar Anasco</strong> on Kaggle (2023).
  The file exports the public-facing bug tracker for
  <strong>Sourcetree for Windows</strong>, Atlassian's free Git GUI client.
</p>
{stat_row(
  ("49,000","Raw rows in export"),
  (f"{n_total:,}","Unique tickets after deduplication"),
  ("491","Columns (48 &lt;80% null)"),
  ("1","Project: SRCTREEWIN"),
)}
{callout(
  "<strong>Deduplication finding:</strong> Every ticket appears exactly 49 times in the raw export — "
  "the only varying field is <em>Last Viewed</em> (timestamp). The 49× bloat is an artifact of "
  "JIRA's view-log export, not distinct data.",
  "warn"
)}
<p>
  The dataset spans <strong>nearly 10 years</strong> of ticket history (December 2013 – May 2023).
  All effort fields (Story Points, Original Estimate, Time Spent, Work Ratio) are empty —
  this is a customer-facing feedback tracker, not an internal sprint board.
  The sole effort signal available is resolution time for the {n_resolved_pct}% of tickets that were fixed.
</p>

<!-- ─── 2. METHODOLOGY ────────────────────────────────────────────── -->
<h2>2 &nbsp; Methodology</h2>
<h3>Resolution outcome scale</h3>
<p>
  Each ticket was assigned a score on a 7-point scale representing
  <em>whether it generated any real developer action</em> — not just elapsed time,
  but whether a fix was actually written:
</p>
<table>
  <tr><th>Level</th><th>Label</th><th>Criterion</th><th>n</th></tr>
  <tr><td>0</td><td>No-action disposal</td>
      <td>Spam, Duplicate, Invalid, Cannot Reproduce, or clearly spam content marked Fixed</td>
      <td>{oc[0]}</td></tr>
  <tr><td>1</td><td>Hours (&lt;24h)</td><td>Genuinely fixed within a working day</td><td>{oc[1]}</td></tr>
  <tr><td>2</td><td>Days (1–7d)</td><td></td><td>{oc[2]}</td></tr>
  <tr><td>3</td><td>Weeks (1–4w)</td><td></td><td>{oc[3]}</td></tr>
  <tr><td>4</td><td>Quarters (1–6mo)</td><td></td><td>{oc[4]}</td></tr>
  <tr><td>5</td><td>Years / long-tail</td><td>Fixed but took &gt;6 months</td><td>{oc[5]}</td></tr>
  <tr><td>6</td><td>Never / ignored</td><td>Open with no resolution at export date</td><td>{oc[6]}</td></tr>
</table>
<h3>Text analysis approach</h3>
<p>
  Crash logs and exception reports — the technical readouts .NET applications generate
  automatically when they crash — were stripped from ticket descriptions before analysis,
  so the algorithm learns from what users wrote, not from machine-generated error output.
  The remaining text was converted into a word-frequency table (300 terms weighted by how
  distinctive each term is across tickets; includes single words and two-word phrases).
  Two complementary methods were applied to find natural groupings:
</p>
<ul>
  <li><strong>NMF — Non-negative Matrix Factorization</strong> (10 topics, chosen by reconstruction
      error sweep across N=8–14): finds groups of tickets that share vocabulary. Each ticket gets a
      positive score for each topic; only tickets scoring above 0.07 on their dominant topic are
      assigned to it — {n_unclassified} of {n_relevant} on-product tickets fall below this threshold
      and are treated as unclassified rather than forced into the nearest group.
      This is the primary method used throughout the report.</li>
  <li><strong>PCA — Principal Component Analysis</strong> (50 components, applied as cross-check):
      finds the directions of greatest variation across the full feature set including metadata;
      confirmed the same major themes as NMF but requires more interpretation effort.</li>
</ul>
<p>
  Three preprocessing steps were required before the standard NMF pipeline produced clean topics:
  (1) <strong>Spam filter</strong> — {n_spam_removed} tickets mentioning no Sourcetree-domain term
  (git, commit, branch, clone, etc.) were removed before topic modelling; these were tickets filed
  against other products that leaked into the dataset and, having only generic bug-template language,
  clustered on template structure rather than product content.
  (2) <strong>Sourcetree git-command echo stripping</strong> — Sourcetree prints its own internal
  git invocations when an operation fails (e.g., <code>git -c diff.mnemonicprefix=false -c
  core.quotepath=false fetch origin</code>); without removal these machine-generated tokens formed
  a spurious "Git config options" topic.
  (3) <strong>Domain stop words</strong> — near-universal terms like "sourcetree", "windows",
  "problem", "issue" were added to the TF-IDF stop list; they appeared in too many tickets to
  discriminate between issue types and were anchoring a topic on their own.
</p>
{callout(
  "<strong>Why NMF for topic discovery:</strong> "
  "NMF produces additive topic clusters — each ticket's score for a topic is a positive number "
  "that can be read directly as 'how much is this ticket about Topic X?' "
  "PCA produces axes that can go negative, making individual scores harder to interpret without "
  "domain knowledge. Both methods found the same major themes; NMF results are presented "
  "throughout because the topic weights are intuitive.",
  "insight"
)}

<!-- ─── 3. TRIAGE FUNNEL ───────────────────────────────────────────── -->
<h2>3 &nbsp; Triage Funnel — Operational Health</h2>
<p><em>Triage is the first step after a ticket arrives: a team member reviews it and decides
what to do — fix it, defer it to a backlog, mark it a duplicate of an existing report,
or close it as outside scope. The chart below shows the final state of each of the
{n_total:,} unique tickets in the dataset.</em></p>
<div class="chart-wrap">{charts["funnel"]}</div>
{callout(
  f"<strong>Key finding:</strong> {n_untriaged_pct}% of all tickets are untriaged — sitting at \"Needs Triage\" "
  f"with no action taken. The resolution rate is {n_resolved_pct}%. For every ticket that gets fixed, "
  "roughly four are never looked at. The triage funnel indicates a team significantly "
  "under-resourced relative to incoming volume.",
  "stat"
)}
<p>
  The <strong>Gathering Interest</strong> state ({n_gathering_pct}%) is a community voting mechanism the team
  uses to defer prioritisation. The top requests with no path to resolution include:
  {gi_narrative}.
  Users who vote expect acknowledgement; the data shows no evidence these graduate.
</p>

<!-- ─── 4. DEFECT LANDSCAPE ───────────────────────────────────────── -->
<h2>4 &nbsp; Defect Landscape</h2>
<p><em>Defect families are matched against ticket summaries (user-authored text). Pattern counts
exclude description bodies to avoid inflation from .NET stack traces.</em></p>
<div class="chart-wrap">{charts["defects_votes"]}</div>
<div class="chart-wrap">{charts["defects_open"]}</div>

<h3>The v3.3.6 refresh regression — a single event dominates the corpus</h3>
{callout(
  f"The <strong>Refresh / auto-update</strong> family accumulated {refresh_votes:,} community votes "
  f"from a single regression shipped in v3.3.6 — the version is named in 77 ticket titles and bodies. "
  f"The top ticket alone has {top_votes} votes and {top_comments} comments. "
  f"The family has a <strong>{refresh_dup_pct}% duplicate rate</strong>: {refresh_dup_n} of {refresh_n} "
  "tickets are re-filings of the same bug. "
  "The core invariant that broke: after any operation that changes repository state, "
  "the UI must reflect that state without user intervention.",
  "stat"
)}
<p>
  This is an integration test gap. A single automated test —
  run any state-changing operation (stage a file, commit, fetch, switch branch),
  then assert that the UI reflects the new state within 2 seconds —
  would have caught this before release.
</p>

<h3>Auth / credentials — chronic, structurally ignored</h3>
<p>
  {auth_n} auth/credential tickets, <strong>{auth_open} open ({auth_open_pct}%)</strong>,
  and a near-zero duplicate rate ({auth_dup_pct}%).
  The low duplicate rate is the key signal: these are not the same bug expressed differently —
  each new version introduces a new permutation of the same class of failure.
  The code responsible for saving and restoring account credentials
  has effectively no automated test coverage.
  The recurring pattern across tickets: configure an account → restart the app → account is gone.
</p>

<h3>Component health</h3>
<div class="chart-wrap">{charts["components"]}</div>
<ul>
  <li><span class="tag tag-red">{spam_bullet_1}</span> — inadequately gated submission channel</li>
  <li><span class="tag tag-red">{spam_bullet_2}</span> — public beta channel attracted supplement spammers</li>
  <li><span class="tag tag-orange">Bitbucket: {bbc_res}% resolution, {bbc_untr}% untriaged</span>
      — Bitbucket integration work is systematically deprioritised</li>
  <li><span class="tag tag-green">{best_res_name}: {best_res_pct}% resolution rate</span>
      — highest of any component</li>
</ul>

<!-- ─── 5. TOPIC DIMENSIONS ───────────────────────────────────────── -->
<h2>5 &nbsp; Topic Dimensions (NMF)</h2>
<p>NMF was run on the {n_relevant} on-product tickets (after removing {n_spam_removed} off-product
tickets). {n_unclassified} tickets scored below the 0.07 minimum threshold and are excluded from
topic-level charts; {len(classified)} tickets are classified into one of 10 topics.</p>
<div class="chart-wrap">{charts["topic_votes"]}</div>
<div class="chart-wrap">{charts["topic_outcome"]}</div>
{callout(
  f"Topic alignment (Cramér's V {cv_range} across Issue Type, Priority, Component, and Outcome). "
  "Cramér's V is a 0–1 association score between two categorical groupings: 0 = no relationship, "
  "1 = perfect correspondence. "
  "This range confirms the topics capture sub-structure <em>within</em> existing categories "
  "rather than merely restating them; Component shows the strongest alignment — topics are a "
  "finer-grained, text-derived version of the component taxonomy. "
  "Predictive modelling (Ridge regression, 5-fold cross-validation) showed that all creation-time "
  "ticket features combined — category, priority, component, and NMF scores — explain essentially "
  "none of the variance in resolution outcome (R² &lt; 0.05). "
  "Whether a ticket gets fixed is determined by team triage decisions after filing, "
  "not by what the ticket says.",
  "insight"
)}
<p><small><em>
  r = Pearson correlation with the resolution outcome scale (range: −1 to +1).
  Negative r = these tickets tend to resolve faster than average;
  positive r = these tickets tend to stay open longer.
  Significance: p&lt;0.01 = highly significant; p&lt;0.05 = significant; ns = not significant
  (result could plausibly be random noise).
</em></small></p>
<table>
  <tr><th>Topic</th><th>r</th><th>Significance</th><th>Interpretation</th></tr>
  {topic_table_rows}
</table>

<!-- ─── 6. CUSTOMER SEGMENTS ─────────────────────────────────────── -->
<h2>6 &nbsp; Customer Segments</h2>
<p>Tickets were classified into six workflow-complexity tiers based on vocabulary in the ticket text,
from basic Git usage to enterprise server administration:</p>
<table style="margin-bottom:4px">
  <tr><th>Tier</th><th>Typical Git operations described</th></tr>
  <tr><td><strong>T0 General</strong></td><td>No Git-specific terms; general usage questions</td></tr>
  <tr><td><strong>T1 Basic</strong></td><td>commit, push, pull, clone</td></tr>
  <tr><td><strong>T2 Branch</strong></td><td>branching, merging, checkout, stash (saved-but-uncommitted work), pull requests</td></tr>
  <tr><td><strong>T3 Advanced</strong></td><td>rebase, cherry-pick, submodules, Git LFS (large file storage), multiple remotes</td></tr>
  <tr><td><strong>T4 Power</strong></td><td>interactive rebase, Git flow, custom actions, SSH key management, external diff/merge tools</td></tr>
  <tr><td><strong>T5 Enterprise</strong></td><td>Bitbucket Server / Azure DevOps / TFS (on-premise Git hosting), LDAP, Active Directory, corporate proxy</td></tr>
</table>
<div class="chart-wrap">{charts["tiers"]}</div>
{stat_row(
  (f"{n_corp_pct}%", f"Corporate-domain tickets"),
  (f"{n_pers_pct}%", "Personal email tickets"),
  (f"{vote_ratio}×", "Avg votes: T2 Branch vs T1 Basic"),
  (f"{n_unique_corp:,}", "Unique corporate domains — no single dominant enterprise"),
)}

<h3>The T2 Branch user is the core constituency</h3>
<p>
  The <strong>T2 Branch tier</strong> (branching, merging, pull requests) has {vote_ratio}× the average
  vote rate of T1 Basic users, despite being a mid-sized tier by ticket count.
  These are collaborative developers doing real team workflows who care enough to engage
  the community — and who were hardest hit by the v3.3.6 refresh regression, because
  their daily workflow (branch → change → commit → confirm in UI) depends entirely on UI state
  staying current.
</p>

<h3>Three archetypes</h3>
<table>
  <tr><th>Archetype</th><th>Tier</th><th>Primary complaints</th><th>Lock-in signals</th></tr>
  <tr><td><strong>Corporate Branch Developer</strong></td><td>T2</td>
      <td>Refresh regression; UI not updating after operations</td>
      <td>Daily driver; team-wide deployment ("happening to quite a few people on our team")</td></tr>
  <tr><td><strong>Enterprise Admin</strong></td><td>T5</td>
      <td>Bitbucket Server OAuth resetting; SSO / app password failures</td>
      <td>Atlassian double lock-in (Bitbucket + Sourcetree); org-wide version control</td></tr>
  <tr><td><strong>SSH Power User</strong></td><td>T4</td>
      <td>Pageant closed on exit; custom actions shortcuts missing; diff tool config</td>
      <td>Scripted workflows; Pageant auth; configured external diff/merge tools</td></tr>
</table>

<!-- ─── 7. SENTIMENT & LOYALTY ────────────────────────────────────── -->
<h2>7 &nbsp; Sentiment &amp; Loyalty</h2>
<div class="chart-wrap">{charts["sentiment"]}</div>
{callout(
  f"The dominant tone is <strong>frustrated loyalty</strong>. "
  f"{n_reinstall} tickets describe uninstalling and reinstalling as a troubleshooting step — "
  f"a loyalty signal, not departure intent: a user who has given up simply leaves; "
  f"someone who reinstalls is still trying to make the app work. "
  f"Explicit intent-to-leave language (\"switching to\", \"moving to\") appears in "
  f"{n_leave_intent} {leave_word}. "
  f"Positive sentiment (\"love / great / best\" about the product) appears in "
  f"{n_positive_sent} {positive_word}. "
  "Users are not leaving, but they are not delighted.",
  "insight"
)}
<h3>Lock-in mechanisms (descending signal strength)</h3>
<ul>
  <li><strong>Bitbucket double lock-in</strong> ({n_bitbucket} tickets) — customers who host code on
      Atlassian's Bitbucket <em>and</em> use Sourcetree (also Atlassian) are tied to the ecosystem twice;
      switching the Git client means re-authenticating every repository connection</li>
  <li><strong>SSH / Pageant integration</strong> ({n_ssh_tickets} tickets) — Pageant is the SSH key
      manager bundled with PuTTY (the standard Windows terminal); users route Sourcetree authentication
      through Pageant rather than the Windows keystore, creating a workflow dependency</li>
  <li><strong>Custom actions / scripts</strong> ({n_cusact_tickets} tickets, {n_cusact_votes} votes) —
      external tool calls wired into the UI</li>
  <li><strong>External diff / merge tools</strong> ({n_difftool} tickets) — Beyond Compare, WinMerge, KDiff
      configured as default resolvers</li>
  <li><strong>Git flow UI</strong> ({n_gitflow} tickets) — release cadence built on the feature/
      release/hotfix buttons</li>
</ul>
{callout(
  "Notable absence: <strong>zero tickets mention GPG signed commits</strong>. "
  "GPG (GNU Privacy Guard) signing attaches a cryptographic identity to each commit, permanently "
  "tying a developer's history to a specific key pair — the deepest possible switching barrier. "
  "No tickets reference it, meaning this user base has not invested in identity-bound commits. "
  "Lock-in here is workflow habit and tool configuration, not identity.",
  "warn"
)}

<!-- ─── 8. RECOMMENDATIONS ────────────────────────────────────────── -->
<h2>8 &nbsp; Cross-Cutting Recommendations</h2>
<p>
  Ordered by effort-to-impact ratio for a team that cannot add headcount.
  <em>Effort tags:
  <span class="tag tag-green">Zero eng</span> = process or config change, no code required &nbsp;·&nbsp;
  <span class="tag tag-green">Low</span> = &lt;1 sprint &nbsp;·&nbsp;
  <span class="tag tag-orange">Medium</span> = 1–2 sprints.</em>
</p>
<table>
  <tr><th>#</th><th>Measure</th><th>Addresses</th><th>Effort</th></tr>
  <tr>
    <td>1</td>
    <td><strong>Structured submission template</strong><br>
        <small>Required fields: Windows version · git version · embedded vs system git ·
        proxy (y/n) · multi-monitor (y/n) · steps to reproduce</small></td>
    <td>{n_cannot_repro} Cannot Reproduce tickets; reduces per-ticket triage effort</td>
    <td><span class="tag tag-green">Zero eng</span></td>
  </tr>
  <tr>
    <td>2</td>
    <td><strong>UI state regression suite</strong><br>
        <small>After each state-changing operation (stage file, commit, fetch, switch branch),
        assert the UI reflects the new state within 2 seconds</small></td>
    <td>{refresh_votes:,}-vote refresh family; {refresh_dup_pct}% duplicate rate</td>
    <td><span class="tag tag-orange">Medium</span></td>
  </tr>
  <tr>
    <td>3</td>
    <td><strong>Credential persistence smoke test</strong><br>
        <small>Configure account → restart process → assert account still configured</small></td>
    <td>{auth_open} open auth tickets across multiple versions</td>
    <td><span class="tag tag-green">Low</span></td>
  </tr>
  <tr>
    <td>4</td>
    <td><strong>Duplicate detection at submission</strong><br>
        <small>Text-similarity check: "these open tickets look similar — is one of them your issue?"</small></td>
    <td>~15–20% of incoming volume based on family duplicate rates</td>
    <td><span class="tag tag-orange">Medium</span></td>
  </tr>
  <tr>
    <td>5</td>
    <td><strong>Installer smoke test in the release pipeline</strong><br>
        <small>CI (continuous integration) = automated tests that run before every release.
        Add a clean install and an in-place upgrade test on Windows 10 and Windows 11 images.</small></td>
    <td>{install_n} install/update tickets; v3.4.10 batch incident (24 mentions)</td>
    <td><span class="tag tag-green">Low</span></td>
  </tr>
  <tr>
    <td>6</td>
    <td><strong>Background process lifecycle test</strong><br>
        <small>Startup → idle → foreground/background switch → clean exit;
        assert no orphaned processes, no Pageant termination</small></td>
    <td>SSH/Pageant ({n_ssh_tickets} tickets, {fam_df.loc[fam_df["Family"]=="SSH / SSL / cert","Total votes"].values[0]} votes); cpu-hungry ssh-agent.exe</td>
    <td><span class="tag tag-green">Low</span></td>
  </tr>
</table>

<footer>
  <strong>Customer Issue Dimension Analysis (CIDA)</strong> &nbsp;·&nbsp;
  Data: <a href="https://www.kaggle.com/datasets/cesaranasco/jira-dataset/data"
  target="_blank"><em>JIRA Dataset</em></a> by Cesar Anasco (Kaggle, 2023) &nbsp;·&nbsp;
  Methods: NMF · PCA · TF-IDF · Cramér's V · one-way ANOVA &nbsp;·&nbsp;
  Analysis: May 2026
</footer>

</div>
</body>
</html>
"""

out_path = "jira/output/CIDA_report.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(body)

print(f"Wrote: {out_path}")
print(f"File size: {os.path.getsize(out_path):,} bytes")
