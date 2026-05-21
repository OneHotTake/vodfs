"""HTTP filesystem request handlers"""

import logging
from typing import Dict, Any, Optional
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
from urllib.parse import quote

from .tree import FSNode, DirectoryNode, FileNode, VirtualTree


logger = logging.getLogger(__name__)


class HTTPFilesystem:
    """HTTP filesystem request handlers"""

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
        """Handle GET request"""
        node = self.tree.resolve_path(path)

        if node is None:
            return Response(status_code=404, content="Not found")

        # Directory without trailing slash -> redirect
        if node.is_directory() and not path.endswith("/"):
            return RedirectResponse(url=f"{path}/", status_code=301)

        if node.is_directory():
            return await self.serve_directory(node, path)
        else:
            return await self.serve_file(node)

    async def handle_head(self, path: str, request: Request) -> Response:
        """Handle HEAD request"""
        node = self.tree.resolve_path(path)

        if node is None:
            return Response(status_code=404, content="Not found")

        # Directory without trailing slash -> redirect
        if node.is_directory() and not path.endswith("/"):
            return RedirectResponse(url=f"{path}/", status_code=301)

        if node.is_directory():
            return Response(status_code=200, headers={"content-type": "text/html"})
        else:
            return await self.head_file(node)

    async def serve_directory(self, node: DirectoryNode, path: str) -> Response:
        """Serve directory listing as HTML"""
        entries = []

        # Parent directory link (unless at root)
        if path != "/":
            entries.append({
                "name": "../",
                "href": "../"
            })

        # Sort children: directories first, then files
        children = sorted(
            node.children,
            key=lambda x: (0 if x.is_directory() else 1, x.name.lower())
        )

        for child in children:
            if child.is_directory():
                href = quote(child.name + "/")
                entries.append({
                    "name": child.name + "/",
                    "href": href
                })
            else:
                href = quote(child.name)
                entries.append({
                    "name": child.name,
                    "href": href,
                    "size": child.get_file_size()
                })

        html = self._render_directory_html(path, entries)
        return HTMLResponse(content=html)

    async def serve_file(self, node: FileNode) -> Response:
        """Serve file - redirect to stream URL"""
        stream_url = node.metadata.get("stream_url")

        if not stream_url:
            return Response(status_code=500, content="No stream URL available")

        # 302 redirect to Dispatcharr proxy URL
        return RedirectResponse(url=stream_url, status_code=302)

    async def head_file(self, node: FileNode) -> Response:
        """Handle HEAD request for file"""
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": node.get_content_type(),
            "Content-Length": str(node.get_file_size())
        }

        # Add Last-Modified if available
        if "last_modified" in node.metadata:
            headers["Last-Modified"] = node.metadata["last_modified"]

        return Response(status_code=200, headers=headers)

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