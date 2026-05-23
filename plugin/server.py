"""FastAPI HTTP server for VOD filesystem"""

import logging
import os
import threading
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response

try:
    from .tree import VirtualTree
    from .httpfs import HTTPFilesystem
except ImportError:
    from tree import VirtualTree
    from httpfs import HTTPFilesystem

logger = logging.getLogger(__name__)

_ENABLE_AUTH = os.environ.get("VODFS_ENABLE_AUTH", "false").lower() == "true"


def check_network_access(request: Request):
    """Check if client IP is allowed per Dispatcharr STREAMS policy"""
    try:
        from dispatcharr.utils import network_access_allowed
        if not network_access_allowed(request, "STREAMS"):
            raise HTTPException(status_code=403, detail="Forbidden")
    except ImportError:
        # Dispatcharr utils not available, allow (matches default behavior)
        pass


def check_api_key_auth(request: Request):
    """Validate Dispatcharr API key from Authorization or X-API-Key header"""
    if not _ENABLE_AUTH:
        return

    # Check X-API-Key header first
    api_key = request.headers.get("x-api-key")

    # Fall back to Authorization: ApiKey <key>
    if not api_key:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("apikey "):
            api_key = auth_header[7:].strip()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Validate against Dispatcharr User model
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(api_key=api_key, is_active=True)
        request.state.auth_user = user
    except User.DoesNotExist:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )


def create_app(tree: VirtualTree) -> FastAPI:
    """Create FastAPI application with HTTP filesystem handlers"""
    app = FastAPI(title="VOD HTTP Filesystem")
    httpfs = HTTPFilesystem(tree)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    async def handle_request(
        path: str,
        request: Request,
        _network=Depends(check_network_access),
        _auth=Depends(check_api_key_auth),
    ):
        """Handle all filesystem requests"""
        if not path.startswith("/"):
            path = "/" + path
        return await httpfs.handle_request(path, request)

    @app.get("/")
    async def root(
        request: Request,
        _network=Depends(check_network_access),
        _auth=Depends(check_api_key_auth),
    ):
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

    logger.info("Uvicorn starting on 0.0.0.0:%d (auth: %s)", port, "enabled" if _ENABLE_AUTH else "disabled")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        access_log=True
    )
