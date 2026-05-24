## Session: Sprint 114 - Proxy URLs & Playback Fix

### Changes Made
1. **plugin.py**: Added `dispatcharr_base_url` setting (default: `http://127.0.0.1:9191`)
2. **plugin/integration.py**: Updated `get_all_movies()` and `get_series_episodes()` to generate full proxy URLs using `_get_dispatcharr_base_url()`
3. **plugin/tree.py**: Fixed movie size not being passed to `add_file()` (was causing 0-byte files)
4. **plugin/server.py**: Moved hydration to background thread so server starts immediately
5. **plugin/httpfs.py**: Reverted to 302 redirects (proxy streaming was buffering entire files)

### Key Fix
- Set `dispatcharr_base_url` to container IP (`http://172.19.0.2:9191`) so rclone can reach the proxy from the host

### Result
- ✅ rclone mount stable at `/tmp/vodfs`
- ✅ Plex playback works via 302 redirect chain
- ✅ STRONG provider movies stream successfully
- ⚠️ Some MEGA provider content returns 403 (provider-side block)

### Next Steps
- Consider adding multi-provider fallback in Dispatcharr proxy
- Monitor for any remaining 403 issues with MEGA content

## Session: Rclone Config Endpoint

### Changes Made
1. **plugin/server.py**: Added hidden `GET /rclone_conf` endpoint returning plain-text rclone config, mount command, Plex paths, and API key guidance.
2. **plugin.py**: Updated `show_rclone_config` action message to point users to `/rclone_conf`.
3. Reverted the local Dispatcharr frontend copy-panel patch and rebuilt the container frontend from reverted source.

### Verification
- `/rclone_conf` returns copy/paste-ready text with request host in the `url =` line.
- VODFS child server restarted and endpoint verified after Dispatcharr container restart.

## Session: User-Focused Documentation Rewrite

### Changes Made
1. **README.md**: Rewritten as a user-facing guide focused on what VODFS does, how to get `/rclone_conf`, how to mount with rclone, and how to add Plex libraries.
2. **architecture/OVERVIEW.md**: Rewritten with current live-DB architecture, request flows, direct file resolution, `/rclone_conf`, cache behavior, and removed legacy manifest/hydration design details.

### Verification
- Checked README for stale manifest/hydration references.
- Architecture doc only mentions legacy manifest/hydration as intentionally removed.

## Session: Hidden Fortune Endpoint

### Changes Made
1. **plugin/server.py**: Added hidden `GET /fortune` endpoint returning a random VODFS fortune as plain text.

### Verification
- Deployed to the running container and verified `/fortune` returns a text fortune.
