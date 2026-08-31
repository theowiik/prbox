# box

<p align="center">
    <img src="assets/logo.png" alt="Logo" width="250px"/>
</p>

A generic little event display box: an LED matrix on a Raspberry Pi that shows
whatever you send it. Connectors — a Discord listener, a build watcher, a GIF
sender — POST events to its API; a scheduler decides what's on the panel.

```
your desktop                          the pi
──────────────                        ───────
discord listener ──┐
build watcher    ──┼── POST /api/events ──► scheduler ──► LED matrix
gifcast          ──┘                            ▲
                                                │
                                   weather, clock (on-box sources)
```

Connectors run wherever the data is; the box only has to render. Anything that
must still be on screen when your desktop sleeps (weather, clock) runs on the Pi
itself — but through the identical event path.

## Quick Start

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/). The exact
interpreter is pinned in `.python-version`; `uv` installs it for you.

```bash
cd box
make dev
```

Open http://localhost:8000 for the web preview, or `/docs` for API docs.

The server renders real RGB frames at a fixed frame rate and streams them over
a WebSocket, so the browser preview shows exactly what the LED matrix shows —
same font, same scrolling, same gamma.

## Sending something

One endpoint, one shape, one header. A connector is a curl call:

```bash
curl -m 2 -H "Authorization: Bearer $BOX_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"source":"discord","priority":"alert",
          "scene":{"kind":"text","text":"@theo mentioned you"}}' \
     http://box:8000/api/events
```

No colour in that payload: the box knows Discord is blurple. **Connectors send
what happened; the box owns how it looks.** Restyling is then one edit on the Pi
rather than a redeploy of everything.

### Priorities

| Priority | Behaviour |
| --- | --- |
| `alert` | Takes the panel immediately. Whatever it interrupted resumes after. |
| `normal` | Queued, shown in turn for `duration`, then back to ambient. |
| `ambient` | Joins the idle rotation. Never interrupts. |

One pending event per source: a burst of ten Discord pings does not buy eighty
seconds of panel time — the newest wins.

### Scenes

| `kind` | Notes |
| --- | --- |
| `text` | Centred when it fits, smoothly scrolled when it doesn't |
| `frames` | Pre-rendered RGB animation, any size, looped or once |
| `solid` | Flat fill |
| `blank` | Off |

That is the whole set, on purpose. The box renders **text and pixels**;
everything generative is content, produced by a connector and sent as `frames`.
Adding a new visual never means changing anything on the Pi.

Scene changes crossfade rather than cutting.

## Connectors

| Connector | What it does |
| --- | --- |
| [gifcast](connectors/gifcast) | Sends a GIF, decoded and resized on the sender |
| [boxdemo](connectors/boxdemo) | Rainbow blobs, Game of Life, gradient — rendered on the sender |

Writing another one means POSTing the JSON above. There is no SDK to keep in
sync.

## Configuration

All settings are environment variables, so the same code runs on a laptop and
on the Pi.

| Variable | Default | Description |
| --- | --- | --- |
| `BOX_DISPLAY_MODE` | `dev` | `dev` or `matrix` |
| `BOX_DISPLAY_WIDTH` | `32` | Panel width in pixels |
| `BOX_DISPLAY_HEIGHT` | `32` | Panel height in pixels |
| `BOX_FPS` | `30` | Render loop frame rate (1–120) |
| `BOX_GAMMA` | `2.2` | Gamma correction for LED brightness |
| `BOX_CITY` | `Stockholm` | City for the weather source |
| `BOX_HOST` | `0.0.0.0` | Bind address — connectors are on other machines |
| `BOX_PORT` | `8000` | |
| `BOX_TOKEN` | *(unset)* | Bearer token for writes. Unset disables auth |
| `BOX_AMBIENT_DWELL` | `12` | Seconds each ambient card holds the panel |
| `BOX_SOURCE_INTERVAL` | `60` | How often on-box sources refresh |
| `BOX_TTY_PREVIEW` | `0` | Draw the panel in the terminal with half-blocks |

### Raspberry Pi

`BOX_DISPLAY_MODE=matrix` needs the `rgbmatrix` Python module from
[hzeller/rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix)
(build it with `make build-python && sudo make install-python`). It is not on
PyPI, so it is not a declared dependency. Install Pillow too — it makes frame
uploads much faster:

```bash
uv sync --extra pi
```

Hardware wiring options:

| Variable | Default |
| --- | --- |
| `BOX_MATRIX_CHAIN` | `1` |
| `BOX_MATRIX_PARALLEL` | `1` |
| `BOX_MATRIX_MAPPING` | `regular` |
| `BOX_MATRIX_GPIO_SLOWDOWN` | `2` |
| `BOX_MATRIX_PWM_BITS` | `11` |
| `BOX_MATRIX_PWM_LSB_NS` | `130` |
| `BOX_MATRIX_HW_BRIGHTNESS` | `100` |

Run `make bench` **on the Pi** before trusting `BOX_FPS` — it reports the frames
per second each core scene sustains at your panel size. Playing frames at native
size is a buffer copy and effectively free; scrolling text and scaled frames are
the ones worth checking.

## Layout

```
box/            the box itself — scheduling, rendering, hardware
connectors/     separate projects that send it events over HTTP
```

The box stays deliberately small: it schedules events and draws text and pixels.
Anything generative lives in a connector.

Inside `box/`, one rule: **`box.api` is the interface (HTTP, auth, dashboard);
everything else is the box and never imports a web framework.** A test enforces
it, so the core stays drivable from something other than HTTP later.

## Development

```bash
make dev      # run with auto-reload, bound to 0.0.0.0
make serve    # what runs on the Pi; host/port from BOX_* env
make check    # lint + tests
make format   # format and autofix
make bench    # measure scene render throughput
```

### Running it on the Pi

`BOX_TOKEN` is strongly recommended once the box is on the network — a
Tailscale ACL is the real boundary, but the token is the second one.

```ini
# /etc/systemd/system/box.service
[Service]
Environment=BOX_DISPLAY_MODE=matrix
Environment=BOX_TOKEN=your-secret
WorkingDirectory=/home/pi/box/box
ExecStart=/home/pi/.local/bin/uv run python -m box
Restart=always
```
