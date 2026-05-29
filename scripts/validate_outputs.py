"""
validate_outputs.py
===================
Validates the cleaned output CSV against all 25 required schema columns.
Prints PASS / FAIL for each check. Raises exception on critical failures
so Airflow marks the task red.

Place at: job_market_project/scripts/validate_outputs.py
"""

import pandas as pd
import os
import sys

# ── Path (Docker / Linux) ─────────────────────────────────────────────────────
BASE_DIR   = os.environ.get("AIRFLOW_HOME", "/opt/airflow")
INPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "clean_ai_ml_data_jobs.csv")

# ── All 25 required schema columns ────────────────────────────────────────────
REQUIRED_COLS = [
    "source", "job_id", "title", "company_name",
    "location_raw", "remote_status", "job_type",
    "category_raw", "tags_raw", "description",
    "publication_date", "job_url",
    "salary_text_raw", "salary_min_raw", "salary_max_raw", "currency_raw",
    "salary_min_usd", "salary_max_usd", "salary_mid_usd",
    "experience_years_min", "experience_years_max", "experience_bracket",
    "extracted_skills", "job_category_clean", "scrape_date",
]

VALID_REMOTE_STATUSES  = {"Remote", "On-site", "Hybrid", "Unknown"}
VALID_EXP_BRACKETS     = {"0-1", "1-3", "3-5", "5-8", "8+", "Not mentioned"}
VALID_JOB_TYPES        = {"Full-time", "Part-time", "Contract", "Freelance", "Internship", "Unknown"}


def check(label, passed, detail=""):
    status = "[OK] PASS" if passed else "[FAIL] FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return passed


def validate_data():
    print("=" * 60)
    print("VALIDATION LAYER — Job Market Pipeline Output")
    print("=" * 60)

    failures = []

    # ── CHECK 0: File exists ───────────────────────────────────────────────────
    file_ok = os.path.exists(INPUT_FILE)
    if not check("Output file exists", file_ok, INPUT_FILE):
        failures.append("Output file missing")
        print("\n[FAIL] CRITICAL: Cannot continue — output file not found.")
        raise FileNotFoundError(f"Cleaned CSV not found: {INPUT_FILE}")

    # Load
    try:
        df = pd.read_csv(INPUT_FILE, encoding="latin1")
    except Exception:
        df = pd.read_csv(INPUT_FILE, encoding="utf-8", errors="replace")

    print(f"\nLoaded {len(df)} rows × {len(df.columns)} columns\n")

    # ── CHECK 1: Not empty ─────────────────────────────────────────────────────
    if not check("File is not empty", len(df) > 0):
        failures.append("File is empty")
        raise ValueError("Cleaned CSV is empty")

    # ── CHECK 2: All 25 schema columns present ─────────────────────────────────
    print("\n--- Schema Check (25 required columns) ---")
    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    present_count = len(REQUIRED_COLS) - len(missing_cols)
    schema_ok = len(missing_cols) == 0
    check(f"All 25 schema columns present ({present_count}/25)", schema_ok,
          f"Missing: {missing_cols}" if missing_cols else "")
    if not schema_ok:
        failures.append(f"Missing columns: {missing_cols}")

    # ── CHECK 3: Missing value percentages (critical columns) ──────────────────
    print("\n--- Missing Value Check (critical columns) ---")
    critical = ["source", "title", "company_name", "job_url", "description", "remote_status"]
    for col in critical:
        if col in df.columns:
            pct = df[col].isnull().sum() / len(df) * 100
            passed = pct < 50  # flag if >50% missing
            check(f"{col} completeness", passed, f"{pct:.1f}% missing")
            if not passed:
                failures.append(f"{col} has {pct:.1f}% missing")

    # ── CHECK 4: Remote status values ─────────────────────────────────────────
    print("\n--- Remote Status Check ---")
    if "remote_status" in df.columns:
        invalid = df[~df["remote_status"].isin(VALID_REMOTE_STATUSES)]
        passed = len(invalid) == 0
        check("remote_status values valid", passed,
              f"{len(invalid)} invalid rows" if not passed else
              str(df["remote_status"].value_counts().to_dict()))
        if not passed:
            failures.append(f"remote_status has {len(invalid)} invalid values")

    # ── CHECK 5: Experience bracket values ─────────────────────────────────────
    print("\n--- Experience Bracket Check ---")
    if "experience_bracket" in df.columns:
        invalid = df[~df["experience_bracket"].isin(VALID_EXP_BRACKETS)]
        passed = len(invalid) == 0
        check("experience_bracket values valid", passed,
              f"{len(invalid)} invalid" if not passed else
              str(df["experience_bracket"].value_counts().to_dict()))
        if not passed:
            failures.append(f"experience_bracket has {len(invalid)} invalid values")

    # ── CHECK 6: Job type values ───────────────────────────────────────────────
    print("\n--- Job Type Check ---")
    if "job_type" in df.columns:
        invalid = df[~df["job_type"].isin(VALID_JOB_TYPES)]
        passed = len(invalid) == 0
        check("job_type values valid", passed,
              f"{len(invalid)} invalid" if not passed else
              str(df["job_type"].value_counts().to_dict()))

    # ── CHECK 7: Salary columns (zeros should be treated as null) ──────────────
    print("\n--- Salary Check ---")
    if "salary_mid_usd" in df.columns:
        valid_sal = df["salary_mid_usd"].replace(0, pd.NA).replace("", pd.NA).dropna()
        pct = len(valid_sal) / len(df) * 100
        # Even 5% coverage is acceptable (salary is sparse in job APIs)
        check("salary_mid_usd has some valid values", pct > 0,
              f"{pct:.1f}% coverage ({len(valid_sal)} jobs with salary)")

    # ── CHECK 8: extracted_skills not all empty ────────────────────────────────
    print("\n--- Skills Check ---")
    if "extracted_skills" in df.columns:
        have_skills = df["extracted_skills"].replace("", pd.NA).notna().sum()
        pct = have_skills / len(df) * 100
        check("extracted_skills populated", pct > 10,
              f"{pct:.1f}% of jobs have skills ({have_skills} rows)")

    # ── CHECK 9: job_category_clean not all empty ──────────────────────────────
    print("\n--- Category Check ---")
    if "job_category_clean" in df.columns:
        have_cat = df["job_category_clean"].replace("", pd.NA).notna().sum()
        check("job_category_clean populated", have_cat > 0,
              str(df["job_category_clean"].value_counts().to_dict()))

    # ── CHECK 10: Minimum row count ────────────────────────────────────────────
    print("\n--- Row Count Check ---")
    check("At least 50 cleaned jobs present", len(df) >= 50, f"{len(df)} rows")
    if len(df) < 50:
        failures.append(f"Only {len(df)} rows — expected at least 50")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if failures:
        print(f"[FAIL] VALIDATION FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"   • {f}")
        print("=" * 60)
        raise ValueError(f"Validation failed: {failures}")
    else:
        print(f"[OK] ALL CHECKS PASSED — {len(df)} clean jobs ready for metrics")
        print("=" * 60)
    return True


if __name__ == "__main__":
    validate_data()
