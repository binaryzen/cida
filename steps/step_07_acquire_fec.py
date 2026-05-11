#!/usr/bin/env python3
"""
Step 7: Acquire FEC contributions via bulk download.

Downloads committee-to-candidate contributions (pas2) and committee master (cm)
flat files from FEC bulk data, then aggregates by industry type.

No API key required, no rate limiting.
Files: ~24 MB each (compressed), cached locally in data/fec_bulk/.

Industry classification:
  Primary:  cm.ORG_TP  (C=Corp, L=Labor, T=Trade, M=Membership, V=Coop, W=Corp-NCS)
  Fallback: cm.CMTE_TP (N=Non-connected PAC, A/B=Party, O/I/U=Super PAC, etc.)
"""

import sys
import json
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests


ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "votes.db"
OUTPUT_DIR = ROOT / "output"
BULK_DIR = ROOT / "data" / "fec_bulk"
BULK_DIR.mkdir(parents=True, exist_ok=True)

FEC_BULK = "https://www.fec.gov/files/bulk-downloads"
CYCLES = [2022, 2024]

# pas2 column layout (pipe-delimited, no header)
PAS2_COLS = [
    "CMTE_ID", "AMNDT_IND", "RPT_TP", "TRANSACTION_PGI", "IMAGE_NUM",
    "TRANSACTION_TP", "ENTITY_TP", "NAME", "CITY", "STATE", "ZIP_CODE",
    "EMPLOYER", "OCCUPATION", "TRANSACTION_DT", "TRANSACTION_AMT",
    "OTHER_ID", "CAND_ID", "TRAN_ID", "FILE_NUM", "MEMO_CD", "MEMO_TEXT", "SUB_ID",
]

# cm column layout
CM_COLS = [
    "CMTE_ID", "CMTE_NM", "TRES_NM", "CMTE_ST1", "CMTE_ST2", "CMTE_CITY",
    "CMTE_ST", "CMTE_ZIP", "CMTE_DSGN", "CMTE_TP", "CMTE_PTY_AFFILIATION",
    "CMTE_FILING_FREQ", "ORG_TP", "CONNECTED_ORG_NM", "CAND_ID_CM",
]

ORG_TP_LABELS = {
    "C": "Corporation",
    "L": "Labor Organization",
    "M": "Membership Organization",
    "T": "Trade Association",
    "V": "Cooperative",
    "W": "Corp w/o Capital Stock",
}

CMTE_TP_LABELS = {
    "N": "Non-connected PAC",
    "Q": "Multi-candidate PAC",
    "O": "Super PAC",
    "I": "Super PAC (non-contrib)",
    "U": "Single-candidate IE",
    "V": "PAC w/ non-contrib acct",
    "W": "Super PAC hybrid",
    "A": "Party - national",
    "B": "Party - state/local",
    "X": "Party - national (NQ)",
    "Y": "Party - state (NQ)",
    "Z": "Party - national (NQ2)",
    "D": "Non-qualified PAC",
    "H": "House campaign",
    "S": "Senate campaign",
    "P": "Presidential campaign",
    "F": "Communication costs",
}


def industry_label(org_tp, cmte_tp):
    if org_tp and org_tp in ORG_TP_LABELS:
        return ORG_TP_LABELS[org_tp]
    if cmte_tp and cmte_tp in CMTE_TP_LABELS:
        return CMTE_TP_LABELS[cmte_tp]
    return "Other"


def download(url, dest):
    if dest.exists():
        print(f"  Cached: {dest.name}", flush=True)
        return
    print(f"  Downloading {dest.name}...", flush=True)
    r = requests.get(url, stream=True, timeout=120, allow_redirects=True)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    written = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 512):
            f.write(chunk)
            written += len(chunk)
            if total:
                print(f"    {written/total*100:.0f}%\r", end="", flush=True)
    print(f"  Done: {dest.name} ({written//1024//1024} MB)", flush=True)


def load_cm(zip_path):
    """Load committee master → dict: cmte_id → (org_tp, cmte_tp)"""
    with zipfile.ZipFile(zip_path) as z:
        fname = next(n for n in z.namelist() if n.lower().endswith(".txt"))
        with z.open(fname) as f:
            df = pd.read_csv(
                f, sep="|", header=None, names=CM_COLS,
                dtype=str, on_bad_lines="skip", encoding="latin-1",
                usecols=["CMTE_ID", "CMTE_TP", "ORG_TP"],
            )
    df = df.fillna("")
    return dict(zip(df["CMTE_ID"], zip(df["ORG_TP"], df["CMTE_TP"])))


def load_pas2_filtered(zip_path, candidate_ids):
    """Load pas2, returning only rows where CAND_ID is in candidate_ids."""
    chunks = []
    with zipfile.ZipFile(zip_path) as z:
        fname = next(n for n in z.namelist() if n.lower().endswith(".txt"))
        with z.open(fname) as f:
            reader = pd.read_csv(
                f, sep="|", header=None, names=PAS2_COLS,
                dtype=str, on_bad_lines="skip", encoding="latin-1",
                usecols=["CMTE_ID", "TRANSACTION_AMT", "CAND_ID"],
                chunksize=200_000,
            )
            for chunk in reader:
                hit = chunk[chunk["CAND_ID"].isin(candidate_ids)]
                if not hit.empty:
                    chunks.append(hit)
    if not chunks:
        return pd.DataFrame(columns=["CMTE_ID", "TRANSACTION_AMT", "CAND_ID"])
    return pd.concat(chunks, ignore_index=True)


def write_status(status, data):
    path = OUTPUT_DIR / "step_07_status.json"
    with open(path, "w") as f:
        json.dump({"step": 7, "status": status,
                   "timestamp": datetime.now().isoformat(), **data}, f, indent=2)


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Rebuild FEC tables with clean schema
    cursor.executescript("""
        DROP TABLE IF EXISTS fec_disbursements;
        DROP TABLE IF EXISTS fec_receipts;
        DROP TABLE IF EXISTS fec_committees;
        CREATE TABLE fec_receipts (
            bioguide_id TEXT,
            cycle       INTEGER,
            industry    TEXT,
            total_amount REAL,
            PRIMARY KEY (bioguide_id, cycle, industry)
        );
    """)
    conn.commit()

    # Load legislator → fec_candidate_id mapping
    cursor.execute("""
        SELECT bioguide_id, fec_candidate_id
        FROM legislators
        WHERE fec_candidate_id IS NOT NULL AND fec_candidate_id != ''
    """)
    leg_map = {fec_id: bio for bio, fec_id in cursor.fetchall()}
    candidate_ids = set(leg_map.keys())
    print(f"Targeting {len(candidate_ids)} FEC candidate IDs", flush=True)

    all_rows = []

    for cycle in CYCLES:
        yy = str(cycle)[-2:]

        # Download bulk files
        pas2_zip = BULK_DIR / f"pas2{yy}.zip"
        cm_zip = BULK_DIR / f"cm{yy}.zip"
        download(f"{FEC_BULK}/{cycle}/pas2{yy}.zip", pas2_zip)
        download(f"{FEC_BULK}/{cycle}/cm{yy}.zip", cm_zip)

        print(f"  Loading committee master ({cycle})...", flush=True)
        cm = load_cm(cm_zip)

        print(f"  Scanning contributions ({cycle})...", flush=True)
        pas2 = load_pas2_filtered(pas2_zip, candidate_ids)
        print(f"    {len(pas2):,} matching contribution records", flush=True)

        if pas2.empty:
            continue

        # Convert amount
        pas2["TRANSACTION_AMT"] = pd.to_numeric(pas2["TRANSACTION_AMT"], errors="coerce").fillna(0)
        pas2 = pas2[pas2["TRANSACTION_AMT"] > 0]

        # Map contributing committee to industry label
        pas2["industry"] = pas2["CMTE_ID"].map(
            lambda cid: industry_label(*cm.get(cid, ("", "")))
        )
        pas2["bioguide_id"] = pas2["CAND_ID"].map(leg_map)
        pas2["cycle"] = cycle

        agg = (
            pas2.groupby(["bioguide_id", "cycle", "industry"], as_index=False)["TRANSACTION_AMT"]
            .sum()
            .rename(columns={"TRANSACTION_AMT": "total_amount"})
        )
        all_rows.append(agg)

    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)
        combined.to_sql("fec_receipts", conn, if_exists="append", index=False)
        conn.commit()
        total_records = len(combined)
        legs_covered = combined["bioguide_id"].nunique()
    else:
        total_records = 0
        legs_covered = 0

    print(f"Inserted {total_records:,} industry-aggregated records for {legs_covered} legislators",
          flush=True)

    # Match rate check
    matrix_legs = set()
    for csv_name in ["legislators_house.csv", "legislators_senate.csv"]:
        p = OUTPUT_DIR / csv_name
        if p.exists():
            matrix_legs.update(pd.read_csv(p)["bioguide_id"].tolist())

    match_rate = 0.0
    matched = 0
    if matrix_legs and legs_covered > 0:
        cursor.execute("SELECT DISTINCT bioguide_id FROM fec_receipts")
        covered = {r[0] for r in cursor.fetchall()}
        matched = len(matrix_legs & covered)
        match_rate = matched / len(matrix_legs)
        print(f"Match rate: {match_rate:.2%} ({matched}/{len(matrix_legs)})", flush=True)
        if match_rate < 0.80:
            print(f"KICKBACK: match rate {match_rate:.2%} < 80%")
            write_status("kickback", {"match_rate": match_rate, "receipts_total": total_records})
            conn.close()
            sys.exit(1)

    log_path = OUTPUT_DIR / "methodology_log.md"
    with open(log_path, "a") as f:
        f.write(f"\n## {datetime.now().isoformat()} — Step 7: Acquire FEC (bulk download)\n")
        f.write(f"- source: fec.gov bulk files pas2{{yy}}.zip + cm{{yy}}.zip\n")
        f.write(f"- cycles: {CYCLES}\n")
        f.write(f"- industry_field: ORG_TP (fallback: CMTE_TP)\n")
        f.write(f"- legislators_matched: {legs_covered}\n")
        f.write(f"- receipt_records: {total_records:,}\n")
        f.write(f"- match_rate: {match_rate:.2%}\n\n")

    write_status("success", {"receipts_total": total_records, "match_rate": match_rate})
    conn.close()
    print("Step 7: OK", flush=True)


if __name__ == "__main__":
    main()
