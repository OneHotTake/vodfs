# System Overview

The VOD HTTP Filesystem Plugin exposes Dispatcharr's VOD library as a mountable HTTP filesystem for use with rclone and media servers like Plex.

## High-Level Architecture

```
┌─────────────────┐
│   Dispatcharr   │
│  (Main Process) │
└────────┬────────┘
         │
         │ Plugin Interface
         │ (run/stop hooks)
         │
┌────────▼────────┐
│  VODFS Plugin   │  ← Control Plane
│   (plugin.py)   │     - Starts child process
│                 │     - Manages lifecycle
│                 │     - Exposes UI
└────────┬────────┘
         │
         │ subprocess
         │
┌────────▼──────────────────────────────┐
│  Child HTTP Process (FastAPI Server) │  ← Service Plane
│                                        │     - Serves HTTP
│  ┌────────────────────────────────┐   │     - Handles requests
│  │  Virtual Tree (tree.py)        │   │     - 302 redirects
│  │  - Movies/Series structure     │   │
│  │  - All + categories            │   │
│  └────────────────────────────────┘   │
│  ┌────────────────────────────────┐   │
│  │  HTTP Handlers (httpfs.py)     │   │
│  │  - GET/HEAD requests           │   │
│  │  - Directory listings          │   │
│  │  - 302 redirects               │   │
│  └────────────────────────────────┘   │
│  ┌────────────────────────────────┐   │
│  │  Integration (integration.py)  │   │
│  │  - Django models               │   │
│  │  - VOD content fetch           │   │
│  │  - Episode hydration           │   │
│  └────────────────────────────────┘   │
└────────────────────────────────────────┘
         │
         │ HTTP 302 Redirect
         │
┌────────▼────────┐
│  Dispatcharr    │
│     Proxy       │
│  (Streaming)    │
└─────────────────┘
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

**Key Methods**:
- `run(action, params, context)` - Handle enable/disable/config actions
- `stop(context)` - Called on disable/delete/reload
- `_enable(logger, settings)` - Start child process
- `_disable(logger)` - Stop child process

### 2. Virtual Filesystem Tree (`tree.py`)

**Purpose**: Build and maintain the virtual directory structure.

**Responsibilities**:
- Represent filesystem as a tree of `FSNode` objects
- Build Movies structure (All + categories)
- Build Series structure (All + categories)
- Resolve paths to nodes
- Support directory and file node types

**Key Classes**:
- `FSNode` - Base node class
- `DirectoryNode` - Directory with children
- `FileNode` - File with stream URL
- `VirtualTree` - Tree builder and resolver

### 3. HTTP Handlers (`httpfs.py`)

**Purpose**: Handle HTTP requests for the filesystem.

**Responsibilities**:
- Serve directory listings (GET)
- Handle HEAD requests (metadata)
- Return 302 redirects (GET on files)
- Generate HTML directory listings
- Handle trailing slash redirects

**Key Methods**:
- `handle_get(path, request)` - GET request handler
- `handle_head(path, request)` - HEAD request handler
- `serve_directory(node, path)` - Directory listing
- `serve_file(node)` - 302 redirect to stream URL

### 4. Dispatcharr Integration (`integration.py`)

**Purpose**: Bridge to Dispatcharr's VOD models and tasks.

**Responsibilities**:
- Fetch movies from `apps.vod.models.Movie`
- Fetch series and episodes
- Fetch categories
- Trigger `refresh_series_episodes` task
- Generate Dispatcharr proxy URLs
- Handle hydration cooldowns

**Key Classes**:
- `DispatcharrIntegrator` - Main integration class
- Methods for fetching VOD content
- Hydration queue management

## Data Flow

### Startup Flow

```
1. User clicks "Enable HTTP Filesystem"
2. Dispatcharr calls Plugin.run("enable", ...)
3. Plugin validates settings (port, auto_hydrate)
4. Plugin starts child HTTP process (subprocess.Popen)
5. Plugin saves PID to /data/plugins/vodfs/server.pid
6. Child process initializes:
   a. Connects to Django (same process)
   b. Fetches VOD content from Dispatcharr models
   c. Builds virtual tree
   d. Starts FastAPI server on 127.0.0.1:port
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
5. HTTP handler returns 302 redirect to /proxy/vod/movie/{uuid}?stream_id={id}
6. Plex follows redirect to Dispatcharr proxy
7. Dispatcharr proxy streams video from upstream
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
- ✅ Non-blocking to Dispatcharr
- ✅ Can use async I/O
- ✅ Process isolation
- ❌ Need PID management
- ❌ Slightly more complex deployment

### Why HTTP 302 Redirects?

**Reason**: Avoid proxying video data through this plugin.

**Approach**: Redirect all playback to Dispatcharr's proxy.

**Trade-offs**:
- ✅ Leverages Dispatcharr's optimized proxy
- ✅ No data flow through plugin
- ✅ Supports authentication automatically
- ❌ Requires Dispatcharr proxy infrastructure

### Why Virtual Tree?

**Reason**: Need to represent Dispatcharr's VOD structure as a filesystem.

**Approach**: Build an in-memory tree of directory/file nodes.

**Trade-offs**:
- ✅ Simple and flexible
- ✅ Fast path resolution
- ✅ Easy to test
- ❌ In-memory (rebuild on restart)
- ❌ No caching across restarts

### Why "All" + Categories Structure?

**Reason**: Mirrors Dispatcharr's VOD browsing model and user expectations.

**Approach**: "All" is a sibling to categories, not a parent.

**Trade-offs**:
- ✅ Matches Dispatcharr UI
- ✅ Easy to browse everything or filtered
- ✅ No duplication in All view
- ❌ Slightly more complex tree building

## Security Considerations

1. **Localhost Only**: HTTP server binds to `127.0.0.1`
2. **No Credential Exposure**: Never log M3U credentials
3. **Path Traversal Prevention**: Validate all input paths
4. **DoS Protection**: Rate limit directory listings (future)
5. **Input Validation**: Validate all settings and params

## Performance Considerations

1. **Tree Rebuild**: Rebuild on startup only (or refresh interval)
2. **Lazy Loading**: Don't fetch all episodes upfront
3. **Bounded Concurrency**: Limit hydration concurrency
4. **Cooldown Timers**: Prevent spam hydration
5. **Directory Caching**: Cache listings per session (future)

## Future Enhancements

- [ ] WebDAV support for native clients
- [ ] Caching across restarts
- [ ] Directory listing caching
- [ ] Rate limiting per IP
- [ ] Scanner detection (Plex/Emby/Jellyfin)
- [ ] Rich metadata enrichment
- [ ] Search endpoint
- [ ] Progress indicators for hydration