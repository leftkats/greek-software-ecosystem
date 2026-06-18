"""Build static ``index.html`` from YAML, Workable snapshot, and Jinja2.

Data flow
---------
1. ``_data/companies/*.yaml`` — one file per company (sectors, locations, careers URLs, policies).
   Coarse **industries** (≤20, for the dropdown) are derived from ``sectors`` via
   ``greek_software_ecosystem.industry_clusters`` at build time. **Locations** are Greece-focused:
   known non-Greek place names are dropped (see ``_NON_GREEK_LOCATIONS_CASEFOLD``),
   and common Greek spelling variants are canonicalised in ``normalize_location``.
2. This module normalises rows and sets ``workable_slug`` for apply.workable.com URLs
   (see ``greek_software_ecosystem.workable_apply_slug``).
3. ``_data/workable_counts.yaml`` — Greece ``incountry`` counts per slug, from
   ``python -m greek_software_ecosystem.fetch_workable_counts`` (server-side; avoids browser CORS).
   Embedded in the page for badges, header totals, sort, and hiring-only filter.
4. ``templates/index_template.html`` → ``index.html`` (hub); ``page_job_search_combined.html`` →
   ``job-search.html`` (directory + Workable);    ``page_resources.html`` → ``resources.html``
   (queries + open Greek data as one searchable table);    ``page_workspaces.html`` → ``workspaces.html`` (café YAML);
   ``page_open_source.html`` → ``open-source.html`` (open-source YAML + stars/forks from
   ``_data/open_source_github_stats.yaml``; each row includes a precomputed ``data-search`` blob);
   ``employers.html`` is a short redirect.

Run
---
* ``uv run python -m greek_software_ecosystem.generate_index`` — render (use existing snapshot YAML if any).
* ``uv run python -m greek_software_ecosystem.generate_index --fetch-workable`` — fetch then render.

CI: ``.github/workflows/sync-on-main-merge.yaml`` runs on ``main`` (push, weekly,
manual): refreshes ``_data/workable_counts.yaml`` on schedule, regenerates readme /
engineering-hubs, runs this script, then **force-pushes** only the static bundle
(HTML and page assets) to branch ``live``; ``sitemap.xml`` / ``robots.txt`` are written here
(``greek_software_site.sitemap_robots``), gitignored on ``main``, and copied into ``_site/`` by CI.
Paths align with ``greek_software_ecosystem.fetch_workable_counts``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml
from collections import Counter

from jinja2 import Environment, FileSystemLoader

from greek_software_ecosystem.industry_clusters import (
    industries_for_sectors,
    sort_industries_for_filter,
)
from greek_software_ecosystem.generate_readme import (
    build_remote_cafe_resources_markdown,
)
from greek_software_ecosystem.github_stars import (
    format_compact_github_count,
    load_open_source_github_stats_yaml,
    parse_github_repo_url,
)
from greek_software_ecosystem.load_companies import (
    QUERIES_YAML,
    WORKABLE_COUNTS_YAML,
    load_companies,
)
from greek_software_ecosystem.podcast_urls import podcast_summary_table_html
from greek_software_site.markdown_html import markdown_to_html
from greek_software_site.sitemap_robots import write_robots_txt, write_sitemap_xml
from greek_software_ecosystem.workable_apply_slug import extract_workable_apply_slug

_PKG_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = _PKG_ROOT / "templates"

# --- Configuration (aligned with fetch_workable_counts.py) ---
OUTPUT_INDEX = "index.html"
OUTPUT_EMPLOYERS = "employers.html"
OUTPUT_JOB_SEARCH = "job-search.html"
OUTPUT_RESOURCES = "resources.html"
OUTPUT_PODCASTS = "podcasts.html"
OUTPUT_WORKSPACES = "workspaces.html"
OUTPUT_OPEN_SOURCE = "open-source.html"
ITEMS_PER_PAGE = 20
WORKABLE_SNAPSHOT_PATH = WORKABLE_COUNTS_YAML
PODCASTS_YAML = Path("_data/podcasts.yaml")
CAFE_RESOURCES_YAML = Path("_data/cafe_resources.yaml")
OPEN_GREEK_DATA_YAML = Path("_data/open_greek_data.yaml")
OPEN_SOURCE_PROJECTS_YAML = Path("_data/open_source_projects.yaml")
OPEN_SOURCE_GITHUB_STATS_YAML = Path("_data/open_source_github_stats.yaml")

# Hero / first-card blurbs (plain text, ≤ this length after normalisation).
FIRST_CARD_DESC_MAX = 130

# ``open-source.html`` hero (YAML ``intro`` still feeds ``just readme`` / docs only).
OSP_HERO_SUBTITLE = "Greek-related GitHub repos sorted by stars (counts at build). "

# Per-page ``meta name="keywords"`` (unique, topical; home keeps ``load_site_meta`` defaults).
_SEO_KW_JOB = (
    "Greek tech jobs, software engineer Greece, IT employer directory, Workable jobs Greece, "
    "remote work Greece tech, hybrid jobs Athens, developer careers Thessaloniki"
)
_SEO_KW_RES = (
    "Greek tech job boards, open data Greece, GitHub awesome lists, startup resources Greece, "
    "engineering links Greece"
)
_SEO_KW_POD = "Greek tech podcasts, startup podcast Greece, software engineering Greece, IT careers audio"
_SEO_KW_WS = "laptop friendly cafes Greece, remote work cafes Athens, coworking Greece, workspace YAML Greece"
_SEO_KW_OSP = (
    "Greek open source GitHub, Greece OSS repositories, Greek developers open source, "
    "committers.top Greece, civic tech Greece"
)

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

_README_YAML = Path("_data/readme.yaml")


def page_canonical_url(site_origin: str, relpath: str) -> str:
    """Absolute canonical URL for a top-level HTML page (Jekyll ``permalink: /:stem/``)."""
    o = site_origin.rstrip("/")
    stem = Path(relpath).stem
    if stem == "index":
        return f"{o}/"
    return f"{o}/{stem}/"


def _jekyll_front_matter(filename: str) -> str:
    """YAML front matter so Jekyll applies ``permalink`` (clean URLs under ``jekyll-pages/``)."""
    stem = Path(filename).stem
    if stem == "index":
        return "---\npermalink: /\n---\n"
    return f"---\npermalink: /{stem}/\n---\n"


def write_jekyll_html(path: Path, html: str, *, local_flat: bool = False) -> None:
    """Write HTML; prepend Jekyll front matter unless ``local_flat`` (browser / static server preview)."""
    if local_flat:
        path.write_text(html, encoding="utf-8")
    else:
        path.write_text(_jekyll_front_matter(path.name) + html, encoding="utf-8")


def navigation_hrefs(site_baseurl: str, *, local_flat: bool) -> dict[str, str]:
    """Internal page targets: GitHub Pages paths, or sibling ``*.html`` for local preview.

    Local preview uses **relative** paths (no leading ``/``) so nav and assets work when the site is
    served under a subpath (e.g. Live Server), from ``python -m http.server`` at the repo root, or
    via ``file://`` — root-absolute ``/…`` URLs break in those cases.
    """
    if local_flat:
        return {
            "home": "index.html",
            "job_search": "job-search.html",
            "resources": "resources.html",
            "podcasts": "podcasts.html",
            "open_source": "open-source.html",
            "workspaces": "workspaces.html",
            "job_search_employers": "job-search.html#employers",
        }
    b = (site_baseurl or "").rstrip("/")

    def seg(name: str) -> str:
        return f"{b}/{name}/" if b else f"/{name}/"

    return {
        "home": f"{b}/" if b else "/",
        "job_search": seg("job-search"),
        "resources": seg("resources"),
        "podcasts": seg("podcasts"),
        "open_source": seg("open-source"),
        "workspaces": seg("workspaces"),
        "job_search_employers": seg("job-search") + "#employers",
    }


def assets_base(site_baseurl: str, *, local_flat: bool) -> str:
    """Prefix for static assets (relative ``assets`` locally; ``baseurl``-aware on GH Pages)."""
    if local_flat:
        return "assets"
    b = (site_baseurl or "").rstrip("/")
    return f"{b}/assets" if b else "/assets"


def apply_site_navigation_context(meta: dict, *, local_flat: bool) -> dict:
    """Add ``nav``, ``assets_base``, ``local_preview``; clear ``site_baseurl`` when previewing locally."""
    out = dict(meta)
    out["local_preview"] = local_flat
    if local_flat:
        out["site_baseurl"] = ""
    out["nav"] = navigation_hrefs(out["site_baseurl"], local_flat=local_flat)
    out["assets_base"] = assets_base(out["site_baseurl"], local_flat=local_flat)
    return out


def _truncate_first_card_description(
    s: str, max_chars: int = FIRST_CARD_DESC_MAX
) -> str:
    """Short hero blurb; prefers a word boundary before ``max_chars``."""
    s = " ".join(s.split())
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars * 2 // 3:
        cut = s[:last_space]
    else:
        cut = s[: max_chars - 1] + "…"
        return cut
    return cut.rstrip(" ,.;:") + "…"


def load_site_meta() -> dict:
    """SEO, Open Graph / Twitter, canonical URL (aligned with ``_data/readme.yaml``)."""
    origin = "https://leftkats.github.io/greek-software-ecosystem"
    title = "Greek Software Ecosystem"
    desc = (
        "A community-maintained list of remote-first employers hiring for technology roles in Greece — "
        "sectors, careers, and weekly Workable snapshots."
    )
    repo_slug = "leftkats/greek-software-ecosystem"
    if _README_YAML.is_file():
        try:
            with _README_YAML.open(encoding="utf-8") as f:
                rd = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            rd = {}
        else:
            site_title = rd.get("title")
            if isinstance(site_title, str) and site_title.strip():
                title = site_title.strip()
            live = rd.get("live_url")
            if isinstance(live, str) and live.strip():
                origin = live.strip().rstrip("/")
            long_desc = rd.get("description")
            if isinstance(long_desc, str) and long_desc.strip():
                desc = " ".join(long_desc.split()).replace("**", "")
            rs = rd.get("repo")
            if isinstance(rs, str) and rs.strip():
                repo_slug = rs.strip()
    if len(desc) > 200:
        desc = desc[:197].rstrip() + "…"
    og_image_url = f"{origin}/assets/og-image.png"
    canonical_url = f"{origin}/"
    sitemap_url = f"{origin}/sitemap.xml"
    github_repo_url = f"https://github.com/{repo_slug}"
    document_title = f"{title} | Greece software engineering & careers"
    if len(document_title) > 60:
        document_title = f"{title} | Greek software engineering careers"
    seo_keywords = (
        "Greece software engineering jobs, software engineer Greece, IT careers Athens, "
        "remote work Greece, tech startups Greece, developer jobs Greece, "
        "engineering jobs Thessaloniki, hiring Greece"
    )
    site_baseurl = ""
    if origin.startswith(("http://", "https://")):
        site_baseurl = (urlparse(origin).path or "").rstrip("/")
    return {
        "canonical_url": canonical_url,
        "site_origin": origin,
        "site_baseurl": site_baseurl,
        "sitemap_url": sitemap_url,
        "document_title": document_title,
        "og_description": desc,
        "og_image_url": og_image_url,
        "og_image_alt": f"{title} — preview image",
        "og_site_name": title,
        "github_repo_url": github_repo_url,
        "seo_keywords": seo_keywords,
    }


def build_schema_home_hub(
    *,
    canonical_url: str,
    origin: str,
    name: str,
    description: str,
    document_title: str,
    github_repo_url: str,
) -> str:
    """JSON-LD for the home hub: WebSite, Organization, WebPage (no employer list)."""
    website_id = f"{origin}/#website"
    org_id = f"{origin}/#organization"
    employers_search = f"{origin}/job-search/?q={{search_term_string}}"
    graph: list[dict] = [
        {
            "@type": "WebSite",
            "@id": website_id,
            "url": canonical_url,
            "name": name,
            "description": description,
            "inLanguage": "en-GB",
            "publisher": {"@id": org_id},
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": employers_search,
                },
                "query-input": "required name=search_term_string",
            },
        },
        {
            "@type": "Organization",
            "@id": org_id,
            "name": name,
            "url": canonical_url,
            "logo": _logo_image_object(origin),
            "sameAs": [github_repo_url],
        },
        {
            "@type": "WebPage",
            "@id": canonical_url,
            "url": canonical_url,
            "name": document_title,
            "description": description,
            "inLanguage": "en-GB",
            "isPartOf": {"@id": website_id},
            "about": {
                "@type": "Thing",
                "name": "Technology and software hiring in Greece",
            },
        },
    ]
    return json.dumps(
        {"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False
    )


def build_schema_employers_directory(
    *,
    home_canonical_url: str,
    employers_canonical_url: str,
    origin: str,
    name: str,
    description: str,
    document_title: str,
    total_companies: int,
    github_repo_url: str,
) -> str:
    """JSON-LD for the job search page including employer directory ``CollectionPage``."""
    website_id = f"{origin}/#website"
    org_id = f"{origin}/#organization"
    employers_search = f"{origin}/job-search/?q={{search_term_string}}"
    graph: list[dict] = [
        {
            "@type": "WebSite",
            "@id": website_id,
            "url": home_canonical_url,
            "name": name,
            "description": description,
            "inLanguage": "en-GB",
            "publisher": {"@id": org_id},
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": employers_search,
                },
                "query-input": "required name=search_term_string",
            },
        },
        {
            "@type": "Organization",
            "@id": org_id,
            "name": name,
            "url": home_canonical_url,
            "logo": _logo_image_object(origin),
            "sameAs": [github_repo_url],
        },
        {
            "@type": "WebPage",
            "@id": employers_canonical_url,
            "url": employers_canonical_url,
            "name": document_title,
            "description": description,
            "inLanguage": "en-GB",
            "isPartOf": {"@id": website_id},
            "about": {
                "@type": "Thing",
                "name": "Technology and software hiring in Greece",
            },
        },
        {
            "@type": "CollectionPage",
            "@id": f"{employers_canonical_url}#employers",
            "name": "Technology employers hiring in Greece",
            "isPartOf": {"@id": employers_canonical_url},
            "numberOfItems": total_companies,
        },
        _breadcrumb_list(
            page_url=employers_canonical_url,
            crumbs=[
                ("Home", home_canonical_url),
                ("Job search", employers_canonical_url),
            ],
        ),
    ]
    return json.dumps(
        {"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False
    )


def _breadcrumb_list(
    *,
    page_url: str,
    crumbs: list[tuple[str, str]],
) -> dict:
    """``BreadcrumbList`` with absolute URLs (Home + path to current page)."""
    elements: list[dict] = []
    for i, (name, url) in enumerate(crumbs, start=1):
        elements.append(
            {
                "@type": "ListItem",
                "position": i,
                "name": name,
                "item": url,
            }
        )
    return {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": elements,
    }


def build_schema_subpage(
    *,
    canonical_url: str,
    document_title: str,
    description: str,
    origin: str,
    site_name: str,
    github_repo_url: str,
    breadcrumbs: list[tuple[str, str]],
    item_list_count: int | None = None,
) -> str:
    """JSON-LD for static subpages: WebSite, Organization, WebPage, BreadcrumbList; optional ItemList."""
    o = origin.rstrip("/")
    website_id = f"{o}/#website"
    org_id = f"{o}/#organization"
    graph: list[dict] = [
        {
            "@type": "WebSite",
            "@id": website_id,
            "name": site_name,
            "url": f"{o}/",
            "inLanguage": "en-GB",
            "publisher": {"@id": org_id},
        },
        {
            "@type": "Organization",
            "@id": org_id,
            "name": site_name,
            "url": f"{o}/",
            "logo": _logo_image_object(origin),
            "sameAs": [github_repo_url],
        },
        {
            "@type": "WebPage",
            "@id": canonical_url,
            "url": canonical_url,
            "name": document_title,
            "description": description,
            "inLanguage": "en-GB",
            "isPartOf": {"@id": website_id},
        },
        _breadcrumb_list(page_url=canonical_url, crumbs=breadcrumbs),
    ]
    if item_list_count is not None and item_list_count > 0:
        graph.append(
            {
                "@type": "ItemList",
                "name": "Curated Greek-related GitHub repositories",
                "numberOfItems": item_list_count,
                "url": canonical_url,
            }
        )
    return json.dumps(
        {"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False
    )


def _page_breadcrumb_trail(
    origin: str, current_label: str, relpath: str
) -> list[tuple[str, str]]:
    """Home + current page for JSON-LD ``BreadcrumbList`` (absolute URLs)."""
    o = origin.rstrip("/")
    return [("Home", f"{o}/"), (current_label, page_canonical_url(origin, relpath))]


def _logo_image_object(origin: str) -> dict:
    """Organization logo pointing at the same asset used for Open Graph previews."""
    o = origin.rstrip("/")
    return {
        "@type": "ImageObject",
        "url": f"{o}/assets/og-image.png",
        "width": 1200,
        "height": 630,
    }


def load_workable_job_counts_enabled() -> bool:
    """Whether Workable open-role counts are shown on the site and README."""
    if not _README_YAML.is_file():
        return True
    try:
        with _README_YAML.open(encoding="utf-8") as f:
            rd = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return True
    feat = rd.get("features") or {}
    wjc = feat.get("workable_job_counts") or {}
    if "enabled" in wjc:
        return bool(wjc["enabled"])
    return True


def load_readme_hero() -> tuple[str, str]:
    """Tagline and short intro for the home hub (from ``_data/readme.yaml``)."""
    default_tag = "The open-source pulse on remote-first IT and software jobs in Greece"
    default_intro = (
        "Browse remote-first employers, job boards, curated lists, remote café guides, and "
        "podcasts—aligned with the GitHub repository."
    )
    if not _README_YAML.is_file():
        return default_tag, default_intro
    try:
        with _README_YAML.open(encoding="utf-8") as f:
            rd = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return default_tag, default_intro
    tag = rd.get("tagline")
    tagline = tag.strip() if isinstance(tag, str) and tag.strip() else default_tag
    desc = rd.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return tagline, default_intro
    intro = " ".join(desc.split()).strip().replace("**", "")
    if len(intro) > 320:
        intro = intro[:317].rstrip() + "…"
    return tagline, intro


def load_queries_split() -> tuple[list[dict], list[dict]]:
    """Job-board sections and awesome-list query rows from ``_data/queries.yaml``."""
    if not QUERIES_YAML.is_file():
        return [], []
    try:
        with QUERIES_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return [], []
    sections = data.get("sections") or []
    job_sections: list[dict] = []
    awesome_queries: list[dict] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        title = (sec.get("title") or "").strip()
        if title == "Job boards, portals & search":
            job_sections.append(sec)
        elif title == "Curated awesome lists (GitHub)":
            q = sec.get("queries") or []
            if isinstance(q, list):
                awesome_queries = [x for x in q if isinstance(x, dict)]
    return job_sections, awesome_queries


def load_open_greek_data_entries() -> list[dict]:
    """Rows for ``open_greek_data.yaml`` → resources page (name, url, description)."""
    if not OPEN_GREEK_DATA_YAML.is_file():
        return []
    try:
        with OPEN_GREEK_DATA_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    raw = data.get("entries") or []
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        if not name or not url:
            continue
        desc = (row.get("description") or "").strip()
        out.append({"name": name, "url": url, "description": desc})
    return out


def _resources_row_search_text(
    category: str,
    name: str,
    url: str,
    desc_raw: str,
) -> str:
    """Lowercase text for ``data-search`` on resources.html (category + link + description)."""
    parts = [category, name, url, desc_raw]
    s = " ".join(p for p in parts if p).lower()
    s = " ".join(s.split())
    if len(s) > 4096:
        s = s[:4096]
    return s


def build_resources_table_rows(
    *,
    query_sections: list[dict],
    awesome_queries: list[dict],
    open_greek_data_queries: list[dict],
    github_repo_url: str,
    site_baseurl: str = "",
    local_flat: bool = False,
) -> list[dict]:
    """Flatten YAML query sections + awesome + open data → table rows for ``page_resources.html``."""
    rows: list[dict] = []
    for sec in query_sections:
        if not isinstance(sec, dict):
            continue
        cat = (sec.get("title") or "").strip()
        for q in sec.get("queries") or []:
            if not isinstance(q, dict):
                continue
            name = (q.get("name") or "").strip()
            url = (q.get("url") or "").strip()
            if not name or not url:
                continue
            desc_raw = (q.get("description") or "").strip()
            desc_html = (
                markdown_to_html(
                    desc_raw,
                    github_repo_url=github_repo_url,
                    site_baseurl=site_baseurl,
                    local_flat=local_flat,
                )
                if desc_raw
                else ""
            )
            rows.append(
                {
                    "category": cat,
                    "name": name,
                    "url": url,
                    "description_html": desc_html,
                    "search_text": _resources_row_search_text(cat, name, url, desc_raw),
                }
            )

    cat_awesome = "Curated awesome lists (GitHub)"
    for q in awesome_queries:
        if not isinstance(q, dict):
            continue
        name = (q.get("name") or "").strip()
        url = (q.get("url") or "").strip()
        if not name or not url:
            continue
        desc_raw = (q.get("description") or "").strip()
        desc_html = (
            markdown_to_html(
                desc_raw,
                github_repo_url=github_repo_url,
                site_baseurl=site_baseurl,
                local_flat=local_flat,
            )
            if desc_raw
            else ""
        )
        rows.append(
            {
                "category": cat_awesome,
                "name": name,
                "url": url,
                "description_html": desc_html,
                "search_text": _resources_row_search_text(
                    cat_awesome, name, url, desc_raw
                ),
            }
        )

    cat_open = "Open Greek data & public knowledge"
    for q in open_greek_data_queries:
        if not isinstance(q, dict):
            continue
        name = (q.get("name") or "").strip()
        url = (q.get("url") or "").strip()
        if not name or not url:
            continue
        desc_raw = (q.get("description") or "").strip()
        desc_html = (
            markdown_to_html(
                desc_raw,
                github_repo_url=github_repo_url,
                site_baseurl=site_baseurl,
                local_flat=local_flat,
            )
            if desc_raw
            else ""
        )
        rows.append(
            {
                "category": cat_open,
                "name": name,
                "url": url,
                "description_html": desc_html,
                "search_text": _resources_row_search_text(
                    cat_open, name, url, desc_raw
                ),
            }
        )
    return rows


def load_podcasts_page_data() -> dict:
    """YAML → structured data for ``page_podcasts.html`` (summary table)."""
    out: dict = {
        "summary_table_html": "",
    }
    if not PODCASTS_YAML.is_file():
        return out
    try:
        with PODCASTS_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return out
    if not isinstance(data, dict):
        return out

    raw_podcasts = [
        p
        for p in (data.get("podcasts") or [])
        if isinstance(p, dict) and (p.get("title") or "").strip()
    ]
    if raw_podcasts:
        out["summary_table_html"] = podcast_summary_table_html(raw_podcasts)

    return out


def load_remote_workspace_html(
    github_repo_url: str,
    *,
    site_baseurl: str = "",
    local_flat: bool = False,
) -> str:
    """``_data/cafe_resources.yaml`` → HTML (same markdown pipeline as ``docs/remote-cafe-resources.md``)."""
    if not CAFE_RESOURCES_YAML.is_file():
        return ""
    try:
        with CAFE_RESOURCES_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return ""
    if not isinstance(data, dict):
        data = {}
    md = build_remote_cafe_resources_markdown(data, for_web_embed=True).strip()
    if not md:
        return ""
    return markdown_to_html(
        md,
        github_repo_url=github_repo_url,
        site_baseurl=site_baseurl,
        local_flat=local_flat,
    )


def _open_source_row_search_text(
    title: str,
    url: str,
    desc_raw: str,
    stars_display: str,
    forks_display: str,
) -> str:
    """Lowercase, whitespace-normalised text for ``data-search`` (filter without ``innerText``)."""
    parts = [
        title,
        url,
        desc_raw,
        stars_display.replace("—", " "),
        forks_display.replace("—", " "),
    ]
    s = " ".join(p for p in parts if p).lower()
    s = " ".join(s.split())
    if len(s) > 4096:
        s = s[:4096]
    return s


def load_open_source_projects_page(
    github_repo_url: str,
    *,
    site_baseurl: str = "",
    local_flat: bool = False,
    skip_github_stats: bool = False,
) -> dict:
    """``_data/open_source_projects.yaml`` + ``_data/open_source_github_stats.yaml`` → open-source page."""
    out: dict = {
        "rows": [],
        "has_projects": False,
        "project_count": 0,
    }
    if not OPEN_SOURCE_PROJECTS_YAML.is_file():
        return out
    try:
        with OPEN_SOURCE_PROJECTS_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return out
    if not isinstance(data, dict):
        return out

    projects = data.get("projects") or []
    valid: list[dict] = []
    if isinstance(projects, list):
        for p in projects:
            if not isinstance(p, dict):
                continue
            title = (p.get("title") or "").strip()
            url = (p.get("url") or "").strip()
            if not title or not url:
                continue
            valid.append(p)

    if not valid:
        return out

    total = len(valid)
    stats_cache: dict[str, tuple[int | None, int | None]] = {}
    if not skip_github_stats:
        stats_cache = load_open_source_github_stats_yaml(OPEN_SOURCE_GITHUB_STATS_YAML)
        if not stats_cache and total > 0:
            print(
                "Open source: no _data/open_source_github_stats.yaml (or empty). "
                "Star/fork columns show —. Run: just fetch-open-source-stats",
                file=sys.stderr,
                flush=True,
            )
        elif stats_cache:
            print(
                f"Open source: using {len(stats_cache)} cached repo stats from "
                f"{OPEN_SOURCE_GITHUB_STATS_YAML.name}.",
                file=sys.stderr,
                flush=True,
            )
    else:
        print(
            "Open source: skipping cached GitHub stats (stars/forks show as —).",
            file=sys.stderr,
            flush=True,
        )

    rows_scored: list[tuple[dict, int | None, int | None]] = []
    for p in valid:
        stars: int | None = None
        forks: int | None = None
        parsed = parse_github_repo_url((p.get("url") or "").strip())
        if parsed and not skip_github_stats:
            key = f"{parsed[0]}/{parsed[1]}"
            if key in stats_cache:
                stars, forks = stats_cache[key]
        rows_scored.append((p, stars, forks))
    rows_scored.sort(key=lambda r: r[1] if r[1] is not None else -1, reverse=True)

    rows: list[dict] = []
    for p, stars, forks in rows_scored:
        desc_raw = (p.get("description") or "").strip()
        desc_html = (
            markdown_to_html(
                desc_raw,
                github_repo_url=github_repo_url,
                site_baseurl=site_baseurl,
                local_flat=local_flat,
            )
            if desc_raw
            else ""
        )
        title_s = (p.get("title") or "").strip()
        url_s = (p.get("url") or "").strip()
        stars_display = format_compact_github_count(stars)
        forks_display = format_compact_github_count(forks)
        rows.append(
            {
                "title": title_s,
                "url": url_s,
                "stars": stars,
                "forks": forks,
                "stars_display": stars_display,
                "forks_display": forks_display,
                "search_text": _open_source_row_search_text(
                    title_s, url_s, desc_raw, stars_display, forks_display
                ),
                "description_html": desc_html,
            }
        )

    out["rows"] = rows
    out["has_projects"] = True
    out["project_count"] = len(rows)
    return out


def meta_page(
    base: dict[str, str],
    *,
    relpath: str,
    document_title: str,
    og_description: str | None = None,
    seo_keywords: str | None = None,
) -> dict[str, str]:
    """Clone site meta with a subpage canonical URL and title."""
    out = dict(base)
    out["canonical_url"] = page_canonical_url(base["site_origin"], relpath)
    out["document_title"] = document_title
    if og_description is not None:
        d = og_description.strip()
        if len(d) > 200:
            d = d[:197].rstrip() + "…"
        out["og_description"] = d
    if seo_keywords is not None:
        out["seo_keywords"] = seo_keywords.strip()
    return out


# --- Helper Functions ---
def get_policy_style(policy):
    if not policy:
        return "hidden"
    p = str(policy).lower()
    if "remote" in p:
        return " ".join(
            [
                "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200",
                "dark:bg-emerald-500/10 dark:text-emerald-300",
                "dark:ring-emerald-400/30",
            ]
        )
    if "hybrid" in p:
        return " ".join(
            [
                "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
                "dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/30",
            ]
        )
    return " ".join(
        [
            "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-200",
            "dark:bg-slate-500/10 dark:text-slate-300 dark:ring-slate-400/30",
        ]
    )


def normalize_url(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == "none":
        return None
    return s


def normalize_sector(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return " ".join(s.split())


# Non-Greek / non-in-scope locations (defence in depth; list stays in sync with data policy).
_NON_GREEK_LOCATIONS_CASEFOLD = frozenset(
    {
        "bangalore",
        "hyderabad",
        "santa clara, ca",
        "new york, ny",
        "west end, england",
        "schindellegi, schwyz",
    }
)

# Greek place name typos / transliterations → canonical label on the site.
_LOCATION_ALIASES_CASEFOLD: dict[str, str] = {
    "athina": "Athens",
    "thessaloníki": "Thessaloniki",
    "thessalonig": "Thessaloniki",
    "piraues": "Piraeus",
    "irakleion": "Heraklion",
    "iraklion": "Heraklion",
    "larisa": "Larissa",
}


def normalize_location(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = " ".join(s.split())
    cf = s.casefold()
    if cf in _NON_GREEK_LOCATIONS_CASEFOLD:
        return None
    if cf in _LOCATION_ALIASES_CASEFOLD:
        return _LOCATION_ALIASES_CASEFOLD[cf]
    if cf in {"athens"}:
        return "Athens"
    if cf in {"thessaloniki"}:
        return "Thessaloniki"
    return s


def normalize_policy(value):
    raw = (value or "").strip().lower()
    if not raw:
        return "n/a"
    if raw in {"n/a", "na", "none"}:
        return "n/a"
    if raw == "remote":
        return "remote"
    if raw == "hybrid":
        return "hybrid"
    if raw in {"on-site", "onsite", "on site"}:
        return "on-site"
    return raw


def load_workable_snapshot():
    """Load ``_data/workable_counts.yaml`` for embedding in the HTML output."""
    if not WORKABLE_SNAPSHOT_PATH.is_file():
        return {"generated_at": None, "accounts": {}, "total_open": 0}
    try:
        with WORKABLE_SNAPSHOT_PATH.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {"generated_at": None, "accounts": {}, "total_open": 0}
    if not isinstance(data, dict):
        return {"generated_at": None, "accounts": {}, "total_open": 0}
    accounts = data.get("accounts")
    if not isinstance(accounts, dict):
        accounts = {}
    total = data.get("total_open")
    if not isinstance(total, int):
        total = sum(n for n in accounts.values() if isinstance(n, int))
    return {
        "generated_at": data.get("generated_at"),
        "accounts": accounts,
        "total_open": total,
        "metric": data.get("metric") or "incountry_greece",
    }


def run_generate_index(
    *,
    local_flat: bool = False,
    skip_github_stats: bool = False,
) -> None:
    """Load YAML, snapshot, render ``index.html`` and static resource subpages.

    Set ``local_flat=True`` (``--local`` or ``AGTJ_LOCAL``) for sibling ``*.html`` links,
    relative ``assets/``, and no YAML front matter — suitable for ``python -m http.server``
    from the repo root without Jekyll.

    Set ``skip_github_stats=True`` to skip per-repo GitHub API calls (fast local iteration).
    """
    try:
        print(
            "generate_index: loading companies and rendering pages…",
            file=sys.stderr,
            flush=True,
        )
        companies_data = load_companies()

        if not companies_data:
            print("No companies found in source.")
            companies_data = []

        all_sectors = set()
        all_locations = set()
        all_industries: set[str] = set()
        policy_counts = Counter()
        sector_counts = Counter()
        location_counts = Counter()
        industry_counts = Counter()

        for c in companies_data:
            if not c.get("work_policy"):
                c["work_policy"] = "N/A"
            else:
                c["work_policy"] = str(c["work_policy"]).strip()

            careers_url = normalize_url(c.get("careers_url"))
            company_url = normalize_url(c.get("url"))
            c["careers_url"] = careers_url
            c["url"] = company_url
            c["site_url"] = company_url or "#"
            c["career_url"] = careers_url or company_url or "#"
            c["workable_slug"] = extract_workable_apply_slug(careers_url)

            raw_sectors = c.get("sectors", []) or []
            normalized = []
            for s in raw_sectors:
                ns = normalize_sector(s)
                if ns:
                    normalized.append(ns)

            seen = set()
            deduped = []
            for s in normalized:
                k = s.casefold()
                if k in seen:
                    continue
                seen.add(k)
                deduped.append(s)
            deduped.sort(key=lambda x: x.casefold())
            c["sectors"] = deduped

            c["industries"] = industries_for_sectors(deduped)
            for ind in c["industries"]:
                all_industries.add(ind)
                industry_counts[ind] += 1

            raw_locations = c.get("locations", []) or []
            loc_normalized = []
            for loc in raw_locations:
                nl = normalize_location(loc)
                if nl:
                    loc_normalized.append(nl)
            seen = set()
            loc_deduped = []
            for loc in loc_normalized:
                k = loc.casefold()
                if k in seen:
                    continue
                seen.add(k)
                loc_deduped.append(loc)
            loc_deduped.sort(key=lambda x: x.casefold())
            c["locations"] = loc_deduped
            # Card / row data: only this company’s offices (never the global directory list).
            c["office_locations"] = loc_deduped

            for s in c.get("sectors", []):
                all_sectors.add(s)
                sector_counts[s] += 1
            for loc in c.get("locations", []):
                all_locations.add(loc)
                location_counts[loc] += 1

            policy_counts[normalize_policy(c.get("work_policy"))] += 1

        sorted_sectors = sorted(list(all_sectors))
        sorted_locations = sorted(list(all_locations))
        industries_for_dropdown = sort_industries_for_filter(all_industries)

        stats = {
            "total_companies": len(companies_data),
            "policy_counts": dict(policy_counts),
            "top_sectors": sector_counts.most_common(10),
            "top_locations": location_counts.most_common(10),
            "top_industries": industry_counts.most_common(12),
            "workable_companies_count": sum(
                1 for c in companies_data if c.get("workable_slug")
            ),
        }

    except FileNotFoundError as e:
        print(f"Error loading companies: {e}", file=sys.stderr)
        raise SystemExit(1)

    tagline, intro_blurb = load_readme_hero()
    show_workable_job_counts = load_workable_job_counts_enabled()
    if not show_workable_job_counts:
        stats["workable_companies_count"] = 0
    job_sections, awesome_queries = load_queries_split()
    open_greek_data_queries = load_open_greek_data_entries()

    template = env.get_template("index_template.html")

    _workable_snapshot = load_workable_snapshot()
    _meta = apply_site_navigation_context(load_site_meta(), local_flat=local_flat)
    _home_schema = build_schema_home_hub(
        canonical_url=_meta["canonical_url"],
        origin=_meta["site_origin"],
        name=_meta["og_site_name"],
        description=_meta["og_description"],
        document_title=_meta["document_title"],
        github_repo_url=_meta["github_repo_url"],
    )
    final_html = template.render(
        schema_json_ld=_home_schema,
        site_tagline=tagline,
        site_intro_blurb=intro_blurb,
        show_workable_job_counts=show_workable_job_counts,
        current_page="home",
        **_meta,
    )

    write_jekyll_html(Path(OUTPUT_INDEX), final_html, local_flat=local_flat)

    site_name = _meta["og_site_name"]

    job_combined_desc = _truncate_first_card_description(
        "Searchable remote-first Greek tech employers: sectors, locations, and Workable Greece role counts."
    )
    job_meta = meta_page(
        _meta,
        relpath=OUTPUT_JOB_SEARCH,
        document_title=f"{site_name} | Job search",
        og_description=job_combined_desc,
        seo_keywords=_SEO_KW_JOB,
    )
    job_schema_combined = build_schema_employers_directory(
        home_canonical_url=_meta["canonical_url"],
        employers_canonical_url=job_meta["canonical_url"],
        origin=_meta["site_origin"],
        name=_meta["og_site_name"],
        description=job_meta["og_description"],
        document_title=job_meta["document_title"],
        total_companies=stats["total_companies"],
        github_repo_url=_meta["github_repo_url"],
    )
    write_jekyll_html(
        Path(OUTPUT_JOB_SEARCH),
        env.get_template("page_job_search_combined.html").render(
            companies=companies_data,
            sectors=sorted_sectors,
            locations=sorted_locations,
            industries_for_dropdown=industries_for_dropdown,
            agtj_config_json=json.dumps(
                {
                    "itemsPerPage": ITEMS_PER_PAGE,
                    "showWorkableJobCounts": show_workable_job_counts,
                },
                ensure_ascii=False,
            ),
            get_style=get_policy_style,
            stats=stats,
            show_workable_job_counts=show_workable_job_counts,
            workable_snapshot=_workable_snapshot,
            workable_snapshot_json=json.dumps(_workable_snapshot, ensure_ascii=False),
            schema_json_ld=job_schema_combined,
            current_page="job-search",
            page_kicker="Job search · Directory & links",
            page_title="Job search",
            **job_meta,
        ),
        local_flat=local_flat,
    )
    write_jekyll_html(
        Path(OUTPUT_EMPLOYERS),
        env.get_template("employers_redirect.html").render(
            canonical_job_search_url=job_meta["canonical_url"],
            **job_meta,
        ),
        local_flat=local_flat,
    )

    res_desc = _truncate_first_card_description(
        "Job boards, awesome GitHub lists, open Greek data—all YAML-driven. "
        "Laptop cafés: Workspaces page."
    )
    res_meta = meta_page(
        _meta,
        relpath=OUTPUT_RESOURCES,
        document_title=f"{site_name} | Resources",
        og_description=res_desc,
        seo_keywords=_SEO_KW_RES,
    )
    res_schema = build_schema_subpage(
        canonical_url=res_meta["canonical_url"],
        document_title=res_meta["document_title"],
        description=res_meta["og_description"],
        origin=_meta["site_origin"],
        site_name=_meta["og_site_name"],
        github_repo_url=_meta["github_repo_url"],
        breadcrumbs=_page_breadcrumb_trail(
            _meta["site_origin"], "Resources", OUTPUT_RESOURCES
        ),
    )
    remote_html = load_remote_workspace_html(
        _meta["github_repo_url"],
        site_baseurl=_meta["site_baseurl"],
        local_flat=local_flat,
    )
    resource_rows = build_resources_table_rows(
        query_sections=job_sections,
        awesome_queries=awesome_queries,
        open_greek_data_queries=open_greek_data_queries,
        github_repo_url=_meta["github_repo_url"],
        site_baseurl=_meta["site_baseurl"],
        local_flat=local_flat,
    )
    write_jekyll_html(
        Path(OUTPUT_RESOURCES),
        env.get_template("page_resources.html").render(
            page_kicker="Resources · Lists & data",
            page_title="Resources & curated links",
            page_subtitle=res_desc,
            resource_rows=resource_rows,
            resource_count=len(resource_rows),
            has_resource_rows=bool(resource_rows),
            current_page="resources",
            schema_json_ld=res_schema,
            **res_meta,
        ),
        local_flat=local_flat,
    )

    pod_desc = _truncate_first_card_description(
        "Greek tech & startup podcasts—video/audio, platform links in one table (YAML)."
    )
    pod_meta = meta_page(
        _meta,
        relpath=OUTPUT_PODCASTS,
        document_title=f"{site_name} | Podcasts",
        og_description=pod_desc,
        seo_keywords=_SEO_KW_POD,
    )
    pod_schema = build_schema_subpage(
        canonical_url=pod_meta["canonical_url"],
        document_title=pod_meta["document_title"],
        description=pod_meta["og_description"],
        origin=_meta["site_origin"],
        site_name=_meta["og_site_name"],
        github_repo_url=_meta["github_repo_url"],
        breadcrumbs=_page_breadcrumb_trail(
            _meta["site_origin"], "Podcasts", OUTPUT_PODCASTS
        ),
    )
    pod_page = load_podcasts_page_data()
    write_jekyll_html(
        Path(OUTPUT_PODCASTS),
        env.get_template("page_podcasts.html").render(
            current_page="podcasts",
            schema_json_ld=pod_schema,
            page_kicker="Podcasts · Greek tech & startups",
            page_title="Greek tech & startup podcasts",
            page_subtitle=_truncate_first_card_description(
                "Shows from Greece on tech, startups & engineering-curated list."
            ),
            **pod_page,
            **pod_meta,
        ),
        local_flat=local_flat,
    )

    ws_desc = _truncate_first_card_description(
        "Laptop-friendly cafés & workspace finders for Greece—YAML: _data/cafe_resources.yaml."
    )
    ws_meta = meta_page(
        _meta,
        relpath=OUTPUT_WORKSPACES,
        document_title=f"{site_name} | Workspaces & cafés",
        og_description=ws_desc,
        seo_keywords=_SEO_KW_WS,
    )
    ws_schema = build_schema_subpage(
        canonical_url=ws_meta["canonical_url"],
        document_title=ws_meta["document_title"],
        description=ws_meta["og_description"],
        origin=_meta["site_origin"],
        site_name=_meta["og_site_name"],
        github_repo_url=_meta["github_repo_url"],
        breadcrumbs=_page_breadcrumb_trail(
            _meta["site_origin"], "Workspaces & cafés", OUTPUT_WORKSPACES
        ),
    )
    write_jekyll_html(
        Path(OUTPUT_WORKSPACES),
        env.get_template("page_workspaces.html").render(
            current_page="workspaces",
            remote_workspace_html=remote_html,
            schema_json_ld=ws_schema,
            page_kicker="Workspaces · Cafés & places",
            page_title="Workspaces & laptop-friendly cafés",
            page_subtitle=ws_desc,
            **ws_meta,
        ),
        local_flat=local_flat,
    )

    osp_desc = _truncate_first_card_description(OSP_HERO_SUBTITLE)
    osp_meta = meta_page(
        _meta,
        relpath=OUTPUT_OPEN_SOURCE,
        document_title=f"{site_name} | Open source",
        og_description=osp_desc,
        seo_keywords=_SEO_KW_OSP,
    )
    osp_page = load_open_source_projects_page(
        _meta["github_repo_url"],
        site_baseurl=_meta["site_baseurl"],
        local_flat=local_flat,
        skip_github_stats=skip_github_stats,
    )
    osp_schema = build_schema_subpage(
        canonical_url=osp_meta["canonical_url"],
        document_title=osp_meta["document_title"],
        description=osp_meta["og_description"],
        origin=_meta["site_origin"],
        site_name=_meta["og_site_name"],
        github_repo_url=_meta["github_repo_url"],
        breadcrumbs=_page_breadcrumb_trail(
            _meta["site_origin"], "Open source", OUTPUT_OPEN_SOURCE
        ),
        item_list_count=(
            osp_page["project_count"] if osp_page.get("has_projects") else None
        ),
    )
    write_jekyll_html(
        Path(OUTPUT_OPEN_SOURCE),
        env.get_template("page_open_source.html").render(
            current_page="open-source",
            schema_json_ld=osp_schema,
            page_kicker="Open source · GitHub",
            page_title="Greek open source on GitHub",
            page_subtitle=osp_desc,
            **osp_page,
            **osp_meta,
        ),
        local_flat=local_flat,
    )

    write_sitemap_xml(_REPO_ROOT, _meta["site_origin"])
    write_robots_txt(_REPO_ROOT, _meta["site_origin"])

    print(
        f"Generated {OUTPUT_INDEX}, {OUTPUT_EMPLOYERS} (redirect), {OUTPUT_JOB_SEARCH}, "
        f"{OUTPUT_RESOURCES}, {OUTPUT_PODCASTS}, {OUTPUT_WORKSPACES}, {OUTPUT_OPEN_SOURCE}, "
        "sitemap.xml, robots.txt."
    )
    if local_flat:
        print(
            "Local preview: sibling *.html + assets/ (no baseurl prefix; no Jekyll front matter)."
        )
    else:
        print(
            "GitHub Pages layout: baseurl paths + Jekyll front matter (for jekyll build / CI)."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate index.html (hub), job-search.html (directory), "
            "employers.html (redirect), resources.html (queries + open data), podcasts.html, "
            "workspaces.html (café YAML), open-source.html (open-source YAML + GitHub stars/forks), "
            "sitemap.xml, and robots.txt from _data/companies/*.yaml, _data/queries.yaml, "
            "_data/cafe_resources.yaml, _data/open_source_projects.yaml, "
            "_data/open_source_github_stats.yaml, _data/podcasts.yaml, and readme data."
        ),
    )
    parser.add_argument(
        "--fetch-workable",
        action="store_true",
        help=(
            "Run fetch_workable_counts first (writes _data/workable_counts.yaml "
            "over the network)."
        ),
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help=(
            "Force local preview output (sibling *.html + assets/). "
            "Also AGTJ_LOCAL=1. Default on developer machines; CI sets production automatically."
        ),
    )
    parser.add_argument(
        "--github-pages",
        action="store_true",
        help=(
            "Force GitHub Pages output (baseurl from live_url + Jekyll front matter). "
            "Also AGTJ_GH_PAGES=1. Default in GitHub Actions (CI=true)."
        ),
    )
    parser.add_argument(
        "--skip-github-stats",
        action="store_true",
        help=(
            "Ignore _data/open_source_github_stats.yaml for open-source rows (stars/forks show as —). "
            "Also AGTJ_SKIP_GITHUB_STATS=1."
        ),
    )
    args = parser.parse_args(argv)

    if args.fetch_workable:
        from greek_software_ecosystem.fetch_workable_counts import (
            main as fetch_workable_main,
        )

        rc = fetch_workable_main()
        if rc != 0:
            return rc

    env_local = os.environ.get("AGTJ_LOCAL", "").strip().lower()
    in_env_local = env_local in ("1", "true", "yes", "on")
    env_gh = os.environ.get("AGTJ_GH_PAGES", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    ci = os.environ.get("CI", "").strip().lower() in ("true", "1", "yes")
    if in_env_local:
        local_flat = True
    elif args.github_pages or env_gh:
        local_flat = False
    elif args.local:
        local_flat = True
    else:
        # Developers: local http.server from repo root. CI: paths for Jekyll + deploy.
        local_flat = not ci

    skip_gh = args.skip_github_stats or os.environ.get(
        "AGTJ_SKIP_GITHUB_STATS", ""
    ).strip().lower() in ("1", "true", "yes", "on")

    run_generate_index(local_flat=local_flat, skip_github_stats=skip_gh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
