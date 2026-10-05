# gifcast

Send a GIF to your [box](../../README.md).

```bash
make gif GIF=party.gif    # from the repo root
uv run gifcast party.gif  # or from here
```

Talks to `http://localhost:8000` unless told otherwise: `--url`, `BOX_URL`, or
`BOX_PORT` in a `.env` at the repo root.

Decoding and resizing happen here, so the box only ever receives raw pixels and
never needs an image stack.

| Option | Default | |
| --- | --- | --- |
| `--size` | asked from the box | |
| `--crop` | off | Fill the panel instead of letterboxing |
| `--fps` | from the GIF's delays | Averaged; the panel plays at one rate |
| `--max-frames` | 120 | Caps upload size |
| `--duration` | 10 | Seconds to hold the panel |
| `--priority` | `normal` | `ambient` for wallpaper, `alert`/`alarm` to cut in |
| `--once` | off | Play through once instead of looping |

Resizing is nearest-neighbour: at 32×32 a smooth downscale turns detail into
grey mush, and hard edges are what actually read. Transparency composites onto
black rather than inheriting whatever the palette's index 0 happens to be.

## Writing your own

There is nothing special about this one — the box takes a single JSON shape, so
a connector can be a shell script:

```bash
curl -m 2 -H 'Content-Type: application/json' \
     -d '{"source":"discord","priority":"alert",
          "scene":{"kind":"text","text":"@theo mentioned you"}}' \
     http://localhost:8000/api/events
```

Use a short timeout and ignore failures: a missed notification is fine, a
connector hung on an unreachable box is not.
