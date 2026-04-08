# ============================================================
#  config.py — Auto-populated from Dayanand Ranmalle's Resume
# ============================================================

# ── Candidate Details (from Resume) ─────────────────────────
CANDIDATE_NAME       = "Dayanand Balaji Ranmalle"
MIN_EXPERIENCE_YEARS = 4.5      # 4+ years on resume

# ── Job Roles to Search ──────────────────────────────────────
# Mapped from: current title + skills + desired roles
JOB_KEYWORDS = [
    "Application Support Engineer",
    "L2 Application Support",
    "Production Support Engineer",
    "Technical Support Engineer",
    "DevOps Engineer",
    "Associate Consultant",
    "Azure DevOps Engineer",
    "WCS WES Support",
]

# ── Preferred Locations ──────────────────────────────────────
JOB_LOCATIONS = [
    "Navi Mumbai",
    "Mumbai",
    "Pune",
    "Hyderabad",
]

# ── Key Skills from Resume (used for relevance match) ────────
CANDIDATE_SKILLS = [
    "SQL", "Oracle", "Linux", "Unix", "Azure DevOps",
    "Kubernetes", "Docker", "Grafana", "WCS", "WES",
    "Application Support", "Production Support", "L2 Support",
    "Kubernetes", "kubectl",
]

# ── Real-Time Polling Config ─────────────────────────────────
# Script polls every N minutes; alerts fire INSTANTLY for new jobs
POLL_INTERVAL_MINUTES = 5               # How often to check (mins)
SEEN_JOBS_FILE        = "seen_jobs.json"  # Tracks already-sent jobs (auto-created)

# ── Results per source per keyword per location ──────────────
MAX_RESULTS_PER_SOURCE = 5

# ── Telegram Bot (FREE & Reliable) ──────────────────────────
# Bot Token from @BotFather on Telegram
TELEGRAM_BOT_TOKEN = "8755358120:AAEWEyt1akoLNnnyjUBDRqk5aVZK4lyYnNc"
# Your personal Chat ID from @userinfobot on Telegram
TELEGRAM_CHAT_ID   = "1736948232"

# ── Email — Gmail SMTP ───────────────────────────────────────
# One-time setup:
#   Enable 2-Step Verification → https://myaccount.google.com/apppasswords
#   Create App Password for "Mail" and paste below
EMAIL_SENDER   = "ranmaledayanand@gmail.com"    # From resume
EMAIL_PASSWORD = "YOUR_GMAIL_APP_PASSWORD"      # ← App Password (not login password)
EMAIL_RECEIVER = "ranmaledayanand@gmail.com"
SMTP_HOST      = "smtp.gmail.com"
SMTP_PORT      = 587

# ── Gemini AI API Key (FREE) ─────────────────────────────
# Free key from: https://aistudio.google.com
GEMINI_API_KEY = "AIzaSyB2_4sOj3y8XTBWH8niwNtpRwPP4ngN_O4"

# ── Gemini AI API Key (FREE) ─────────────────────────────
# Free API key from aistudio.google.com
GEMINI_API_KEY = "AIzaSyB2_4sOj3y8XTBWH8niwNtpRwPP4ngN_O4"
