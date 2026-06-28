# HTTP Filesystem Behavior

VODFS speaks the same minimal protocol that rclone's `http` backend already understands: HTML directory indexes, `HEAD` for metadata, and `GET` that either returns an index or a redirect. There is no WebDAV here, and no need for it — a `<a href="...">` per entry is the whole interface contract.

## Requests

A directory request looks like:

```http
GET /Movies/All/ HTTP/1.1
Host: 127.0.0.1:8888
User-Agent: rclone/v1.65.0
```

and returns a small HTML page with one `<a>` per entry. `HEAD` on a file returns content-type and length headers without a body — the `Content-Length` is the real size, which VODFS probes from Dispatcharr's proxy on first access and caches (see [OVERVIEW.md](OVERVIEW.md#size-probing)). `GET` on a file returns:

```http
HTTP/1.1 302 Found
Location: http://dispatcharr/proxy/vod/movie/<uuid>?stream_id=<id>
```

The plugin never streams media bytes itself.

## Path Resolution

There is no manifest or snapshot. Every path is resolved against Dispatcharr's database when the request comes in:

| Path | Resolves to |
|------|-------------|
| `/` | Root index (`Movies`, `Series`) |
| `/Movies/` | Enabled movie categories plus `All` |
| `/Movies/All/` or `/Movies/<Category>/` | `tree.movies` — one folder per movie |
| `/Movies/<…>/<Movie Folder>/` | `tree.movie_files` — one file per provider stream |
| `/Series/All/` or `/Series/<Category>/` | `tree.series` — one folder per show |
| `/Series/<…>/<Show>/` | `tree.seasons` — `Season NN` folders |
| `/Series/<…>/<Show>/Season 01/` | `tree.episodes` — one file per provider stream |
| Anything else | `404` |

These all arrive at the catch-all `/{path}` route, which hands off to `tree.resolve_path_with_db` (for a single node / file redirect) or the listing builder in `httpfs.py`. The named endpoints `/healthz`, `/readyz`, `/status`, `/stats`, and `/rclone_conf` are matched ahead of the catch-all.

Each movie is its own folder; the files inside are formatted as:

```text
{Title} ({Year}) {tmdb-NNN} {imdb-ttNNN} - {PROVIDER} - {StreamID}.{ext}
```

Episode files (under `Season NN/`) as:

```text
{Show} ({Year}) - S01E01 - {Episode Title} - {StreamID}.{ext}
```

The provider label is only present when a title has more than one provider stream. The trailing stream ID is what a direct file `GET` resolves on — it's unique per M3U account, so the file maps back to one provider stream deterministically after a restart, without re-parsing the rest of the name and without needing the parent directory to have been listed first.

## Directory Index

The HTML is intentionally bland: a table with `Name` and `Size` columns, a `../` link at the top, directories before files, names URL-encoded. rclone's HTTP parser is tolerant but conservative; this format has been the path of least surprise.

## Status Codes

| Status | When |
|--------|------|
| `200` | Directory listing or `HEAD` on a known file |
| `301` | Directory request without trailing slash, redirected to the slashed form |
| `302` | `GET` on a file, redirecting to Dispatcharr's VOD proxy |
| `404` | Unknown path |
| `405` | Method other than `GET` or `HEAD` |
| `500` | Directory listing raised (logged with a traceback) |

## Content Types

Files are served as `video/x-matroska` with `Accept-Ranges: bytes` and the probed real `Content-Length`; directories are `text/html; charset=utf-8`. Range requests for media bytes are not handled here — the `GET` redirects to Dispatcharr's proxy, which serves the bytes with `Range` support.

## Subtitles and Audio Languages

There are no sidecar subtitle files. The Xtream-codes API carries no subtitle data, so there is nothing for VODFS to write out. Multi-language audio and subtitle tracks are the ones embedded in the streamed container; Plex surfaces them when it analyses the proxied stream, which only works once the `HEAD`/open size probe has reported an accurate file size.

## Caching

A small in-memory TTL/LRU cache (`plugin/cache.py`) sits in front of directory rendering so repeated `ls` from rclone doesn't re-query the database every time. It is a performance cache only and expires within minutes; the source of truth is always Dispatcharr.
