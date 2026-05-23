# System Overview

The VOD HTTP Filesystem Plugin exposes Dispatcharr's VOD library as a mountable HTTP filesystem for use with rclone and media servers like Plex.

## High-Level Architecture

```
+-----------------+
|   Dispatcharr   |
|  (Main Process) |
+--------+--------+
         |
         | Plugin Interface
         | (run/stop hooks)
         |
+--------v--------+
|  VODFS Plugin   |  <-- Control Plane
|   (plugin.py)   |      - Starts child process
|                 |      - Manages lifecycle
|                 |      - Exposes UI
+--------+--------+
         |
         | subprocess
         |
+--------v----------------------------------+
|  Child HTTP Process (FastAPI Server) |  <-- Service Plane
|                                        |      - Serves HTTP
|  +--------------------------------+   |      - Handles requests
|  |  Virtual Tree (tree.py)        |   |      - 302 redirects
|  |  - Movies/Series structure     |   |
|  |  - All + categories            |   |
|  +--------------------------------+   |
|  +--------------------------------+   |
|  |  HTTP Handlers (httpfs.py)     |   |
|  |  - GET/HEAD requests           |   |
|  |  - Directory listings          |   |
|  |  - 302 redirects               |   |
|  +--------------------------------+   |
|  +--------------------------------+   |
|  |  Integration (integration.py)  |   |
|  |  - Django models               |   |
|  |  - VOD content fetch           |   |
|  |  - Episode hydration           |   |
|  +--------------------------------+   |
+-----------------------------------------+
         |
         | HTTP 302 Redirect
         |
+--------v--------+
|  Dispatcharr    |
|     Proxy       |
|  (Streaming)    |
+-----------------+
```

## Components

### 1. Plugin Control Plane (`plugin.py`)

**Purpose**: Manage plugin lifecycle within Dispatcharr.

**Responsibilities**:
- Implement `Plugin.run()` for action handling
- Implement `Plugin.stop()` for graceful shutdown
- Start/stop child HTTP process
- Manage PID file persistence
- Provide rclone configuration
- Pass `VODFS_DISPATCHARR_BASE_URL` to child process

**Key Methods**:
- `run(action, params, context)` - Handle enable/disable/config actions
- `stop(context)` - Called on disable/delete/reload
- `_enable(logger, settings)` - Start child process
- `_disable(logger)` - Stop child process

### 2. Virtual Filesystem Tree (`tree.py`)

**Purpose**: Build and maintain the virtual directory structure.

**Responsibilities**:
- Represent filesystem as a tree of `FSNode` objects
- Build Movies structure (All + real categories from `vod_vodcategory`)
- Build Series structure (All + real categories)
- Resolve paths to nodes
- Support directory and file node types
- Hydrate from Dispatcharr data

**Key Classes**:
- `FSNode` - Base node class
- `DirectoryNode` - Directory with children
- `FileNode` - File with stream URL and size
- `VirtualTree` - Tree builder and resolver

### 3. HTTP Handlers (`httpfs.py`)

**Purpose**: Handle HTTP requests for the filesystem.

**Responsibilities**:
- Serve directory listings (GET)
- Handle HEAD requests (metadata)
- Return 302 redirects to Dispatcharr proxy (GET on files)
- Generate HTML directory listings
- Handle trailing slash redirects
- Trigger episode hydration for empty Series directories

**Key Methods**:
- `handle_get(path, request)` - GET request handler
- `handle_head(path, request)` - HEAD request handler
- `serve_directory(node, path)` - Directory listing
- `serve_file(node)` - 302 redirect to stream URL
- `_maybe_hydrate_series(node)` - Trigger episode hydration

### 4. Dispatcharr Integration (`integration.py`)

**Purpose**: Bridge to Dispatcharr's VOD models and tasks.

**Responsibilities**:
- Fetch movies from `apps.vod.models.Movie`
- Fetch series and episodes
- Fetch real categories from `VODCategory`
- Trigger `refresh_series_episodes` task
- Generate Dispatcharr proxy URLs with configurable base URL
- Handle hydration cooldowns
- Estimate file sizes from duration

**Key Classes**:
- `DispatcharrIntegrator` - Main integration class
- `_get_dispatcharr_base_url()` - Helper for proxy URL generation

### 5. HTTP Server (`server.py`)

**Purpose**: FastAPI/uvicorn server entry point.

**Responsibilities**:
- Create FastAPI application
- Build virtual tree
- Start hydration in background thread
- Run uvicorn server

**Key Functions**:
- `create_app(tree)` - Create FastAPI app
- `_hydrate_background(tree)` - Background hydration thread
- `run_server(port)` - Start uvicorn

### 6. Standalone Runner (`standalone_runner.py`)

**Purpose**: Child process bootstrap with Django initialization.

**Responsibilities**:
- Initialize Django (`django.setup()`)
- Add plugin directory to Python path
- Start HTTP server

## Data Flow

### Startup Flow

```
1. User clicks "Enable HTTP Filesystem"
2. Dispatcharr calls Plugin.run("enable", ...)
3. Plugin validates settings (port, auto_hydrate, dispatcharr_base_url)
4. Plugin starts child HTTP process (subprocess.Popen)
5. Plugin saves PID to /data/plugins/vodfs/server.pid
6. Child process initializes:
   a. Connects to Django (same process)
   b. Builds virtual tree
   c. Starts FastAPI server on 0.0.0.0:port
   d. Background thread hydrates tree from Dispatcharr models
7. Plugin returns success to UI
```

### Directory Listing Flow

```
1. rclone or Plex requests GET /Movies/All/
2. HTTP handler receives request
3. Tree resolves path to DirectoryNode
4. HTTP handler generates HTML listing
5. Returns HTML with links to children
6. rclone/Plex parses HTML and lists entries
```

### File Playback Flow

```
1. Plex requests HEAD /Movies/All/Inception (2010).mkv
2. HTTP handler resolves path to FileNode
3. HTTP handler returns metadata (size, content-type)
4. Plex requests GET /Movies/All/Inception (2010).mkv
5. HTTP handler returns 302 redirect to Dispatcharr proxy:
   http://<dispatcharr_base>/proxy/vod/movie/{uuid}?stream_id={id}
6. Plex follows redirect to Dispatcharr proxy
7. Dispatcharr proxy streams video from upstream M3U provider
8. Plex plays video
```

### Episode Hydration Flow

```
1. User browses /Series/All/Show Name/
2. HTTP handler detects zero episodes
3. Integration checks hydration cooldown
4. If not in cooldown, enqueue refresh_series_episodes task
5. Task runs in background (Celery)
6. Episodes fetched from provider
7. Next browse shows episodes
```

## Design Decisions

### Why Separate Child Process?

**Reason**: Dispatcharr plugins run in the main Django process. Long-running HTTP servers would block the main thread.

**Approach**: Use subprocess to run a separate FastAPI server.

**Trade-offs**:
- Non-blocking to Dispatcharr
- Can use async I/O
- Process isolation
- Need PID management
- Slightly more complex deployment

### Why HTTP 302 Redirects?

**Reason**: Avoid proxying video data through this plugin.

**Approach**: Redirect all playback to Dispatcharr's proxy.

**Trade-offs**:
- Leverages Dispatcharr's optimized proxy
- No data flow through plugin
- Supports authentication automatically
- Requires Dispatcharr proxy infrastructure

### Why Background Hydration?

**Reason**: Library hydration can take minutes for large libraries. Server should start immediately.

**Approach**: Start uvicorn first, hydrate tree in background daemon thread.

**Trade-offs**:
- Server responds immediately
- Directory listings available before hydration completes
- Hydrated entries appear progressively
- Tree is eventually consistent

### Why Virtual Tree?

**Reason**: Need to represent Dispatcharr's VOD structure as a filesystem.

**Approach**: Build an in-memory tree of directory/file nodes.

**Trade-offs**:
- Simple and flexible
- Fast path resolution
- Easy to test
- In-memory (rebuild on restart)
- No caching across restarts

### Why "All" + Categories Structure?

**Reason**: Mirrors Dispatcharr's VOD browsing model and user expectations.

**Approach**: "All" is a sibling to categories, not a parent. Categories derived from `vod_vodcategory` table.

**Trade-offs**:
- Matches Dispatcharr UI
- Easy to browse everything or filtered
- No duplication in All view
- Slightly more complex tree building

## Security Considerations

1. **Localhost Only**: HTTP server binds to `127.0.0.1` (or container IP via Docker port mapping)
2. **No Credential Exposure**: Never log M3U credentials
3. **Path Traversal Prevention**: Validate all input paths
4. **Input Validation**: Validate all settings and params
5. **Secrets Management**: Credentials stored in `.env.secrets` (gitignored)

## Performance Considerations

1. **Background Hydration**: Server starts immediately, hydration runs in background
2. **Lazy Loading**: Don't fetch all episodes upfront
3. **Bounded Concurrency**: Limit hydration concurrency
4. **Cooldown Timers**: Prevent spam hydration
5. **Dict-based Child Lookup**: O(1) path resolution

## Future Enhancements

- [ ] WebDAV support for native clients
- [ ] Caching across restarts
- [ ] Directory listing caching
- [ ] Rate limiting per IP
- [ ] Scanner detection (Plex/Emby/Jellyfin)
- [ ] Rich metadata enrichment
- [ ] Search endpoint
- [ ] Progress indicators for hydration
- [ ] Multi-provider fallback in Dispatcharr proxy
