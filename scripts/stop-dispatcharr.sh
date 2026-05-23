#!/bin/bash
# Stop Dispatcharr integration test instance

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VODFS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$VODFS_DIR/scripts/integration-compose.yml"

echo "=== Stopping Dispatcharr ==="
docker compose -f "$COMPOSE_FILE" stop
echo "✓ Dispatcharr stopped"