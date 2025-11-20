"""
Configuration for Privacy Contact Scraper
Easily modify these settings without touching the main code
"""

# ===========================
# HTTP Request Configuration
# ===========================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,en-US;q=0.9",
    "Connection": "close",
}

REQUEST_TIMEOUT = 15  # seconds
MAX_BYTES = 3_000_000  # 3 MB per page cap
PAUSE_MIN = 0.8  # minimum delay between requests (seconds)
PAUSE_MAX = 1.8  # maximum delay between requests (seconds)

# ===========================
# Crawling Paths
# ===========================

# Target pages to try per domain (in order of priority)
CANDIDATE_PATHS = [
    "/",
    "/privacy",
    "/privacy-policy",
    "/legal/privacy",
    "/legal",
    "/help/privacy",
    "/support/privacy",
    "/ccpa",
    "/cpra",
    "/do-not-sell",
    "/do-not-sell-my-personal-information",
    "/your-privacy-choices",
    "/data-request",
    "/privacy-request",
    "/dsar",
    "/gdpr",
    "/contact",
    "/about",
    "/imprint",
    "/impressum",
]

# Maximum number of extra links to follow from homepage
MAX_EXTRA_LINKS = 5

# ===========================
# Search Keywords
# ===========================

# Link text / URL keyword patterns (case-insensitive)
KEYWORDS_LINK = [
    r"privacy",
    r"privacy\s*policy",
    r"data\s*protection",
    r"gdpr",
    r"ccpa",
    r"cpra",
    r"erase",
    r"erasure",
    r"delete\s*(my|your)?\s*data",
    r"delete\s*account",
    r"(data\s*subject\s*request|dsar)",
    r"privacy\s*request",
    r"do\s*not\s*sell(\s*or\s*share)?",
    r"your\s*privacy\s*choices",
    r"contact",
    r"impressum",
    r"imprint",
    # Spanish keywords
    r"el\s+derecho\s+al\s+olvido",
    r"el\s+derecho\s+a\s+la\s+supresión\s+de\s+datos",
    r"eliminación\s+de\s+datos",
    r"eliminar\s+mi\s+cuenta",
    r"eliminar\s+mis\s+datos",
    r"solicitud\s+de\s+privacidad",
    r"contacto",
    # German keywords
    r"datenschutz",
    r"impressum",
    r"kontakt",
    # French keywords
    r"confidentialité",
    r"protection\s+des\s+données",
    r"contact",
]

# Text (page body) patterns for context
KEYWORDS_TEXT = [
    r"right\s+to\s+erasure",
    r"right\s+to\s+be\s+forgotten",
    r"article\s*17",
    r"withdraw\s+consent",
    r"supervisory\s+authority",
    r"delete\s+my\s+(data|information)",
    r"verifiable\s+consumer\s+request",
    r"service\s+provider",
    r"do\s+not\s+sell(\s*or\s*share)?",
    # Spanish
    r"derecho\s+al\s+olvido",
    r"derecho\s+a\s+la\s+supresión\s+de\s+datos",
    r"artículo\s+17",
    r"retirar\s+consentimiento",
    r"autoridad\s+de\s+supervisión",
    r"eliminar\s+mis\s+(datos|información)",
    # German
    r"recht\s+auf\s+löschung",
    r"recht\s+auf\s+vergessenwerden",
    r"artikel\s+17",
    # French
    r"droit\s+à\s+l'effacement",
    r"droit\s+à\s+l'oubli",
    r"article\s+17",
]

# ===========================
# Email Detection
# ===========================

# Email regex pattern
EMAIL_REGEX_PATTERN = r"\b([a-z0-9._%+\-]+)@([a-z0-9.\-]+\.[a-z]{2,})\b"

# Privacy-related email handles (for scoring boost)
PRIVACY_HANDLE_PATTERN = r"(privacy|dpo|gdpr|dataprotection|legal|compliance|contact)"

# ===========================
# Scoring Configuration
# ===========================

# Base scores by finding type
SCORE_EMAIL = 60
SCORE_MAILTO = 60
SCORE_JSONLD_EMAIL = 60
SCORE_FORM = 40
SCORE_LINK = 40
SCORE_CONTEXT = 20

# Bonus scores
SCORE_KEYWORD_MATCH = 20
SCORE_PRIVACY_HANDLE = 20

# Maximum score cap
MAX_SCORE = 100

# ===========================
# Output Configuration
# ===========================

# Number of top findings to save per domain
TOP_PICKS_PER_DOMAIN = 3

# CSV column order
OUTPUT_COLUMNS = [
    "domain",
    "page_url",
    "found_type",
    "value",
    "anchor_text",
    "context_snippet",
    "relevance_score",
    "status_code",
    "note",
    "detected_language",
    "language_confidence",
]

# ===========================
# Feature Toggles
# ===========================

# Enable/disable specific extraction methods
EXTRACT_TEXT_EMAILS = True
EXTRACT_MAILTO_LINKS = True
EXTRACT_PRIVACY_LINKS = True
EXTRACT_FORM_BUTTONS = True
EXTRACT_JSONLD = True
EXTRACT_CONTEXT_KEYWORDS = False  # Usually not needed in output

# Enable following extra links from homepage
FOLLOW_HOMEPAGE_LINKS = True

# ===========================
# Advanced Settings
# ===========================

# Context snippet radius (characters before/after match)
CONTEXT_SNIPPET_RADIUS = 120

# Deduplicate findings by these fields
DEDUP_FIELDS = ["domain", "found_type", "value"]
