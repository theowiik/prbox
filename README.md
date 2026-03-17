# prbox

<p align="center">
    <img src="assets/logo.png" alt="Logo" width="250px"/>
</p>

A fun little event display box. LED matrix on a Raspberry Pi to show events — server status, weather, and more. Web interface for control and live preview.

## Quick Start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd server
make dev
```

Open http://localhost:8000 for the web preview, or `/docs` for API docs.

## Configuration

- `PRBOX_DISPLAY_MODE` — `dev` (default) or `matrix`
- `PRBOX_DISPLAY_WIDTH` — matrix width in pixels (default: 32)
- `PRBOX_DISPLAY_HEIGHT` — matrix height in pixels (default: 8)
