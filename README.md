# VOD HTTP Filesystem Plugin

Expose your Dispatcharr VOD library to Plex and similar clients as a mountable HTTP filesystem using rclone.

> **Security note:** vodfs fully inherits Dispatcharr's network access rules and uses your existing API key for authentication. See the [Security & Access Control](#security--access-control) section for details.

## Features

- **Virtual HTTP Filesystem**: Browse your VOD library as a directory structure
- **Category Support**: Both "All" aggregate views and per-category browsing
- **Multi-Provider Streaming**: Multiple streams for the same title appear as separate files
- **Episode Hydration**: Automatically fetch episodes when browsing Series directories
- **Dispatcharr Integration**: Uses Dispatcharr models, tasks, and proxy infrastructure
- **302 Redirect Streaming**: All playback goes through Dispatcharr's optimized proxy
- **Background Hydration**: Server starts immediately; library hydration runs in background thread

## Architecture

### High-Level Overview

```
+-----------------+
|   Dispatcharr   |  <-- Main Django process
|  (Main Process) |      - Plugin management
+--------+--------+      - VOD models & proxy
         |
         | Plugin Interface (run/stop hooks)
         |
+--------v--------+
|  VODFS Plugin   |  <-- Control Plane
|   (plugin.py)   |      - Starts child process
|                 |      - Manages lifecycle
|                 |      - Exposes UI settings
+--------+--------+
         |
         | subprocess.Popen()
         | (Django-initialized)
         |
+--------v----------------------------------+
|  Child HTTP Process (FastAPI/uvicorn) |  <-- Service Plane
|                                        |      - Serves HTTP directory listings
|  +--------------------------------+   |      - Handles GET/HEAD requests
|  |  Virtual Tree (tree.py)        |   |      - 302 redirects to proxy
|  |  - Movies/Series structure     |   |
|  |  - All + real categories       |   |
|  +--------------------------------+   |
|  +--------------------------------+   |
|  |  HTTP Handlers (httpfs.py)     |   |
|  |  - Directory listings (HTML)   |   |
|  |  - 302 redirects               |   |
|  |  - Series hydration triggers   |   |
|  +--------------------------------+   |
|  +--------------------------------+   |
|  |  Integration (integration.py)  |   |
|  |  - Django models (direct)      |   |
|  |  - Proxy URL generation        |   |
|  |  - Episode hydration           |   |
|  +--------------------------------+   |
+-----------------------------------------+
         |
         | HTTP 302 Redirect
         |
+--------v--------+
|  Dispatcharr    |  <-- Streaming
|     Proxy       |      - Handles auth
|  (Streaming)    |      - Streams from M3U providers
+--------+--------+
         |
         | Actual video stream
         |
+--------v--------+
|  M3U Provider   |  <-- Xtream Codes API
|  (MEGA/STRONG)  |      - Actual video content
+-----------------+
```

### Component Lifecycle

#### Enable (Start)

1. User clicks **Enable HTTP Filesystem** in Dispatcharr UI
2. Dispatcharr calls `Plugin.run("enable", params, context)`
3. Plugin validates settings (port, auto_hydrate, dispatcharr_base_url)
4. Plugin starts child HTTP process via `subprocess.Popen()`:
   - Inherits Django-initialized Python environment
   - Receives `VODFS_DISPATCHARR_BASE_URL` env var
   - Runs `standalone_runner.py --port <port>`
5. Plugin saves PID to `/data/plugins/vodfs/server.pid`
6. Child process initializes:
   - `django.setup()` already available from parent
   - Builds virtual tree (`tree.py`)
   - Starts uvicorn on `0.0.0.0:<port>`
   - **Background thread** hydrates tree from Dispatcharr models
7. Server immediately responds to requests (hydration happens in background)

#### Disable (Stop)

1. User clicks **Disable HTTP Filesystem** in Dispatcharr UI
2. Dispatcharr calls `Plugin.run("disable", params, context)`
3. Plugin reads PID from `/data/plugins/vodfs/server.pid`
4. Plugin sends `SIGTERM` to child process
5. Child process shuts down gracefully (uvicorn handles cleanup)
6. Plugin removes PID file

#### Reload/Restart

1. Dispatcharr calls `Plugin.stop(context)` on plugin reload
2. Plugin terminates child process via PID
3. Plugin may be re-initialized with new settings
4. User clicks **Enable** to start fresh

#### Graceful Shutdown

- `Plugin.stop()` is called on disable, delete, or reload
- Sends `SIGTERM` to child process
- Removes PID file
- Child process (uvicorn) handles connection drain

### Data Flow

#### Directory Listing

1. rclone requests GET /Movies/All/
2. FastAPI handler receives request
3. VirtualTree resolves path to DirectoryNode
4. HTTP handler generates HTML directory listing
5. Returns HTML with links to children
6. rclone parses HTML and lists entries

#### File Playback

1. Plex requests HEAD /Movies/All/Movie (2024).mkv
2. HTTP handler resolves path to FileNode
3. HTTP handler returns metadata (size, content-type)
4. Plex requests GET /Movies/All/Movie (2024).mkv
5. HTTP handler returns 302 redirect:
   `http://<dispatcharr_base>/proxy/vod/movie/{uuid}?stream_id={id}`
6. Plex follows redirect to Dispatcharr proxy
7. Dispatcharr proxy streams video from M3U provider
8. Plex plays video

#### Episode Hydration

1. User browses /Series/All/Show Name/
2. HTTP handler detects zero episodes
3. Integration checks hydration cooldown (5 min)
4. If not in cooldown, enqueues refresh_series_episodes task
5. Task runs in background (Celery)
6. Episodes fetched from M3U provider
7. Next browse shows episodes

### Configuration Settings

| Setting | Description | Default |
|---------|-------------|---------|
| **HTTP Port** | Port for the HTTP filesystem server | 8888 |
| **Auto-hydrate Empty Series** | Automatically fetch episodes when browsing | true |
| **Dispatcharr Base URL** | Base URL of Dispatcharr instance (used for internal proxy redirects). Usually left at default. | http://127.0.0.1:9191 |
| **Enable Authentication (Token-based)** | Require valid Dispatcharr API key for access | false |

### Actions

| Action | Description |
|--------|-------------|
| Enable HTTP Filesystem | Start the HTTP filesystem server |
| Disable HTTP Filesystem | Stop the HTTP filesystem server |
| rclone Config | Display the rclone configuration |

## Quick Start

### 1. Install the Plugin

1. Download the plugin ZIP from the Dispatcharr Plugin Repository
2. Extract to `/data/plugins/vodfs/`
3. Enable the plugin in Dispatcharr Settings -> Plugins

### 2. Configure

1. Set the **HTTP Port** (default: 8888)
2. Enable **Auto-hydrate Empty Series** (default: enabled)
3. Set **Dispatcharr Base URL** to match your setup:
   - **Same host**: `http://127.0.0.1:9191`
   - **Docker container**: `http://<container_ip>:9191` (find IP with `docker inspect <container>`)
   - **Remote host**: `http://<dispatcharr_host>:9191`
4. Click **Enable HTTP Filesystem**

### 3. Mount with rclone

Add this to your `rclone.conf`:

```ini
[vodfs]
type = http
url = http://127.0.0.1:8888/
```

> **Note**: If Dispatcharr runs in Docker, use the container IP instead of `127.0.0.1`:
> ```ini
> [vodfs]
> type = http
> url = http://172.19.0.2:8888/
> ```

> **Authentication**: If you enabled "Enable Authentication (Token-based)" in plugin settings, add your API key:
> ```ini
> [vodfs]
> type = http
> url = http://127.0.0.1:8888/
> headers = Authorization, ApiKey YOUR_DISPATCHARR_API_KEY_HERE
> ```

Mount the filesystem:

```bash
rclone mount vodfs: /path/to/mount --allow-other --vfs-cache-mode full --daemon
```

### 4. Add to Plex

In Plex Media Server:
1. Add a new library
2. Select "Movies" or "TV Shows"
3. Point to the mount path (e.g., `/tmp/vodfs/Movies` or `/tmp/vodfs/Series`)
4. Scan the library

## Filesystem Structure

The filesystem mirrors Dispatcharr's VOD category model:

```
/Movies
    /All
        Movie Name (2024).mkv
        Movie Name (2024) - Provider2-streamid.mkv  # Multiple streams
        Another Movie (2023).mkv

    /[MULTI-LANG] TOP 2026 MOVIES
        Movie Name (2024).mkv

    /Action
        Another Movie (2023).mkv

    /Comedy
        Comedy Movie (2021).mkv

/Series
    /All
        Show Name (2023)
            /Season 01
                Show Name (2023) - S01E01 - Episode Title.mkv

    /Drama
        Show Name (2023)
            /Season 01
                Show Name (2023) - S01E01 - Episode Title.mkv
```

**Key Points:**
- `/Movies/All` contains every movie
- `/Series/All` contains every series
- Category directories are **siblings** of `All`, not children
- Categories are derived from Dispatcharr's `vod_vodcategory` table (not hardcoded)
- Multiple streams for the same title appear as separate files
- Episodes are organized by season and episode number

## Filename Convention

When multiple providers offer the same title:

```
{Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
```

Example:
```
Inception (2010) - xtream-12345.mkv
Inception (2010) - iptv-org-67890.mkv
```

## Streaming

All media playback is handled by Dispatcharr's proxy:

- Files return **HTTP 302 redirect** to proxy URLs
- Proxy URL format:
  - Movies: `http://<dispatcharr_base>/proxy/vod/movie/{uuid}?stream_id={stream_id}`
  - Episodes: `http://<dispatcharr_base>/proxy/vod/episode/{uuid}?stream_id={stream_id}`
- No data flows through this plugin - it's a redirector only
- Dispatcharr proxy handles authentication and streaming from M3U providers

## Hydration Behavior

### Startup Hydration
- Server starts immediately (uvicorn binds to port)
- Library hydration runs in background thread
- Directory listings are available before hydration completes
- Hydrated entries appear progressively

### Episode Hydration
When browsing a Series directory that has zero episodes:

1. The plugin triggers `refresh_series_episodes` in the background
2. Bounded concurrency prevents overwhelming Dispatcharr
3. Per-series cooldown (5 minutes) prevents spam
4. Episodes appear on the next browse

## File Sizes

- **Movies**: Estimated from `duration_secs` if available, otherwise defaults to 100 min (~1.4 GB at 2 Mbps)
- **Episodes**: Estimated from `duration_secs * 250 KB/s`
- Note: Most Xtream providers don't return file sizes in the standard API

## Requirements

- Dispatcharr v0.20.0 or later
- Python 3.10+
- rclone (for mounting)
- Active M3U provider(s) configured in Dispatcharr

## Security & Access Control

**vodfs is a lightweight plugin that re-uses Dispatcharr's existing security model 100%.**  
It creates **no new users, passwords, tokens, or credential storage** — everything is inherited directly from Dispatcharr.

### 1. Network Access (automatic)
vodfs automatically respects your existing **Dispatcharr → Settings → Network Access → Stream Endpoints** rules.  
If you have restricted streaming to your LAN or specific IP/CIDR ranges, vodfs enforces exactly the same limits with zero extra configuration.

### 2. Authentication (optional, token-based)
- Authentication is **turned OFF by default**.  
  This makes initial testing and troubleshooting extremely simple — just open the filesystem URL in your browser and browse your entire library instantly.
- When you are ready for production, enable **"Enable Authentication (Token-based)"** in the plugin settings.
- It uses your **existing Dispatcharr API key** (the same one already shown in your user profile). No new secrets to manage.

**rclone configuration when authentication is enabled:**
```ini
[vodfs]
type = http
url = http://your-dispatcharr-host:8888/
headers = Authorization, ApiKey YOUR_DISPATCHARR_API_KEY_HERE
# Alternative header (also supported):
# headers = X-API-Key, YOUR_DISPATCHARR_API_KEY_HERE
```

### 3. Logging & Credential Exposure
- **The vodfs plugin itself never logs any credentials** — not in its own logs, not in uvicorn access logs, and not even at debug level.
- Playback flow (what actually happens):
  1. vodfs returns a simple `302` redirect to Dispatcharr's internal proxy URL (`/proxy/vod/...`). This URL contains **only** a UUID and stream ID — **no** username or password.
  2. Dispatcharr then **streams the video bytes server-side** using `StreamingHttpResponse`.
- **Key security benefit**: rclone and any media player **never receive or see the real IPTV provider URL** that contains your `username` and `password`. Those credentials stay entirely inside the Dispatcharr process and are never transmitted to the client.

The **only** place IPTV credentials may appear is inside **Dispatcharr's own VOD proxy logs** (at INFO level). This is standard Dispatcharr behavior and unrelated to vodfs.

### Summary
This architecture gives you:
- Full reuse of Dispatcharr's network rules and authentication
- Zero credential leakage to rclone, players, or external logs
- Lightweight operation (no unnecessary byte proxying through the plugin)
- Easy debugging (leave auth off while testing)

Once testing is complete, simply enable authentication in the plugin settings and vodfs becomes fully protected by the same security model Dispatcharr already provides.

## Troubleshooting

### Server won't start

- Check port is not in use: `netstat -tlnp | grep 8888`
- Check Dispatcharr logs for errors
- Verify `/data/plugins/vodfs/` is writable
- Check server logs: `/data/plugins/vodfs/plugin/server.log`

### Can't mount with rclone

- Verify server is running: `curl http://127.0.0.1:8888/`
- Check firewall allows loopback connections
- Verify rclone configuration matches the port
- If using Docker, use container IP instead of `127.0.0.1`

### Playback fails (s1001 Network error)

- Verify `dispatcharr_base_url` setting is reachable from rclone/Plex
- Check Dispatcharr proxy logs for streaming errors
- Some M3U providers may return 403 for certain content
- Test redirect chain: `curl -svL http://<server>:8888/Movies/All/<movie>.mkv`

### Plex scan finds no content

- Verify mount path is correct in Plex settings
- Check `/Movies/All` and `/Series/All` are browsable
- Verify Dispatcharr has VOD content loaded
- Ensure rclone mount is active: `mount | grep vodfs`

### Episodes not appearing

- Verify `auto_hydrate_empty_series` is enabled
- Check Dispatcharr logs for `refresh_series_episodes` tasks
- Wait for hydration to complete (background task)
- Browse the Series directory again

### Large library slow to browse

- This is expected for libraries with 1000+ items
- Directory listings are cached per session
- Consider category filtering instead of "All" view

## Development

See `architecture/OVERVIEW.md` and `CONTRIBUTING.md` for development details.

### Project Structure

```
vodfs/
├── plugin.py              # Plugin control plane (enable/disable)
├── plugin.json            # Plugin manifest
├── plugin/
│   ├── server.py          # FastAPI/uvicorn server entry point
│   ├── tree.py            # Virtual filesystem tree
│   ├── httpfs.py          # HTTP request handlers
│   ├── integration.py     # Dispatcharr VOD integration
│   ├── standalone_runner.py  # Child process bootstrap
│   └── celery_worker.py   # Background task definitions
├── architecture/
│   ├── OVERVIEW.md        # System architecture
│   ├── HTTPFS.md          # HTTP protocol design
│   └── HYDRATION.md       # Episode hydration strategy
├── tests/                 # Unit and integration tests
├── scripts/               # Helper scripts
├── .ai/                   # Sprint planning and task tracking
└── docs/                  # Additional documentation
```

## Sprint History

| Sprint | Description | Status |
|--------|-------------|--------|
| 100 | Project Setup | Complete |
| 101 | GitHub Repository Setup | Complete |
| 102 | Basic HTTP Server | Complete |
| 103 | Virtual Filesystem Tree | Complete |
| 104 | Dispatcharr Integration | Complete |
| 105 | HTTP 302 Redirects | Complete |
| 106 | Celery Background Tasks | Complete |
| 107 | Series Episode Hydration | Complete |
| 109 | Multi-Stream File Handling | Complete |
| 110 | Large Library Performance | Complete |
| 111 | Error Handling and Logging | Complete |
| 112 | Documentation Polish | Complete |
| 113 | File Sizes + Real Categories | Complete |
| 114 | Proxy URLs & Playback Fix | Complete |

## License

MIT License - see `LICENSE` file.

## Credits

Based on the [xtream-vodfs](https://github.com/OneHotTake/xtream-vodfs) proof of concept.

## Support

- Issues: [GitHub Issues](https://github.com/OneHotTake/dispatcharr-vodfs/issues)
- Discord: [Dispatcharr Discord](https://discord.gg/dispatcharr)
