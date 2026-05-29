"""
calculate_metrics.py
====================
Generates a comprehensive metrics_summary.json with ALL required fields:
  - jobs_by_category, average_salary_by_category
  - average_salary_by_experience_bracket
  - top_skills (top 10)
  - hybrid_jobs, unknown_remote_status
  - salary_coverage_by_source
  - all previously existing metrics

Place at: job_market_project/scripts/calculate_metrics.py
"""

import pandas as pd
import json
import os
from collections import Counter
from datetime import date

# ── Paths (Docker / Linux) ────────────────────────────────────────────────────
BASE_DIR     = os.environ.get("AIRFLOW_HOME", "/opt/airflow")
INPUT_FILE   = os.path.join(BASE_DIR, "data", "processed", "clean_ai_ml_data_jobs.csv")
MERGED_FILE  = os.path.join(BASE_DIR, "data", "merged",    "merged_raw_jobs.csv")
OUTPUT_FILE  = os.path.join(BASE_DIR, "data", "processed", "metrics_summary.json")


def safe_int(val):
    try:
        return int(val)
    except Exception:
        return 0


def safe_float(val):
    try:
        f = float(val)
        return round(f, 2) if f == f else 0.0   # NaN check
    except Exception:
        return 0.0


def generate_metrics():
    print("=" * 55)
    print("CALCULATE METRICS — Job Market Pipeline")
    print("=" * 55)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Cleaned CSV not found: {INPUT_FILE}")

    # Load
    try:
        df = pd.read_csv(INPUT_FILE, encoding="latin1")
    except Exception:
        df = pd.read_csv(INPUT_FILE, encoding="utf-8", errors="replace")

    print(f"Loaded {len(df)} rows from cleaned dataset")

    # ── Total before filter ────────────────────────────────────────────────────
    total_before = 0
    merged_df = None
    if os.path.exists(MERGED_FILE):
        try:
            merged_df = pd.read_csv(MERGED_FILE, encoding="latin1")
        except Exception:
            merged_df = pd.read_csv(MERGED_FILE, encoding="utf-8", errors="replace")
        total_before = len(merged_df)

    # ── Jobs by source ─────────────────────────────────────────────────────────
    jobs_by_source = {}
    if "source" in df.columns:
        for src, cnt in df["source"].value_counts().items():
            jobs_by_source[str(src)] = safe_int(cnt)

    # ── Remote status breakdown ────────────────────────────────────────────────
    remote_counts = {}
    remote_jobs, onsite_jobs, hybrid_jobs, unknown_remote = 0, 0, 0, 0
    if "remote_status" in df.columns:
        for status, cnt in df["remote_status"].value_counts().items():
            remote_counts[str(status)] = safe_int(cnt)
        remote_jobs  = remote_counts.get("Remote",  0)
        onsite_jobs  = remote_counts.get("On-site", 0)
        hybrid_jobs  = remote_counts.get("Hybrid",  0)
        unknown_remote = remote_counts.get("Unknown", 0)

    # Remote ratio percentage
    total = len(df)
    remote_ratio_pct = round(remote_jobs / total * 100, 1) if total > 0 else 0

    # ── Experience bracket distribution ────────────────────────────────────────
    exp_dist = {}
    entry_level_count = 0
    if "experience_bracket" in df.columns:
        for bracket, cnt in df["experience_bracket"].value_counts().items():
            exp_dist[str(bracket)] = safe_int(cnt)
        entry_level_count = exp_dist.get("0-1", 0)

    # ── Salary stats ───────────────────────────────────────────────────────────
    avg_salary = 0.0
    salary_coverage_pct = 0.0
    if "salary_mid_usd" in df.columns:
        df["_sal"] = pd.to_numeric(df["salary_mid_usd"], errors="coerce")
        df["_sal"] = df["_sal"].replace(0, pd.NA)
        valid_sal = df["_sal"].dropna()
        if len(valid_sal) > 0:
            avg_salary = round(valid_sal.mean(), 2)
        salary_coverage_pct = round(len(valid_sal) / total * 100, 1) if total > 0 else 0

    # ── Jobs by category ───────────────────────────────────────────────────────
    jobs_by_category = {}
    if "job_category_clean" in df.columns:
        for cat, cnt in df["job_category_clean"].value_counts().items():
            jobs_by_category[str(cat)] = safe_int(cnt)

    # ── Average salary by category ─────────────────────────────────────────────
    avg_salary_by_category = {}
    if "job_category_clean" in df.columns and "_sal" in df.columns:
        for cat, grp in df.groupby("job_category_clean"):
            vals = grp["_sal"].dropna()
            if len(vals) > 0:
                avg_salary_by_category[str(cat)] = round(vals.mean(), 2)

    # ── Average salary by experience bracket ──────────────────────────────────
    avg_salary_by_experience = {}
    if "experience_bracket" in df.columns and "_sal" in df.columns:
        for bracket, grp in df.groupby("experience_bracket"):
            vals = grp["_sal"].dropna()
            if len(vals) > 0:
                avg_salary_by_experience[str(bracket)] = round(vals.mean(), 2)

    # ── Top 10 skills ──────────────────────────────────────────────────────────
    top_skills = []
    if "extracted_skills" in df.columns:
        skill_counter = Counter()
        for skills_str in df["extracted_skills"].dropna():
            for skill in str(skills_str).split(","):
                skill = skill.strip()
                if skill:
                    skill_counter[skill] += 1
        top_skills = [
            {"skill": s, "count": c}
            for s, c in skill_counter.most_common(10)
        ]

    # ── Salary coverage by source ─────────────────────────────────────────────
    salary_coverage_by_source = {}
    if "source" in df.columns and "_sal" in df.columns:
        for src, grp in df.groupby("source"):
            total_src = len(grp)
            with_sal = grp["_sal"].dropna()
            pct = round(len(with_sal) / total_src * 100, 1) if total_src > 0 else 0
            salary_coverage_by_source[str(src)] = {
                "total_jobs": total_src,
                "with_salary": len(with_sal),
                "coverage_pct": pct,
            }

    # ── FX rates used (from patch step or fallback) ────────────────────────────
    fx_rates_used = {"USD": 1.0, "EUR": 1.08, "GBP": 1.25, "PKR": 0.0036}

    # ── Assignment analysis fields (Q1–Q15) for n8n / report ───────────────────
    df_raw = merged_df if merged_df is not None else df

    q1 = {str(k): safe_int(v) for k, v in df_raw["source"].value_counts().items()} if "source" in df_raw.columns else {}
    q3 = jobs_by_source.copy()
    q3_top = max(q3, key=q3.get) if q3 else "N/A"
    q4_pct = {k: round(v / total * 100, 2) for k, v in remote_counts.items()} if total > 0 else {}
    q5 = {}
    if "source" in df.columns and "remote_status" in df.columns:
        for src in df["source"].unique():
            q5[str(src)] = {str(k): safe_int(v) for k, v in df[df["source"] == src]["remote_status"].value_counts().items()}
    sal_valid = df["_sal"].dropna() if "_sal" in df.columns else pd.Series(dtype=float)
    q8_cnt = len(sal_valid)
    q8_med = round(float(sal_valid.median()), 2) if q8_cnt else 0.0
    skill_map = {}
    if "extracted_skills" in df.columns:
        sc = Counter()
        for skills_str in df["extracted_skills"].dropna():
            for skill in str(skills_str).split(","):
                skill = skill.strip().lower()
                if skill:
                    sc[skill] += 1
        skill_map = dict(sc.most_common(10))
    q12 = {str(k): safe_int(v) for k, v in df["company_name"].value_counts().head(10).items()} if "company_name" in df.columns else {}
    q13_top = max(jobs_by_category, key=jobs_by_category.get) if jobs_by_category else "N/A"
    q14 = {src: info.get("coverage_pct", 0) for src, info in salary_coverage_by_source.items()}
    q14_top = max(q14, key=q14.get) if q14 else "N/A"
    q15 = {
        "total_raw_records": len(df_raw),
        "total_clean_records": total,
        "filter_drop_rate_pct": round((1 - total / len(df_raw)) * 100, 2) if len(df_raw) > 0 else 0,
        "missing_title_pct": round(df["title"].isnull().mean() * 100, 2) if "title" in df.columns else 0,
        "missing_company_pct": round(df["company_name"].isnull().mean() * 100, 2) if "company_name" in df.columns else 0,
        "missing_salary_pct": round(df["salary_mid_usd"].isnull().mean() * 100, 2) if "salary_mid_usd" in df.columns else 0,
    }

    analysis_q = {
        "Q1_jobs_per_source_before_filter": q1,
        "Q2_total_jobs_after_filter": total,
        "Q3_jobs_per_source_after_filter": q3,
        "Q3_top_source": q3_top,
        "Q4_remote_status_distribution": remote_counts,
        "Q4_remote_status_percentage": q4_pct,
        "Q5_remote_by_source": q5,
        "Q6_entry_level_jobs_count": entry_level_count,
        "Q7_experience_bracket_distribution": exp_dist,
        "Q8_avg_salary_usd": avg_salary,
        "Q8_median_salary_usd": q8_med,
        "Q8_salary_data_count": q8_cnt,
        "Q9_avg_salary_by_category": avg_salary_by_category,
        "Q10_avg_salary_by_experience": avg_salary_by_experience,
        "Q11_top_10_skills": skill_map,
        "Q12_top_companies_by_job_count": q12,
        "Q13_jobs_by_category": jobs_by_category,
        "Q13_top_category": q13_top,
        "Q14_salary_coverage_by_source": q14,
        "Q14_top_salary_coverage_source": q14_top,
        "Q15_data_quality_summary": q15,
    }

    # ── Assemble final metrics payload ─────────────────────────────────────────
    metrics = {
        # ---- Basic info ----
        "run_date": str(date.today()),
        "pipeline_status": "Success",

        # ---- Volume ----
        "total_jobs_before_filter":  total_before,
        "total_jobs_after_filter":   total,

        # ---- Source breakdown ----
        "jobs_by_source": jobs_by_source,

        # ---- Remote status ----
        "remote_status_counts": remote_counts,
        "remote_status_ratio": {
            "Remote":  remote_jobs,
            "On-site": onsite_jobs,
            "Hybrid":  hybrid_jobs,
            "Unknown": unknown_remote,
        },
        "remote_ratio_pct":     remote_ratio_pct,
        "hybrid_jobs":          hybrid_jobs,
        "unknown_remote_status": unknown_remote,

        # ---- Experience ----
        "experience_bracket_distribution": exp_dist,
        "zero_to_one_year_jobs": entry_level_count,

        # ---- Salary ----
        "average_salary_usd":          avg_salary,
        "salary_coverage_pct":         salary_coverage_pct,
        "average_salary_by_category":  avg_salary_by_category,
        "average_salary_by_experience_bracket": avg_salary_by_experience,
        "salary_coverage_by_source":   salary_coverage_by_source,

        # ---- Category ----
        "jobs_by_category": jobs_by_category,

        # ---- Skills ----
        "top_skills": top_skills,

        # ---- FX ----
        "fx_rates_used": fx_rates_used,
        "fx_rate_date":  str(date.today()),

        # Assignment question fields (used by n8n notification workflow)
        **analysis_q,
    }

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(metrics, f, indent=4)

    print(f"\n[OK] Metrics saved to: {OUTPUT_FILE}")
    print(f"   Jobs after filter:       {total}")
    print(f"   Remote jobs:             {remote_jobs}  |  Hybrid: {hybrid_jobs}")
    print(f"   0-1 yr experience jobs:  {entry_level_count}")
    print(f"   Avg salary USD:          ${avg_salary:,.2f}")
    print(f"   Salary coverage:         {salary_coverage_pct}%")
    print(f"   Categories found:        {len(jobs_by_category)}")
    print(f"   Top skills extracted:    {len(top_skills)}")


if __name__ == "__main__":
    generate_metrics()
