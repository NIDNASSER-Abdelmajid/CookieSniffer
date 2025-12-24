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

    # Case 1: legacy structure with cookies/requests keys
    if isinstance(cookie_data, dict):
        cookies = cookie_data.get("cookies", [])
        requests = cookie_data.get("requests", [])

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
                expanded_rows.append(
                    {
                        "cookie_name": cookie.get("name"),
                        "cookie_value": cookie.get("value"),
                        "cookie_domain": cookie.get("domain"),
                        "cookie_path": cookie.get("path"),
                        "cookie_secure": cookie.get("secure"),
                        "cookie_expires": cookie.get("expires"),
                        "cookie_httpOnly": cookie.get("httpOnly"),
                        "request_url": request.get("url"),
                        "request_method": request.get("method"),
                        "request_timestamp": request.get("timestamp"),
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

    expanded_df = pd.DataFrame(expanded_rows)
    expanded_df = expanded_df.drop_duplicates()
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
