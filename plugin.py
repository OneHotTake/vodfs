"""
Dispatcharr VOD HTTP Filesystem Plugin

Exposes VOD library as mountable HTTP filesystem for rclone/Plex.
Supports category browsing, multi-provider streaming, and episode hydration.
"""

import os
import sys
import signal
import subprocess
import logging
from typing import Dict, Any
from pathlib import Path

# Plugin metadata
name = "VOD HTTP Filesystem"
version = "0.1.0"
description = "Expose VOD library to Plex as mountable HTTP filesystem"
author = "onehottake"

# Settings schema
fields = [
    {
        "id": "enabled",
        "label": "Enabled",
        "type": "boolean",
        "default": False
    },
    {
        "id": "http_port",
        "label": "HTTP Port",
        "type": "number",
        "default": 8888,
        "min": 1024,
        "max": 65535,
        "help_text": "Port for the HTTP filesystem server"
    },
    {
        "id": "auto_hydrate_empty_series",
        "label": "Auto-hydrate Empty Series",
        "type": "boolean",
        "default": True,
        "help_text": "Automatically fetch episodes when browsing Series directories"
    },
    {
        "id": "dispatcharr_base_url",
        "label": "Dispatcharr Base URL",
        "type": "string",
        "default": "http://127.0.0.1:9191",
        "help_text": "Base URL of Dispatcharr instance (must be reachable from rclone/Plex)"
    }
]

# Available actions
actions = [
    {
        "id": "enable",
        "label": "Enable HTTP Filesystem",
        "description": "Start the HTTP filesystem server",
        "button_label": "🚀 Enable",
        "button_variant": "filled",
        "button_color": "green"
    },
    {
        "id": "disable",
        "label": "Disable HTTP Filesystem",
        "description": "Stop the HTTP filesystem server",
        "button_label": "🛑 Disable",
        "button_variant": "outline",
        "button_color": "red",
        "confirm": {
            "message": "Are you sure you want to stop the HTTP filesystem server?"
        }
    },
    {
        "id": "show_rclone_config",
        "label": "Show rclone Configuration",
        "description": "Display the rclone configuration for mounting this filesystem",
        "button_label": "📋 rclone Config",
        "button_variant": "outline",
        "button_color": "cyan"
    }
]


class Plugin:
    """VOD HTTP Filesystem Plugin - Main entry point"""

    def __init__(self):
        self._child_process = None
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
        auto_hydrate = settings.get("auto_hydrate_empty_series", True)
        dispatcharr_base_url = settings.get("dispatcharr_base_url", "http://127.0.0.1:9191")

        logger.info("Starting HTTP filesystem server on port %d", port)

        # Start child process with Django-initialized server
        # Use direct file path since plugin module is loaded under a different name
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        # standalone_runner.py is in the plugin/ subdirectory
        plugin_subdir = os.path.join(plugin_dir, "plugin")
        runner_path = os.path.join(plugin_subdir, "standalone_runner.py")

        # Use the Dispatcharr Python environment which has all dependencies
        python_exe = sys.executable  # This is the Dispatcharr Python

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
            self._child_process = process

            logger.info("Server started on PID %d, binding to 127.0.0.1:%d", process.pid, port)

            return {
                "status": "ok",
                "message": "HTTP filesystem server enabled",
                "pid": process.pid,
                "port": port,
                "auto_hydrate": auto_hydrate
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

        config = f"""[vodfs]
type = http
url = http://127.0.0.1:{port}/
"""

        return {
            "status": "ok",
            "config": config,
            "message": "Add this to your rclone config file"
        }

    def stop(self, context: Dict[str, Any]):
        """Called when plugin is disabled/deleted/reloaded"""
        logger = context.get("logger", logging.getLogger(__name__))

        pid = self._read_pid()
        if pid and self._is_running(pid):
            logger.info("Plugin stop() - terminating server (PID %d)", pid)
            self._stop_process(pid, logger)
            self._remove_pid_file()