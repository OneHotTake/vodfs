# Troubleshooting Guide

## Common Issues

### Server Won't Start

**Symptom**: Plugin enable fails or server doesn't bind to port.

**Solutions**:
1. Check if port is already in use: `lsof -i :8888`
2. Change HTTP Port in plugin settings
3. Check plugin logs for errors
4. Verify PID file location: `/data/plugins/vodfs/server.pid`

### rclone Mount Fails

**Symptom**: `rclone mount` returns connection refused.

**Solutions**:
1. Verify server is running: `curl http://127.0.0.1:8888/Movies/`
2. Check rclone config URL matches server port
3. Ensure server binds to 127.0.0.1 (not 0.0.0.0)
4. Restart plugin and retry mount

### Plex Can't Scan Library

**Symptom**: Plex shows empty library after scan.

**Solutions**:
1. Verify rclone mount is accessible: `ls /path/to/mount/Movies/All/`
2. Check directory listing returns files: `curl http://127.0.0.1:8888/Movies/All/`
3. Ensure files have `.mkv` extension
4. Verify stream URLs are valid

### Playback Fails

**Symptom**: Plex buffers or shows error during playback.

**Solutions**:
1. Check 302 redirect: `curl -I http://127.0.0.1:8888/Movies/All/Movie.mkv`
2. Verify redirect URL is accessible from Plex server
3. Check Dispatcharr proxy is running
4. Verify network connectivity between Plex and Dispatcharr

### Missing Episodes

**Symptom**: Series directory shows no episodes.

**Solutions**:
1. Enable "Auto-hydrate Empty Series" in plugin settings
2. Browse into the series directory to trigger hydration
3. Check Dispatcharr has episode data for the series
4. Verify series ID is stored in directory metadata

### Performance Issues

**Symptom**: Slow directory listing or high memory usage.

**Solutions**:
1. Library should handle 10K+ items efficiently
2. Check memory usage: `ps aux | grep vodfs`
3. Verify Celery worker is running for background hydration
4. Consider reducing category count if using custom categories

### Credential Exposure

**Symptom**: API key appears in logs.

**Solutions**:
1. This should never happen - report as bug
2. Check log level is not set to DEBUG
3. Verify error messages use "REDACTED" for sensitive data
4. Rotate API key if exposure is confirmed

## Log Locations

- Plugin logs: Dispatcharr application logs
- Server logs: stdout/stderr of child process
- PID file: `/data/plugins/vodfs/server.pid`

## Getting Help

1. Check this troubleshooting guide first
2. Review plugin logs for error messages
3. Verify rclone configuration
4. Test with `curl` commands to isolate issues
5. Report bugs with full error output and configuration