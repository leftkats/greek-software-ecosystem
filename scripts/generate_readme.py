"""Generate ``readme.md`` and ``engineering-hubs.md`` from YAML sources."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml


def generate() -> None:
    with open("data/companies.yaml", "r", encoding="utf-8") as f:
        companies_data = yaml.safe_load(f)

    with open("readme.yaml", "r", encoding="utf-8") as f:
        readme_data = yaml.safe_load(f)

    with open("data/queries.yaml", "r", encoding="utf-8") as f:
        queries_data = yaml.safe_load(f)

    workable_counts_path = Path("data/workable_counts.yaml")
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

    # ── Build README ────────────────────────────────────────
    lines: list[str] = []

    lines.append(f"# {readme_data['title']}\n")
    tagline = readme_data.get("tagline", "")
    lines.append(f"> {tagline}\n")
    lines.append("")

    badge = (
        "![Companies]"
        f"(https://img.shields.io/badge/Companies-{total}"
        "-blue?style=for-the-badge) "
        "![Hub]"
        f"(https://img.shields.io/badge/Hub-{top_loc}"
        "-red?style=for-the-badge) "
        "![Remote]"
        f"(https://img.shields.io/badge/Remote-{remote}"
        "-green?style=for-the-badge) "
        "![Hybrid]"
        f"(https://img.shields.io/badge/Hybrid-{hybrid}"
        "-yellow?style=for-the-badge) "
        "![Open Roles]"
        f"(https://img.shields.io/badge/Open%20Roles-{open_roles}"
        "-orange?style=for-the-badge)"
    )
    lines.append(badge)
    lines.append("")

    if live_url:
        lines.append(
            f"[**Explore the Live Directory**]({live_url})\n"
        )
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

    if queries_data and "queries" in queries_data:
        lines.append("---\n")
        lines.append("## Useful Search Queries\n")
        for q in queries_data["queries"]:
            lines.append(f"- [{q['name']}]({q['url']})")
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

    lines.append("---\n")
    lines.append("## Disclaimer\n")
    if readme_data.get("disclaimer"):
        lines.append(
            f"{readme_data['disclaimer'].strip()}\n"
        )

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
