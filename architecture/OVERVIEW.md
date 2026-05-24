# VODFS Architecture

This document describes the current VODFS runtime architecture. The short version: Dispatcharr remains the source of truth, and VODFS exposes a lightweight HTTP filesystem view over live Dispatcharr ORM queries.

## Design Goals

- Do not maintain a separate VOD manifest.
- Do not copy or proxy media bytes through VODFS.
- Respect Dispatcharr's enabled VOD category/account state.
- Keep rclone and Plex browsing responsive enough for large libraries.
- Keep the plugin simple to operate and easy to debug.

## Runtime Shape

```text
Dispatcharr main process
  |
  | plugin run/stop actions
  v
plugin.py
  - reads plugin settings
  - starts/stops child process
  - writes PID file
  |
  | subprocess
  v
standalone_runner.py
  - initializes Django
  - starts FastAPI server
  |
  v
server.py / httpfs.py / tree.py / integration.py
  - serves directory listings
  - runs live Django ORM queries
  - returns 302 redirects to Dispatcharr proxy URLs
```

The child server binds to the configured HTTP port and is intended to be reached by rclone. In Docker deployments, this usually means using the container IP or a mapped host port.

## Important Files

| File | Responsibility |
|------|----------------|
| `plugin.py` | Dispatcharr plugin entry point. Starts and stops the child HTTP process. Generates rclone config action output. |
| `plugin/standalone_runner.py` | Child process bootstrap. Calls `django.setup()` before starting the server. |
| `plugin/server.py` | FastAPI app, health endpoints, `/rclone_conf`, auth/network dependency checks, uvicorn startup. |
| `plugin/httpfs.py` | HTTP filesystem request handling, directory listing rendering, rclone-compatible HTML, file redirects. |
| `plugin/tree.py` | Virtual path resolution and live DB-backed movie/series/episode lookup. |
| `plugin/integration.py` | Dispatcharr model integration and episode stream relation grouping. |
| `plugin/cache.py` | Small in-memory TTL/LRU cache for directory listing responses. |

## Filesystem Layout

VODFS intentionally exposes a simple two-root structure:

```text
/Movies
  /All
  /<enabled movie category>

/Series
  /All
  /<enabled series category>
```

`All` is a sibling of category directories. It is not a parent directory.

Movie files use this format:

```text
{Movie Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
```

Episode files use this format:

```text
S01E01 - {Episode Name} - {ProviderShortName}-{StreamID}.{ext}
```

The stream ID is part of the filename so direct file resolution remains deterministic after restart and across providers.

## Directory Listing Flow

```text
rclone GET /Movies/All/
  -> server.py routes to HTTPFilesystem
  -> tree.py resolves /Movies/All as a directory
  -> httpfs.py asks tree.py for movies from DB
  -> tree.py queries enabled M3UMovieRelation rows
  -> httpfs.py renders a simple HTML index
  -> rclone parses links as files/folders
```

Series flow is similar, with one extra level:

```text
/Series/All/Show Name/
  -> season directories

/Series/All/Show Name/S01/
  -> episode files
```

## File Playback Flow

```text
Plex/rclone GET /Movies/All/Movie (2024) - STRONG-12345.mkv
  -> tree.py parses the filename and stream ID
  -> tree.py verifies the relation is enabled in Dispatcharr
  -> httpfs.py returns 302 Location: http://dispatcharr/proxy/vod/movie/{uuid}?stream_id=12345
  -> client follows redirect to Dispatcharr
  -> Dispatcharr streams the media
```

Episodes work the same way, using Dispatcharr's episode proxy endpoint:

```text
http://dispatcharr/proxy/vod/episode/{uuid}?stream_id={stream_id}
```

## Live DB Queries

VODFS does not use a manifest file or snapshot. Every listing is derived from Dispatcharr database state.

The core enabled-content rule is:

```text
M3UVODCategoryRelation.enabled = True
and relation.m3u_account matches the content relation's m3u_account
```

That same-account check matters because enabled category state is account-specific.

Movie listing uses `M3UMovieRelation` and joins through category/account relations.

Series listing uses `M3USeriesRelation` and joins through category/account relations.

Episode listing bulk-fetches `M3UEpisodeRelation` rows for the series and groups them by episode to avoid one query per episode.

## Directory Cache

`plugin/cache.py` provides a small in-memory TTL/LRU cache for rendered directory entries:

- max entries: 5000
- TTL: 600 seconds

This is a performance cache only. It is not a source of truth. If Dispatcharr content changes, VODFS will naturally refresh after cache expiry or process restart.

## `/rclone_conf`

The hidden helper endpoint:

```text
GET /rclone_conf
```

returns `text/plain` containing:

- an rclone remote block
- suggested mount point
- mount command
- Plex library paths
- API key header guidance

It uses the incoming request host for the `url =` line, which makes it useful whether the user opens it through localhost, LAN IP, or Docker container IP.

## Child Process Lifecycle

Enable action:

```text
Dispatcharr -> plugin.py -> subprocess.Popen(standalone_runner.py --port <port>)
```

The child process:

1. initializes Django
2. builds the basic virtual tree roots
3. starts FastAPI/uvicorn
4. serves live DB-backed filesystem requests

Disable/stop action:

```text
plugin.py reads PID -> sends SIGTERM -> removes PID file
```

The FastAPI lifespan handler shuts down the thread pool used for synchronous ORM work.

## Threading Model

FastAPI handlers are async, but Django ORM calls are synchronous. VODFS uses a small `ThreadPoolExecutor` in `httpfs.py` to run DB-backed operations outside the async event loop.

This avoids Django `SynchronousOnlyOperation` errors while keeping request handling responsive.

## Security Model

VODFS is an internal Dispatcharr plugin and inherits Dispatcharr's deployment/security assumptions.

Runtime behavior:

- VODFS never exposes upstream IPTV provider URLs.
- Media file GET requests return Dispatcharr proxy redirects.
- Optional API-key auth uses Dispatcharr API keys.
- Network checks call Dispatcharr's stream network-access policy when available.

The server binds to the configured interface/port so rclone can reach it. Secure the Dispatcharr environment and network as you normally would.

## Removed Legacy Architecture

Older versions experimented with manifest snapshots, hydration queues, watermark polling, and Celery-side plugin tasks. Those pieces are intentionally gone.

Current behavior is live-query only:

```text
request -> Dispatcharr ORM -> directory listing or 302 redirect
```

This keeps the plugin smaller and avoids a second library state that can drift from Dispatcharr.

## Operational Notes

- The plugin is easiest to debug by opening `/Movies/`, `/Series/`, and `/rclone_conf` in a browser.
- Direct file URLs should return `302`, not video bytes.
- If a direct episode or movie request happens after restart, filename parsing plus DB lookup should resolve it without requiring the parent directory to be listed first.
- Large `All` directories are expected to be heavier than category directories.
