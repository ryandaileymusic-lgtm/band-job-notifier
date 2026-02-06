import os
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
import smtplib
from geopy.distance import geodesic

# =========================
# EMAIL CONFIG
# =========================
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_TO = os.environ["EMAIL_TO"]

# =========================
# LOCATION CENTERS (lat, lon)
# =========================
SEARCH_CENTERS = {
    "Lake Zurich": (42.1956, -88.0934),
    "Wheaton": (41.8661, -88.1070),
    "Joliet": (41.5250, -88.0817),
}

SEARCH_RADIUS_MILES = 20

# =========================
# JOB FILTERS
# =========================
INCLUDE_KEYWORDS = [
    "band director",
    "band teacher",
    "music teacher",
    "instrumental music",
]

EXCLUDE_KEYWORDS = [
    "choir",
    "choral",
    "vocal",
]

EXCLUDE_LOCATIONS = [
    "chicago, il",
]

# =========================
# IEJB SEARCH
# =========================
IEJB_URL = "https://www.illinoiseducationjobbank.org/jobs"

def within_radius(job_lat, job_lon):
    for center in SEARCH_CENTERS.values():
        if geodesic(center, (job_lat, job_lon)).miles <= SEARCH_RADIUS_MILES:
            return True
    return False

def fetch_iejb_jobs():
    response = requests.get(IEJB_URL, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    for posting in soup.select(".job-result"):
        title = posting.get_text(" ", strip=True).lower()

        if not any(k in title for k in INCLUDE_KEYWORDS):
            continue
        if any(k in title for k in EXCLUDE_KEYWORDS):
            continue
        if any(loc in title for loc in EXCLUDE_LOCATIONS):
            continue
        if "full-time" not in title and "full time" not in title:
            continue

        link = posting.find("a")
        url = link["href"] if link else IEJB_URL

        jobs.append({
            "title": title.title(),
            "url": url
        })

    return jobs

# =========================
# EMAIL RESULTS
# =========================
def send_email(jobs):
    if not jobs:
        body = "No new matching band or music teacher jobs were found today."
    else:
        body = "New matching jobs found:\n\n"
        for job in jobs:
            body += f"{job['title']}\n{job['url']}\n\n"

    msg = EmailMessage()
    msg["Subject"] = "Chicago Suburbs Band & Music Teacher Jobs"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# =========================
# MAIN
# =========================
jobs = fetch_iejb_jobs()
send_email(jobs)

print(f"Email sent with {len(jobs)} job(s).")

