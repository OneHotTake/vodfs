# HTTP Filesystem Design

## Protocol Choice

The plugin implements a **simple HTTP directory listing protocol** compatible with rclone's `http` backend.

**Why not WebDAV?**
- WebDAV is complex and overkill for read-only browsing
- rclone's `http` backend is simpler and sufficient
- Fewer dependencies and edge cases
- Better performance for large libraries

## Request Flow

### GET Request

```
GET /Movies/All/ HTTP/1.1
Host: 127.0.0.1:8888
User-Agent: rclone/v1.65.0
```

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
...
</html>
```

### HEAD Request

```
HEAD /Movies/All/Inception (2010).mkv HTTP/1.1
Host: 127.0.0.1:8888
User-Agent: rclone/v1.65.0
```

**Response**:
```http
HTTP/1.1 200 OK
Content-Type: video/x-matroska
Content-Length: 1234567890
Accept-Ranges: bytes
Last-Modified: Mon, 20 May 2026 12:00:00 GMT
```

### GET File Request

```
GET /Movies/All/Inception (2010).mkv HTTP/1.1
Host: 127.0.0.1:8888
User-Agent: Plex/1.32.0
```

**Response**:
```http
HTTP/1.1 302 Found
Location: /proxy/vod/movie/abc123-def456-ghi789?stream_id=12345
```

## Directory Listing Format

The plugin generates HTML directory listings that rclone can parse.

**Template**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Index of /Movies/All/</title>
    <style>
        body { font-family: monospace; padding: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th { text-align: left; padding: 5px; border-bottom: 1px solid #ccc; }
        td { padding: 5px; }
        a { text-decoration: none; color: #0066cc; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Index of /Movies/All/</h1>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Size</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><a href="../">../</a></td>
                <td></td>
            </tr>
            <tr>
                <td><a href="Inception%20%282010%29.mkv">Inception (2010).mkv</a></td>
                <td>1234567890</td>
            </tr>
            <tr>
                <td><a href="The%20Matrix%20%281999%29.mkv">The Matrix (1999).mkv</a></td>
                <td>987654321</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
```

**Key Points**:
- Parent directory link (`../`) at top
- Directories sorted first (by name)
- Files sorted next (by name)
- URLs are URL-encoded
- File size shown in bytes

## Headers

### Directory Response (GET/HEAD)

```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
```

### File Response (HEAD)

```http
HTTP/1.1 200 OK
Content-Type: video/x-matroska
Content-Length: 1234567890
Accept-Ranges: bytes
Last-Modified: Mon, 20 May 2026 12:00:00 GMT
```

### File Response (GET)

```http
HTTP/1.1 302 Found
Location: /proxy/vod/movie/abc123?stream_id=12345
```

## Path Resolution

Path resolution follows standard filesystem semantics:

1. Split path by `/`
2. Traverse tree from root
3. Return node or None (404)

**Examples**:
- `/` → Root node (Movies, Series)
- `/Movies/` → Movies directory
- `/Movies/All/` → All movies directory
- `/Movies/Action/` → Action category directory
- `/Movies/All/Inception (2010).mkv` → File node
- `/Invalid/Path/` → None (404)

## Trailing Slash Handling

Directories without trailing slash return 301 redirect:

```
GET /Movies/All HTTP/1.1
→
HTTP/1.1 301 Moved Permanently
Location: /Movies/All/
```

This ensures consistent behavior and proper relative link resolution.

## Error Handling

| Status | Description |
|--------|-------------|
| 200 | Success (directory listing, HEAD on file) |
| 301 | Trailing slash redirect |
| 302 | Redirect to stream URL |
| 404 | Not found (invalid path) |
| 405 | Method not allowed |
| 500 | Internal error (no stream URL, etc.) |

## Content-Type Mapping

| Extension | Content-Type |
|-----------|--------------|
| .mkv | video/x-matroska |
| .mp4 | video/mp4 |
| .avi | video/x-msvideo |
| .mov | video/quicktime |
| .wmv | video/x-ms-wmv |
| .flv | video/x-flv |
| .webm | video/webm |
| directory | text/html |

## Range Support (Future)

For seekable playback, the plugin may support Range headers:

```
GET /Movies/All/Video.mkv HTTP/1.1
Host: 127.0.0.1:8888
Range: bytes=0-1023
```

**Response**:
```http
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/1234567890
Content-Length: 1024
Accept-Ranges: bytes
```

**Note**: Currently, all requests redirect to Dispatcharr proxy, which handles Range headers. The plugin itself doesn't stream data.