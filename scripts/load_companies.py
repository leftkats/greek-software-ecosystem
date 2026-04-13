"""Load company records from per-file YAML under ``_data/companies/``."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

DATA_DIR = Path("_data")
COMPANIES_DIR = DATA_DIR / "companies"
QUERIES_YAML = DATA_DIR / "queries.yaml"
WORKABLE_COUNTS_YAML = DATA_DIR / "workable_counts.yaml"


def slugify_filename(name: str) -> str:
    """ASCII filesystem slug from a display name (for migration / tooling)."""
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "company"


def load_companies() -> list[dict]:
    """Load all companies: one YAML mapping per file in ``_data/companies``."""
    if not COMPANIES_DIR.is_dir():
        raise FileNotFoundError(
            f"Missing companies directory: {COMPANIES_DIR}"
        )
    paths = sorted(COMPANIES_DIR.glob("*.yaml"))
    if not paths:
        raise ValueError(f"No company YAML files under {COMPANIES_DIR}")
    companies: list[dict] = []
    for path in paths:
        with path.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if doc is None:
            raise ValueError(f"Empty YAML: {path}")
        if not isinstance(doc, dict):
            raise ValueError(
                f"{path}: expected a mapping (single company), "
                f"got {type(doc).__name__}"
            )
        if "name" not in doc:
            raise ValueError(f"{path}: missing required key 'name'")
        companies.append(doc)
    return companies
