# Episode Hydration Strategy

## Problem

When a Series is first added to Dispatcharr, it may have zero episodes (no M3UEpisodeRelation entries). Browsing such a Series shows an empty directory, which is confusing for users.

## Solution

The plugin automatically triggers episode hydration when a user browses a Series directory with zero episodes.

## Hydration Flow

```
1. User browses /Series/All/Show Name/
2. HTTP handler requests episodes for series
3. Integration queries M3UEpisodeRelation → zero results
4. Integration checks hydration state:
   a. Is auto_hydrate enabled?
   b. Is series in cooldown?
   c. Has hydration been triggered recently?
5. If not in cooldown:
   a. Find M3USeriesRelation for series
   b. Get external_series_id
   c. Queue refresh_series_episodes.delay()
6. Task runs in background (Celery)
7. Episodes fetched from provider
8. Episodes created in Dispatcharr
9. M3UEpisodeRelation entries created
10. Next browse shows episodes
```

## Cooldown Management

To prevent spamming the hydration system, each Series has a cooldown timer.

**Cooldown Duration**: 5 minutes (300 seconds)

**Cooldown Logic**:
```python
if series_uuid in self._hydration_queue:
    last_hydration = self._hydration_queue[series_uuid]
    cooldown_remaining = self._hydration_cooldown - (now - last_hydration)
    if cooldown_remaining > 0:
        return False  # In cooldown, don't trigger
```

**Why Cooldown?**
- Prevents duplicate task submissions
- Avoids overwhelming Dispatcharr with background tasks
- Gives provider API time to respond
- Respects rate limits

## Bounded Concurrency

When multiple Series are browsed simultaneously, we limit concurrent hydration tasks.

**Concurrency Limit**: 5 concurrent tasks

**Implementation**: Use asyncio.Semaphore in child process

```python
hydration_semaphore = asyncio.Semaphore(5)

async def trigger_hydration(series_uuid):
    async with hydration_semaphore:
        # Trigger hydration task
        await refresh_series_episodes.delay(...)
```

**Why Limit?**
- Prevents overwhelming Dispatcharr's task queue
- Avoids provider API rate limits
- Ensures system remains responsive

## Fire-and-Forget

Hydration tasks are non-blocking and fire-and-forget.

**Pattern**:
```python
# Queue task, don't wait for completion
refresh_series_episodes.delay(account_id, series_id, external_series_id)

# Continue with directory listing
return serve_directory(node, path)
```

**Benefits**:
- Directory listings return immediately
- User sees directory even while episodes fetch
- No timeout issues for large Series
- Background processing

## Task Selection

The plugin uses Dispatcharr's built-in `refresh_series_episodes` task.

**Location**: `apps.vod.tasks.refresh_series_episodes`

**Parameters**:
- `account_id` - M3U account ID
- `series_id` - Series model ID
- `external_series_id` - Provider's series ID

**What It Does**:
- Fetches episode data from provider
- Creates Episode models
- Creates M3UEpisodeRelation entries
- Handles duplicates gracefully

## Hydration State

The plugin maintains hydration state in memory:

```python
self._hydration_queue: Dict[str, datetime] = {}
```

**Key**: Series UUID
**Value**: Timestamp of last hydration trigger

**Note**: State is lost on restart, but cooldown prevents immediate re-triggering.

## Edge Cases

### Series Already Hydrated

If episodes already exist, hydration is not triggered.

```python
episode_count = series.episodes.count()
if episode_count > 0:
    return  # Don't trigger hydration
```

### No M3U Account

If no active M3U account is found, hydration cannot trigger.

```python
accounts = M3UAccount.objects.filter(is_active=True)
if not accounts:
    logger.warning("No active M3U accounts")
    return False
```

### No External Series ID

If M3USeriesRelation has no external_series_id, hydration cannot trigger.

```python
if not rel.external_series_id:
    logger.warning("No external_series_id for series %s", series.name)
    continue
```

### Task Failure

If the hydration task fails, it's logged but doesn't block browsing.

**User Experience**:
- Directory appears empty initially
- Next browse (after cooldown) shows episodes
- If still empty, check Dispatcharr logs

### Provider API Down

If provider API is down, the task fails gracefully.

**Behavior**:
- Task logs error
- Cooldown timer prevents immediate retry
- User sees empty directory
- Retry after cooldown expires

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_hydrate_empty_series` | Enable automatic hydration | true |

Users can disable hydration if they prefer manual refresh.

## Monitoring

**Logs**:
- Hydration trigger: "Enqueued hydration for series {name}"
- Cooldown active: "Series {uuid} in cooldown ({seconds} remaining)"
- No episodes: "Series {uuid} has zero episodes"
- Task queued: "refresh_series_episodes.delay(...)"

**UI**:
- No direct hydration status shown
- Directory listings show actual state

## Future Enhancements

- [ ] Show hydration progress in directory listings
- [ ] Manual "Refresh" button per Series
- [ ] Configurable cooldown duration
- [ ] Configurable concurrency limit
- [ ] Hydration status API endpoint
- [ ] Hydration history and statistics
- [ ] Retry failed hydrations automatically