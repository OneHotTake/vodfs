#!/bin/bash
# Start Dispatcharr for integration testing
# Uses Docker Compose with AIO image (includes PostgreSQL + Redis)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VODFS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DISPATCHARR_DIR="/home/onehottake/Projects/Dispatcharr"
COMPOSE_FILE="$VODFS_DIR/scripts/integration-compose.yml"

echo "=== Starting Dispatcharr for Integration Testing ==="

# Load secrets
if [ -f "$VODFS_DIR/.env.secrets" ]; then
    set -a
    source "$VODFS_DIR/.env.secrets"
    set +a
    echo "✓ Loaded .env.secrets"
else
    echo "✗ .env.secrets not found!"
    exit 1
fi

# Check if already running
if docker compose -f "$COMPOSE_FILE" ps 2>/dev/null | grep -q "Up"; then
    echo "✓ Dispatcharr is already running"
    echo "  Web UI: http://localhost:9191"
    exit 0
fi

# Start services
echo "Starting Docker Compose services..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for Dispatcharr to be ready
echo "Waiting for Dispatcharr to be ready..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:9191/ | grep -q "200\|301\|302"; then
        echo "✓ Dispatcharr is ready after ${WAITED}s"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo "  Waiting... (${WAITED}s)"
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "✗ Dispatcharr failed to start within ${MAX_WAIT}s"
    docker compose -f "$COMPOSE_FILE" logs --tail=50
    exit 1
fi

echo ""
echo "=== Dispatcharr Started ==="
echo "Web UI:    http://localhost:9191"
echo "Plugins:   http://localhost:9191/settings/plugins"
echo ""
echo "Next steps:"
echo "  1. Create admin user: $VODFS_DIR/scripts/setup-dispatcharr.sh"
echo "  2. Add M3U accounts:  $VODFS_DIR/scripts/setup-m3u-accounts.sh"