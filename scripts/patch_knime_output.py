"""
patch_knime_output.py
=====================
Runs AFTER KNIME (or the Python fallback cleaner).
Ensures ALL 25 required schema columns exist with proper values:
  - salary_min_usd / salary_max_usd / salary_mid_usd  (live FX via Frankfurter)
  - experience_years_min / experience_years_max / experience_bracket
  - extracted_skills
  - job_category_clean
  - all other required fields padded if missing

Place at: job_market_project/scripts/patch_knime_output.py
"""

import pandas as pd
import os
import re
import json
import requests
from datetime import date

# ── Paths (Docker / Linux) ────────────────────────────────────────────────────
BASE_DIR = os.environ.get("AIRFLOW_HOME", "/opt/airflow")
INPUT_FILE  = os.path.join(BASE_DIR, "data", "processed", "clean_ai_ml_data_jobs.csv")
OUTPUT_FILE = INPUT_FILE   # overwrite in place

# ── Required 25-column schema ─────────────────────────────────────────────────
REQUIRED_SCHEMA = [
    "source", "job_id", "title", "company_name",
    "location_raw", "remote_status", "job_type",
    "category_raw", "tags_raw", "description",
    "publication_date", "job_url",
    "salary_text_raw", "salary_min_raw", "salary_max_raw", "currency_raw",
    "salary_min_usd", "salary_max_usd", "salary_mid_usd",
    "experience_years_min", "experience_years_max", "experience_bracket",
    "extracted_skills", "job_category_clean", "scrape_date",
]

# ── FX rate fetcher ────────────────────────────────────────────────────────────
def get_fx_rates():
    """Fetch live EUR->USD, GBP->USD, etc. from Frankfurter API."""
    rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.25, "PKR": 0.0036, "CAD": 0.74, "AUD": 0.65}
    try:
        r = requests.get("https://api.frankfurter.dev/v2/latest?base=USD", timeout=10)
        if r.status_code == 200:
            data = r.json()
            usd_rates = data.get("rates", {})
            # Invert: if 1 USD = X EUR, then 1 EUR = 1/X USD
            for currency, rate_vs_usd in usd_rates.items():
                if rate_vs_usd and rate_vs_usd > 0:
                    rates[currency.upper()] = round(1.0 / rate_vs_usd, 6)
            rates["USD"] = 1.0
            print(f"[FX] Live rates fetched for {len(rates)} currencies")
    except Exception as e:
        print(f"[FX] Could not fetch live rates: {e} — using fallback rates")
    return rates


# ── Salary extraction helpers ──────────────────────────────────────────────────
def parse_salary_raw(text):
    """Extract min/max salary numbers from a raw salary string."""
    if not text or str(text).strip() in ("", "nan"):
        return None, None
    text = str(text).replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    nums = [float(n) for n in nums if float(n) > 100]  # filter noise
    if not nums:
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)


def detect_currency(row):
    """Detect currency from raw fields."""
    for col in ("currency_raw", "salary_text_raw"):
        val = str(row.get(col, "")).upper()
        if "EUR" in val or "€" in val: return "EUR"
        if "GBP" in val or "£" in val: return "GBP"
        if "PKR" in val: return "PKR"
        if "CAD" in val: return "CAD"
        if "AUD" in val: return "AUD"
        if "USD" in val or "$" in val: return "USD"
    return "USD"


def to_usd(value, currency, fx_rates):
    if value is None or value == 0:
        return None
    rate = fx_rates.get(currency.upper(), 1.0)
    return round(float(value) * rate, 2)


# ── Experience extraction ──────────────────────────────────────────────────────
EXP_PATTERNS = [
    (r"(\d+)\+?\s*years?\s*(?:of\s+)?experience",     "min"),
    (r"(\d+)\s*[-–]\s*(\d+)\s*years?",                "range"),
    (r"at\s+least\s+(\d+)\s*years?",                  "min"),
    (r"minimum\s+(\d+)\s*years?",                      "min"),
    (r"(\d+)\s*yr",                                    "min"),
]

def extract_experience(text):
    if not text or str(text).strip() in ("", "nan"):
        return None, None
    text = str(text).lower()
    for pattern, kind in EXP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            if kind == "range":
                lo, hi = int(m.group(1)), int(m.group(2))
                return lo, hi
            else:
                lo = int(m.group(1))
                return lo, lo + 2
    return None, None


def exp_to_bracket(lo, hi):
    if lo is None:
        return "Not mentioned"
    if lo <= 1:
        return "0-1"
    if lo <= 3:
        return "1-3"
    if lo <= 5:
        return "3-5"
    if lo <= 8:
        return "5-8"
    return "8+"


# ── Skill extraction ───────────────────────────────────────────────────────────
SKILLS_LIST = [
    ("Python", ["python"]),
    ("SQL", [" sql ", "sql,", "sql.", "postgresql", "mysql", "sqlite", "bigquery"]),
    ("R", [" r,", " r ", "r programming", "rstudio"]),
    ("Spark", ["pyspark", "apache spark", " spark"]),
    ("Hadoop", ["hadoop"]),
    ("Tableau", ["tableau"]),
    ("Power BI", ["power bi", "powerbi"]),
    ("Machine Learning", ["machine learning", " ml ", "scikit", "sklearn"]),
    ("Deep Learning", ["deep learning", "neural network", "tensorflow", "keras", "pytorch"]),
    ("NLP", ["nlp", "natural language", "bert", "gpt", "llm", "large language"]),
    ("Airflow", ["airflow"]),
    ("dbt", [" dbt", "dbt "]),
    ("AWS", [" aws ", "amazon web services", "s3", "ec2", "sagemaker"]),
    ("GCP", ["google cloud", " gcp ", "bigquery"]),
    ("Azure", [" azure", "microsoft azure"]),
    ("Docker", ["docker"]),
    ("Kubernetes", ["kubernetes", " k8s"]),
    ("Git", [" git", "github", "gitlab"]),
    ("Excel", [" excel"]),
    ("Scala", ["scala"]),
]

def extract_skills(text):
    if not text or str(text).strip() in ("", "nan"):
        return ""
    text_lower = str(text).lower()
    found = []
    for skill_name, keywords in SKILLS_LIST:
        if any(kw in text_lower for kw in keywords):
            found.append(skill_name)
    return ", ".join(found)


# ── Job category classifier ────────────────────────────────────────────────────
def classify_job_category(title, tags="", category=""):
    text = f"{title} {tags} {category}".lower()
    if any(k in text for k in ["data engineer", "etl", "pipeline", "spark", "kafka", "databricks", "dbt"]):
        return "Data Engineering"
    if any(k in text for k in ["machine learning", " ml ", "mlops", "ai engineer", "deep learning", "llm"]):
        return "AI/ML Engineering"
    if any(k in text for k in ["data scientist", "data science", "nlp", "research scientist"]):
        return "Data Science"
    if any(k in text for k in ["data analyst", "business analyst", "bi analyst", "analytics", "tableau", "power bi"]):
        return "Data Analytics"
    if any(k in text for k in ["data architect", "cloud architect", "solution architect"]):
        return "Data Architecture"
    if any(k in text for k in ["data manager", "head of data", "chief data", "vp data"]):
        return "Data Management"
    return "Other Data"


# ── Main patch function ────────────────────────────────────────────────────────
def patch_data():
    print("=" * 55)
    print("PATCH KNIME OUTPUT — ensuring all 25 schema columns")
    print("=" * 55)

    if not os.path.exists(INPUT_FILE):
        # Try to create from merged if KNIME produced nothing
        merged = os.path.join(BASE_DIR, "data", "merged", "merged_raw_jobs.csv")
        if os.path.exists(merged):
            print(f"[WARN] Processed file not found. Copying from merged: {merged}")
            import shutil
            os.makedirs(os.path.dirname(INPUT_FILE), exist_ok=True)
            shutil.copy(merged, INPUT_FILE)
        else:
            raise FileNotFoundError(f"Neither processed nor merged CSV found at {BASE_DIR}/data/")

    # Load
    try:
        df = pd.read_csv(INPUT_FILE, encoding="latin1", dtype=str)
    except Exception:
        df = pd.read_csv(INPUT_FILE, encoding="utf-8", errors="replace", dtype=str)
    df = df.fillna("")
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    # ── Step 1: Add any completely missing columns ─────────────────────────────
    for col in REQUIRED_SCHEMA:
        if col not in df.columns:
            df[col] = ""
            print(f"  [+] Added missing column: {col}")

    # ── Step 2: Bridge column aliases ─────────────────────────────────────────
    # KNIME may output 'description_clean' — alias it to 'description'
    if "description" not in df.columns or df["description"].eq("").all():
        for alias in ("description_clean", "desc", "job_description"):
            if alias in df.columns and not df[alias].eq("").all():
                df["description"] = df[alias]
                print(f"  [~] Aliased '{alias}' -> 'description'")
                break

    # salary_min_raw / salary_max_raw from KNIME 'salary_min_clean' etc.
    for raw_col, knime_col in [("salary_min_raw", "salary_min_clean"),
                                ("salary_max_raw", "salary_max_clean")]:
        if (df[raw_col].eq("").all()) and (knime_col in df.columns):
            df[raw_col] = df[knime_col]

    # ── Step 3: Live FX rates ──────────────────────────────────────────────────
    fx_rates = get_fx_rates()

    # ── Step 4: Salary USD columns ─────────────────────────────────────────────
    print("[Salary] Computing USD columns...")
    need_salary = (
        df["salary_min_usd"].eq("") |
        df["salary_max_usd"].eq("") |
        df["salary_mid_usd"].eq("")
    )

    def compute_salary_usd(row):
        currency = detect_currency(row)
        # Try raw numeric columns first
        lo = pd.to_numeric(row.get("salary_min_raw", ""), errors="coerce")
        hi = pd.to_numeric(row.get("salary_max_raw", ""), errors="coerce")
        # Fall back to parsing salary_text_raw
        if pd.isna(lo) or lo == 0:
            lo, hi = parse_salary_raw(row.get("salary_text_raw", ""))
        lo_usd = to_usd(lo, currency, fx_rates)
        hi_usd = to_usd(hi, currency, fx_rates)
        if lo_usd and hi_usd:
            mid = round((lo_usd + hi_usd) / 2, 2)
        elif lo_usd:
            mid = lo_usd
        else:
            mid = None
        return pd.Series({
            "salary_min_usd": lo_usd if lo_usd else "",
            "salary_max_usd": hi_usd if hi_usd else "",
            "salary_mid_usd": mid if mid else "",
            "currency_raw": currency,
        })

    salary_computed = df.apply(compute_salary_usd, axis=1)
    for col in ("salary_min_usd", "salary_max_usd", "salary_mid_usd", "currency_raw"):
        mask = df[col].eq("")
        df.loc[mask, col] = salary_computed.loc[mask, col].astype(str)

    have_salary = df["salary_mid_usd"].replace("", pd.NA).notna().sum()
    print(f"  Salary coverage: {have_salary}/{len(df)} rows ({100*have_salary//len(df)}%)")

    # ── Step 5: Experience columns ─────────────────────────────────────────────
    print("[Experience] Extracting experience brackets...")
    need_exp = df["experience_bracket"].eq("") | df["experience_bracket"].eq("Not mentioned")

    def compute_experience(row):
        text = str(row.get("description", "")) + " " + str(row.get("title", ""))
        lo, hi = extract_experience(text)
        bracket = exp_to_bracket(lo, hi)
        return pd.Series({
            "experience_years_min": lo if lo is not None else "",
            "experience_years_max": hi if hi is not None else "",
            "experience_bracket": bracket,
        })

    exp_computed = df[need_exp].apply(compute_experience, axis=1)
    for col in ("experience_years_min", "experience_years_max", "experience_bracket"):
        df.loc[need_exp, col] = exp_computed[col].astype(str).values

    bracket_dist = df["experience_bracket"].value_counts().to_dict()
    print(f"  Brackets: {bracket_dist}")

    # ── Step 6: Skills extraction ──────────────────────────────────────────────
    print("[Skills] Extracting skills from description...")
    need_skills = df["extracted_skills"].eq("")
    df.loc[need_skills, "extracted_skills"] = df.loc[need_skills].apply(
        lambda r: extract_skills(str(r.get("description", "")) + " " + str(r.get("title", ""))),
        axis=1
    ).astype(str).values
    have_skills = df["extracted_skills"].replace("", pd.NA).notna().sum()
    print(f"  Skills coverage: {have_skills}/{len(df)} rows")

    # ── Step 7: Job category ───────────────────────────────────────────────────
    print("[Category] Classifying job categories...")
    need_cat = df["job_category_clean"].eq("")
    df.loc[need_cat, "job_category_clean"] = df.loc[need_cat].apply(
        lambda r: classify_job_category(r.get("title", ""), r.get("tags_raw", ""), r.get("category_raw", "")),
        axis=1
    ).astype(str).values
    cat_dist = df["job_category_clean"].value_counts().to_dict()
    print(f"  Categories: {cat_dist}")

    # ── Step 8: job_id fallback ────────────────────────────────────────────────
    if df["job_id"].eq("").all():
        df["job_id"] = [f"job_{i:05d}" for i in range(len(df))]

    # ── Step 9: scrape_date fallback ──────────────────────────────────────────
    if df["scrape_date"].eq("").all():
        df["scrape_date"] = str(date.today())

    # ── Step 10: Reorder to required schema + keep extras ─────────────────────
    extra_cols = [c for c in df.columns if c not in REQUIRED_SCHEMA]
    final_cols = REQUIRED_SCHEMA + extra_cols
    df = df[final_cols]

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")
    print(f"\n[OK] Patched file saved: {OUTPUT_FILE}")
    print(f"   Rows: {len(df)}  |  Columns: {len(df.columns)}")
    print(f"   Schema columns present: {sum(c in df.columns for c in REQUIRED_SCHEMA)}/25")


if __name__ == "__main__":
    patch_data()

