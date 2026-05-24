"""
NMF pipeline improvements + N-sweep.
Tests cleaning v2, spam filter, domain stop words across N=8/10/12/14.
Reports: reconstruction error, topic sizes, top terms, % unclassified at
confidence thresholds 0.05 and 0.07.
"""
import re, sys
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

sys.stdout.reconfigure(encoding="utf-8")

# ── load ─────────────────────────────────────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8",
                  on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()
print(f"Loaded: {len(raw)} unique tickets")

# ── cleaning v2 ───────────────────────────────────────────────────────────────
# Adds git config key=value lines and git config commands to the strip list.
# These appear as debug paste in descriptions and caused the spurious T03
# "Git config options" topic.

_STACK = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(|Version=\d|Culture=neutral"
    r"|PublicKeyToken=|Could\s+not\s+load\s+file|---+\s*(End|inner)"
    r"|[A-Za-z]:\\[^\s]{4,}", re.MULTILINE | re.IGNORECASE)
_GITCFG = re.compile(
    # INI section headers:  [core]  [remote "origin"]
    r"^\s*\[[\w\s\"./\\-]+\]\s*$"
    # indented key = bool:  \tquotepath = false
    r"|^\s+[\w-]+\s*=\s*(?:false|true|yes|no|0|1|auto|none|never|always"
    r"|plain|normal|default|warn|error|info)\s*$"
    # dotted key = value:  core.quotepath=false
    r"|^\s*(?:core|diff|http|merge|fetch|push|credential|remote|branch)\.\S+\s*=",
    re.MULTILINE | re.IGNORECASE)
# Sourcetree prints its git invocations on failure, e.g.:
#   "error: git -c diff.mnemonicprefix=false -c core.quotepath=false fetch origin"
# These mid-line echoes are machine text; strip them via substitution.
_GITCMD = re.compile(
    r"git(?:\s+-c\s+\S+)+\s+\S+[^\n]*",
    re.IGNORECASE)
_NOISE  = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b")

def clean_v2(s, d):
    lines = str(d).splitlines()
    lines = [l for l in lines if not _STACK.search(l)]
    lines = [l for l in lines if not _GITCFG.search(l)]
    desc  = _GITCMD.sub(" ", " ".join(lines))
    text  = str(s) + " " + desc
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).lower().strip()

raw["text_clean"] = raw.apply(
    lambda r: clean_v2(r["Summary"], r["Description"]), axis=1)

# ── spam filter ───────────────────────────────────────────────────────────────
# Require at least one Sourcetree-domain term in the cleaned text.
# Removes off-product tickets (calculator apps, humidity sensors, etc.)
# that polluted T07 by speaking only in bug-template language.

SOURCETREE_VOCAB = {
    "sourcetree", "git", "clone", "commit", "branch", "repository",
    "bitbucket", "atlassian", "push", "pull", "merge", "diff", "repo",
    "stash", "rebase", "fetch", "lfs", "mercurial", "svn", "hunk",
    "staged", "unstaged", "checkout", "remote", "submodule",
}

def has_domain_signal(text):
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & SOURCETREE_VOCAB)

raw["relevant"] = raw["text_clean"].apply(has_domain_signal)
relevant = raw[raw["relevant"]].copy().reset_index(drop=True)
n_removed = len(raw) - len(relevant)
print(f"Spam filter: {len(raw)} -> {len(relevant)} tickets  ({n_removed} removed)")

# ── domain stop words ─────────────────────────────────────────────────────────
# Removes near-universal corpus terms that were forming their own topics
# (T05) without discriminating between issue types.
# Kept: "git", "error", "version", "install", "update" — still discriminating.

DOMAIN_STOPS = list(ENGLISH_STOP_WORDS) + [
    "sourcetree", "source", "tree", "windows", "use", "using",
    "problem", "issue", "work", "working", "doesn", "isn",
    "tried", "trying", "please", "want", "need",
]

# ── N sweep ───────────────────────────────────────────────────────────────────

for N in [8, 10, 12, 14]:
    tfidf = TfidfVectorizer(
        max_features=300, min_df=4, max_df=0.75,
        sublinear_tf=True, ngram_range=(1, 2),
        stop_words=DOMAIN_STOPS,
    )
    T    = tfidf.fit_transform(relevant["text_clean"])
    vocab = tfidf.get_feature_names_out()

    nmf  = NMF(n_components=N, random_state=42, max_iter=600, init="nndsvda")
    W    = nmf.fit_transform(T)
    H    = nmf.components_

    T_dense = T.toarray()
    recon = np.linalg.norm(T_dense - W @ H, "fro")

    dom_scores = W.max(axis=1)
    dominant   = W.argmax(axis=1)
    sizes      = [(dominant == k).sum() for k in range(N)]

    # % unclassified at two thresholds
    unc_05 = (dom_scores < 0.05).mean() * 100
    unc_07 = (dom_scores < 0.07).mean() * 100

    print(f"\n{'='*70}")
    print(f"N={N}  recon={recon:.1f}  "
          f"unclassified @0.05={unc_05:.1f}%  @0.07={unc_07:.1f}%")
    print(f"Sizes: {sorted(sizes, reverse=True)}")
    for k in range(N):
        top = ", ".join(vocab[np.argsort(H[k])[::-1][:10]])
        print(f"  T{k+1:02d} n={sizes[k]:3d}: {top}")
