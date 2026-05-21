# Development Guide

## Setting Up Development Environment

### Prerequisites

- Python 3.10+
- Dispatcharr source code (for model imports during testing)
- Virtual environment (recommended)

### Clone the Repository

```bash
git clone https://github.com/OneHotTake/dispatcharr-vodfs.git
cd dispatcharr-vodfs
```

### Install Dependencies

```bash
pip install fastapi uvicorn jinja2 httpx celery pytest pytest-asyncio
```

### Development Workflow

1. Edit code in `plugin/` directory
2. Test with Dispatcharr running
3. Install plugin into `/data/plugins/vodfs/`
4. Enable plugin in Dispatcharr UI
5. Verify functionality

### Testing with Dispatcharr

**Install Plugin**:
```bash
cp -r . /data/plugins/vodfs/
```

**Start Dispatcharr**:
```bash
# From Dispatcharr source directory
python manage.py runserver
```

**Access Plugin UI**:
- Navigate to Settings → Plugins → VOD HTTP Filesystem

**Test HTTP Server**:
```bash
curl http://127.0.0.1:8888/
curl http://127.0.0.1:8888/Movies/
curl http://127.0.0.1:8888/Movies/All/
```

**Test rclone Mount**:
```bash
# Add to rclone.conf
[vodfs]
type = http
url = http://127.0.0.1:8888/

# Mount
rclone mount vodfs: /tmp/vodfs --vfs-cache-mode full
```

## Project Structure

```
vodfs/
├── plugin.json              # Plugin manifest
├── plugin.py                # Main Plugin class
├── plugin/
│   ├── __init__.py          # Package init
│   ├── tree.py              # Virtual filesystem tree
│   ├── httpfs.py            # HTTP request handlers
│   └── integration.py       # Dispatcharr integration
├── architecture/            # Design docs
│   ├── OVERVIEW.md
│   ├── HTTPFS.md
│   └── HYDRATION.md
├── docs/                    # User docs
├── tests/                   # Test files
├── scripts/                 # Helper scripts
├── CLAUDE.md                # AI steering rules
├── BACKLOG.md               # Task backlog
├── REPO_MAP.md              # Repository map
├── TOKEN_BUDGET.md          # Token budget
├── TODO.md                  # Open items
├── README.md                # Main documentation
└── LICENSE                  # MIT license
```

## Coding Standards

### Python Style

- Follow PEP 8
- Use type hints where appropriate
- Docstrings for all public functions/classes
- Max line length: 100 characters

### Error Handling

```python
try:
    # Operation
    pass
except SpecificException as e:
    logger.exception("Operation failed: %s", e)
    return {"status": "error", "message": str(e)}
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Information message")
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Exception with traceback")
```

### Django Model Access

```python
# Always handle ImportError for development
try:
    from apps.vod.models import Movie
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    Movie = None

# Check availability before use
if not DJANGO_AVAILABLE:
    logger.warning("Django models not available")
    return []
```

## Testing

### Unit Tests

```bash
# Run tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_tree.py

# Run with coverage
python -m pytest tests/ --cov=plugin --cov-report=html
```

### Integration Tests

Integration tests require a running Dispatcharr instance with sample data.

```bash
# Start Dispatcharr
python manage.py runserver

# Run integration tests
python -m pytest tests/test_integration.py --live
```

### Manual Testing

1. **Plugin Enable/Disable**:
   - Enable plugin
   - Verify server starts
   - Check PID file created
   - Disable plugin
   - Verify server stops
   - Check PID file removed

2. **HTTP Server**:
   - Browse root: `curl http://127.0.0.1:8888/`
   - Browse Movies: `curl http://127.0.0.1:8888/Movies/`
   - Browse All: `curl http://127.0.0.1:8888/Movies/All/`
   - Browse Category: `curl http://127.0.0.1:8888/Movies/Action/`

3. **File Access**:
   - HEAD request: `curl -I http://127.0.0.1:8888/Movies/All/Inception.mkv`
   - GET request: `curl -I http://127.0.0.1:8888/Movies/All/Inception.mkv`
   - Verify 302 redirect

4. **rclone Mount**:
   - Mount filesystem
   - Browse with `ls`
   - Verify directory structure
   - Unmount cleanly

5. **Plex Scan**:
   - Add library to Plex
   - Scan library
   - Verify content discovered
   - Play a movie

## Debugging

### Dispatcharr Logs

```bash
# View Dispatcharr logs
tail -f /path/to/dispatcharr/logs/dispatcharr.log
```

### Plugin Logs

Plugin logs appear in Dispatcharr logs with prefix `[vodfs]`.

### Child Process Logs

Child process logs (when implemented) will be in:
```
/data/plugins/vodfs/server.log
```

### Common Issues

**Server won't start**:
- Check port availability: `netstat -tlnp | grep 8888`
- Check Dispatcharr logs
- Verify `/data/plugins/vodfs/` is writable

**Import errors**:
- Verify Django models are available
- Check Dispatcharr version compatibility
- Restart Dispatcharr after plugin changes

**Empty directories**:
- Verify VOD content exists in Dispatcharr
- Check M3U account is active
- Verify categories are populated

**No streaming**:
- Check Dispatcharr proxy is running
- Verify stream URLs are valid
- Check M3U account credentials

## Architecture Overview

### Components

- **plugin.py** - Main entry point, manages child HTTP server process
- **server.py** - FastAPI HTTP server binding to 127.0.0.1
- **httpfs.py** - HTTP request handlers (GET, HEAD, 302 redirects)
- **tree.py** - Virtual filesystem tree with O(1) child lookup
- **dispatcharr.py** - Dispatcharr API client (movies, series, episodes)
- **celery_worker.py** - Background hydration tasks

### Data Flow

1. Plugin `run()` starts FastAPI server as subprocess
2. Server binds to 127.0.0.1:port
3. rclone mounts HTTP endpoint
4. Plex scans mounted filesystem
5. Directory requests return HTML listing
6. File requests return 302 redirect to Dispatcharr proxy
7. Series browsing triggers episode hydration

### Sprint History

| Sprint | Title | Status |
|--------|-------|--------|
| 101 | GitHub Repository Setup | ✓ |
| 102 | Basic HTTP Server | ✓ |
| 103 | Virtual Filesystem Tree | ✓ |
| 104 | Dispatcharr Integration | ✓ |
| 105 | HTTP 302 Redirects | ✓ |
| 106 | Celery Background Tasks | ✓ |
| 107 | Series Episode Hydration | ✓ |
| 108 | Plex Integration Testing | Pending |
| 109 | Multi-Stream File Handling | ✓ |
| 110 | Large Library Performance | ✓ |
| 111 | Error Handling and Logging | ✓ |
| 112 | Documentation Polish | ✓ |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Update documentation
6. Submit a pull request

See `CONTRIBUTING.md` for detailed guidelines.

## Release Process

1. Update `plugin.json` version
2. Update `CHANGELOG.md`
3. Run full test suite
4. Commit changes
5. Tag release: `git tag v1.0.0`
6. Push tag: `git push origin v1.0.0`
7. Create GitHub release
8. Submit to Dispatcharr plugin repository

## Questions?

- GitHub Issues: https://github.com/OneHotTake/dispatcharr-vodfs/issues
- Discord: https://discord.gg/dispatcharr