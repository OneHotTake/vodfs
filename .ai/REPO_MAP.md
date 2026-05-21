# Repository Map

## Structure
- `plugin/` — Main plugin code
  - `plugin.py` — Main entry point, child process management
  - `server.py` — FastAPI HTTP server (127.0.0.1 binding)
  - `httpfs.py` — HTTP request handlers, 302 redirects
  - `tree.py` — Virtual filesystem tree (Movies/All + categories)
  - `dispatcharr.py` — Dispatcharr API client
- `tests/` — Test suite (49 tests)
- `.ai/` — Project state and sprint tracking
- `docs/` — User and developer documentation