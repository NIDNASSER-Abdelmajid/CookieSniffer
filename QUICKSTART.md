# CookieSniffer - Quick Start Guide

## Installation

```bash
cd /home/joyboy/Desktop/crawlers/CookieSniffer
source env/bin/activate
pip install -r requirements.txt
```

## Basic Usage

### Full Crawl (Cookies + Privacy Contacts)

```bash
python3 cli.py -u example.com -t 30
```

Output: `profiles/example_com/data.json`, `profiles/example_com/privacy_contacts_example_com.csv`

### Privacy Contacts Only (Fast)

```bash
python3 run_contact_scraper.py -d example.com -o contacts.csv
```

### Disable Contact Scraping

```bash
python3 cli.py -u example.com -t 30 --no-contact-scraper
```

## Features

- **Cookie Tracking**: Captures all cookies with detailed metadata
- **Privacy Contact Extraction**: Finds emails, links, forms related to privacy/GDPR/CCPA
- **Language Detection**: 6-method weighted voting (HTML lang, meta tags, langdetect, py3langid, URL patterns, keywords)
- **Multi-language Support**: Keyword matching for ES, FR, DE, IT, PT, NL, AR, PL, SV, DA and more

## Configuration

Edit `helpers/contact_scraper_config.py` to customize:

- Candidate paths to check
- Keywords for privacy detection
- Scoring weights
- Extraction methods (emails, mailto, links, forms, JSON-LD)

## Output Columns

CSV includes: domain, page_url, found_type, value, anchor_text, context_snippet, relevance_score, status_code, note, detected_language, language_confidence
