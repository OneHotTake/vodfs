# Sprint 110 — Large Library Performance

**Status:** Draft | **Risk:** MEDIUM | **Depends:** sprint-106 | **Target:** v0.0.9

## Why
Libraries with 10K+ items need to remain responsive. Tree traversal and directory listing must be optimized for scale.

## Non-Goals
- No database backend
- No pagination
- No caching layer

## Tasks

### PERF-110-01: Optimize tree traversal
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** Use dict-based child lookup instead of linear search. O(1) vs O(n) for find_child().

### PERF-110-02: Lazy directory listing
**Files:** plugin/httpfs.py (modify)
**Effort:** M
**What:** Sort children only when serving directory. Avoid pre-sorting during hydration.

### PERF-110-03: Benchmark with large dataset
**Files:** tests/test_performance.py (create)
**Effort:** S
**What:** Generate 10K+ item tree. Measure path resolution and directory listing times.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_performance.py` (all tests pass)
- [ ] Manual test: 10K items, directory listing < 100ms
- [ ] Path resolution < 10ms for any depth
- [ ] Memory usage < 500MB for 10K items

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 110"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated