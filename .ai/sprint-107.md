# Sprint 107 — Series Episode Hydration

**Status:** Draft | **Risk:** MEDIUM | **Depends:** sprint-104 | **Target:** v0.0.7

## Why
Series directories start empty. Need to fetch episodes on-demand when user browses into a Series directory, populating season/episode structure.

## Non-Goals
- No pre-fetching all episodes
- No caching layer
- No episode metadata enrichment

## Tasks

### HYDRATE-107-01: Detect empty Series directories
**Files:** plugin/httpfs.py (modify)
**Effort:** S
**What:** When serving empty Series directory, trigger hydration. Use metadata flag to track hydration state.

### HYDRATE-107-02: Fetch episodes from Dispatcharr
**Files:** plugin/dispatcharr.py (modify)
**Effort:** M
**What:** Add method to fetch episodes for a series. Include season/episode numbers, stream URLs, file sizes.

### HYDRATE-107-03: Populate episode files
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** Create season directories and episode files. Format: S01E01 - Episode Title.mkv. Mark directory as hydrated.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_hydration.py` (all tests pass)
- [ ] Manual test: Browse empty Series directory triggers hydration
- [ ] Verify season/episode structure created
- [ ] Verify episode files have stream URLs

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 107"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated