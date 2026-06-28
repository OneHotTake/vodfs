# Installation Guide

VODFS is the same on every install: a Dispatcharr plugin that serves an HTTP
filesystem, an **rclone** remote that mounts it, and a **media server** (Plex,
Jellyfin, or Emby) that reads the mount. Only two things change between setups:

1. **Where rclone runs** — directly on the host, in its own container, or
   already-bundled inside a stack like DUMB.
2. **How the media server reaches the mount** — a host path, or a bind-mount
   into a container.

This guide does the common combinations end to end:

| # | rclone | Media server | Jump to |
|---|--------|--------------|---------|
| A | native binary on host | native (Plex/Jellyfin/Emby on host) | [Scenario A](#scenario-a--native-rclone--native-media-server) |
| B | `rclone/rclone` container | container | [Scenario B](#scenario-b--rclone-in-docker--media-server-in-docker) |
| C | built into the **DUMB** stack | the stack's own Plex | [Scenario C](#scenario-c--dumb-rclone-built-in) |

Everything Plex-specific applies equally to **Jellyfin** and **Emby** — the
mount is identical; only the library/agent setup differs. See
[Jellyfin & Emby](#jellyfin--emby) for those deltas.

---

## Step 0 — Install the plugin (do this once, same for everyone)

This part is independent of how you mount or which media server you use.

1. **Install the plugin in Dispatcharr.** Drop the `vodfs` folder into
   Dispatcharr's plugins directory (or use the in-app plugin manager).
2. Open the **VOD HTTP Filesystem** plugin settings and set:
   - **HTTP Port** — default `8888`. Pick any free port ≥ 1024.
   - **Dispatcharr Base URL** — the address of Dispatcharr **as the media-server
     host will reach it** (see the warning below). Default
     `http://127.0.0.1:9191`.
   - **Enable Authentication** — leave **off** for first setup; turn it on later
     if you expose the port (see [Authentication](#authentication--exposure)).
3. Click **🚀 Enable HTTP Filesystem**.

On first enable VODFS installs its own web deps (`uvicorn`, `fastapi`,
`jinja2`) into Dispatcharr's Python env. If your environment blocks that:

```bash
/dispatcharrpy/bin/python -m pip install uvicorn fastapi jinja2
```

Verify the server is up (from the Dispatcharr host):

```bash
curl http://127.0.0.1:8888/healthz      # -> ok
curl http://127.0.0.1:8888/stats        # -> per-category counts; 0 means upstream has no VOD
```

> [!IMPORTANT]
> **The "Dispatcharr Base URL" must be reachable from wherever the media server
> runs, not just from Dispatcharr.** Every file open is a `302` redirect to this
> URL's VOD proxy. If it points at `127.0.0.1` and Plex is in another container
> or on another box, listings will appear but playback will fail. Use a LAN IP
> or a container alias the media server can resolve.

### Get your rclone config

After enabling, open the **rclone config** endpoint from the host that will run
rclone:

```
http://<vodfs-host>:8888/rclone_conf
```

It returns a paste-ready `[vodfs]` block. **The `url =` line uses whatever host
you opened the page from**, so open it from the machine/container that rclone
runs on — use the LAN/container IP, never `127.0.0.1`, unless rclone runs on the
very same host. A typical block:

```ini
[vodfs]
type = http
url = http://192.168.1.50:8888
# headers = Authorization,ApiKey YOUR_DISPATCHARR_API_KEY   # only if auth is enabled
```

Keep this handy — each scenario below tells you where to put it.

---

## Scenario A — native rclone + native media server

Plex/Jellyfin/Emby installed directly on a Linux host, rclone as a host binary.
Simplest setup; the media server just reads a normal directory.

### 1. Install rclone + FUSE

```bash
# Debian/Ubuntu
sudo apt install rclone fuse3
# or always-latest:
curl https://rclone.org/install.sh | sudo bash
```

To let the media-server user read a mount owned by another user (almost always
the case), enable `--allow-other`:

```bash
echo 'user_allow_other' | sudo tee -a /etc/fuse.conf
```

### 2. Add the remote

```bash
mkdir -p ~/.config/rclone
# paste the [vodfs] block from /rclone_conf into:
nano ~/.config/rclone/rclone.conf
```

### 3. Mount

```bash
sudo mkdir -p /mnt/vodfs
rclone mount vodfs: /mnt/vodfs \
  --allow-other --read-only --dir-cache-time 5m \
  --vfs-cache-mode off --no-modtime --poll-interval 0 --daemon
```

Confirm: `ls /mnt/vodfs/Movies/All | head`. Unmount with
`fusermount -u /mnt/vodfs`.

The native proxy honours HTTP `Range`, so `--vfs-cache-mode off` direct-plays
fine. Switch to `--vfs-cache-mode full` only if your provider's CDN seeks
slowly.

### 4. Make the mount persist (systemd)

A one-off `rclone mount` dies on reboot. Run it as a service:

```ini
# /etc/systemd/system/vodfs.service
[Unit]
Description=VODFS rclone mount
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/rclone mount vodfs: /mnt/vodfs \
  --allow-other --read-only --dir-cache-time 5m \
  --vfs-cache-mode off --no-modtime --poll-interval 0
ExecStop=/bin/fusermount -u /mnt/vodfs
Restart=on-failure
RestartSec=10
# run as the user whose ~/.config/rclone/rclone.conf you edited:
User=youruser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vodfs.service
```

### 5. Add the library

Point your media server at `/mnt/vodfs/Movies/All` and `/mnt/vodfs/Series/All`.
See [Media-server library setup](#media-server-library-setup).

---

## Scenario B — rclone in Docker + media server in Docker

rclone runs in the official `rclone/rclone` container, mounts on the **host**
with shared propagation, and the host path is bind-mounted into the media-server
container. This is the reliable pattern: mounting *inside* the media-server
container is fragile, so keep rclone in its own container and share the result.

> [!NOTE]
> A FUSE mount created inside a container is invisible to other containers
> **unless** it is created under a bind-mount with `rshared` propagation. That's
> what `--mount type=bind,...,bind-propagation=rshared` (CLI) /
> `:rshared` (compose) below is doing. Without it, Plex sees an empty folder.

### 1. Prepare the host

```bash
sudo mkdir -p /mnt/vodfs
mkdir -p ./rclone-config
# paste the [vodfs] block into:
nano ./rclone-config/rclone.conf
echo 'user_allow_other' | sudo tee -a /etc/fuse.conf
```

### 2. docker-compose

```yaml
services:
  vodfs-rclone:
    image: rclone/rclone:latest
    container_name: vodfs-rclone
    restart: unless-stopped
    # FUSE needs these:
    cap_add: [SYS_ADMIN]
    devices: ["/dev/fuse"]
    security_opt: ["apparmor:unconfined"]
    volumes:
      - ./rclone-config:/config/rclone
      - type: bind
        source: /mnt/vodfs
        target: /mnt/vodfs
        bind:
          propagation: rshared          # <-- so Plex's container sees the mount
    command: >
      mount vodfs: /mnt/vodfs
      --allow-other --read-only --dir-cache-time 5m
      --vfs-cache-mode off --no-modtime --poll-interval 0

  plex:
    image: plexinc/pms-docker:latest
    container_name: plex
    restart: unless-stopped
    network_mode: host
    environment:
      - TZ=Etc/UTC
      # - PLEX_CLAIM=claim-xxxx        # from https://plex.tv/claim on first run
    volumes:
      - ./plex-config:/config
      - type: bind
        source: /mnt/vodfs
        target: /mnt/vodfs
        bind:
          propagation: rslave           # <-- receives the mount from the host
    depends_on:
      - vodfs-rclone
```

```bash
docker compose up -d
docker exec plex ls /mnt/vodfs/Movies/All | head   # should list movies
```

If `docker exec plex ls /mnt/vodfs` is empty but the rclone container's mount
works, propagation is the culprit — confirm `/mnt/vodfs` is `rshared` on the
host (`findmnt -o TARGET,PROPAGATION /mnt/vodfs`) and the Plex bind is
`rslave`.

### 3. Add the library

Inside the container the path is `/mnt/vodfs/Movies/All` and
`/mnt/vodfs/Series/All`. See
[Media-server library setup](#media-server-library-setup).

> Jellyfin: swap the `plex` service for `jellyfin/jellyfin` (same `cap_add` /
> `devices` are **not** needed for the media-server container — only for the
> rclone one). Emby: use `emby/embyserver`. The bind-mount + propagation is
> identical.

---

## Scenario C — DUMB (rclone built-in)

[DUMB](https://dumbarr.com) (Debrid Unlimited Media Bridge) already bundles
rclone and a media server and shares a single `/mnt` mount between them with
`rshared` propagation. You're adding VODFS *alongside* the debrid mounts so the
same Plex sees both.

> [!NOTE]
> DUMB's managed rclone instances are designed for **debrid/WebDAV** providers —
> it auto-generates their configs. VODFS is a plain `http` remote, so you add it
> manually. Two approaches; pick one. DUMB evolves quickly, so cross-check the
> [DUMB rclone docs](https://dumbarr.com/services/dependent/rclone/) for the
> current `dumb_config.json` schema.

### Approach C1 — a custom rclone instance inside DUMB (most integrated)

1. **Add the VODFS remote to DUMB's rclone config file.** Edit the rclone config
   DUMB uses (e.g. `/config/rclone.config` inside the container, a mounted
   volume on the host) and append the `[vodfs]` block from `/rclone_conf`. Use
   an address the DUMB container can reach (LAN IP of the Dispatcharr/VODFS
   host).

2. **Define a custom instance** in `/config/dumb_config.json` under
   `rclone.instances`, modelled on an existing one but pointing at the `vodfs`
   remote and a fresh mount subdir under the shared `/mnt`:

   ```json
   "VODFS": {
     "enabled": true,
     "process_name": "rclone w/ VODFS",
     "key_type": "",
     "zurg_enabled": false,
     "decypharr_enabled": false,
     "mount_dir": "/mnt/vodfs",
     "mount_name": "vodfs",
     "config_file": "/config/rclone.config",
     "log_file": "/log/rclone_vodfs.log",
     "command": [
       "--allow-other", "--read-only", "--dir-cache-time", "5m",
       "--vfs-cache-mode", "off", "--no-modtime", "--poll-interval", "0"
     ]
   }
   ```

   (No `api_key` / `key_type` — VODFS is not a debrid service. If your auth is
   enabled, the credential travels via the `headers =` line in the rclone
   remote, not here.)

3. **Restart DUMB.** It launches the extra rclone process and mounts VODFS at
   `/mnt/vodfs`, which the bundled Plex already sees because `/mnt` is shared.

### Approach C2 — a sidecar rclone container (decoupled)

If you'd rather not touch `dumb_config.json`, run a separate
`rclone/rclone` container exactly as in [Scenario B](#scenario-b--rclone-in-docker--media-server-in-docker),
but mount into a subdirectory of the **same host path DUMB shares to its Plex**
(commonly `/mnt`), e.g. host `/mnt/vodfs`. DUMB's Plex container, already
bind-mounting that shared path with `rslave`, picks it up. This keeps VODFS
fully independent of DUMB's update cycle.

### Add the library

In DUMB's Plex, add libraries at `/mnt/vodfs/Movies/All` and
`/mnt/vodfs/Series/All` (the path *as seen inside the Plex container*). See
[Media-server library setup](#media-server-library-setup).

---

## Media-server library setup

The mount is read-only and Plex-correctly named, so setup is short. Add a
**Movie** library at `…/Movies/All` and a **TV** library at `…/Series/All`
(or point at individual category folders for smaller, faster libraries — `All`
is a *sibling* of the category folders, not a parent).

### Plex

- Use the current **Plex Movie** and **Plex TV Series** agents — the
  `{tmdb-…}` / `{imdb-…}` filename hints only work with these, not the legacy
  agents.
- **Scan periodically.** FUSE mounts don't deliver reliable change
  notifications, so enable *Scan my library periodically* instead of relying on
  auto-scan.
- **Tame analysis.** Set *Generate video preview thumbnails* and *Perform
  extensive media analysis during maintenance* to **never** — deep analysis can
  pull large amounts of data from your provider.
- Multi-language audio and subtitles are **embedded in the streamed container**
  (VODFS fabricates no sidecar files); Plex surfaces every track once it
  analyses the file, which the accurate size probe enables.

### Jellyfin & Emby

VODFS presents *real* files, so unlike `.strm` setups you don't need any special
plugin — Jellyfin/Emby read the mount like local media. Differences from Plex:

- Add the same two libraries (`…/Movies/All`, `…/Series/All`) with content types
  **Movies** and **Shows / TV**.
- **Metadata downloaders:** enable **TheMovieDb** (and TheTVDB for series).
  Jellyfin/Emby match primarily on the cleaned `Title (Year)` and, where
  present, the embedded TMDB/IMDb IDs.
- Turn off real-time monitoring / library file watching (unreliable over FUSE);
  use a scheduled library scan instead.
- Disable aggressive chapter-image / "extract on scan" options for the same
  bandwidth reason as Plex's extensive analysis.
- Everything else — the mount, propagation, and rclone flags in Scenarios
  A/B/C — is unchanged. Swap the Plex container image for
  `jellyfin/jellyfin` or `emby/embyserver` in Scenario B and proceed.

> Note: `.strm`-based VOD tools exist for Jellyfin/Emby/Kodi, but VODFS's
> real-file approach is what makes the *same* library work in Plex too. If
> you're Jellyfin/Emby-only, dedicated `.strm` generators may fit your workflow
> better — VODFS's advantage is being media-server-agnostic with seekable,
> analysable files.

---

## Authentication & exposure

VODFS binds `0.0.0.0` (it must, to be reachable through a container's published
port). On a trusted LAN that's fine. If the port is reachable from untrusted
networks:

1. In the plugin settings, enable **Authentication (Token-based)**.
2. Get/generate a Dispatcharr API key under your avatar → **API & XC**.
3. Re-open `/rclone_conf` and uncomment the `headers =` line — it carries
   `Authorization,ApiKey <key>`. VODFS reuses existing Dispatcharr keys; it does
   not invent a separate password.

Every request then needs a valid key via `Authorization: ApiKey <key>` or
`X-API-Key: <key>`.

---

## Quick troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Folders empty / config page won't load | `curl …:8888/healthz` then `…/stats`; `0` means upstream has no enabled VOD content. |
| Mount empty *inside* a container | Propagation: rclone side must be `rshared`, media-server side `rslave` (Scenario B). |
| Titles appear but playback fails | **Dispatcharr Base URL** isn't reachable from the media-server host — set a LAN IP / resolvable alias. |
| Slow scans | Point libraries at specific categories instead of the heavy `/All`; first scan also probes each file once for its real size. |
| `rclone mount` exits immediately in Docker | Missing `cap_add: SYS_ADMIN`, `devices: /dev/fuse`, or `security_opt: apparmor:unconfined`. |

More detail in [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) and the architecture
in [`OVERVIEW.md`](OVERVIEW.md).
