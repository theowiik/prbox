# gifcast

Send a GIF to your [box](../../README.md).

This is a **connector**: a separate program that talks to the box over HTTP. It
does not run on the Pi. Decoding and resizing happen here, so the box only ever
receives raw pixels and never needs an image stack.

```bash
uv sync
uv run gifcast party.gif
```

## Usage

```
gifcast GIF [--url URL] [--token TOKEN] [--size WxH] [--crop]
            [--fps FPS] [--max-frames N] [--duration SECONDS]
            [--priority ambient|normal|alert] [--source NAME] [--once]
```

| Option | Default | Notes |
| --- | --- | --- |
| `--url` | `$BOX_URL` or `http://box:8000` | Tailscale MagicDNS means the hostname just works |
| `--token` | `$BOX_TOKEN` | Only needed if the box sets `BOX_TOKEN` |
| `--size` | asked from the box | Override to skip the lookup |
| `--crop` | off | Fill the panel and crop instead of letterboxing |
| `--fps` | from the GIF's frame delays | Averaged, since the panel plays at one rate |
| `--max-frames` | 120 | Caps upload size |
| `--duration` | 10 | Seconds to hold the panel |
| `--priority` | `normal` | `alert` interrupts; `ambient` joins the idle rotation |
| `--once` | off | Play through once instead of looping |

Examples:

```bash
# Take the panel right now, for 15 seconds
gifcast alert.gif --priority alert --duration 15

# Use it as wallpaper: joins the ambient rotation
gifcast slow-loop.gif --priority ambient

# Crop to fill, capped at 30 frames
gifcast wide.gif --crop --max-frames 30
```

## How it decides things

**Nearest-neighbour resizing.** On a 32×32 panel a smooth downscale turns
detail into grey mush; nearest keeps edges hard, which is what actually reads at
that size.

**Letterbox by default.** Aspect ratio is preserved and the gaps are black.
`--crop` fills instead, losing the edges.

**Transparency composites onto black** rather than inheriting whatever the GIF
palette's index 0 happens to be.

**One frame rate.** GIFs carry a per-frame delay; the panel plays at a single
rate, so delays are averaged. Variable-rate playback is not worth the protocol.

## Writing your own connector

There is nothing special about this one. The box takes a single JSON shape, so
a connector can be a shell script:

```bash
curl -m 2 -H "Authorization: Bearer $BOX_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"source":"discord","priority":"alert",
          "scene":{"kind":"text","text":"@theo mentioned you"}}' \
     http://box:8000/api/events
```

Note there is no colour in that payload — the box knows Discord is blurple. Send
*what happened*; let the box decide what it looks like. Then restyling is one
edit on the Pi instead of a redeploy of every connector.

Use a short timeout (`-m 2` above) and ignore failures. A missed notification is
fine; a connector hung on an unreachable box is not.
