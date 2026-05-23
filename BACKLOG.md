# VOD HTTP Filesystem Plugin - Backlog

## Attack Order

100 → 101 → 102 → 103 → 104 → 105 → 200 → 201 → 202 → 203 → 204 → 300 → 301 → 302

## Priority Map

| ID | Priority | Sprint | Description |
|----|----------|--------|-------------|
| SETUP-01 | HIGH | 100 | Initialize project structure and GitHub repository |
| SETUP-02 | HIGH | 100 | Create plugin.json manifest and basic plugin.py skeleton |
| SETUP-03 | HIGH | 100 | Set up project management files (CLAUDE.md, BACKLOG.md, etc.) |
| SETUP-04 | HIGH | 100 | Create directory structure and .ai templates |
| ARCH-01 | HIGH | 101 | Design virtual filesystem tree structure (FSNode, tree.py) |
| ARCH-02 | HIGH | 101 | Design HTTP request handlers (GET/HEAD, directory listings) |
| ARCH-03 | HIGH | 101 | Design child process management (start/stop, PID handling) |
| ARCH-04 | HIGH | 101 | Design hydration strategy (refresh_series_episodes triggering) |
| CORE-01 | HIGH | 102 | Implement Plugin class with fields and actions |
| CORE-02 | HIGH | 102 | Implement child process lifecycle (run/stop hooks) |
| CORE-03 | HIGH | 102 | Implement HTTP server startup (FastAPI, port binding) |
| CORE-04 | HIGH | 102 | Implement PID persistence and cleanup |
| TREE-01 | HIGH | 103 | Implement FSNode dataclass and NodeType enum |
| TREE-02 | HIGH | 103 | Implement Directory and File node types |
| TREE-03 | HIGH | 103 | Implement tree building logic (Movies/Series with All + categories) |
| TREE-04 | HIGH | 103 | Implement path resolution (traversal, error handling) |
| HTTP-01 | HIGH | 104 | Implement directory listing HTML generation |
| HTTP-02 | HIGH | 104 | Implement HEAD request handling (file size, metadata) |
| HTTP-03 | HIGH | 104 | Implement GET request handling (302 redirects) |
| HTTP-04 | HIGH | 104 | Implement Range header support for seekable playback |
| INT-01 | MED | 200 | Integrate Dispatcharr VOD models (Movie, Series, Episode) |
| INT-02 | MED | 200 | Integrate M3U relations (provider streaming URLs) |
| INT-03 | MED | 200 | Implement refresh_series_episodes task triggering |
| INT-04 | MED | 200 | Handle category filtering and All aggregation |
| HYD-01 | MED | 201 | Implement empty Series directory detection |
| HYD-02 | MED | 201 | Implement bounded concurrency for episode hydration |
| HYD-03 | MED | 201 | Implement cooldown timers to avoid spam |
| HYD-04 | MED | 201 | Implement fire-and-forget async hydration |
| RED-01 | MED | 202 | Generate Dispatcharr proxy URLs for movies |
| RED-02 | MED | 202 | Generate Dispatcharr proxy URLs for episodes |
| RED-03 | MED | 202 | Handle multiple streams per title (filename convention) |
| RED-04 | MED | 202 | Stream ID extraction from M3U relations |
| CONF-01 | LOW | 203 | Add configuration UI (http_port, auto_hydrate settings) |
| CONF-02 | LOW | 203 | Add rclone configuration display in plugin UI |
| CONF-03 | LOW | 203 | Add status display (running/stopped, port) |
| CONF-04 | LOW | 203 | Add enable/disable action with confirmation |
| TEST-01 | MED | 300 | Write unit tests for tree building |
| TEST-02 | MED | 300 | Write unit tests for HTTP handlers |
| TEST-03 | MED | 300 | Write integration tests with Dispatcharr models |
| TEST-04 | MED | 300 | Test with rclone mount and Plex scan |
| TEST-05 | MED | 301 | Test multi-provider overlapping titles |
| TEST-06 | MED | 301 | Test Series hydration on first browse |
| TEST-07 | MED | 301 | Test restart resilience |
| TEST-08 | MED | 301 | Test large library performance |
| DOCS-01 | LOW | 302 | Write comprehensive README.md |
| DOCS-02 | LOW | 302 | Write ARCHITECTURE.md |
| DOCS-03 | LOW | 302 | Write CONTRIBUTING.md |
| DOCS-04 | LOW | 302 | Create rclone configuration examples |

## Sprint 100 — Project Setup

**Status:** Draft | **Risk:** LOW | **Scope:** SETUP-01, 02, 03, 04

- [ ] Create GitHub repository (OneHotTake/dispatcharr-vodfs)
- [ ] Initialize project directory structure
- [ ] Create plugin.json with manifest metadata
- [ ] Create basic plugin.py with Plugin class skeleton
- [ ] Create CLAUDE.md with steering rules
- [ ] Create BACKLOG.md with task catalog
- [ ] Create .ai directory structure with templates
- [ ] Create architecture/ and docs/ directories
- [ ] Create LICENSE (MIT)
- [ ] Commit and push initial structure

## Sprint 101 — Architecture Design

**Status:** Pending | **Risk:** LOW | **Scope:** ARCH-01, 02, 03, 04

- [ ] Design FSNode dataclass structure
- [ ] Design Directory and File node types
- [ ] Design HTTP request handler interfaces
- [ ] Design child process lifecycle
- [ ] Design hydration strategy and concurrency model
- [ ] Document design in architecture/ directory
- [ ] Review design against specification

## Sprint 102 — Core Plugin Implementation

**Status:** Pending | **Risk:** MED | **Scope:** CORE-01, 02, 03, 04

- [ ] Implement Plugin class with fields and actions
- [ ] Implement run() hook for starting child process
- [ ] Implement stop() hook for graceful shutdown
- [ ] Implement HTTP server startup with FastAPI
- [ ] Implement PID file management
- [ ] Test plugin enable/disable cycle
- [ ] Verify child process cleanup on stop

## Sprint 103 — Virtual Filesystem Tree

**Status:** Pending | **Risk:** MED | **Scope:** TREE-01, 02, 03, 04

- [ ] Implement FSNode dataclass and NodeType enum
- [ ] Implement Directory and File node classes
- [ ] Implement tree building for Movies (All + categories)
- [ ] Implement tree building for Series (All + categories)
- [ ] Implement path resolution logic
- [ ] Test tree structure with sample data
- [ ] Verify All is sibling to categories (not parent)

## Sprint 104 — HTTP Filesystem Handlers

**Status:** Pending | **Risk:** MED | **Scope:** HTTP-01, 02, 03, 04

- [ ] Implement directory listing HTML template
- [ ] Implement HEAD request handler
- [ ] Implement GET request handler
- [ ] Implement Range header support
- [ ] Implement trailing slash redirect
- [ ] Test with browser and rclone
- [ ] Verify Content-Type and Accept-Ranges headers

## Sprint 200 — Dispatcharr Integration

**Status:** Pending | **Risk:** HIGH | **Scope:** INT-01, 02, 03, 04

- [ ] Integrate Movie, Series, Episode models
- [ ] Integrate M3U relations for stream URLs
- [ ] Implement refresh_series_episodes triggering
- [ ] Implement category filtering logic
- [ ] Test with real Dispatcharr instance
- [ ] Verify All aggregation includes all items
- [ ] Verify category filtering matches Dispatcharr

## Sprint 201 — Hydration Implementation

**Status:** Pending | **Risk:** MED | **Scope:** HYD-01, 02, 03, 04

- [ ] Implement empty Series directory detection
- [ ] Implement bounded concurrency with semaphore
- [ ] Implement cooldown timers per Series
- [ ] Implement fire-and-forget async hydration
- [ ] Test with Series starting with zero episodes
- [ ] Verify hydration triggers on browse
- [ ] Verify cooldown prevents spam

## Sprint 202 — Streaming Redirects

**Status:** Pending | **Risk:** MED | **Scope:** RED-01, 02, 03, 04

- [ ] Generate movie proxy URLs with stream_id
- [ ] Generate episode proxy URLs with stream_id
- [ ] Handle multiple streams per title
- [ ] Implement filename convention: `{Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}`
- [ ] Test 302 redirects with rclone
- [ ] Test playback through Dispatcharr proxy
- [ ] Verify multiple streams appear as separate files

## Sprint 203 — Configuration UI

**Status:** Pending | **Risk:** LOW | **Scope:** CONF-01, 02, 03, 04

- [ ] Add http_port field (default: 8888)
- [ ] Add auto_hydrate_empty_series field (default: true)
- [ ] Add rclone configuration display
- [ ] Add status display (running/stopped, port)
- [ ] Add enable/disable action
- [ ] Add confirmation dialog for disable
- [ ] Test configuration persistence
- [ ] Verify settings in plugin UI

## Sprint 300 — Core Testing

**Status:** Pending | **Risk:** MED | **Scope:** TEST-01, 02, 03, 04

- [ ] Write unit tests for tree building
- [ ] Write unit tests for HTTP handlers
- [ ] Write integration tests with Dispatcharr models
- [ ] Test rclone mount functionality
- [ ] Test Plex library scan
- [ ] Verify all success criteria met

## Sprint 301 — Edge Case Testing

**Status:** Pending | **Risk:** MED | **Scope:** TEST-05, 06, 07, 08

- [ ] Test multi-provider overlapping titles
- [ ] Test Series hydration on first browse
- [ ] Test restart resilience
- [ ] Test large library performance (1000+ items)
- [ ] Test aggressive Plex scanning
- [ ] Verify no duplicates in All view
- [ ] Verify category filtering correctness

## Sprint 302 — Documentation

**Status:** Pending | **Risk:** LOW | **Scope:** DOCS-01, 02, 03, 04

- [ ] Write comprehensive README.md
- [ ] Write ARCHITECTURE.md
- [ ] Write CONTRIBUTING.md
- [ ] Create rclone configuration examples
- [ ] Document API endpoints
- [ ] Document hydration behavior
- [ ] Document troubleshooting steps
- [ ] Prepare for public release

## Done Items

- [ ] Project setup completed (Sprint 100)