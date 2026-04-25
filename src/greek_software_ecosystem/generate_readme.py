"""Generate ``docs/search-queries-and-resources.md``, ``docs/greek-tech-podcasts.md``,
``docs/open-source-projects.md``, ``docs/remote-cafe-resources.md``, ``docs/development.md``,
and ``docs/engineering-hubs.md`` from YAML, plus the repo root ``README.md``.

**Do not edit these output ``*.md`` files by hand.** Change ``_data/readme.yaml``, ``_data/queries.yaml``,
``_data/podcasts.yaml``, ``_data/open_source_projects.yaml``, ``_data/open_source_github_stats.yaml`` (via
``just fetch-open-source-stats``), ``_data/cafe_resources.yaml``, company YAML under ``_data/companies/``,
then run ``just readme`` (or ``just generate``).
"""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote, urlparse

import yaml

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
from greek_software_ecosystem.podcast_urls import (
    podcast_summary_matrix_markdown_lines,
)

README_YAML = Path("_data/readme.yaml")
DOCS_MD_DIR = Path("docs")
ROOT_README = Path("README.md")

# Fallback when ``work_policy_notice`` is missing from ``_data/readme.yaml`` (also used by ``generate_index``).
DEFAULT_WORK_POLICY_NOTICE = (
    "**Note:** Work policy labels (remote, hybrid, on-site) are community-maintained and "
    "may be incorrect or outdated. Always verify roles, locations, and policies on each "
    "employer's official website using the company and careers URLs in the directory."
)

SEARCH_QUERIES_MD = "search-queries-and-resources.md"
GREEK_TECH_PODCASTS_MD = "greek-tech-podcasts.md"
OPEN_SOURCE_PROJECTS_MD = "open-source-projects.md"
ENGINEERING_HUBS_MD = "engineering-hubs.md"
PODCASTS_YAML = Path("_data/podcasts.yaml")
OPEN_SOURCE_PROJECTS_YAML = Path("_data/open_source_projects.yaml")
REMOTE_CAFE_RESOURCES_MD = "remote-cafe-resources.md"
CAFE_RESOURCES_YAML = Path("_data/cafe_resources.yaml")
DEVELOPMENT_MD = "development.md"
# Back-link line on generated pages under ``docs/`` → repository root readme.
README_BACKLINK_MD = "← [README.md](../README.md)"

# Fallbacks when ``_data/readme.yaml`` → ``generated_markdown`` omits a key.
_DEFAULT_SEARCH_QUERIES_INTRO = (
    "Hand-picked links for Greek (and broader remote) job hunting. "
    "Each entry includes a short note on what you’ll find there. "
    f"For **laptop-friendly cafés and remote workspaces**, see "
    f"**[{REMOTE_CAFE_RESOURCES_MD}]({REMOTE_CAFE_RESOURCES_MD})**."
)
_DEFAULT_EH_TITLE = "Engineering Hubs & Career Portals"
_DEFAULT_EH_INTRO = (
    "Curated organizations, focus sectors, work policy, and talent links."
)
_DEFAULT_EH_DISCLAIMER = (
    "**Disclaimer:** This list is community-maintained. Information may be "
    "incomplete, outdated, or incorrect. If you notice an error or want an "
    "update, please [open a GitHub issue]({issue_chooser_url}) "
    "(pick the template that fits)."
)
_DEFAULT_README_OVERVIEW_LINKS = (
    "**What’s in this repository**\n\n"
    f"- **[{ENGINEERING_HUBS_MD}]({ENGINEERING_HUBS_MD})** — the sortable employer "
    "table: sectors, work policy, and talent portals.\n"
    f"- **[{SEARCH_QUERIES_MD}]({SEARCH_QUERIES_MD})** — job search links, "
    "curated lists, and tips & notes.\n"
    f"- **[{GREEK_TECH_PODCASTS_MD}]({GREEK_TECH_PODCASTS_MD})** — Greek tech "
    "& startup podcasts (video and audio).\n"
    f"- **[{OPEN_SOURCE_PROJECTS_MD}]({OPEN_SOURCE_PROJECTS_MD})** — open source "
    "Greek tech projects on GitHub you can contribute to.\n"
    f"- **[{REMOTE_CAFE_RESOURCES_MD}]({REMOTE_CAFE_RESOURCES_MD})** — remote "
    "café & laptop-friendly workspace guides (e.g. "
    "[Remote Work Café](https://remotework.cafe/))."
)
_DEFAULT_README_DEV_BLURB = (
    "Setup, regeneration commands, and CI checks are documented in "
    f"**[{DEVELOPMENT_MD}]({DEVELOPMENT_MD})** "
    "(copy-paste shell blocks)."
)
_DEFAULT_README_COMMUNITY_DISCORD = (
    "**[Join the project Discord]({url})** to ask questions about the directory, "
    "coordinate contributions, and chat with other people using this list."
)


def _readme_markdown_for_repository_root(generated_readme_body: str) -> str:
    """Rewrite relative doc links so they work from the repo root ``README.md``."""
    replacements: tuple[tuple[str, str], ...] = (
        ("](engineering-hubs.md)", "](docs/engineering-hubs.md)"),
        (
            "](search-queries-and-resources.md)",
            "](docs/search-queries-and-resources.md)",
        ),
        ("](greek-tech-podcasts.md)", "](docs/greek-tech-podcasts.md)"),
        ("](open-source-projects.md)", "](docs/open-source-projects.md)"),
        ("](development.md)", "](docs/development.md)"),
        ("](remote-cafe-resources.md)", "](docs/remote-cafe-resources.md)"),
        ("](../remote-cafe-resources.md)", "](docs/remote-cafe-resources.md)"),
    )
    out = generated_readme_body
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def _engineering_hubs_disclaimer_text(readme_data: dict, issue_chooser: str) -> str:
    """Non-empty disclaimer paragraph for ``engineering-hubs.md`` (always written on each run)."""
    gm_eh = (readme_data.get("generated_markdown") or {}).get("engineering_hubs") or {}
    raw = gm_eh.get("disclaimer")
    if raw is None or not str(raw).strip():
        tmpl = _DEFAULT_EH_DISCLAIMER
    else:
        tmpl = str(raw).strip()
    out = tmpl.replace("{issue_chooser_url}", issue_chooser).strip()
    if not out:
        out = _DEFAULT_EH_DISCLAIMER.replace(
            "{issue_chooser_url}", issue_chooser
        ).strip()
    return out


def _iter_tips_note_bullets(notes: list) -> list[tuple[str, str]]:
    """(display title, body) pairs matching readme Tips & Notes rules."""
    pairs: list[tuple[str, str]] = []
    for n in notes:
        title = n["title"]
        if title.strip().lower() == "job counts":
            title = "Job Counts (Experimental)"
        body = n["content"].strip()
        pairs.append((title, body))
    return pairs


def _tips_notes_resource_lines(notes: list) -> list[str]:
    """Line fragments for ``search-queries-and-resources.md`` (``\\n``.join style)."""
    lines: list[str] = ["## Tips & Notes", ""]
    for title, body in _iter_tips_note_bullets(notes):
        lines.append(f"- **{title}:** {body}")
    lines.append("")
    return lines


def _append_query_bullets_to(out: list[str], query_items: list) -> None:
    for q in query_items:
        name = (q.get("name") or "").strip()
        url = (q.get("url") or "").strip()
        desc = (q.get("description") or "").strip()
        if not name or not url:
            continue
        if desc:
            out.append(f"- [{name}]({url}) — {desc}")
        else:
            out.append(f"- [{name}]({url})")


def build_search_queries_markdown(
    queries_data: dict | None, readme_data: dict | None = None
) -> str:
    """Markdown for ``search-queries-and-resources.md`` (queries + optional tips)."""
    gm = (readme_data or {}).get("generated_markdown") or {}
    sq_meta = gm.get("search_queries") or {}
    intro_text = (sq_meta.get("intro") or _DEFAULT_SEARCH_QUERIES_INTRO).strip()
    body: list[str] = [
        "# Search queries & resources",
        "",
        README_BACKLINK_MD,
        "",
        intro_text,
        "",
    ]
    sections = (queries_data or {}).get("sections")
    legacy_queries = (queries_data or {}).get("queries")
    if sections:
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            title = (sec.get("title") or "").strip()
            items = sec.get("queries") or []
            if not items:
                continue
            if title:
                body.append(f"## {title}")
                body.append("")
            _append_query_bullets_to(body, items)
            body.append("")
    elif legacy_queries:
        _append_query_bullets_to(body, legacy_queries)
        body.append("")

    notes = ((readme_data or {}).get("footer") or {}).get("notes") or []
    if notes:
        body.extend(_tips_notes_resource_lines(notes))

    while body and body[-1] == "":
        body.pop()
    body.append("")
    return "\n".join(body)


def build_greek_tech_podcasts_markdown(podcasts_data: dict | None) -> str:
    """Markdown for ``greek-tech-podcasts.md`` from ``_data/podcasts.yaml``."""
    data = podcasts_data or {}
    intro = (data.get("intro") or "").strip()
    disclaimer = (data.get("disclaimer") or "").strip()
    items = data.get("podcasts") or []

    valid_items: list[dict] = []
    for pod in items:
        if isinstance(pod, dict) and (pod.get("title") or "").strip():
            valid_items.append(pod)

    body: list[str] = [
        "# Greek tech & startup podcasts",
        "",
        README_BACKLINK_MD,
        "",
    ]
    if intro:
        body.append(intro)
        body.append("")
        body.append("---")
        body.append("")

    if valid_items:
        body.append("")
        body.append(
            "Each **●** links to that show on the given platform (empty cells mean "
            "no URL listed in the data yet)."
        )
        body.append("")
        body.extend(podcast_summary_matrix_markdown_lines(valid_items))
        body.append("")
        body.append("---")
        body.append("")

    for idx, pod in enumerate(valid_items):
        title = (pod.get("title") or "").strip()
        desc = (pod.get("description") or "").strip()
        body.append(f"## {title}")
        body.append("")
        if desc:
            body.append(desc.rstrip())
            body.append("")
        if idx < len(valid_items) - 1:
            body.append("---")
            body.append("")

    if disclaimer:
        if valid_items:
            body.append("---")
            body.append("")
        body.append(disclaimer)
        body.append("")

    return "\n".join(body).rstrip() + "\n"


def _open_source_table_cell(text: str) -> str:
    """Single-line table cell: collapse whitespace; avoid breaking GitHub pipe tables."""
    s = " ".join((text or "").split())
    return s.replace("|", "\\|")


def build_open_source_projects_markdown(data: dict | None) -> str:
    """Markdown for ``docs/open-source-projects.md`` from ``_data/open_source_projects.yaml``."""
    data = data or {}
    intro = (data.get("intro") or "").strip()
    disclaimer = (data.get("disclaimer") or "").strip()
    projects = data.get("projects") or []

    lines: list[str] = [
        "# Greek open source on GitHub",
        "",
        README_BACKLINK_MD,
        "",
    ]
    if intro:
        lines.append(intro.rstrip())
        lines.append("")
        lines.append("---")
        lines.append("")

    valid: list[dict] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        title = (p.get("title") or "").strip()
        url = (p.get("url") or "").strip()
        if not title or not url:
            continue
        valid.append(p)

    if valid:
        stats_map = load_open_source_github_stats_yaml(
            Path("_data/open_source_github_stats.yaml")
        )
        rows: list[tuple[dict, int | None, int | None]] = []
        for p in valid:
            stars: int | None = None
            forks: int | None = None
            parsed = parse_github_repo_url((p.get("url") or "").strip())
            if parsed:
                key = f"{parsed[0]}/{parsed[1]}"
                if key in stats_map:
                    stars, forks = stats_map[key]
            rows.append((p, stars, forks))
        rows.sort(key=lambda r: r[1] if r[1] is not None else -1, reverse=True)

        lines.append("## Projects")
        lines.append("")
        lines.append(
            "Repositories are **sorted by GitHub stars** (highest first). **Star** and **fork** counts come from "
            "`_data/open_source_github_stats.yaml` (run `just fetch-open-source-stats` to refresh them)."
        )
        lines.append("")
        lines.append("| Project | Stars | Forks | Description |")
        lines.append("| :------ | ----: | ----: | :---------- |")
        for p, stars, forks in rows:
            title = (p.get("title") or "").strip()
            url = (p.get("url") or "").strip()
            desc = _open_source_table_cell((p.get("description") or "").strip())
            link = f"[{title}]({url})"
            star_cell = format_compact_github_count(stars)
            fork_cell = format_compact_github_count(forks)
            lines.append(f"| {link} | {star_cell} | {fork_cell} | {desc} |")
        lines.append("")
        lines.append(
            "*Each description is one line in the table; open the repository for the full README, "
            "licence, and contribution guidelines.*"
        )
        lines.append("")

    if not valid:
        lines.append(
            "*No projects listed yet—add entries under `projects` in "
            "`_data/open_source_projects.yaml` and run `just readme`.*"
        )
        lines.append("")

    if disclaimer:
        if valid:
            lines.append("---")
            lines.append("")
        lines.append(disclaimer.rstrip())
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    lines.append("")
    return "\n".join(lines)


def _cafe_detail_label(key: str) -> str:
    return str(key).strip().rstrip(":")


def _cafe_cell_markdown(value: object) -> str:
    """Format a table cell: bare http(s) URLs become markdown links."""
    t = str(value).strip()
    if t.startswith(("http://", "https://")):
        parsed = urlparse(t)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        label = host or t
        return f"[{label}]({t})"
    return t


def build_remote_cafe_resources_markdown(
    data: dict | None, *, for_web_embed: bool = False
) -> str:
    """Markdown from ``_data/cafe_resources.yaml``.

    Default: full doc for ``docs/remote-cafe-resources.md`` (title + readme link).
    With ``for_web_embed=True``: body only, for HTML embedded under the Resources page hero
    (same generator as the docs file; no duplicate hand-maintained copy).
    """
    data = data or {}
    if for_web_embed:
        lines: list[str] = []
    else:
        lines = [
            "# Remote café & laptop-friendly workspaces",
            "",
            README_BACKLINK_MD,
            "",
        ]
    intro = (data.get("intro") or "").strip()
    if intro:
        lines.append(intro)
        lines.append("")

    raw_entries = data.get("entries") or []
    if not isinstance(raw_entries, list):
        raw_entries = []

    valid_entries: list[dict] = []
    for ent in raw_entries:
        if isinstance(ent, dict) and (ent.get("title") or "").strip():
            valid_entries.append(ent)

    if valid_entries:
        if lines:
            lines.append("---")
            lines.append("")

    for idx, ent in enumerate(valid_entries):
        title = (ent.get("title") or "").strip()
        kind = str(ent.get("kind") or "").strip().lower()
        url = (ent.get("url") or "").strip()

        lines.append(f"## {title}")
        lines.append("")

        if kind == "cafe" and url:
            lines.append(f"**Venue:** [{url}]({url})")
            lines.append("")

        loc = (ent.get("location") or "").strip()
        if loc:
            lines.append(f"*Location:* {loc}")
            lines.append("")

        desc = (ent.get("description") or "").strip()
        if desc:
            lines.append(desc)
            lines.append("")

        details = ent.get("details")
        if isinstance(details, dict) and details:
            lines.append("| | |")
            lines.append("| :--- | :--- |")
            for k, v in details.items():
                label = _cafe_detail_label(str(k))
                lines.append(f"| **{label}** | {_cafe_cell_markdown(v)} |")
            lines.append("")
        elif isinstance(details, str) and details.strip():
            lines.append(details.strip())
            lines.append("")

        note = (ent.get("note") or "").strip()
        if note:
            lines.append(note)
            lines.append("")

        if idx < len(valid_entries) - 1:
            lines.append("---")
            lines.append("")

    if not valid_entries:
        lines.append(
            "*No café resources yet—add `entries` to `_data/cafe_resources.yaml` "
            "and run `just readme`.*"
        )
        lines.append("")

    disclaimer = (data.get("disclaimer") or "").strip()
    if disclaimer:
        if valid_entries:
            lines.append("---")
            lines.append("")
        lines.append(disclaimer)
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    lines.append("")
    return "\n".join(lines)


def build_development_markdown(readme_data: dict) -> str:
    """Markdown for ``development.md`` (commands in fenced ``sh`` blocks)."""
    dev = readme_data.get("development")
    if not isinstance(dev, dict):
        return ""

    lines: list[str] = [
        "# Development",
        "",
        README_BACKLINK_MD,
        "",
    ]
    intro = (dev.get("intro") or "").strip()
    if intro:
        lines.append(intro)
        lines.append("")

    for blk in dev.get("blocks") or []:
        if not isinstance(blk, dict):
            continue
        title = (blk.get("title") or "").strip()
        commands = blk.get("commands")
        if not title or not commands:
            continue
        if isinstance(commands, str):
            cmd_text = commands.rstrip()
        else:
            cmd_text = "\n".join(str(c).rstrip() for c in commands if str(c).strip())
        if not cmd_text:
            continue
        lines.append(f"## {title}")
        lines.append("")
        note_before = (blk.get("note_before") or "").strip()
        if note_before:
            lines.append(note_before)
            lines.append("")
        lines.append("```sh")
        lines.append(cmd_text)
        lines.append("```")
        lines.append("")
        note = (blk.get("note") or "").strip()
        if note:
            lines.append(note)
            lines.append("")

    footer = (dev.get("footer") or "").strip()
    if footer:
        lines.append(footer)
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    lines.append("")
    return "\n".join(lines)


def generate() -> None:
    companies_data = load_companies()

    DOCS_MD_DIR.mkdir(parents=True, exist_ok=True)

    with README_YAML.open("r", encoding="utf-8") as f:
        readme_data = yaml.safe_load(f)

    with QUERIES_YAML.open("r", encoding="utf-8") as f:
        queries_data = yaml.safe_load(f)

    dev_md_body = build_development_markdown(readme_data)

    workable_counts_path = WORKABLE_COUNTS_YAML
    open_roles = 0
    if workable_counts_path.exists():
        with workable_counts_path.open("r", encoding="utf-8") as f:
            workable_data = yaml.safe_load(f) or {}
        if isinstance(workable_data, dict):
            maybe_total = workable_data.get("total_open")
            if isinstance(maybe_total, int):
                open_roles = maybe_total

    podcast_count = 0
    if PODCASTS_YAML.is_file():
        with PODCASTS_YAML.open("r", encoding="utf-8") as f:
            podcasts_data = yaml.safe_load(f) or {}
        if isinstance(podcasts_data, dict):
            plist = podcasts_data.get("podcasts")
            if isinstance(plist, list):
                podcast_count = len(plist)

    all_companies = sorted(companies_data, key=lambda x: x["name"].lower())

    seen: set[str] = set()
    duplicates = [
        c["name"] for c in all_companies if c["name"] in seen or seen.add(c["name"])
    ]
    if duplicates:
        names = ", ".join(set(duplicates))
        raise ValueError(f"Duplicate company names: {names}")

    total = len(all_companies)
    loc_counts = Counter(
        loc.strip().title() for c in all_companies for loc in c.get("locations", [])
    )
    top_loc, top_n = loc_counts.most_common(1)[0] if loc_counts else ("N/A", 0)

    policy_counts = Counter(
        c.get("work_policy", "N/A").strip().title() for c in all_companies
    )
    remote = policy_counts.get("Remote", 0)
    hybrid = policy_counts.get("Hybrid", 0)
    onsite = policy_counts.get("On-Site", 0) + policy_counts.get("Onsite", 0)

    sector_counts = Counter(
        s.strip() for c in all_companies for s in c.get("sectors", [])
    )
    top_sectors = sector_counts.most_common(5)

    repo = readme_data.get("repo", "leftkats/greek-software-ecosystem")
    live_url = readme_data.get("live_url", "")
    branding = readme_data.get("branding", {}) or {}
    _default_intro_line_2 = (
        "Community-curated directory with weekly open roles count updates."
    )
    if "intro_line_2" in branding:
        raw_intro_2 = branding["intro_line_2"]
        if raw_intro_2 is None:
            intro_line_2 = ""
        else:
            intro_line_2 = str(raw_intro_2).strip()
    else:
        intro_line_2 = _default_intro_line_2
    badges_cfg = readme_data.get("badges", {}) or {}
    stats_cfg = badges_cfg.get("stats", {}) or {}
    stats_style = stats_cfg.get("style", "for-the-badge")
    companies_color = stats_cfg.get("companies_color", "2563eb")
    open_roles_color = stats_cfg.get("open_roles_color", "f59e0b")
    remote_color = stats_cfg.get("remote_color", "16a34a")
    hybrid_color = stats_cfg.get("hybrid_color", "ca8a04")
    podcasts_color = stats_cfg.get("podcasts_color", "9333ea")
    meta_cfg = badges_cfg.get("meta", {}) or {}
    show_ci = bool(meta_cfg.get("show_ci", False))
    ci_workflow = meta_cfg.get("ci_workflow", "pr-validation.yaml")
    show_license = bool(meta_cfg.get("show_license", True))
    show_last_commit = bool(meta_cfg.get("show_last_commit", True))

    # ── Build README ────────────────────────────────────────
    lines: list[str] = []

    tagline = readme_data.get("tagline", "")
    lines.append('<p align="center">')
    lines.append(f"  {tagline}<br><br>")
    if live_url:
        cta = (readme_data.get("live_directory_cta") or "").strip()
        if not cta:
            cta = "Open the interactive directory"
        lines.append(
            f'  <a href="{escape(live_url, quote=True)}">'
            f"<strong>{escape(cta)}</strong></a><br>"
        )
    if intro_line_2:
        lines.append(f"  {intro_line_2}<br>")
    lines.append("  <br>")
    lines.append("  <br>")
    lines.append("</p>")
    lines.append("")

    lines.append('<p align="center">')
    companies_href = live_url or f"https://github.com/{repo}"
    open_roles_href = f"{live_url}?hire=1" if live_url else companies_href
    remote_href = f"{live_url}?pol=remote" if live_url else companies_href
    hybrid_href = f"{live_url}?pol=hybrid" if live_url else companies_href
    if live_url:
        base = live_url.rstrip("/")
        podcasts_href = f"{base}/podcasts"
    else:
        podcasts_href = (
            f"https://github.com/{repo}/blob/main/docs/{GREEK_TECH_PODCASTS_MD}"
        )
    lines.append(
        "  "
        f'<a href="{companies_href}">'
        f'<img src="https://img.shields.io/badge/Companies-{total}-{companies_color}?style={stats_style}" alt="Companies" /></a>'
    )
    lines.append(
        "  "
        f'<a href="{open_roles_href}">'
        f'<img src="https://img.shields.io/badge/Open%20Roles-{open_roles}-{open_roles_color}?style={stats_style}" alt="Open Roles" /></a>'
    )
    lines.append(
        "  "
        f'<a href="{remote_href}">'
        f'<img src="https://img.shields.io/badge/Remote-{remote}-{remote_color}?style={stats_style}" alt="Remote" /></a>'
    )
    lines.append(
        "  "
        f'<a href="{hybrid_href}">'
        f'<img src="https://img.shields.io/badge/Hybrid-{hybrid}-{hybrid_color}?style={stats_style}" alt="Hybrid" /></a>'
    )
    lines.append(
        "  "
        f'<a href="{podcasts_href}">'
        f'<img src="https://img.shields.io/badge/Podcasts-{podcast_count}-{podcasts_color}?style={stats_style}" alt="Podcasts" /></a>'
    )
    community_cfg = (readme_data.get("community") or {}).get("discord") or {}
    raw_inv = community_cfg.get("invite")
    discord_invite = str(raw_inv).strip() if raw_inv is not None else ""
    discord_href = ""
    if discord_invite:
        discord_badge_lbl = (
            str(community_cfg.get("badge_label") or "Community").strip() or "Community"
        )
        d_right = discord_badge_lbl.replace(" ", "%20")
        discord_color = str(community_cfg.get("color") or "5865F2").strip()
        # Static “Discord” label + configurable second segment (e.g. Community) + blurple.
        discord_badge_url = (
            f"https://img.shields.io/badge/Discord-{d_right}-{discord_color}?"
            f"style={stats_style}&logo=discord&logoColor=white"
        )
        # Discord invite slugs are unreserved path chars; keep e.g. "_" unencoded.
        enc_inv = quote(discord_invite, safe="-._~")
        discord_href = f"https://discord.gg/{enc_inv}"
        lines.append("  <!-- Set community.discord in _data/readme.yaml -->")
        lines.append(
            "  "
            f'<a href="{escape(discord_href, quote=True)}">'
            f'<img src="{escape(discord_badge_url, quote=True)}" '
            f'alt="Join us on Discord" /></a>'
        )
    lines.append("</p>")
    lines.append("")

    meta_badges: list[str] = []
    if show_ci:
        meta_badges.append(
            f'<a href="https://github.com/{repo}/actions/workflows/{ci_workflow}">'
            f'<img src="https://img.shields.io/github/actions/workflow/status/{repo}/{ci_workflow}?branch=main&logo=githubactions&label=CI" alt="CI" /></a>'
        )
    if show_license:
        meta_badges.append(
            f'<a href="https://github.com/{repo}/blob/main/LICENSE">'
            f'<img src="https://img.shields.io/github/license/{repo}?logo=github&label=License" alt="License" /></a>'
        )
    if show_last_commit:
        meta_badges.append(
            f'<img src="https://img.shields.io/github/last-commit/{repo}?logo=github&label=Last%20Commit" alt="Last Commit" />'
        )
    if meta_badges:
        lines.append('<p align="center">')
        for badge in meta_badges:
            lines.append(f"  {badge}")
        lines.append("</p>")
        lines.append("")

    lines.append("## Overview\n")
    lines.append(f"{readme_data['description'].strip()}\n")
    lines.append("")

    sec_str = ""
    if top_sectors:
        parts = [f"**{s}** ({n})" for s, n in top_sectors]
        sec_str = f" The most common sectors are {', '.join(parts)}."

    lines.append(
        f"Currently tracking **{total}** companies, "
        f"with **{top_loc}** as the leading hub "
        f"({top_n} offices). "
        f"**{remote}** teams are fully remote, "
        f"**{hybrid}** hybrid, and "
        f"**{onsite}** on-site."
        f"{sec_str}\n"
    )
    lines.append("")
    wpn = (
        readme_data.get("work_policy_notice") or ""
    ).strip() or DEFAULT_WORK_POLICY_NOTICE
    lines.append(f"{wpn}\n")
    lines.append("")
    gm_readme = (readme_data.get("generated_markdown") or {}).get("readme") or {}
    overview_links = (
        gm_readme.get("overview_links_paragraph") or _DEFAULT_README_OVERVIEW_LINKS
    ).strip()
    lines.append(overview_links + "\n")
    lines.append("")

    footer = readme_data.get("footer", {})
    lines.append("---\n")
    lines.append("## Contributors\n")
    lines.append(
        f"[![Contributors]"
        f"(https://contrib.rocks/image?repo={repo})]"
        f"(https://github.com/{repo}/graphs/contributors)\n"
    )
    if footer.get("description"):
        lines.append(f"{footer['description']}\n")
    lines.append("")

    if discord_href:
        lines.append("---\n")
        lines.append("## Community\n")
        raw_cdesc = community_cfg.get("description")
        if raw_cdesc is not None and str(raw_cdesc).strip():
            comm_body = str(raw_cdesc).strip().replace("{url}", discord_href)
        else:
            comm_body = _DEFAULT_README_COMMUNITY_DISCORD.format(url=discord_href)
        lines.append(comm_body + "\n")
        lines.append("")
        star_hist_href = f"https://star-history.com/#{repo}&Date"
        star_hist_src = f"https://api.star-history.com/svg?repos={repo}&type=Date"
        lines.append('<p align="center">')
        lines.append(
            "  "
            f'<a href="{escape(star_hist_href, quote=True)}">'
            f'<img src="{escape(star_hist_src, quote=True)}" '
            'alt="Star history chart" /></a>'
        )
        lines.append("</p>")
        lines.append("")

    if dev_md_body:
        lines.append("---\n")
        lines.append("## Development\n")
        dev_blurb = (
            (readme_data.get("generated_markdown") or {})
            .get("readme", {})
            .get("development_section_blurb")
            or _DEFAULT_README_DEV_BLURB
        ).strip()
        lines.append(dev_blurb + "\n")
        lines.append("")

    lines.append("---\n")
    lines.append("## Disclaimer\n")
    if readme_data.get("disclaimer"):
        lines.append(f"{readme_data['disclaimer'].strip()}\n")

    readme_text = "\n".join(lines) + "\n"
    ROOT_README.write_text(
        _readme_markdown_for_repository_root(readme_text),
        encoding="utf-8",
    )

    with (DOCS_MD_DIR / SEARCH_QUERIES_MD).open("w", encoding="utf-8") as f:
        f.write(build_search_queries_markdown(queries_data, readme_data))

    podcasts_data: dict = {}
    if PODCASTS_YAML.is_file():
        with PODCASTS_YAML.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                podcasts_data = loaded
    with (DOCS_MD_DIR / GREEK_TECH_PODCASTS_MD).open("w", encoding="utf-8") as f:
        f.write(build_greek_tech_podcasts_markdown(podcasts_data))

    osp_data: dict = {}
    if OPEN_SOURCE_PROJECTS_YAML.is_file():
        with OPEN_SOURCE_PROJECTS_YAML.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                osp_data = loaded
    with (DOCS_MD_DIR / OPEN_SOURCE_PROJECTS_MD).open("w", encoding="utf-8") as f:
        f.write(build_open_source_projects_markdown(osp_data))

    cafe_resources_data: dict = {}
    if CAFE_RESOURCES_YAML.is_file():
        with CAFE_RESOURCES_YAML.open("r", encoding="utf-8") as f:
            loaded_cafe = yaml.safe_load(f)
            if isinstance(loaded_cafe, dict):
                cafe_resources_data = loaded_cafe
    with (DOCS_MD_DIR / REMOTE_CAFE_RESOURCES_MD).open("w", encoding="utf-8") as f:
        f.write(build_remote_cafe_resources_markdown(cafe_resources_data))

    if dev_md_body:
        with (DOCS_MD_DIR / DEVELOPMENT_MD).open("w", encoding="utf-8") as f:
            f.write(dev_md_body)

    # ── Build engineering-hubs.md ───────────────────────────
    issue_chooser = f"https://github.com/{repo}/issues/new/choose"
    gm_eh = (readme_data.get("generated_markdown") or {}).get("engineering_hubs") or {}
    eh_title = (gm_eh.get("title") or _DEFAULT_EH_TITLE).strip()
    eh_intro = (gm_eh.get("intro") or _DEFAULT_EH_INTRO).strip()
    eh_disclaimer = _engineering_hubs_disclaimer_text(readme_data, issue_chooser)
    hubs: list[str] = [
        f"# {eh_title}\n",
        "\n",
        f"{eh_intro}\n",
        "\n",
        f"{eh_disclaimer}\n",
        "\n",
        "| # | Organization | Focus Sectors | Policy | Talent Portals |\n",
        "| :--- | :--- | :--- | :--- | :--- |\n",
    ]

    p_colors = {
        "remote": "brightgreen",
        "hybrid": "blue",
        "onsite": "orange",
        "on-site": "orange",
    }

    for idx, c in enumerate(all_companies, start=1):
        name_md = f"[{c['name']}]({c['url']})" if c.get("url") else c["name"]

        raw = c.get("work_policy", "N/A").strip().lower().replace("-", "")
        color = p_colors.get(raw, "lightgrey")
        pbadge = f"![](https://img.shields.io/badge/-{raw}-{color}?style=flat-square)"

        careers = f"[Careers]({c['careers_url']})" if c.get("careers_url") else "—"
        lid = c.get("linkedin_company_id", "")
        li = f"[LinkedIn](https://www.linkedin.com/company/{lid})" if lid else "—"

        sectors = ", ".join(f"`{s}`" for s in c.get("sectors", []))

        hubs.append(
            f"| {idx:02} | **{name_md}** | {sectors} | {pbadge} | {careers} · {li} |\n"
        )

    with (DOCS_MD_DIR / ENGINEERING_HUBS_MD).open("w", encoding="utf-8") as f:
        f.writelines(hubs)


if __name__ == "__main__":
    generate()
    print(
        "README.md (repo root), docs/search-queries-and-resources.md, "
        "docs/greek-tech-podcasts.md, docs/open-source-projects.md, "
        "docs/remote-cafe-resources.md, docs/development.md, and "
        "docs/engineering-hubs.md written successfully!"
    )
