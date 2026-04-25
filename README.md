# CookieSniffer

Web crawler for cookie tracking and privacy contact extraction with multi-language support.

## Features

- **Cookie Tracking**: Captures all website cookies with detailed metadata
- **Privacy Contact Extraction**: Automatically finds privacy-related emails, forms, and links (GDPR/CCPA compliance contacts)
- **Language Detection**: 6-method weighted voting system for accurate language detection
- **Multi-language Support**: Keyword matching for 10+ languages (EN, ES, FR, DE, IT, PT, NL, AR, PL, SV, DA, etc.)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Full crawl (cookies + privacy contacts)
python cli.py -u example.com -t 30

# Privacy contacts only (without full crawl)
python run_contact_scraper.py -d example.com -o contacts.csv

# GDPR data analysis (convert cookie JSON -> CSV)
python Sec_GDPR_Right_DataAnalysis.py -i data/google_de.json -o cleaned.csv

# Aggregate all JSON files in a folder
python Sec_GDPR_Right_DataAnalysis.py -d data -o aggregated.csv
```

## Recent Changes

### Version Updates and Enhancements

- **Custom CSV Input Support**: Added `-cu` flag to `cli.py` for crawling domains from a custom CSV file (one domain per line). This allows batch processing of specific domain lists, such as regional subsets (e.g., Ireland or Sweden domains).
  - Usage: `python cli.py -cu ireland_domains.csv -t 60`
  - Category is set to "Custom" for tracking.

- **Expanded Domain Datasets**:
  - Added comprehensive Ireland (.ie) domain data collection with 474 domains crawled.
  - Added Sweden (.se) domain data collection.
  - Expanded US domain list in `data.csv` with additional entries (from line 2187 onwards), increasing coverage of US websites for cookie and privacy analysis.

- **New Data Files**:
  - `ireland_domains.csv`: List of Ireland domains for batch crawling.
  - `sweden_domains.csv`: List of Sweden domains for batch crawling.
  - Numerous new JSON data files in `data/` for Ireland and Sweden domains, containing cookie and privacy contact information.

These changes enhance the crawler's flexibility for targeted regional analysis and expand the dataset for GDPR/CCPA compliance research.

## Command Options

### Main Crawler (cli.py)

- `-u URL`: Single URL to crawl
- `-uc CATEGORY`: Crawl URLs from category (eu/usa)
- `-cu FILE`: Crawl domains from a custom CSV file (one domain per line)
- `-t SECONDS`: Time to spend per website (default: 60)
- `-p DIR`: Profiles directory (default: ./profiles)
- `-ch`: Use Chromium browser
- `-vpn`: Use ProtonVPN
- `--no-contact-scraper`: Disable privacy contact extraction

### Contact Scraper (run_contact_scraper.py)

- `-d DOMAIN`: Domain to scrape
- `-f FILE`: File with domain list
- `-o FILE`: Output CSV file
- `--top-picks`: Save top N findings per domain

### GDPR Data Analysis (Sec_GDPR_Right_DataAnalysis.py)

- `-i PATH`: Input JSON file or folder containing `data.json`
- `-d DIR`: Directory of JSON files to aggregate
- `-o FILE`: Output CSV file path

## Project Structure

```
CookieSniffer/
├── cli.py                      # Main CLI interface
├── crawler.py                  # Web crawler core
├── run_contact_scraper.py      # Standalone contact scraper
├── helpers/
│   ├── contact_scraper.py      # Contact extraction logic
│   ├── contact_scraper_config.py # Configuration
│   ├── language_detector.py    # Language detection
│   ├── essentials.py           # Path configurations
│   └── VPN.py                  # VPN management
├── data/                       # Cookie data (JSON)
├── profiles/                   # Per-domain outputs
└── logs/                       # Crawler logs
```

## Configuration

Edit `helpers/contact_scraper_config.py` to customize:

- Candidate paths to check
- Keywords for privacy detection
- Scoring weights
- Extraction methods

## Output

### Cookie Data

`profiles/[domain]/data.json` - Detailed cookie information

### Privacy Contacts

`profiles/[domain]/privacy_contacts_[domain].csv` - Per-domain findings
`privacy_contacts_aggregated.csv` - All findings combined

**CSV Columns**: domain, page_url, found_type, value, anchor_text, context_snippet, relevance_score, status_code, note, detected_language, language_confidence

## Prerequisites

- Python 3.7+
- Chrome/Chromium browser
- Selenium WebDriver
- Optional: ProtonVPN for VPN support

Configure paths in `helpers/essentials.py`:

- `chromium_path`: Path to Chromium executable (for -ch flag)
- `vpn_path`: Path to ProtonVPN (for -vpn flag)

## License

See LICENSE file for details.
