import re, sys, numpy as np, pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

sys.stdout.reconfigure(encoding="utf-8")

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
    1:"General / install",    2:"Remote / Bitbucket",   3:"Git config options",
    4:"File stage & diff",    5:"App open / refresh",   6:"Branch & push",
    7:"Formal bug reports",   8:"SharpCompress crash",  9:"Commit / history",
   10:"Git terminal / LFS",  11:"Crash / clone",       12:"Error / pull / log",
}

rng = np.random.default_rng(99)

for k in range(12):
    label = TOPIC_LABEL[k+1]
    top_terms = ", ".join(vocab[np.argsort(H[k])[::-1][:10]])
    dominant_mask = W.argmax(axis=1) == k
    idx = raw.index[dominant_mask].tolist()
    n   = len(idx)
    sample_idx = rng.choice(idx, size=min(5, n), replace=False)
    summaries  = raw.loc[sample_idx, "Summary"].tolist()
    print(f"\n-- T{k+1:02d}  {label}  (n={n}) " + "-"*40)
    print(f"   Top terms: {top_terms}")
    for i, s in enumerate(summaries, 1):
        print(f"   [{i}] {str(s)[:100]}")
