"""Background size-hydration.

vodfs only surfaces titles whose size Dispatcharr already knows (stored bitrate).
This drips Dispatcharr's own refresh tasks so the rest fill in over time — movie
detail (``refresh_movie_advanced_data``) and un-hydrated series
(``batch_refresh_series_episodes``) — paced by a rate limit and run on a schedule
(full pass on load, then at the configured off-peak times). Convention mirrors the
PiratesIRC plugins: a daemon thread (no Celery beat), HHMM ``scheduled_times`` +
timezone + a rate limit.

All config arrives via env (set by the plugin's enable action):
  VODFS_HYDRATE_RATE      refreshes/sec; 0 disables (default 0)
  VODFS_HYDRATE_ON_LOAD   "true" => full pass when the server starts (default true)
  VODFS_HYDRATE_TIMES     comma-separated HHMM, e.g. "0300,1500" (default "")
  VODFS_HYDRATE_TZ        IANA tz for the times (default America/Chicago)
"""
import os
import time
import logging
import threading
import datetime

logger = logging.getLogger("vodfs.hydrator")


def _parse_times(raw):
    out = []
    for tok in (raw or "").replace(" ", "").split(","):
        if len(tok) == 4 and tok.isdigit():
            h, m = int(tok[:2]), int(tok[2:])
            if 0 <= h < 24 and 0 <= m < 60:
                out.append((h, m))
    return out


class Hydrator:
    def __init__(self):
        self.rate = max(0.0, float(os.environ.get("VODFS_HYDRATE_RATE", "0") or 0))
        self.on_load = os.environ.get("VODFS_HYDRATE_ON_LOAD", "true").lower() == "true"
        self.times = _parse_times(os.environ.get("VODFS_HYDRATE_TIMES", ""))
        self.tz = os.environ.get("VODFS_HYDRATE_TZ", "America/Chicago")
        self._thread = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._run_now = threading.Event()
        self._running = False
        self._last = None  # (reason, ts, movies, series)

    # --- lifecycle ---------------------------------------------------------------
    def start(self):
        if self.rate <= 0:
            logger.info("Hydration disabled (rate=0)")
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="vodfs-hydrator")
            self._thread.start()
            logger.info("Hydrator started: rate=%s/s on_load=%s times=%s tz=%s",
                        self.rate, self.on_load, self.times, self.tz)

    def stop(self):
        self._stop.set()
        self._run_now.set()

    def trigger_now(self):
        """Request an immediate pass (used by the 'Hydrate Now' action)."""
        if self.rate <= 0:
            return False
        self.start()                      # ensure the thread exists
        self._run_now.set()
        return True

    def status(self):
        nxt = self._next_run_iso()
        last = None
        if self._last:
            reason, ts, nm, ns = self._last
            last = {"reason": reason, "at": datetime.datetime.utcfromtimestamp(ts)
                    .replace(microsecond=0).isoformat() + "Z", "movies": nm, "series": ns}
        return {
            "enabled": self.rate > 0,
            "running": self._running,
            "rate_per_sec": self.rate,
            "scheduled_times": ["%02d%02d" % t for t in self.times],
            "timezone": self.tz,
            "next_run": nxt,
            "last_pass": last,
        }

    # --- scheduling --------------------------------------------------------------
    def _now(self):
        try:
            from zoneinfo import ZoneInfo
            return datetime.datetime.now(ZoneInfo(self.tz))
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    def _next_run_iso(self):
        if not self.times:
            return None
        now = self._now()
        cands = []
        for h, m in self.times:
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if t <= now:
                t += datetime.timedelta(days=1)
            cands.append(t)
        return min(cands).isoformat(timespec="minutes")

    def _loop(self):
        if self.on_load:
            self._run_pass("on-load")
        last_minute = None
        while not self._stop.is_set():
            triggered = self._run_now.wait(timeout=20)
            if self._stop.is_set():
                break
            if triggered:
                self._run_now.clear()
                self._run_pass("manual")
                continue
            now = self._now()
            key = (now.hour, now.minute)
            if key in self.times and last_minute != key:
                last_minute = key
                self._run_pass("scheduled")

    # --- the actual work ---------------------------------------------------------
    def _run_pass(self, reason):
        if self._running:
            return
        self._running = True
        try:
            from django.db import close_old_connections
            close_old_connections()
            nm = self._drip_movies()
            ns = self._drip_series()
            self._last = (reason, time.time(), nm, ns)
            logger.info("Hydration pass (%s) done: %d movies, %d series refreshed",
                        reason, nm, ns)
        except Exception:
            logger.exception("Hydration pass failed")
        finally:
            try:
                from django.db import close_old_connections
                close_old_connections()
            except Exception:
                pass
            self._running = False

    def _sleep(self):
        # pace to the configured rate; interruptible by stop
        self._stop.wait(timeout=1.0 / self.rate if self.rate else 1.0)

    def _drip_movies(self):
        try:
            from apps.vod.models import M3UMovieRelation
            from apps.vod.tasks import refresh_movie_advanced_data
            from .tree import _enabled, _MOVIE_SIZED
        except ImportError:
            try:
                from tree import _enabled, _MOVIE_SIZED  # noqa: F401
            except ImportError:
                return 0
            from apps.vod.models import M3UMovieRelation
            from apps.vod.tasks import refresh_movie_advanced_data
        base = M3UMovieRelation.objects.filter(**_enabled())
        all_ids = set(base.values_list("id", flat=True))
        sized = set(base.filter(**_MOVIE_SIZED).values_list("id", flat=True))
        todo = sorted(all_ids - sized)          # set-diff: JSON exclude() misses nulls
        n = 0
        for rid in todo:
            if self._stop.is_set():
                break
            try:
                refresh_movie_advanced_data(rid)   # self-throttled to 24h by Dispatcharr
                n += 1
            except Exception:
                logger.debug("movie refresh failed for %s", rid, exc_info=True)
            self._sleep()
        return n

    def _drip_series(self):
        try:
            from apps.vod.models import M3USeriesRelation, Series
            from apps.vod.tasks import batch_refresh_series_episodes
            from .tree import _enabled
        except ImportError:
            try:
                from tree import _enabled  # noqa: F401
            except ImportError:
                return 0
            from apps.vod.models import M3USeriesRelation, Series
            from apps.vod.tasks import batch_refresh_series_episodes
        # un-hydrated series (no episodes yet), grouped by account for the batch task
        rels = (M3USeriesRelation.objects.filter(**_enabled())
                .exclude(series__episodes__isnull=False)
                .values_list("m3u_account_id", "series_id").distinct())
        by_account = {}
        for acct_id, sid in rels:
            by_account.setdefault(acct_id, []).append(sid)
        n = 0
        for acct_id, sids in by_account.items():
            for i in range(0, len(sids), 50):     # small chunks, paced
                if self._stop.is_set():
                    return n
                chunk = sids[i:i + 50]
                try:
                    batch_refresh_series_episodes(acct_id, chunk)
                    n += len(chunk)
                except Exception:
                    logger.debug("series batch failed acct=%s", acct_id, exc_info=True)
                self._sleep()
        return n
