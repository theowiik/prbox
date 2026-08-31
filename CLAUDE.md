# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `server/` via Makefile. Uses uv for package management.

- `make dev` — run dev server (FastAPI + uvicorn, port 8000, auto-reload)
- `make check` — lint + tests
- `make format` — format and autofix with ruff
- `make bench` — measure scene render throughput at the configured panel size
- `uv run pytest tests/test_render.py::test_long_text_scrolls` — run a single test

## Project Structure

```
server/                        # FastAPI backend (uv-managed, hatchling build)
├── Makefile                   # dev, format, lint, test, check, bench
├── pyproject.toml             # Dependencies, ruff config, pytest config
├── src/prbox/                 # Source package (src layout)
│   ├── app.py                 # create_app(), lifespan, router registration
│   ├── config.py              # Settings/MatrixOptions dataclasses from PRBOX_* env
│   ├── controller.py          # DisplayController — API-facing state + scene switching
│   ├── bench.py               # `make bench` — per-scene fps measurement
│   ├── render/                # Everything that turns state into pixels
│   │   ├── engine.py          # RenderEngine — fixed-rate loop, crossfade, gamma, fan-out
│   │   ├── frame.py           # Frame buffer, colour conversion, subpixel text drawing
│   │   ├── font.py            # 5x7 bitmap font (single source of truth)
│   │   ├── noise.py           # ValueNoise — animated value noise + fbm
│   │   ├── life.py            # Conway's Game of Life rules (no rendering)
│   │   └── scenes.py          # Blank/Text/Rainbow/Life/Solid scenes
│   ├── display/               # Frame sinks
│   │   ├── base.py            # Display protocol + DisplayState pydantic model
│   │   ├── dev.py             # DevDisplay — holds latest frame, optional TTY preview
│   │   └── matrix.py          # MatrixDisplay — rpi-rgb-led-matrix (lazy import)
│   ├── sources/               # Event sources that feed the display
│   │   ├── base.py            # Source protocol + SourcePayload
│   │   └── weather.py         # MockWeather — bucketed fake weather data
│   ├── routers/
│   │   ├── display.py         # /api/display/*, /ws/display, GET /
│   │   └── sources.py         # /api/sources/*
│   └── web/index.html         # Web dashboard + live panel preview
└── tests/
    ├── conftest.py            # TestClient + settings fixtures
    ├── test_api.py            # HTTP + WebSocket integration tests
    ├── test_render.py         # Frame, font, noise, scene unit tests
    ├── test_life.py           # Life rules, LifeScene, and its endpoint
    ├── test_engine.py         # Render loop and controller tests
    ├── test_config.py         # Env parsing and validation
    └── test_sources.py        # Weather source tests
assets/                        # Project assets (logo, diagrams)
```

## Architecture

Monorepo with one package (`server/`) using src layout (`server/src/prbox/`).

**The server renders pixels, not text.** This is the central design decision.
`render/` rasterises the active scene into an RGB `Frame`; both the LED matrix
and the browser preview consume those finished frames. Nothing downstream knows
about fonts or layout, so the preview cannot drift from the hardware. (It used
to: the 5x7 font was duplicated in JavaScript, and the browser and the panel
disagreed about overflow.)

**Render loop** — `RenderEngine` runs one asyncio task on a fixed-interval
clock. Each tick it renders the active scene, crossfades from the outgoing
scene if one is still fading, applies a gamma + brightness LUT, pushes the
result to the display backend, and fans it out to WebSocket subscribers. Even
pacing matters more than raw frame rate for how smooth the panel looks, so the
loop tracks absolute deadlines and resyncs rather than burst-catching-up when
it falls behind. A failing display backend is logged, not fatal.

**Stateful scenes** — `LifeScene` is the exception that proves the rule. Life
is inherently stateful, but it still presents a pure `render(frame, t)`: the
generation number is derived from `t`, and rewinding `t` replays from the seed
deterministically. Generations tick a few times a second while the loop runs at
30fps, so births fade in and deaths fade out across each tick. Small boards
stagnate quickly, so a board that repeats a recent state or dies out is
reseeded. The rules live in `render/life.py` with no rendering in them, so they
can be tested against gliders and blinkers directly.

**Scenes** — a `Scene` is anything with a `name` and `render(frame, t)`, where
`t` is seconds since the scene became active (Protocol, structural subtyping).
Scenes are stateless with respect to wall-clock time, which makes them trivial
to test at arbitrary `t`. `TextScene` centres text that fits and scrolls text
that doesn't, at fractional pixel offsets — `Frame.draw_text` accepts a float
`x` and splits each glyph column across two pixel columns.

**Performance** — the target is a Raspberry Pi, so the scene inner loops are
written for speed over elegance: `RainbowScene` uses a precomputed HSV palette
LUT, samples noise on a coarse grid and interpolates, and writes pixels as byte
slices. `make bench` reports what the current device sustains; run it on the Pi
before raising `PRBOX_FPS`.

**Displays** — `Display` (`display/base.py`) is a Protocol with `push_frame`
and `close`. `DevDisplay` keeps the latest frame and can draw the panel in the
terminal with truecolor half-blocks (`PRBOX_TTY_PREVIEW=1`). `MatrixDisplay`
drives real HUB75 hardware via `rgbmatrix`, imported lazily so the module still
imports off-device; it writes to an offscreen canvas and swaps on vsync.

**Configuration** — `Settings.from_env()` reads every `PRBOX_*` variable and
validates it at startup, so a typo fails loudly instead of silently rendering
at the wrong size. `create_app(settings)` takes an explicit `Settings` so tests
never touch the environment.

**App lifecycle** — `create_app()` builds the display, engine, controller and
sources in the lifespan handler and stores them on `app.state`. Routers reach
them through `Depends` accessors. The engine is stopped and the display closed
on shutdown.

**Event sources** — pluggable data producers (`sources/`) exposing a
`SourcePayload` with `display_text` and `display_color`. `MockWeather` is
deterministic per 5-minute bucket and per city. The frontend polls a source and
pushes its payload to `/api/display/text`.

**API** — display routes under `/api/display`:

- `GET /api/display` — current `DisplayState` (scene, text, colour, brightness, size, fps)
- `GET /api/display/frame` — latest frame as base64 RGB (non-WebSocket fallback)
- `POST /api/display/text` — `{"text": "...", "color": "#RRGGBB"}`
- `POST /api/display/rainbow` — `{"speed", "blobs", "noise", "saturation"}`
- `POST /api/display/life` — `{"speed", "density", "hue"}`
- `POST /api/display/solid` — `{"color": "#RRGGBB"}`
- `POST /api/display/clear`
- `POST /api/display/brightness` — `{"brightness": 0.0-1.0}`
- `WS /ws/display` — a JSON `hello` with panel size and fps, then raw RGB frames

`GET /` serves `web/index.html`; `/docs` is auto-generated.

**Web preview** — the page opens the WebSocket, draws each frame as round
"LEDs" on a canvas with a cheap radial-gradient bloom, and reconnects with
exponential backoff. It contains no rendering logic beyond scaling pixels up.

**Testing** — `tests/conftest.py` builds an app from an explicit `Settings` per
test. Async engine tests use `@pytest.mark.anyio` with the `anyio_backend`
fixture. Scene tests assert on frame contents rather than on state flags.

## Code Style

- Ruff with line-length 88, rules: E, F, I, UP, B (`fastapi.Depends` etc. exempted from B008)
- Python 3.12+, type hints, Pydantic v2 models for API schemas
- Protocols for abstractions (structural subtyping, no base class inheritance needed)
- Request/response models defined in the router file that uses them, domain models in their own module
- Comments explain *why*, especially where code is shaped by hardware constraints
