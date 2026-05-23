# Sprint 102 — Basic HTTP Server

**Status:** Draft | **Risk:** LOW | **Depends:** sprint-101 | **Target:** v0.0.2

## Why
Plugin needs internal HTTP server for handling Plex/rclone requests. Must bind securely to 127.0.0.1 and implement graceful shutdown with PID persistence.

## Non-Goals
- No filesystem implementation
- No Dispatcharr integration
- No external API endpoints

## Tasks

### HTTP-102-01: Implement HTTP server binding
**Files:** plugin/httpfs.py (modify)
**Effort:** M
**What:** Create HTTP server that binds to 127.0.0.1 only. Configure port from plugin params or default to 8765.

### HTTP-102-02: Implement graceful shutdown
**Files:** plugin/plugin.py (modify)
**Effort:** M
**What:** Implement stop() hook that properly shuts down HTTP server and child processes. Ensure all connections close cleanly.

### HTTP-102-03: Add PID persistence
**Files:** plugin/plugin.py (modify)
**Effort:** S
**What:** Store child process PID in /data/plugins/vodfs/pid.txt for recovery. Clean up PID file on shutdown.

## Verification (run these or it fails)

- [ ] `python -m pytest tests/test_httpfs.py` (all tests pass)
- [ ] Manual test: Start plugin, verify server binds to 127.0.0.1:8765
- [ ] Manual test: Stop plugin, verify server shuts down cleanly
- [ ] Verify PID file created and removed properly
- [ ] Verify server rejects connections from non-localhost

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 102"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated