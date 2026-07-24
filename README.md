# Job Market ETL Pipeline

A multi-tool data engineering pipeline that extracts job postings from 4 public APIs (Arbeitnow, RemoteOK, Himalayas, RemoteJobs), cleans and transforms them via KNIME, merges and validates the results, calculates market metrics, and generates a Word report — orchestrated by Apache Airflow and notified via n8n.

## What it does

Python scripts extract live job data from 4 APIs in parallel, merge and standardize schemas into a single CSV, then send it to KNIME Analytics Platform (running on the Windows host) for AI/ML role filtering, salary conversion via Frankfurter FX rates, and experience extraction. Post-KNIME patching fixes column types, validation checks data quality, and metrics calculation produces Q1–Q15 analysis results. A Word report generator produces `final_report.docx`. The entire pipeline runs daily via an Apache Airflow DAG, with n8n sending a summary email on completion.

**Note:** KNIME runs on the Windows host, not in Docker. The Flask API bridge communicates between Airflow (Docker) and KNIME (Windows) via `host.docker.internal`. The KNIME workflow file (`.knwf`) is a binary format that cannot be reviewed in text — it requires the KNIME GUI to open.

## Tech stack

- **Orchestration:** Apache Airflow 2.9.1 (Docker), n8n
- **ETL:** KNIME Analytics Platform (Windows host, HTTP bridge via Flask)
- **Backend:** Python (requests, pandas), Flask (API bridge)
- **Database:** PostgreSQL (Airflow metadata)
- **Infrastructure:** Docker Compose, Windows batch/PowerShell scripts

## Data sources

- Arbeitnow API, RemoteOK API, Himalayas API, RemoteJobs.org API
- Frankfurter API (FX rates for salary USD conversion)

## Pipeline stages

1. Extract — 4 API pullers run in parallel
2. Merge — Standardize schemas, combine into single CSV
3. Clean (KNIME) — Filter AI/ML/Data roles, extract salary & experience, convert FX
4. Patch — Post-KNIME column fixes and enrichment
5. Validate — Schema, null, and duplicate checks
6. Metrics — Q1–Q15 analysis metrics
7. Report — Generate `final_report.docx`
8. Notify — n8n sends summary email
9. Archive — Copy outputs to date-stamped folder

## Setup

```bash
git clone https://github.com/tahasync/Job-Market-Analytics-Pipeline.git
cd Job-Market-Analytics-Pipeline
echo "AIRFLOW_UID=50000" > .env
pip install -r flask_api/requirements.txt
# Start Docker services
powershell -ExecutionPolicy Bypass -File .\compose-up.ps1
# Also run knime_flask_api.py on Windows host for KNIME integration
```

## Status

**Academic project — functional but architecture-dependent.** The extraction, merge, validation, metrics, and report scripts work independently. The full pipeline requires a Windows host with KNIME Analytics Platform installed, Docker Desktop, and the Flask bridge running — making it non-portable to Linux/Mac without architecture changes. No automated tests. No pinned dependency versions (no `requirements.txt` at root level).

*Assignment 3 — Tools and Techniques for Data Science, University of Central Punjab*