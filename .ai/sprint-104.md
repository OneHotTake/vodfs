# Sprint 104 — Dispatcharr Integration

**Status:** Draft | **Risk:** MEDIUM | **Depends:** sprint-103 | **Target:** v0.0.4

## Why
Plugin needs to fetch actual VOD library data from Dispatcharr API to populate the virtual filesystem. Must handle credentials securely and hydrate filesystem nodes with real movie/series data.

## Non-Goals
- No Celery background tasks (sprint 106)
- No episode hydration (sprint 107)
- No multi-stream handling (sprint 109)

## Tasks

### DISP-104-01: Create Dispatcharr client
**Files:** plugin/dispatcharr.py (create)
**Effort:** M
**What:** Implement HTTP client for Dispatcharr API. Handle authentication via API key from plugin params. Never log credentials.

### DISP-104-02: Fetch movies/series lists
**Files:** plugin/dispatcharr.py (create), plugin/tree.py (modify)
**Effort:** M
**What:** Implement methods to fetch movie and series lists from Dispatcharr. Parse response and convert to filesystem nodes.

### DISP-104-03: Hydrate filesystem nodes
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** Populate virtual tree with fetched data. Add files to All directories and category directories. Handle multiple providers/streams.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_integration.py` (all tests pass)
- [ ] Manual test: Fetch movies from Dispatcharr
- [ ] Manual test: Verify All directory populated
- [ ] Verify credentials never appear in logs

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 104"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated