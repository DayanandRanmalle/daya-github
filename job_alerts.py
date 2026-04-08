"""
job_alerts.py  -  AI-Powered Real-Time Job Alert Bot + Auto-Apply Helper
==============================================================
Candidate : Dayanand Balaji Ranmalle
Sources   : LinkedIn + Naukri.com
Alerts    : Telegram Bot (AI-powered conversational + scheduled)
NEW       : Auto-open job links in browser for quick apply

Bot can:
  - Reply to ANY question instantly using Gemini AI
  - Search jobs on demand
  - Give career advice
  - Answer resume questions
  - Auto-alert every 5 mins for new jobs
  - AUTO-OPEN job links in browser (LinkedIn Easy Apply + Naukri Quick Apply)

Install:
  pip install requests beautifulsoup4 schedule selenium webdriver-manager

Run:
  python job_alerts.py
==============================================================
"""

import json
import logging
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime
from urllib.parse import quote

import requests
import schedule
from bs4 import BeautifulSoup

# ── Fix Windows CMD Unicode encoding ─────────────────────────
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Config ────────────────────────────────────────────────────
from config import (
    CANDIDATE_NAME, MIN_EXPERIENCE_YEARS,
    JOB_KEYWORDS, JOB_LOCATIONS, CANDIDATE_SKILLS,
    POLL_INTERVAL_MINUTES, SEEN_JOBS_FILE, MAX_RESULTS_PER_SOURCE,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    GEMINI_API_KEY,
)

# ── Auto-Apply Target Roles (case-insensitive match) ─────────
AUTO_APPLY_ROLES = [
    "application support",
    "system support",
    "technical support",
    "devops engineer",
    "devops",
    "sre",
    "site reliability",
    "production support",
    "l2 support",
    "l2 application",
]

# ── Logging ───────────────────────────────────────────────────
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            msg_safe = msg.encode("ascii", errors="replace").decode("ascii")
            self.stream.write(msg_safe + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        SafeStreamHandler(sys.stdout),
        logging.FileHandler("job_alerts.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Browser headers ───────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TG_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN

CANDIDATE_PROFILE = """
Name        : Dayanand Balaji Ranmalle
Current Role: Associate Consultant - Application Support (L2)
Company     : Jio Platforms Ltd (Reliance Retail), Navi Mumbai
Experience  : 4+ years
Skills      : SQL, Oracle DB, Linux/Unix, Azure DevOps, Kubernetes (kubectl),
              Docker, Grafana, WCS/WES, SIT/UAT Testing, Application Support
Education   : BCA - Dr. Babasaheb Ambedkar Marathwada University (2022)
Locations   : Navi Mumbai, Mumbai, Pune, Hyderabad
Job Targets : Application Support Engineer, Production Support Engineer,
              L2 Support, DevOps Engineer, Associate Consultant,
              Technical Support Engineer
"""

_conversation_history = {}


# ==============================================================
#  1. SEEN-JOBS TRACKER
# ==============================================================

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()

def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)

def make_job_id(job):
    return job["title"].lower().strip() + "|" + job["company"].lower().strip() + "|" + job["location"].lower().strip()


# ==============================================================
#  2. AUTO-APPLY HELPER (Browser-Based)
# ==============================================================

def is_auto_apply_role(title):
    """Check if job title matches auto-apply target roles."""
    title_lower = title.lower()
    return any(role in title_lower for role in AUTO_APPLY_ROLES)


def auto_open_linkedin(job):
    """
    Open LinkedIn job in browser.
    For Easy Apply jobs: opens the job page directly — user just clicks Apply.
    For external apply: opens the job page.
    """
    try:
        link = job["link"]
        log.info("AUTO-OPEN LinkedIn: " + job["title"] + " @ " + job["company"])
        webbrowser.open(link)
        time.sleep(2)  # Small delay between openings to avoid overwhelming browser
        return True
    except Exception as e:
        log.error("Auto-open LinkedIn failed: " + str(e))
        return False


def auto_open_naukri(job):
    """
    Open Naukri job in browser.
    Naukri Quick Apply: opens the job page — user just clicks Apply.
    """
    try:
        link = job["link"]
        log.info("AUTO-OPEN Naukri: " + job["title"] + " @ " + job["company"])
        webbrowser.open(link)
        time.sleep(2)
        return True
    except Exception as e:
        log.error("Auto-open Naukri failed: " + str(e))
        return False


def process_auto_apply(jobs):
    """
    For each matching job, auto-open in browser.
    Returns list of jobs that were auto-opened.
    """
    auto_opened = []
    for job in jobs:
        if is_auto_apply_role(job["title"]):
            success = False
            if job["source"] == "LinkedIn":
                success = auto_open_linkedin(job)
            elif job["source"] == "Naukri":
                success = auto_open_naukri(job)

            if success:
                job["auto_applied"] = True
                auto_opened.append(job)
                log.info("Auto-opened: " + job["title"] + " [" + job["source"] + "]")
        else:
            job["auto_applied"] = False

    return auto_opened


# ==============================================================
#  3. SCRAPERS
# ==============================================================

def scrape_linkedin(keyword, location, limit):
    jobs = []
    url = (
        "https://www.linkedin.com/jobs/search/"
        "?keywords=" + quote(keyword) +
        "&location=" + quote(location) +
        "&f_TPR=r3600&f_E=4&sortBy=DD"
    )
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25 + attempt * 10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.base-card")[:limit]
            for card in cards:
                title_tag   = card.select_one("h3.base-search-card__title")
                company_tag = card.select_one("h4.base-search-card__subtitle")
                loc_tag     = card.select_one("span.job-search-card__location")
                link_tag    = card.select_one("a.base-card__full-link")
                time_tag    = card.select_one("time")
                jobs.append({
                    "title"     : title_tag.get_text(strip=True)   if title_tag   else "N/A",
                    "company"   : company_tag.get_text(strip=True) if company_tag else "N/A",
                    "location"  : loc_tag.get_text(strip=True)     if loc_tag     else location,
                    "posted"    : time_tag.get_text(strip=True)    if time_tag    else "Just now",
                    "experience": str(MIN_EXPERIENCE_YEARS) + "+ yrs",
                    "link"      : link_tag["href"].split("?")[0]   if link_tag    else url,
                    "source"    : "LinkedIn",
                    "auto_applied": False,
                })
            break
        except requests.exceptions.Timeout:
            log.warning("LinkedIn timeout attempt " + str(attempt+1) + "/3")
            time.sleep(3)
        except Exception as e:
            log.warning("LinkedIn error [" + keyword + " | " + location + "]: " + str(e))
            break
    return jobs


def scrape_naukri(keyword, location, limit):
    jobs = []
    kw_slug  = keyword.lower().replace(" ", "-")
    loc_slug = location.lower().replace(" ", "-")
    url = (
        "https://www.naukri.com/" + quote(kw_slug) +
        "-jobs-in-" + quote(loc_slug) +
        "?experienceRange=4%2C20&jobAge=0&sortBy=displayDate"
    )
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25 + attempt * 10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = (
                soup.select("article.jobTuple") or
                soup.select("div.cust-job-tuple") or
                soup.select("div.job-container")
            )
            cards = cards[:limit]
            for card in cards:
                title_tag   = card.select_one("a.title") or card.select_one("a.job-title")
                company_tag = card.select_one("a.subTitle") or card.select_one("a.comp-name")
                loc_tag     = card.select_one("li.location span") or card.select_one("span.locWdth")
                exp_tag     = card.select_one("li.experience span") or card.select_one("span.expwdth")
                posted_tag  = card.select_one("span.job-post-day") or card.select_one("span.freshness")
                link = title_tag["href"] if title_tag and title_tag.has_attr("href") else url
                jobs.append({
                    "title"     : title_tag.get_text(strip=True)   if title_tag   else "N/A",
                    "company"   : company_tag.get_text(strip=True) if company_tag else "N/A",
                    "location"  : loc_tag.get_text(strip=True)     if loc_tag     else location,
                    "posted"    : posted_tag.get_text(strip=True)  if posted_tag  else "Today",
                    "experience": exp_tag.get_text(strip=True)     if exp_tag     else str(MIN_EXPERIENCE_YEARS) + "+ yrs",
                    "link"      : link,
                    "source"    : "Naukri",
                    "auto_applied": False,
                })
            break
        except requests.exceptions.Timeout:
            log.warning("Naukri timeout attempt " + str(attempt+1) + "/3")
            time.sleep(3)
        except Exception as e:
            log.warning("Naukri error [" + keyword + " | " + location + "]: " + str(e))
            break
    return jobs


def fetch_new_jobs(seen):
    new_jobs = []
    for kw in JOB_KEYWORDS:
        for loc in JOB_LOCATIONS:
            for job in scrape_linkedin(kw, loc, MAX_RESULTS_PER_SOURCE):
                jid = make_job_id(job)
                if jid not in seen:
                    seen.add(jid)
                    new_jobs.append(job)
            time.sleep(1)
            for job in scrape_naukri(kw, loc, MAX_RESULTS_PER_SOURCE):
                jid = make_job_id(job)
                if jid not in seen:
                    seen.add(jid)
                    new_jobs.append(job)
            time.sleep(1)
    return new_jobs


def fetch_all_jobs_now():
    all_jobs = []
    seen_temp = set()
    for kw in JOB_KEYWORDS:
        for loc in JOB_LOCATIONS:
            for job in scrape_linkedin(kw, loc, MAX_RESULTS_PER_SOURCE):
                jid = make_job_id(job)
                if jid not in seen_temp:
                    seen_temp.add(jid)
                    all_jobs.append(job)
            time.sleep(1)
            for job in scrape_naukri(kw, loc, MAX_RESULTS_PER_SOURCE):
                jid = make_job_id(job)
                if jid not in seen_temp:
                    seen_temp.add(jid)
                    all_jobs.append(job)
            time.sleep(1)
    return all_jobs


# ==============================================================
#  4. AI-POWERED REPLY (Gemini API)
# ==============================================================

def ask_gemini(user_message, chat_id):
    global _conversation_history

    if chat_id not in _conversation_history:
        _conversation_history[chat_id] = []

    _conversation_history[chat_id].append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    if len(_conversation_history[chat_id]) > 20:
        _conversation_history[chat_id] = _conversation_history[chat_id][-20:]

    system_prompt = (
        "You are DayanandJobBot, a personal AI job assistant for Dayanand Balaji Ranmalle. "
        "You are running inside his Telegram bot. Be friendly, helpful, and conversational. "
        "Keep replies concise and clear — this is a chat interface. "
        "Here is Dayanand's profile:\n" + CANDIDATE_PROFILE + "\n\n"
        "You can help with:\n"
        "- Job search advice and career guidance\n"
        "- Resume tips and interview preparation\n"
        "- Salary negotiation advice\n"
        "- Explaining job descriptions\n"
        "- Skill improvement suggestions\n"
        "- Any general questions Dayanand asks\n\n"
        "For job searches, tell him to type /search and the bot will search LinkedIn and Naukri.\n"
        "Today's date: " + datetime.now().strftime("%d %B %Y") + "\n"
        "Always reply in a warm, supportive tone like a career mentor."
    )

    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": _conversation_history[chat_id],
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            reply = data["candidates"][0]["content"]["parts"][0]["text"]
            _conversation_history[chat_id].append({
                "role": "model",
                "parts": [{"text": reply}]
            })
            return reply
        else:
            log.error("Gemini API error: " + str(resp.status_code) + " - " + resp.text[:200])
            return None
    except Exception as e:
        log.error("Gemini API exception: " + str(e))
        return None


# ==============================================================
#  5. FORMATTERS
# ==============================================================

def format_jobs_message(jobs, title="JOB SEARCH RESULTS"):
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    lines = [
        "=" * 32,
        title + " - " + now,
        "Candidate : " + CANDIDATE_NAME,
        "Locations : " + " | ".join(JOB_LOCATIONS),
        "Experience: " + str(MIN_EXPERIENCE_YEARS) + "+ yrs",
        str(len(jobs)) + " job(s) found",
        "=" * 32,
    ]
    for i, j in enumerate(jobs, 1):
        auto_tag = " [AUTO-OPENED]" if j.get("auto_applied") else ""
        lines.append(
            "\n" + str(i) + ". " + j["title"] + auto_tag +
            "\n   Company : " + j["company"] +
            "\n   Location: " + j["location"] +
            "\n   Exp     : " + j["experience"] +
            "\n   Posted  : " + j["posted"] +
            "\n   Source  : " + j["source"] +
            "\n   Link    : " + j["link"]
        )
    lines.append("\nDayanand Job Bot")
    return "\n".join(lines)


def format_auto_apply_summary(auto_opened):
    """Format a summary message for auto-opened jobs."""
    if not auto_opened:
        return None
    lines = [
        "=" * 32,
        "AUTO-OPENED IN BROWSER",
        str(len(auto_opened)) + " job(s) opened — just click Apply!",
        "=" * 32,
    ]
    for i, j in enumerate(auto_opened, 1):
        lines.append(
            "\n" + str(i) + ". " + j["title"] +
            "\n   " + j["company"] + " | " + j["source"] +
            "\n   " + j["link"]
        )
    lines.append("\nGo apply now! All tabs are open in your browser.")
    return "\n".join(lines)


# ==============================================================
#  6. TELEGRAM SENDER & INTERACTIVE BOT
# ==============================================================

def send_telegram(message, chat_id=None):
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID
    max_len = 4000
    if len(message) <= max_len:
        try:
            requests.post(
                TG_API + "/sendMessage",
                json={"chat_id": chat_id, "text": message},
                timeout=15
            )
        except Exception as e:
            log.error("[ERROR] Telegram: " + str(e))
    else:
        for i in range(0, len(message), max_len):
            chunk = message[i:i + max_len]
            try:
                requests.post(
                    TG_API + "/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=15
                )
                time.sleep(0.5)
            except Exception as e:
                log.error("[ERROR] Telegram chunk: " + str(e))


def send_typing(chat_id):
    try:
        requests.post(
            TG_API + "/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5
        )
    except Exception:
        pass


def handle_message(message_text, chat_id):
    text = message_text.strip()
    text_lower = text.lower()

    send_typing(chat_id)

    # /start
    if text_lower in ["/start", "hello", "hi", "hey"]:
        reply = (
            "Hello Dayanand! I am your AI-powered Job Assistant Bot.\n\n"
            "I can help you with:\n"
            "- Job search (type /search)\n"
            "- Auto-open jobs for quick apply (/autoapply)\n"
            "- Career advice\n"
            "- Resume tips\n"
            "- Interview preparation\n"
            "- Salary guidance\n"
            "- Any question you have!\n\n"
            "Just talk to me like a friend. I am here 24/7!"
        )
        send_telegram(reply, chat_id)

    # Job search commands
    elif any(kw in text_lower for kw in ["/search", "search job", "find job", "get job", "show job", "latest job", "new job", "any new job", "any post", "recent post", "check job"]):
        send_telegram("Searching jobs for you right now... Please wait 1-2 minutes.", chat_id)
        log.info("On-demand job search triggered: " + text)
        jobs = fetch_all_jobs_now()
        if jobs:
            batch_size = 10
            for i in range(0, len(jobs), batch_size):
                batch = jobs[i:i + batch_size]
                send_telegram(format_jobs_message(batch, "JOB SEARCH RESULTS"), chat_id)
                time.sleep(1)
            send_telegram("That's all the current listings! I will auto-alert you when new ones are posted.", chat_id)
        else:
            send_telegram("No new jobs found right now. I will alert you the moment something is posted!", chat_id)

    # /autoapply — manually trigger auto-open for matching roles
    elif any(kw in text_lower for kw in ["/autoapply", "auto apply", "open jobs", "apply jobs"]):
        send_telegram("Searching and auto-opening matching jobs in your browser... Stand by!", chat_id)
        log.info("Manual auto-apply triggered")
        jobs = fetch_all_jobs_now()
        if jobs:
            auto_opened = process_auto_apply(jobs)
            if auto_opened:
                summary = format_auto_apply_summary(auto_opened)
                send_telegram(summary, chat_id)
                send_telegram(
                    str(len(auto_opened)) + " job tab(s) opened in your browser!\n"
                    "Just go to each tab and click Apply / Easy Apply.\n"
                    "No manual search needed!",
                    chat_id
                )
            else:
                send_telegram(
                    "Found " + str(len(jobs)) + " jobs but none matched your auto-apply roles.\n"
                    "Auto-apply roles: Application Support, DevOps, SRE, Technical Support, System Support.",
                    chat_id
                )
        else:
            send_telegram("No jobs found to auto-apply right now.", chat_id)

    # /status
    elif text_lower in ["/status", "status", "bot status"]:
        reply = (
            "Bot Status\n"
            "==========\n"
            "Status    : Running 24/7\n"
            "Candidate : " + CANDIDATE_NAME + "\n"
            "Roles     : " + str(len(JOB_KEYWORDS)) + " job titles\n"
            "Locations : " + ", ".join(JOB_LOCATIONS) + "\n"
            "Experience: " + str(MIN_EXPERIENCE_YEARS) + "+ yrs\n"
            "Auto poll : every " + str(POLL_INTERVAL_MINUTES) + " mins\n"
            "Tracked   : " + str(len(_seen_jobs)) + " jobs seen so far\n"
            "Auto-open : Enabled (Application Support, DevOps, SRE, etc.)\n"
            "Time      : " + datetime.now().strftime("%d %b %Y %I:%M %p")
        )
        send_telegram(reply, chat_id)

    # /help
    elif text_lower in ["/help", "help"]:
        reply = (
            "Dayanand Job Bot - Help\n"
            "=======================\n\n"
            "Commands:\n"
            "/search      - Search all jobs right now\n"
            "/autoapply   - Auto-open matching jobs in browser\n"
            "/status      - Bot status\n"
            "/help        - This help menu\n\n"
            "Auto-Apply Roles (auto-opens in browser):\n"
            "- Application Support\n"
            "- System Support\n"
            "- Technical Support\n"
            "- DevOps Engineer\n"
            "- SRE / Site Reliability\n"
            "- Production Support / L2 Support\n\n"
            "Or just talk to me freely!\n"
            "Examples:\n"
            "- How should I prepare for interviews?\n"
            "- What salary should I ask for?\n"
            "- How to improve my resume?\n"
            "- What skills should I learn next?"
        )
        send_telegram(reply, chat_id)

    # Everything else — send to Gemini AI
    else:
        log.info("Sending to Gemini AI: " + text)
        reply = ask_gemini(text, chat_id)
        if reply:
            send_telegram(reply, chat_id)
        else:
            send_telegram(
                "Sorry, I could not process that right now. Try:\n"
                "/search     - to find jobs\n"
                "/autoapply  - to auto-open matching jobs\n"
                "/help       - to see all commands",
                chat_id
            )


# ==============================================================
#  7. TELEGRAM POLLING
# ==============================================================

_update_offset = 0

def check_telegram_messages():
    global _update_offset
    try:
        resp = requests.get(
            TG_API + "/getUpdates",
            params={"offset": _update_offset, "timeout": 5},
            timeout=15
        )
        if resp.status_code != 200:
            return
        for update in resp.json().get("result", []):
            _update_offset = update["update_id"] + 1
            message = update.get("message", {})
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))
            if text and chat_id:
                log.info("Message from Telegram [" + chat_id + "]: " + text)
                threading.Thread(
                    target=handle_message,
                    args=(text, chat_id),
                    daemon=True
                ).start()
    except Exception as e:
        log.warning("Telegram polling error: " + str(e))


# ==============================================================
#  8. SCHEDULED JOB POLLING WITH AUTO-OPEN
# ==============================================================

_seen_jobs = set()

def poll_and_alert():
    global _seen_jobs
    log.info("Auto-poll started - " + datetime.now().strftime("%d %b %Y %I:%M:%S %p"))
    new_jobs = fetch_new_jobs(_seen_jobs)

    if new_jobs:
        log.info(str(len(new_jobs)) + " new job(s) found!")

        # Send job alert messages
        batch_size = 10
        for i in range(0, len(new_jobs), batch_size):
            batch = new_jobs[i:i + batch_size]
            send_telegram(format_jobs_message(batch, "NEW JOB ALERT"))
            time.sleep(2)

        # Auto-open matching jobs in browser
        auto_opened = process_auto_apply(new_jobs)
        if auto_opened:
            log.info("Auto-opened " + str(len(auto_opened)) + " job(s) in browser.")
            summary = format_auto_apply_summary(auto_opened)
            send_telegram(summary)
            send_telegram(
                str(len(auto_opened)) + " matching job(s) auto-opened in your browser!\n"
                "Go click Apply on each tab. No manual search needed!"
            )

        save_seen_jobs(_seen_jobs)
    else:
        log.info("No new jobs this cycle.")

    log.info("Poll complete. Total tracked: " + str(len(_seen_jobs)))


# ==============================================================
#  9. STARTUP
# ==============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Dayanand AI Job Bot - LIVE MODE")
    print("  Candidate : " + CANDIDATE_NAME)
    print("  Roles     : " + str(len(JOB_KEYWORDS)) + " job titles")
    print("  Locations : " + ", ".join(JOB_LOCATIONS))
    print("  Exp filter: " + str(MIN_EXPERIENCE_YEARS) + "+ years")
    print("  Auto poll : every " + str(POLL_INTERVAL_MINUTES) + " minutes")
    print("  AI Chat   : Gemini-powered instant replies (FREE)")
    print("  Telegram  : Chat ID " + str(TELEGRAM_CHAT_ID))
    print("  Auto-open : Enabled for Application Support, DevOps, SRE, etc.")
    print("=" * 60)

    _seen_jobs = load_seen_jobs()
    log.info("Loaded " + str(len(_seen_jobs)) + " previously seen jobs.")

    send_telegram(
        "Dayanand AI Job Bot is now ONLINE!\n\n"
        "I am your 24/7 AI-powered job assistant.\n\n"
        "NEW: Auto-open feature enabled!\n"
        "Matching jobs will auto-open in your browser.\n"
        "You just click Apply!\n\n"
        "Commands:\n"
        "/search     - Search jobs now\n"
        "/autoapply  - Auto-open matching jobs\n"
        "/help       - All commands"
    )

    log.info("Running first poll...")
    poll_and_alert()

    schedule.every(POLL_INTERVAL_MINUTES).minutes.do(poll_and_alert)
    schedule.every(3).seconds.do(check_telegram_messages)

    log.info("Bot live! AI replies active. Auto-poll every " + str(POLL_INTERVAL_MINUTES) + " mins.")

    while True:
        schedule.run_pending()
        time.sleep(1)
