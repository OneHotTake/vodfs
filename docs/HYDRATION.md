# Hydration — sizing your library (and why you shouldn't size *all* of it)

VODFS only shows a title once Dispatcharr knows its exact size (stored bitrate), so
Plex never has to probe the provider during a scan. **Hydration** is the background
job that fetches those sizes: a `get_vod_info` round-trip per movie, plus an episode
batch per un-hydrated series. Until a title is hydrated it stays hidden.

This doc covers how long that takes and — importantly — why you should scope what you
expose rather than hydrating an entire 100k-title provider.

## How fast it goes

Each fetch is a network round-trip to the provider (~0.5–1.7s), so throughput is set
by **concurrency** (`⚡ Hydration Concurrency`), not CPU. Fetches run in a bounded
thread pool; concurrency is both the speed knob and the provider-load cap — never more
than N requests are in flight at once.

Measured on real hardware:

| Mode | Concurrency | Throughput | Notes |
|------|-------------|-----------|-------|
| Serial drip (old) | 1 | **~1.1 / sec** | network-latency-bound, CPU idle 90% |
| Parallel (slow provider) | 12 | **~6 / sec** | ~5.5× faster |
| Parallel (typical provider) | 16 | **~9–10 / sec** | ~8.5× faster |

Throughput scales roughly linearly with concurrency until the provider's metadata API
starts pushing back. 16–24 is a sane ceiling for an initial fill; the default of 8 is
a gentle steady-state.

## Approximate time to fully size a library

At the typical **~10/sec** (concurrency 16). Counts are *streams to size* — on a
multi-provider library that's roughly 1.5–2× the number of unique titles, since the
same movie appears once per provider.

| Streams to size | Approx. full-hydration time | ~80% visible by* |
|-----------------|-----------------------------|------------------|
| 1,000           | ~2 min                      | ~1 min  |
| 5,000           | ~8 min                      | ~5 min  |
| 10,000          | ~17 min                     | ~10 min |
| 25,000          | ~42 min                     | ~25 min |
| 50,000          | ~1.4 h                      | ~50 min |
| 100,000         | ~2.8 h                      | ~1.7 h  |
| 200,000         | ~5.6 h                      | ~3.3 h  |

\* A title appears after its *first* stream is sized, so the library looks "mostly
there" well before every stream is done.

Halve these times at concurrency 24–32 (watch for provider errors); double them at the
default 8.

The nightly 3am pass is **time-capped to 240 minutes** (`VODFS_HYDRATE_MAX_MINUTES`)
so it can't bleed into peak viewing — a library that needs more than one cap's worth
just finishes over successive nights.

## ⚠️ Don't expose your entire provider

A big XC/M3U provider can carry **100k+ movies and tens of thousands of series**. You
almost certainly don't want all of it in Plex, and hydrating all of it is the slow,
expensive path:

- **Hours of hydration and a metadata-API storm.** 200k streams is ~5–6h of constant
  `get_vod_info` calls. Some providers rate-limit or temp-ban for that.
- **A catalog refresh wipes sizes.** Any Dispatcharr VOD refresh resets
  `custom_properties.detailed_info`, so every movie goes un-sized (hidden) until
  hydration re-fills it. The bigger the library, the longer that recovery window —
  and it recurs on every refresh.
- **Plex hates giant folders.** Even though VODFS streams its listings, a single
  category with 50k+ items makes Plex scans and browsing sluggish. Point Plex at
  per-category dirs, never `/Movies/All`.
- **Most of it is noise.** Dead links, duplicate rips, and content you'll never watch
  all consume hydration time and Plex match effort.

**Recommended:** curate before you hydrate.

1. In Dispatcharr, enable VOD only on the **M3U accounts / categories you actually
   want** — VODFS reflects exactly what's enabled, so disabling a category there
   removes it here.
2. Start with a **small concurrency (8)** and watch `/vodfs/stats` (`movies.sized`
   vs `total`) so you can see the shape and cost before committing.
3. Mount and scan Plex against **specific category dirs**, not the firehose `All`.
4. Only then raise concurrency for the initial fill if the scope is genuinely large.

Think of VODFS as a window onto a *curated slice* of your VOD, not a 1:1 mirror of
every link your provider carries.

## Watching progress

- **🩺 Status** action — visible vs pending, next scheduled run, current concurrency.
- `GET /vodfs/hydrate/status` — `{enabled, running, concurrency, next_run, last_pass}`.
- `GET /vodfs/stats` — `library.movies.sized` vs `total` (and series).
- **💧 Hydrate Now** — kick an immediate pass without waiting for the schedule.

Hydration uses `refresh_movie_advanced_data` / `batch_refresh_series_episodes` — these
are **metadata calls, not streams**, so they don't consume the provider's `max_streams`
slots and won't interrupt playback.
