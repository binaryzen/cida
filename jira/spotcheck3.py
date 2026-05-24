"""
Spot-check N=10 with improved preprocessing.
HIGH/MID/LOW bands, 5 tickets each.
"""
import re, sys
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

sys.stdout.reconfigure(encoding="utf-8")

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8",
                  on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

_STACK = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(|Version=\d|Culture=neutral"
    r"|PublicKeyToken=|Could\s+not\s+load\s+file|---+\s*(End|inner)"
    r"|[A-Za-z]:\\[^\s]{4,}", re.MULTILINE | re.IGNORECASE)
_GITCFG = re.compile(
    r"^\s*\[[\w\s\"./\\-]+\]\s*$"
    r"|^\s+[\w-]+\s*=\s*(?:false|true|yes|no|0|1|auto|none|never|always"
    r"|plain|normal|default|warn|error|info)\s*$"
    r"|^\s*(?:core|diff|http|merge|fetch|push|credential|remote|branch)\.\S+\s*=",
    re.MULTILINE | re.IGNORECASE)
_GITCMD = re.compile(r"git(?:\s+-c\s+\S+)+\s+\S+[^\n]*", re.IGNORECASE)
_NOISE  = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b")

def clean_v2(s, d):
    lines = str(d).splitlines()
    lines = [l for l in lines if not _STACK.search(l)]
    lines = [l for l in lines if not _GITCFG.search(l)]
    desc  = _GITCMD.sub(" ", " ".join(lines))
    text  = str(s) + " " + desc
    return re.sub(r"\s+", " ", _NOISE.sub(" ", text)).lower().strip()

SOURCETREE_VOCAB = {
    "sourcetree", "git", "clone", "commit", "branch", "repository",
    "bitbucket", "atlassian", "push", "pull", "merge", "diff", "repo",
    "stash", "rebase", "fetch", "lfs", "mercurial", "svn", "hunk",
    "staged", "unstaged", "checkout", "remote", "submodule",
}
raw["text_clean"] = raw.apply(lambda r: clean_v2(r["Summary"], r["Description"]), axis=1)
raw["relevant"]   = raw["text_clean"].apply(
    lambda t: bool(set(re.findall(r"\b\w+\b", t.lower())) & SOURCETREE_VOCAB))
relevant = raw[raw["relevant"]].copy().reset_index(drop=True)

DOMAIN_STOPS = list(ENGLISH_STOP_WORDS) + [
    "sourcetree", "source", "tree", "windows", "use", "using",
    "problem", "issue", "work", "working", "doesn", "isn",
    "tried", "trying", "please", "want", "need",
]
tfidf = TfidfVectorizer(max_features=300, min_df=4, max_df=0.75,
                         sublinear_tf=True, ngram_range=(1, 2),
                         stop_words=DOMAIN_STOPS)
T     = tfidf.fit_transform(relevant["text_clean"])
vocab = tfidf.get_feature_names_out()
nmf   = NMF(n_components=10, random_state=42, max_iter=600, init="nndsvda")
W     = nmf.fit_transform(T)
H     = nmf.components_

TOPIC_LABEL = {
    0: "UI navigation / dark mode",
    1: "File staging & diff",
    2: "Branch & push",
    3: "Install & update",
    4: "Pull & fetch errors",
    5: "Git terminal & LFS",
    6: "Commit & history",
    7: "Crash & clone",
    8: "Repository browser",
    9: "Bitbucket auth",
}

dom_scores = W.max(axis=1)
dominant   = W.argmax(axis=1)
MIN_SCORE  = 0.07

print("=" * 72)
print(f"N=10  corpus={len(relevant)}  unclassified @{MIN_SCORE}="
      f"{(dom_scores < MIN_SCORE).mean()*100:.1f}%")
print("=" * 72)

for k in range(10):
    label     = TOPIC_LABEL[k]
    top_terms = ", ".join(vocab[np.argsort(H[k])[::-1][:10]])
    mask      = (dominant == k) & (dom_scores >= MIN_SCORE)
    idx       = np.where(mask)[0]
    n_total   = (dominant == k).sum()
    n_above   = mask.sum()
    scores_k  = W[idx, k]
    order     = np.argsort(scores_k)[::-1]
    idx_s     = idx[order]
    scores_s  = scores_k[order]

    def band(arr, lo, hi):
        lo_i = int(len(arr) * lo); hi_i = int(len(arr) * hi)
        return arr[lo_i:hi_i]

    top_idx = idx_s[:5];              top_sc = scores_s[:5]
    mid_idx = band(idx_s,.45,.55)[:5]; mid_sc = band(scores_s,.45,.55)[:5]
    bot_idx = idx_s[-5:];             bot_sc = scores_s[-5:]

    print(f"\n{'─'*72}")
    print(f"T{k+1:02d}  {label}  (n_above_threshold={n_above}  n_total={n_total})")
    print(f"Top terms: {top_terms}")
    print(f"Scores: {scores_s[-1]:.3f} – {scores_s[0]:.3f}  (median {np.median(scores_s):.3f})")

    for section, si, ss in [("HIGH", top_idx, top_sc),
                              ("MID",  mid_idx, mid_sc),
                              ("LOW",  bot_idx, bot_sc)]:
        print(f"  ··· {section} ···")
        for i, sc in zip(si, ss):
            row = relevant.iloc[i]
            w_row = W[i]
            t2 = np.argsort(w_row)[::-1]
            t2 = t2[1] if t2[0] == k else t2[0]
            ratio = w_row[t2] / sc if sc > 0 else 0
            print(f"    sc={sc:.3f} 2nd=T{t2+1}({ratio:.2f})  {str(row['Summary'])[:95]}")
