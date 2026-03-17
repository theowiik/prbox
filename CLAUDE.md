# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the repo root via Makefile. Server code lives in `server/` and uses uv.

- `make dev` — run dev server (FastAPI + uvicorn, port 8000, auto-reload)
- `make test` — run all tests
- `make format` — format and autofix with ruff
- `make lint` — lint check with ruff
- `make install` — install dependencies (`uv sync` in server/)
- `cd server && uv run pytest tests/test_display.py::test_show_text` — run a single test

## Project Structure

```
server/                        # FastAPI backend (uv-managed, hatchling build)
├── pyproject.toml             # Dependencies, ruff config, pytest config
├── src/prbox/                 # Source package (src layout)
│   ├── app.py                 # FastAPI app creation, lifespan, router registration
│   ├── config.py              # Environment-based config (PRBOX_DISPLAY_MODE)
│   ├── display/               # Display abstraction layer
│   │   ├── base.py            # Display protocol + DisplayState pydantic model
│   │   ├── dev.py             # DevDisplay — console output + in-memory state for web preview
│   │   └── matrix.py          # MatrixDisplay — Raspberry Pi LED matrix (placeholder)
│   └── routers/
│       └── display.py         # API routes (/api/display/*) + inline HTML preview page
└── tests/
    └── test_display.py        # API integration tests using FastAPI TestClient
assets/                        # Project assets (logo, diagrams)
```

## Architecture

Monorepo with one package (`server/`) using src layout (`server/src/prbox/`).

**Display abstraction** — the core pattern is a `Display` protocol (`display/base.py`) with two backends:
- `DevDisplay` (`display/dev.py`) — prints to console, stores state in memory for the web preview
- `MatrixDisplay` (`display/matrix.py`) — placeholder for real Raspberry Pi LED matrix hardware

New display backends implement the `Display` protocol methods: `show_text`, `clear`, `set_brightness`, `get_state`. No base class inheritance needed — structural subtyping via Protocol.

`DisplayState` (pydantic model in `base.py`) is the shared state representation returned by `get_state()` and serialized directly as the API response.

**App lifecycle** — the display instance is created in the FastAPI lifespan handler (`app.py`) and stored on `app.state.display`. The active backend is selected at startup via `PRBOX_DISPLAY_MODE` env var (`dev` or `matrix`, defaults to `dev`). Routers access it via a `Depends(_get_display)` dependency that reads from `request.app.state`.

**Web preview** — `GET /` serves an inline HTML page (string constant in `routers/display.py`) that polls `GET /api/display` every second and renders a visual LED matrix simulator with text input, color picker, and brightness slider. API docs are auto-generated at `/docs`.

**API routes** — all under `/api/display`:
- `GET /api/display` — returns current `DisplayState` as JSON
- `POST /api/display/text` — `{"text": "...", "color": "#RRGGBB"}` (color defaults to `#00FF00`)
- `POST /api/display/clear` — clears displayed text
- `POST /api/display/brightness` — `{"brightness": 0.0-1.0}`

**Testing** — tests use `fastapi.testclient.TestClient` with a pytest fixture that creates a fresh client (and thus a fresh `DevDisplay`) per test for isolation.

## Code Style

- Ruff with line-length 88, rules: E, F, I (pyflakes, pycodestyle, isort)
- Python 3.12+, type hints, Pydantic v2 models for API schemas
- Protocols for abstractions (structural subtyping, no base class inheritance needed)
- Request/response models defined in the router file that uses them (e.g. `ShowTextRequest` in `routers/display.py`), domain models in their own module (e.g. `DisplayState` in `display/base.py`)
