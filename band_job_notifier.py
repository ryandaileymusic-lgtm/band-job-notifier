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
# SEARCH CENTERS (coords + radius)
# =========================
SEARCH_CENTERS = {
    "Lake Zurich": {"coords": (42.1956, -88.0934), "radius": 20},
    "Wheaton": {"coords": (41.8661, -88.1070), "radius": 20},
    "Joliet": {"coords": (41.5250, -88.0817), "radius": 10},
}

# =========================
# JOB FILTERS
# =========================
INCLUDE_KEYWORDS = [
    "band director",
    "instrumental music",
    "music teacher",
]

EXCLUDE_KEYWORDS = [
    "choir",
    "choral",
    "vocal",
]

# Explicit CPS exclusion only
EXCLUDE_DISTRICTS = [
    "chicago public schools",
    "cps",
]

IEJB_URL = "https://www.illinoiseducationjobbank.org/jobs"

# =========================
# DISTANCE CHECK (future-proof)
# =========================
def within_any_radius(lat, lon):
    for center in SEARCH_CENTERS.values():
        if geodesic(center["coords"], (lat, lon)).miles <= center["radius"]:
            return True
    return False

# =========================
# IEJB SCRAPER
# =========================
def fetch_iejb_jobs():
    response = requests.get(IEJB_URL, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []

    for posting in soup.select(".job-result"):
        text = posting.get_text(" ", strip=True).lower()

        # Include filters
        if not any(k in text for k in INCLUDE_KEYWORDS):
            continue

        # Exclude choir/vocal
        if any(k in text for k in EXCLUDE_KEYWORDS):
            continue

        # Exclude CPS only
        if any(d in text for d in EXCLUDE_DISTRICTS):
            continue

        # Full-time only
        if "full-time" not in text and "full time" not in text:
            continue

        link = posting.find("a")
        url = link["href"] if link else IEJB_URL

        jobs.append({
            "title": posting.get_text(" ", strip=True),
            "url": url
        })

    return jobs

# =========================
# EMAIL RESULTS
# =========================
def send_email(jobs):
    if not jobs:
        body = "No new full-time band or general music teaching jobs matched your criteria today."
    else:
        body = "New matching teaching positions found:\n\n"
        for job in jobs:
            body += f"{job['title']}\n{job['url']}\n\n"

    msg = EmailMessage()
    msg["Subject"] = "Chicago Suburbs Band & Music Teaching Jobs"
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
