"""Standalone HTTP server runner with Django initialization"""

import os
import sys
import logging

# Configure logging before Django setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)

logger = logging.getLogger(__name__)


def setup_django():
    """Initialize Django in the child process"""
    # Must be set before django.setup()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dispatcharr.settings")

    try:
        import django
        django.setup()
        logger.info("Django initialized successfully in child process")

        # Verify model access
        from apps.vod.models import Movie, Series
        logger.info("VOD models accessible: Movie, Series")
        return True
    except Exception as e:
        logger.error("Failed to initialize Django: %s", e)
        return False


def run_server(port: int = 8888):
    """Run the HTTP filesystem server with Django context"""
    if not setup_django():
        logger.error("Cannot start server without Django")
        sys.exit(1)

    # Now we can import our modules that depend on Django
    from plugin.tree import VirtualTree
    from plugin.server import create_app, run_server as _run_server

    logger.info("Starting HTTP filesystem server on port %d", port)
    _run_server(port)


def main():
    """Entry point for child process"""
    import argparse

    parser = argparse.ArgumentParser(description="VOD HTTP Filesystem Server")
    parser.add_argument("--port", type=int, default=8888, help="Port to listen on")
    args = parser.parse_args()

    run_server(args.port)


if __name__ == "__main__":
    main()