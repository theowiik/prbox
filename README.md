# box

<p align="center">
    <img src="assets/logo.png" alt="Logo" width="250px"/>
</p>

An LED matrix on a Raspberry Pi that shows whatever you send it. Everything
that can run on the Pi does — weather, RSS feeds, animations, the scheduler —
so the box works on its own. Anything that needs another machine (a GIF on
your laptop, a Discord login) POSTs events to it.

```
            ┌──────────────────── the Pi ─────────────────────┐
gifcast ──┐ │                                                 │
curl    ──┼─┼─► POST /api/events ──► scheduler ──► render ──► LED matrix
discord ──┘ │                          ▲                      │   or
            │   weather, feeds ────────┘        /emulator ◄───┘ (no hardware)
            └─────────────────────────────────────────────────┘
```

## Start

Needs [uv](https://docs.astral.sh/uv/), nothing else. There is nothing to
configure.

```bash
make dev                # the box, on http://localhost:8000
make demo VISUAL=beer   # play a built-in visual, from another terminal
```

No hardware needed: without `BOX_DISPLAY_MODE=matrix` the box emulates the
panel. **http://localhost:8000/emulator** is exactly what the matrix would
show — the pixels on black, nothing else. The dashboard at `/` adds controls
and the event log; `/docs` is the API. Both draw the same frames the matrix
gets, so they cannot drift from the hardware.

Running the box somewhere else, or on another port? Put it in a `.env` at the
repo root — the box, the Makefile and gifcast all read it, so it is one line in
one place:

```ini
BOX_PORT=9100
# BOX_URL=http://box.local:8000   # connectors only, when the box is not local
```

## Sending something

```bash
curl -H 'Content-Type: application/json' \
     -d '{"source":"discord","priority":"alert",
          "scene":{"kind":"text","text":"@theo mentioned you"}}' \
     http://localhost:8000/api/events
```

No colour in that payload: the box knows Discord is blurple. Connectors send
*what happened*; the box owns how it looks.

| Priority | |
| --- | --- |
| `alarm` | Always takes the panel, interrupting even an alert |
| `alert` | Takes it too — unless an instant event is already up, then it shows next |
| `normal` | Queued behind any waiting alerts |
| `ambient` | Joins the idle rotation, never interrupts |

Two instant tiers so a burst stays readable: pings line up behind each other
instead of each shoving the last off screen. One pending event per source, so
ten pings do not buy eighty seconds of panel time.

Scenes are `text` (centred, or scrolled when it does not fit), `visual` (a
built-in animation by name: `rainbow`, `life`, `gradient`, `beer`), `frames`
(your own RGB animation), `solid` and `blank`.

## What runs where

**On the Pi, if it can.** Anything that needs nothing but the box and the
internet runs there, so it keeps working while every other machine sleeps and
there is no second service to keep alive:

- **Feeds** — RSS and Atom, one line each in `box/src/box/sources/feeds.py`. A
  new item shows its title, or plays a visual: a new
  [En Stor Stark Review](https://enstorstarkreview.se/) review pours a pint.
- **Weather** — on the box's own timer (mocked, for now).
- **Visuals** — generated on the box, once, then cached.

**Elsewhere, only if it must.** A connector exists because it depends on
something the Pi does not have. [gifcast](connectors/gifcast) needs the GIF on
your disk; a Discord listener would need your login. Anything that can run
`curl` is a connector — there is no SDK to keep in sync.

## On the Pi

Set `BOX_DISPLAY_MODE=matrix` and install the `rgbmatrix` Python bindings from
[hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
into the box's environment (they are not on PyPI, so not a declared
dependency); `uv sync --extra pi` adds Pillow, which makes pushing frames to
the panel much faster. Run `make bench` **on the Pi** before raising `BOX_FPS`.

[`box/deploy/box.service`](box/deploy/box.service) runs it at boot under
systemd. Feed state (which items were already shown) lives in
`~/.local/state/box`, or `BOX_STATE_DIR`; `BOX_FEEDS=0` turns feeds off.

Everything else is a `BOX_*` environment variable — in the environment or that
`.env` — with a working default: panel size, fps, gamma, city, host and port,
`BOX_TOKEN` to require a bearer token on writes, and the matrix wiring options.
`box/src/box/config.py` is the list.

## Development

```bash
make check    # lint + tests, the box and gifcast
make format
```

Two structural rules, both enforced by tests: `box.api` is the interface
(HTTP, auth, dashboard) and the rest of the box never imports a web framework;
and only `display/matrix.py` touches the hardware, which is what lets the
emulator stand in for it exactly.
