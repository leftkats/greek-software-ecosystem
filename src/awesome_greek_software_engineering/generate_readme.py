"""Generate ``readme.md``, ``search-queries-and-resources.md``, ``development.md``, and ``engineering-hubs.md`` from YAML.

**Do not edit generated ``*.md`` files by hand.** Change ``readme.yaml``, ``_data/queries.yaml``,
company YAML under ``_data/companies/``, then run ``just readme`` (or ``just generate``).
"""

from __future__ import annotations

from collections import Counter
from html import escape

import yaml

from awesome_greek_software_engineering.load_companies import (
    QUERIES_YAML,
    WORKABLE_COUNTS_YAML,
    load_companies,
)

SEARCH_QUERIES_MD = "search-queries-and-resources.md"
DEVELOPMENT_MD = "development.md"

# Fallbacks when ``readme.yaml`` → ``generated_markdown`` omits a key.
_DEFAULT_SEARCH_QUERIES_INTRO = (
    "Hand-picked links for Greek (and broader remote) job hunting. "
    "Each entry includes a short note on what you’ll find there."
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
    "The sortable employer table is in "
    "**[engineering-hubs.md](engineering-hubs.md)** — sectors, work policy, "
    "and talent portals. "
    "Job search links, curated lists, and tips & notes live in "
    f"**[{SEARCH_QUERIES_MD}]({SEARCH_QUERIES_MD})**."
)
_DEFAULT_README_DEV_BLURB = (
    "Setup, regeneration commands, and CI checks are documented in "
    f"**[{DEVELOPMENT_MD}]({DEVELOPMENT_MD})** "
    "(copy-paste shell blocks)."
)


def _engineering_hubs_disclaimer_text(
    readme_data: dict, issue_chooser: str
) -> str:
    """Non-empty disclaimer paragraph for ``engineering-hubs.md`` (always written on each run)."""
    gm_eh = (readme_data.get("generated_markdown") or {}).get(
        "engineering_hubs"
    ) or {}
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
        "← [readme.md](readme.md)",
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


def build_development_markdown(readme_data: dict) -> str:
    """Markdown for ``development.md`` (commands in fenced ``sh`` blocks)."""
    dev = readme_data.get("development")
    if not isinstance(dev, dict):
        return ""

    lines: list[str] = [
        "# Development",
        "",
        "← [readme.md](readme.md)",
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
            cmd_text = "\n".join(
                str(c).rstrip() for c in commands if str(c).strip()
            )
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

    with open("readme.yaml", "r", encoding="utf-8") as f:
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

    all_companies = sorted(
        companies_data, key=lambda x: x["name"].lower()
    )

    seen: set[str] = set()
    duplicates = [
        c["name"]
        for c in all_companies
        if c["name"] in seen or seen.add(c["name"])
    ]
    if duplicates:
        names = ", ".join(set(duplicates))
        raise ValueError(f"Duplicate company names: {names}")

    total = len(all_companies)
    loc_counts = Counter(
        loc.strip().title()
        for c in all_companies
        for loc in c.get("locations", [])
    )
    top_loc, top_n = (
        loc_counts.most_common(1)[0] if loc_counts else ("N/A", 0)
    )

    policy_counts = Counter(
        c.get("work_policy", "N/A").strip().title()
        for c in all_companies
    )
    remote = policy_counts.get("Remote", 0)
    hybrid = policy_counts.get("Hybrid", 0)
    onsite = (
        policy_counts.get("On-Site", 0)
        + policy_counts.get("Onsite", 0)
    )

    sector_counts = Counter(
        s.strip()
        for c in all_companies
        for s in c.get("sectors", [])
    )
    top_sectors = sector_counts.most_common(5)

    repo = readme_data.get(
        "repo", "leftkats/awesome-greek-software-engineering"
    )
    live_url = readme_data.get("live_url", "")
    branding = readme_data.get("branding", {}) or {}
    logo_cfg = branding.get("logo", {}) or {}
    logo_alt = logo_cfg.get("alt", "AGSE")
    logo_light = logo_cfg.get("src_light", "assets/awgj.svg")
    logo_dark = logo_cfg.get("src_dark", logo_light)
    logo_width = int(logo_cfg.get("width", 180))
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
    meta_cfg = badges_cfg.get("meta", {}) or {}
    show_ci = bool(meta_cfg.get("show_ci", False))
    ci_workflow = meta_cfg.get("ci_workflow", "pr-validation.yaml")
    show_license = bool(meta_cfg.get("show_license", True))
    show_last_commit = bool(meta_cfg.get("show_last_commit", True))

    # ── Build README ────────────────────────────────────────
    lines: list[str] = []

    lines.append('<p align="center">')
    lines.append("  <br>")
    lines.append(
        f"  <img alt=\"{logo_alt}\" src=\"{logo_light}\" width=\"{logo_width}\" />"
    )
    lines.append("  <br>")
    lines.append("  <br>")
    lines.append("</p>")
    lines.append("")

    tagline = readme_data.get("tagline", "")
    lines.append('<p align="center">')
    lines.append(f"  {tagline}<br>")
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
    lines.append(
        "  "
        f"<a href=\"{companies_href}\">"
        f"<img src=\"https://img.shields.io/badge/Companies-{total}-{companies_color}?style={stats_style}\" alt=\"Companies\" /></a>"
    )
    lines.append(
        "  "
        f"<a href=\"{open_roles_href}\">"
        f"<img src=\"https://img.shields.io/badge/Open%20Roles-{open_roles}-{open_roles_color}?style={stats_style}\" alt=\"Open Roles\" /></a>"
    )
    lines.append(
        "  "
        f"<a href=\"{remote_href}\">"
        f"<img src=\"https://img.shields.io/badge/Remote-{remote}-{remote_color}?style={stats_style}\" alt=\"Remote\" /></a>"
    )
    lines.append(
        "  "
        f"<a href=\"{hybrid_href}\">"
        f"<img src=\"https://img.shields.io/badge/Hybrid-{hybrid}-{hybrid_color}?style={stats_style}\" alt=\"Hybrid\" /></a>"
    )
    lines.append("</p>")
    lines.append("")

    meta_badges: list[str] = []
    if show_ci:
        meta_badges.append(
            f"<a href=\"https://github.com/{repo}/actions/workflows/{ci_workflow}\">"
            f"<img src=\"https://img.shields.io/github/actions/workflow/status/{repo}/{ci_workflow}?branch=main&logo=githubactions&label=CI\" alt=\"CI\" /></a>"
        )
    if show_license:
        meta_badges.append(
            f"<a href=\"https://github.com/{repo}/blob/main/LICENSE\">"
            f"<img src=\"https://img.shields.io/github/license/{repo}?logo=github&label=License\" alt=\"License\" /></a>"
        )
    if show_last_commit:
        meta_badges.append(
            f"<img src=\"https://img.shields.io/github/last-commit/{repo}?logo=github&label=Last%20Commit\" alt=\"Last Commit\" />"
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
        sec_str = (
            f" The most common sectors are {', '.join(parts)}."
        )

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

    with open("readme.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(SEARCH_QUERIES_MD, "w", encoding="utf-8") as f:
        f.write(build_search_queries_markdown(queries_data, readme_data))

    if dev_md_body:
        with open(DEVELOPMENT_MD, "w", encoding="utf-8") as f:
            f.write(dev_md_body)

    # ── Build engineering-hubs.md ───────────────────────────
    issue_chooser = f"https://github.com/{repo}/issues/new/choose"
    gm_eh = (readme_data.get("generated_markdown") or {}).get("engineering_hubs") or {}
    eh_title = (gm_eh.get("title") or _DEFAULT_EH_TITLE).strip()
    eh_intro = (gm_eh.get("intro") or _DEFAULT_EH_INTRO).strip()
    eh_disclaimer = _engineering_hubs_disclaimer_text(
        readme_data, issue_chooser
    )
    hubs: list[str] = [
        f"# {eh_title}\n",
        "\n",
        f"{eh_intro}\n",
        "\n",
        f"{eh_disclaimer}\n",
        "\n",
        "| # | Organization | Focus Sectors "
        "| Policy | Talent Portals |\n",
        "| :--- | :--- | :--- | :--- | :--- |\n",
    ]

    p_colors = {
        "remote": "brightgreen",
        "hybrid": "blue",
        "onsite": "orange",
        "on-site": "orange",
    }

    for idx, c in enumerate(all_companies, start=1):
        name_md = (
            f"[{c['name']}]({c['url']})"
            if c.get("url")
            else c["name"]
        )

        raw = (
            c.get("work_policy", "N/A")
            .strip()
            .lower()
            .replace("-", "")
        )
        color = p_colors.get(raw, "lightgrey")
        pbadge = (
            "![](https://img.shields.io/badge/"
            f"-{raw}-{color}?style=flat-square)"
        )

        careers = (
            f"[Careers]({c['careers_url']})"
            if c.get("careers_url")
            else "—"
        )
        lid = c.get("linkedin_company_id", "")
        li = (
            "[LinkedIn]"
            f"(https://www.linkedin.com/company/{lid})"
            if lid
            else "—"
        )

        sectors = ", ".join(
            f"`{s}`" for s in c.get("sectors", [])
        )

        hubs.append(
            f"| {idx:02} | **{name_md}** "
            f"| {sectors} | {pbadge} "
            f"| {careers} · {li} |\n"
        )

    with open(
        "engineering-hubs.md", "w", encoding="utf-8"
    ) as f:
        f.writelines(hubs)


if __name__ == "__main__":
    generate()
    print(
        "readme.md, search-queries-and-resources.md, development.md, "
        "and engineering-hubs.md generated successfully!"
    )
