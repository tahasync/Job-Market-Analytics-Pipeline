# 📊 Job Market Analytics Pipeline

An end-to-end **data engineering pipeline** that extracts, cleans, transforms, and analyzes job postings from multiple public APIs. Built for the **Tools and Techniques for Data Science** course at the **University of Central Punjab**.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Airflow-2.x-017CEE?logo=apacheairflow&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![KNIME](https://img.shields.io/badge/KNIME-FDD10C?logo=knime&logoColor=black)
![n8n](https://img.shields.io/badge/n8n-EA4C89?logo=n8n&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)

---

## 🏗️ Architecture

```
Public Job APIs (Arbeitnow, RemoteOK, Himalayas, RemoteJobs.org)
        │
        ▼
  Python Extract Scripts ──► Merge & Standardize
        │
        ▼
  KNIME Analytics Platform ──► AI/ML filtering, salary conversion, experience extraction
        │
        ▼
  Patch & Validate ──► Metrics Calculation ──► Word Report
        │                                           │
        ▼                                           ▼
  n8n Notification (Email Alert)           final_report.docx
        │
        ▼
  Archive Outputs
```

**Orchestrated by Apache Airflow** — all steps run daily via a DAG.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|-----------|---------|
| **Apache Airflow** | Workflow orchestration (Docker) |
| **KNIME Analytics Platform** | Data cleaning & transformation |
| **n8n** | Automation & email notifications |
| **Flask** | REST API bridge (Airflow Docker → Windows KNIME) |
| **PostgreSQL** | Airflow metadata database |
| **Docker / Docker Compose** | Containerized services |
| **Python** | Extraction, merging, validation, metrics, report generation |
| **Pandas** | Data manipulation |

---

## 📡 Data Sources

| Source | Endpoint |
|--------|----------|
| Arbeitnow | `arbeitnow.com/api/job-board-api` |
| RemoteOK | `remoteok.com/api` |
| Himalayas | `himalayas.app/jobs/api/search?q=data` |
| RemoteJobs.org | `remotejobs.org/api/v1/jobs?category=data-science` |
| Frankfurter API | FX rates for salary USD conversion |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker Desktop
- KNIME Analytics Platform installed
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/mtahanaeem/Assignment3-DataScience.git
cd Assignment3-DataScience

# Create .env file
echo "AIRFLOW_UID=50000" > .env
echo "KNIME_API_KEY=your_api_key" >> .env
echo "STUDENT_EMAIL=your@email.com" >> .env
echo "STUDENT_NAME=Your Name" >> .env

# Install Python dependencies
pip install -r flask_api/requirements.txt

# Start the pipeline
powershell -ExecutionPolicy Bypass -File .\compose-up.ps1
```

### URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow UI | `http://localhost:8080` | `airflow` / `airflow` |
| n8n UI | `http://localhost:5678` | Set on first login |
| Flask API | `http://localhost:8005` | API key required |

---

## 📋 Pipeline Steps

1. **📥 Extract** — Pulls job data from 4 APIs in parallel
2. **🔀 Merge** — Standardizes schemas and combines into one CSV
3. **🧹 Clean (KNIME)** — Filters AI/ML/Data roles, extracts salary & experience, converts FX
4. **🩹 Patch** — Post-KNIME column fixes and enrichment
5. **✅ Validate** — Data quality checks (schema, nulls, duplicates)
6. **📊 Metrics** — Generates analysis metrics (Q1–Q15)
7. **📧 Notify** — Sends summary email via n8n
8. **📦 Archive** — Copies outputs to date-stamped archive folder

---

## 📁 Project Structure

```
├── dags/
│   └── job_market_pipeline.py        # Airflow DAG
├── flask_api/
│   ├── knime_flask_api.py            # Flask REST API
│   └── run_job_market_cleaning.bat   # KNIME launcher
├── scripts/
│   ├── extract_*.py                  # 4 API extraction scripts
│   ├── merge_sources.py              # CSV merge & standardize
│   ├── patch_knime_output.py         # Post-KNIME patching
│   ├── validate_outputs.py           # Data quality checks
│   ├── calculate_metrics.py          # Analysis metrics
│   └── start_flask_api.ps1           # Manual Flask launcher
├── knime_workflow/
│   └── job_market_cleaning.knwf      # KNIME workflow
├── n8n/
│   └── job_market_alert.json         # n8n notification workflow
├── report/
│   ├── generate_report.py            # Word report generator
│   └── final_report.docx             # Generated report
├── compose-up.ps1                    # One-command startup
├── docker-compose.yaml               # Docker services
├── .env                              # Environment variables (excluded from git)
└── README.md
```

---

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AIRFLOW_UID` | Docker user ID for Airflow | Yes |
| `KNIME_API_KEY` | Shared secret for Flask API auth | Yes |
| `STUDENT_EMAIL` | Email for n8n notifications | Yes |
| `STUDENT_NAME` | Student name for report | Yes |

---

## 👤 Author

**Muhammad Taha Naeem** — University of Central Punjab, Lahore  
Faculty of IT & CS — Department of Applied Computing & Technologies  
Tools and Techniques for Data Science — Assignment 3
