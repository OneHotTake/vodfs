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
        elif action == "run_hydration_now":
            return self._run_hydration_now(settings)
        elif action == "check_status":
            return self._check_status(settings)
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    def _child(self, settings, path, method="GET", timeout=15):
        """Call the child server's own HTTP API (it runs the hydrator + stats)."""
        import json as _json
        import urllib.request
        port = settings.get("http_port", 8888)
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _json.loads(r.read().decode() or "{}")

    def _run_hydration_now(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        if not self._is_running(self._read_pid()):
            return {"status": "error", "message": "Server not running — click 🚀 Enable first."}
        try:
            d = self._child(settings, "/hydrate/run", method="POST")
        except Exception as e:
            return {"status": "error", "message": f"Could not reach server: {e}"}
        st = d.get("status", {})
        if not d.get("triggered"):
            return {"status": "ok", "message": "Hydration is disabled — set 'Hydration Rate' above 0 and re-enable."}
        return {"status": "ok", "message":
                f"Hydration pass started at {st.get('rate_per_sec')}/sec. Titles appear as sizes land — "
                f"watch progress at /vodfs/stats or click 🩺 Status."}

    def _check_status(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        if not self._is_running(self._read_pid()):
            return {"status": "ok", "message": "Server is STOPPED. Click 🚀 Enable to start."}
        try:
            stats = self._child(settings, "/stats")
            hy = self._child(settings, "/hydrate/status")
        except Exception as e:
            return {"status": "error", "message": f"Server running but not responding: {e}"}
        lib = stats.get("library", {})
        mv, sv = lib.get("movies", {}), lib.get("series", {})
        lines = [
            "✅ Server running.",
            f"Movies visible: {mv.get('sized', '?')} / {mv.get('total', '?')}  "
            f"(Series: {sv.get('sized', '?')} / {sv.get('total', '?')})",
        ]
        if hy.get("enabled"):
            nxt = hy.get("next_run") or "manual only"
            run = "running now" if hy.get("running") else f"next run {nxt}"
            lines.append(f"Hydration: {hy.get('rate_per_sec')}/sec, {run}.")
            if hy.get("last_pass"):
                lp = hy["last_pass"]
                lines.append(f"Last pass ({lp.get('reason')}): {lp.get('movies')} movies, {lp.get('series')} series.")
        else:
            lines.append("Hydration: disabled (rate=0).")
        gap = (mv.get('total', 0) or 0) - (mv.get('sized', 0) or 0)
        if gap > 0:
            lines.append(f"Next step: {gap} movies still need sizes — click 💧 Hydrate Now.")
        else:
            lines.append("Next step: point Plex at /mnt/vodfs/Movies/<Category>.")
        return {"status": "ok", "message": "\n".join(lines)}

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

    @staticmethod
    def _validate_base_url(url: str) -> str | None:
        """Return an error string if the Dispatcharr base URL is unusable, else None.

        Note this is reachability-agnostic: 127.0.0.1 is a valid default for
        same-host setups. We only catch values that can never produce a working
        redirect (empty, no scheme, non-HTTP scheme, or no host).
        """
        from urllib.parse import urlparse
        value = (url or "").strip()
        if not value:
            return "Dispatcharr base URL is empty — set it in the plugin settings."
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            return ("Dispatcharr base URL must start with http:// or https:// "
                    f"(got {value!r}).")
        if not parsed.netloc:
            return f"Dispatcharr base URL has no host (got {value!r})."
        return None

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

        # Reject an obviously-broken base URL up front. Every playback request 302s
        # to this address, so starting with a malformed value just yields dead
        # redirects that surface much later as unplayable files in Plex/rclone.
        url_error = self._validate_base_url(dispatcharr_base_url)
        if url_error:
            logger.error("Refusing to start: %s", url_error)
            return {"status": "error", "message": url_error}

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

        # Pass hydration (size-backfill scheduler) settings to the child
        env["VODFS_HYDRATE_RATE"] = str(settings.get("hydrate_rate", 2))
        env["VODFS_HYDRATE_ON_LOAD"] = str(settings.get("hydrate_on_load", True)).lower()
        env["VODFS_HYDRATE_TIMES"] = str(settings.get("scheduled_times", "0300") or "")
        env["VODFS_HYDRATE_TZ"] = str(settings.get("timezone", "America/Chicago") or "America/Chicago")

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
        """Point the user at the persistent, copy/paste rclone-config page.

        We don't embed the config in this (toast-style) message — it would flash and,
        worse, we can't know the externally-reachable host from in here. Instead the
        page at /vodfs/rclone_conf builds the correct remote URL from your own browser
        request (reverse-proxy aware), so whatever host you opened Dispatcharr on is
        what rclone gets. Relative path = no IP to get wrong."""
        if not self._is_running(self._read_pid()):
            return {"status": "error",
                    "message": "Server not running — click 🚀 Enable first, then this button."}
        auth_note = (" Use any active Dispatcharr API key in the headers line."
                     if settings.get("enable_auth", False) else "")
        return {
            "status": "ok",
            "message": ("Open  /vodfs/rclone_conf  on this host (just append it to your "
                        "Dispatcharr URL) for the copy/paste rclone config — the remote URL "
                        "is filled in correctly from your browser." + auth_note),
        }

    def stop(self, context: Dict[str, Any]):
        """Called when plugin is disabled/deleted/reloaded"""
        logger = context.get("logger", logging.getLogger(__name__))

        pid = self._read_pid()
        if pid and self._is_running(pid):
            logger.info("Plugin stop() - terminating server (PID %d)", pid)
            self._stop_process(pid, logger)
            self._remove_pid_file()
