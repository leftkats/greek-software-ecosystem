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
   ``job-search.html`` (employer directory + job-board links); ``employers.html`` is a short redirect.

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
import sys
from pathlib import Path

import yaml
from collections import Counter

from jinja2 import Environment, FileSystemLoader

from greek_software_ecosystem.industry_clusters import (
    industries_for_sectors,
    sort_industries_for_filter,
)
from greek_software_ecosystem.load_companies import (
    QUERIES_YAML,
    WORKABLE_COUNTS_YAML,
    load_companies,
)
from greek_software_site.markdown_html import markdown_file_to_html, markdown_to_html
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
ITEMS_PER_PAGE = 50
WORKABLE_SNAPSHOT_PATH = WORKABLE_COUNTS_YAML
PODCASTS_YAML = Path("_data/podcasts.yaml")
REMOTE_CAFE_MD = Path("remote-cafe-resources.md")

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

_README_YAML = Path("_data/readme.yaml")


def load_site_meta() -> dict:
    """SEO, Open Graph / Twitter, canonical URL (aligned with ``_data/readme.yaml``)."""
    origin = "https://leftkats.github.io/greek-software-ecosystem"
    title = "Awesome Greek Software Engineering"
    desc = (
        "A vibrant map of employers hiring for technology roles in Greece — "
        "sectors, work policies, careers, and weekly Workable snapshots."
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
    github_repo_url = f"https://github.com/{repo_slug}"
    document_title = f"{title} | Greece software engineering & careers"
    if len(document_title) > 60:
        document_title = f"{title} | Greek software engineering careers"
    seo_keywords = (
        "Greece software engineering jobs, software engineer Greece, IT careers Athens, "
        "remote work Greece, tech startups Greece, developer jobs Greece, "
        "engineering jobs Thessaloniki, hiring Greece"
    )
    return {
        "canonical_url": canonical_url,
        "site_origin": origin,
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
    employers_search = f"{origin}/job-search.html?q={{search_term_string}}"
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
            "sameAs": [github_repo_url],
        },
        {
            "@type": "WebPage",
            "@id": canonical_url,
            "url": canonical_url,
            "name": document_title,
            "description": description,
            "isPartOf": {"@id": website_id},
            "about": {
                "@type": "Thing",
                "name": "Technology and software hiring in Greece",
            },
        },
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


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
    """JSON-LD for the employers directory page including CollectionPage."""
    website_id = f"{origin}/#website"
    org_id = f"{origin}/#organization"
    employers_search = f"{origin}/job-search.html?q={{search_term_string}}"
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
            "sameAs": [github_repo_url],
        },
        {
            "@type": "WebPage",
            "@id": employers_canonical_url,
            "url": employers_canonical_url,
            "name": document_title,
            "description": description,
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
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def build_schema_subpage(
    *,
    canonical_url: str,
    document_title: str,
    description: str,
) -> str:
    """Minimal JSON-LD for static resource subpages."""
    graph: list[dict] = [
        {
            "@type": "WebPage",
            "@id": canonical_url,
            "url": canonical_url,
            "name": document_title,
            "description": description,
        }
    ]
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def load_readme_hero() -> tuple[str, str]:
    """Tagline + short intro for the home hub (from ``_data/readme.yaml``)."""
    default_tag = "The open-source pulse on IT and software jobs across Greece"
    default_intro = (
        "Browse employers, job boards, curated lists, remote café guides, and "
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


def podcast_link_kind(label: str) -> str:
    """Map link label to icon bucket for the podcasts page template."""
    s = (label or "").casefold().strip()
    if "spotify" in s:
        return "spotify"
    if "apple" in s:
        return "apple"
    if "google" in s and "podcast" in s:
        return "google_podcasts"
    if "youtube" in s:
        return "youtube"
    if s in ("site", "website", "web") or "website" in s:
        return "site"
    return "other"


def load_podcasts_page_data(github_repo_url: str = "") -> dict:
    """YAML → structured data for ``page_podcasts.html`` (cards + intro)."""
    out: dict = {"intro_html": "", "disclaimer_html": "", "podcasts": []}
    if not PODCASTS_YAML.is_file():
        return out
    try:
        with PODCASTS_YAML.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return out
    if not isinstance(data, dict):
        return out

    intro = (data.get("intro") or "").strip()
    if intro:
        out["intro_html"] = markdown_to_html(
            intro, github_repo_url=github_repo_url
        )
    disc = (data.get("disclaimer") or "").strip()
    if disc:
        out["disclaimer_html"] = markdown_to_html(
            disc, github_repo_url=github_repo_url
        )

    shows: list[dict] = []
    for pod in data.get("podcasts") or []:
        if not isinstance(pod, dict):
            continue
        title = (pod.get("title") or "").strip() or "Podcast"
        desc_raw = (pod.get("description") or "").strip()
        desc_html = (
            markdown_to_html(desc_raw, github_repo_url=github_repo_url)
            if desc_raw
            else ""
        )
        links_out: list[dict] = []
        for link in pod.get("links") or []:
            if not isinstance(link, dict):
                continue
            label = (link.get("label") or "").strip()
            url = (link.get("url") or "").strip()
            anchor = (link.get("anchor") or label).strip()
            if not label or not url:
                continue
            links_out.append(
                {
                    "label": label,
                    "url": url,
                    "anchor": anchor,
                    "kind": podcast_link_kind(label),
                }
            )
        shows.append(
            {
                "title": title,
                "description_html": desc_html,
                "links": links_out,
            }
        )

    out["podcasts"] = shows
    return out


def meta_page(
    base: dict[str, str],
    *,
    relpath: str,
    document_title: str,
    og_description: str | None = None,
) -> dict[str, str]:
    """Clone site meta with a subpage canonical URL and title."""
    out = dict(base)
    origin = base["site_origin"].rstrip("/")
    out["canonical_url"] = f"{origin}/{relpath}"
    out["document_title"] = document_title
    if og_description is not None:
        d = og_description.strip()
        if len(d) > 200:
            d = d[:197].rstrip() + "…"
        out["og_description"] = d
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


def run_generate_index() -> None:
    """Load YAML, snapshot, render ``index.html`` and static resource subpages."""
    try:
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
    job_sections, awesome_queries = load_queries_split()

    template = env.get_template("index_template.html")

    _workable_snapshot = load_workable_snapshot()
    _meta = load_site_meta()
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
        current_page="home",
        **_meta,
    )

    Path(OUTPUT_INDEX).write_text(final_html, encoding="utf-8")

    site_name = _meta["og_site_name"]

    job_combined_desc = (
        "Technology employers in Greece—search and filter by industry, location, sector, "
        "and work policy, with weekly Workable role counts where available. Further down, "
        "curated job boards and portals from the repository YAML. "
    )
    job_meta = meta_page(
        _meta,
        relpath=OUTPUT_JOB_SEARCH,
        document_title=f"{site_name} | Job search",
        og_description=job_combined_desc,
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
    Path(OUTPUT_JOB_SEARCH).write_text(
        env.get_template("page_job_search_combined.html").render(
            query_sections=job_sections,
            companies=companies_data,
            sectors=sorted_sectors,
            locations=sorted_locations,
            industries_for_dropdown=industries_for_dropdown,
            agtj_config_json=json.dumps({"itemsPerPage": ITEMS_PER_PAGE}, ensure_ascii=False),
            get_style=get_policy_style,
            stats=stats,
            workable_snapshot=_workable_snapshot,
            workable_snapshot_json=json.dumps(_workable_snapshot, ensure_ascii=False),
            schema_json_ld=job_schema_combined,
            current_page="job-search",
            page_kicker="Job search · Directory & links",
            page_title="Job search",
            page_subtitle=job_combined_desc,
            **job_meta,
        ),
        encoding="utf-8",
    )
    Path(OUTPUT_EMPLOYERS).write_text(
        env.get_template("employers_redirect.html").render(
            canonical_job_search_url=job_meta["canonical_url"],
        ),
        encoding="utf-8",
    )

    res_desc = (
        "Curated GitHub awesome lists plus remote café and laptop-friendly workspace "
        "guides—the same content as in the repository."
    )
    res_meta = meta_page(
        _meta,
        relpath=OUTPUT_RESOURCES,
        document_title=f"{site_name} | Resources",
        og_description=res_desc,
    )
    res_schema = build_schema_subpage(
        canonical_url=res_meta["canonical_url"],
        document_title=res_meta["document_title"],
        description=res_meta["og_description"],
    )
    remote_html = ""
    if REMOTE_CAFE_MD.is_file():
        try:
            remote_html = markdown_file_to_html(
                REMOTE_CAFE_MD, github_repo_url=_meta["github_repo_url"]
            )
        except OSError:
            remote_html = ""
    Path(OUTPUT_RESOURCES).write_text(
        env.get_template("page_resources.html").render(
            awesome_queries=awesome_queries,
            remote_workspace_html=remote_html,
            page_kicker="Resources · Lists & spaces",
            page_title="Resources & workspaces",
            page_subtitle=res_desc,
            current_page="resources",
            schema_json_ld=res_schema,
            **res_meta,
        ),
        encoding="utf-8",
    )

    pod_desc = (
        "Greek tech and startup podcasts in video and audio—curated from the repository "
        "and shown here as browsable cards with listen links."
    )
    pod_meta = meta_page(
        _meta,
        relpath=OUTPUT_PODCASTS,
        document_title=f"{site_name} | Podcasts",
        og_description=pod_desc,
    )
    pod_schema = build_schema_subpage(
        canonical_url=pod_meta["canonical_url"],
        document_title=pod_meta["document_title"],
        description=pod_meta["og_description"],
    )
    pod_page = load_podcasts_page_data(_meta["github_repo_url"])
    Path(OUTPUT_PODCASTS).write_text(
        env.get_template("page_podcasts.html").render(
            current_page="podcasts",
            schema_json_ld=pod_schema,
            page_kicker="Podcasts · Greek tech & startups",
            page_title="Greek tech & startup podcasts",
            page_subtitle=(
                "Video and audio from Greece covering technology, startups, product, and "
                "engineering—the same curated list as on this site’s other pages."
            ),
            **pod_page,
            **pod_meta,
        ),
        encoding="utf-8",
    )

    write_sitemap_xml(_REPO_ROOT, _meta["site_origin"])
    write_robots_txt(_REPO_ROOT, _meta["site_origin"])

    print(
        f"Generated {OUTPUT_INDEX}, {OUTPUT_EMPLOYERS} (redirect), {OUTPUT_JOB_SEARCH}, "
        f"{OUTPUT_RESOURCES}, {OUTPUT_PODCASTS}, sitemap.xml, robots.txt."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate index.html (hub), job-search.html (directory + links), "
            "employers.html (redirect), resources.html, podcasts.html, sitemap.xml, "
            "and robots.txt from _data/companies/*.yaml, "
            "_data/queries.yaml, _data/podcasts.yaml, and markdown resources."
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
    args = parser.parse_args(argv)

    if args.fetch_workable:
        from greek_software_ecosystem.fetch_workable_counts import (
            main as fetch_workable_main,
        )

        rc = fetch_workable_main()
        if rc != 0:
            return rc

    run_generate_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
