#!/usr/bin/env python3
"""
Standalone Privacy Contact Scraper
Run this to scrape privacy contacts without the full crawler
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from helpers.contact_scraper import (
    scrape_privacy_contacts,
    save_findings,
    findings_to_dataframe,
    get_top_picks,
)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape privacy contact information from websites"
    )

    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-d", "--domain", help="Single domain to scrape (e.g., example.com)"
    )
    input_group.add_argument(
        "-f", "--file", help="File containing list of domains (one per line)"
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        default="privacy_contacts.csv",
        help="Output CSV file (default: privacy_contacts.csv)",
    )

    parser.add_argument(
        "--top-picks",
        action="store_true",
        help="Also save top picks per domain to separate file",
    )

    # Verbose logging
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    logger = setup_logging(args.verbose)

    # Collect domains
    domains = []
    if args.domain:
        domains = [args.domain]
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                domains = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]
        except Exception as e:
            logger.error(f"Error reading file {args.file}: {e}")
            return 1

    if not domains:
        logger.error("No domains to scrape")
        return 1

    logger.info(f"Starting privacy contact scraper for {len(domains)} domain(s)")

    # Scrape all domains
    all_findings = []
    for i, domain in enumerate(domains, 1):
        logger.info(f"[{i}/{len(domains)}] Scraping {domain}...")
        try:
            findings = scrape_privacy_contacts(domain, logger)
            all_findings.extend(findings)
            logger.info(f"  → Found {len(findings)} contact points")
        except Exception as e:
            logger.error(f"  ✗ Error scraping {domain}: {e}")
            continue

    # Save results
    if not all_findings:
        logger.warning("No findings to save")
        return 0

    logger.info(f"\nSaving {len(all_findings)} total findings to {args.output}...")
    save_findings(all_findings, args.output, logger)

    # Save top picks if requested
    if args.top_picks:
        df = findings_to_dataframe(all_findings)
        top_df = get_top_picks(df)
        top_output = args.output.replace(".csv", "_top_picks.csv")
        top_df.to_csv(top_output, index=False, encoding="utf-8")
        logger.info(f"Saved top picks to {top_output}")

    logger.info("\n✓ Privacy contact scraping completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
