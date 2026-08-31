.PHONY: dev serve format lint test check bench

# Bound to all interfaces: connectors run on other machines (desktop, tailnet),
# so loopback-only would make the box unreachable.
dev:
	uv run uvicorn box.api.app:app --reload --host 0.0.0.0 --port 8000

# What runs on the Pi. Host, port and everything else come from BOX_* env.
serve:
	uv run python -m box

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
# configured panel size — run this on the Pi before trusting BOX_FPS.
bench:
	uv run python -m box.bench
