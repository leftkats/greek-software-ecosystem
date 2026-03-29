"""Fetch open-job counts from Workable public endpoints.

Primary source is ``/count`` (fast). If ``/count`` appears geo-biased (for
example ``total > 0`` but ``incountry = 0``) or otherwise unusable, this
script falls back to Workable's public v3 jobs endpoint filtered by
``location.countryCode = GR``.
"""

from __future__ import annotations

import sys
import time
import os
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.workable_apply_slug import extract_workable_apply_slug

YAML_PATH = Path("data/companies.yaml")
OUTPUT_PATH = Path("data/workable_counts.yaml")

DELAY_BETWEEN_SLUGS_SEC = 2.25
TIMEOUT_SEC = (12, 30)
_RETRY_TOTAL = 5
_RETRY_BACKOFF_FACTOR = 1.5
_RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)

_COUNT_URL_CANDIDATES = (
    "https://apply.workable.com/api/v1/accounts/{slug}/jobs/count",
    "https://apply.workable.com/api/v1/accounts/{slug}/jobs/count?country=Greece",
    "https://apply.workable.com/api/v1/accounts/{slug}/jobs/count?country=GR",
)
_V3_JOBS_URL = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"
_V3_GR_LOCATION_FILTER = {"location": [{"countryCode": "GR"}]}
_ROBOTS_TXT_URL = "https://www.workable.com/robots.txt"
_ROBOTS_ENDPOINT_PROBES = (
    "https://apply.workable.com/api/v1/accounts/example/jobs/count",
    "https://apply.workable.com/api/v3/accounts/example/jobs",
)

_USER_AGENT = (
    "awesome-greek-tech-jobs/1.0 "
    "(+https://github.com/leftkats/awesome-greek-tech-jobs; "
    "python-requests; Greece job board snapshot)"
)
_VERBOSE = os.getenv("WORKABLE_VERBOSE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
        }
    )
    retry = Retry(
        total=_RETRY_TOTAL,
        connect=_RETRY_TOTAL,
        read=_RETRY_TOTAL,
        backoff_factor=_RETRY_BACKOFF_FACTOR,
        status_forcelist=_RETRY_STATUS_FORCELIST,
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _debug(msg: str) -> None:
    if _VERBOSE:
        print(msg, file=sys.stderr)


def _ensure_robots_allows_fetch(session: requests.Session) -> None:
    """Fail fast if workable.com robots.txt disallows endpoint probes."""
    try:
        resp = session.get(_ROBOTS_TXT_URL, timeout=TIMEOUT_SEC)
    except requests.RequestException as e:
        raise RuntimeError(f"robots.txt fetch failed: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"robots.txt fetch returned HTTP {resp.status_code}"
        )

    rp = RobotFileParser()
    rp.parse(resp.text.splitlines())
    for endpoint_url in _ROBOTS_ENDPOINT_PROBES:
        if not rp.can_fetch(_USER_AGENT, endpoint_url):
            raise RuntimeError(
                "robots.txt disallows endpoint probe: "
                f"{endpoint_url}"
            )
    print(f"robots.txt check passed ({_ROBOTS_TXT_URL})")


def _fetch_count_from_count_endpoints(
    session: requests.Session, slug: str, idx: int = 0, total: int = 0
) -> tuple[int | None, int | None, bool]:
    """Try /count variants first; skip geo-mismatched results and continue."""
    headers = {
        "Origin": "https://apply.workable.com",
        "Referer": f"https://apply.workable.com/{slug}/",
    }
    last_status: int | None = None
    saw_geo_mismatch = False

    for candidate in _COUNT_URL_CANDIDATES:
        url = candidate.format(slug=slug)
        try:
            resp = session.get(url, headers=headers, timeout=TIMEOUT_SEC)
        except requests.RequestException as e:
            _debug(f"/count request failed for {slug} ({url}) -> {e}")
            continue

        last_status = resp.status_code
        if resp.status_code != 200:
            _debug(
                f"/count HTTP {resp.status_code} for {slug} ({url}) -> "
                f"{resp.text[:200]}".strip()
            )
            continue

        try:
            data = resp.json()
        except ValueError:
            _debug(f"/count invalid JSON for {slug} ({url})")
            continue

        raw_total = data.get("total")
        raw_incountry = data.get("incountry")
        if not isinstance(raw_total, int) or not isinstance(raw_incountry, int):
            _debug(f"/count missing keys for {slug} ({url})")
            continue

        # If there are jobs but requester-geo "incountry" is 0, this endpoint is
        # likely not reflecting Greece for CI; mark and continue.
        if raw_total > 0 and raw_incountry == 0:
            saw_geo_mismatch = True
            _debug(
                f"/count geo mismatch for {slug} ({url}) total={raw_total} "
                "incountry=0"
            )
            continue

        return raw_incountry, resp.status_code, False

    return None, last_status, saw_geo_mismatch


def _fetch_count_from_v3_gr_location(
    session: requests.Session, slug: str
) -> tuple[int | None, int | None]:
    """Fallback using public v3 endpoint with explicit Greece location filter."""
    url = _V3_JOBS_URL.format(slug=slug)
    headers = {
        "Origin": "https://apply.workable.com",
        "Referer": f"https://apply.workable.com/{slug}/",
        "Content-Type": "application/json",
    }
    try:
        resp = session.post(
            url,
            headers=headers,
            json=_V3_GR_LOCATION_FILTER,
            timeout=TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        _debug(f"/v3 request failed for {slug} ({url}) -> {e}")
        return None, None

    if resp.status_code != 200:
        _debug(
            f"/v3 HTTP {resp.status_code} for {slug} ({url}) -> "
            f"{resp.text[:200]}".strip()
        )
        return None, resp.status_code

    try:
        data = resp.json()
    except ValueError:
        _debug(f"/v3 invalid JSON for {slug} ({url})")
        return None, resp.status_code

    raw_total = data.get("total")
    if not isinstance(raw_total, int):
        _debug(f"/v3 missing total for {slug} ({url})")
        return None, resp.status_code
    return raw_total, resp.status_code


def fetch_count(
    session: requests.Session, slug: str, idx: int = 0, total: int = 0
) -> int:
    """Fetch Greece count, using /count first then v3 GR fallback."""
    prefix = f"[{idx}/{total}] {slug}"
    count_value, count_status, saw_geo_mismatch = _fetch_count_from_count_endpoints(
        session, slug, idx=idx, total=total
    )
    if isinstance(count_value, int):
        print(f"{prefix}: /count HTTP {count_status or 200} -> {count_value}")
        return count_value

    v3_value, v3_status = _fetch_count_from_v3_gr_location(session, slug)
    if isinstance(v3_value, int):
        source = "/v3(location=GR)"
        if saw_geo_mismatch:
            source = "/v3(location=GR) fallback-from-geo-mismatch"
        print(f"{prefix}: {source} HTTP {v3_status or 200} -> {v3_value}")
        return v3_value

    print(
        f"{prefix}: /count HTTP {count_status or 'ERR'}, "
        f"/v3 HTTP {v3_status or 'ERR'} -> 0"
    )
    return 0


def main() -> int:
    session = _build_session()
    try:
        _ensure_robots_allows_fetch(session)
    except RuntimeError as e:
        print(f"Workable fetch aborted: {e}", file=sys.stderr)
        return 2

    with YAML_PATH.open(encoding="utf-8") as f:
        companies = yaml.safe_load(f)

    slugs: list[str] = []
    seen: set[str] = set()
    for c in companies or []:
        slug = extract_workable_apply_slug(c.get("careers_url"))
        if slug and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    accounts: dict[str, int] = {}

    print(f"Fetching {len(slugs)} Workable accounts…")
    for i, slug in enumerate(slugs, 1):
        if i > 1:
            time.sleep(DELAY_BETWEEN_SLUGS_SEC)
        accounts[slug] = fetch_count(session, slug, idx=i, total=len(slugs))

    total_open = sum(accounts.values())
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metric": "greece_country_code_gr",
        "accounts": accounts,
        "total_open": total_open,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write(
            "# Workable Greece counts from public /count + /v3 jobs endpoints "
            "(generated by scripts/fetch_workable_counts)\n"
        )
        yaml.dump(
            out,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )
    print(f"Wrote {OUTPUT_PATH} ({len(slugs)} accounts, total_open={total_open})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
