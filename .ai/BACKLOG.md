# Backlog

## In Progress
- sprint-101 — GitHub repository setup

## Upcoming Sprints

### sprint-102 — Basic HTTP server
- **Priority:** HIGH
- **Estimated:** 1-2 days
- **Depends:** sprint-101
- Test HTTP server binding to 127.0.0.1
- Implement graceful shutdown in stop() hook
- Add PID persistence to /data/plugins/vodfs/

### sprint-103 — Virtual filesystem tree
- **Priority:** HIGH
- **Estimated:** 2-3 days
- **Depends:** sprint-102
- Implement Movies/Series top-level directories
- Add All sibling structure for Movies
- Test directory listing

### sprint-104 — Dispatcharr integration
- **Priority:** HIGH
- **Estimated:** 2-3 days
- **Depends:** sprint-103
- Implement client with credentials from params
- Fetch movies/series lists
- Hydrate filesystem nodes

### sprint-105 — HTTP 302 redirects
- **Priority:** HIGH
- **Estimated:** 1-2 days
- **Depends:** sprint-104
- Redirect to Dispatcharr proxy URLs
- Stream file contents
- Test with rclone

### sprint-106 — Celery background tasks
- **Priority:** MEDIUM
- **Estimated:** 2-3 days
- **Depends:** sprint-104
- Implement Celery worker
- Hydrate large libraries async
- Don't block run() hook

### sprint-107 — Series episode hydration
- **Priority:** MEDIUM
- **Estimated:** 2-3 days
- **Depends:** sprint-104
- Trigger on empty directory read
- Fetch episodes from Dispatcharr
- Populate episode files

### sprint-108 — Plex integration testing
- **Priority:** HIGH
- **Estimated:** 1-2 days
- **Depends:** sprint-105
- Test Plex scanning Movies/All
- Test Plex scanning category dirs
- Verify playback works

### sprint-109 — Multi-stream file handling
- **Priority:** MEDIUM
- **Estimated:** 1-2 days
- **Depends:** sprint-104
- Show multiple streams as files
- Deduplicate by stream ID
- File naming conventions

### sprint-110 — Large library performance
- **Priority:** MEDIUM
- **Estimated:** 2-3 days
- **Depends:** sprint-106
- Test with 10K+ items
- Optimize tree traversal
- Measure response times

### sprint-111 — Error handling and logging
- **Priority:** LOW
- **Estimated:** 1-2 days
- **Depends:** sprint-105
- Graceful error responses
- Never expose credentials in logs
- Structured logging

### sprint-112 — Documentation polish
- **Priority:** LOW
- **Estimated:** 1 day
- **Depends:** sprint-108
- Update user docs
- Add troubleshooting guide
- Finalize developer docs

## Completed
- sprint-101 — GitHub repository setup ✓
- setup — Project initialization