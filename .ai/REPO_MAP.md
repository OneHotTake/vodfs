# Repository Map

## Structure
- `plugin/` — Main plugin code (plugin.py, httpfs.py, tree.py, dispatcharr.py)
- `tests/` — Test suite
- `.ai/` — Project state and sprint tracking
- `docs/` — User and developer documentation

## Key Files
- `plugin/plugin.py` — Main entry point, child process management
- `plugin/httpfs.py` — HTTP request handlers, 302 redirects
- `plugin/tree.py` — Virtual filesystem tree (Movies/All + categories)
- `plugin/dispatcharr.py` — Dispatcharr API integration