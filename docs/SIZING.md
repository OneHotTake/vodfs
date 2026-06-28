# File sizes & the visibility gate

VODFS serves a virtual filesystem that Plex (via rclone) scans and plays. Two hard
facts drive the whole sizing design:

1. **Plex needs each file's *exact* size.** rclone caps reads at the size VODFS
   reports on `HEAD`. If that size is **too small**, Plex reads a truncated
   container and fails with *"no video or audio stream"* / `s1001` — the file is
   listed but unplayable. (Too *large* is mostly harmless for MKV but risks
   moov-at-end MP4, so "exact" is the only safe target.)
2. **There's no free size.** A file's size isn't known until something asks the
   provider. Doing that for every file during a Plex scan is one upstream request
   per title — at 100k titles that's a back-to-back storm that can flag the
   account/IP.

## Where the size comes from

Dispatcharr stores the provider's **overall bitrate + duration**, and
`bitrate × duration` reproduces the real file size (verified to ~0.002% on a 4K
movie, ~1% on episodes). VODFS reads it from the two shapes Dispatcharr uses:

| Content | Path in `custom_properties` | Populated by | Coverage out of the box |
|---------|------------------------------|--------------|-------------------------|
| Movies  | `detailed_info.bitrate`      | `refresh_movie_advanced_data` (on-demand) | ~0% until backfilled |
| Episodes| `info.info.bitrate`          | series hydration (`refresh_series_episodes`) | ~99% |

`size_from_bitrate()` normalises both. We deliberately ignore
`video.tags.NUMBER_OF_BYTES` — that's the *video stream alone* and would
under-report the whole file (→ truncation).

## The gate (`VODFS_REQUIRE_SIZE`, default on)

VODFS only surfaces a title whose size it can compute from stored metadata:

- a **movie** needs `detailed_info.bitrate`;
- a **series** needs ≥1 episode with `info.info.bitrate`;
- an **episode** needs `info.info.bitrate`.

Anything unsized stays **hidden**, so Plex never sees it and never tries to open
(and thereby probe) it. **A Plex scan makes zero provider requests for sizing.**
The library is *eventually consistent*: titles appear as their size becomes known.

Because episodes are ~99% covered by normal hydration, **series work immediately**.
Movies need a backfill.

## The backfill (`tools/backfill_sizes.py`)

Drips Dispatcharr's `refresh_movie_advanced_data` over the enabled movie relations
that still lack a bitrate, at a controlled rate — a metadata-only trickle to the
provider, never a burst. Each fetch makes that movie pop into VODFS on its next
listing (it also fills in `tmdb_id`, improving Plex matches).

```
docker exec -e VODFS_BACKFILL_RATE=2 -e VODFS_BACKFILL_LIMIT=all \
  -e PYTHONPATH=/app:/data/plugins/vodfs/plugin \
  -e DJANGO_SETTINGS_MODULE=dispatcharr.settings -w /app <dispatcharr-container> \
  sh -c 'echo "exec(open(\"/data/plugins/vodfs/tools/backfill_sizes.py\").read())" \
         | /dispatcharrpy/bin/python manage.py shell'
```

- `VODFS_BACKFILL_RATE` — relations/sec (default 2 → ~100k in ~14 h).
- `VODFS_BACKFILL_LIMIT` — cap per run, or `all` (default 5000). Run in waves.
- `VODFS_BACKFILL_FORCE` — re-fetch titles refreshed <24 h ago (default false).

Idempotent — re-running only picks up what's still unsized. Watch progress with
`/stats` (`movies.sized` climbing toward `movies.total`).

## Turning the gate off

Set `VODFS_REQUIRE_SIZE=false` to show everything immediately, and
`VODFS_PROBE_SIZE=true` so playback still gets a real size (VODFS probes the proxy
on file open and caches it). This brings back per-scan provider probing — only do it
on a small library, or pair it with a Dispatcharr per-provider max-connections cap.
