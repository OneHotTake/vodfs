# Architecture

VODFS exposes a live, read-only HTTP view of Dispatcharr's enabled VOD content. Dispatcharr remains the single source of truth — the plugin holds no library state of its own. Every directory listing comes from a Django ORM query at request time, and every file open is a `302` redirect into Dispatcharr's existing VOD proxy. The plugin streams nothing.

Three rules drive the design: don't maintain a parallel manifest, don't proxy media bytes, and respect whatever set of categories and accounts Dispatcharr currently has enabled. Within those constraints the rest follows.

## Runtime Shape

```text
Dispatcharr main process
  │ run/stop actions
  ▼
plugin.py
  • reads plugin settings
  • spawns/terminates child process
  • writes PID file
  │ subprocess
  ▼
standalone_runner.py
  • initializes Django
  • starts FastAPI/uvicorn
  ▼
server.py / httpfs.py / tree.py / integration.py
  • serves directory listings
  • runs live Django ORM queries
  • returns 302 redirects to Dispatcharr proxy URLs
```

The child binds to the port configured in plugin settings and is reached by rclone. In Docker deployments that almost always means using the container's published port or its IP on a shared network, not loopback.

## Source Map

| File | Responsibility |
|------|----------------|
| `plugin.py` | Dispatcharr-side entry point. Starts and stops the child HTTP process; emits the rclone config from the plugin UI. |
| `plugin/standalone_runner.py` | Child bootstrap. Calls `django.setup()` before anything else, then hands off to the server. |
| `plugin/server.py` | FastAPI app: health endpoints, `/rclone_conf`, auth and network checks, uvicorn startup. |
| `plugin/httpfs.py` | Request handling, directory rendering, file redirects, the synchronous-ORM thread pool. |
| `plugin/tree.py` | Virtual path resolution and the DB-backed movie/series/episode lookups behind it. |
| `plugin/integration.py` | Dispatcharr model integration; groups episode stream relations. |
| `plugin/cache.py` | Small in-memory TTL/LRU cache fronting directory listings. |

## Filesystem Layout

Two top-level directories, each with `All` as a sibling of the category folders rather than a parent:

```text
/Movies
  /All
  /<enabled movie category>

/Series
  /All
  /<enabled series category>
```

Movie files:

```text
{Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
```

Episode files:

```text
S01E01 - {Episode Name} - {ProviderShortName}-{StreamID}.{ext}
```

The stream ID lives in the filename on purpose: a direct `GET` against a known file can resolve back to the right relation without needing the parent directory to have been listed first, and the resolution is stable across plugin restarts.

## Directory Listing Flow

```text
rclone GET /Movies/All/
  → server.py routes to HTTPFilesystem
  → tree.py resolves /Movies/All as a directory
  → httpfs.py asks tree.py for the contents
  → tree.py queries enabled M3UMovieRelation rows
  → httpfs.py renders the HTML index
  → rclone parses the <a> tags as files and folders
```

Series add one level on top — `/Series/All/<Show>/` yields season directories, and `/Series/All/<Show>/S01/` yields episode files.

## File Playback Flow

```text
Plex/rclone GET /Movies/All/Movie (2024) - STRONG-12345.mkv
  → tree.py parses filename → stream_id=12345
  → tree.py verifies the relation is enabled
  → httpfs.py returns 302 Location: http://dispatcharr/proxy/vod/movie/<uuid>?stream_id=12345
  → client follows redirect; Dispatcharr streams the bytes
```

Episodes are identical, with `/proxy/vod/episode/<uuid>?stream_id=<id>`.

## Live DB Queries

There is no manifest, snapshot, or cache of last-known state. The core enabled-content predicate is:

```text
M3UVODCategoryRelation.enabled = True
  AND relation.m3u_account == content_relation.m3u_account
```

That same-account check matters because category enable/disable is account-scoped — turning on a category for one M3U account does not surface content from another.

Movie listings join through `M3UMovieRelation`, series through `M3USeriesRelation`, episodes through `M3UEpisodeRelation`. Episode lookups bulk-fetch and group in Python rather than running one query per episode.

## Directory Cache

`plugin/cache.py` is an in-memory TTL/LRU cache (5000 entries, 600 seconds) sitting in front of rendered directory listings. It is strictly a performance cache — the source of truth is always Dispatcharr, and the cache will catch up after expiry or a process restart.

## `/rclone_conf`

A helper endpoint that returns `text/plain` with a paste-ready rclone remote block, a suggested mount point, the mount command, the Plex library paths, and an optional `headers =` line for secured installs. The `url =` line uses the request's incoming host, so opening the page from `localhost`, a LAN IP, or a container IP all produce a config that works from that vantage point.

## Child Process Lifecycle

Enable: `plugin.py` runs `subprocess.Popen(standalone_runner.py --port <port>)`. The child initializes Django, builds the root virtual tree, starts FastAPI, and begins serving. Disable: `plugin.py` reads the PID file, sends `SIGTERM`, removes the PID file. The FastAPI lifespan handler shuts down the synchronous ORM thread pool.

## Threading

FastAPI handlers are async; Django ORM is synchronous. `httpfs.py` owns a small `ThreadPoolExecutor` and dispatches all ORM work to it. This sidesteps `SynchronousOnlyOperation` while keeping the event loop responsive. New ORM code must go through that executor.

## Security

VODFS inherits Dispatcharr's deployment posture. The plugin never exposes upstream provider URLs — all file `GET`s redirect to Dispatcharr's proxy. Optional API-key authentication validates against existing Dispatcharr keys; no new credential is introduced. Network checks consult Dispatcharr's stream network-access policy when available. The server binds to whatever interface is configured, so secure the surrounding environment as you would any other Dispatcharr service.

## What Used to Be Here

Earlier iterations carried a manifest snapshot, a hydration queue with cooldowns, watermark polling, and Celery-side plugin tasks. Those are gone. The current shape — live query in, listing or redirect out — replaced all of it, deleted the second source of truth, and shrank the plugin by roughly an order of magnitude. PRs that try to reintroduce that machinery should expect a hard look.

## Operational Notes

The plugin debugs best from a browser: open `/Movies/`, `/Series/`, and `/rclone_conf` and inspect what comes back. Direct file URLs should always return `302`, never bytes. `/All` directories are inherently heavier than category directories — that's the price of the flat layout, and the rclone `--dir-cache-time` flag is the main lever for managing it.
