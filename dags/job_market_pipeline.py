"""
job_market_pipeline.py
======================
Comprehensive Airflow DAG for the Job Market Data Pipeline.
Architecture:
  Extract -> Merge -> KNIME (Flask API) -> Patch -> Validate -> Metrics -> n8n -> Archive

DAG schedule: once per day via @daily
"""

from airflow import DAG
from airflow.decorators import dag, task
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import sys
import os
import json
import requests
import shutil
from collections import Counter

# ── Paths (mounted into Airflow container) ─────────────────────────────────
BASE_PATH = "/opt/airflow"
SCRIPTS_PATH = os.path.join(BASE_PATH, "scripts")

# Flask API running on Windows host (accessed via host.docker.internal)
FLASK_API_URL = "http://host.docker.internal:8005/run-knime"
FLASK_API_KEY = os.environ.get("KNIME_API_KEY", "")

# n8n webhook (inside Docker network, accessible via service name)
N8N_WEBHOOK_URL = "http://n8n:5678/webhook/job-market"

default_args = {
    "owner": "Muhammad Taha",
    "depends_on_past": False,
    "start_date": datetime(2026, 5, 10),
    "retries": 0,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": False,
}


def run_script(script_name, raise_on_error=True):
    script_path = os.path.join(SCRIPTS_PATH, script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True, text=True, cwd=BASE_PATH,
        env={**os.environ, "AIRFLOW_HOME": BASE_PATH},
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"STDERR:\n{result.stderr}")
        if raise_on_error:
            raise RuntimeError(f"{script_name} failed with exit code {result.returncode}")
        else:
            print(f"WARNING: {script_name} returned non-zero — continuing.")


# ── Task functions ─────────────────────────────────────────────────────────

def extract_arbeitnow():
    run_script("extract_arbeitnow.py")

def extract_remoteok():
    run_script("extract_remoteok.py")

def extract_himalayas():
    run_script("extract_himalayas.py")

def extract_remotejobs():
    run_script("extract_remotejobs.py")

def merge_sources():
    run_script("merge_sources.py")


def run_knime_workflow():
    """
    Triggers KNIME workflow via Flask API running on Windows.
    Architecture: Airflow (Docker) -> Flask API (Windows) -> batch file -> KNIME
    """
    headers = {"X-API-Key": FLASK_API_KEY}
    print(f"[Flask] Calling KNIME Flask API at {FLASK_API_URL}")
    try:
        response = requests.post(FLASK_API_URL, headers=headers, timeout=7200)
        print(f"[Flask] Response HTTP {response.status_code}: {response.text[:500]}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot reach KNIME Flask API at {FLASK_API_URL}. "
            f"Ensure start_flask_api.ps1 is running on Windows. Error: {e}"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("KNIME Flask API timed out after 7200 seconds")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"KNIME Flask API request failed: {e}")


def patch_knime_output():
    run_script("patch_knime_output.py")

def validate_clean_output():
    run_script("validate_outputs.py")

def calculate_metrics():
    run_script("calculate_metrics.py")


def trigger_n8n_workflow(**context):
    pipeline_state = "success"
    error_details = None

    ti = context.get("ti")
    if ti:
        dag_run = ti.dag_run
        failed_tasks = []
        for task_id in dag_run.dag.task_ids:
            if task_id == ti.task_id:
                continue
            try:
                state = ti.xcom_pull(task_ids=task_id, key="return_value")
            except Exception:
                state = None
            task_instance = dag_run.get_task_instance(task_id)
            if task_instance and task_instance.state in ("failed", "upstream_failed"):
                failed_tasks.append(task_id)

        if failed_tasks:
            pipeline_state = "failed"
            error_details = f"Failed tasks: {', '.join(failed_tasks)}"

    metrics_path = os.path.join(BASE_PATH, "data", "processed", "metrics_summary.json")
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)
    else:
        metrics = {
            "pipeline_status": pipeline_state,
            "message": "Metrics file not found",
        }

    metrics["run_date"] = metrics.get("run_date", datetime.now().date().isoformat())
    metrics["pipeline_status"] = pipeline_state
    if error_details:
        metrics["error_details"] = error_details

    payload = {
        **metrics,
        "student_name": os.environ.get("STUDENT_NAME", "Muhammad Taha"),
        "student_email": os.environ.get("STUDENT_EMAIL", ""),
        "source": "airflow",
        "pipeline": "job_market_pipeline",
        "triggered_at": datetime.now().isoformat(),
    }

    clean_csv = os.path.join(BASE_PATH, "data", "processed", "clean_ai_ml_data_jobs.csv")
    if not os.path.exists(clean_csv):
        raise FileNotFoundError(
            f"KNIME output missing before n8n: {clean_csv}. "
            "Ensure run_knime_workflow and patch_knime_output succeeded."
        )
    payload["knime_output_rows"] = payload.get("Q2_total_jobs_after_filter", 0)
    payload["knime_output_file"] = "data/processed/clean_ai_ml_data_jobs.csv"

    try:
        response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=60)
        print(f"n8n webhook -> HTTP {response.status_code}: {response.text[:300]}")
        if response.status_code >= 400:
            raise RuntimeError(
                f"n8n webhook failed ({response.status_code}). "
                "Activate workflow 'Taha Job Market Pipeline Alert System' in n8n UI. "
                f"URL: {N8N_WEBHOOK_URL}"
            )
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Cannot reach n8n at {N8N_WEBHOOK_URL}: {e}") from e


def archive_outputs():
    today = str(datetime.now().date())
    archive_dir = os.path.join(BASE_PATH, "data", "archive", today)
    os.makedirs(archive_dir, exist_ok=True)

    files_to_archive = [
        os.path.join(BASE_PATH, "data", "merged", "merged_raw_jobs.csv"),
        os.path.join(BASE_PATH, "data", "processed", "clean_ai_ml_data_jobs.csv"),
        os.path.join(BASE_PATH, "data", "processed", "metrics_summary.json"),
    ]

    archived = 0
    for f in files_to_archive:
        if os.path.exists(f):
            dest = os.path.join(archive_dir, os.path.basename(f))
            shutil.copy(f, dest)
            print(f"Archived: {os.path.basename(f)} -> {archive_dir}")
            archived += 1
        else:
            print(f"WARNING: Could not archive (not found): {f}")

    print(f"Archived {archived}/{len(files_to_archive)} files to {archive_dir}")


# ── DAG definition ─────────────────────────────────────────────────────────

with DAG(
    dag_id="job_market_pipeline",
    default_args=default_args,
    description="Job Market Pipeline: Extract -> Merge -> KNIME(Flask API) -> Patch -> Validate -> Metrics -> n8n -> Archive",
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["job-market", "assignment3"],
) as dag:

    t1 = PythonOperator(task_id="extract_arbeitnow", python_callable=extract_arbeitnow, retries=1)
    t2 = PythonOperator(task_id="extract_remoteok", python_callable=extract_remoteok, retries=1)
    t3 = PythonOperator(task_id="extract_himalayas", python_callable=extract_himalayas, retries=1)
    t4 = PythonOperator(task_id="extract_remotejobs", python_callable=extract_remotejobs, retries=1)
    t5 = PythonOperator(task_id="merge_sources", python_callable=merge_sources)
    t6 = PythonOperator(task_id="run_knime_workflow", python_callable=run_knime_workflow, retries=1, execution_timeout=timedelta(hours=2))
    t7 = PythonOperator(task_id="patch_knime_output", python_callable=patch_knime_output)
    t8 = PythonOperator(task_id="validate_clean_output", python_callable=validate_clean_output)
    t9 = PythonOperator(task_id="calculate_metrics", python_callable=calculate_metrics)
    t10 = PythonOperator(task_id="trigger_n8n_workflow", python_callable=trigger_n8n_workflow, provide_context=True, trigger_rule="all_done")
    t11 = PythonOperator(task_id="archive_outputs", python_callable=archive_outputs)

    [t1, t2, t3, t4] >> t5 >> t6 >> t7 >> t8 >> t9 >> t10 >> t11
