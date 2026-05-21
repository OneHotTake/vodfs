# Sprint 111 — Error Handling and Logging

**Status:** Draft | **Risk:** LOW | **Depends:** sprint-105 | **Target:** v0.0.10

## Why
Production needs graceful error responses and structured logging. Must never expose credentials in logs.

## Non-Goals
- No external logging service
- No alerting
- No log rotation

## Tasks

### ERROR-111-01: Add structured logging
**Files:** plugin/server.py (modify), plugin/plugin.py (modify)
**Effort:** S
**What:** Configure JSON structured logging. Include request ID, path, status code. Redact credentials.

### ERROR-111-02: Graceful error responses
**Files:** plugin/httpfs.py (modify)
**Effort:** M
**What:** Return proper HTTP error codes with JSON bodies. Handle timeouts, connection errors, missing data.

### ERROR-111-03: Credential redaction
**Files:** plugin/dispatcharr.py (modify)
**Effort:** S
**What:** Ensure API key never appears in logs. Use redacted format in error messages.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_errors.py` (all tests pass)
- [ ] Manual test: Error responses are JSON with proper codes
- [ ] Verify no credentials in log output
- [ ] Verify structured log format

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 111"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated