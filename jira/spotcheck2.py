"""
Expanded spot-check: 20 samples per topic, sorted by descending dominance score.
Shows each ticket's top-2 topic scores so we can see whether mislabels are
low-confidence assignments or genuine model errors.
"""
import re, sys
import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

sys.stdout.reconfigure(encoding="utf-8")

# ── rebuild (same params as step_05) ────────────────────────────────────────

df  = pd.read_csv("jira/data/GFG_FINAL.csv", encoding="utf-8", on_bad_lines="skip", low_memory=False)
raw = df.drop_duplicates(subset="Issue key", keep="first").copy()

_STACK = re.compile(
    r"^\s*at\s+[\w$][\w.$<>\[\]]+\s*\(|Version=\d|Culture=neutral"
    r"|PublicKeyToken=|Could\s+not\s+load\s+file|---+\s*(End|inner)"
    r"|[A-Za-z]:\\[^\s]{4,}", re.MULTILINE|re.IGNORECASE)
_NOISE = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b")
def clean(s, d):
    lines = [l for l in str(d).splitlines() if not _STACK.search(l)]
    return re.sub(r"\s+"," ",_NOISE.sub(" ", str(s)+" "+" ".join(lines))).lower().strip()
raw["text_clean"] = raw.apply(lambda r: clean(r["Summary"],r["Description"]), axis=1)

tfidf = TfidfVectorizer(max_features=300, min_df=4, max_df=0.75,
                         sublinear_tf=True, ngram_range=(1,2), stop_words="english")
T = tfidf.fit_transform(raw["text_clean"])
vocab = tfidf.get_feature_names_out()

nmf = NMF(n_components=12, random_state=42, max_iter=400, init="nndsvda")
W   = nmf.fit_transform(T)
H   = nmf.components_

TOPIC_LABEL = {
    0:"General / install",    1:"Remote / Bitbucket",   2:"Git config options",
    3:"File stage & diff",    4:"App open / refresh",   5:"Branch & push",
    6:"Formal bug reports",   7:"SharpCompress crash",  8:"Commit / history",
    9:"Git terminal / LFS",  10:"Crash / clone",       11:"Error / pull / log",
}

rng = np.random.default_rng(99)

# ── per-topic summary ────────────────────────────────────────────────────────

print("=" * 72)
print("NMF SPOT-CHECK  —  20 samples per topic, sorted by score (desc)")
print("score = NMF weight for this topic  |  2nd = next-highest topic weight")
print("=" * 72)

all_dominant = W.argmax(axis=1)

for k in range(12):
    label     = TOPIC_LABEL[k]
    top_terms = ", ".join(vocab[np.argsort(H[k])[::-1][:12]])
    dom_mask  = all_dominant == k
    idx       = np.where(dom_mask)[0]
    n         = len(idx)

    scores_k  = W[idx, k]
    # sort by descending score
    order     = np.argsort(scores_k)[::-1]
    idx_s     = idx[order]
    scores_s  = scores_k[order]

    # sample: take top-5, mid-5 (around median), bottom-5, plus 5 random from rest
    def band(arr, lo_pct, hi_pct):
        lo = int(len(arr) * lo_pct)
        hi = int(len(arr) * hi_pct)
        return arr[lo:hi]

    top_idx  = idx_s[:5]
    top_sc   = scores_s[:5]
    mid_idx  = band(idx_s, 0.45, 0.55)[:5]
    mid_sc   = band(scores_s, 0.45, 0.55)[:5]
    bot_idx  = idx_s[-5:]
    bot_sc   = scores_s[-5:]

    print(f"\n{'─'*72}")
    print(f"T{k+1:02d}  {label}  (n={n})")
    print(f"Top terms: {top_terms}")
    print(f"Score range: {scores_s[-1]:.3f} – {scores_s[0]:.3f}  "
          f"(median {np.median(scores_s):.3f})")

    for section, si, ss in [("HIGH CONFIDENCE", top_idx, top_sc),
                              ("MID CONFIDENCE",  mid_idx, mid_sc),
                              ("LOW CONFIDENCE",  bot_idx, bot_sc)]:
        print(f"  ··· {section} ···")
        for i, sc in zip(si, ss):
            row = raw.iloc[i]
            w_row = W[i]
            # second-best topic
            sorted_t = np.argsort(w_row)[::-1]
            t2 = sorted_t[1] if sorted_t[0] == k else sorted_t[0]
            ratio = w_row[t2] / sc if sc > 0 else 0
            summary = str(row["Summary"])[:95]
            print(f"    sc={sc:.3f} 2nd=T{t2+1}({ratio:.2f})  {summary}")
