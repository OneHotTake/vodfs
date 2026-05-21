SCOPE_CEILING: Max 3 files | Deliverable: diff only | Stop after first working solution

COMPLETE: sprints 103-105 — Virtual FS Tree, Dispatcharr Integration, HTTP 302 Redirects. Build: OK.
---
status: active
task: sprints 103-105 — Virtual FS Tree, Dispatcharr Integration, HTTP 302 Redirects
last_updated: 2026-05-21

## Summary
- **Sprint 103:** Added All sibling structure and category directories to VirtualTree
- **Sprint 104:** Created DispatcharrClient for API integration, added tree hydration
- **Sprint 105:** Verified 302 redirect logic, added range request support tests

## Files Modified
- `plugin/tree.py` — Added All directories, category dirs, hydrate_from_dispatcharr()
- `plugin/dispatcharr.py` — Created Dispatcharr API client
- `plugin/httpfs.py` — Fixed content-type header charset
- `tests/test_tree.py` — Added All sibling structure tests
- `tests/test_integration.py` — Rewrote for DispatcharrClient and hydration tests
- `tests/test_httpfs.py` — Added range request and rclone simulation tests

## Verification
- [x] `python3 -m pytest tests/` — 49/49 tests pass
- [x] All directories created: /Movies/All, /Series/All, categories
- [x] Dispatcharr client fetches movies/series
- [x] Tree hydration populates filesystem nodes
- [x] 302 redirects work for file playback
- [x] Range request headers present for seekable playback

## Next Steps
- [ ] Begin sprint-106 — Celery background tasks