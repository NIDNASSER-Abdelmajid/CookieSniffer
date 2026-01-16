import os
import json
import argparse
import glob
import pandas as pd
import tld


def load_cookie_data(input_path):
    """Load cookie/request data from a json file or a folder containing data.json."""
    if os.path.isdir(input_path):
        input_file = os.path.join(input_path, "data.json")
    else:
        input_file = input_path

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_cookie_data(cookie_data):
    """Normalize cookie/request data to a list of flat rows."""
    expanded_rows = []

    # Case 1: dictionary input (handles both legacy cookies+requests and already-flattened cookie records)
    if isinstance(cookie_data, dict):
        cookies = cookie_data.get("cookies", [])

        # If cookies are already flattened/enriched (crawler's per-cookie records), adapt directly
        if (
            cookies
            and isinstance(cookies, list)
            and isinstance(cookies[0], dict)
            and ("cookie_name" in cookies[0] or "name" in cookies[0])
        ):
            for entry in cookies:
                # Prefer the standardized flattened keys, fall back to legacy keys where present
                cookie_name = entry.get("cookie_name") or entry.get("name")
                cookie_value = entry.get("cookie_value") or entry.get("value")
                cookie_domain = entry.get("cookie_domain") or entry.get("domain")
                cookie_path = entry.get("cookie_path") or entry.get("path")
                cookie_secure = (
                    entry.get("cookie_secure")
                    if "cookie_secure" in entry
                    else entry.get("secure")
                )
                cookie_httpOnly = (
                    entry.get("cookie_httpOnly")
                    if "cookie_httpOnly" in entry
                    else entry.get("httpOnly")
                )
                cookie_expires = (
                    entry.get("cookie_expires")
                    or entry.get("expiry")
                    or entry.get("expires")
                )

                request_url = entry.get("request_url") or (
                    entry.get("request") or {}
                ).get("url")
                request_method = entry.get("request_method") or (
                    entry.get("request") or {}
                ).get("method")
                request_body = entry.get("request_body") or (
                    entry.get("request") or {}
                ).get("body")
                request_headers = entry.get("request_headers") or (
                    entry.get("request") or {}
                ).get("headers")
                response_status = entry.get("response_status_code") or (
                    entry.get("response") or {}
                ).get("status_code")
                response_headers = entry.get("response_headers") or (
                    entry.get("response") or {}
                ).get("headers")
                request_timestamp = entry.get("request_timestamp") or entry.get(
                    "timestamp"
                )

                expanded_rows.append(
                    {
                        "cookie_name": cookie_name,
                        "cookie_value": cookie_value,
                        "cookie_domain": cookie_domain,
                        "cookie_path": cookie_path,
                        "cookie_secure": cookie_secure,
                        "cookie_expires": cookie_expires,
                        "cookie_httpOnly": cookie_httpOnly,
                        "request_url": request_url,
                        "request_method": request_method,
                        "request_body": request_body,
                        "request_headers": request_headers,
                        "response_status_code": response_status,
                        "response_headers": response_headers,
                        "request_timestamp": request_timestamp,
                        "source_url": entry.get("source_url")
                        or cookie_data.get("source_url")
                        or cookie_data.get("url"),
                        "timestamp": entry.get("timestamp")
                        or cookie_data.get("crawl_timestamp")
                        or cookie_data.get("timestamp"),
                        "page_title": entry.get("page_title")
                        or cookie_data.get("page_title"),
                        "browser_id": entry.get("browser_id")
                        or cookie_data.get("browser_id", ""),
                        "party_type": entry.get("party_type", "unknown"),
                    }
                )

            return expanded_rows

        # Legacy structure: cookies + requests (support both "requests" and "network_requests")
        requests = cookie_data.get("requests", []) or cookie_data.get(
            "network_requests", []
        )

        try:
            source_url_tld = tld.get_tld(cookie_data.get("url", ""))
        except Exception:
            source_url_tld = None

        for cookie in cookies:
            cookie_domain_raw = cookie.get("domain", "")
            cookie_domain = "http://" + cookie_domain_raw

            try:
                cookie_domain_tld = tld.get_tld(cookie_domain)
            except tld.exceptions.TldBadUrl:
                print(f"Skipping invalid cookie domain: {cookie_domain_raw}")
                continue

            party_type = (
                "First-party"
                if source_url_tld and cookie_domain_tld == source_url_tld
                else "Third-party"
            )

            for request in requests:
                # normalize request/response shapes
                if (
                    isinstance(request, dict)
                    and "request" in request
                    and "response" in request
                ):
                    req = request.get("request", {}) or {}
                    resp = request.get("response", {}) or {}
                    req_ts = request.get("timestamp")
                else:
                    req = request or {}
                    resp = (
                        request.get("response") if isinstance(request, dict) else None
                    ) or {}
                    req_ts = (
                        request.get("timestamp") if isinstance(request, dict) else None
                    )

                cookie_expires_val = cookie.get("expires") or cookie.get("expiry")
                expanded_rows.append(
                    {
                        "cookie_name": cookie.get("name"),
                        "cookie_value": cookie.get("value"),
                        "cookie_domain": cookie.get("domain"),
                        "cookie_path": cookie.get("path"),
                        "cookie_secure": cookie.get("secure"),
                        "cookie_expires": cookie_expires_val,
                        "cookie_httpOnly": cookie.get("httpOnly"),
                        "request_url": req.get("url"),
                        "request_method": req.get("method"),
                        "request_body": req.get("body"),
                        "request_headers": req.get("headers"),
                        "response_status_code": resp.get("status_code"),
                        "response_headers": resp.get("headers"),
                        "request_timestamp": req_ts,
                        "source_url": cookie_data.get("url"),
                        "timestamp": cookie_data.get("timestamp"),
                        "page_title": cookie_data.get("page_title"),
                        "browser_id": cookie_data.get("browser_id", ""),
                        "party_type": party_type,
                    }
                )

    # Case 2: flattened list of entries (already expanded by crawler)
    elif isinstance(cookie_data, list):
        for entry in cookie_data:
            cookie_domain = entry.get("cookie_domain", "")
            source_url = entry.get("source_url", "")

            party_type_tld = "Unknown"
            if cookie_domain and source_url:
                try:
                    c_dom = cookie_domain.lstrip(".")
                    if not c_dom.startswith("http"):
                        c_dom = "http://" + c_dom
                    cookie_tld = tld.get_tld(c_dom, fail_silently=True)
                    source_tld = tld.get_tld(source_url, fail_silently=True)
                    if cookie_tld and source_tld:
                        party_type_tld = (
                            "First-party" if cookie_tld == source_tld else "Third-party"
                        )
                except Exception:
                    party_type_tld = "Error"

            new_entry = dict(entry)
            new_entry.setdefault("party_type", entry.get("party_type", ""))
            new_entry["party_type_tld"] = party_type_tld
            expanded_rows.append(new_entry)

    else:
        raise ValueError("Unsupported input JSON structure")

    return expanded_rows


def process_json_to_csv(input_path, output_path):
    cookie_data = load_cookie_data(input_path)
    expanded_rows = expand_cookie_data(cookie_data)

    # Sanitize any dict/list fields to strings so pandas can deduplicate reliably
    for r in expanded_rows:
        for k in (
            "request_headers",
            "response_headers",
            "request_body",
            "response_body",
        ):
            v = r.get(k)
            if isinstance(v, (dict, list)):
                try:
                    r[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    r[k] = str(v)

    expanded_df = pd.DataFrame(expanded_rows)
    expanded_df = expanded_df.drop_duplicates()

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    expanded_df.to_csv(output_path, index=False)

    print(f"Data has been cleaned, categorized, and saved to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="GDPR Data Analysis")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-i",
        "--input",
        help="Path to a single input json file or folder containing data.json",
    )
    group.add_argument(
        "-d",
        "--input-dir",
        help="Directory containing multiple JSON files to aggregate",
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Path to output CSV file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.input_dir:
        json_files = sorted(glob.glob(os.path.join(args.input_dir, "*.json")))
        if not json_files:
            raise FileNotFoundError(
                f"No JSON files found in directory: {args.input_dir}"
            )

        all_rows = []
        for jf in json_files:
            try:
                cookie_data = load_cookie_data(jf)
                all_rows.extend(expand_cookie_data(cookie_data))
            except Exception as e:
                print(f"Skipping {jf}: {e}")

        df = pd.DataFrame(all_rows)
        df = df.drop_duplicates()
        df.to_csv(args.output, index=False)
        print(
            f"Aggregated {len(df)} rows from {len(json_files)} files into {args.output}"
        )
    else:
        process_json_to_csv(args.input, args.output)


if __name__ == "__main__":
    main()
