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
│   ├── standalone_runner.py # Child process bootstrap: django.setup() + uvicorn
│   ├── server.py            # FastAPI app, /healthz, /rclone_conf, auth
│   ├── httpfs.py            # Directory/file request handlers, HTML rendering
│   ├── tree.py              # Virtual path resolution; live DB lookups
│   ├── integration.py       # Dispatcharr model integration
│   └── cache.py             # In-memory TTL/LRU cache for directory listings
├── architecture/            # OVERVIEW.md, HTTPFS.md
├── docs/                    # DEV_GUIDE.md, TROUBLESHOOTING.md
├── tests/                   # pytest suites
└── scripts/                 # Helper scripts
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
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Movies/All/
curl -I http://127.0.0.1:8888/Movies/All/"Some Title (2024) - PROV-12345.mkv"
```

The last one should come back as `302 Found` with a `Location:` pointing into Dispatcharr's `/proxy/vod/...` namespace. If it doesn't, the bug is almost certainly in `tree.py`'s filename-to-stream-ID parser or in `integration.py`'s enabled-relation check.

## Testing

```bash
python -m pytest tests/
python -m pytest tests/ --cov=plugin --cov-report=html
```

Integration tests that need a live Dispatcharr are gated:

```bash
python -m pytest tests/ -m live
```

## Style Notes

- Type hints on anything public.
- Logger calls, not `print`.
- Synchronous Django ORM calls go through the `ThreadPoolExecutor` in `httpfs.py`; never call ORM directly from an async handler.
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
