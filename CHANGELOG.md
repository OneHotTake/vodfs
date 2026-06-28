# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.42.0] — 2026-06-28

First production release. Verified end-to-end against Dispatcharr 0.27.1 with a live library (3,000+ movies, ~180 series, ~3,000 episodes): rclone mount → Plex match (TMDB/IMDB) → seekable playback through the native VOD proxy, validated with Plex, Chromium, and ffmpeg.

### Added
- **Plex-correct naming.** A robust provider-name parser (validated against the full live catalog) strips quality/language prefixes (`4K-EN`, `EN|`, `D+`), bracket tags (`[MULTI-SUB]`, `[4K]`), list numbers, and dotted release names; extracts the year from the title when the DB field is empty; and emits external IDs as `{tmdb-NNN}` / `{imdb-ttNNN}`, each in its own brace, on movie folders/files and show folders.
- **Plex TV layout** — `Show (Year) {tmdb-N}/Season NN/Show (Year) - SxxEyy - Title - StreamID.ext`.
- **Accurate, seekable sizes.** On file `HEAD`/open VODFS probes Dispatcharr's VOD proxy once for the real `Content-Length` (from `Content-Range`) and caches it, so Plex analyses and seeks correctly. This also lets Plex surface the container's embedded multi-language audio and subtitle tracks.
- **Self-bootstrapping dependencies** — the plugin installs `uvicorn`/`fastapi`/`jinja2` into Dispatcharr's environment on first enable.
- Configurable bind host (`VODFS_BIND_HOST`) and size-probe controls (`VODFS_PROBE_SIZE`, `VODFS_PROBE_CONCURRENCY`).

### Changed
- **Resolution rewrite.** Files resolve by their trailing provider `stream_id` (unique per account) instead of re-parsing the full filename, and folder→object lookups use the TMDB id when present (exact) with a title/year fallback. The tree, HTTP, and integration layers were rewritten and simplified (net ~−270 lines).
- Season directories are now `Season NN` (Plex convention) instead of `Sxx`.
- Shared helpers consolidated: a single proxy-URL builder, enabled-category predicate, provider-suffix/extension helpers, and DB-task wrapper.

### Fixed
- **Critical: concurrency collapse under load.** Dispatcharr's gevent connection-pool DB backend is incompatible with the plugin's asyncio + thread-pool server (every concurrent request raised `gevent LoopExit` → 500). The standalone server now uses the standard blocking psycopg3 backend; a full Plex/rclone scan no longer fails. (Reproduced at 46/48 failures before, 96/96 success after.)
- Worker-thread DB connection hygiene (`close_old_connections`) so a stalled connection no longer poisons a thread.
- Honest bind-address logging (was claiming `127.0.0.1` while binding `0.0.0.0`).

### Removed
- `/fortune` easter-egg endpoint and its payload; unused `_child_process`, dead imports, and the no-op `build()` method.

### Security
- Base URL scheme validation (rejects non-`http(s)` so the size probe can't be coerced onto another scheme); the base URL is operator-set and points at the trusted internal Dispatcharr.
- Readiness/status endpoints now report real startup errors (the error list was dead).
- Size-probe failures no longer log the full URL.
- `enable_auth` toggle (existing) plus documented guidance to enable auth when the port is exposed beyond a trusted network.

## [0.1.0] — 2026-05-21

Initial scaffolding release. Plugin manifest (`plugin.json`), base `Plugin` class with `run` and `stop` hooks, the `plugin/` package skeleton, and the initial documentation set. Not functional end-to-end on its own — see the Unreleased section for the working implementation that followed.
