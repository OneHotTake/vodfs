# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Robustness pass informed by a comparison against the VOD2MLIB plugin — adopting the fixes that apply to our live-query/302 model, while deliberately skipping its push-to-disk machinery (`.strm`/`.nfo` files, cron rescans, on-disk URL persistence) that our architecture doesn't need.

### Added
- **Eventual-consistency size gate (`VODFS_REQUIRE_SIZE`, default on).** Plex needs a title's exact size or it truncates the file and can't play it (rclone caps reads at the reported size), and probing every file during a scan storms the provider. So VODFS only surfaces titles whose real size Dispatcharr already knows (stored bitrate); the rest stay hidden until known. **Plex never sees — and never probes — an unsized file.** Movie listings/resolution require `detailed_info.bitrate`; series require ≥1 episode with `info.info.bitrate`; episodes require `info.info.bitrate`. Set `VODFS_REQUIRE_SIZE=false` to show everything (then set `VODFS_PROBE_SIZE=true` so playback still gets a real size).
- **Throttled size backfill** (`tools/backfill_sizes.py`). Drips Dispatcharr's `refresh_movie_advanced_data` over enabled movie relations that lack a bitrate, at `VODFS_BACKFILL_RATE`/sec (waves via `VODFS_BACKFILL_LIMIT`) — a controlled, metadata-only trickle, never a burst. Each one Dispatcharr fetches makes that movie appear. Episodes need no backfill: series hydration already populates ~99% of them.
- **`sized` vs `total` in `/stats`** — watch the backfill fill the library in.
- **Unit test suite** (`tests/`, 54 pure-helper tests, ~0.2s) covering provider-name parsing, Plex naming, external-ID formatting, sanitisation, path-resolution regexes, tiered sizing, and base-URL validation — no Django/DB. Run with `python3 -m pytest tests/`.
- **Orphaned-content counts in `/stats`** — movies/series hidden because their provider account is inactive, so a sudden drop in visible counts is explainable.

### Fixed
- **OOM on large libraries.** `/Movies/All` (and category/series lists) built the entire listing in RAM — at ~100k titles it ballooned to ~2 GB and got OOM-killed. Listings now **stream** (`.values()` + `.order_by(id).iterator()` + `StreamingResponse`, emitting rows incrementally); peak RSS is flat (126 MB measured streaming 99,611 rows on prod) regardless of library size. The warmed folder→id maps were dropped (descent falls back to the tmdb/imdb/title lookup, now keyed on the title's most *distinctive* word, not "The").
- **Plugin failed to load before deps were installed.** `plugin/__init__.py` eagerly imported uvicorn/fastapi; made lazy (PEP 562) so Dispatcharr can load the plugin in-process without the child-process deps.
- **Dead redirects from deactivated providers.** Listings and file resolution now require `m3u_account__is_active=True`.
- **Title junk after a duplicated year.** `parse_title` truncates at the first *parenthesised* year and strips inline resolution/codec tokens, so `Cool Hand Luke 4K (1967) PAUL NEWMAN (1967)` becomes `Cool Hand Luke (1967)`. A bare year that is part of the title (`Blade Runner 2049`) is preserved; real-word codes (`Max`, `HBO`) are never stripped.

### Changed
- **Sizes come from Dispatcharr's own metadata, never a probe.** `size_from_bitrate()` reads the provider's overall bitrate × duration from both shapes — movies at `custom_properties.detailed_info`, episodes at `custom_properties.info.info` (matched a real probe to ~0.002% on a 4K movie, ~1% on episodes). The video-stream-only `NUMBER_OF_BYTES` is deliberately ignored (it under-reports the file → truncation). `VODFS_PROBE_SIZE` defaults **off**.
- Enabling the plugin now validates the Dispatcharr base URL (scheme + host) up front and refuses to start on a malformed value.

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
