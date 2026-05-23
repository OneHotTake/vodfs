"""Aggressive episode hydration scheduler with backoff only on failure"""

import threading
import time
from datetime import datetime, timedelta
from collections import deque
import logging

try:
    from .integration import DispatcharrIntegrator
except ImportError:
    from integration import DispatcharrIntegrator

logger = logging.getLogger(__name__)


class HydrationScheduler:
    """
    Aggressive episode hydration with backoff only on failure.
    Queues everything immediately on startup.
    """

    def __init__(self, max_workers: int = 5):
        self.state = {}
        self.max_workers = max_workers
        self.active_count = 0
        self.recent_failures = deque(maxlen=20)
        self.lock = threading.Lock()
        self.running = False
        self.threads = []

    def start(self):
        if self.running:
            return

        integrator = DispatcharrIntegrator()
        if not integrator.is_available():
            logger.warning("Django not available, skipping hydration")
            return

        zero_episode = integrator.get_zero_episode_series()

        # Populate state BEFORE starting workers
        with self.lock:
            for series in zero_episode:
                uuid = series.get("series_uuid")
                if not uuid:
                    continue
                if uuid not in self.state:
                    self.state[uuid] = {
                        "series_uuid": uuid,
                        "status": "queued",
                        "failure_count": 0,
                        "last_error": None,
                        "next_retry": None,
                        "series_id": series.get("series_id"),
                        "series_name": series.get("series_name", "Unknown"),
                        "providers": series.get("providers", []),
                    }
            # Now mark as running and start workers
            self.running = True

        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"HydrationWorker-{i}")
            t.start()
            self.threads.append(t)

        logger.info("HydrationScheduler started - queued %d series with %d workers", len(zero_episode), self.max_workers)

    def _worker_loop(self):
        while self.running:
            try:
                task = self._get_next_to_hydrate()
                if not task:
                    time.sleep(2)
                    continue
                logger.debug("Worker got task: %s", task.get("series_uuid", "unknown"))
                self._hydrate(task)
            except Exception as e:
                import traceback
                logger.error("Hydration worker error: %s", e)
                logger.error("Traceback: %s", traceback.format_exc())
                time.sleep(5)

    def _get_next_to_hydrate(self):
        now = datetime.now()
        with self.lock:
            if self.active_count >= self.max_workers:
                return None
            for uuid, data in self.state.items():
                if data.get("status") == "queued":
                    data["status"] = "hydrating"
                    self.active_count += 1
                    return data
                if data.get("status") == "failed" and data.get("next_retry"):
                    if now >= data["next_retry"]:
                        data["status"] = "hydrating"
                        self.active_count += 1
                        return data
        return None

    def _hydrate(self, task_data: dict):
        series_uuid = task_data["series_uuid"]
        series_name = task_data["series_name"]
        series_id = task_data["series_id"]
        providers = task_data["providers"]

        logger.info("Hydrating series: %s (providers: %d)", series_name, len(providers))

        try:
            from apps.vod.tasks import refresh_series_episodes
            from apps.vod.models import Series
            from apps.m3u.models import M3UAccount

            success = False
            for provider in providers:
                try:
                    account_id = provider["account_id"]
                    external_series_id = provider["external_series_id"]

                    # Fetch model objects (function expects objects, not IDs)
                    account = M3UAccount.objects.get(id=account_id)
                    series = Series.objects.get(id=series_id)

                    if hasattr(refresh_series_episodes, "apply_async"):
                        refresh_series_episodes.apply_async(args=[account, series, external_series_id])
                    elif hasattr(refresh_series_episodes, "delay"):
                        refresh_series_episodes.delay(account, series, external_series_id)
                    else:
                        refresh_series_episodes(account, series, external_series_id)

                    logger.info("Enqueued hydration for %s (account: %s)", series_name, account.name)
                    success = True
                except Exception as e:
                    logger.error("Failed to enqueue hydration for %s: %s", series_name, e)

            with self.lock:
                self.active_count = max(0, self.active_count - 1)
                if success:
                    self.state[series_uuid]["status"] = "hydrated"
                    self.state[series_uuid]["failure_count"] = 0
                    self.state[series_uuid]["last_error"] = None
                else:
                    self._handle_failure_locked(series_uuid, "All providers failed")

        except Exception as e:
            with self.lock:
                self.active_count = max(0, self.active_count - 1)
            self._handle_failure(series_uuid, str(e))

    def _handle_failure(self, series_uuid: str, error: str):
        with self.lock:
            self._handle_failure_locked(series_uuid, error)

    def _handle_failure_locked(self, series_uuid: str, error: str):
        if series_uuid not in self.state:
            return

        data = self.state[series_uuid]
        data["failure_count"] += 1
        data["last_error"] = error
        data["status"] = "failed"

        delay = min(2 ** data["failure_count"], 300)
        data["next_retry"] = datetime.now() + timedelta(seconds=delay)

        self.recent_failures.append(time.time())
        recent = [t for t in self.recent_failures if time.time() - t < 60]
        if len(recent) >= 8:
            self.max_workers = max(1, self.max_workers - 1)
            logger.warning("Reducing hydration concurrency to %d due to failures", self.max_workers)

    def get_status(self) -> dict:
        with self.lock:
            total = len(self.state)
            hydrated = sum(1 for s in self.state.values() if s["status"] == "hydrated")
            hydrating = sum(1 for s in self.state.values() if s["status"] == "hydrating")
            pending = sum(1 for s in self.state.values() if s["status"] == "queued")
            failed = sum(1 for s in self.state.values() if s["status"] == "failed")

            return {
                "total_series_tracked": total,
                "hydrated": hydrated,
                "hydrating": hydrating,
                "pending": pending,
                "failed": failed,
                "current_workers": self.max_workers,
                "active_count": self.active_count,
                "recent_failures_last_minute": len([t for t in self.recent_failures if time.time() - t < 60]),
            }

    def stop(self):
        self.running = False
        for t in self.threads:
            t.join(timeout=5)
        logger.info("HydrationScheduler stopped")
