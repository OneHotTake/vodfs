"""FastAPI HTTP server for VOD filesystem - live DB queries"""

import asyncio
import logging
import os
import uvicorn
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, JSONResponse

try:
    from .tree import VirtualTree
    from .httpfs import HTTPFilesystem, shutdown_executor, _directory_cache
    from .integration import DispatcharrIntegrator
except (ImportError, AttributeError):
    from tree import VirtualTree
    from httpfs import HTTPFilesystem, shutdown_executor, _directory_cache
    from integration import DispatcharrIntegrator

logger = logging.getLogger(__name__)

_ENABLE_AUTH = os.environ.get("VODFS_ENABLE_AUTH", "false").lower() == "true"
# Bind host. Defaults to 0.0.0.0: the server runs inside the Dispatcharr
# container and must be reachable through Docker's published port by rclone/Plex,
# which a 127.0.0.1-only listener prevents. Lock down with VODFS_BIND_HOST and/or
# enable_auth + Dispatcharr's STREAMS network policy when exposing it.
_BIND_HOST = os.environ.get("VODFS_BIND_HOST", "0.0.0.0")

_server_ready = False
_startup_errors: List[str] = []


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


def _check_django_available():
    """Check Django availability at startup"""
    global _server_ready, _startup_errors

    integrator = DispatcharrIntegrator()
    if integrator.is_available():
        logger.info("Django available - all queries will be live against DB")
    else:
        msg = "Django/VOD models not available - listings will be empty"
        logger.warning(msg)
        _startup_errors.append(msg)

    _server_ready = True


def _build_rclone_config(base_url: str) -> str:
    """Build copy/paste-ready rclone config and mount notes."""
    base_url = base_url.rstrip("/") + "/"
    if _ENABLE_AUTH:
        auth_note = "# Secured installs: replace <your-dispatcharr-api-key> with an active Dispatcharr API key."
        auth_line = "headers = Authorization, ApiKey <your-dispatcharr-api-key>"
    else:
        auth_note = "# Secured installs: enable plugin auth, then uncomment the headers line and replace the placeholder."
        auth_line = "# headers = Authorization, ApiKey <your-dispatcharr-api-key>"

    return f"""# VODFS rclone remote
# Paste the [vodfs] block into your rclone.conf file.
# Suggested mount point: /mnt/vodfs
# Mount command (use --vfs-cache-mode full for Plex — see note below):
#   mkdir -p /mnt/vodfs /var/cache/vodfs
#   rclone mount vodfs: /mnt/vodfs --allow-other --read-only \\
#     --vfs-cache-mode full --cache-dir /var/cache/vodfs \\
#     --vfs-cache-max-size 100G --vfs-cache-max-age 24h \\
#     --vfs-read-ahead 256M --buffer-size 64M \\
#     --dir-cache-time 1h --poll-interval 0
#
# WHY --vfs-cache-mode full (NOT off): Plex transcodes/remuxes and seeks (resume,
# scrub, replay). With cache off, every seek re-opens the stream from a new offset,
# re-fetching from the provider — which thrashes and, on a provider with a low
# max_streams, fails outright ("No available stream"). cache=full serves seeks/
# replays from local disk; the provider is read once. (cache=off is fine only for a
# single sequential watch.)
# Plex library paths (prefer per-category dirs on large libraries; /All can be huge):
#   Movies: /mnt/vodfs/Movies/<Category>   (or /mnt/vodfs/Movies/All)
#   Series: /mnt/vodfs/Series/<Category>   (or /mnt/vodfs/Series/All)
#
# AVOID HAMMERING YOUR PROVIDER (important at scale):
#   - vodfs serves duration-based ESTIMATE sizes by default (no provider probe), so
#     rclone's per-file HEAD during a scan is cheap and NEVER touches your provider —
#     it only queries Dispatcharr. Keep 'no_head = false' (the default): with
#     no_head = true rclone can't read our listing sizes and every file shows an
#     unknown size, which breaks Plex. The provider is only contacted on real
#     playback (the proxy reports the true size then).
#   - In Plex, DISABLE deep analysis during scan: Settings > Library >
#     uncheck "Analyze audio tracks"/"Perform extensive media analysis", and prefer
#     "Scan my library automatically" off / scheduled. Plex opening every file for
#     analysis is what actually slams the provider.
#   - In Dispatcharr, set a per-provider MAX CONNECTIONS on each M3U account so
#     playback can't open more upstream streams than your provider allows. vodfs only
#     issues 302 redirects (it is never in the data path), so this cap is the right
#     place to throttle.
{auth_note}

[vodfs]
type = http
url = {base_url}
no_head = false
{auth_line}
"""


def _query_stats_sync() -> dict:
    """Synchronous ORM portion of /stats. Returns counts only."""
    try:
        from apps.vod.models import M3UMovieRelation, M3USeriesRelation
        from django.db.models import Count
    except ImportError:
        return {"available": False}

    try:
        from .tree import _enabled, _MOVIE_SIZED, _SERIES_HAS_SIZED_EP
    except ImportError:
        from tree import _enabled, _MOVIE_SIZED, _SERIES_HAS_SIZED_EP
    enabled = _enabled()
    # Same predicate but for *inactive* accounts: content that would be listed if
    # the provider were re-activated. Surfacing it explains a sudden drop in counts.
    orphaned = dict(enabled, **{"m3u_account__is_active": False})

    def per_category(model):
        rows = (
            model.objects.filter(**enabled)
            .values("category__name")
            .annotate(n=Count("id", distinct=True))
            .order_by("-n")
        )
        return {r["category__name"]: r["n"] for r in rows if r["category__name"]}

    def total(model):
        return model.objects.filter(**enabled).distinct().count()

    def orphaned_total(model):
        return model.objects.filter(**orphaned).distinct().count()

    # "sized" = how many are actually visible under the size gate (have a known
    # size). The gap to total is the movie backfill's remaining work.
    movies_sized = M3UMovieRelation.objects.filter(**enabled, **_MOVIE_SIZED).distinct().count()
    series_sized = M3USeriesRelation.objects.filter(**enabled, **_SERIES_HAS_SIZED_EP).distinct().count()

    return {
        "available": True,
        "movies": {
            "total": total(M3UMovieRelation),
            "sized": movies_sized,
            "by_category": per_category(M3UMovieRelation),
        },
        "series": {
            "total": total(M3USeriesRelation),
            "sized": series_sized,
            "by_category": per_category(M3USeriesRelation),
        },
        "orphaned": {
            "movies": orphaned_total(M3UMovieRelation),
            "series": orphaned_total(M3USeriesRelation),
        },
    }


async def _collect_stats() -> dict:
    """Run stats query off the event loop and merge in cache info."""
    loop = asyncio.get_event_loop()
    library = await loop.run_in_executor(None, _query_stats_sync)
    return {
        "library": library,
        "cache": _directory_cache.stats(),
        "auth_enabled": _ENABLE_AUTH,
    }


def create_app(tree: VirtualTree) -> FastAPI:
    """Create FastAPI application with HTTP filesystem handlers"""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _check_django_available()
        try:
            yield
        finally:
            shutdown_executor()
            logger.info("Shutdown complete")

    app = FastAPI(title="VOD HTTP Filesystem", lifespan=lifespan)
    httpfs = HTTPFilesystem(tree)

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

    @app.get("/rclone_conf")
    async def rclone_conf(
        request: Request,
        _network=Depends(check_network_access),
        _auth=Depends(check_api_key_auth),
    ):
        """Return copy/paste-ready rclone configuration."""
        return Response(
            content=_build_rclone_config(str(request.base_url)),
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/stats")
    async def stats(
        _network=Depends(check_network_access),
        _auth=Depends(check_api_key_auth),
    ):
        """Return library visibility counts.

        Answers the operator question: 'is the plugin actually seeing
        my library?' Counts only — no titles, URLs, or credentials.
        Uses the same enabled-category/same-account predicate the
        directory listings use, so the numbers reflect what rclone
        and Plex will see.
        """
        return JSONResponse(content=await _collect_stats())

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
        return await httpfs.handle_request("/", request)

    return app


def run_server(port: int, log_level: str = "info"):
    """Run the FastAPI server using uvicorn"""
    app = create_app(VirtualTree())

    logger.info("Uvicorn starting on %s:%d (auth: %s)", _BIND_HOST, port,
                "enabled" if _ENABLE_AUTH else "disabled")
    uvicorn.run(
        app,
        host=_BIND_HOST,
        port=port,
        log_level=log_level,
        access_log=True
    )
