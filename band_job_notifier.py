import os
import re
import time
import smtplib
import ssl
import requests
from email.message import EmailMessage
from datetime import datetime
from bs4 import BeautifulSoup

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# ----------------------------
# CONFIG
# ----------------------------

SEARCH_QUERIES = [
    # Northwest suburbs
    '"Band Teacher" "Lake Zurich"',
    '"Music Teacher" "Lake Zurich"',
    '"Band Teacher" "Barrington"',
    '"Music Teacher" "Barrington"',
    '"Band Teacher" "Palatine"',
    '"Music Teacher" "Palatine"',
    '"Band Teacher" "Schaumburg"',
    '"Music Teacher" "Schaumburg"',
    '"Band Teacher" "Arlington Heights"',
    '"Music Teacher" "Arlington Heights"',

    # West suburbs
    '"Band Teacher" "Wheaton"',
    '"Music Teacher" "Wheaton"',
    '"Band Teacher" "Glen Ellyn"',
    '"Music Teacher" "Glen Ellyn"',
    '"Band Teacher" "Naperville"',
    '"Music Teacher" "Naperville"',
    '"Band Teacher" "Aurora"',
    '"Music Teacher" "Aurora"',
    '"Band Teacher" "Geneva"',
    '"Music Teacher" "Geneva"',

    # Southwest suburbs
    '"Band Teacher" "Joliet"',
    '"Music Teacher" "Joliet"',
    '"Band Teacher" "Plainfield"',
    '"Music Teacher" "Plainfield"',
    '"Band Teacher" "Romeoville"',
    '"Music Teacher" "Romeoville"',
    '"Band Teacher" "Bolingbrook"',
    '"Music Teacher" "Bolingbrook"',

    # High-priority districts
    '"Band Teacher" "Indian Prairie School District 204"',
    '"Music Teacher" "Indian Prairie School District 204"',
    '"Band Teacher" "Valley View School District 365-U"',
    '"Music Teacher" "Valley View School District 365-U"',

    # Broad catch-all searches
    '"Band Teacher" Illinois',
    '"Instrumental Music Teacher" Illinois',
    '"General Music Teacher" Illinois',
]

ALLOWED_DOMAINS = [
    "k12jobspot.com",
    "applitrack.com",
    "generalasp.com",
    "indeed.com",
]

REQUIRED_KEYWORDS = [
    "band",
    "instrumental",
    "music teacher",
    "general music",
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

FULL_TIME_TERMS = [
    "full-time",
    "full time",
    "fte",
    "1.0",
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

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen_links):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for link in sorted(seen_links):
            f.write(link + "\n")

def normalize_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()

def domain_allowed(url):
    return any(domain in url for domain in ALLOWED_DOMAINS)

def text_matches(text):
    t = text.lower()

    if not any(k in t for k in REQUIRED_KEYWORDS):
        return False

    if any(k in t for k in EXCLUDED_KEYWORDS):
        return False

    if not any(k in t for k in FULL_TIME_TERMS):
        return False

    return True

def clean_link(url):
    if url.startswith("//"):
        return "https:" + url
    return url

# ----------------------------
# EMAIL
# ----------------------------

def send_email(jobs):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = f"Band / Music Job Alert — {datetime.now().strftime('%b %d')}"

    if not jobs:
        body = "No new qualifying jobs were found today."
    else:
        parts = []
        for job in jobs:
            parts.append(
                f"{job['title']}\n"
                f"{job['district']}\n"
                f"{job['location']}\n"
                f"{job['link']}"
            )
        body = "\n\n".join(parts)

    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# ----------------------------
# SEARCH ENGINE SCRAPE
# ----------------------------

def duckduckgo_search(query):
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}

    response = requests.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        title = normalize_whitespace(a.get_text(" ", strip=True))

        if href and title:
            results.append({
                "title": title,
                "link": clean_link(href)
            })

    return results

# ----------------------------
# DETAIL PAGE PARSERS
# ----------------------------

def parse_k12jobspot(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = normalize_whitespace(soup.get_text(" ", strip=True))

    if not text_matches(text):
        return None

    # Title
    title = "Untitled Job"
    title_el = soup.select_one("h1")
    if title_el:
        title = normalize_whitespace(title_el.get_text(" ", strip=True))

    # District
    district = "Unknown District"

    # Look for common district patterns in page text
    district_patterns = [
        r"Indian Prairie School District 204",
        r"Valley View School District 365-U",
        r"Naperville CUSD 203",
        r"Community Unit School District 200",
        r"Lake Zurich CUSD 95",
        r"Barrington CUSD 220",
        r"Palatine CCSD",
        r"Schaumburg CCSD",
        r"Arlington Heights School District",
        r"Geneva CUSD 304",
        r"Plainfield School District 202",
        r"Joliet Public Schools District 86",
        r"Joliet Township High School District 204",
        r"Bolingbrook",
        r"Romeoville",
    ]

    for pattern in district_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            district = match.group(0)
            break

    # Fall back to h2 tags if district still unknown
    if district == "Unknown District":
        for h2 in soup.find_all("h2"):
            htxt = normalize_whitespace(h2.get_text(" ", strip=True))
            if htxt and htxt.lower() != "description":
                district = htxt
                break

    # Location
    location = "Location not listed"

    location_patterns = [
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

    for pattern in location_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            location = match.group(0)
            break

    return {
        "title": title,
        "district": district,
        "location": location,
        "link": url
    }

def parse_generic(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = normalize_whitespace(soup.get_text(" ", strip=True))

    if not text_matches(text):
        return None

    title = "Untitled Job"
    if soup.title:
        title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    district = "Unknown District"
    district_patterns = [
        r"Indian Prairie School District 204",
        r"Valley View School District 365-U",
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
        match = re.search(pattern, text, re.I)
        if match:
            district = match.group(0)
            break

    location = "Location not listed"
    location_patterns = [
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
    for pattern in location_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            location = match.group(0)
            break

    return {
        "title": title,
        "district": district,
        "location": location,
        "link": url
    }

def parse_job_page(url):
    try:
        if "k12jobspot.com/Job/" in url:
            return parse_k12jobspot(url)
        return parse_generic(url)
    except Exception:
        return None

# ----------------------------
# MAIN SEARCH LOGIC
# ----------------------------

def run_search():
    seen = load_seen()
    found_jobs = []
    updated_seen = set(seen)

    for query in SEARCH_QUERIES:
        try:
            results = duckduckgo_search(query)
            time.sleep(2)

            for result in results:
                url = result["link"]

                if not domain_allowed(url):
                    continue

                if url in updated_seen:
                    continue

                job = parse_job_page(url)
                time.sleep(1)

                if not job:
                    continue

                updated_seen.add(url)
                found_jobs.append(job)

        except Exception as e:
            print(f"Error while processing query '{query}': {e}")

    save_seen(updated_seen)

    # Remove duplicates by link
    deduped = {}
    for job in found_jobs:
        deduped[job["link"]] = job

    return list(deduped.values())

# ----------------------------
# RUN
# ----------------------------

if __name__ == "__main__":
    jobs = run_search()
    send_email(jobs)
    print(f"Email sent with {len(jobs)} new job(s).")
