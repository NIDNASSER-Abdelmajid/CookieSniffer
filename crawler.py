import os
import json
import csv
import time
import logging
import threading
from datetime import datetime
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

class WebCrawler:
    def __init__(self, profile_dir="profiles", chromium=None, logger=None):

        self.profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), profile_dir)
        self.logger = logger or logging.getLogger(__name__)
        self.driver = None
        self.current_profile = None
        self.chromium = chromium

        os.makedirs(self.profile_dir, exist_ok=True)
    
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
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option("useAutomationExtension", False)


        # TODO: Implement next step here

        try:
            self.driver = webdriver.Chrome(
                options=chrome_options
            )
            
            # Enable network domain to capture all network events including headers
            self.driver.execute_cdp_cmd("Network.enable", {
                "maxTotalBufferSize": 10000000,
                "maxResourceBufferSize": 5000000,
                "maxPostDataSize": 5000000
            })
            
            # Also enable Page domain for complete monitoring
            self.driver.execute_cdp_cmd("Page.enable", {})
            
            self.logger.info("ChromeDriver initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing ChromeDriver: {e}")
            
            try:
                self.logger.info("Trying fallback initialization...")
                self.driver = webdriver.Chrome(options=chrome_options)

                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                self.logger.info("ChromeDriver initialized with fallback method")
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
        """Capture network requests and associate cookies with setting requests"""
        try:
            logs = self.driver.get_log("performance")
            requests = []
            cookies_before_request = {}
            
            for log_entry in logs:
                try:
                    log_message = json.loads(log_entry["message"])["message"]
                    method = log_message["method"]
                    params = log_message["params"]
                    
                    if method == "Network.requestWillBeSent":
                        request_id = params["requestId"]
                        request = params["request"]
                        
                        # Capture cookies before this request
                        try:
                            current_cookies = self.driver.get_cookies()
                            cookies_before_request[request_id] = {f"{c['name']}:{c.get('domain', '')}": c for c in current_cookies}
                        except:
                            cookies_before_request[request_id] = {}
                        
                        requests.append({
                            "id": request_id,
                            "url": request["url"],
                            "method": request["method"],
                            "timestamp": datetime.fromtimestamp(log_entry["timestamp"] / 1000).isoformat(),
                            "headers": request.get("headers", {}),
                            "cookies_set": []
                        })
                        
                    elif method == "Network.loadingFinished":
                        request_id = params["requestId"]
                        
                        # Capture cookies after this request finished
                        try:
                            current_cookies = self.driver.get_cookies()
                            current_cookie_map = {f"{c['name']}:{c.get('domain', '')}": c for c in current_cookies}
                            
                            # Find the request this corresponds to
                            for req in requests:
                                if req["id"] == request_id and request_id in cookies_before_request:
                                    prev_cookies = cookies_before_request[request_id]
                                    
                                    # Find new cookies
                                    new_cookies = []
                                    for cookie_key, cookie_data in current_cookie_map.items():
                                        if cookie_key not in prev_cookies:
                                            # This is a new cookie
                                            new_cookies.append({
                                                "name": cookie_data["name"],
                                                "value": cookie_data["value"],
                                                "domain": cookie_data.get("domain", ""),
                                                "path": cookie_data.get("path", "/"),
                                                "secure": cookie_data.get("secure", False),
                                                "httpOnly": cookie_data.get("httpOnly", False)
                                            })
                                    
                                    if new_cookies:
                                        req["cookies_set"] = new_cookies
                                        self.logger.info(f"Request {req['url'][:50]}... set {len(new_cookies)} cookies")
                                    break
                                    
                        except Exception as e:
                            self.logger.debug(f"Error checking cookies for request {request_id}: {e}")
                            
                except Exception as e:
                    self.logger.debug(f"Error processing log entry: {e}")
                    continue
            
            # Debug logging
            cookies_found = sum(len(req.get("cookies_set", [])) for req in requests)
            self.logger.info(f"Captured {len(requests)} requests with {cookies_found} cookies set via network activity")
            
            return requests
        except Exception as e:
            self.logger.error(f"Error capturing requests: {e}")
            return []

    def _capture_all_cookies(self):
        """Capture all cookies (standard, CDP, JS) and merge them."""
        all_cookies = []

        # 1. Normal cookies
        try:
            selenium_cookies = self.driver.get_cookies()
            all_cookies.extend(selenium_cookies)
        except Exception as e:
            if self.logger: self.logger.error(f"Selenium get_cookies failed: {e}")

        # 2. CDP cookies
        try:
            cdp_cookies = self.driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            all_cookies.extend(cdp_cookies)
        except Exception as e:
            if self.logger: self.logger.error(f"CDP getAllCookies failed: {e}")

        seen = set()
        unique_cookies = []
        for c in all_cookies:
            key = (c.get("name"), c.get("domain"), c.get("path"))
            if key not in seen:
                seen.add(key)
                unique_cookies.append(c)

        return unique_cookies


    def _save_data(self, profile_path, url, cookies, requests, profile_name):
        """Save all data to JSON file with flattened structure - only cookies with request associations"""
        data_file = os.path.join(profile_path, "data.json")
        parsed_url = url.replace("www.","").replace(".", "_").split("//")[-1]
        
        source_domain = urlparse(url).netloc
        timestamp = datetime.now().isoformat()
        page_title = self.driver.title if self.driver else ""
        browser_id = profile_name  # Using profile_name as browser_id
        
        entries = []
        processed_cookies = set()  # Track which cookies we've already added
        
        # Process requests and match with cookies
        for request in requests:
            request_url = request["url"]
            request_method = request["method"]
            request_timestamp = request["timestamp"]
            
            # Skip chrome:// and other internal URLs
            if request_url.startswith(("chrome://", "chrome-extension://", "devtools://")):
                continue
            
            request_domain = request_url.split("/")[2] if "://" in request_url else ""
            
            # Check if this request set any cookies (from before/after comparison)
            cookies_set = request.get("cookies_set", [])
            
            if cookies_set:
                # This request directly set cookies
                for cookie_info in cookies_set:
                    cookie_name = cookie_info.get("name", "")
                    cookie_value = cookie_info.get("value", "")
                    cookie_domain = cookie_info.get("domain", "")
                    cookie_path = cookie_info.get("path", "/")
                    cookie_secure = cookie_info.get("secure", False)
                    cookie_httpOnly = cookie_info.get("httpOnly", False)
                    
                    # Skip if essential cookie attributes are null/empty
                    if not cookie_name or not cookie_value:
                        continue
                    
                    # Determine party_type
                    if cookie_domain:
                        cookie_domain_clean = cookie_domain.lstrip(".")
                        if source_domain.endswith(cookie_domain_clean) or cookie_domain_clean == source_domain:
                            party_type = "first-party"
                        else:
                            party_type = "third-party"
                    else:
                        party_type = "unknown"
                    
                    entry = {
                        "cookie_name": cookie_name,
                        "cookie_value": cookie_value,
                        "cookie_domain": cookie_domain,
                        "cookie_path": cookie_path,
                        "cookie_secure": cookie_secure,
                        "cookie_httpOnly": cookie_httpOnly,
                        "request_url": request_url,
                        "request_method": request_method,
                        "request_timestamp": request_timestamp,
                        "source_url": url,
                        "timestamp": timestamp,
                        "page_title": page_title,
                        "browser_id": browser_id,
                        "party_type": party_type
                    }
                    entries.append(entry)
                    processed_cookies.add(f"{cookie_name}:{cookie_domain}")
            else:
                # Try to match existing cookies with this request based on domain matching
                for cookie in cookies:
                    cookie_name = cookie.get("name", "")
                    cookie_value = cookie.get("value", "")
                    cookie_domain = cookie.get("domain", "")
                    cookie_path = cookie.get("path", "/")
                    cookie_secure = cookie.get("secure", False)
                    cookie_httpOnly = cookie.get("httpOnly", False)
                    
                    if not cookie_name or not cookie_value:
                        continue
                    
                    # Check if cookie domain matches request domain
                    cookie_domain_clean = cookie_domain.lstrip(".")
                    matches_domain = (
                        request_domain.endswith(cookie_domain_clean) or
                        cookie_domain_clean == request_domain or
                        request_domain == cookie_domain
                    )
                    
                    # Check if this cookie hasn't been processed yet
                    cookie_key = f"{cookie_name}:{cookie_domain}"
                    if matches_domain and cookie_key not in processed_cookies:
                        # Determine party_type
                        if cookie_domain:
                            if source_domain.endswith(cookie_domain_clean) or cookie_domain_clean == source_domain:
                                party_type = "first-party"
                            else:
                                party_type = "third-party"
                        else:
                            party_type = "unknown"

                        entry = {
                            "cookie_name": cookie_name,
                            "cookie_value": cookie_value,
                            "cookie_domain": cookie_domain,
                            "cookie_path": cookie_path,
                            "cookie_secure": cookie_secure,
                            "cookie_httpOnly": cookie_httpOnly,
                            "request_url": request_url,
                            "request_method": request_method,
                            "request_timestamp": request_timestamp,
                            "source_url": url,
                            "timestamp": timestamp,
                            "page_title": page_title,
                            "browser_id": browser_id,
                            "party_type": party_type
                        }
                        entries.append(entry)
                        processed_cookies.add(cookie_key)
        
        try:
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            with open(f"data/{parsed_url}.json", "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Data saved: {len(entries)} cookie entries with request associations")
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
    
    def visit_website(self, website_index, url, wait_time=10, category='Unknown'):
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
            # if os.path.exists(data_file):
            #     try:
            #         with open(data_file, "r") as f:
            #             existing_data = json.load(f)
            #             cookies = existing_data.get("cookies", [])
            #         self.driver.delete_all_cookies()
                    
            #         current_domain = parsed_url.netloc
            #         for cookie in cookies:
            #             cookie_domain = cookie.get("domain", "")                        
            #             if cookie_domain:
            #                 cookie_domain_clean = cookie_domain.lstrip(".").lstrip("www.")
                            
            #                 domain_matches = (
            #                     cookie_domain_clean == current_domain or
            #                     current_domain == "." + cookie_domain_clean or
            #                     current_domain.startswith == ".www." + cookie_domain_clean or
            #                     current_domain.startswith == "www." + cookie_domain_clean
            #                 )

            #                 # print(current_domain, cookie_domain_clean, domain_matches)
                            
            #                 if not domain_matches:
            #                     self.logger.warning(f"Skipping cookie {cookie.get("name")} with domain {cookie_domain} for {current_domain}")
            #                     continue
                        
            #             cookie_copy = cookie.copy()
            #             for key in list(cookie_copy.keys()):
            #                 if key not in ["name", "value", "domain", "path", "expiry", "secure", "httpOnly"]:
            #                     del cookie_copy[key]
                        
            #             try:
            #                 self.driver.add_cookie(cookie_copy)
            #                 self.logger.info(f"Set cookie: {cookie.get("name")}")
            #             except Exception as e:
            #                 self.logger.warning(f"Could not set cookie {cookie.get("name")}: {e}")
                    
            #         self.logger.info(f"Set {len(cookies)} cookies from previous session")
                    
            #     except Exception as e:
            #         self.logger.error(f"Error setting cookies: {e}")
            
            # self.logger.info(f"Going to: {url} in 5s...")
            # time.sleep(2.11)
            # self.driver.get(url)
            
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            self.logger.info(f"Waiting for {wait_time} seconds...")
            # time.sleep(wait_time)
            comment = [""]
            input_received = threading.Event()

            def wait_for_input():
                self.logger.info("Enter a comment for this crawl (or press Enter to skip): ")
                comment[0] = input("> ")
                input_received.set()

            input_thread = threading.Thread(target=wait_for_input)
            input_thread.daemon = True
            input_thread.start()

            input_received.wait(timeout=wait_time)

            if not input_received.is_set():
                print() # Move to next line after timeout
                self.logger.info("No input received, proceeding without comment.")
                self.logger.info("Enter a comment to continue: ")
                input_thread.join()
            
            comment = comment[0]
            
            self.logger.info("Capturing data...")
            cookies = self._capture_all_cookies()
            requests = self._capture_network_requests()  
            self._save_data(profile_path, url, cookies, requests, profile_name)

            # Update masterfile.csv safely
            rows = []
            updated = False
            with open('masterfile.csv', 'r', newline='', encoding='utf-8') as mf:
                reader = csv.reader(mf)
                header = next(reader)
                if 'Region' not in header:
                    header.insert(2, 'Region')
                rows.append(header)
                for row in reader:
                    if 'Region' not in header and len(header) == 8:  # old header without Region
                        row.insert(2, '')  # insert empty Region
                    if len(row) > 1 and row[1] == url:
                        # Update existing row
                        row[2] = category  # Region
                        row[3] = self.driver.title
                        row[4] = "Success" if not comment else "Failed"
                        row[5] = str(len(cookies))
                        row[6] = str(len(requests))
                        row[7] = datetime.now().isoformat()
                        row[8] = comment
                        updated = True
                    rows.append(row)
            
            if not updated:
                # Append new row
                new_row = [str(website_index), url, category, self.driver.title, "Success" if not comment else "Failed", str(len(cookies)), str(len(requests)), datetime.now().isoformat(), comment]
                rows.append(new_row)
            
            with open('masterfile.csv', 'w', newline='', encoding='utf-8') as mf:
                writer = csv.writer(mf)
                writer.writerows(rows)
            
            # Remove from input file if success
            if not comment and category in ("EU", "USA"):
                # Determine source CSV by category
                source_csv = 'urls/EU_websites.csv' if category == 'EU' else 'urls/USA_websites.csv'
                domain_to_remove = urlparse(url).netloc.replace('www.', '')
                try:
                    # Read CSV and remove the domain
                    remaining_rows = []
                    with open(source_csv, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        fieldnames = reader.fieldnames or []
                        for row in reader:
                            if row.get('Domain', '').strip() != domain_to_remove:
                                remaining_rows.append(row)
                    # Write back without the removed domain
                    with open(source_csv, 'w', newline='', encoding='utf-8') as f:
                        if fieldnames:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            writer.writerows(remaining_rows)
                    self.logger.info(f"Removed {domain_to_remove} from {source_csv} after successful crawl")
                except Exception as rem_err:
                    self.logger.error(f"Error updating source list {source_csv}: {rem_err}")
            
            self.logger.info(f"Title: {self.driver.title}")
            self.logger.info(f"URL(last visited page/subpage): {self.driver.current_url}")
            self.logger.info(f"Cookies captured: {len(cookies)}")
            self.logger.info(f"Requests captured: {len(requests)}")
            
        except Exception as e:
            self.logger.error(f"Error visiting {url}: {e}")
            
            if self.driver:
                self.driver.quit()
                self.driver = None

            try:
                rows = []
                updated = False
                with open('masterfile.csv', 'r', newline='', encoding='utf-8') as mf:
                    reader = csv.reader(mf)
                    header = next(reader)
                    if 'Region' not in header:
                        header.insert(2, 'Region')
                    rows.append(header)
                    for row in reader:
                        if 'Region' not in header and len(header) == 8:
                            row.insert(2, '')
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
                    if 'Region' not in header:
                        new_row = [str(website_index), url, category, "", "Failed", "0", "0", datetime.now().isoformat(), "Connection timeout"]
                    else:
                        new_row = [str(website_index), url, category, "", "Failed", "0", "0", datetime.now().isoformat(), "Connection timeout"]
                    rows.append(new_row)
                
                with open('masterfile.csv', 'w', newline='', encoding='utf-8') as mf:
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
