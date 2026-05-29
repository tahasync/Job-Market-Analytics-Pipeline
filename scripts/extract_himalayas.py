import requests
import csv
import datetime
import os
import time

def extract_himalayas():
    print("=== Extracting from Himalayas ===")

    scrape_date = datetime.date.today().isoformat()
    os.makedirs("data/raw", exist_ok=True)

    all_jobs = []
    keywords = ["data", "machine learning", "data engineer"]

    for keyword in keywords:
        for page in range(1, 4):
            url = f"https://himalayas.app/jobs/api/search?q={keyword}&sort=recent&page={page}"
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                jobs = data.get("jobs", [])
                if not jobs:
                    print(f"  No jobs on page {page} for '{keyword}', stopping")
                    break
                all_jobs.extend(jobs)
                print(f"  Keyword '{keyword}' page {page}: {len(jobs)} jobs")
                time.sleep(1)
            except Exception as e:
                print(f"  ERROR page {page} keyword '{keyword}': {e}")
                break

    print(f"Total jobs before dedup: {len(all_jobs)}")

    # Fix: deduplicate using title+company instead of id (id field may be missing)
    seen = set()
    unique_jobs = []
    for job in all_jobs:
        # Try multiple possible id fields
        jid = (
            str(job.get("id", "")) or
            str(job.get("slug", "")) or
            str(job.get("title", "")) + str(job.get("companyName", ""))
        )
        if jid not in seen:
            seen.add(jid)
            unique_jobs.append(job)

    print(f"Total unique jobs after dedup: {len(unique_jobs)}")

    output_file = "data/raw/raw_himalayas_jobs.csv"

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
            # Print first job keys so we can debug
            desc = job.get("description", "")
            if isinstance(desc, list):
                desc = " ".join(desc)
            desc = str(desc)
            desc = " ".join(desc.split())

            sal_min = job.get("minSalary", "") or job.get("salary_min", "") or ""
            sal_max = job.get("maxSalary", "") or job.get("salary_max", "") or ""

            salary_text = ""
            if sal_min and sal_max:
                salary_text = f"${sal_min} - ${sal_max}"

            location = job.get("locationRestrictions", []) or job.get("location", "")
            if isinstance(location, list):
                location = ", ".join(location)

            tags = job.get("categories", []) or job.get("tags", [])
            if isinstance(tags, list):
                tags = "|".join([str(t) for t in tags])
            else:
                tags = str(tags)

            writer.writerow({
                "source": "Himalayas",
                "job_id": str(job.get("id", "") or job.get("slug", "")),
                "title": job.get("title", ""),
                "company_name": job.get("companyName", "") or job.get("company_name", ""),
                "location_raw": location,
                "remote_status": "Remote",
                "job_type": job.get("employmentType", "") or job.get("job_type", ""),
                "description": desc[:1000],
                "tags_raw": tags,
                "publication_date": job.get("postedAt", "") or job.get("created_at", ""),
                "job_url": job.get("applicationLink", "") or job.get("url", ""),
                "salary_min_raw": sal_min,
                "salary_max_raw": sal_max,
                "salary_text_raw": salary_text,
                "scrape_date": scrape_date
            })

    print(f"Saved {len(unique_jobs)} jobs to {output_file}")
    print("=== Himalayas DONE ===\n")

    # Debug: print keys of first job to verify structure
    if all_jobs:
        print(f"DEBUG - First job keys: {list(all_jobs[0].keys())}")
        print(f"DEBUG - First job title: {all_jobs[0].get('title','NO TITLE')}")

if __name__ == "__main__":
    extract_himalayas()