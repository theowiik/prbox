.PHONY: dev test format lint install

dev:
	cd server && uv run uvicorn prbox.app:app --reload --port 8000

test:
	cd server && uv run pytest

format:
	cd server && uv run ruff format .
	cd server && uv run ruff check --fix .

lint:
	cd server && uv run ruff check .

install:
	cd server && uv sync
