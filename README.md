# VODFS for Dispatcharr

VODFS exposes your Dispatcharr VOD library as a simple HTTP filesystem that rclone can mount for Plex, Jellyfin, Emby, or ordinary browsing.

It does not copy media, scan provider playlists itself, or maintain a separate library. Dispatcharr stays the source of truth. VODFS only asks Dispatcharr what movies, series, seasons, and episodes are currently enabled, then returns folder listings and redirects playback back through Dispatcharr's VOD proxy.

## What You Get

- Browse Dispatcharr VOD as folders and files.
- Mount the library with rclone.
- Add `/Movies/All` and `/Series/All` to Plex.
- Browse enabled Dispatcharr VOD categories as folders.
- Keep multiple provider streams as separate playable files.
- Stream through Dispatcharr's existing proxy instead of exposing provider URLs.
- Get a copy/paste rclone config from `http://<vodfs-host>:8888/rclone_conf`.

## How It Looks

After mounting, the filesystem looks like this:

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

`All` is a sibling of your categories. It is not a parent folder. This makes Plex setup simple: point movie libraries at `/Movies/All` and TV libraries at `/Series/All`.

## Requirements

- Dispatcharr with VOD content already loaded.
- One or more enabled VOD categories in Dispatcharr.
- rclone installed on the machine that will mount the filesystem.
- Plex, Jellyfin, Emby, or another client that can read from the mounted folder.

## Install

1. Install the plugin in Dispatcharr.
2. Open Dispatcharr settings for the VODFS plugin.
3. Choose an HTTP port. The default is `8888`.
4. Set the Dispatcharr Base URL if needed.
5. Click **Enable HTTP Filesystem**.

For most local installs, the default settings are enough.

## Get Your rclone Config

After enabling the plugin, open this URL in your browser:

```text
http://<vodfs-host>:8888/rclone_conf
```

Examples:

```text
http://127.0.0.1:8888/rclone_conf
http://192.168.1.21:8888/rclone_conf
http://172.19.0.2:8888/rclone_conf
```

The page returns plain text you can copy directly into your `rclone.conf`. It includes:

- the `[vodfs]` remote block
- a suggested mount point
- the mount command
- Plex movie and series paths
- the optional API key header for secured installs

Example output:

```ini
# VODFS rclone remote
# Paste the [vodfs] block into your rclone.conf file.
# Suggested mount point: /mnt/vodfs
# Mount command:
#   mkdir -p /mnt/vodfs
#   rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
# Plex library paths:
#   Movies: /mnt/vodfs/Movies/All
#   Series: /mnt/vodfs/Series/All
# Secured installs: enable plugin auth, then uncomment the headers line and replace the placeholder.

[vodfs]
type = http
url = http://192.168.1.21:8888/
# headers = Authorization, ApiKey <your-dispatcharr-api-key>
```

## Mount With rclone

Create your mount point:

```bash
sudo mkdir -p /mnt/vodfs
```

Mount VODFS:

```bash
rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
```

For a background mount, add `--daemon`:

```bash
rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0 --daemon
```

Quick check:

```bash
ls /mnt/vodfs
ls /mnt/vodfs/Movies/All
ls /mnt/vodfs/Series/All
```

## Add to Plex

In Plex Media Server:

1. Add a movie library.
2. Use this folder:

```text
/mnt/vodfs/Movies/All
```

3. Add a TV library.
4. Use this folder:

```text
/mnt/vodfs/Series/All
```

5. Scan the libraries.

You can also point Plex at category folders if you want smaller libraries, for example:

```text
/mnt/vodfs/Movies/[EN] NEW RELEASES
/mnt/vodfs/Series/APPLE+ SERIES
```

## Secured Installs

VODFS can require a Dispatcharr API key. Enable **Authentication (Token-based)** in the plugin settings.

Then use this in your rclone config:

```ini
[vodfs]
type = http
url = http://192.168.1.21:8888/
headers = Authorization, ApiKey <your-dispatcharr-api-key>
```

Use an active Dispatcharr API key. No new VODFS-specific password is created.

## How It Works

At a high level:

1. rclone asks VODFS for a folder listing.
2. VODFS queries Dispatcharr's database for the currently enabled VOD categories and content.
3. VODFS returns a normal HTML directory listing that rclone understands.
4. When a player opens a file, VODFS returns an HTTP `302` redirect to Dispatcharr's VOD proxy.
5. Dispatcharr streams the media from the provider.

VODFS does not proxy video bytes itself. That keeps the plugin lightweight and lets Dispatcharr handle the actual streaming path.

## Troubleshooting

### The rclone config page does not open

Check that the plugin server is running:

```bash
curl http://127.0.0.1:8888/healthz
```

If Dispatcharr runs in Docker, use the container IP or host-mapped address instead of `127.0.0.1`.

### rclone mounts, but folders are empty

Check these in Dispatcharr:

- VOD content exists.
- VOD categories are enabled.
- The provider/account for that content is enabled.

Then try:

```bash
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Series/
```

### Plex sees movies but playback fails

Make sure the **Dispatcharr Base URL** plugin setting is reachable from the machine running Plex/rclone. Playback redirects go to Dispatcharr's proxy, not directly to the IPTV provider.

### Plex scans too slowly

Start with `/Movies/All` and `/Series/All`. If the library is very large, consider adding category-specific libraries so Plex scans smaller folders.

### Stop the mount

```bash
fusermount -u /mnt/vodfs
```

## More Detail

- Architecture: [`architecture/OVERVIEW.md`](architecture/OVERVIEW.md)
- HTTP behavior: [`architecture/HTTPFS.md`](architecture/HTTPFS.md)
- Troubleshooting notes: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

## License

MIT License.
