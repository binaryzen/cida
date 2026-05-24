"""Diagnose where core/quotepath/mnemonicprefix terms actually live."""
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
    r"^\s*(?:core|diff|http|merge|fetch|push|pull|remote|branch|credential"
    r"|pack|receive|transfer|alias|color|format|status|log|tag|gc|gui"
    r"|filter|protocol|safe|submodule|url|init|include|advice"
    r"|pager|help|man)\.\S+\s*="
    r"|^\s*\[[\w\s\"./\\-]+\]\s*$"
    r"|^\s+[\w-]+\s*=\s*(?:false|true|yes|no|0|1|auto|none|never|always"
    r"|plain|normal|default|warn|error|info)\s*$",
    re.MULTILINE | re.IGNORECASE)
_NOISE  = re.compile(
    r"https?://\S+|!\S+!|\{[^}]*\}|[^\w\s]|\b\d[\d.]*\d\b|\b[a-f0-9]{6,}\b")

TARGET = re.compile(r"quotepath|mnemonicprefix|optionallock|optional.lock", re.IGNORECASE)

print("=== Tickets where TARGET terms appear in SUMMARY ===")
in_summary = raw[raw["Summary"].fillna("").str.contains(TARGET, regex=True)]
print(f"Count: {len(in_summary)}")
for _, r in in_summary.head(10).iterrows():
    print(f"  [{r['Issue key']}] {r['Summary'][:100]}")

print("\n=== Tickets where TARGET terms appear in DESCRIPTION only (not summary) ===")
in_desc_only = raw[
    ~raw["Summary"].fillna("").str.contains(TARGET, regex=True) &
    raw["Description"].fillna("").str.contains(TARGET, regex=True)
]
print(f"Count: {len(in_desc_only)}")

# For a few, show what lines contain the terms and whether they get stripped
for _, r in in_desc_only.head(5).iterrows():
    desc = str(r["Description"])
    hit_lines = [l for l in desc.splitlines() if TARGET.search(l)]
    stripped   = [l for l in hit_lines if _GITCFG.search(l)]
    kept       = [l for l in hit_lines if not _GITCFG.search(l)]
    print(f"\n  [{r['Issue key']}] {r['Summary'][:80]}")
    print(f"  Lines with target term: {len(hit_lines)}")
    print(f"  Stripped by regex: {len(stripped)}")
    print(f"  Kept (not stripped): {len(kept)}")
    for l in kept[:3]:
        print(f"    KEPT: {l[:120]}")
    for l in stripped[:2]:
        print(f"    STRIP: {l[:120]}")

print("\n=== How many description lines does _GITCFG match overall? ===")
total_stripped = 0
for desc in raw["Description"].fillna(""):
    for line in desc.splitlines():
        if _GITCFG.search(line):
            total_stripped += 1
print(f"Total lines matched by _GITCFG: {total_stripped}")
