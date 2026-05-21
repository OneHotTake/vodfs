"""FastAPI HTTP server for VOD filesystem"""

import argparse
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
        # Normalize path - ensure leading slash
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
    tree = VirtualTree()
    tree.build()

    app = create_app(tree)

    # Bind to 127.0.0.1 only (localhost)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level=log_level,
        access_log=True
    )


def main():
    """Main entry point for running the server"""
    parser = argparse.ArgumentParser(description="VOD HTTP Filesystem Server")
    parser.add_argument("--port", type=int, default=8888, help="Port to listen on")
    parser.add_argument("--log-level", type=str, default="info", help="Log level")
    args = parser.parse_args()

    run_server(args.port, args.log_level)


if __name__ == "__main__":
    main()