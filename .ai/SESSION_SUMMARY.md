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
