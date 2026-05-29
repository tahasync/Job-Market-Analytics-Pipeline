import requests
import csv
import datetime
import os

def extract_arbeitnow():
    print("=== Extracting from Arbeitnow ===")
    
    url = "https://www.arbeitnow.com/api/job-board-api"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        jobs = data.get("data", [])
        print(f"API returned {len(jobs)} jobs")
    except Exception as e:
        print(f"ERROR fetching Arbeitnow: {e}")
        return

    scrape_date = datetime.date.today().isoformat()
    os.makedirs("data/raw", exist_ok=True)

    output_file = "data/raw/raw_arbeitnow_jobs.csv"

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source", "job_id", "title", "company_name",
            "location_raw", "remote_status", "job_type",
            "description", "tags_raw", "publication_date",
            "job_url", "salary_text_raw", "scrape_date"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for job in jobs:
            # Clean description - remove HTML
            desc = job.get("description", "")
            desc = desc.replace("<br>", " ").replace("</br>", " ")
            desc = desc.replace("<p>", " ").replace("</p>", " ")
            desc = desc.replace("<li>", " ").replace("</li>", " ")
            desc = desc.replace("<ul>", " ").replace("</ul>", " ")
            desc = desc.replace("<strong>", "").replace("</strong>", "")
            desc = " ".join(desc.split())  # remove extra spaces

            writer.writerow({
                "source": "Arbeitnow",
                "job_id": job.get("slug", ""),
                "title": job.get("title", ""),
                "company_name": job.get("company_name", ""),
                "location_raw": job.get("location", ""),
                "remote_status": "Remote" if job.get("remote") else "On-site",
                "job_type": job.get("job_types", [""])[0] if job.get("job_types") else "",
                "description": desc[:1000],
                "tags_raw": "|".join(job.get("tags", [])),
                "publication_date": job.get("created_at", ""),
                "job_url": job.get("url", ""),
                "salary_text_raw": "",
                "scrape_date": scrape_date
            })

    print(f"Saved {len(jobs)} jobs to {output_file}")
    print("=== Arbeitnow DONE ===\n")

if __name__ == "__main__":
    extract_arbeitnow()