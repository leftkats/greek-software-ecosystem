# Development

← [README.md](../README.md)

Use [uv](https://github.com/astral-sh/uv) for Python and [just](https://github.com/casey/just) for short commands. Each block below is a fenced shell snippet you can copy into your terminal. `just index` writes `index.html`, `job-search.html` (remote jobs / employer directory + job-board links), `employers.html` (redirect to `job-search.html#employers`), `resources.html`, `podcasts.html`, `sitemap.xml`, and `robots.txt` (plus shared `assets/`) for the static site. Those files are gitignored on **`main`** (do not commit them); **`sitemap.xml`** / **`robots.txt`** are included only in the CI deploy to branch **`live`**. Branch **`live`** (GitHub Pages) holds the built site after CI.

## Install or refresh dependencies

```sh
just setup
just sync
```

In CI, use `just sync --frozen`.

## Regenerate readme, hubs, search-queries, and index (no Workable fetch)

```sh
just generate
```

## Fetch Workable counts, then regenerate everything

```sh
just all
```

## Refresh open source GitHub stars/forks (local or manual CI)

```sh
just open-source-stats-update
```

CI runs this automatically on the 1st of each month (`.github/workflows/open-source-stats-monthly.yaml`); use **Actions → Update open source GitHub stats → Run workflow** to trigger it manually.

## Refresh README star history chart (GitHub Actions)

```sh
gh workflow run star-history.yaml
```

Updates `assets/star-history.svg` and `assets/star-history-dark.svg` via [rust-star-history](https://github.com/Flux159/rust-star-history) (`.github/workflows/star-history.yaml`). Uses `GITHUB_TOKEN` in Actions; optional secret `STAR_HISTORY_TOKEN` (fine-grained PAT with read-only repo metadata) if you hit rate limits. Scheduled daily at 05:00 UTC; use **Actions → Star History → Run workflow** (or the command above) to refresh manually.

## Same checks as pull request validation

```sh
just check
```

## Jekyll (optional): build the live site bundle like CI

Requires Ruby/Bundler. Run `just index` first, then copy `index.html`, `employers.html`, `job-search.html`, `resources.html`, `podcasts.html`, `sitemap.xml`, `robots.txt`, and `assets/` into `jekyll-pages/` as in CI, then run:

```sh
uv run python -m greek_software_ecosystem.jekyll_url_config > jekyll-pages/_url.yml
cd jekyll-pages && bundle install && bundle exec jekyll build --config _config.yml,_url.yml
```

## Run script modules directly (equivalent to just recipes)

```sh
uv run python -m greek_software_ecosystem.generate_readme
uv run python -m greek_software_ecosystem.generate_index
uv run python -m greek_software_ecosystem.fetch_workable_counts
```

See [contributing.md](../contributing.md) for the full workflow and repository conventions.
