# Development

← [README.md](README.md)

Use [uv](https://github.com/astral-sh/uv) for Python and [just](https://github.com/casey/just) for short commands. Each block below is a fenced shell snippet you can copy into your terminal. `just index` writes `index.html`, `job-search.html` (employer directory + job-board links), `employers.html` (redirect to `job-search.html#employers`), `resources.html`, `podcasts.html`, `sitemap.xml`, and `robots.txt` (plus shared `assets/`) for the static site. Those files are gitignored on **`main`**; branch **`live`** (GitHub Pages) holds the built site after CI.

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

## Same checks as pull request validation

```sh
just check
```

## Jekyll (optional): build the live site bundle like CI

Requires Ruby/Bundler. Run `just index` first, then copy `index.html`, `employers.html`, `job-search.html`, `resources.html`, `podcasts.html`, `sitemap.xml`, `robots.txt`, and `assets/` into `jekyll-pages/` as in CI, then run:

```sh
uv run python -m awesome_greek_software_engineering.jekyll_url_config > jekyll-pages/_url.yml
cd jekyll-pages && bundle install && bundle exec jekyll build --config _config.yml,_url.yml
```

## Run script modules directly (equivalent to just recipes)

```sh
uv run python -m awesome_greek_software_engineering.generate_readme
uv run python -m awesome_greek_software_engineering.generate_index
uv run python -m awesome_greek_software_engineering.fetch_workable_counts
```

See [contributing.md](../contributing.md) for the full workflow and repository conventions.
