# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from `box/` via Makefile. Uses uv for package management.

- `make dev` — run dev server (FastAPI + uvicorn, port 8000, auto-reload)
- `make check` — lint + tests
- `make format` — format and autofix with ruff
- `make bench` — measure scene render throughput at the configured panel size
- `uv run pytest tests/test_render.py::test_long_text_scrolls` — run a single test

## Project Structure

Monorepo. `box/` is the box; `connectors/` are separate projects that talk to it
over HTTP and are never installed on the Pi.

```
box/                               # The box itself (uv-managed, hatchling build)
├── Makefile                       # dev, serve, format, lint, test, check, bench
├── pyproject.toml                 # Dependencies, ruff config, pytest config
├── .python-version                # Pins the interpreter (3.14.7) for uv
├── src/box/
│   │                              # ── core: never imports a web framework ──
│   ├── config.py                  # Settings/MatrixOptions from BOX_* env
│   ├── state.py                   # PanelState — what is on screen right now
│   ├── events.py                  # Event contract: SceneSpec union, priorities, styling
│   ├── scheduler.py               # Scheduler — priorities, queue, ambient rotation
│   ├── bench.py                   # `make bench` — per-scene fps measurement
│   ├── __main__.py                # `python -m box` / `box` console script
│   ├── render/                    # Turning state into pixels
│   │   ├── engine.py              # RenderEngine — fixed-rate loop, crossfade, gamma
│   │   ├── frame.py               # Frame buffer, colour conversion, subpixel text
│   │   ├── font.py                # 5x7 bitmap font (single source of truth)
│   │   └── scenes.py              # Blank/Text/Frames/Solid — the whole set
│   ├── display/                   # Output devices — frame sinks
│   │   ├── protocol.py            # Display protocol
│   │   ├── dev.py                 # DevDisplay — latest frame + optional TTY preview
│   │   └── matrix.py              # MatrixDisplay — rpi-rgb-led-matrix (lazy import)
│   ├── sources/                   # On-box producers: run on the Pi, emit Events
│   │   ├── protocol.py            # Source protocol (poll() -> Event | None)
│   │   ├── runner.py              # SourceRunner — polls sources headlessly
│   │   └── weather.py             # MockWeather — reference on-box source
│   │                              # ── interface: the only layer with FastAPI ──
│   └── api/
│       ├── app.py                 # create_app(), lifespan, router registration
│       ├── auth.py                # Bearer-token dependency for writes
│       ├── routes/
│       │   ├── events.py          # POST/DELETE /api/events — the connector API
│       │   ├── panel.py           # /api/display/*, /ws/display, GET /
│       │   └── sources.py         # /api/sources/*
│       └── web/index.html         # Dashboard + live panel preview
└── tests/
    ├── conftest.py                # TestClient + settings fixtures
    ├── test_architecture.py       # Enforces the core/interface boundary
    ├── test_events_api.py         # /api/events contract, auth, animation upload
    ├── test_scheduler.py          # Priorities, coalescing, ambient rotation
    ├── test_api.py                # Panel state, WebSocket, dashboard routes
    ├── test_render.py             # Frame, font, scene, FramesScene tests
    ├── test_engine.py             # Render loop
    ├── test_config.py             # Env parsing and validation
    └── test_sources.py            # Weather source tests
connectors/                        # Separate projects; never installed on the Pi
├── gifcast/                       # Sends a GIF
│   └── src/gifcast/
│       ├── convert.py             # GIF -> panel-sized RGB frames
│       ├── client.py              # Thin HTTP wrapper (the API needs no SDK)
│       └── cli.py                 # `gifcast party.gif`
└── boxdemo/                       # Generative visuals, rendered on the sender
    └── src/boxdemo/
        ├── canvas.py              # Its own RGB buffer + hsv_to_rgb
        ├── noise.py               # ValueNoise — animated value noise + fbm
        ├── life.py                # Conway's Game of Life rules
        ├── scenes.py              # rainbow_frames / life_frames / gradient_frames
        └── cli.py                 # `boxdemo rainbow`
assets/                            # Project assets (logo, diagrams)
```

## Architecture

**The core/interface boundary is the main structural rule.** `box.api` owns
everything HTTP — FastAPI, auth, the dashboard. Every other module is the box
itself and must stay importable with no web framework installed, so the core is
testable in isolation and could later be driven by something other than HTTP.
`tests/test_architecture.py` enforces this by parsing imports; it fails if a core
module reaches for `fastapi`, `starlette`, `uvicorn`, or `box.api`.

`PanelState` lives in `state.py`, not beside the `Display` protocol: `display/`
is about *devices that consume frames*, while `PanelState` is the scheduler's
answer to *what is on screen*. Conflating them was the old `DisplayState`.

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

**The core renders text and pixels, nothing else.** `scenes.py` ships only
Blank, Text, Frames and Solid. Generative visuals (rainbow gradients, Game of
Life) are *content*: they live in `connectors/boxdemo`, render frames locally,
and arrive as ordinary `frames` events. This is why the box has no `hsv_to_rgb`,
no noise, and no Life rules — a new visual needs no change on the Pi. Connectors
never import the box package; boxdemo carries its own `canvas.py`, the same way
gifcast depends on Pillow.

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
before raising `BOX_FPS`.

**Displays** — `Display` (`display/base.py`) is a Protocol with `push_frame`
and `close`. `DevDisplay` keeps the latest frame and can draw the panel in the
terminal with truecolor half-blocks (`BOX_TTY_PREVIEW=1`). `MatrixDisplay`
drives real HUB75 hardware via `rgbmatrix`, imported lazily so the module still
imports off-device; it writes to an offscreen canvas and swaps on vsync.

**Configuration** — `Settings.from_env()` reads every `BOX_*` variable and
validates it at startup, so a typo fails loudly instead of silently rendering
at the wrong size. `create_app(settings)` takes an explicit `Settings` so tests
never touch the environment.

**App lifecycle** — `create_app()` builds the display, engine, scheduler, sources
and runner in the lifespan handler and stores them on `app.state`. Routers reach
them through `Depends` accessors. Everything is stopped in reverse on shutdown.

**Events and the scheduler** — the central idea. `set_scene` is last-write-wins,
which is fine for a control panel and useless for a box several independent
services push to. `Scheduler` owns *what is on screen now*: `alert` preempts (and
the interrupted event resumes with its remaining time), `normal` queues, `ambient`
joins an idle rotation. One pending event per source, so a burst coalesces.

**Presentation lives on the box, not in connectors.** A connector sends `source`,
`text` and `priority`; `events.py` maps source to colour and priority to duration.
Restyling every integration is one edit there instead of redeploying each one.

**Connectors are separate projects.** They run wherever the data is — a Discord
listener belongs on a desktop, not the Pi — and talk to `/api/events` over HTTP.
The split is by *availability*, not mechanism: anything that must still be on
screen when the desktop sleeps (weather, clock) runs on the Pi as a `Source`, but
goes through the identical event path.

**On-box sources** — `SourceRunner` polls them on a timer and submits ambient
events. This is what makes the box work headless; previously the dashboard's
JavaScript ran that timer, so closing the tab froze the panel.

**API** — `/api/events` is the contract; `/api/display/*` is dashboard sugar over it.

- `POST /api/events` — the one endpoint connectors use
- `DELETE /api/events` — drop the queue
- `GET /api/display` — current `DisplayState` (scene, source, queued, ambient, …)
- `GET /api/display/frame` — latest frame as base64 RGB (non-WebSocket fallback)
- `POST /api/display/text` — `{"text": "...", "color": "#RRGGBB"}`

Writes take an optional bearer token (`BOX_TOKEN`); reads stay open so the
dashboard loads before it knows the token. The server binds `0.0.0.0` by default
because connectors are on other machines.
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
- Python 3.14+ (pinned to 3.14.7 in `.python-version`), type hints, Pydantic v2 models
- Deferred annotations (PEP 649) are on by default, so forward references need no quotes
- Protocols for abstractions (structural subtyping, no base class inheritance needed)
- Request/response models defined in the router file that uses them, domain models in their own module
- Comments explain *why*, especially where code is shaped by hardware constraints
