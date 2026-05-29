import requests
import csv
import datetime
import os

def extract_remotejobs():
    print("=== Extracting from RemoteJobs.org ===")

    scrape_date = datetime.date.today().isoformat()
    os.makedirs("data/raw", exist_ok=True)

    all_jobs = []

    # Try multiple categories
    categories = ["data-science", "software-dev", "devops-sysadmin"]

    for category in categories:
        url = f"https://remotejobs.org/api/v1/jobs?category={category}&limit=50"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            jobs = response.json().get("data", [])
            all_jobs.extend(jobs)
            print(f"  Category '{category}': {len(jobs)} jobs")
        except Exception as e:
            print(f"  ERROR category '{category}': {e}")

    # Remove duplicates
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        jid = str(job.get("id", ""))
        if jid not in seen:
            seen.add(jid)
            unique_jobs.append(job)

    print(f"Total unique jobs: {len(unique_jobs)}")

    output_file = "data/raw/raw_remotejobs_jobs.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source", "job_id", "title", "company_name",
            "location_raw", "remote_status", "job_type",
            "description", "tags_raw", "publication_date",
            "job_url", "salary_min_raw", "salary_max_raw",
            "salary_text_raw", "scrape_date"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for job in unique_jobs:
            desc = job.get("description", "")
            desc = " ".join(desc.split())

            company = job.get("company", {})
            if isinstance(company, dict):
                company_name = company.get("name", "")
            else:
                company_name = str(company)

            writer.writerow({
                "source": "RemoteJobs.org",
                "job_id": str(job.get("id", "")),
                "title": job.get("title", ""),
                "company_name": company_name,
                "location_raw": job.get("location", ""),
                "remote_status": "Remote",
                "job_type": job.get("type", ""),
                "description": desc[:1000],
                "tags_raw": job.get("category", ""),
                "publication_date": job.get("posted_at", ""),
                "job_url": job.get("url", ""),
                "salary_min_raw": job.get("salary_min", ""),
                "salary_max_raw": job.get("salary_max", ""),
                "salary_text_raw": job.get("salary_text", ""),
                "scrape_date": scrape_date
            })

    print(f"Saved {len(unique_jobs)} jobs to {output_file}")
    print("=== RemoteJobs.org DONE ===\n")

if __name__ == "__main__":
    extract_remotejobs()