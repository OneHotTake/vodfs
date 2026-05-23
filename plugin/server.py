"""FastAPI HTTP server for VOD filesystem"""

import logging
import threading
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response

try:
    from .tree import VirtualTree
    from .httpfs import HTTPFilesystem
except ImportError:
    from tree import VirtualTree
    from httpfs import HTTPFilesystem

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


def _hydrate_background(tree: VirtualTree):
    """Hydrate tree in background thread"""
    try:
        try:
            from integration import DispatcharrIntegrator
        except ImportError:
            from .integration import DispatcharrIntegrator

        integrator = DispatcharrIntegrator()
        if integrator.is_available():
            logger.info("Hydrating tree from Dispatcharr (background)...")
            movies = integrator.get_all_movies()
            series = integrator.get_all_series()
            tree.hydrate_from_dispatcharr(movies, series, integrator)
            logger.info("Hydrated %d movies and %d series", len(movies), len(series))
        else:
            logger.warning("Dispatcharr integration not available, tree will be empty")
    except Exception as e:
        logger.error("Failed to hydrate tree: %s", e)


def run_server(port: int, log_level: str = "info"):
    """Run the FastAPI server using uvicorn"""
    tree = VirtualTree()
    tree.build()

    # Start hydration in background thread
    hydrate_thread = threading.Thread(target=_hydrate_background, args=(tree,), daemon=True)
    hydrate_thread.start()

    app = create_app(tree)

    logger.info("Uvicorn starting on 0.0.0.0:%d", port)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        access_log=True
    )