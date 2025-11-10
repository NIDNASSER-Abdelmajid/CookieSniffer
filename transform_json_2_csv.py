import os
import json
import csv
import argparse
from pathlib import Path


DEFAULT_ORDER = [
	"cookie_name",
	"cookie_value",
	"cookie_domain",
	"cookie_path",
	"cookie_secure",
	"cookie_httpOnly",
	"request_url",
	"request_method",
	"request_timestamp",
	"source_url",
	"timestamp",
	"page_title",
	"browser_id",
	"party_type",
]


def collect_json_entries(data_dir: str):
	
	all_entries = []
	all_keys = set()

	data_path = Path(data_dir)
	if not data_path.exists() or not data_path.is_dir():
		raise FileNotFoundError(f"Data folder not found: {data_dir}")

	for p in sorted(data_path.rglob('*.json')):
		try:
			with p.open('r', encoding='utf-8') as f:
				obj = json.load(f)
		except Exception as e:
			print(f"Skipping {p}: failed to load JSON ({e})")
			continue

		entries = []
		if isinstance(obj, list):
			entries = obj
		elif isinstance(obj, dict):
			if 'cookies' in obj and isinstance(obj['cookies'], list):
				entries = obj['cookies']
			else:
				entries = [obj]

		for e in entries:
			if not isinstance(e, dict):
				continue
			all_entries.append(e)
			all_keys.update(e.keys())

	return all_entries, all_keys


def write_csv(entries, keys, out_file: str):
	ordered_keys = [k for k in DEFAULT_ORDER if k in keys]
	other_keys = [k for k in sorted(keys) if k not in ordered_keys]
	header = ordered_keys + other_keys

	out_path = Path(out_file)
	out_path.parent.mkdir(parents=True, exist_ok=True)

	with out_path.open('w', newline='', encoding='utf-8') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=header, extrasaction='ignore')
		writer.writeheader()
		for row in entries:
			normalized = {}
			for k in header:
				v = row.get(k, '')
				if isinstance(v, bool):
					v = 'true' if v else 'false'
				normalized[k] = v
			writer.writerow(normalized)


def main():
	parser = argparse.ArgumentParser(description='Aggregate cookie JSON files into a CSV')
	parser.add_argument('--data-dir', '-d', default='data', help='Directory containing JSON files (default: data)')
	parser.add_argument('--out', '-o', default='aggregated_cookies.csv', help='Output CSV file path')
	args = parser.parse_args()

	entries, keys = collect_json_entries(args.data_dir)
	print(f"Found {len(entries)} entries across JSON files. Columns detected: {len(keys)}")

	if not entries:
		print("No entries found, exiting.")
		return

	write_csv(entries, keys, args.out)
	print(f"Wrote {len(entries)} rows to {args.out}")


if __name__ == '__main__':
	main()
