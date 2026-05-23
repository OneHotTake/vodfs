#!/bin/bash
# Setup Dispatcharr: create admin user and add M3U accounts
# Uses Django management commands + Playwright for browser automation

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VODFS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load secrets
if [ -f "$VODFS_DIR/.env.secrets" ]; then
    set -a
    source "$VODFS_DIR/.env.secrets"
    set +a
else
    echo "✗ .env.secrets not found!"
    exit 1
fi

CONTAINER="vodfs_integration"

echo "=== Setting up Dispatcharr ==="

# Step 1: Create admin user via Django management command
echo "Creating admin user: $DISPATCHARR_ADMIN_USERNAME"
docker exec -u root "$CONTAINER" bash -c "
    cd /app && \
    python manage.py shell -c \"
from apps.accounts.models import User
if not User.objects.filter(username='$DISPATCHARR_ADMIN_USERNAME').exists():
    User.objects.create_superuser('$DISPATCHARR_ADMIN_USERNAME', password='$DISPATCHARR_ADMIN_PASSWORD')
    print('✓ Admin user created')
else:
    print('✓ Admin user already exists')
\""

# Step 2: Add M3U accounts via Playwright
echo ""
echo "Adding M3U accounts via browser automation..."
python3 "$SCRIPT_DIR/setup-m3u-accounts.py"

echo ""
echo "=== Setup Complete ==="
echo "Login: http://localhost:9191 ($DISPATCHARR_ADMIN_USERNAME / $DISPATCHARR_ADMIN_PASSWORD)"