#!/bin/bash
# Reset Dispatcharr integration test instance (stop + remove data)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VODFS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$VODFS_DIR/scripts/integration-compose.yml"

echo "=== Resetting Dispatcharr ==="
docker compose -f "$COMPOSE_FILE" down -v
echo "✓ All data removed"
echo ""
echo "Run start-dispatcharr.sh to start fresh"