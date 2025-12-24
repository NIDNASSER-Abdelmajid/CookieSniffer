import os
import json
import pandas as pd
import tld  


def process_json_to_csv(folder_path, output_path):

    data_file_path = os.path.join(folder_path, "data.json")


    if not os.path.exists(data_file_path):
        print(f"No data.json found in {folder_path}, skipping...")
        return


    try:
        with open(data_file_path, "r", encoding="utf-8") as f:
            cookie_data = json.load(f)
    except Exception as e:
        print(f"Error reading {data_file_path}: {e}")
        return


    cookies = cookie_data.get("cookies", [])
    requests = cookie_data.get("requests", [])


    source_url_tld = tld.get_tld(cookie_data.get("url", ""))


    expanded_rows = []

    for cookie in cookies:

        cookie_domain = "http://" + cookie.get("domain", "")

        try:

            cookie_domain_tld = tld.get_tld(cookie_domain)
        except tld.exceptions.TldBadUrl:
            print(f"Skipping invalid cookie domain: {cookie.get('domain', '')}")
            continue

        # Classification cookie as first-party or third-party
        if cookie_domain_tld == source_url_tld:
            party_type = "First-party"
        else:
            party_type = "Third-party"

        for request in requests:
            expanded_rows.append({
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
                "browser_id": cookie_data.get("browser_id", ""),  # Add browser_id from JSON
                "party_type": party_type  # Categorize cookies based on the TLD comparison
            })


    expanded_df = pd.DataFrame(expanded_rows)


    expanded_df = expanded_df.drop_duplicates()


    expanded_df.to_csv(output_path, index=False)

    print("Data has been cleaned, categorized, and saved successfully!")


# Example usage
folder_path = r'D:\Data\DP16and18\profiles\n_tv_de'
output_path = r'D:\Data\DP16and18\cleaned_data.csv'
process_json_to_csv(folder_path, output_path)
