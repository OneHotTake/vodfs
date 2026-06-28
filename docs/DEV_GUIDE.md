# Developer Guide

This is a small plugin that lives inside Dispatcharr. There is no separate service to deploy and no schema of its own — everything VODFS knows it learns by querying Dispatcharr's Django ORM at request time.

## Prerequisites

- Python 3.10+
- A working Dispatcharr checkout (the plugin imports Dispatcharr's Django models at runtime)
- `rclone` installed if you want to test the mount path

## Layout

```text
vodfs/
├── plugin.json              # Plugin manifest (settings UI, actions)
├── plugin.py                # Dispatcharr-side entry point; manages child process
├── plugin/
│   ├── standalone_runner.py # Child bootstrap: django.setup() + blocking DB backend + uvicorn
│   ├── server.py            # FastAPI app, /healthz, /stats, /rclone_conf, auth
│   ├── httpfs.py            # Directory/file request handlers, HTML rendering
│   ├── tree.py              # Virtual path resolution; live DB lookups
│   ├── integration.py       # Dispatcharr model integration; name parsing, size probing
│   └── cache.py             # In-memory TTL/LRU cache for directory listings
└── docs/                    # OVERVIEW.md, HTTPFS.md, DEV_GUIDE.md, TROUBLESHOOTING.md
```

## Running Locally

The plugin runs as a Dispatcharr plugin, so the development loop is: install into Dispatcharr's plugin directory, enable it from the UI, exercise it through `curl` or rclone.

```bash
cp -r . /data/plugins/vodfs/
# In Dispatcharr UI: Settings → Plugins → VOD HTTP Filesystem → Enable
```

Sanity checks against a running server:

```bash
curl http://127.0.0.1:8888/healthz
curl http://127.0.0.1:8888/stats          # per-category counts of what VODFS can see
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Movies/All/     # one folder per movie
curl http://127.0.0.1:8888/Movies/All/"Some Title (2024) {tmdb-12345}/"   # files inside
curl http://127.0.0.1:8888/Movies/All/"Some Title (2024) {tmdb-12345}/Some Title (2024) {tmdb-12345} - PROV - 67890.mkv"
```

The last one (a `GET`, no `-I`) should come back as `302 Found` with a `Location:` pointing into Dispatcharr's `/proxy/vod/...` namespace. Resolution keys on the trailing stream ID (`67890` here), so if it `404`s the bug is almost certainly in `tree.py`'s trailing-stream-ID lookup or in `integration.py`'s enabled-relation check. A `HEAD` (`curl -I`) on the same file returns `200` with the probed `Content-Length`.

## Style Notes

- Type hints on anything public.
- Logger calls, not `print`.
- Synchronous Django ORM calls go through the `ThreadPoolExecutor` in `httpfs.py` (wrapped by `_db_task`, which runs `close_old_connections()` around each call); never call ORM directly from an async handler.
- Don't assume Dispatcharr's gevent pooled DB backend — the child swaps it for blocking psycopg3 in `standalone_runner._use_blocking_db_backend`, because there's no gevent hub here and the pooled connections raise `gevent LoopExit` under concurrency.
- Guard model imports with a `DJANGO_AVAILABLE` flag so unit tests can import the modules without a full Django setup.

```python
try:
    from apps.vod.models import Movie
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    Movie = None
```

## Debugging

- Plugin-side logs land in Dispatcharr's application log with a `[vodfs]` prefix.
- The child FastAPI process writes to `/data/plugins/vodfs/server.log`.
- The PID file at `/data/plugins/vodfs/server.pid` is how `plugin.py` stops the child.
- If `plugin.py` thinks it's already running, check that the PID in that file actually exists; stale PIDs are the most common cause of "enable does nothing".

## Releases

1. Bump the version in `plugin.json`.
2. Update `CHANGELOG.md`.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. Cut a GitHub release.
