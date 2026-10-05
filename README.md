# box

<p align="center">
    <img src="assets/logo.png" alt="Logo" width="250px"/>
</p>

An LED matrix on a Raspberry Pi that shows whatever you send it. Connectors — a
Discord listener, a build watcher, a GIF sender — POST events; a scheduler
decides what is on the panel.

```
discord listener ──┐
build watcher    ──┼── POST /api/events ──► scheduler ──► LED matrix
gifcast          ──┘                            ▲
                                   weather, clock (on-box sources)
```

## Start

Needs [uv](https://docs.astral.sh/uv/), nothing else. There is nothing to
configure.

```bash
make dev     # the box, on http://localhost:8000
make demo    # send it a rainbow, from another terminal
```

That address is the dashboard: a live preview of the panel, controls, and the
event log. `/docs` is the API. The preview draws the same RGB frames the matrix
gets, so it cannot drift from the hardware.

Running the box somewhere else, or on another port? Put it in a `.env` at the
repo root — the box and the connectors both read it, so it is one line in one
place:

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

Scenes are `text` (centred, or scrolled when it does not fit), `frames` (an RGB
animation, looped), `solid` and `blank`. That is the whole set: anything
generative is *content*, rendered by a connector and sent as `frames`, so a new
visual never means changing the Pi.

## Connectors

[gifcast](connectors/gifcast) sends a GIF; [boxdemo](connectors/boxdemo) sends
rainbow blobs and Game of Life. Both default to `http://localhost:8000` and take
`--url` or the `.env` above. Writing another one is the curl above — there is no
SDK to keep in sync.

## On the Pi

Set `BOX_DISPLAY_MODE=matrix` and install the `rgbmatrix` module from
[hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
(not on PyPI, so not a declared dependency); `uv sync --extra pi` adds Pillow,
which makes frame uploads much faster. Run `make bench` **on the Pi** before
raising `BOX_FPS`.

Everything else is a `BOX_*` environment variable — in the environment or that
`.env` — with a working default: panel size, fps, gamma, city, host and port,
`BOX_TOKEN` to require a bearer token on writes, and the matrix wiring options.
`box/src/box/config.py` is the list.

## Development

```bash
make check    # lint + tests, box and connectors
make format
```

One structural rule: `box.api` is the interface (HTTP, auth, dashboard) and
everything else is the box, which never imports a web framework. A test
enforces it.
