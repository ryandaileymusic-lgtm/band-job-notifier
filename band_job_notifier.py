import os
import smtplib
import ssl
import requests
from email.message import EmailMessage
from datetime import datetime

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# ======================
# SEARCH CONFIG
# ======================

CENTERS = {
    "Lake Zurich, IL": 20,
    "Wheaton, IL": 20,
    "Joliet, IL": 10
}

KEYWORDS_REQUIRED = [
    "band",
    "instrumental",
    "music teacher"
]

KEYWORDS_EXCLUDED = [
    "choir",
    "choral",
    "cps",
    "chicago public schools"
]

FULL_TIME_TERMS = [
    "full-time",
    "full time",
    "fte"
]

# ======================
# INDEED SEARCH
# ======================

def search_indeed(center, radius):
    jobs = []
    query = "band OR instrumental music teacher"

    url = "https://www.indeed.com/jobs"
    params = {
        "q": query,
        "l": center,
        "radius": radius,
        "fromage": 1,
        "sort": "date"
    }

    response = requests.get(url, params=params, timeout=15)
    text = response.text.lower()

    for line in text.splitlines():
        if "jobtitle" in line or "href" in line:
            if any(k in line for k in KEYWORDS_REQUIRED) \
               and not any(x in line for x in KEYWORDS_EXCLUDED):
                jobs.append(f"Indeed result near {center}")

    return jobs

# ======================
# IEJB SEARCH
# ======================

def search_iejb():
    jobs = []
    url = "https://www.illinoiseducationjobbank.org/search.aspx?cat=music"

    response = requests.get(url, timeout=15)
    text = response.text.lower()

    for line in text.splitlines():
        if "band" in line and "full" in line:
            if not any(x in line for x in KEYWORDS_EXCLUDED):
                jobs.append("IEJB listing")

    return jobs

# ======================
# MAIN
# ======================

def run_search():
    results = []

    results.extend(search_iejb())

    for center, radius in CENTERS.items():
        results.extend(search_indeed(center, radius))

    return list(set(results))

def send_email(jobs):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = f"Band Job Alert — {datetime.now().strftime('%b %d')}"

    if not jobs:
        body = "No qualifying band or instrumental music positions were found today."
    else:
        body = "New qualifying positions:\n\n" + "\n".join(jobs)

    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

if __name__ == "__main__":
    jobs = run_search()
    send_email(jobs)

