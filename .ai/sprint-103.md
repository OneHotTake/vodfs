# Sprint 103 — Virtual Filesystem Tree

**Status:** Draft | **Risk:** LOW | **Depends:** sprint-102 | **Target:** v0.0.3

## Why
Virtual filesystem needs proper Movies/Series structure with All sibling directories for Plex category browsing. Current tree.py has basic structure but lacks All directories and category organization.

## Non-Goals
- No Dispatcharr integration
- No actual data fetching
- No hydration logic

## Tasks

### TREE-103-01: Add All sibling structure
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** Add All directory as sibling to category directories under Movies and Series. Structure: /Movies/All, /Movies/Action, /Movies/Comedy, etc.

### TREE-103-02: Implement category directories
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** Add method to create category directories dynamically. Support common categories: Action, Comedy, Drama, Horror, SciFi, Documentary.

### TREE-103-03: Test directory structure
**Files:** tests/test_tree.py (modify)
**Effort:** S
**What:** Add tests for All sibling structure, category directories, and path resolution.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_tree.py` (all tests pass)
- [ ] Manual test: Verify /Movies/All exists
- [ ] Manual test: Verify /Movies/Action, /Movies/Comedy, etc. exist
- [ ] Verify path resolution works for all directories

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 103"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated