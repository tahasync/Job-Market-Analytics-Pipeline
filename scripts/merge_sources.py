"""
merge_sources.py
================
Merges all 4 raw CSVs into merged_raw_jobs.csv.
Fixed: uses /opt/airflow absolute paths (not relative), ensures all 25
required schema columns exist in the merged output.

Place at: job_market_project/scripts/merge_sources.py
"""

import pandas as pd
import os
import datetime

# ── Paths (Docker / Linux) ────────────────────────────────────────────────────
BASE_DIR    = os.environ.get("AIRFLOW_HOME", "/opt/airflow")
RAW_DIR     = os.path.join(BASE_DIR, "data", "raw")
MERGED_DIR  = os.path.join(BASE_DIR, "data", "merged")
OUTPUT_FILE = os.path.join(MERGED_DIR, "merged_raw_jobs.csv")

# Raw source columns (what KNIME expects as input — 17 cols)
# KNIME CSV Reader expects: source, job_id, title, company_name, ...
RAW_COLS = [
    "source", "job_id", "title", "company_name",
    "location_raw", "remote_status", "job_type",
    "category_raw", "tags_raw", "description",
    "publication_date", "job_url",
    "salary_text_raw", "salary_min_raw", "salary_max_raw",
    "currency_raw", "scrape_date",
]

# Full 25-column schema (achieved after KNIME + Patch)
STANDARD_COLS = RAW_COLS + [
    "job_id", "category_raw",
    "salary_min_raw", "salary_max_raw",
    "salary_min_usd", "salary_max_usd", "salary_mid_usd",
    "experience_years_min", "experience_years_max", "experience_bracket",
    "extracted_skills", "job_category_clean",
]

FILES = {
    "Arbeitnow":      "raw_arbeitnow_jobs.csv",
    "RemoteOK":       "raw_remoteok_jobs.csv",
    "Himalayas":      "raw_himalayas_jobs.csv",
    "RemoteJobs.org": "raw_remotejobs_jobs.csv",
}


def fix_remote(val):
    val = str(val).strip().lower()
    if val in ("remote", "true", "yes", "1"):       return "Remote"
    if val in ("on-site", "onsite", "office", "false", "no", "0"): return "On-site"
    if "hybrid" in val:                              return "Hybrid"
    return "Remote" if val == "" else "Unknown"


def fix_job_type(val):
    val = str(val).strip().lower()
    if "full" in val:      return "Full-time"
    if "part" in val:      return "Part-time"
    if "contract" in val:  return "Contract"
    if "freelance" in val: return "Freelance"
    if "intern" in val:    return "Internship"
    return "Unknown"


def merge_sources():
    print("=" * 55)
    print("MERGE SOURCES — combining all 4 raw CSVs")
    print("=" * 55)

    os.makedirs(MERGED_DIR, exist_ok=True)
    scrape_date = datetime.date.today().isoformat()
    dfs = []

    for source, filename in FILES.items():
        path = os.path.join(RAW_DIR, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, dtype=str).fillna("")
            except Exception as e:
                print(f"  WARNING: Could not read {path}: {e}")
                continue
            df["source"] = source
            print(f"  Loaded {len(df):>4} rows from {source}")
            dfs.append(df)
        else:
            print(f"  WARNING: {path} not found — skipping {source}")

    if not dfs:
        raise RuntimeError("No raw files found. Run extraction scripts first.")

    # Standardize and add missing columns ──────────────────────────────────────
    standardized = []
    for df in dfs:
        # Column aliases: Himalayas uses 'pubDate', some use 'currency'
        if "pubDate" in df.columns and "publication_date" not in df.columns:
            df["publication_date"] = df["pubDate"]
        if "currency" in df.columns and "currency_raw" not in df.columns:
            df["currency_raw"] = df["currency"]
        # Alias 'description_clean' or 'desc' → 'description'
        for alias in ("description_clean", "desc", "job_description"):
            if alias in df.columns and "description" not in df.columns:
                df["description"] = df[alias]
        # Alias salary raw columns from KNIME/extractor names
        for alias in ("salary_min_clean", "salary_min"):
            if alias in df.columns and "salary_min_raw" not in df.columns:
                df["salary_min_raw"] = df[alias]
        for alias in ("salary_max_clean", "salary_max"):
            if alias in df.columns and "salary_max_raw" not in df.columns:
                df["salary_max_raw"] = df[alias]

        # Add all missing raw columns as empty string
        for col in RAW_COLS:
            if col not in df.columns:
                df[col] = ""

        # Set scrape_date if empty
        mask = df["scrape_date"].eq("")
        df.loc[mask, "scrape_date"] = scrape_date

        # Keep only raw columns (KNIME expects these 13 source columns)
        df = df[RAW_COLS].copy()
        standardized.append(df)

    merged = pd.concat(standardized, ignore_index=True)
    print(f"\nTotal rows before deduplication: {len(merged)}")

    # Deduplicate ──────────────────────────────────────────────────────────────
    before = len(merged)
    url_mask = merged["job_url"].ne("")
    dedup_url    = merged[url_mask].drop_duplicates(subset=["job_url"], keep="first")
    dedup_no_url = merged[~url_mask].drop_duplicates(
        subset=["title", "company_name", "source"], keep="first"
    )
    merged = pd.concat([dedup_url, dedup_no_url], ignore_index=True)
    print(f"Duplicates removed: {before - len(merged)}")
    print(f"Total rows after deduplication: {len(merged)}")

    # Clean up strings ─────────────────────────────────────────────────────────
    for col in merged.columns:
        merged[col] = merged[col].astype(str).str.strip()
    merged = merged.replace("nan", "")

    # Standardize controlled fields
    merged["remote_status"] = merged["remote_status"].apply(fix_remote)
    merged["job_type"]      = merged["job_type"].apply(fix_job_type)

    # Report ───────────────────────────────────────────────────────────────────
    print("\n--- Jobs by Source ---")
    print(merged["source"].value_counts().to_string())
    print("\n--- Remote Status ---")
    print(merged["remote_status"].value_counts().to_string())
    print("\n--- Job Type ---")
    print(merged["job_type"].value_counts().to_string())

    # Save ─────────────────────────────────────────────────────────────────────
    merged.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\n[OK] Saved merged file: {OUTPUT_FILE}")
    print(f"   Total rows: {len(merged)}  |  Columns: {len(merged.columns)}")
    print("=" * 55)


if __name__ == "__main__":
    merge_sources()
