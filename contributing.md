# Contributing to Awesome Greek Tech Jobs

Thank you for wanting to improve this list! We love community contributions. To keep the repository organized, please follow these simple steps to add or update content.

## Repository Structure

This repository organizes its data under the `_data` directory. Below is a description of the files you can contribute to:

- **`_data/companies/`**: One YAML file per company (`.yaml`). Each file is a single mapping with the company name, sectors, careers page URL, LinkedIn company ID, and other fields. For the LinkedIn ID, open the company’s LinkedIn page and copy the segment after `/company/` (for example `https://www.linkedin.com/company/**company-id**/`).
- **`_data/queries.yaml`**: Predefined search queries and resources, grouped into sections. Each query has a name, URL, and optional description; sections appear as headings under “Useful Search Queries & Resources” in `readme.md`.

## How to Contribute via Pull Request

1. **Fork the Repository**: Click the 'Fork' button at the top right of the main page.
2. **Edit the Data Files**: Open the appropriate file(s) under `_data` in your fork.
3. **Add or Update Content**:
    - For **companies**: Add a new file under `_data/companies/` (for example `_data/companies/my-company.yaml`). Use a short ASCII filename (letters, numbers, hyphens); it only needs to be unique. The file must contain **one** company as a YAML mapping (not a list), for example:
      ```yaml
      name: Company Name
      url: https://www.company-website.com/
      sectors:
        - Sector Name
      careers_url: Careers full url
      linkedin_company_id: Company LinkedIn ID
      locations:
        - Athens
      work_policy: remote
      ```
    - For `_data/queries.yaml`: Add a new predefined search query:
      ```yaml
      - name: "Startup Pirate: Learn what matters in Greek tech and startups"
        url: https://startuppirate.gr/
      ```
4. **Commit Changes**: Use a clear commit message like `feat: add [Company Name] to _data/companies`.
5. **Create Pull Request**: Go back to the original repository and click "New Pull Request".
6. **Automated Review & Merge**: If your Pull Request passes the validation checks and follows the required format, our automated workflow will merge via a squash commit.

## How to Resolve an Issue

If you want to work on an open issue, follow this simple flow:

1. **Pick an issue**: Start with `good first issue` or `easy` labels if you are new.
2. **Comment on the issue**: Leave a short message like "I can work on this" to avoid duplicate work.
3. **Create a branch**: Use a clear branch name, for example `fix/workable-count-summary` or `docs/uv-quickstart`.
4. **Implement and test locally** (install [uv](https://github.com/astral-sh/uv) and [just](https://github.com/casey/just)):
   - `just setup` or `just sync` — install dependencies (use `just sync --frozen` to match CI lockfile)
   - `just generate` — regenerate `readme.md`, `engineering-hubs.md`, and `index.html` (writes `index.html` in the repo root; gitignored on `main`). **`sitemap.xml`** and **`robots.txt`** for the live site are produced by **Jekyll** (`jekyll-pages/`, plugin `jekyll-sitemap` + Liquid `robots.txt`) during CI before deploy to branch **`live`**. To run that locally: install Ruby/Bundler, copy `index.html` and `assets/` into `jekyll-pages/` like CI, then `uv run python scripts/jekyll_url_config.py > jekyll-pages/_url.yml` and `cd jekyll-pages && bundle install && bundle exec jekyll build --config _config.yml,_url.yml` (output in `jekyll-pages/_site/`).
   - (if needed) `just fetch` — refresh Workable counts (`_data/workable_counts.yaml`)

   Equivalent `uv` commands still work, for example `uv sync --frozen`, `uv run python -m scripts.generate_readme`, and `uv run python -m scripts.generate_index`.
5. **Open a PR linked to the issue**:
   - Include `Closes #<issue-number>` (or `Fixes #<issue-number>`) in the PR description so GitHub closes the issue automatically after merge.
   - Add a short summary of what changed and how you tested it.
6. **Address review feedback**: Push follow-up commits to the same branch until approved.

## Contribution Rules

* **Tech Focus Only**: Please only add companies, roles, or resources relevant to Computer/Software Engineering, Data, or Tech-Business roles. No mechanical, civil, or non-tech engineering.
* **Working Links**: Ensure all URLs provided are active and correct.
* **YAML Validation**: Make sure the YAML files are properly formatted and valid.
* **Descriptive Entries**: Provide clear and concise descriptions for roles and resources.

## GitHub Pages

Branch **`live`** holds **only** the built static site (HTML, **Jekyll-generated** `sitemap.xml` and `robots.txt`, page assets, and **`.nojekyll`** so GitHub Pages does not run Jekyll a second time on that branch). It is updated automatically on every push to **`main`**. Point **Settings → Pages** at **`live`** / **`/`**. Jekyll source for SEO files lives under **`jekyll-pages/`** on **`main`**.

## Workflow Automation

This repository uses GitHub Actions to validate contributions:
- **YAML Validation**: Ensures all YAML files are properly formatted.
- **Link Checker**: Verifies that all URLs are reachable.
- **Alphabetical Order Check**: Confirms that entries are sorted alphabetically.

Thank you for contributing to Awesome Greek Tech Jobs!
