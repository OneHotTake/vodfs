# VOD HTTP Filesystem Plugin

Expose your Dispatcharr VOD library to Plex and similar clients as a mountable HTTP filesystem using rclone.

## Features

- **Virtual HTTP Filesystem**: Browse your VOD library as a directory structure
- **Category Support**: Both "All" aggregate views and per-category browsing
- **Multi-Provider Streaming**: Multiple streams for the same title appear as separate files
- **Episode Hydration**: Automatically fetch episodes when browsing Series directories
- **Dispatcharr Integration**: Uses Dispatcharr models, tasks, and proxy infrastructure
- **302 Redirect Streaming**: All playback goes through Dispatcharr's optimized proxy

## Quick Start

### 1. Install the Plugin

1. Download the plugin ZIP from the Dispatcharr Plugin Repository
2. Extract to `/data/plugins/vodfs/`
3. Enable the plugin in Dispatcharr Settings → Plugins

### 2. Configure

1. Set the **HTTP Port** (default: 8888)
2. Enable **Auto-hydrate Empty Series** (default: enabled)
3. Click **🚀 Enable HTTP Filesystem**

### 3. Mount with rclone

Add this to your `rclone.conf`:

```ini
[vodfs]
type = http
url = http://127.0.0.1:8888/
```

Mount the filesystem:

```bash
rclone mount vodfs: /path/to/mount --vfs-cache-mode full
```

### 4. Add to Plex

In Plex Media Server:
1. Add a new library
2. Select "Movies" or "TV Shows"
3. Point to the mount path
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

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| **HTTP Port** | Port for the HTTP filesystem server | 8888 |
| **Auto-hydrate Empty Series** | Automatically fetch episodes when browsing | true |

## Actions

| Action | Description |
|--------|-------------|
| 🚀 Enable HTTP Filesystem | Start the HTTP filesystem server |
| 🛑 Disable HTTP Filesystem | Stop the HTTP filesystem server |
| 📋 rclone Config | Display the rclone configuration |

## Hydration Behavior

When browsing a Series directory that has zero episodes:

1. The plugin triggers `refresh_series_episodes` in the background
2. Bounded concurrency prevents overwhelming Dispatcharr
3. Per-series cooldown (5 minutes) prevents spam
4. Episodes appear on the next browse

## Streaming

All media playback is handled by Dispatcharr's proxy:

- Files return **HTTP 302 redirect** to proxy URLs
- Proxy URL format:
  - Movies: `/proxy/vod/movie/{uuid}?stream_id={stream_id}`
  - Episodes: `/proxy/vod/episode/{uuid}?stream_id={stream_id}`
- No data flows through this plugin - it's a redirector only

## Requirements

- Dispatcharr v0.20.0 or later
- Python 3.10+
- rclone (for mounting)
- Active M3U provider(s) configured in Dispatcharr

## Architecture

- **Plugin** (`plugin.py`): Control plane - starts/stops child process
- **Child Process** (not yet implemented): Service plane - HTTP server
- **Tree Builder** (`tree.py`): Virtual filesystem structure
- **HTTP Handlers** (`httpfs.py`): Request handlers (GET/HEAD, listings)
- **Integration** (`integration.py`): Dispatcharr models and tasks

See `ARCHITECTURE.md` for details.

## Security

- HTTP server binds to `127.0.0.1` only (localhost)
- Dispatcharr credentials never exposed in logs
- All streaming goes through Dispatcharr's proxy infrastructure

## Troubleshooting

### Server won't start

- Check port is not in use: `netstat -tlnp | grep 8888`
- Check Dispatcharr logs for errors
- Verify `/data/plugins/vodfs/` is writable

### Can't mount with rclone

- Verify server is running: `curl http://127.0.0.1:8888/`
- Check firewall allows loopback connections
- Verify rclone configuration matches the port

### Plex scan finds no content

- Verify mount path is correct in Plex settings
- Check `/Movies/All` and `/Series/All` are browsable
- Verify Dispatcharr has VOD content loaded

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

See `ARCHITECTURE.md` and `CONTRIBUTING.md` for development details.

## License

MIT License - see `LICENSE` file.

## Credits

Based on the [xtream-vodfs](https://github.com/OneHotTake/xtream-vodfs) proof of concept.

## Support

- Issues: [GitHub Issues](https://github.com/OneHotTake/dispatcharr-vodfs/issues)
- Discord: [Dispatcharr Discord](https://discord.gg/dispatcharr)