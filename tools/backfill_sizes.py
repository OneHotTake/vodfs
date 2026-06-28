"""Throttled backfill of movie sizes for VODFS's eventual-consistency size gate.

VODFS only surfaces titles whose size Dispatcharr already knows (stored bitrate).
Episodes get that during normal series hydration; movie detail is only fetched on
demand, so this script drips Dispatcharr's ``refresh_movie_advanced_data`` over the
enabled movie relations that lack a bitrate — at a controlled rate, so the provider
is never hit in a burst. Each one Dispatcharr fetches makes that movie appear in
VODFS (and Plex) on its next listing.

Run inside the Dispatcharr container, e.g.:

    docker exec -e VODFS_BACKFILL_RATE=2 -e VODFS_BACKFILL_LIMIT=5000 \\
      -e PYTHONPATH=/app:/data/plugins/vodfs/plugin \\
      -e DJANGO_SETTINGS_MODULE=dispatcharr.settings -w /app <container> \\
      sh -c 'echo "exec(open(\\"/data/plugins/vodfs/tools/backfill_sizes.py\\").read())" \\
             | /dispatcharrpy/bin/python manage.py shell'

Env:
  VODFS_BACKFILL_RATE   relations enqueued per second (default 2)
  VODFS_BACKFILL_LIMIT  max to enqueue this run, "all" for everything (default 5000)
  VODFS_BACKFILL_FORCE  "true" to re-fetch even titles refreshed <24h ago (default false)

Idempotent: only enqueues relations that still lack a bitrate, so re-running just
picks up what's left. Safe to run in waves.
"""
import os

from apps.vod.models import M3UMovieRelation
from apps.vod.tasks import refresh_movie_advanced_data

try:                                      # the gate's exact "sized" predicate
    from tree import _enabled, _MOVIE_SIZED
except ImportError:                       # pragma: no cover - path fallback
    import sys
    sys.path.insert(0, "/data/plugins/vodfs/plugin")
    from tree import _enabled, _MOVIE_SIZED

RATE = float(os.environ.get("VODFS_BACKFILL_RATE", "2") or 2)
_limit = os.environ.get("VODFS_BACKFILL_LIMIT", "5000")
LIMIT = None if str(_limit).lower() == "all" else int(_limit)
FORCE = os.environ.get("VODFS_BACKFILL_FORCE", "false").lower() == "true"

base = M3UMovieRelation.objects.filter(**_enabled())
# "Unsized" = enabled minus sized. Django's JSON exclude() mishandles missing keys
# (treats absent as non-match), so use set difference instead.
all_ids = set(base.values_list("id", flat=True))
sized_ids = set(base.filter(**_MOVIE_SIZED).values_list("id", flat=True))
todo = sorted(all_ids - sized_ids)
total = len(todo)
if LIMIT is not None:
    todo = todo[:LIMIT]

print("[vodfs-backfill] enabled=%d sized=%d unsized=%d enqueuing=%d at %.2f/s force=%s"
      % (len(all_ids), len(sized_ids), total, len(todo), RATE, FORCE))

for i, rid in enumerate(todo):
    # spread the work out so the provider sees a steady trickle, never a burst
    refresh_movie_advanced_data.apply_async((rid,), kwargs={"force_refresh": FORCE},
                                            countdown=i / RATE)

eta_min = (len(todo) / RATE) / 60 if RATE else 0
print("[vodfs-backfill] enqueued %d tasks; ~%.1f min to drain. %d still unsized after."
      % (len(todo), eta_min, max(0, total - len(todo))))
