# VODFS for Dispatcharr

VODFS exposes your Dispatcharr VOD library as a read-only HTTP filesystem. Point rclone at it, mount the result, and Plex, Jellyfin, or Emby will see your movies and series as ordinary folders and files.

Dispatcharr stays the source of truth. VODFS does not copy media, scan playlists, or hold its own library. Every directory listing is a live query against Dispatcharr's database, and every file open is a `302` redirect into Dispatcharr's existing VOD proxy. The plugin is small on purpose: if it broke or vanished tomorrow, Dispatcharr would still work.

## Layout

Once mounted, the filesystem looks like this:

```text
/mnt/vodfs
  /Movies
    /All
      Example Movie (2024) - STRONG-12345.mkv
      Example Movie (2024) - MEGA-67890.mkv
    /[EN] NEW RELEASES
      Example Movie (2024) - STRONG-12345.mkv

  /Series
    /All
      Example Show (2024)
        /S01
          S01E01 - Pilot - STRONG-11111.mkv
          S01E02 - Next Episode - STRONG-11112.mkv
    /APPLE+ SERIES
      Example Show (2024)
        /S01
          S01E01 - Pilot - STRONG-11111.mkv
```

`All` is a sibling of the category folders, not a parent. That makes Plex setup boringly simple — point a movie library at `/Movies/All`, a TV library at `/Series/All`, and you're done. If a title is carried by more than one provider, each stream shows up as its own file. Pick the one you want; the rest are there if a stream goes down.

## Requirements

- Dispatcharr with VOD content already loaded and at least one VOD category enabled.
- [rclone](https://rclone.org/downloads/) installed on the host that will read the media (typically the Plex host).
- FUSE on that same host so `rclone mount` can produce a real directory.
- A client — Plex, Jellyfin, Emby, or just `ls` — that can read from the mount point.

rclone has to run wherever Plex reads media from. In a Docker setup that usually means mounting on the host and bind-mounting the result into the Plex container:

```text
Dispatcharr/VODFS server  --->  rclone mount on Plex host  --->  Plex library path
```

On Debian/Ubuntu:

```bash
sudo apt install rclone fuse3
```

If you plan to use `--allow-other`, add `user_allow_other` to `/etc/fuse.conf`.

## Install

1. Install the plugin in Dispatcharr.
2. Open the VODFS settings.
3. Pick an HTTP port (default `8888`) and set the Dispatcharr Base URL if it isn't reachable on the default.
4. Click **Enable HTTP Filesystem**.

For most local installs the defaults are fine.

## rclone Configuration

The plugin generates a ready-to-paste config. After enabling it, open:

```text
http://<vodfs-host>:8888/rclone_conf
```

The page returns plain text containing the `[vodfs]` remote block, a suggested mount point, the mount command, the Plex library paths, and an optional `headers =` line for secured installs. Whatever host you opened the page from is the host that ends up in `url =`, so use the IP that rclone will actually be able to reach (typically the Docker container or LAN address, not `127.0.0.1`).

Sample output:

```ini
# VODFS rclone remote
# Suggested mount point: /mnt/vodfs
# Mount command:
#   mkdir -p /mnt/vodfs
#   rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
# Plex library paths:
#   Movies: /mnt/vodfs/Movies/All
#   Series: /mnt/vodfs/Series/All

[vodfs]
type = http
url = http://192.168.1.21:8888/
# headers = Authorization, ApiKey <your-dispatcharr-api-key>
```

## Mounting

Run on the host that serves media to Plex:

```bash
sudo mkdir -p /mnt/vodfs
rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
```

Add `--daemon` to background it. To unmount:

```bash
fusermount -u /mnt/vodfs
```

The recommended flags are aggressive about freshness because Dispatcharr's enabled-content set can change at any time. If you have a stable library and want faster `ls`, raise `--dir-cache-time`.

## Plex

Add a Movie library pointed at `/mnt/vodfs/Movies/All` and a TV library pointed at `/mnt/vodfs/Series/All`, then scan. For smaller, more focused libraries you can point Plex at individual categories instead, e.g. `/mnt/vodfs/Movies/[EN] NEW RELEASES` or `/mnt/vodfs/Series/APPLE+ SERIES`.

## Authentication

By default VODFS is open on the configured port. If your Dispatcharr host isn't on a trusted network, enable **Authentication (Token-based)** in the plugin settings. VODFS will then require a valid Dispatcharr API key on every request, sent either as `Authorization: ApiKey <key>` or `X-API-Key: <key>`.

To find or generate the key:

1. In Dispatcharr, click your avatar in the lower-left.
2. Open the **API & XC** tab.
3. Generate a key if you don't have one and copy it.

Then uncomment the `headers =` line in your rclone config:

```ini
[vodfs]
type = http
url = http://192.168.1.21:8888/
headers = Authorization, ApiKey <your-dispatcharr-api-key>
```

VODFS reuses existing Dispatcharr keys. It does not invent a separate password.

## How It Works

A directory listing is just a Django ORM query against Dispatcharr's `M3UMovieRelation`, `M3USeriesRelation`, and `M3UEpisodeRelation` tables, filtered to the categories and accounts you have enabled, rendered as the same minimal HTML index rclone's `http` backend already speaks. A file open is parsed back to a stream ID and turned into a `302` to Dispatcharr's `/proxy/vod/movie/...` or `/proxy/vod/episode/...` endpoint. Dispatcharr handles the byte streaming; VODFS never touches media data.

This is why the plugin can stay roughly a thousand lines and why it doesn't drift out of sync with Dispatcharr — there is no second copy of the library to drift.

For implementation detail, see [`docs/OVERVIEW.md`](docs/OVERVIEW.md) and [`docs/HTTPFS.md`](docs/HTTPFS.md).

## Troubleshooting

**The rclone config page won't open.** Check that the server is up: `curl http://127.0.0.1:8888/healthz`. If Dispatcharr is in Docker, you need the container IP or a mapped host port, not loopback.

**rclone mounts but the folders are empty.** Hit `/stats` first — it returns counts of what VODFS can currently see, broken down per enabled category:

```bash
curl http://127.0.0.1:8888/stats
```

If the totals are zero, the problem is upstream: confirm in Dispatcharr that VOD content exists, the relevant categories are enabled, and the providing M3U account is active. If `/stats` shows non-zero but a specific folder is empty, check that category in particular. You can also sanity-check the listings directly:

```bash
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Series/
```

**Plex sees titles but playback fails.** The redirect from VODFS points at the **Dispatcharr Base URL** plugin setting. That URL needs to be reachable from the Plex host, not just from Dispatcharr's own host. Set it to a LAN address or container alias that Plex can actually resolve.

**Plex scans are slow.** Start with the `/All` directories — they're the largest. If scans drag, attach Plex to specific categories instead so each library is smaller and more cacheable.

More notes in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## License

MIT.
