"""FastAPI HTTP server for VOD filesystem - live DB queries, no manifest caching"""

import logging
import os
import threading
import uvicorn
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, JSONResponse

try:
    from .tree import VirtualTree
    from .httpfs import HTTPFilesystem
    from .cache import LRUCache
    from .integration import DispatcharrIntegrator
except (ImportError, AttributeError):
    from tree import VirtualTree
    from httpfs import HTTPFilesystem
    from cache import LRUCache
    from integration import DispatcharrIntegrator

logger = logging.getLogger(__name__)

_ENABLE_AUTH = os.environ.get("VODFS_ENABLE_AUTH", "false").lower() == "true"


# Global state
_server_ready = False
_startup_errors: List[str] = []
_directory_cache = LRUCache(max_size=5000, ttl=600)


def check_network_access(request: Request):
    """Check if client IP is allowed per Dispatcharr STREAMS policy"""
    try:
        from dispatcharr.utils import network_access_allowed
        if not network_access_allowed(request, "STREAMS"):
            raise HTTPException(status_code=403, detail="Forbidden")
    except (ImportError, AttributeError):
        pass


def check_api_key_auth(request: Request):
    """Validate Dispatcharr API key from Authorization or X-API-Key header"""
    if not _ENABLE_AUTH:
        return

    api_key = request.headers.get("x-api-key")

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


def _initialize_on_startup_sync():
    """Mark server as ready (no manifest/hydration needed - live DB queries)"""
    global _server_ready, _startup_errors

    try:
        integrator = DispatcharrIntegrator()
        if integrator.is_available():
            logger.info("Django available - all queries will be live against DB")
        else:
            logger.warning("Django not available - queries will return empty results")

        _server_ready = True
        logger.info("Server ready")

    except Exception as e:
        logger.error("Failed to initialize: %s", e)
        _startup_errors.append(str(e))
        import traceback
        logger.error(traceback.format_exc())


def _initialize_on_startup():
    """Initialize on startup (runs in thread)"""
    thread = threading.Thread(target=_initialize_on_startup_sync, daemon=True)
    thread.start()


def create_app(tree: VirtualTree) -> FastAPI:
    """Create FastAPI application with HTTP filesystem handlers"""
    app = FastAPI(title="VOD HTTP Filesystem")
    httpfs = HTTPFilesystem(tree)

    @app.on_event("startup")
    async def startup_event():
        """Initialize on startup"""
        _initialize_on_startup()

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        logger.info("Shutdown complete")

    @app.get("/healthz")
    async def healthz():
        """Basic health check"""
        return Response(status_code=200, content="OK")

    @app.get("/readyz")
    async def readyz():
        """Readiness check"""
        if not _server_ready:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "errors": _startup_errors
                }
            )

        status = {
            "status": "ready",
            "architecture": "live-db-queries",
            "warnings": []
        }

        if _startup_errors:
            status['warnings'].extend(_startup_errors)

        return JSONResponse(content=status)

    @app.get("/status")
    async def status():
        """Detailed status"""
        return JSONResponse(content={
            "architecture": "live-db-queries",
            "system": {
                "auth_enabled": _ENABLE_AUTH,
                "ready": _server_ready,
                "startup_errors": _startup_errors
            }
        })

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


def run_server(port: int, log_level: str = "info"):
    """Run the FastAPI server using uvicorn"""
    tree = VirtualTree()
    tree.build()

    app = create_app(tree)

    logger.info("Uvicorn starting on 0.0.0.0:%d (auth: %s)", port, "enabled" if _ENABLE_AUTH else "disabled")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        access_log=True
    )
