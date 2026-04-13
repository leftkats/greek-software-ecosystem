"""Generate ``readme.md`` and ``engineering-hubs.md`` from YAML sources."""

from __future__ import annotations

from collections import Counter

import yaml

from scripts.load_companies import (
    QUERIES_YAML,
    WORKABLE_COUNTS_YAML,
    load_companies,
)


def generate() -> None:
    companies_data = load_companies()

    with open("readme.yaml", "r", encoding="utf-8") as f:
        readme_data = yaml.safe_load(f)

    with QUERIES_YAML.open("r", encoding="utf-8") as f:
        queries_data = yaml.safe_load(f)

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
        "repo", "leftkats/awesome-greek-tech-jobs"
    )
    live_url = readme_data.get("live_url", "")
    branding = readme_data.get("branding", {}) or {}
    logo_cfg = branding.get("logo", {}) or {}
    logo_alt = logo_cfg.get("alt", "AWGJ")
    logo_light = logo_cfg.get("src_light", "assets/awgj.svg")
    logo_dark = logo_cfg.get("src_dark", logo_light)
    logo_width = int(logo_cfg.get("width", 180))
    intro_line_2 = branding.get(
        "intro_line_2",
        "Community-curated directory with weekly open roles count updates.",
    )
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
    lines.append(f"  {intro_line_2}")
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

    if live_url:
        lines.append(f"[**Explore the Live Directory**]({live_url})\n")
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

    lines.append("---\n")
    lines.append("## Company Directory\n")
    lines.append(
        "The full table lives in "
        "**[engineering-hubs.md](engineering-hubs.md)** "
        "— sortable by sector, policy, and talent portals.\n"
    )
    lines.append("")

    def _append_query_bullets(query_items: list) -> None:
        for q in query_items:
            name = (q.get("name") or "").strip()
            url = (q.get("url") or "").strip()
            desc = (q.get("description") or "").strip()
            if not name or not url:
                continue
            if desc:
                lines.append(f"- [{name}]({url}) — {desc}")
            else:
                lines.append(f"- [{name}]({url})")

    if queries_data:
        sections = queries_data.get("sections")
        legacy_queries = queries_data.get("queries")
        if sections or legacy_queries:
            lines.append("---\n")
            lines.append("## Useful Search Queries & Resources\n")
            lines.append(
                "Hand-picked links for Greek (and broader remote) job hunting. "
                "Each entry includes a short note on what you’ll find there.\n"
            )
            if sections:
                for sec in sections:
                    if not isinstance(sec, dict):
                        continue
                    title = (sec.get("title") or "").strip()
                    items = sec.get("queries") or []
                    if not items:
                        continue
                    if title:
                        lines.append(f"### {title}\n")
                    _append_query_bullets(items)
                    lines.append("")
            elif legacy_queries:
                _append_query_bullets(legacy_queries)
                lines.append("")

    footer = readme_data.get("footer", {})
    notes = footer.get("notes", [])
    if notes:
        lines.append("---\n")
        lines.append("## Tips & Notes\n")
        for n in notes:
            title = n["title"]
            if title.strip().lower() == "job counts":
                title = "Job Counts (Experimental)"
            body = n["content"].strip()
            lines.append(f"- **{title}:** {body}")
        lines.append("")

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

    dev_md = readme_data.get("development")
    if dev_md:
        lines.append("---\n")
        lines.append("## Development\n")
        lines.append(f"{str(dev_md).strip()}\n")
        lines.append("")

    lines.append("---\n")
    lines.append("## Disclaimer\n")
    if readme_data.get("disclaimer"):
        lines.append(f"{readme_data['disclaimer'].strip()}\n")

    with open("readme.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ── Build engineering-hubs.md ───────────────────────────
    hubs: list[str] = [
        "# Engineering Hubs & Career Portals\n",
        "\n",
        "Curated organizations, focus sectors, "
        "work policy, and talent links.\n",
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
    print("readme.md generated successfully!")
