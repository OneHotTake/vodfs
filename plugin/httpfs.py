"""HTTP filesystem request handlers with lazy resolution and caching"""

import logging
from typing import Dict, Any, Optional, List
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
from urllib.parse import quote
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    from .tree import FSNode, DirectoryNode, FileNode, VirtualTree
    from .cache import LRUCache
except ImportError:
    from tree import FSNode, DirectoryNode, FileNode, VirtualTree
    from cache import LRUCache


logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)
_directory_cache = LRUCache(max_size=5000, ttl=600)


class HTTPFilesystem:
    """HTTP filesystem request handlers with lazy resolution + cache"""

    def __init__(self, tree: 'VirtualTree'):
        self.tree = tree

    async def handle_request(self, path: str, request: Request) -> Response:
        """Handle incoming HTTP request"""
        if request.method == "GET":
            return await self.handle_get(path, request)
        elif request.method == "HEAD":
            return await self.handle_head(path, request)
        else:
            return Response(status_code=405, content="Method not allowed")

    async def handle_get(self, path: str, request: Request) -> Response:
        """Handle GET request with lazy resolution"""
        node = self.tree.resolve_path_with_db(path)

        if node is None:
            return Response(status_code=404, content="Not found")

        if node.is_directory() and not path.endswith("/"):
            return RedirectResponse(url=f"{path}/", status_code=301)

        if node.is_directory():
            return await self.serve_directory(node, path)
        else:
            return await self.serve_file(node)

    async def handle_head(self, path: str, request: Request) -> Response:
        """Handle HEAD request with lazy resolution"""
        node = self.tree.resolve_path_with_db(path)

        if node is None:
            return Response(status_code=404, content="Not found")

        if node.is_directory() and not path.endswith("/"):
            return RedirectResponse(url=f"{path}/", status_code=301)

        if node.is_directory():
            return Response(status_code=200, headers={"content-type": "text/html; charset=utf-8"})
        else:
            return await self.head_file(node)

    async def serve_directory(self, node: DirectoryNode, path: str) -> Response:
        """Serve directory listing with lazy query + cache"""
        try:
            components = [c for c in path.split("/") if c]

            cache_key = f"dir:{path}"
            cached = _directory_cache.get(cache_key)
            if cached is not None:
                html = self._render_directory_html(path, cached)
                return HTMLResponse(content=html)

            if not components or path == "/":
                entries = [
                    {"name": "Movies/", "href": "Movies/", "size": ""},
                    {"name": "Series/", "href": "Series/", "size": ""}
                ]
            elif components[0] == "Movies" and len(components) == 1:
                # /Movies/ - list categories + All
                entries = [{"name": "../", "href": "../", "size": ""}]
                entries.append({"name": "All/", "href": "All/", "size": ""})
                categories = self.tree._manifest_manager.get_categories('movies')
                for cat in categories:
                    entries.append({"name": cat + "/", "href": cat + "/", "size": ""})
            elif components[0] == "Series" and len(components) == 1:
                # /Series/ - list categories + All
                entries = [{"name": "../", "href": "../", "size": ""}]
                entries.append({"name": "All/", "href": "All/", "size": ""})
                categories = self.tree._manifest_manager.get_categories('series')
                for cat in categories:
                    entries.append({"name": cat + "/", "href": cat + "/", "size": ""})
            elif components[0] == "Movies" and len(components) >= 2:
                if components[1] == "All":
                    entries = await self._get_movies_listing(None)
                else:
                    entries = await self._get_movies_listing(components[1])
            elif components[0] == "Series" and len(components) == 2:
                if components[1] == "All":
                    entries = await self._get_series_listing(None)
                else:
                    entries = await self._get_series_listing(components[1])
            elif components[0] == "Series" and len(components) == 3:
                # /Series/{Category}/{Show}/ - list seasons
                series_name = components[2]
                entries = await self._get_seasons_listing(series_name)
            elif components[0] == "Series" and len(components) >= 4:
                # /Series/{Category}/{Show}/S01/ - list episodes
                series_name = components[2]
                season_name = components[3]
                entries = await self._get_episodes_listing(series_name, season_name)
            else:
                entries = []

            _directory_cache.set(cache_key, entries)

            html = self._render_directory_html(path, entries)
            return HTMLResponse(content=html)

        except Exception as e:
            logger.error("Failed to serve directory %s: %s", path, e)
            import traceback
            logger.error(traceback.format_exc())
            return Response(status_code=500, content="Error listing directory")

    async def _get_movies_listing(self, category: Optional[str]) -> List[Dict[str, str]]:
        """Get movies listing with lazy DB query"""
        loop = asyncio.get_event_loop()
        movies = await loop.run_in_executor(_executor, self.tree.get_movies_from_db, category)

        entries = [{"name": "../", "href": "../", "size": ""}]

        for movie in movies:
            href = quote(movie.name)
            size = self._format_size(movie.get_file_size()) if movie.get_file_size() else ""
            entries.append({
                "name": movie.name,
                "href": href,
                "size": size
            })

        return entries

    async def _get_series_listing(self, category: Optional[str]) -> List[Dict[str, str]]:
        """Get series listing with lazy DB query"""
        loop = asyncio.get_event_loop()
        series = await loop.run_in_executor(_executor, self.tree.get_series_from_db, category)

        entries = [{"name": "../", "href": "../", "size": ""}]

        for show in series:
            href = quote(show.name + "/")
            entries.append({
                "name": show.name + "/",
                "href": href,
                "size": ""
            })

        return entries

    async def _get_seasons_listing(self, series_name: str) -> List[Dict[str, str]]:
        """Get seasons/episodes listing with lazy DB query"""
        logger.info("_get_seasons_listing called for: %s", series_name)
        series_uuid = self._extract_series_uuid(series_name)
        logger.info("_get_seasons_listing found UUID: %s", series_uuid)

        if not series_uuid:
            logger.warning("Could not find UUID for series: %s", series_name)
            return []

        loop = asyncio.get_event_loop()
        seasons = await loop.run_in_executor(_executor, self.tree.get_seasons_from_db, series_uuid)

        entries = [{"name": "../", "href": "../", "size": ""}]

        for season in seasons:
            href = quote(season.name + "/")
            entries.append({
                "name": season.name + "/",
                "href": href,
                "size": ""
            })

        return entries

    async def _get_episodes_listing(self, series_name: str, season_name: str) -> List[Dict[str, str]]:
        """Get episodes listing for a specific season with lazy DB query"""
        logger.info("_get_episodes_listing called for: %s/%s", series_name, season_name)
        series_uuid = self._extract_series_uuid(series_name)
        logger.info("_get_episodes_listing found UUID: %s", series_uuid)

        if not series_uuid:
            logger.warning("Could not find UUID for series: %s", series_name)
            return []

        loop = asyncio.get_event_loop()
        seasons = await loop.run_in_executor(_executor, self.tree.get_seasons_from_db, series_uuid)

        entries = [{"name": "../", "href": "../", "size": ""}]

        for season in seasons:
            if season.name == season_name:
                for child in season.children:
                    if child.is_file():
                        href = quote(child.name)
                        size = self._format_size(child.get_file_size()) if child.get_file_size() else ""
                        entries.append({
                            "name": child.name,
                            "href": href,
                            "size": size
                        })
                break

        return entries

    def _extract_series_uuid(self, series_name: str) -> Optional[str]:
        """Extract series UUID from series directory name using manifest"""
        skeleton = self.tree._manifest_manager.get_series_skeleton()
        logger.info("_extract_series_uuid looking for: %s (skeleton count: %d)", series_name, len(skeleton))

        for series in skeleton:
            # Try both formats: name may already include year
            display_name_with_year = f"{series['name']} ({series['year']})"
            logger.debug("  Checking: name='%s', with_year='%s' vs target='%s'", series['name'], display_name_with_year, series_name)
            if series['name'] == series_name or display_name_with_year == series_name:
                logger.info("  MATCH found: %s", series['uuid'])
                return series['uuid']

        logger.warning("No match found for series_name: %s", series_name)
        return None

    async def serve_file(self, node: FileNode) -> Response:
        """Serve file - redirect to stream URL"""
        stream_url = node.metadata.get("stream_url")

        if not stream_url:
            return Response(status_code=500, content="No stream URL available")

        return RedirectResponse(url=stream_url, status_code=302)

    async def head_file(self, node: FileNode) -> Response:
        """Handle HEAD request for file"""
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": node.get_content_type(),
            "Content-Length": str(node.get_file_size())
        }

        if "last_modified" in node.metadata:
            headers["Last-Modified"] = node.metadata["last_modified"]

        return Response(status_code=200, headers=headers)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size"""
        if size_bytes == 0:
            return ""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                if unit == "B":
                    return f"{int(size)}"
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _render_directory_html(self, path: str, entries: list) -> str:
        """Render directory listing HTML"""
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <title>Index of {{ path }}</title>
    <style>
        body { font-family: monospace; padding: 20px; }
        h1 { margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th { text-align: left; padding: 5px; border-bottom: 1px solid #ccc; }
        td { padding: 5px; }
        a { text-decoration: none; color: #0066cc; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Index of {{ path }}</h1>
    <table>
        <thead>
            <tr>
                <th>Name</th>
                <th>Size</th>
            </tr>
        </thead>
        <tbody>
            {% for entry in entries %}
            <tr>
                <td><a href="{{ entry.href }}">{{ entry.name }}</a></td>
                <td>{{ entry.get('size', '') }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""
        template = Template(template_str)
        return template.render(path=path, entries=entries)
