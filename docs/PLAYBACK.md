# Playback: rclone, provider connections, and why dev ≠ prod

VODFS itself is only ever a directory listing + a 302 redirect — it never touches
the media bytes. So once a title is **visible and correctly sized** (see
`SIZING.md`), every remaining playback problem lives in the **rclone mount**, the
**Dispatcharr VOD proxy**, or the **provider** — not in VODFS. The three things that
actually decide whether a file plays smoothly:

## 1. rclone must use `--vfs-cache-mode full` for Plex

Plex doesn't read a file once, start to finish. It **transcodes/remuxes** (DASH),
reads ahead aggressively, and **seeks** — resume-from-position, scrubbing, replay.

- With **`--vfs-cache-mode off`**, every seek re-opens the source from a new offset,
  re-fetching from the provider each time. That thrashes, and against a
  connection-limited provider it fails (`No available stream`). Symptom in Plex
  logs: the player re-requests the **same segment** (`…/<n>.m4s`) over and over while
  the transcoder dies with *"didn't get any data … End of file"*.
- With **`--vfs-cache-mode full`**, rclone caches read data to local disk; seeks and
  replays are served from the cache and the provider is read **once**.

Recommended mount (bound the cache to your disk):
```
rclone mount vodfs: /mnt/vodfs --allow-other --read-only \
  --vfs-cache-mode full --cache-dir /var/cache/vodfs \
  --vfs-cache-max-size 100G --vfs-cache-max-age 24h \
  --vfs-read-ahead 256M --buffer-size 64M \
  --dir-cache-time 1h --poll-interval 0
```
`cache-mode off` is acceptable only for a single sequential watch with no seeking.

## 2. The provider needs enough concurrent streams

A transcode/remux opens **more than one** connection (a read stream plus seeks). A
provider set to **`max_streams = 1`** therefore fails the moment Plex seeks —
`503 "No available stream"` → ffmpeg `I/O error` → unplayable. Set a few (we use 5):
`PATCH /api/m3u/accounts/<id>/ {"max_streams": 5}`.

## 3. Dispatcharr leaks VOD connections

Each VOD play creates a Redis lock `vod_persistent_connection:<id>` with a **1-hour
TTL** that isn't released promptly. They pile up and occupy the provider's stream
slots, so eventually everything returns `No available stream`. Mitigations:
- Give `max_streams` headroom (so a few leaked slots don't block everything).
- Use the **`dispatcharr_vod_fix`** plugin or Dispatcharr `:dev` (the connection-
  counting fix the community uses).
- Manual clear (frees slots immediately):
  `redis-cli --scan --pattern 'vod_persistent_connection:*' | xargs redis-cli del`

## Why it "worked in dev but not prod" (a testing lesson)

Dev playback was validated with `ffmpeg -ss 20 -frames:v 2` — a single, brief,
~sequential read. Real Plex is a *transcode + read-ahead + seek + resume + replay*
workload against a connection-limited provider with a caching-off mount. The gentle
dev harness never exercised any of the failure modes above, so it passed while prod
thrashed. **To validate VOD playback realistically, test through an actual Plex (or
Jellyfin) client doing a resume/seek — not a one-shot ffmpeg read** — and against a
provider with a realistic `max_streams`.
