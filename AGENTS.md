# AGENTS.md

Guidance for coding agents (and humans) working in this repository.

## Commands

Uses uv for package management. The root Makefile is the front door — nothing
needs installing or configuring first:

- `make dev` — run the box (port 8000, auto-reload, emulated panel at `/emulator`)
- `make demo` / `make demo VISUAL=beer` — play a built-in visual
- `make gif GIF=party.gif` — send a GIF
- `make check` / `make format` — the box *and* gifcast

Inside `box/` the same targets cover the box alone, plus:

- `make serve` — what runs on the Pi; host/port from `BOX_*`
- `make bench` — measure scene render throughput at the configured panel size
- `uv run pytest tests/test_render.py::test_long_text_scrolls` — run a single test

## Project Structure

Monorepo. `box/` is the box and runs on the Pi; `connectors/` are separate
projects that talk to it over HTTP and are never installed on the Pi. See
"What runs where" below for which side something belongs on.

```
Makefile                           # dev, demo, gif, check, format — the front door
box/                               # The box itself (uv-managed, hatchling build)
├── Makefile                       # dev, serve, format, lint, test, check, bench
├── pyproject.toml                 # Pi runtime deps (only), ruff, pytest config
├── .python-version                # Pins the interpreter (3.14.8) for uv
├── deploy/box.service             # systemd unit for the Pi
├── src/box/
│   │                              # ── core: never imports a web framework ──
│   ├── config.py                  # Settings/MatrixOptions from BOX_* env
│   ├── state.py                   # PanelState — what is on screen right now
│   ├── events.py                  # Event contract: SceneSpec union, priorities, styling
│   ├── logs.py                    # LogBuffer + logging bridge — the debug view's tail
│   ├── scheduler.py               # Scheduler — priorities, queue, ambient rotation
│   ├── bench.py                   # `make bench` — per-scene fps measurement
│   ├── __main__.py                # `python -m box` / `box` console script
│   ├── render/                    # Turning state into pixels
│   │   ├── engine.py              # RenderEngine — fixed-rate loop, crossfade, gamma
│   │   ├── frame.py               # Frame buffer, colour conversion, subpixel text
│   │   ├── font.py                # 5x7 bitmap font (single source of truth)
│   │   └── scenes.py              # Blank/Text/Frames/Solid — the whole set
│   ├── visuals/                   # Built-in animations, pre-rendered to frames
│   │   ├── __init__.py            # VISUALS registry + cached frames(name, w, h)
│   │   ├── animations.py          # rainbow / life / gradient / beer generators
│   │   ├── life.py                # Conway's Game of Life rules
│   │   ├── noise.py               # ValueNoise — animated value noise + fbm
│   │   └── color.py               # hsv_to_rgb
│   ├── display/                   # Output devices — frame sinks
│   │   ├── protocol.py            # Display protocol
│   │   ├── emulator.py            # EmulatorDisplay — no hardware; + TTY preview
│   │   └── matrix.py              # MatrixDisplay — the ONLY hardware code (lazy)
│   ├── sources/                   # On-box producers: run on the Pi, emit Events
│   │   ├── protocol.py            # Source protocol (name, interval, poll())
│   │   ├── runner.py              # SourceRunner — a loop per source, off-loop polls
│   │   ├── feeds.py               # FEEDS + FeedSource — RSS/Atom, seen-state on disk
│   │   └── weather.py             # MockWeather — reference on-box source
│   │                              # ── interface: the only layer with FastAPI ──
│   └── api/
│       ├── app.py                 # create_app(), lifespan, router registration
│       ├── auth.py                # Bearer-token dependency for writes
│       ├── routes/
│       │   ├── events.py          # POST/DELETE /api/events — the connector API
│       │   ├── logs.py            # /api/logs, /ws/logs — recent lines and events
│       │   ├── panel.py           # /api/display/*, /ws/display, GET /
│       │   └── sources.py         # /api/sources/*
│       └── web/
│           ├── index.html         # Dashboard + live panel preview
│           └── emulator.html      # The panel alone, pixel for pixel
└── tests/
    ├── conftest.py                # TestClient + settings fixtures
    ├── test_architecture.py       # Core/interface boundary + hardware boundary
    ├── test_events_api.py         # /api/events contract, auth, animation upload
    ├── test_scheduler.py          # Priorities, coalescing, ambient rotation
    ├── test_api.py                # Panel state, WebSocket, dashboard routes
    ├── test_render.py             # Frame, font, scene, FramesScene tests
    ├── test_engine.py             # Render loop
    ├── test_config.py             # Env parsing and validation
    ├── test_sources.py            # Weather source tests
    ├── test_runner.py             # SourceRunner: off-loop polling, isolation
    ├── test_feeds.py              # Feed parsing, seen-state, ETag over real HTTP
    ├── test_visuals.py            # Generators, registry, visual events
    ├── test_visuals_life.py       # Life rules: gliders, blinkers
    └── test_logs.py               # Ring buffer, logging bridge, /api/logs
connectors/                        # Only what needs another machine
└── gifcast/                       # Sends a GIF from your disk
    └── src/gifcast/
        ├── convert.py             # GIF -> panel-sized RGB frames
        ├── client.py              # Thin HTTP wrapper + .env discovery
        └── cli.py                 # `gifcast party.gif`
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

**The render loop draws text and pixels, nothing else.** `render/scenes.py`
ships only Blank, Text, Frames and Solid. Generative visuals — rainbow, Game of
Life, the beer pour — live in `visuals/` and are *pre-rendered* into frames, so
the loop only ever plays bytes. An event names one (`{"kind": "visual",
"name": "beer"}`); `events.prepare()` renders it on a worker thread (seconds,
on a Pi, for the rainbow) and `visuals.frames()` caches it per panel size, so
`build_scene` finds it ready. Anything that names a visual — a route, a source
— must call `prepare` off the loop first. Add a visual by writing a generator
and registering it in `VISUALS`; the dashboard lists them from the API.

**Scenes** — a `Scene` is anything with a `name` and `render(frame, t)`, where
`t` is seconds since the scene became active (Protocol, structural subtyping).
Scenes are stateless with respect to wall-clock time, which makes them trivial
to test at arbitrary `t`. `TextScene` centres text that fits and scrolls text
that doesn't, at fractional pixel offsets — `Frame.draw_text` accepts a float
`x` and splits each glyph column across two pixel columns.

**Performance** — the target is a Raspberry Pi, so per-frame work avoids
per-byte Python loops: gamma is one `bytes.translate` through the LUT, the
crossfade translates both frames through per-weight scale tables and adds them
as big integers (provably carry-free), and `FramesScene` copies byte slices.
`make bench` reports what the current device sustains; run it on the Pi before
raising `BOX_FPS`.

**Displays** — `Display` (`display/protocol.py`) is a Protocol with `push_frame`
and `close`. `BOX_DISPLAY_MODE` picks one: `emulator` (the default; `dev` is
the old name and still accepted) uses `EmulatorDisplay`, which stands in for
the matrix and can draw the panel in the terminal with truecolor half-blocks
(`BOX_TTY_PREVIEW=1`); `matrix` uses `MatrixDisplay`, which drives real HUB75
hardware via `rgbmatrix`, imported lazily so the module still imports
off-device; it writes to an offscreen canvas and swaps on vsync. **Only
`display/matrix.py` may import hardware libraries** — `test_architecture.py`
enforces it — which is what makes the emulator exact.

**Deploying** — `box/deploy/box.service` runs `uv run --no-dev --extra pi
python -m box` under systemd. `pyproject.toml`'s runtime dependencies are
exactly what the Pi needs; dev-only tools (the `--reload` file watcher, test
and lint tools) live in the dev group.

**Configuration** — `Settings.from_env()` reads every `BOX_*` variable and
validates it at startup, so a typo fails loudly instead of silently rendering
at the wrong size — booleans included (`ture` is an error, not False), and in
matrix mode the chain/parallel wiring must divide the panel size.
`create_app(settings)` takes an explicit `Settings` so tests never touch the
environment, and it is also the uvicorn factory: importing `box.api.app`
builds nothing and reads no environment.

**App lifecycle** — `create_app()` builds the display, engine, scheduler, sources
and runner in the lifespan handler and stores them on `app.state`. Routers reach
them through `Depends` accessors. Everything is stopped in reverse on shutdown.

**One thread owns the scheduler.** Handlers that touch the scheduler or engine
are `async def`: a plain `def` handler runs in FastAPI's threadpool, where it
would mutate the queue while the scheduler's tick reads it on the event loop.
Blocking work goes the other way — `SourceRunner` runs each `poll()` on a
worker thread and submits the result back on the loop.

**Events and the scheduler** — the central idea. `set_scene` is last-write-wins,
which is fine for a control panel and useless for a box several independent
services push to. `Scheduler` owns *what is on screen now*. Four tiers:
`alarm` always preempts; `alert` preempts too but yields to an instant event
already on the panel and takes the head of the queue instead; `normal` queues
behind any waiting alerts; `ambient` joins an idle rotation. An interrupted
event resumes with its remaining time, ahead even of same-rank items waiting.
One pending event per source, so a burst coalesces.

The two instant tiers exist because "instant" nearly always means *jump the
queue*, not *shove whatever is on screen* — a burst of pings that each preempt
the last is a burst of unreadable glimpses. `Priority.rank` is the ordering:
`Priority` is a `StrEnum`, so `<` would compare spelling, and "alarm" sorts
before "alert".

**Presentation lives on the box, not in connectors.** A connector sends `source`,
`text` and `priority`; `events.py` maps source to colour and priority to duration.
Restyling every integration is one edit there instead of redeploying each one.

**No configuration to get started.** Every default is the setup you probably
have: the box serves `localhost:8000` and connectors send there. The one thing
that genuinely differs between machines is the port, so `load_dotenv()` reads an
optional `.env` — same tiny parser in `config.py` and in each connector's
`client.py`, since connectors never import the box. A real environment variable
always wins over the file, and the search stops at the repo root so a stray
`~/.env` cannot configure anything. `make dev` runs `python -m box --reload`,
the same entry point as production, so the port lives in one place.

**What runs where.** The rule: *on the Pi, unless it depends on something the
Pi does not have.* Feeds, weather and visuals need nothing but the box and the
internet, so they are on-box `Source`s and `visuals/` — no second service to
keep alive, and they keep working while every other machine sleeps. A
connector exists only because of a dependency: gifcast needs a GIF on your
disk; a Discord listener would need your login. Connectors are separate
projects that talk to `/api/events` over HTTP and never import the box (hence
the same tiny `.env` parser copied into each). Both sides go through the
identical event path. Before adding a connector, ask whether it could be a
`Source` instead; it usually can.

**On-box sources** — anything with `name`, `interval` and `poll() -> Event |
None`. `SourceRunner` gives each its own loop, so a feed timing out never
delays the weather, and runs `poll()` (plus `prepare` for any visual it asks
for) on a worker thread, so it may block on HTTP; the event is submitted back
on the loop. Sources start polling as the app starts, without startup waiting
on them — a Pi often brings the network up after the service.

**Feeds** — `sources/feeds.py`. One `FeedConfig` line per feed in `FEEDS`;
`show` is `"title"` (scroll the item titles) or a visual name (En Stor Stark
Review pours a pint). RSS 2.0 and Atom via stdlib `urllib` + ElementTree, with
ETag/304. "New" means a guid not in `Seen`, persisted under `BOX_STATE_DIR`
(write-then-rename, since a Pi loses power); the first poll only records, so
boot never floods the panel, and a burst becomes one event because the
scheduler keeps one pending per source. `BOX_FEEDS=0` disables them; tests
build `Settings(feeds=False)` so nothing hits the network.

**The log tail** — the dashboard is an admin view, and the question it exists to
answer is *what did the box just do*. `LogBuffer` (`logs.py`) keeps the last 500
lines in memory; `BufferHandler` tees the root logger into it, so uvicorn,
sources and render errors (tracebacks included) all land in the same place.
Events ride the same pipeline rather than a channel of their own: the scheduler
attaches `extra={"box_event": {...}}` to the line it already logs, and the
handler turns those into `event` rows. One path, so the console and the debug
view cannot disagree about what happened.

**API** — `/api/events` is the contract; `/api/display/*` is dashboard sugar over it.

- `POST /api/events` — the one endpoint connectors use
- `GET /api/events/visuals` — names a `visual` scene accepts
- `DELETE /api/events` — drop the queue
- `GET /api/display` — current `PanelState` (scene, source, queued, ambient, …)
- `GET /api/display/frame` — latest frame as base64 RGB (non-WebSocket fallback)
- `POST /api/display/text` — `{"text": "...", "color": "#RRGGBB"}`

Writes take an optional bearer token (`BOX_TOKEN`); reads stay open so the
dashboard loads before it knows the token. The server binds `0.0.0.0` by default
because connectors are on other machines.
- `POST /api/display/solid` — `{"color": "#RRGGBB"}`
- `POST /api/display/visual` — `{"name": "beer"}`, into the rotation and on screen
- `POST /api/display/clear`
- `POST /api/display/brightness` — `{"brightness": 0.0-1.0}`
- `WS /ws/display` — a JSON `hello` with panel size and fps, then raw RGB frames
- `GET /api/logs` — recent entries; `since` is a cursor, `channel` filters to `log` or `event`
- `DELETE /api/logs` — drop the tail
- `WS /ws/logs` — a `hello` carrying the backlog, then one message per new entry

`GET /` serves `web/index.html`; `GET /emulator` serves `web/emulator.html`;
`/docs` is auto-generated.

**Web preview** — the page opens the WebSocket, draws each frame as round
"LEDs" on a canvas with a cheap radial-gradient bloom, and reconnects with
exponential backoff. It contains no rendering logic beyond scaling pixels up.

**Emulator** — `/emulator` is the hardware stand-in: the same frame stream the
matrix gets, drawn as one square per pixel on black, nothing else. Both pages
re-encode values for the screen (`v^(1/2.2)`): frames are gamma-corrected for
LEDs, whose light is linear in the value, and drawing them raw applies gamma
twice. What it cannot show is anything the matrix library does after the
frame — hardware brightness (`BOX_MATRIX_HW_BRIGHTNESS`) and refresh artefacts.

**Testing** — `tests/conftest.py` builds an app from an explicit `Settings` per
test. Async engine tests use `@pytest.mark.anyio` with the `anyio_backend`
fixture. Scene tests assert on frame contents rather than on state flags.

## Code Style

- Ruff with line-length 88, rules: E, F, I, UP, B (`fastapi.Depends` etc. exempted from B008)
- Python 3.14+ (pinned to 3.14.8 in `.python-version`), type hints, Pydantic v2 models
- Deferred annotations (PEP 649) are on by default, so forward references need no quotes
- Protocols for abstractions (structural subtyping, no base class inheritance needed)
- Request/response models defined in the router file that uses them, domain models in their own module
- Comments explain *why*, especially where code is shaped by hardware constraints
