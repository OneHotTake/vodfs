# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- FastAPI HTTP filesystem server running as a Dispatcharr plugin child process, bootstrapped via `standalone_runner.py` (`django.setup()` before model imports).
- `/Movies` and `/Series` virtual roots, each with `All` as a sibling of the per-category folders.
- Multi-stream filenames — each provider surfaces its own file (`Title (Year) - PROVIDER-StreamID.ext`), with the stream ID embedded so a direct `GET` resolves deterministically after restart.
- Season/episode browsing under `/Series/<Category>/<Show>/S01/`.
- `302` redirects to Dispatcharr's `/proxy/vod/movie/...` and `/proxy/vod/episode/...` on file opens; VODFS never streams media bytes itself.
- `/rclone_conf` endpoint returning a paste-ready rclone remote block, suggested mount point, mount command, and Plex library paths, keyed to the request's incoming host.
- `/healthz` liveness endpoint.
- `/stats` endpoint returning library visibility counts (totals plus per-enabled-category breakdown for movies and series, plus directory-cache stats). Mirrors the same enabled-category/same-account predicate the directory listings use, so the numbers reflect what rclone and Plex see. Counts only — no titles, URLs, or credentials. Gated by the same auth/network checks as the other endpoints.
- `/fortune` endpoint.
- Optional token authentication against existing Dispatcharr API keys (`Authorization: ApiKey <key>` or `X-API-Key: <key>`).
- Inheritance of Dispatcharr's stream network-access policy when constructing redirect URLs.
- In-memory TTL/LRU cache (5000 entries, 600s) fronting rendered directory listings.
- Plugin manifest fields for HTTP port, Dispatcharr base URL, and auth toggle, with corresponding settings UI.

### Changed
- Live-query architecture. Directory listings are now Django ORM queries at request time against `M3UMovieRelation`, `M3USeriesRelation`, and `M3UEpisodeRelation`, joined through enabled category/account state. The plugin holds no library snapshot of its own.
- Documentation rewritten end-to-end: user-facing README, `docs/OVERVIEW.md`, `docs/HTTPFS.md`, `docs/DEV_GUIDE.md`, `docs/TROUBLESHOOTING.md`, `CONTRIBUTING.md`.
- Repository structure simplified: `architecture/` folded into `docs/`; empty `tests/` removed; AI-session scaffolding (`.ai/`, `CLAUDE.md`) and personal dev `scripts/` are kept on disk but untracked from the public repo.

### Removed
- Manifest snapshot layer.
- Celery-based episode hydration (queue, cooldown, watermark polling). The plugin no longer maintains a second source of truth.
- Stale documentation (`HYDRATION.md`, `docs/USER_GUIDE.md`).

### Fixed
- Child process now initializes Django before importing Dispatcharr models, so the server actually starts under the plugin runner.
- Episode directory listing no longer recurses infinitely.
- Direct file `GET` against a known stream resolves without requiring the parent directory to have been listed first.
- Duplicate entries in directory listings.
- Movie and episode resolution edge cases surfaced in the post-refactor audit.

### Security
- Hard-coded credential fallback removed from the M3U setup helper.
- `Authorization` and `X-API-Key` header values are stripped from log output; provider URLs are never exposed in responses or logs.
- Plugin manifest gained the `enable_auth` toggle so deployments on untrusted networks can require an API key on every request.

## [0.1.0] — 2026-05-21

Initial scaffolding release. Plugin manifest (`plugin.json`), base `Plugin` class with `run` and `stop` hooks, the `plugin/` package skeleton, and the initial documentation set. Not functional end-to-end on its own — see the Unreleased section for the working implementation that followed.
