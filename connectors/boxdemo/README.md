# boxdemo

Generative visuals for a [box](../../README.md) display — rainbow blobs, Conway's
Game of Life, and a plain hue sweep.

```bash
uv sync
uv run boxdemo rainbow
```

These used to live inside the box. They moved out because they are **content,
not core**: the box knows how to play a buffer of RGB frames, and everything
here just produces one. A new visual now needs no change on the Pi.

## Usage

```
boxdemo {rainbow|life|gradient} [--url URL] [--token TOKEN] [--size WxH]
                               [--frames N] [--fps FPS] [--seed N]
                               [--priority ambient|normal|alert] [--duration S]
```

| Option | Default | Notes |
| --- | --- | --- |
| `--url` | `$BOX_URL` or `http://box:8000` | |
| `--token` | `$BOX_TOKEN` | Only if the box sets `BOX_TOKEN` |
| `--frames` | 180 | 15s at 12fps. Max 600 |
| `--fps` | 12 | Playback rate |
| `--priority` | `ambient` | Wallpaper by default, not a notification |
| `--seed` | random | Reproducible output |

Rainbow: `--speed`, `--blobs`, `--noise`. Life: `--density`, `--hue`.

```bash
boxdemo rainbow --blobs 8 --noise 0.4      # busier wallpaper
boxdemo life --density 0.5 --frames 600    # a long Life loop
boxdemo gradient --priority alert          # take the panel now
```

## Push once, loops forever

Frames are generated here and uploaded in one request. The box loops the buffer
on its own, so **nothing needs to keep running** — send a rainbow once and it
stays as wallpaper through reboots of your desktop.

That is why `--priority ambient` is the default: the visual joins the box's idle
rotation and shares it with weather and anything else, rather than queueing as a
notification.

The trade is that a loop is finite. Life genuinely evolves within the buffer,
but at the end it restarts rather than continuing. Use more `--frames` for a
longer cycle — 600 frames at 12fps is 50 seconds before it repeats.

## Sizing

The panel size is read from the box unless you pass `--size`. Frames are
generated at native size, so nothing is scaled on the Pi.

Generating is the slow part and it is quadratic in panel area: 180 frames of
rainbow at 32×32 takes well under a second, but 64×64 is four times that. Life
and gradient are much cheaper than rainbow.
