# Sprint 109 — Multi-Stream File Handling

**Status:** Draft | **Risk:** LOW | **Depends:** sprint-104 | **Target:** v0.0.8

## Why
Multiple providers can have same movie/series. Need to show each stream as a separate file so users can choose quality/provider.

## Non-Goals
- No deduplication
- No automatic stream selection
- No quality ranking

## Tasks

### STREAM-109-01: Generate multi-stream filenames
**Files:** plugin/tree.py (modify)
**Effort:** M
**What:** When adding files, include provider and stream ID in filename. Format: Title (Year) - Provider-StreamID.mkv

### STREAM-109-02: Handle duplicate titles
**Files:** plugin/tree.py (modify)
**Effort:** S
**What:** Allow multiple files with different stream IDs in same directory. No deduplication.

### STREAM-109-03: Test multi-stream listing
**Files:** tests/test_multistream.py (create)
**Effort:** S
**What:** Verify multiple streams appear as separate files. Test filename generation and directory listing.

## Verification (run these or it fails)

- [ ] `python3 -m pytest tests/test_multistream.py` (all tests pass)
- [ ] Manual test: Multiple streams visible in directory
- [ ] Verify filename format matches spec
- [ ] Verify each stream has unique URL

## Completion

- [ ] All tasks done
- [ ] All verification steps pass
- [ ] BACKLOG.md updated (mark complete)
- [ ] REPO_MAP.md updated
- [ ] git commit -m "chore: end sprint 109"
- [ ] git push
- [ ] SESSION_SUMMARY.md updated