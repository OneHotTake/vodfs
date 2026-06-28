# VODFS for Dispatcharr

VODFS exposes your Dispatcharr VOD library as a read-only HTTP filesystem. Point rclone at it, mount the result, and Plex (or Jellyfin/Emby) sees your movies and series as ordinary, correctly-named folders and files.

Dispatcharr stays the source of truth. VODFS does not copy media, scan playlists, or hold its own library. Every directory listing is a live query against Dispatcharr's database, and every file open is a `302` redirect into Dispatcharr's native VOD proxy. The plugin is small on purpose: if it vanished tomorrow, Dispatcharr would still work.

## Why a mount instead of `.strm` files?

The common way to get IPTV VOD into a media server is to generate `.strm` files. **Plex does not play `.strm` files** — so the whole `.strm` ecosystem targets Jellyfin/Emby/Kodi. VODFS takes the other road: it presents *real* files over HTTP so Plex treats them like local media. Playback, seeking, and analysis all work because the files redirect to Dispatcharr's VOD proxy, which serves the real container with HTTP `Range` support and a correct `Content-Length`.

## Layout

Once mounted, the filesystem follows Plex's recommended naming exactly:

```text
/mnt/vodfs
  /Movies
    /All
      Deadpool & Wolverine (2024) {tmdb-533535}/
        Deadpool & Wolverine (2024) {tmdb-533535} - MEGA - 1387956.mkv
      Avatar (2009) {tmdb-19995}/
        Avatar (2009) {tmdb-19995} - STRONG - 680339.mkv
    /DISNEY+ MOVIES/
      ...
  /Series
    /All
      Acapulco (2021) {tmdb-133727}/
        Season 01/
          Acapulco (2021) - S01E01 - Pilot - 1522534.mkv
          Acapulco (2021) - S01E02 - Jessie's Girl - 1522535.mkv
    /APPLE+ SERIES/
      ...
```

What VODFS does to make Plex matching reliable:

- **Cleans provider noise.** `4K-EN - Deadpool  (2016)` becomes `Deadpool (2016)`; quality/language prefixes (`4K-EN`, `EN|`, `D+`), bracket tags (`[MULTI-SUB]`, `[4K]`), dotted release names, and list numbers are stripped.
- **Extracts the year** from the title when Dispatcharr's `year` field is empty.
- **Embeds external IDs** the way Plex wants them — `{tmdb-NNN}` and `{imdb-ttNNN}`, each in its own brace, on the folder (and movie file). With a TMDB id present, Plex matches by id regardless of surrounding text.
- **Uses `Season 01` folders** and `SxxEyy` episode names, per Plex's TV convention.

`All` is a sibling of the category folders, not a parent — point a Plex movie library at `/Movies/All` and a TV library at `/Series/All` and you're done. If a title is carried by more than one provider, each stream shows up as its own file (grouped by Plex as versions of the same movie).

## Subtitles & audio languages

VODFS does **not** fabricate subtitle files. The Xtream-codes API exposes no subtitle data, so there is nothing to sidecar. Instead, multi-language audio and subtitles come through the way they actually exist — **embedded in the streamed container**. Because file opens redirect to Dispatcharr's VOD proxy (which serves the real file with `Range` support and the true size), Plex's analyzer reads the container and surfaces every embedded track. A single VOD file routinely carries a dozen-plus audio languages and many subtitle tracks (with `forced`/`SDH` flags), all selectable in Plex once the item is analyzed.

## Requirements

- Dispatcharr (v0.20+; tested against 0.27.x) with VOD content loaded and at least one VOD category enabled.
- [rclone](https://rclone.org/downloads/) + FUSE on the host that reads the media (typically the Plex host).
- A client — Plex, Jellyfin, Emby, or just `ls` — reading from the mount point.

rclone runs wherever Plex reads media. In Docker that usually means mounting on the host and bind-mounting the result into the Plex container:

```text
Dispatcharr/VODFS server  --->  rclone mount on Plex host  --->  Plex library path
```

On Debian/Ubuntu: `sudo apt install rclone fuse3`. To use `--allow-other`, add `user_allow_other` to `/etc/fuse.conf`.

## Install

> For step-by-step instructions covering every common deployment — native Plex + native rclone, Plex in Docker + rclone in Docker, and the DUMB stack (rclone built-in), each with Jellyfin/Emby notes — see **[`docs/INSTALL.md`](docs/INSTALL.md)**. The summary below is the short version.

1. Install the plugin in Dispatcharr (drop it in the plugins directory or use the plugin manager).
2. Open the VODFS settings, pick an HTTP port (default `8888`), and set the Dispatcharr Base URL if it isn't reachable on the default.
3. Click **Enable HTTP Filesystem**.

On first enable VODFS installs its own web dependencies (`uvicorn`, `fastapi`, `jinja2`) into Dispatcharr's Python environment. If your environment blocks that, install them manually:

```bash
/dispatcharrpy/bin/python -m pip install uvicorn fastapi jinja2
```

### Why VODFS needs external dependencies

VODFS runs a small HTTP server in its **own child process** (bound to a port you choose), separate from Dispatcharr's web workers. It does this on purpose: serving file bytes-ranges and directory walks to rclone must never block Dispatcharr's request workers, and the child needs its own control over the bind host and a plain blocking DB path. That child process is an ASGI app, and Dispatcharr ships a Django/WSGI (gevent) stack — not an ASGI one — so the three pieces that stack lacks are pulled in explicitly:

| Dependency | Why it's needed |
|------------|-----------------|
| **`fastapi`** | The web framework that *is* the filesystem: routing for the `GET`/`HEAD` handlers, the directory-index responses, `302` redirects to Dispatcharr's VOD proxy, and the `/healthz`, `/stats`, and `/rclone_conf` endpoints. |
| **`uvicorn`** | The ASGI server that actually runs the FastAPI app and listens on the port — the HTTP listener rclone connects to. Dispatcharr's gevent/WSGI server can't host an ASGI app. |
| **`jinja2`** | Renders the minimal HTML directory-index pages that rclone's `http` backend parses to walk the tree. No template engine, no listings rclone can read. |

These are small, ubiquitous, MIT/BSD-licensed PyPI packages with no native build step. They are installed **only into Dispatcharr's existing Python environment** (the same `pip` Dispatcharr itself uses) — VODFS does not create a venv, download binaries, or touch system packages. You can pre-install them yourself (command above) and VODFS will detect them and skip the install. The check is a simple `importlib.util.find_spec` for each module; if all three are present, nothing is installed.

What VODFS does **not** add: it needs no database driver of its own. The standalone child reuses Dispatcharr's already-installed **psycopg3**, simply swapping the gevent connection pool for the standard blocking backend inside its own process — so there is no extra DB dependency to install. Beyond the three packages above, VODFS pulls in nothing.

## rclone configuration & mounting

After enabling, open `http://<vodfs-host>:8888/rclone_conf` for a paste-ready `[vodfs]` remote. Whatever host you open it from is the host that ends up in `url =`, so use the address rclone will actually reach (the container or LAN IP, not `127.0.0.1`).

Mount on the host that serves media to Plex:

```bash
sudo mkdir -p /mnt/vodfs
rclone mount vodfs: /mnt/vodfs \
  --allow-other --read-only --dir-cache-time 5m \
  --vfs-cache-mode off --no-modtime --poll-interval 0 --daemon
```

Unmount with `fusermount -u /mnt/vodfs`. The native proxy honours `Range`, so `--vfs-cache-mode off` direct-plays fine; switch to `--vfs-cache-mode full` if your provider's CDN is slow to seek.

## Plex setup

Add a **Movie** library at `/mnt/vodfs/Movies/All` and a **TV** library at `/mnt/vodfs/Series/All` (or point at individual categories for smaller libraries). Then:

- Use the current **Plex Movie** / **Plex TV Series** agents (the `{tmdb-}`/`{imdb-}` hints only work with these, not the legacy agents).
- **Scan periodically.** Filesystem change notifications don't fire reliably over FUSE mounts, so enable "Scan my library periodically" rather than relying on auto-scan.
- **Tame analysis.** Set "Generate video preview thumbnails" and "Perform extensive media analysis during maintenance" to **never** — deep analysis can pull large amounts of data from your provider.

## Authentication & exposure

By default VODFS is open on its port and honours Dispatcharr's `STREAMS` network-access policy. The server listens on `0.0.0.0` because it must be reachable through the container's published port — so if that port is exposed beyond a trusted network, enable **Authentication (Token-based)** in the plugin settings. VODFS then requires a valid Dispatcharr API key on every request (`Authorization: ApiKey <key>` or `X-API-Key: <key>`); find or generate one under your avatar → **API & XC**. Then uncomment the `headers =` line in the rclone config. VODFS reuses existing Dispatcharr keys — it does not invent a separate password.

## How it works

A directory listing is a Django ORM query against Dispatcharr's `M3UMovieRelation` / `M3USeriesRelation` / `M3UEpisodeRelation` tables, filtered to enabled categories and accounts, rendered as the minimal HTML index rclone's `http` backend speaks. A file open parses the trailing stream ID out of the filename, looks up the exact provider stream, and returns a `302` to `/proxy/vod/movie/...` or `/proxy/vod/episode/...`. Dispatcharr streams the bytes; VODFS never touches media data. On a file `HEAD`/open VODFS probes the proxy once for the real size (cached) so Plex seeks and analyses correctly.

For implementation detail see [`docs/OVERVIEW.md`](docs/OVERVIEW.md), [`docs/HTTPFS.md`](docs/HTTPFS.md), and [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md).

## Troubleshooting

**Config page won't open / folders empty.** Check `curl http://127.0.0.1:8888/healthz`, then `curl http://127.0.0.1:8888/stats` — it returns per-category counts of what VODFS can see. Zero means the problem is upstream (no VOD content, category not enabled, or M3U account inactive).

**Plex sees titles but playback fails.** The redirect targets the **Dispatcharr Base URL** plugin setting. It must be reachable *from the Plex host*, not just from Dispatcharr — set it to a LAN address or container alias Plex can resolve.

**Plex scans are slow.** The `/All` directories are the largest; point Plex at specific categories for smaller, faster libraries. The first scan also probes each file once for its real size, which warms a cache.

More in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## License

MIT.
