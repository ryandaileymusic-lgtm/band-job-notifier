import os
import re
import time
import ssl
import smtplib
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
from datetime import datetime
from urllib.parse import urljoin

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# ----------------------------
# CONFIG
# ----------------------------

FRONTLINE_SOURCES = [
    {
        "name": "Indian Prairie SD 204",
        "url": "https://www.applitrack.com/ip204/onlineapp/default.aspx?all=1",
        "base": "https://www.applitrack.com/ip204/onlineapp/",
    },
    {
        "name": "Valley View SD 365U",
        "url": "https://www.applitrack.com/d365/onlineapp/default.aspx?all=1",
        "base": "https://www.applitrack.com/d365/onlineapp/",
    },
    {
        "name": "DuPage County ROE",
        "url": "https://www.applitrack.com/dupage/onlineapp/default.aspx?all=1",
        "base": "https://www.applitrack.com/dupage/onlineapp/",
    },
]

K12JOBSPOT_QUERIES = [
    '"Band Teacher" "Indian Prairie School District 204" site:k12jobspot.com',
    '"Music Teacher" "Indian Prairie School District 204" site:k12jobspot.com',
    '"Band Teacher" "Naperville" site:k12jobspot.com',
    '"Band Teacher" "Wheaton" site:k12jobspot.com',
    '"Band Teacher" "Lake Zurich" site:k12jobspot.com',
    '"Band Teacher" "Barrington" site:k12jobspot.com',
    '"Band Teacher" "Palatine" site:k12jobspot.com',
    '"Band Teacher" "Schaumburg" site:k12jobspot.com',
    '"Band Teacher" "Arlington Heights" site:k12jobspot.com',
    '"Band Teacher" "Aurora" site:k12jobspot.com',
    '"Band Teacher" "Geneva" site:k12jobspot.com',
    '"Band Teacher" "Joliet" site:k12jobspot.com',
    '"Band Teacher" "Plainfield" site:k12jobspot.com',
    '"Band Teacher" "Romeoville" site:k12jobspot.com',
    '"Band Teacher" "Bolingbrook" site:k12jobspot.com',
    '"General Music Teacher" Illinois site:k12jobspot.com',
    '"Instrumental Music Teacher" Illinois site:k12jobspot.com',
]

REQUIRED_KEYWORDS = [
    "band",
    "instrumental",
    "music teacher",
    "general music",
]

FULL_TIME_TERMS = [
    "full-time",
    "full time",
    "fte",
    "1.0",
]

EXCLUDED_KEYWORDS = [
    "choir",
    "choral",
    "vocal",
    "cps",
    "chicago public schools",
    "substitute",
    "long term substitute",
    "summer school",
]

SEEN_FILE = "seen_jobs.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}

# ----------------------------
# HELPERS
# ----------------------------

def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen_links):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for link in sorted(seen_links):
            f.write(link + "\n")

def looks_like_match(text):
    t = text.lower()

    if not any(k in t for k in REQUIRED_KEYWORDS):
        return False

    if any(k in t for k in EXCLUDED_KEYWORDS):
        return False

    if not any(k in t for k in FULL_TIME_TERMS):
        return False

    return True

def extract_location(text):
    suburb_patterns = [
        r"Lake Zurich,\s*IL(?:\s*\d{5})?",
        r"Barrington,\s*IL(?:\s*\d{5})?",
        r"Palatine,\s*IL(?:\s*\d{5})?",
        r"Schaumburg,\s*IL(?:\s*\d{5})?",
        r"Arlington Heights,\s*IL(?:\s*\d{5})?",
        r"Wheaton,\s*IL(?:\s*\d{5})?",
        r"Glen Ellyn,\s*IL(?:\s*\d{5})?",
        r"Naperville,\s*IL(?:\s*\d{5})?",
        r"Aurora,\s*IL(?:\s*\d{5})?",
        r"Geneva,\s*IL(?:\s*\d{5})?",
        r"Joliet,\s*IL(?:\s*\d{5})?",
        r"Plainfield,\s*IL(?:\s*\d{5})?",
        r"Romeoville,\s*IL(?:\s*\d{5})?",
        r"Bolingbrook,\s*IL(?:\s*\d{5})?",
    ]
    for pattern in suburb_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0)
    return "Location not listed"

def send_email(jobs):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = f"Band / Music Job Alert — {datetime.now().strftime('%b %d')}"

    if not jobs:
        body = "No new qualifying jobs were found today."
    else:
        blocks = []
        for job in jobs:
            blocks.append(
                f"{job['title']}\n"
                f"{job['district']}\n"
                f"{job['location']}\n"
                f"{job['link']}"
            )
        body = "\n\n".join(blocks)

    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# ----------------------------
# FRONTLINE / APPLITRACK
# ----------------------------

def parse_frontline_source(source):
    response = requests.get(source["url"], headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = normalize_whitespace(soup.get_text(" ", strip=True))
    jobs = []

    # Frontline pages often expose posting titles in anchor text and summary text
    for a in soup.find_all("a", href=True):
        anchor_text = normalize_whitespace(a.get_text(" ", strip=True))
        href = a["href"]

        if not anchor_text:
            continue

        combined_text = (anchor_text + " " + text).lower()

        if not any(k in combined_text for k in REQUIRED_KEYWORDS):
            continue

        if any(k in combined_text for k in EXCLUDED_KEYWORDS):
            continue

        if not any(k in combined_text for k in FULL_TIME_TERMS):
            # fallback: many frontline postings don't say full-time in anchor text;
            # keep if title is strong and page contains "position type" in relevant teaching category
            if "position type" not in text.lower():
                continue

        if "jobid" not in href.lower() and "view.asp" not in href.lower():
            continue

        job_link = urljoin(source["base"], href)
        jobs.append({
            "title": anchor_text,
            "district": source["name"],
            "location": extract_location(text),
            "link": job_link
        })

    # de-duplicate by link
    deduped = {}
    for job in jobs:
        deduped[job["link"]] = job

    return list(deduped.values())

# ----------------------------
# DUCKDUCKGO -> K12JOBSPOT DETAIL PAGES
# ----------------------------

def duckduckgo_search(query):
    url = "https://html.duckduckgo.com/html/"
    response = requests.get(url, params={"q": query}, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        title = normalize_whitespace(a.get_text(" ", strip=True))
        if href and title and "k12jobspot.com" in href:
            results.append({"title": title, "link": href})

    return results

def parse_k12jobspot_detail(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = normalize_whitespace(soup.get_text(" ", strip=True))

    if not looks_like_match(page_text):
        return None

    title = "Untitled Job"
    h1 = soup.select_one("h1")
    if h1:
        title = normalize_whitespace(h1.get_text(" ", strip=True))
    elif soup.title:
        title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    district = "Unknown District"
    district_patterns = [
        r"Indian Prairie School District 204",
        r"Valley View (?:Community Unit )?School District 365U?",
        r"Naperville CUSD 203",
        r"Community Unit School District 200",
        r"Lake Zurich CUSD 95",
        r"Barrington CUSD 220",
        r"Geneva CUSD 304",
        r"Plainfield School District 202",
        r"Joliet Public Schools District 86",
        r"Joliet Township High School District 204",
    ]
    for pattern in district_patterns:
        m = re.search(pattern, page_text, re.I)
        if m:
            district = m.group(0)
            break

    location = extract_location(page_text)

    return {
        "title": title,
        "district": district,
        "location": location,
        "link": url
    }

# ----------------------------
# MAIN
# ----------------------------

def run_search():
    seen = load_seen()
    found_jobs = []
    updated_seen = set(seen)

    # 1) Direct Frontline checks
    for source in FRONTLINE_SOURCES:
        try:
            jobs = parse_frontline_source(source)
            time.sleep(1)

            for job in jobs:
                if job["link"] in updated_seen:
                    continue
                updated_seen.add(job["link"])
                found_jobs.append(job)

        except Exception as e:
            print(f"Frontline error for {source['name']}: {e}")

    # 2) K12JobSpot detail pages via DuckDuckGo
    for query in K12JOBSPOT_QUERIES:
        try:
            results = duckduckgo_search(query)
            time.sleep(2)

            for result in results:
                url = result["link"]

                if url in updated_seen:
                    continue

                job = parse_k12jobspot_detail(url)
                time.sleep(1)

                if not job:
                    continue

                updated_seen.add(url)
                found_jobs.append(job)

        except Exception as e:
            print(f"K12JobSpot query error for {query}: {e}")

    save_seen(updated_seen)

    deduped = {}
    for job in found_jobs:
        deduped[job["link"]] = job

    return list(deduped.values())

if __name__ == "__main__":
    jobs = run_search()
    send_email(jobs)
    print(f"Email sent with {len(jobs)} new job(s).")
