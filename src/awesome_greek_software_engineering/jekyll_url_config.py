"""Emit a small Jekyll config fragment: url + baseurl from readme.yaml.

Reads ``live_url`` from ``readme.yaml``. Used as:
``jekyll build --config _config.yml,_url.yml``
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
README_YAML = _REPO_ROOT / "readme.yaml"


def main() -> int:
    url = "https://leftkats.github.io"
    baseurl = "/awesome-greek-software-engineering"
    if README_YAML.is_file():
        try:
            with README_YAML.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            data = {}
        live = (data.get("live_url") or "").strip().rstrip("/")
        if live:
            p = urlparse(live)
            if p.scheme and p.netloc:
                url = f"{p.scheme}://{p.netloc}"
                path = (p.path or "").rstrip("/")
                baseurl = path if path else ""
    sys.stdout.write(f'url: "{url}"\n')
    sys.stdout.write(f'baseurl: "{baseurl}"\n')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
