# prbox

<p align="center">
    <img src="assets/logo.png" alt="Logo" width="250px"/>
</p>

A fun little event display box. Uses an LED matrix on a Raspberry Pi to show events like server status, weather updates, and more. Comes with a web interface for control and live preview.

## Structure

```
server/   # FastAPI backend — display control and web preview
assets/   # Project assets (logo, diagrams)
```

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### Install

```bash
make install
```

### Run

```bash
make dev
```

Open http://localhost:8000 for the web preview, or http://localhost:8000/docs for the API documentation.

### Commands

| Command        | Description            |
| -------------- | ---------------------- |
| `make dev`     | Run development server |
| `make test`    | Run tests              |
| `make format`  | Format code with ruff  |
| `make lint`    | Lint code with ruff    |
| `make install` | Install dependencies   |

## Display Modes

Set `PRBOX_DISPLAY_MODE` to switch between display backends:

- **`dev`** (default) — prints to console, state available via web preview
- **`matrix`** — drives a real LED matrix on Raspberry Pi (not yet implemented)
