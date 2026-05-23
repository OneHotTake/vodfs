# Helper scripts for development and testing

## start-dispatcharr.sh

Start Dispatcharr for testing with the vodfs plugin.

```bash
#!/bin/bash
# Start Dispatcharr for vodfs plugin testing

DISPATCHARR_DIR="/home/onehottake/Projects/Dispatcharr"
PLUGIN_DIR="/home/onehottake/Projects/Plugins/plugins/vodfs"

echo "Starting Dispatcharr..."

cd "$DISPATCHARR_DIR"

# Start in development mode
python manage.py runserver 0.0.0.0:8000

# Or use production mode:
# gunicorn dispatcharr.wsgi:application --bind 0.0.0.0:8000
```

## install-plugin.sh

Install the vodfs plugin into Dispatcharr.

```bash
#!/bin/bash
# Install vodfs plugin into Dispatcharr

PLUGIN_DIR="/home/onehottake/Projects/Plugins/plugins/vodfs"
TARGET_DIR="/data/plugins/vodfs"

echo "Installing vodfs plugin to $TARGET_DIR..."

# Create target directory
sudo mkdir -p "$TARGET_DIR"

# Copy plugin files
sudo cp -r "$PLUGIN_DIR"/* "$TARGET_DIR/"

# Set permissions
sudo chown -R dispatcharr:dispatcharr "$TARGET_DIR"

echo "Plugin installed. Restart Dispatcharr to load the plugin."
```

## test-http-server.sh

Test the HTTP filesystem server.

```bash
#!/bin/bash
# Test vodfs HTTP server

PORT=${1:-8888}

echo "Testing HTTP server on port $PORT..."

# Test root
echo "Testing root..."
curl -s http://127.0.0.1:$PORT/ | head -20

echo ""
echo "Testing Movies directory..."
curl -s http://127.0.0.1:$PORT/Movies/ | head -20

echo ""
echo "Testing Series directory..."
curl -s http://127.0.0.1:$PORT/Series/ | head -20
```

## test-rclone-mount.sh

Test rclone mount with vodfs.

```bash
#!/bin/bash
# Test rclone mount with vodfs

PORT=${1:-8888}
MOUNT_POINT=${2:-/tmp/vodfs}

echo "Mounting vodfs to $MOUNT_POINT..."

# Create mount point
mkdir -p "$MOUNT_POINT"

# Mount with rclone
rclone mount \
    --http-url http://127.0.0.1:$PORT/ \
    http: \
    "$MOUNT_POINT" \
    --vfs-cache-mode full \
    --daemon

echo "Mounted. Listing contents..."
ls -la "$MOUNT_POINT"

echo ""
echo "To unmount: fusermount -u $MOUNT_POINT"
```

## stop-dispatcharr.sh

Stop Dispatcharr.

```bash
#!/bin/bash
# Stop Dispatcharr

echo "Stopping Dispatcharr..."

# Find and kill Dispatcharr processes
pkill -f "manage.py runserver"
pkill -f "gunicorn dispatcharr"

echo "Dispatcharr stopped."
```

## Usage

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

Run scripts:
```bash
./scripts/start-dispatcharr.sh
./scripts/install-plugin.sh
./scripts/test-http-server.sh 8888
./scripts/test-rclone-mount.sh 8888 /tmp/vodfs
./scripts/stop-dispatcharr.sh
```