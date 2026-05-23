# Repository Map

## Structure
- `plugin/` — Main plugin code
  - `plugin.py` — Main entry point, child process management
  - `server.py` — FastAPI HTTP server (127.0.0.1 binding)
  - `httpfs.py` — HTTP request handlers, 302 redirects
  - `tree.py` — Virtual filesystem tree (O(1) lookup)
  - `dispatcharr.py` — Dispatcharr API client
  - `celery_worker.py` — Background hydration tasks
- `tests/` — Test suite (79 tests)
- `docs/` — User guide, troubleshooting, developer docs
- `.ai/` — Project state and sprint tracking