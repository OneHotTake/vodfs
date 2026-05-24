# HTTP Filesystem Behavior

VODFS speaks the same minimal protocol that rclone's `http` backend already understands: HTML directory indexes, `HEAD` for metadata, and `GET` that either returns an index or a redirect. There is no WebDAV here, and no need for it — a `<a href="...">` per entry is the whole interface contract.

## Requests

A directory request looks like:

```http
GET /Movies/All/ HTTP/1.1
Host: 127.0.0.1:8888
User-Agent: rclone/v1.65.0
```

and returns a small HTML page with one `<a>` per entry. `HEAD` on a file returns content-type and length headers without a body. `GET` on a file returns:

```http
HTTP/1.1 302 Found
Location: http://dispatcharr/proxy/vod/movie/<uuid>?stream_id=<id>
```

The plugin never streams media bytes itself.

## Path Resolution

There is no manifest or snapshot. Every path is resolved against Dispatcharr's database when the request comes in:

| Path | Handler |
|------|---------|
| `/` | Root index (`Movies`, `Series`) |
| `/Movies/` | Enabled movie categories plus `All` |
| `/Movies/All/` or `/Movies/<Category>/` | `_get_movies_listing` |
| `/Series/All/` or `/Series/<Category>/` | `_get_series_listing` |
| `/Series/<Category>/<Show>/` | `_get_seasons_listing` |
| `/Series/<Category>/<Show>/S01/` | `_get_episodes_listing` |
| Anything else | `404` |

Movie files are formatted as:

```text
{Title} ({Year}) - {ProviderShortName}-{StreamID}.{ext}
```

Episode files as:

```text
S01E01 - {Episode Name} - {ProviderShortName}-{StreamID}.{ext}
```

The stream ID is baked into the filename so a direct file `GET` can be resolved deterministically after a restart, without needing the parent directory to have been listed first.

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
| `500` | Stream URL could not be constructed |

## Content Types

The plugin maps the common video extensions (`.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`) to their usual MIME types and serves directories as `text/html; charset=utf-8`. Range headers are not handled here — the redirect target (Dispatcharr's proxy) handles them.

## Caching

A small in-memory TTL/LRU cache (`plugin/cache.py`) sits in front of directory rendering so repeated `ls` from rclone doesn't re-query the database every time. It is a performance cache only and expires within minutes; the source of truth is always Dispatcharr.
