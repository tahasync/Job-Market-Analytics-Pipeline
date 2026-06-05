"""
KNIME Flask API — Job Market Pipeline
Airflow (Docker) -> Flask API (Windows host) -> batch file -> KNIME
"""

from flask import Flask, jsonify, request
import os
import subprocess
import threading

app = Flask(__name__)

PROJECT_DIR = os.environ.get(
    "JOB_MARKET_PROJECT_DIR",
    r"C:\Users\Tahan\Desktop\Assignment 3",
)
BAT_FILE = os.environ.get(
    "KNIME_BAT_FILE",
    os.path.join(PROJECT_DIR, "flask_api", "run_job_market_cleaning.bat"),
)
API_KEY = os.environ.get("KNIME_API_KEY", "")
# ^ falls back to default if env var not set; set KNIME_API_KEY in .env for production
PORT = int(os.environ.get("FLASK_PORT", "8005"))

DATA_MERGED = os.path.join(PROJECT_DIR, "data", "merged", "merged_raw_jobs.csv")
DATA_PROCESSED = os.path.join(PROJECT_DIR, "data", "processed", "clean_ai_ml_data_jobs.csv")

run_lock = threading.Lock()


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "KNIME Flask API is running",
        "status": "ready",
        "architecture": "Airflow -> Flask API -> batch file -> KNIME",
        "project_dir": PROJECT_DIR,
        "endpoints": {
            "GET /": "Health check",
            "GET /status": "Pipeline status",
            "POST /run-knime": "Run KNIME workflow via batch file",
        },
    })


@app.route("/run-knime", methods=["POST"])
def run_knime():
    received_key = request.headers.get("X-API-Key")
    if received_key != API_KEY:
        return jsonify({"status": "error", "message": "Unauthorized request"}), 401

    if not os.path.exists(BAT_FILE):
        return jsonify({
            "status": "error",
            "message": f"Batch file not found: {BAT_FILE}",
        }), 404

    if not run_lock.acquire(blocking=False):
        return jsonify({
            "status": "error",
            "message": "KNIME workflow is already running",
        }), 409

    try:
        print("[Flask] Running KNIME batch file...")
        result = subprocess.run(
            ["cmd", "/c", BAT_FILE],
            capture_output=True,
            text=True,
            timeout=7200,
            cwd=os.path.dirname(BAT_FILE),
        )
        print(f"[Flask] KNIME exit code: {result.returncode}")

        if result.returncode != 0:
            return jsonify({
                "status": "failed",
                "message": "KNIME workflow failed",
                "return_code": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }), 500

        output_exists = os.path.exists(DATA_PROCESSED)
        output_size = os.path.getsize(DATA_PROCESSED) if output_exists else 0

        return jsonify({
            "status": "success",
            "message": "KNIME workflow executed successfully",
            "return_code": result.returncode,
            "output_file_exists": output_exists,
            "output_file_size_bytes": output_size,
            "stdout": result.stdout[-1000:],
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "failed",
            "message": "KNIME workflow timed out after 7200 seconds",
        }), 504

    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Unexpected error: {exc}",
        }), 500

    finally:
        run_lock.release()


@app.route("/status", methods=["GET"])
def status():
    locked = run_lock.acquire(blocking=False)
    if locked:
        run_lock.release()
    return jsonify({
        "api_status": "running",
        "project_dir": PROJECT_DIR,
        "bat_file": BAT_FILE,
        "bat_file_exists": os.path.exists(BAT_FILE),
        "input_csv_exists": os.path.exists(DATA_MERGED),
        "output_csv_exists": os.path.exists(DATA_PROCESSED),
        "output_csv_size": os.path.getsize(DATA_PROCESSED) if os.path.exists(DATA_PROCESSED) else 0,
        "knime_running": not locked,
    })


if __name__ == "__main__":
    print("=" * 55)
    print("KNIME Flask API — Job Market Pipeline")
    print("=" * 55)
    print(f"Project:  {PROJECT_DIR}")
    print(f"Batch:    {BAT_FILE}")
    print(f"Port:     {PORT}")
    print(f"Endpoint: POST http://localhost:{PORT}/run-knime")
    print("=" * 55)
    app.run(host="0.0.0.0", port=PORT, debug=False)
