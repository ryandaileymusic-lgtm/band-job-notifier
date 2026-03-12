import os
import re
import time
import ssl
import smtplib
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
from datetime import datetime

EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# ----------------------------
# CONFIG
# ----------------------------

FRONTLINE_DISTRICTS = [
    {
        "name": "Indian Prairie School District 204",
        "search_terms": [
            '"Band Teacher" "Indian Prairie School District 204" site:applitrack.com',
            '"Music Teacher" "Indian Prairie School District 204" site:applitrack.com',
            '"General Music Teacher" "Indian Prairie School District 204" site:applitrack.com',
        ],
    },
    {
        "name": "Valley View School District 365-U",
        "search_terms": [
            '"Band Teacher" "Valley View School District 365-U" site:applitrack.com',
            '"Music Teacher" "Valley View School District 365-U" site:applitrack.com',
        ],
    },
    {
        "name": "DuPage County area",
        "search_terms": [
            '"Band Teacher" "Naperville" site:applitrack.com',
            '"Band Teacher" "Wheaton" site:applitrack.com',
            '"Band Teacher" "Glen Ellyn" site:applitrack.com',
            '"Band Teacher" "Aurora" site:applitrack.com',
            '"Band Teacher" "Geneva" site:applitrack.com',
        ],
    },
    {
        "name": "Northwest suburbs",
        "search_terms": [
            '"Band Teacher" "Lake Zurich" site:applitrack.com',
            '"Band Teacher" "Barrington" site:applitrack.com',
            '"Band Teacher" "Palatine" site:applitrack.com',
            '"Band Teacher" "Schaumburg" site:applitrack.com',
            '"Band Teacher" "Arlington Heights" site:applitrack.com',
        ],
    },
    {
        "name": "Southwest suburbs",
        "search_terms": [
            '"Band Teacher" "Joliet" site:applitrack.com',
            '"Band Teacher" "Plainfield" site:applitrack.com',
            '"Band Teacher" "Romeoville" site:applitrack.com',
            '"Band Teacher" "Bolingbrook" site:applitrack.com',
        ],
    },
]

K12_QUERIES = [
    '"Band Teacher" "Indian Prairie School District 204" site:k12jobspot.com',
    '"Music Teacher" "Indian Prairie School District 204" site:k12jobspot.com',
    '"Band Teacher" "Naperville" site:k12jobspot.com',
    '"Band Teacher" "Wheaton" site:k12jobspot.com',
    '"Band Teacher" "Glen Ellyn" site:k12jobspot.com',
    '"Band Teacher" "Aurora" site:k12jobspot.com',
    '"Band Teacher" "Geneva" site:k12jobspot.com',
    '"Band Teacher" "Lake Zurich" site:k12jobspot.com',
    '"Band Teacher" "Barrington" site:k12jobspot.com',
    '"Band Teacher" "Palatine" site:k12jobspot.com',
    '"Band Teacher" "Schaumburg" site:k12jobspot.com',
    '"Band Teacher" "Arlington Heights" site:k12jobspot.com',
    '"Band Teacher" "Joliet" site:k12jobspot.com',
    '"Band Teacher" "Plainfield" site:k12jobspot.com',
    '"Band Teacher" "Romeoville" site:k12jobspot.com',
    '"Band Teacher" "Bolingbrook" site:k12jobspot.com',
    '"General Music Teacher" Illinois site:k12jobspot.com',
    '"Instrumental Music Teacher" Illinois site:k12jobspot.com',
]

REQUIRED_TERMS = [
    "band",
    "instrumental",
    "music teacher",
    "general music",
]

EXCLUDED_TERMS = [
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

def contains_required(text):
    t = text.lower()
    return any(term in t for term in REQUIRED_TERMS)

def contains_excluded(text):
    t = text.lower()
    return any(term in t for term in EXCLUDED_TERMS)

def contains_full_time(text):
    t = text.lower()
    return any(term in t for term in FULL_TIME_TERMS)

def extract_location(text):
    patterns = [
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
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0)
    return "Location not listed"

def extract_district(text):
    patterns = [
        r"Indian Prairie School District 204",
        r"Valley View (?:Community Unit )?School District 365-?U",
        r"Naperville CUSD 203",
        r"Community Unit School District 200",
        r"Lake Zurich CUSD 95",
        r"Barrington CUSD 220",
        r"Geneva CUSD 304",
        r"Plainfield School District 202",
        r"Joliet Public Schools District 86",
        r"Joliet Township High School District 204",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(0)
    return "Unknown District"

def send_email(jobs):
    msg = EmailMessage()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg["Subject"] = f"Band / Music Job Alert — {datetime.now().strftime('%b %d')}"

    if not jobs:
        body = "No new qualifying band or instrumental music positions were found today."
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
# SEARCH
# ----------------------------

def duckduckgo_search(query):
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        title = normalize_whitespace(a.get_text(" ", strip=True))
        snippet = ""

        result_container = a.find_parent(class_="result")
        if result_container:
            snippet_el = result_container.select_one(".result__snippet")
            if snippet_el:
                snippet = normalize_whitespace(snippet_el.get_text(" ", strip=True))

        if href and title:
            results.append({
                "title": title,
                "link": href,
                "snippet": snippet,
            })

    return results

# ----------------------------
# FRONTLINE / APPLITRACK
# ----------------------------

def parse_frontline_result(result):
    combined = f"{result['title']} {result['snippet']}"
    t = combined.lower()

    if not contains_required(t):
        return None
    if contains_excluded(t):
        return None

    # Frontline snippets often omit explicit full-time wording.
    # Accept strong teaching-title matches on AppliTrack even if full-time is not in the snippet.
    strong_title = (
        "band teacher" in t
        or "music teacher" in t
        or "music - band" in t
        or "middle school teaching/music - band" in t
    )

    if not contains_full_time(t) and not strong_title:
        return None

    return {
        "title": result["title"],
        "district": extract_district(combined),
        "location": extract_location(combined),
        "link": result["link"],
    }

# ----------------------------
# K12JOBSPOT
# ----------------------------

def parse_k12_detail(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = normalize_whitespace(soup.get_text(" ", strip=True))
    t = text.lower()

    if not contains_required(t):
        return None
    if contains_excluded(t):
        return None
    if not contains_full_time(t):
        return None

    title = "Untitled Job"
    h1 = soup.select_one("h1")
    if h1:
        title = normalize_whitespace(h1.get_text(" ", strip=True))
    elif soup.title:
        title = normalize_whitespace(soup.title.get_text(" ", strip=True))

    district = extract_district(text)
    location = extract_location(text)

    return {
        "title": title,
        "district": district,
        "location": location,
        "link": url,
    }

# ----------------------------
# MAIN
# ----------------------------

def run_search():
    seen = load_seen()
    updated_seen = set(seen)
    found = []

    # Frontline / AppliTrack result parsing
    for district in FRONTLINE_DISTRICTS:
        for query in district["search_terms"]:
            try:
                results = duckduckgo_search(query)
                time.sleep(2)

                for result in results:
                    url = result["link"]
                    if "applitrack.com" not in url:
                        continue
                    if url in updated_seen:
                        continue

                    job = parse_frontline_result(result)
                    if not job:
                        continue

                    updated_seen.add(url)
                    found.append(job)

            except Exception as e:
                print(f"Frontline search error for {query}: {e}")

    # K12JobSpot detail pages
    for query in K12_QUERIES:
        try:
            results = duckduckgo_search(query)
            time.sleep(2)

            for result in results:
                url = result["link"]
                if "k12jobspot.com" not in url:
                    continue
                if url in updated_seen:
                    continue

                job = parse_k12_detail(url)
                time.sleep(1)

                if not job:
                    continue

                updated_seen.add(url)
                found.append(job)

        except Exception as e:
            print(f"K12 search error for {query}: {e}")

    save_seen(updated_seen)

    deduped = {}
    for job in found:
        deduped[job["link"]] = job

    return list(deduped.values())

if __name__ == "__main__":
    jobs = run_search()
    send_email(jobs)
    print(f"Email sent with {len(jobs)} new job(s).")
