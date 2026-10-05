# boxdemo

Generative visuals for a [box](../../README.md): rainbow blobs, Conway's Game
of Life, a hue sweep.

```bash
make demo              # from the repo root
make demo ARGS=life
uv run boxdemo         # or from here
```

Talks to `http://localhost:8000` unless told otherwise: `--url`, `BOX_URL`, or
`BOX_PORT` in a `.env` at the repo root.

Frames are generated here and uploaded in one request; the box loops the buffer
on its own, so **nothing has to keep running**. That is why the default priority
is `ambient`: the visual joins the box's idle rotation as wallpaper rather than
queueing as a notification. A loop is finite, though — more `--frames` means a
longer cycle before it repeats.

| Option | Default | |
| --- | --- | --- |
| `--frames` | 180 | 15s at 12fps, max 600 |
| `--fps` | 12 | Playback rate |
| `--priority` | `ambient` | `normal`, `alert` or `alarm` to take the panel |
| `--duration` | 20 | Seconds per turn in the rotation |
| `--size` | asked from the box | Frames are made at native size, never scaled |
| `--seed` | random | Reproducible output |

Rainbow takes `--speed`, `--blobs`, `--noise`; life takes `--density`, `--hue`.

Generating is the slow part and it is quadratic in panel area: 64×64 costs four
times what 32×32 does. Life and gradient are much cheaper than rainbow.
