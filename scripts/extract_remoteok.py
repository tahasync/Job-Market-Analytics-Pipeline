import requests
import csv
import datetime
import os

def extract_remoteok():
    print("=== Extracting from RemoteOK ===")

    url = "https://remoteok.com/api"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        raw_data = response.json()
        # First item is metadata, skip it
        jobs = [j for j in raw_data if isinstance(j, dict) and "position" in j]
        print(f"API returned {len(jobs)} jobs")
    except Exception as e:
        print(f"ERROR fetching RemoteOK: {e}")
        return

    scrape_date = datetime.date.today().isoformat()
    os.makedirs("data/raw", exist_ok=True)

    output_file = "data/raw/raw_remoteok_jobs.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source", "job_id", "title", "company_name",
            "location_raw", "remote_status", "job_type",
            "description", "tags_raw", "publication_date",
            "job_url", "salary_text_raw",
            "salary_min_raw", "salary_max_raw", "scrape_date"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for job in jobs:
            desc = job.get("description", "")
            desc = " ".join(desc.split())

            sal_min = job.get("salary_min", "")
            sal_max = job.get("salary_max", "")

            # Build salary text
            salary_text = ""
            if sal_min and sal_max:
                salary_text = f"${sal_min} - ${sal_max}"

            writer.writerow({
                "source": "RemoteOK",
                "job_id": str(job.get("id", "")),
                "title": job.get("position", ""),
                "company_name": job.get("company", ""),
                "location_raw": job.get("location", "Worldwide"),
                "remote_status": "Remote",
                "job_type": "",
                "description": desc[:1000],
                "tags_raw": "|".join(job.get("tags", [])),
                "publication_date": job.get("date", ""),
                "job_url": "https://remoteok.com" + job.get("url", ""),
                "salary_text_raw": salary_text,
                "salary_min_raw": sal_min,
                "salary_max_raw": sal_max,
                "scrape_date": scrape_date
            })

    print(f"Saved {len(jobs)} jobs to {output_file}")
    print("=== RemoteOK DONE ===\n")

if __name__ == "__main__":
    extract_remoteok()