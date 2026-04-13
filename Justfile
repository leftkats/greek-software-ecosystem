# Developer command interface for Awesome Greek Tech Jobs (uv underneath).
# List targets: `just` or `just --list`. Install just: https://github.com/casey/just

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# Default: show available recipes
default:
	@just --list

# Install / refresh Python dependencies. CI: `just sync --frozen`
setup *ARGS:
	uv sync {{ARGS}}

# Same as `setup` (common muscle memory for uv users).
sync *ARGS:
	uv sync {{ARGS}}

# Fetch Workable open-role counts into _data/workable_counts.yaml (network).
fetch:
	uv run python -m scripts.fetch_workable_counts

# Regenerate readme.md and engineering-hubs.md from YAML.
readme:
	uv run python -m scripts.generate_readme

# Regenerate index.html for the static directory UI.
index:
	uv run python -m scripts.generate_index

# Regenerate readme + engineering-hubs + index (no Workable fetch).
generate: readme index

# Refresh Workable snapshot, then regenerate readme, hubs, and index.
all:
	just fetch
	just generate

# Same checks as PR validation: regenerate readme then index (run after `just sync`).
check:
	uv run python -m scripts.generate_readme
	uv run python -m scripts.generate_index
