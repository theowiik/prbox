.PHONY: dev format lint test check bench

dev:
	uv run uvicorn prbox.app:app --reload --port 8000

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest

check: lint test

# Measure how many frames/sec the render loop can actually produce at the
# configured panel size — run this on the Pi before trusting PRBOX_FPS.
bench:
	uv run python -m prbox.bench
