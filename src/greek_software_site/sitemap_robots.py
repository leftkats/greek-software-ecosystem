"""Write ``sitemap.xml`` and ``robots.txt`` for the static site."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

# Paths under site root. Index is ``origin/``.
_SITEMAP_ENTRIES: tuple[tuple[str, str], ...] = (
    ("", "1.0"),
    ("job-search.html", "0.95"),
    ("resources.html", "0.85"),
    ("podcasts.html", "0.85"),
    ("workspaces.html", "0.85"),
)


def write_sitemap_xml(repo_root: Path, site_origin: str) -> None:
    """Emit ``sitemap.xml`` for main pages (``site_origin`` from ``_data/readme.yaml``)."""
    origin = site_origin.rstrip("/")
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for relpath, priority in _SITEMAP_ENTRIES:
        loc = f"{origin}/" if not relpath else f"{origin}/{relpath}"
        lines.extend(
            [
                "  <url>",
                f"    <loc>{escape(loc)}</loc>",
                f"    <lastmod>{today}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    out = repo_root / "sitemap.xml"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots_txt(repo_root: Path, site_origin: str) -> None:
    """Emit ``robots.txt`` with ``Allow: /`` and the sitemap URL."""
    origin = site_origin.rstrip("/")
    text = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {origin}/sitemap.xml\n"
    )
    (repo_root / "robots.txt").write_text(text, encoding="utf-8")
