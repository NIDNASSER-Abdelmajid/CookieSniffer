import argparse
import os
import shutil
import time
import logging
from datetime import datetime
from crawler import WebCrawler
import pandas as pd
from helpers.VPN import connect_to_vpn, disconnect_and_kill_vpn
from helpers.essentials import vpn_path, chromium_path


def setup_logging():
    """Setup logging configuration with log rotation into logs/ folder"""
    log_file = "crawler.log"
    logs_dir = "logs"

    os.makedirs(logs_dir, exist_ok=True)

    if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_log = os.path.join(logs_dir, f"crawler_{timestamp}.log")
        shutil.copy(log_file, archived_log)

        open(log_file, "w").close()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )

    return logging.getLogger(__name__)


def read_urls_from_file(file_path):
    """Read URLs from a file"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", newline="", encoding="utf-8") as f:
            file_urls = f.read().splitlines()
            urls = [
                url.strip().replace("\n", "")
                for url in file_urls
                if url.strip() and "#" not in url
            ]
        return urls
    except Exception as e:
        raise IOError(f"Error reading file {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Simple Web Crawler")

    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("-u", "--url", help="Single URL to crawl")
    url_group.add_argument(
        "-uc", "--url-category", help="Category of URLs to crawl", choices=["eu", "usa"]
    )

    parser.add_argument(
        "-t",
        "--time",
        type=int,
        default=60,
        help="Time to wait on each website (seconds)",
    )
    parser.add_argument(
        "-p",
        "--profile-dir",
        default="profiles",
        help="Directory to store website profiles",
    )
    parser.add_argument(
        "-ch", "--chromium", action="store_true", help="Path to Chromium executable"
    )
    parser.add_argument(
        "-vpn", "--vpn", action="store_true", help="Path to VPN executable"
    )
    parser.add_argument(
        "--no-contact-scraper",
        action="store_true",
        help="Disable privacy contact scraper",
    )

    args = parser.parse_args()

    urls = []

    if args.url_category:
        if args.url_category == "eu":
            urls = pd.read_csv("urls/EU_websites.csv")["Domain"].tolist()
            category = "EU"
        elif args.url_category == "usa":
            urls = pd.read_csv("urls/USA_websites.csv")["Domain"].tolist()
            category = "USA"
    else:
        urls = [args.url]
        category = "Unknown"

    if not urls:
        logging.warning("No URLs provided or found in file.")
        return

    logger = setup_logging()
    logger.info(f"Starting crawler with {len(urls)} URLs")

    if args.vpn:
        logger.info("Connecting to VPN...")
        try:
            connect_to_vpn(vpn_path)
            time.sleep(28.7568)
            logger.info("VPN connected")
        except Exception as e:
            logger.error(f"Error connecting to VPN: {e}")

    master_file = "masterfile.csv"
    if not os.path.exists(master_file):
        pd.DataFrame(
            columns=[
                "Id",
                "URL",
                "Region",
                "Page Title",
                "Crawling Status",
                "Number of Cookies",
                "Number of Requests",
                "Last Successful Crawl",
                "Comment",
            ]
        ).to_csv(master_file, index=False)
    else:
        # Check if Region column exists, if not add it
        df = pd.read_csv(master_file)
        if "Region" not in df.columns:
            df["Region"] = ""
            df.to_csv(master_file, index=False)
    os.makedirs("data", exist_ok=True)

    crawler = WebCrawler(
        profile_dir=args.profile_dir,
        chromium=chromium_path,
        logger=logger,
        enable_contact_scraper=not args.no_contact_scraper,
    )

    try:
        counter = 0
        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] Crawling: {url}")

            try:
                crawler.visit_website(i, url, wait_time=args.time, category=category)
                counter += 1
            except Exception as e:
                logger.error(f"Failed to crawl {url}, continuing to next...")
                continue

            if counter >= 20:
                checkpoint = input("Continue crawling? (y/n): ").strip().lower()
                if checkpoint != "y":
                    logger.info("Crawling session ended by user")
                    break
                counter = 0

    except KeyboardInterrupt:
        logger.warning("Crawler interrupted by user")
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
    finally:
        crawler.close()
        if args.vpn:
            disconnect_and_kill_vpn(vpn_path)
            logger.info("VPN disconnected and killed")
        logger.info("Crawler session completed")


if __name__ == "__main__":
    main()
