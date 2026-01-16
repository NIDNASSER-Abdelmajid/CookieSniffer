import os
import json
import csv
import sys
import time
import logging
from datetime import datetime
from urllib.parse import urlparse
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Import privacy contact scraper
try:
    from helpers.contact_scraper import scrape_privacy_contacts, save_findings

    CONTACT_SCRAPER_AVAILABLE = True
except ImportError:
    CONTACT_SCRAPER_AVAILABLE = False


class WebCrawler:
    def __init__(
        self,
        profile_dir="profiles",
        chromium=None,
        logger=None,
        enable_contact_scraper=True,
    ):

        self.profile_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), profile_dir
        )
        self.logger = logger or logging.getLogger(__name__)
        logging.getLogger("seleniumwire").setLevel(logging.WARNING)
        self.driver = None
        self.current_profile = None
        self.chromium = chromium
        self.enable_contact_scraper = (
            enable_contact_scraper and CONTACT_SCRAPER_AVAILABLE
        )

        os.makedirs(self.profile_dir, exist_ok=True)

        if self.enable_contact_scraper:
            self.logger.info("Privacy contact scraper enabled")
        elif not CONTACT_SCRAPER_AVAILABLE:
            self.logger.warning(
                "Privacy contact scraper not available (missing dependencies)"
            )

    def _init_driver(self, user_data_dir):
        """Initialize Chrome WebDriver with custom binary location"""

        chrome_options = Options()
        # if self.chromium:
        #     chrome_options.binary_location = self.chromium

        chrome_options.add_argument("--start-maximized")
        # # chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        chrome_options.add_argument("--no-sandbox")

        chrome_options.add_argument("--remote-debugging-port=9222")
        # chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        # chrome_options.add_argument("--enable-features=MediaFoundationH264Remoting,UseChromeOSDirectVideoDecoder")
        # chrome_options.add_argument("--disable-features=HardwareMediaKeyHandling")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")

        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # selenium-wire options
        seleniumwire_options = {
            "enable_har": True,  # Capture HAR data, gives us requests
            "disable_capture": False,  # Make sure capture is enabled
        }

        try:
            self.driver = webdriver.Chrome(
                options=chrome_options, seleniumwire_options=seleniumwire_options
            )

            self.logger.info("ChromeDriver with selenium-wire initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error initializing ChromeDriver: {e}")

            try:
                self.logger.info("Trying fallback initialization...")
                self.driver = webdriver.Chrome(
                    options=chrome_options, seleniumwire_options=seleniumwire_options
                )

                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                self.logger.info("ChromeDriver with fallback method")
                return True
            except Exception as e2:
                self.logger.error(f"Fallback initialization also failed: {e2}")
                return False

    def _get_profile_name(self, url):
        """Extract profile name from URL"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace("www.", "")
        safe_domain = "".join(c if c.isalnum() else "_" for c in domain)
        return safe_domain

    def _get_user_data_dir(self, profile_name):
        """Get user data directory for specific profile"""
        return os.path.join(self.profile_dir, profile_name, "user_data")

    def _ensure_directories(self, profile_name):
        """Create necessary directories for a profile"""
        profile_path = os.path.join(self.profile_dir, profile_name)
        user_data_dir = self._get_user_data_dir(profile_name)

        os.makedirs(profile_path, exist_ok=True)
        os.makedirs(user_data_dir, exist_ok=True)

        return profile_path, user_data_dir

    def _capture_network_requests(self):
        """Capture network requests using selenium-wire.

        This attempts to collect request/response pairs that have a response.
        Robust against in-flight/failed requests and missing attributes.
        """
        try:
            total = len(self.driver.requests)
        except Exception as e:
            self.logger.debug(f"Could not read driver.requests length: {e}")
            total = "unknown"

        self.logger.info(f"Capturing {total} total requests from selenium-wire.")

        requests_data = []
        try:
            for request in self.driver.requests:
                try:
                    # To prevent errors on requests that are still in-flight or failed
                    if not getattr(request, "response", None):
                        continue

                    req_body = None
                    try:
                        req_body = (
                            request.body.decode("utf-8", "ignore")
                            if getattr(request, "body", None)
                            else None
                        )
                    except Exception:
                        req_body = None

                    resp_body = None
                    try:
                        resp_body = (
                            request.response.body.decode("utf-8", "ignore")
                            if getattr(request.response, "body", None)
                            else None
                        )
                    except Exception:
                        resp_body = None

                    # Normalize headers safely
                    try:
                        req_headers = (
                            dict(request.headers)
                            if getattr(request, "headers", None)
                            else {}
                        )
                    except Exception:
                        req_headers = {}

                    try:
                        resp_headers = (
                            dict(request.response.headers)
                            if getattr(request.response, "headers", None)
                            else {}
                        )
                    except Exception:
                        resp_headers = {}

                    timestamp = None
                    try:
                        timestamp = (
                            request.date.isoformat()
                            if hasattr(request, "date") and request.date
                            else None
                        )
                    except Exception:
                        timestamp = None

                    requests_data.append(
                        {
                            "request": {
                                "url": getattr(request, "url", None),
                                "method": getattr(request, "method", None),
                                "headers": req_headers,
                                "body": req_body,
                            },
                            "response": {
                                "status_code": getattr(
                                    request.response, "status_code", None
                                ),
                                "headers": resp_headers,
                                "body": resp_body,
                            },
                            "timestamp": timestamp,
                        }
                    )
                except Exception as e:
                    # Log and continue processing remaining requests
                    self.logger.debug(f"Error processing a request: {e}")
                    continue
        except Exception as e:
            self.logger.error(f"Error iterating driver.requests: {e}")
            return []

        self.logger.info(
            f"Successfully processed {len(requests_data)} requests with responses."
        )
        return requests_data

    def _sanitize_for_json(self, obj):
        """Recursively sanitize strings in obj to remove problematic line separators and normalize line endings.

        Replaces U+2028 and U+2029 with '\n' and converts CRLF/CR to LF. Handles dicts, lists, and strings.
        """
        try:
            if isinstance(obj, str):
                # Formatting
                s = obj.replace("\u2028", "\n").replace("\u2029", "\n")
                s = s.replace("\r\n", "\n").replace("\r", "\n")
                return s
            elif isinstance(obj, dict):
                return {k: self._sanitize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [self._sanitize_for_json(v) for v in obj]
            else:
                return obj
        except Exception as e:
            self.logger.debug(f"_sanitize_for_json error: {e}")
            return obj

    def _capture_set_cookie_headers(self):
        """Collect raw Set-Cookie headers from captured responses for debugging."""
        headers = []
        try:
            for request in self.driver.requests:
                resp = request.response
                if not resp:
                    continue

                sc = None
                try:
                    sc = resp.headers.get("Set-Cookie") or resp.headers.get(
                        "set-cookie"
                    )
                except Exception:
                    try:
                        sc = dict(resp.headers).get("Set-Cookie") or dict(
                            resp.headers
                        ).get("set-cookie")
                    except Exception:
                        sc = None

                if not sc:
                    continue

                # Normalize to list
                if isinstance(sc, (list, tuple)):
                    for c in sc:
                        headers.append({"url": request.url, "set_cookie_header": c})
                else:
                    headers.append({"url": request.url, "set_cookie_header": sc})
        except Exception as e:
            self.logger.debug(f"_capture_set_cookie_headers error: {e}")

        self.logger.info(
            f"Captured {len(headers)} Set-Cookie header occurrences from responses."
        )
        return headers

    def _capture_all_cookies(self):
        """Capture all unique cookies from the browser session (selenium get_cookies)."""
        try:
            cookies = self.driver.get_cookies()
            self.logger.info(
                f"Captured {len(cookies)} cookies via driver.get_cookies()."
            )

            # Deduplicate just in case, though get_cookies should be fairly clean
            seen = set()
            unique_cookies = []
            for c in cookies:
                key = (c.get("name"), c.get("domain"), c.get("path"))
                if key not in seen:
                    seen.add(key)
                    unique_cookies.append(c)

            return unique_cookies
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to capture cookies: {e}")
            return []

    def _capture_cdp_cookies(self):
        """Capture cookies via Chrome DevTools Protocol (Network.getAllCookies).

        This returns cookies the browser knows about, including third-party cookies
        that may not be visible via driver.get_cookies() when a proxy is active.
        """
        try:
            # Use CDP to get all cookies
            result = self.driver.execute_cdp_cmd("Network.getAllCookies", {})
            cdp = result.get("cookies", []) if isinstance(result, dict) else []
            self.logger.info(
                f"Captured {len(cdp)} cookies via CDP Network.getAllCookies."
            )
            return cdp
        except Exception as e:
            self.logger.debug(f"_capture_cdp_cookies error: {e}")
            return []

    def _normalize_cdp_cookie(self, cdp_cookie):
        """Normalize a CDP cookie dict to Selenium-style cookie structure."""
        try:
            cookie = {
                "name": cdp_cookie.get("name"),
                "value": cdp_cookie.get("value"),
                "domain": cdp_cookie.get("domain") or "",
                "path": cdp_cookie.get("path") or "/",
                "expiry": (
                    int(cdp_cookie.get("expires"))
                    if cdp_cookie.get("expires")
                    else None
                ),
                "secure": bool(cdp_cookie.get("secure", False)),
                "httpOnly": bool(cdp_cookie.get("httpOnly", False)),
                "sameSite": cdp_cookie.get("sameSite"),
                "source": "cdp",
            }
            return cookie
        except Exception as e:
            self.logger.debug(f"_normalize_cdp_cookie error: {e}")
            return {}

    def _parse_set_cookie_header(self, raw_header, url):
        """Parse a Set-Cookie header string into a cookie dict similar to Selenium's format.

        This is best-effort parsing: we extract name, value, Domain, Path, Expires, Secure, HttpOnly.
        """
        try:
            parts = [p.strip() for p in raw_header.split(";") if p.strip()]
            if not parts:
                return {}

            # First part is name=value
            name_value = parts[0]
            if "=" not in name_value:
                return {}
            name, value = name_value.split("=", 1)
            cookie = {"name": name, "value": value}

            # Defaults
            domain = urlparse(url).netloc
            path = "/"
            expiry = None
            secure = False
            httpOnly = False

            for attr in parts[1:]:
                if "=" in attr:
                    k, v = attr.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "domain":
                        domain = v
                    elif k == "path":
                        path = v
                    elif k == "expires":
                        try:
                            from email.utils import parsedate_to_datetime

                            dt = parsedate_to_datetime(v)
                            expiry = int(dt.timestamp())
                        except Exception:
                            expiry = None
                else:
                    # Flags
                    if attr.lower() == "secure":
                        secure = True
                    if attr.lower() == "httponly":
                        httpOnly = True

            cookie.update(
                {
                    "domain": domain,
                    "path": path,
                    "expiry": expiry,
                    "secure": secure,
                    "httpOnly": httpOnly,
                    "source": "set-cookie",
                }
            )
            return cookie
        except Exception as e:
            self.logger.debug(f"_parse_set_cookie_header error: {e}")
            return {}

    def _merge_cookies(self, selenium_cookies, cdp_cookies, set_cookie_cookies):
        """Merge cookies from Selenium, CDP, and Set-Cookie parsed headers into a deduplicated list.

        Priority (highest to lowest): Selenium API values > CDP > Set-Cookie header parsing
        Deduplication key: (name, domain_normalized, path)
        """
        merged = {}

        def norm_domain(d):
            if not d:
                return ""
            return d.lstrip(".").lower()

        def add_cookie(c, src):
            try:
                name = c.get("name")
                if not name:
                    return
                domain = norm_domain(c.get("domain") or "")
                path = c.get("path") or "/"
                key = (name, domain, path)
                if key not in merged:
                    new = {
                        "name": name,
                        "value": c.get("value"),
                        "domain": c.get("domain") or "",
                        "path": path,
                        "expiry": c.get("expiry"),
                        "secure": c.get("secure", False),
                        "httpOnly": c.get("httpOnly", False),
                        "sameSite": c.get("sameSite"),
                        "sources": [src],
                    }
                    merged[key] = new
                else:
                    existing = merged[key]
                    # Update empty fields from lower-priority sources
                    for k in ["value", "expiry", "secure", "httpOnly", "sameSite"]:
                        if not existing.get(k) and c.get(k) is not None:
                            existing[k] = c.get(k)
                    if src not in existing.get("sources", []):
                        existing["sources"].append(src)
            except Exception as e:
                self.logger.debug(f"_merge_cookies add_cookie error: {e}")

        for c in set_cookie_cookies or []:
            add_cookie(c, "set-cookie")
        for c in cdp_cookies or []:
            add_cookie(c, "cdp")
        for c in selenium_cookies or []:
            add_cookie(c, "selenium")

        normalized_result = []
        for v in merged.values():
            normalized_result.append(
                {
                    "name": v.get("name"),
                    "value": v.get("value"),
                    "domain": v.get("domain", ""),
                    "path": v.get("path", "/"),
                    "expiry": v.get("expiry"),
                    "secure": bool(v.get("secure", False)),
                    "httpOnly": bool(v.get("httpOnly", False)),
                    "sameSite": (
                        v.get("sameSite") if v.get("sameSite") is not None else None
                    ),
                }
            )

        self.logger.info(
            f"Merged cookies count: {len(normalized_result)} (selenium={len(selenium_cookies or [])}, cdp={len(cdp_cookies or [])}, set_cookie={len(set_cookie_cookies or [])})"
        )
        return normalized_result

    def _save_data(
        self,
        profile_path,
        url,
        cookies,
        requests,
        profile_name,
        set_cookie_headers=None,
    ):
        """Save all captured data to a JSON file."""
        data_file = os.path.join(profile_path, "data.json")
        parsed_url_fname = url.replace("www.", "").replace(".", "_").split("//")[-1]

        source_domain = urlparse(url).netloc
        timestamp = datetime.now().isoformat()
        page_title = self.driver.title if self.driver else ""
        browser_id = profile_name

        if set_cookie_headers is None:
            try:
                set_cookie_headers = self._capture_set_cookie_headers()
            except Exception:
                set_cookie_headers = []

        # if set_cookie_headers and len(set_cookie_headers) > len(cookies):
        # self.logger.warning(
        #    f"Mismatch: {len(set_cookie_headers)} Set-Cookie headers observed but only {len(cookies)} cookies present in browser. "
        #    "This could indicate the proxy interfered with cookie setting or cookies were set in channels not visible to the browser."
        # )

        # Parse names from Set-Cookie headers and compare to captured cookie names
        # try:
        #    captured_names = set([c.get("name") for c in cookies if c.get("name")])
        #    set_cookie_names = set()
        #    for entry in set_cookie_headers:
        #        raw = entry.get("set_cookie_header", "")
        # cookie string is typically 'NAME=VALUE; attr=...'
        #        name_part = raw.split("=", 1)[0].strip() if raw else None
        #        if name_part:
        # Some headers may include attributes or malformed strings; strip trailing semicolon
        #            set_cookie_names.add(name_part)

        #    missing = set_cookie_names - captured_names
        #    if missing:
        #        sample = list(missing)[:10]
        #       self.logger.warning(
        #           f"Cookies present in Set-Cookie headers but missing from browser cookie jar (sample up to 10): {sample}"
        #        )
        # except Exception as e:
        #    self.logger.debug(
        #       f"Error while comparing Set-Cookie headers to browser cookies: {e}"
        #    )

        # Determine party type for cookies
        for cookie in cookies:
            cookie_domain = cookie.get("domain", "")
            if cookie_domain:
                cookie_domain_clean = cookie_domain.lstrip(".")
                if (
                    source_domain.endswith(cookie_domain_clean)
                    or cookie_domain_clean == source_domain
                ):
                    cookie["party_type"] = "first-party"
                else:
                    cookie["party_type"] = "third-party"
            else:
                cookie["party_type"] = "unknown"

        # Output JSON
        output_data = {
            "source_url": url,
            "source_domain": source_domain,
            "page_title": page_title,
            "browser_id": browser_id,
            "crawl_timestamp": timestamp,
            "cookies": cookies,
            "network_requests": requests,
            "cookie_count": len(cookies or []),
            "request_count": len(requests or []),
        }

        # Check POST request bodies captured
        try:
            post_requests = [
                r
                for r in requests
                if r.get("request", {}).get("method", "").upper() == "POST"
            ]
            post_with_body = [
                r for r in post_requests if r.get("request", {}).get("body")
            ]
            self.logger.info(
                f"POST requests: {len(post_requests)}, bodies captured: {len(post_with_body)}"
            )
            if len(post_requests) and len(post_with_body) < len(post_requests):
                self.logger.warning(
                    f"Some POST requests ({len(post_requests)-len(post_with_body)}) did not have bodies captured."
                )

            problematic_bodies = 0
            for r in post_with_body:
                body = r.get("request", {}).get("body")
                if isinstance(body, str) and ("\u2028" in body or "\u2029" in body):
                    problematic_bodies += 1
            if problematic_bodies:
                self.logger.warning(
                    f"Found {problematic_bodies} POST bodies containing unusual line separators (U+2028/U+2029)"
                )
        except Exception as e:
            self.logger.debug(f"Error while checking POST bodies: {e}")

        try:
            # Build per-cookie records that include request metadata and bodies
            cookie_records = []

            def _find_request_for_cookie(name):
                try:
                    for r in requests or []:
                        try:
                            resp_headers = (
                                r.get("response", {}).get("headers", {}) or {}
                            )
                            for hv in resp_headers.values():
                                if not hv:
                                    continue
                                if isinstance(hv, (list, tuple)):
                                    for v in hv:
                                        if isinstance(v, str) and f"{name}=" in v:
                                            return r
                                elif isinstance(hv, str) and f"{name}=" in hv:
                                    return r
                        except Exception:
                            continue
                except Exception:
                    pass
                return None

            for c in cookies or []:
                req_match = _find_request_for_cookie(c.get("name"))
                request_url = None
                request_method = None
                request_timestamp = None
                request_body = None
                request_headers = None
                response_status = None
                response_headers = None
                if req_match:
                    request_url = req_match.get("request", {}).get("url")
                    request_method = req_match.get("request", {}).get("method")
                    request_timestamp = req_match.get("timestamp")
                    request_body = req_match.get("request", {}).get("body")
                    request_headers = req_match.get("request", {}).get("headers")
                    response_status = req_match.get("response", {}).get("status_code")
                    response_headers = req_match.get("response", {}).get("headers")

                cookie_records.append(
                    {
                        "cookie_name": c.get("name"),
                        "cookie_value": c.get("value"),
                        "cookie_domain": c.get("domain", ""),
                        "cookie_path": c.get("path", "/"),
                        "cookie_secure": bool(c.get("secure", False)),
                        "cookie_httpOnly": bool(c.get("httpOnly", False)),
                        "cookie_expires": c.get("expiry"),
                        "request_url": request_url,
                        "request_method": request_method,
                        "request_timestamp": request_timestamp,
                        "request_body": request_body,
                        "request_headers": request_headers,
                        "response_status_code": response_status,
                        "response_headers": response_headers,
                        "source_url": url,
                        "timestamp": timestamp,
                        "page_title": page_title,
                        "browser_id": browser_id,
                        "party_type": c.get("party_type", "unknown"),
                    }
                )

            # Replace cookies in output_data with the richer per-cookie records
            output_data["cookies"] = cookie_records

            # Sanitize everything
            try:
                sanitized = self._sanitize_for_json(output_data)
            except Exception as e:
                self.logger.debug(f"Sanitization failed: {e}")
                sanitized = output_data

            # Save to profile-specific data.json (full object)
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(sanitized, f, indent=2, ensure_ascii=False)

            # Save to global data/ folder as an array of cookie records (matching existing files)
            global_data_file = os.path.join("data", f"{parsed_url_fname}.json")
            try:
                sanitized_cookie_records = self._sanitize_for_json(cookie_records)
            except Exception:
                sanitized_cookie_records = cookie_records
            with open(global_data_file, "w", encoding="utf-8") as f:
                json.dump(sanitized_cookie_records, f, indent=2, ensure_ascii=False)

            self.logger.info(
                f"Data saved: {len(cookie_records or [])} cookies and {len(requests or [])} network requests."
            )

            cookies_only_file = os.path.join(profile_path, "cookies.json")
            try:
                cookies_only = {
                    "cookies": cookie_records,
                    "cookie_count": len(cookie_records or []),
                    "request_count": len(requests or []),
                }
                sanitized_cookies_only = self._sanitize_for_json(cookies_only)
                with open(cookies_only_file, "w", encoding="utf-8") as cf:
                    json.dump(sanitized_cookies_only, cf, indent=2, ensure_ascii=False)
                self.logger.info(
                    f"Cookies-only file saved: {cookies_only_file} ({len(cookie_records or [])} cookies)"
                )
            except Exception as e:
                self.logger.error(f"Error saving cookies-only file: {e}")

        except Exception as e:
            self.logger.error(f"Error saving data: {e}")

    def visit_website(self, website_index, url, wait_time=10, category="Unknown"):
        """Visit a website and capture data"""
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            profile_name = self._get_profile_name(url)
            self.current_profile = profile_name

            profile_path, user_data_dir = self._ensure_directories(profile_name)

            self.logger.info(f"Using profile: {profile_name}")

            if self.driver:
                self.driver.quit()
                self.driver = None

            if not self._init_driver(user_data_dir):
                raise RuntimeError("Failed to initialize ChromeDriver")

            parsed_url = urlparse(url)
            domain_root = f"{parsed_url.scheme}://{parsed_url.netloc}"

            self.logger.info(f"Navigating to domain root first: {domain_root}")
            self.driver.get(domain_root)

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            data_file = os.path.join(profile_path, "data.json")
            data_folder = "data"
            os.makedirs(data_folder, exist_ok=True)
            # NOTE: restoring cookies from previous session was intentionally disabled.

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            initial_cookies = self._capture_all_cookies()
            self.logger.info(
                f"Initial cookies after navigation: {len(initial_cookies)}"
            )

            self.logger.info(f"Waiting for {wait_time} seconds for the page to load...")
            time.sleep(wait_time)

            self.logger.info("Waiting for user input...")
            comment = input("Enter a comment for this crawl (or press Enter to skip): ")

            self.logger.info("Capturing data...")
            selenium_cookies = self._capture_all_cookies()
            requests = self._capture_network_requests()
            # Debug
            self.logger.debug(
                f"_capture_network_requests returned type={type(requests)}, len={len(requests) if isinstance(requests, list) else 'N/A'}"
            )

            if requests is None or not isinstance(requests, list):
                self.logger.warning(
                    "_capture_network_requests returned non-list; coercing to empty list"
                )
                requests = []
            set_cookie_headers = self._capture_set_cookie_headers()

            set_cookie_cookies = []
            for e in set_cookie_headers:
                parsed = self._parse_set_cookie_header(
                    e.get("set_cookie_header", ""), e.get("url", "")
                )
                if parsed:
                    set_cookie_cookies.append(parsed)

            cdp_raw = self._capture_cdp_cookies()
            cdp_cookies = [self._normalize_cdp_cookie(c) for c in (cdp_raw or [])]

            merged_cookies = self._merge_cookies(
                selenium_cookies, cdp_cookies, set_cookie_cookies
            )

            cookies = merged_cookies

            # Log mismatch if plenty of Set-Cookie headers but few merged cookies
            # try:
            #    if len(set_cookie_headers) > len(merged_cookies):
            #        self.logger.warning(
            #            f"Observed {len(set_cookie_headers)} Set-Cookie headers, but only {len(merged_cookies)} merged cookies present. "
            #            "This may indicate proxy interference, browser blocking, or path/domain mismatches."
            #        )
            # except Exception:
            #    pass

            self._save_data(
                profile_path,
                url,
                merged_cookies,
                requests,
                profile_name,
                set_cookie_headers,
            )

            # Run privacy contact scraper after saving cookie data
            if self.enable_contact_scraper:
                try:
                    self.logger.info("[Privacy Contact Scraper] Starting scan...")

                    # Extract domain from URL
                    domain = urlparse(url).netloc

                    # Run the scraper
                    findings = scrape_privacy_contacts(domain, self.logger)

                    # Save to domain-specific file
                    safe_domain = "".join(c if c.isalnum() else "_" for c in domain)
                    output_file = os.path.join(
                        profile_path, f"privacy_contacts_{safe_domain}.csv"
                    )
                    save_findings(findings, output_file, self.logger)

                    aggregated_file = "privacy_contacts_aggregated.csv"
                    if findings:
                        from helpers.contact_scraper import findings_to_dataframe

                        df = findings_to_dataframe(findings)
                        if not df.empty:
                            if os.path.exists(aggregated_file):
                                df.to_csv(
                                    aggregated_file,
                                    mode="a",
                                    header=False,
                                    index=False,
                                    encoding="utf-8",
                                )
                            else:
                                df.to_csv(
                                    aggregated_file,
                                    mode="w",
                                    header=True,
                                    index=False,
                                    encoding="utf-8",
                                )
                            self.logger.info(
                                f"[Privacy Contact Scraper] Added {len(df)} entries to {aggregated_file}"
                            )
                            try:
                                import shutil
                                import subprocess
                                import sys

                                script = os.path.join(
                                    os.path.dirname(__file__),
                                    "Sec_GDPR_Right_DataAnalysis.py",
                                )
                                gdpr_output_dir = os.path.join("Processed_Data")
                                os.makedirs(gdpr_output_dir, exist_ok=True)
                                gdpr_output = os.path.join(
                                    gdpr_output_dir, f"{profile_name}_gdpr_analysis.csv"
                                )
                                cookies_file = os.path.join(
                                    profile_path, "cookies.json"
                                )

                                interpreters = []
                                if sys.executable:
                                    interpreters.append(sys.executable)
                                py = shutil.which("python")
                                py3 = shutil.which("python3")
                                if py and py not in interpreters:
                                    interpreters.append(py)
                                if py3 and py3 not in interpreters:
                                    interpreters.append(py3)

                                ran = False
                                for interp in interpreters:
                                    try:
                                        proc = subprocess.run(
                                            [
                                                interp,
                                                script,
                                                "-i",
                                                profile_path,
                                                "-o",
                                                gdpr_output,
                                            ],
                                            capture_output=True,
                                            text=True,
                                            timeout=120,
                                        )
                                        if proc.returncode == 0:
                                            self.logger.info(
                                                f"GDPR analysis saved: {gdpr_output} (via {interp})"
                                            )
                                            ran = True
                                            break
                                        else:
                                            self.logger.warning(
                                                f"GDPR analysis via {interp} failed (rc={proc.returncode}): {proc.stderr.strip()}"
                                            )
                                    except Exception as e:
                                        self.logger.warning(
                                            f"GDPR analysis via {interp} exception: {e}"
                                        )

                                if not ran:
                                    try:
                                        from helpers.Sec_GDPR_Right_DataAnalysis import (
                                            process_json_to_csv,
                                        )

                                        process_json_to_csv(profile_path, gdpr_output)
                                        self.logger.info(
                                            f"GDPR analysis saved (in-process): {gdpr_output}"
                                        )
                                    except Exception as e:
                                        self.logger.error(f"GDPR analysis failed: {e}")
                            except Exception as e:
                                self.logger.error(f"GDPR analysis launch failed: {e}")

                except Exception as scraper_error:
                    self.logger.error(
                        f"[Privacy Contact Scraper] Error: {scraper_error}"
                    )

            # Update masterfile.csv safely
            rows = []
            updated = False
            with open("masterfile.csv", "r", newline="", encoding="utf-8") as mf:
                reader = csv.reader(mf)
                header = next(reader)
                if "Region" not in header:
                    header.insert(2, "Region")
                rows.append(header)
                for row in reader:
                    if "Region" not in header and len(header) == 8:
                        row.insert(2, "")
                    if len(row) > 1 and row[1] == url:
                        row[2] = category
                        row[3] = self.driver.title
                        row[4] = "Success" if not comment else "Failed"
                        row[5] = str(len(cookies))
                        row[6] = str(len(requests or []))
                        row[7] = datetime.now().isoformat()
                        row[8] = comment
                        updated = True
                    rows.append(row)

            if not updated:
                new_row = [
                    str(website_index),
                    url,
                    category,
                    self.driver.title,
                    "Success" if not comment else "Failed",
                    str(len(cookies)),
                    str(len(requests or [])),
                    datetime.now().isoformat(),
                    comment,
                ]
                rows.append(new_row)

            with open("masterfile.csv", "w", newline="", encoding="utf-8") as mf:
                writer = csv.writer(mf)
                writer.writerows(rows)

            # Remove from input file if success
            if not comment and category in ("EU", "USA"):
                # Determine source CSV by category
                source_csv = (
                    "urls/EU_websites.csv"
                    if category == "EU"
                    else "urls/USA_websites.csv"
                )
                domain_to_remove = urlparse(url).netloc.replace("www.", "")
                try:
                    remaining_rows = []
                    with open(source_csv, "r", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        fieldnames = reader.fieldnames or []
                        for row in reader:
                            if row.get("Domain", "").strip() != domain_to_remove:
                                remaining_rows.append(row)
                    # Write back without the removed domain
                    with open(source_csv, "w", newline="", encoding="utf-8") as f:
                        if fieldnames:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(remaining_rows)
                    self.logger.info(
                        f"Removed {domain_to_remove} from {source_csv} after successful crawl"
                    )
                except Exception as rem_err:
                    self.logger.error(
                        f"Error updating source list {source_csv}: {rem_err}"
                    )

            self.logger.info(f"Title: {self.driver.title}")
            self.logger.info(
                f"URL(last visited page/subpage): {self.driver.current_url}"
            )
            self.logger.info(f"Cookies captured: {len(cookies)}")
            self.logger.info(f"Requests captured: {len(requests or [])}")

        except Exception as e:
            self.logger.error(f"Error visiting {url}: {e}")

            if self.driver:
                self.driver.quit()
                self.driver = None

            try:
                rows = []
                updated = False
                with open("masterfile.csv", "r", newline="", encoding="utf-8") as mf:
                    reader = csv.reader(mf)
                    header = next(reader)
                    if "Region" not in header:
                        header.insert(2, "Region")
                    rows.append(header)
                    for row in reader:
                        if "Region" not in header and len(header) == 8:
                            row.insert(2, "")
                        if len(row) > 1 and row[1] == url:
                            row[2] = category
                            row[3] = ""
                            row[4] = "Failed"
                            row[5] = "0"
                            row[6] = "0"
                            row[7] = datetime.now().isoformat()
                            row[8] = "Connection timeout"
                            updated = True
                        rows.append(row)

                if not updated:
                    if "Region" not in header:
                        new_row = [
                            str(website_index),
                            url,
                            category,
                            "",
                            "Failed",
                            "0",
                            "0",
                            datetime.now().isoformat(),
                            "Connection timeout",
                        ]
                    else:
                        new_row = [
                            str(website_index),
                            url,
                            category,
                            "",
                            "Failed",
                            "0",
                            "0",
                            datetime.now().isoformat(),
                            "Connection timeout",
                        ]
                    rows.append(new_row)

                with open("masterfile.csv", "w", newline="", encoding="utf-8") as mf:
                    writer = csv.writer(mf)
                    writer.writerows(rows)
            except Exception as csv_error:
                self.logger.error(f"Error updating CSV: {csv_error}")
            raise

    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser closed")
            except Exception:
                pass
            finally:
                self.driver = None
