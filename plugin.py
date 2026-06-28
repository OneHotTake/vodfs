"""
Dispatcharr VOD HTTP Filesystem Plugin

Exposes VOD library as mountable HTTP filesystem for rclone/Plex.
Supports category browsing, multi-provider streaming, and episode hydration.
"""

import os
import json
import signal
import subprocess
import logging
from typing import Dict, Any
from pathlib import Path

with open(Path(__file__).parent / "plugin.json") as f:
    _manifest = json.load(f)

name = _manifest["name"]
version = _manifest["version"]
description = _manifest["description"]
author = _manifest["author"]
fields = _manifest["fields"]
actions = _manifest["actions"]


class Plugin:
    """VOD HTTP Filesystem Plugin - Main entry point"""

    def __init__(self):
        self._pid_file = "/data/plugins/vodfs/server.pid"
        self._data_dir = "/data/plugins/vodfs"
        os.makedirs(self._data_dir, exist_ok=True)

    def _read_pid(self) -> int | None:
        """Read PID from file"""
        try:
            with open(self._pid_file, "r") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError, IOError):
            return None

    def _save_pid(self, pid: int):
        """Save PID to file"""
        with open(self._pid_file, "w") as f:
            f.write(str(pid))

    def _remove_pid_file(self):
        """Remove PID file"""
        try:
            os.remove(self._pid_file)
        except FileNotFoundError:
            pass

    def _is_running(self, pid: int | None = None) -> bool:
        """Check if process is running"""
        if pid is None:
            pid = self._read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
            return True
        except ProcessLookupError:
            return False

    def _stop_process(self, pid: int, logger: logging.Logger):
        """Stop a process gracefully"""
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to process %d", pid)
        except ProcessLookupError:
            logger.warning("Process %d not found", pid)
        except Exception as e:
            logger.exception("Failed to stop process %d: %s", pid, e)

    def run(self, action: str, params: Dict[str, Any], context: Dict[str, Any]):
        """Handle plugin actions"""
        logger = context.get("logger", logging.getLogger(__name__))
        settings = context.get("settings", {})

        if action == "enable":
            return self._enable(logger, settings)
        elif action == "disable":
            return self._disable(logger)
        elif action == "show_rclone_config":
            return self._show_rclone_config(settings)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    _DEPENDENCIES = ("uvicorn", "fastapi", "jinja2")

    def _ensure_dependencies(self, python_exe: str, logger: logging.Logger) -> None:
        """Best-effort install of the web-server dependencies into Dispatcharr's venv."""
        check = "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in %r) else 1)" % (self._DEPENDENCIES,)
        try:
            if subprocess.call([python_exe, "-c", check]) == 0:
                return
            logger.info("Installing VODFS web dependencies: %s", ", ".join(self._DEPENDENCIES))
            subprocess.call([python_exe, "-m", "ensurepip", "--upgrade"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            rc = subprocess.call([python_exe, "-m", "pip", "install", "-q", *self._DEPENDENCIES])
            if rc != 0:
                logger.warning("Dependency install returned %d; server may fail to start. "
                               "Install manually: %s -m pip install %s",
                               rc, python_exe, " ".join(self._DEPENDENCIES))
        except Exception as e:
            logger.warning("Could not verify/install dependencies (%s); continuing", e)

    def _enable(self, logger: logging.Logger, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Enable the plugin and start child process"""
        # Check if already running
        pid = self._read_pid()
        if pid and self._is_running(pid):
            return {
                "status": "ok",
                "message": f"Server already running on PID {pid}",
                "pid": pid
            }

        # Get settings
        port = settings.get("http_port", 8888)
        dispatcharr_base_url = settings.get("dispatcharr_base_url", "http://127.0.0.1:9191")
        enable_auth = settings.get("enable_auth", False)

        logger.info("Starting HTTP filesystem server on port %d (auth: %s)", port, "enabled" if enable_auth else "disabled")

        # Start child process with Django-initialized server
        # Use direct file path since plugin module is loaded under a different name
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        # standalone_runner.py is in the plugin/ subdirectory
        plugin_subdir = os.path.join(plugin_dir, "plugin")
        runner_path = os.path.join(plugin_subdir, "standalone_runner.py")

        # Use the Dispatcharr Python environment (sys.executable is uwsgi in the container).
        python_exe = "/dispatcharrpy/bin/python"

        # The web server needs uvicorn/fastapi/jinja2, which are not part of
        # Dispatcharr's base environment. Install them on first enable.
        self._ensure_dependencies(python_exe, logger)

        cmd = [
            python_exe, runner_path,
            "--port", str(port)
        ]

        # Pass Django settings to child
        env = os.environ.copy()
        if "DJANGO_SETTINGS_MODULE" not in env:
            env["DJANGO_SETTINGS_MODULE"] = "dispatcharr.settings"

        # Add Dispatcharr app directory to PYTHONPATH
        app_dir = "/app"
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = app_dir
        else:
            env["PYTHONPATH"] = f"{app_dir}:{env['PYTHONPATH']}"

        # Pass Dispatcharr base URL to child process
        env["VODFS_DISPATCHARR_BASE_URL"] = dispatcharr_base_url.rstrip("/")

        # Pass auth enable flag to child process
        env["VODFS_ENABLE_AUTH"] = str(enable_auth).lower()

        try:
            # Redirect child output to log file for debugging
            log_file = os.path.join(plugin_subdir, "server.log")
            with open(log_file, "a") as log:
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log,
                    stderr=log,
                    start_new_session=True  # Detach from parent process
                )

            # Save PID for graceful shutdown
            self._save_pid(process.pid)

            logger.info("Server started on PID %d, listening on 0.0.0.0:%d "
                        "(reachable via the container's published port)", process.pid, port)

            return {
                "status": "ok",
                "message": "HTTP filesystem server enabled",
                "pid": process.pid,
                "port": port
            }
        except Exception as e:
            logger.exception("Failed to start server: %s", e)
            return {
                "status": "error",
                "message": f"Failed to start server: {str(e)}"
            }

    def _disable(self, logger: logging.Logger) -> Dict[str, Any]:
        """Disable the plugin and stop child process"""
        pid = self._read_pid()

        if not pid:
            return {
                "status": "ok",
                "message": "Server not running"
            }

        if not self._is_running(pid):
            self._remove_pid_file()
            return {
                "status": "ok",
                "message": f"Server was not running (stale PID {pid})"
            }

        logger.info("Stopping HTTP filesystem server (PID %d)", pid)

        self._stop_process(pid, logger)
        self._remove_pid_file()

        return {
            "status": "ok",
            "message": f"Server stopped (PID {pid})"
        }

    def _show_rclone_config(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rclone configuration"""
        port = settings.get("http_port", 8888)
        enable_auth = settings.get("enable_auth", False)
        config_url = f"http://127.0.0.1:{port}/rclone_conf"

        if enable_auth:
            config = f"""# VODFS rclone remote
# Paste this block into your rclone.conf file.
# Suggested mount point: /mnt/vodfs
# Mount command:
#   mkdir -p /mnt/vodfs
#   rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
# Plex library paths:
#   Movies: /mnt/vodfs/Movies/All
#   Series: /mnt/vodfs/Series/All
# Secured installs: replace <your-dispatcharr-api-key> with an active Dispatcharr API key.

[vodfs]
type = http
url = http://127.0.0.1:{port}/
headers = Authorization, ApiKey <your-dispatcharr-api-key>
"""
            message = f"Open {config_url} for a copy/paste rclone config. Use any active Dispatcharr API key for authentication."
        else:
            config = f"""# VODFS rclone remote
# Paste this block into your rclone.conf file.
# Suggested mount point: /mnt/vodfs
# Mount command:
#   mkdir -p /mnt/vodfs
#   rclone mount vodfs: /mnt/vodfs --allow-other --vfs-cache-mode off --dir-cache-time 5s --poll-interval 0
# Plex library paths:
#   Movies: /mnt/vodfs/Movies/All
#   Series: /mnt/vodfs/Series/All
# Secured installs: enable plugin auth, then uncomment the headers line and replace the placeholder.

[vodfs]
type = http
url = http://127.0.0.1:{port}/
# headers = Authorization, ApiKey <your-dispatcharr-api-key>
"""
            message = f"Open {config_url} for a copy/paste rclone config."

        return {
            "status": "ok",
            "url": config_url,
            "config": config,
            "message": message
        }

    def stop(self, context: Dict[str, Any]):
        """Called when plugin is disabled/deleted/reloaded"""
        logger = context.get("logger", logging.getLogger(__name__))

        pid = self._read_pid()
        if pid and self._is_running(pid):
            logger.info("Plugin stop() - terminating server (PID %d)", pid)
            self._stop_process(pid, logger)
            self._remove_pid_file()
