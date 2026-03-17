.PHONY: dev format

dev:
	uv run uvicorn prbox.app:app --reload --port 8000

format:
	uv run ruff format .
	uv run ruff check --fix .
