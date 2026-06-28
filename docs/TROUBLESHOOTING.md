# Troubleshooting

The README covers the common end-user problems. This file is for the longer tail — symptoms that need a bit more poking around.

## Server Won't Start

The plugin enable action returns an error or the port never opens. Things to check, in order:

1. **Port already bound.** `lsof -i :8888` (or whatever port you configured). Pick a different one in plugin settings if so.
2. **Stale PID file.** `/data/plugins/vodfs/server.pid` may point at a process that no longer exists, in which case `plugin.py` will refuse to start a new one. Remove the file and re-enable.
3. **Permissions.** `/data/plugins/vodfs/` needs to be writable by whatever user Dispatcharr runs as.
4. **Child crashed on startup.** `tail` the server log at `/data/plugins/vodfs/server.log`. The most common failure here is a Django import error caused by running against an incompatible Dispatcharr version.

## 500s / `gevent LoopExit` Under Load

A single `ls` works but a Plex or rclone scan throws `500`s, with `gevent LoopExit: This operation would block forever` in the server log. This means the child is still on Dispatcharr's gevent connection-pool DB backend, which can't run in the plugin's asyncio + thread-pool server. `standalone_runner._use_blocking_db_backend` is supposed to swap it for blocking psycopg3 at startup; confirm the startup log line `Standalone DB backend set to standard blocking psycopg3` is present. If it isn't, the swap's `ENGINE` match didn't fire for your Dispatcharr build — that's the place to look.

## rclone Connection Refused

The server is up (you can `curl` it from the Dispatcharr host) but rclone on a different host can't connect. Two cases:

- **Docker.** The plugin server binds inside the Dispatcharr container. Your rclone config needs to use the container's published port on the host or the container IP, not `127.0.0.1`.
- **Firewall.** If you put a firewall between Dispatcharr and Plex, open the configured port.

## Empty Directories

`/Movies/All/` and `/Series/All/` return nothing. The fastest check is `/stats`, which returns per-category counts of exactly what VODFS can see (using the same enabled-category/same-account predicate as the listings):

```bash
curl http://127.0.0.1:8888/stats
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Movies/All/
curl http://127.0.0.1:8888/Series/All/
```

If `/stats` reports zeros (and the listings are also empty), the data isn't there yet. Check in Dispatcharr that:

- VOD content is loaded for at least one M3U account.
- At least one VOD category is enabled.
- The M3U account that owns the content is active.

VODFS only lists relations whose category is enabled **and** whose `m3u_account` matches that enabled category's account — a category enabled on one account does not surface content from a different account.

## Playback Fails in Plex

Plex sees the file and starts a play, then errors or buffers forever. The `302` redirect is the thing to interrogate — note this is a `GET`, not a `HEAD` (`HEAD` on a file returns `200` with the size, not the redirect):

```bash
curl -s -o /dev/null -D - http://127.0.0.1:8888/Movies/All/"<folder>"/"<filename>"
```

Look at the `Location:` header. The host portion of that URL is the **Dispatcharr Base URL** plugin setting. Plex needs to be able to reach that host. If Dispatcharr is in Docker, set the base URL to the address Plex can resolve (LAN IP, hostname, or a Docker alias on a shared network), not `127.0.0.1`.

If the redirect URL looks right but Plex still errors, hit it directly with `curl -I` to confirm Dispatcharr's proxy is serving the stream.

## Missing Audio or Subtitle Tracks

VODFS writes no sidecar subtitle files — the Xtream API has no subtitle data. Every audio language and subtitle is embedded in the container and only appears after Plex analyses the stream, which depends on an accurate file size. If tracks are missing, the size probe is the suspect: confirm `HEAD` returns a real `Content-Length` (`curl -I` on the file), check that probing isn't disabled (`VODFS_PROBE_SIZE`), and re-run Plex's analyse pass on the item. A `Content-Length` of exactly 2 GiB means the probe failed and the duration-based estimate was used — the proxy or base URL is unreachable from the VODFS process.

## Slow Listings on Large Libraries

The `/All` directories are the heavy ones — they walk every enabled relation. A few options:

- Attach Plex to category folders instead so each library is smaller.
- Raise `--dir-cache-time` on the rclone mount so the same `ls` doesn't re-query VODFS repeatedly.
- Check that the directory cache (`plugin/cache.py`) is actually hot; restart the plugin if you're seeing cold-query latency on every request.

## Authentication Failures

You enabled token auth, set `headers =` in the rclone config, and now everything returns `401`. Common causes:

- The header value has the literal placeholder `<your-dispatcharr-api-key>` instead of a real key.
- The key was revoked or regenerated in Dispatcharr.
- The `Authorization` line is in the wrong rclone block (it must be under the `[vodfs]` remote, not a different one).

VODFS accepts either `Authorization: ApiKey <key>` or `X-API-Key: <key>`. The rclone `headers =` syntax produces the first form.

## Where Things Live

- Plugin logs: Dispatcharr application log, lines prefixed `[vodfs]`.
- Child server log: `/data/plugins/vodfs/server.log`.
- PID file: `/data/plugins/vodfs/server.pid`.

When opening a bug report, include the relevant lines from both logs and the output of `curl -I` on the URL that misbehaved.
