"""FastAPI HTTP server for VOD filesystem"""

import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response

from .tree import VirtualTree
from .httpfs import HTTPFilesystem

logger = logging.getLogger(__name__)


def create_app(tree: VirtualTree) -> FastAPI:
    """Create FastAPI application with HTTP filesystem handlers"""
    app = FastAPI(title="VOD HTTP Filesystem")
    httpfs = HTTPFilesystem(tree)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def handle_request(path: str, request: Request):
        """Handle all filesystem requests"""
        if not path.startswith("/"):
            path = "/" + path
        return await httpfs.handle_request(path, request)

    @app.get("/")
    async def root():
        """Root endpoint"""
        return await httpfs.handle_request("/", Request(scope={"type": "http", "method": "GET"}))

    return app


def run_server(port: int, log_level: str = "info"):
    """Run the FastAPI server using uvicorn"""
    # Import here so Django is already set up by standalone_runner
    from .tree import VirtualTree

    tree = VirtualTree()
    tree.build()

    app = create_app(tree)

    logger.info("Uvicorn starting on 127.0.0.1:%d", port)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level=log_level,
        access_log=True
    )