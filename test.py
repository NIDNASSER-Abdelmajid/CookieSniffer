# Get network requests and responses from "https://zoom.us" and associate cookies with requests
from selenium import webdriver
import json
from datetime import datetime
import csv

options = webdriver.ChromeOptions()
# options.add_argument('--headless=new')
# Enable performance logging
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(options=options)

# Enable network monitoring
driver.execute_cdp_cmd("Network.enable", {})

url = 'https://www.fcbarcelona.com/'
driver.get(url)

# Wait a bit for network activity
import time
time.sleep(15)

# Get performance logs which contain network events
logs = driver.get_log("performance")

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
                current_cookies = driver.get_cookies()
                cookies_before_request[request_id] = {f"{c['name']}:{c.get('domain', '')}": c for c in current_cookies}
            except:
                cookies_before_request[request_id] = {}

            requests.append({
                "id": request_id,
                "url": request["url"],
                "method": request["method"],
                "timestamp": datetime.fromtimestamp(log_entry["timestamp"] / 1000).isoformat(),
                "headers": request.get("headers", {}),
                "cookies_set": []  # Will be populated by comparing before/after
            })

        elif method == "Network.loadingFinished":
            request_id = params["requestId"]

            # Capture cookies after this request finished
            try:
                current_cookies = driver.get_cookies()
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
                                new_cookies.append(cookie_data)

                        if new_cookies:
                            req["cookies_set"] = new_cookies
                        break

            except Exception as e:
                print(f"Error checking cookies for request {request_id}: {e}")

    except Exception as e:
        print(f"Error processing log entry: {e}")
        continue

# Get final cookies (including any that weren't associated with requests)
try:
    final_cookies = driver.get_cookies()
    # Also try to get CDP cookies
    try:
        cdp_cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
        # Merge cookies, avoiding duplicates
        seen = set()
        all_cookies = []
        for cookie in final_cookies + cdp_cookies:
            key = (cookie.get("name"), cookie.get("domain"), cookie.get("path"))
            if key not in seen:
                seen.add(key)
                all_cookies.append(cookie)
        final_cookies = all_cookies
    except Exception as e:
        print(f"Could not get CDP cookies: {e}")
except Exception as e:
    print(f"Error getting final cookies: {e}")
    final_cookies = []

# Create TSV output associating cookies with requests
source_domain = url.replace("https://", "").replace("http://", "").split("/")[0]
page_title = driver.title
timestamp = datetime.now().isoformat()
browser_id = "test_browser"

# Header
header = ["cookie_name", "cookie_value", "cookie_domain", "cookie_path", "cookie_secure", "cookie_httpOnly",
          "request_url", "request_method", "request_timestamp", "source_url", "timestamp", "page_title", "browser_id", "party_type"]

# Collect all cookie entries - ONLY cookies with associated requests
cookie_entries = []

# Create a map of all cookies for matching
all_cookies_map = {}
for cookie in final_cookies:
    cookie_name = cookie.get("name", "")
    cookie_domain = cookie.get("domain", "")
    if cookie_name:
        # Try multiple keys to match cookies with different domain formats
        keys = [
            f"{cookie_name}:{cookie_domain}",
            f"{cookie_name}:{cookie_domain.lstrip('.')}",
            f"{cookie_name}:.{cookie_domain.lstrip('.')}"
        ]
        for key in keys:
            all_cookies_map[key] = cookie

# Process requests and match with cookies
for request in requests:
    request_url = request["url"]
    request_domain = request_url.split("/")[2] if "://" in request_url else ""
    
    # Check if this request set any cookies (from before/after comparison)
    if request.get("cookies_set"):
        for cookie in request["cookies_set"]:
            cookie_name = cookie.get("name", "")
            cookie_value = cookie.get("value", "")
            cookie_domain = cookie.get("domain", "")
            cookie_path = cookie.get("path", "/")
            cookie_secure = cookie.get("secure", False)
            cookie_httpOnly = cookie.get("httpOnly", False)

            # Determine party_type
            if cookie_domain:
                cookie_domain_clean = cookie_domain.lstrip(".")
                if source_domain.endswith(cookie_domain_clean) or cookie_domain_clean == source_domain:
                    party_type = "first-party"
                else:
                    party_type = "third-party"
            else:
                party_type = "unknown"

            entry = [
                cookie_name, cookie_value, cookie_domain, cookie_path, str(cookie_secure), str(cookie_httpOnly),
                request["url"], request["method"], request["timestamp"], url, timestamp, page_title, browser_id, party_type
            ]
            cookie_entries.append(entry)
    else:
        # Try to match existing cookies with this request based on domain matching
        for cookie in final_cookies:
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
            already_processed = any(
                e[0] == cookie_name and e[2] == cookie_domain 
                for e in cookie_entries
            )
            
            if matches_domain and not already_processed:
                # Determine party_type
                if cookie_domain:
                    if source_domain.endswith(cookie_domain_clean) or cookie_domain_clean == source_domain:
                        party_type = "first-party"
                    else:
                        party_type = "third-party"
                else:
                    party_type = "unknown"

                entry = [
                    cookie_name, cookie_value, cookie_domain, cookie_path, str(cookie_secure), str(cookie_httpOnly),
                    request["url"], request["method"], request["timestamp"], url, timestamp, page_title, browser_id, party_type
                ]
                cookie_entries.append(entry)

# Save to TSV file
with open('cookies.tsv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(header)
    writer.writerows(cookie_entries)

print(f"Processed {len(requests)} requests")
print(f"Generated {len(cookie_entries)} cookie entries")
print("Cookies saved to cookies.tsv")

# Also save network logs as before
network_events = []
for log_entry in logs:
    try:
        log_message = json.loads(log_entry["message"])["message"]
        method = log_message["method"]

        if method in ["Network.requestWillBeSent", "Network.responseReceived"]:
            event_data = {
                "timestamp": datetime.fromtimestamp(log_entry["timestamp"] / 1000).isoformat(),
                "event_type": method,
                "request_id": log_message["params"].get("requestId"),
                "data": log_message["params"]
            }
            network_events.append(event_data)
    except Exception as e:
        continue

with open('network_logs.json', 'w') as f:
    json.dump(network_events, f, indent=2)

print(f"Captured {len(network_events)} network events (requests and responses)")
print("Events saved to network_logs.json")

driver.quit()