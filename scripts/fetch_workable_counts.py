"""Fetch open-job counts from Workable (server-side; avoids browser CORS)."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from scripts.workable_apply_slug import extract_workable_apply_slug

YAML_PATH = Path("data/companies.yaml")
OUTPUT_PATH = Path("data/workable_counts.yaml")

# PLAN 1: Anti-Blocking Measures
DELAY_SEC = 2.0  # Slow and steady to avoid IP-based rate limiting
TIMEOUT_SEC = 25
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# The exact endpoint you confirmed
BASE_URL = "https://apply.workable.com/api/v1/accounts/{slug}/jobs/count"
QUERY = urllib.parse.urlencode({"location": "Greece"})


def fetch_count(slug: str) -> int | None:
    """Fetch the 'incountry' count for Greece from the verified endpoint."""
    url = f"{BASE_URL.format(slug=slug)}?{QUERY}"

    # Headers designed to look like a browser session
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,el;q=0.8",
        "Origin": "https://apply.workable.com",
        "Referer": f"https://apply.workable.com/{slug}/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.load(resp)
            # The 'incountry' key represents jobs matching our 'location=Greece' query
            count = data.get("incountry")
            if isinstance(count, (int, float)):
                return int(count)
    except Exception as e:
        print(f"warn: {slug} failed: {e}", file=sys.stderr)

    return None


def main() -> int:
    with YAML_PATH.open(encoding="utf-8") as f:
        companies = yaml.safe_load(f)

    # Extract unique slugs
    slugs = []
    seen = set()
    for c in companies or []:
        slug = extract_workable_apply_slug(c.get("careers_url"))
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    print(f"Updating {len(slugs)} Workable accounts...")
    accounts: dict[str, int | None] = {}

    for i, slug in enumerate(slugs):
        if i > 0:
            time.sleep(DELAY_SEC)

        count = fetch_count(slug)
        accounts[slug] = count
        print(
            f"[{i + 1}/{len(slugs)}] {slug}: {count if count is not None else 'FAILED'}"
        )

    # Prepare YAML output
    total_open = sum(n for n in accounts.values() if n is not None)
    output_data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metric": "incountry_greece",
        "accounts": accounts,
        "total_open": total_open,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write("# Generated Workable Counts\n")
        yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)

    print(f"\nDone! Total Greece Open Roles: {total_open}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
