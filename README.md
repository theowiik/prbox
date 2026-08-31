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

The server renders real RGB frames at a fixed frame rate and streams them over
a WebSocket, so the browser preview shows exactly what the LED matrix shows —
same font, same scrolling, same gamma.

## Scenes

| Scene | Endpoint | Notes |
| --- | --- | --- |
| Text | `POST /api/display/text` | Centred when it fits, smoothly scrolled when it doesn't |
| Rainbow | `POST /api/display/rainbow` | Hue gradient with drifting blobs and value noise |
| Life | `POST /api/display/life` | Conway's Game of Life, toroidal, age-coloured, auto-reseeding |
| Solid | `POST /api/display/solid` | Flat fill |
| Blank | `POST /api/display/clear` | Off |

Scene changes crossfade rather than cutting.

## Configuration

All settings are environment variables, so the same code runs on a laptop and
on the Pi.

| Variable | Default | Description |
| --- | --- | --- |
| `PRBOX_DISPLAY_MODE` | `dev` | `dev` or `matrix` |
| `PRBOX_DISPLAY_WIDTH` | `32` | Panel width in pixels |
| `PRBOX_DISPLAY_HEIGHT` | `32` | Panel height in pixels |
| `PRBOX_FPS` | `30` | Render loop frame rate (1–120) |
| `PRBOX_GAMMA` | `2.2` | Gamma correction for LED brightness |
| `PRBOX_CITY` | `Stockholm` | City for the weather source |
| `PRBOX_TTY_PREVIEW` | `0` | Draw the panel in the terminal with half-blocks |

### Raspberry Pi

`PRBOX_DISPLAY_MODE=matrix` needs the `rgbmatrix` Python module from
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
| `PRBOX_MATRIX_CHAIN` | `1` |
| `PRBOX_MATRIX_PARALLEL` | `1` |
| `PRBOX_MATRIX_MAPPING` | `regular` |
| `PRBOX_MATRIX_GPIO_SLOWDOWN` | `2` |
| `PRBOX_MATRIX_PWM_BITS` | `11` |
| `PRBOX_MATRIX_PWM_LSB_NS` | `130` |
| `PRBOX_MATRIX_HW_BRIGHTNESS` | `100` |

Run `make bench` **on the Pi** before trusting `PRBOX_FPS` — it reports the
frames per second each scene can actually sustain at your panel size. If the
rainbow reads `TIGHT`, lower `PRBOX_FPS`, drop `noise` to `0`, or use fewer
blobs.

## Development

```bash
make dev      # run the server with auto-reload
make check    # lint + tests
make format   # format and autofix
make bench    # measure scene render throughput
```
