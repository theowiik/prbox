# essr

Show each new [En Stor Stark Review](https://enstorstarkreview.se/) review on
your [box](../../README.md) as it is published: the bar's name and its
helhetsbetyg, in lager amber.

```bash
make reviews                  # from the repo root; keeps running
uv run essr                   # or from here
uv run essr --latest          # send the newest review now, to see it work
```

Talks to `http://localhost:8000` unless told otherwise: `--url`, `BOX_URL`, or
`BOX_PORT` in a `.env` at the repo root.

Unlike gifcast and boxdemo this one keeps running. It polls
[the RSS feed](https://enstorstarkreview.se/feed.xml) every five minutes (the
feed's own cache lifetime) with an ETag, so an unchanged feed costs one empty
response.

| Option | Default | |
| --- | --- | --- |
| `--interval` | 300 | Seconds between checks; at least 60 |
| `--priority` | `normal` | `alert` to jump the queue, `ambient` to join the rotation |
| `--duration` | 20 | Seconds on the panel; long names need time to scroll |
| `--state` | `~/.local/state/box/essr.json` | Which reviews were already announced |
| `--once` | off | Check once and exit, for cron or a systemd timer |
| `--latest` | off | Send the newest review regardless, then exit |
| `--feed` | the ESSR feed | Any RSS 2.0 feed with `<guid>`s works |

How "new" works:

- **The first run announces nothing.** It records what is already in the feed,
  so starting the watcher does not flood the panel with twenty old reviews.
- **Each review is announced once**, by `guid`, and remembered across restarts.
  Reviews published while the watcher was off are announced when it comes back.
- **If the box is unreachable**, the review is not marked as announced. The
  next check tries again.
- **Several at once become one event**, oldest first: the box keeps one pending
  event per source, so separate sends would leave only the last on screen.

Swedish names render properly: the box's font has Å, Ä and Ö.
