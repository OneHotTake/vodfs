# Sprint 105 — HTTP 302 Redirects

**Status:** Draft | **Risk:** LOW | **Depends:** sprint-104 | **Target:** v0.0.5

## Why
File playback requires HTTP 302 redirects to Dispatcharr proxy URLs. Current implementation has basic redirect logic but needs testing with rclone and proper stream handling.

## Non-Goals
- No WebDAV implementation
- No deduplication across providers
- No Celery optimization

## Tasks

### REDIR-105-01: Implement 302 redirect logic
**Files:** plugin/httpfs.py (modify)
**Effort:** S
**What:** Ensure file requests return 302 redirect to Dispatcharr proxy URL. Use stream_url from file node metadata.

### REDIR-105-02: Stream file contents
**Files:** plugin/httpfs.py (modify)
**Effort:** M
**What:** Support streaming file contents via redirect. Handle range requests for seekable playback.

### REDIR-105-03: Test with rclone
**Files:** tests/test_integration.py (modify)
**Effort:** M
**What:** Test redirect behavior with rclone mount simulation. Verify playback URLs work correctly.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_httpfs.py` (all tests pass)
- [ ] Manual test: rclone mount and file access
- [ ] Verify 302 redirect to Dispatcharr proxy URL
- [ ] Verify range request support

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 105"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated