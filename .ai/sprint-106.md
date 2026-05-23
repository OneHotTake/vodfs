# Sprint 106 — Celery Background Tasks

**Status:** Draft | **Risk:** MEDIUM | **Depends:** sprint-104 | **Target:** v0.0.6

## Why
Large library hydration blocks the run() hook. Need Celery worker to hydrate asynchronously so plugin startup remains fast and responsive.

## Non-Goals
- No actual Celery broker setup (mock for now)
- No distributed task queue
- No retry logic

## Tasks

### CELERY-106-01: Create Celery worker
**Files:** plugin/celery_worker.py (create)
**Effort:** M
**What:** Create Celery app configuration and worker tasks for library hydration. Use in-memory broker for testing.

### CELERY-106-02: Implement async hydration tasks
**Files:** plugin/celery_worker.py (create), plugin/tree.py (modify)
**Effort:** M
**What:** Create tasks for hydrating movies and series. Accept tree reference and Dispatcharr client. Populate nodes async.

### CELERY-106-03: Integrate with plugin run() hook
**Files:** plugin/plugin.py (modify)
**Effort:** S
**What:** Dispatch Celery tasks from run() instead of blocking. Store task IDs for status tracking.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_celery.py` (all tests pass)
- [ ] Manual test: Plugin starts without blocking
- [ ] Verify hydration happens in background
- [ ] Verify task completion status

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 106"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated