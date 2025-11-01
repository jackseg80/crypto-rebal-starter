# Task Scheduler - Periodic Jobs Documentation

**Created:** Oct 2025
**Status:** Production Ready
**Module:** `api/scheduler.py`

## Overview

The Task Scheduler orchestrates periodic background jobs for the crypto portfolio management system using APScheduler. It handles P&L snapshots, OHLCV updates, staleness monitoring, and API cache warming.

## Architecture

- **Framework:** APScheduler (AsyncIOScheduler)
- **Timezone:** Europe/Zurich
- **Lifecycle:** Integrated into FastAPI startup/shutdown hooks ([api/startup.py](../api/startup.py))
- **Isolation:** Single-instance execution with `max_instances=1` to prevent overlaps

## Configuration

### Enable/Disable Scheduler

```bash
# Enable scheduler (required in production)
export RUN_SCHEDULER=1

# Disable scheduler (default in dev to prevent double execution with --reload)
export RUN_SCHEDULER=0
```

**Important:**
- In dev mode with `--reload`, keep `RUN_SCHEDULER=0` to avoid duplicate job execution
- On Windows, `--reload` is incompatible with Playwright jobs (use normal mode if scheduler enabled)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_SCHEDULER` | `0` | Enable scheduler (set to `1` in production) |
| `SNAPSHOT_USER_ID` | `jack` | Default user ID for P&L snapshots |
| `SNAPSHOT_SOURCE` | `cointracking_api` | Default data source for snapshots |
| `SNAPSHOT_MIN_USD` | `1.0` | Minimum USD threshold for snapshots |
| `API_BASE_URL` | `http://localhost:8080` | API base URL for warmers |

## Scheduled Jobs

### 1. P&L Snapshot Intraday

**Schedule:** Every 15 minutes, 07:00-23:59 Europe/Zurich
**Job ID:** `pnl_intraday`
**Function:** [api/scheduler.py:job_pnl_intraday()](../api/scheduler.py)
**Purpose:** Track portfolio P&L throughout the day

**Cron Expression:**
```
minute="*/15", hour="7-23", timezone="Europe/Zurich", jitter=60
```

**Parameters:**
- Uses `SNAPSHOT_USER_ID`, `SNAPSHOT_SOURCE`, `SNAPSHOT_MIN_USD` env vars
- Calls [scripts/pnl_snapshot.py:create_snapshot()](../scripts/pnl_snapshot.py)

**Next Runs Example:**
- 07:00, 07:15, 07:30, ..., 23:45

---

### 2. P&L Snapshot EOD

**Schedule:** Daily at 23:59 Europe/Zurich
**Job ID:** `pnl_eod`
**Function:** [api/scheduler.py:job_pnl_eod()](../api/scheduler.py)
**Purpose:** Create end-of-day portfolio snapshot

**Cron Expression:**
```
hour=23, minute=59, timezone="Europe/Zurich", jitter=60
```

**Parameters:**
- Same as intraday, but marks snapshot as EOD (`is_eod=True`)

---

### 3. OHLCV Update Daily

**Schedule:** Daily at 03:10 Europe/Zurich
**Job ID:** `ohlcv_daily`
**Function:** [api/scheduler.py:job_ohlcv_daily()](../api/scheduler.py)
**Purpose:** Full daily price history update

**Cron Expression:**
```
hour=3, minute=10, timezone="Europe/Zurich", jitter=60
```

**Implementation:**
- Runs [scripts/update_price_history.py](../scripts/update_price_history.py) as subprocess
- Timeout: 5 minutes max
- Updates OHLCV data for all tracked assets

---

### 4. OHLCV Update Hourly

**Schedule:** Every hour at :05 (e.g., 00:05, 01:05, 02:05...)
**Job ID:** `ohlcv_hourly`
**Function:** [api/scheduler.py:job_ohlcv_hourly()](../api/scheduler.py)
**Purpose:** Incremental hourly price updates

**Cron Expression:**
```
minute=5, timezone="Europe/Zurich", jitter=30
```

**Implementation:**
- Runs `update_price_history.py --incremental`
- Timeout: 2 minutes max
- Lighter than daily full update

---

### 5. Staleness Monitor

**Schedule:** Every hour at :15 (e.g., 00:15, 01:15, 02:15...)
**Job ID:** `staleness_monitor`
**Function:** [api/scheduler.py:job_staleness_monitor()](../api/scheduler.py)
**Purpose:** Check data freshness across all users and sources

**Cron Expression:**
```
minute=15, timezone="Europe/Zurich"
```

**Checks:**
- Saxo data staleness (threshold: 24 hours)
- CoinTracking uploads freshness
- Logs warnings for stale data

---

### 6. API Warmers

**Schedule:** Every 10 minutes
**Job ID:** `api_warmers`
**Function:** [api/scheduler.py:job_api_warmers()](../api/scheduler.py)
**Purpose:** Keep critical endpoint caches warm

**Cron Expression:**
```
IntervalTrigger(minutes=10, jitter=60)
```

**Endpoints Warmed:**
- `/balances/current?source=cointracking&user_id=demo`
- `/portfolio/metrics?source=cointracking&user_id=demo`
- `/api/risk/dashboard?source=cointracking&user_id=demo`

**Timeout:** 10 seconds per request

---

## Job Configuration Defaults

All jobs use these APScheduler defaults:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `coalesce` | `True` | Merge multiple missed runs into one |
| `max_instances` | `1` | Prevent overlapping executions |
| `misfire_grace_time` | `300` | 5-minute grace period for missed jobs |
| `jitter` | `30-60` | Random delay (seconds) to avoid load spikes |

## Manual Job Execution

### Run P&L Snapshot Manually

```bash
# Activate venv first
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Linux/Mac

# Run snapshot
python scripts/pnl_snapshot.py --user_id jack --source cointracking_api --min_usd 1.0

# Mark as EOD snapshot
python scripts/pnl_snapshot.py --eod
```

### Run OHLCV Update Manually

```bash
# Full update
python scripts/update_price_history.py

# Incremental update
python scripts/update_price_history.py --incremental
```

## Monitoring & Health

### Health Check Endpoint

**GET** `/api/scheduler/health`

**Response (scheduler enabled):**
```json
{
  "ok": true,
  "enabled": true,
  "jobs_count": 6,
  "jobs": {
    "pnl_intraday": {
      "last_run": "2025-10-02T14:30:00",
      "status": "success",
      "duration_ms": 245.3,
      "error": null,
      "next_run": "2025-10-02T14:45:00+02:00",
      "name": "P&L Snapshot Intraday"
    },
    "ohlcv_daily": {
      "last_run": "2025-10-02T03:10:00",
      "status": "success",
      "duration_ms": 12543.7,
      "error": null,
      "next_run": "2025-10-03T03:10:00+02:00",
      "name": "OHLCV Update Daily"
    }
  },
  "next_runs": {
    "pnl_intraday": {
      "name": "P&L Snapshot Intraday",
      "next_run": "2025-10-02T14:45:00+02:00"
    }
  }
}
```

**Response (scheduler disabled):**
```json
{
  "ok": false,
  "enabled": false,
  "message": "Scheduler not running (RUN_SCHEDULER != 1)",
  "jobs": {}
}
```

### Job Logs

All jobs log to the standard application logger with structured format:

```
2025-10-02 14:30:00 INFO [pnl_intraday] Starting P&L intraday snapshot...
2025-10-02 14:30:00 INFO [pnl_intraday] ✅ P&L snapshot completed in 245ms
```

**Error logs:**
```
2025-10-02 14:30:00 ERROR [pnl_intraday] ❌ P&L snapshot failed: API timeout
```

### Snapshot Logs

P&L snapshots write to `data/logs/snapshots.log`:

```
[2025-10-02 14:30:00] intraday OK - user=jack source=cointracking_api
[2025-10-02 23:59:00] EOD OK - user=jack source=cointracking_api
[2025-10-02 15:30:00] intraday ERROR - user=jack source=cointracking_api - HTTP 429: Rate limit
```

## Production Deployment

### Docker

Add to `docker-compose.yml`:

```yaml
environment:
  - RUN_SCHEDULER=1
  - SNAPSHOT_USER_ID=jack
  - SNAPSHOT_SOURCE=cointracking_api
  - TZ=Europe/Zurich  # Important for correct job timing
```

### Systemd (Linux)

Scheduler runs within FastAPI process, no separate service needed:

```ini
[Service]
Environment="RUN_SCHEDULER=1"
Environment="TZ=Europe/Zurich"
ExecStart=/path/to/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8080
```

### Windows Task Scheduler (Alternative)

If you prefer Windows native scheduling over in-process:

1. Keep `RUN_SCHEDULER=0`
2. Use `scripts/setup_daily_snapshot_task.ps1` to configure Windows Task Scheduler
3. Configure separate tasks for OHLCV updates

**Note:** In-process scheduler is recommended for better integration and monitoring.

## Troubleshooting

### Scheduler Not Starting

**Symptom:** Log shows "⏸️ Scheduler disabled"

**Solution:**
```bash
# Check environment variable
echo $RUN_SCHEDULER  # Should be "1"

# Set and restart
export RUN_SCHEDULER=1
uvicorn api.main:app --reload
```

---

### Jobs Not Running

**Symptom:** Health endpoint shows no job history

**Check:**
1. Verify scheduler is enabled: `GET /api/scheduler/health`
2. Check logs for job execution attempts
3. Verify timezone is correct (Europe/Zurich)
4. Check `next_run` times in health response

---

### OHLCV Update Timeout

**Symptom:** Job status shows "timeout" after 5 minutes

**Solutions:**
- Reduce number of tracked assets
- Use `--incremental` flag for hourly updates
- Increase timeout in [api/scheduler.py:221](../api/scheduler.py) (daily) or [api/scheduler.py:266](../api/scheduler.py) (hourly)

---

### Double Execution in Dev

**Symptom:** Jobs run twice when using `--reload`

**Solution:**
```bash
# Disable scheduler in dev
export RUN_SCHEDULER=0

# OR run without --reload
uvicorn api.main:app --port 8080  # No --reload flag
```

---

### Windows + Playwright + Reload Issues

**Symptom:** Playwright crashes when using `--reload` on Windows

**Solution:**
- Do NOT use `--reload` when `RUN_SCHEDULER=1` on Windows
- Or disable scheduler in dev and use manual scripts

---

## Performance Considerations

### Resource Usage

| Job | CPU | Memory | I/O | Duration (avg) |
|-----|-----|--------|-----|----------------|
| P&L Intraday | Low | ~50 MB | Low | 200-500 ms |
| P&L EOD | Low | ~50 MB | Low | 200-500 ms |
| OHLCV Daily | Medium | ~100 MB | High | 5-30 seconds |
| OHLCV Hourly | Low | ~80 MB | Medium | 1-5 seconds |
| Staleness Monitor | Low | ~30 MB | Low | 100-300 ms |
| API Warmers | Low | ~20 MB | Low | 1-2 seconds |

### Concurrency

- All jobs use `max_instances=1` to prevent overlaps
- Jitter (30-60s) prevents multiple jobs starting simultaneously
- Staleness monitor runs at :15, OHLCV hourly at :05 (separation)

### Rate Limits

- API warmers space requests 500ms apart
- P&L snapshots respect CoinTracking API rate limits (60 req/min)
- OHLCV updates implement exponential backoff on 429 errors

## Extending the Scheduler

### Add New Job

1. **Define job function** in [api/scheduler.py](../api/scheduler.py):

```python
async def job_my_custom_task():
    job_id = "my_custom_task"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting custom task...")

        # Your logic here
        result = await some_async_function()

        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.info(f"✅ [{job_id}] Completed in {duration_ms:.0f}ms")
        await _update_job_status(job_id, "success", duration_ms)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] Exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))
```

2. **Register job** in `initialize_scheduler()`:

```python
_scheduler.add_job(
    job_my_custom_task,
    CronTrigger(hour=12, minute=0, timezone="Europe/Zurich"),  # Daily at noon
    id="my_custom_task",
    name="My Custom Task",
    **job_defaults
)
```

3. **Test manually:**

```python
from api.scheduler import job_my_custom_task
await job_my_custom_task()
```

### Modify Job Schedule

Edit cron expression in `initialize_scheduler()`:

```python
# Change P&L intraday to every 30 minutes
CronTrigger(minute="*/30", hour="7-23", timezone="Europe/Zurich", jitter=60)

# Change OHLCV daily to 02:00
CronTrigger(hour=2, minute=0, timezone="Europe/Zurich", jitter=60)
```

## Related Documentation

- [P&L Today](PNL_TODAY.md) - Portfolio snapshot system
- OHLCV Data: see [risk-dashboard.md](risk-dashboard.md) (sources de données et scripts), and `services/price_history.py`
- [Startup Lifecycle](../api/startup.py) - Application initialization
- [Multi-User System](../CLAUDE.md#3-système-multi-utilisateurs) - User isolation

## Maintenance

### Regular Tasks

- **Weekly:** Check [data/logs/snapshots.log](../data/logs/snapshots.log) for errors
- **Monthly:** Review job durations in health endpoint, optimize if needed
- **Quarterly:** Review job schedules with business requirements

### Monitoring Alerts (Optional)

Set up alerts for:
- Job failures (status != "success")
- Job duration exceeds threshold (e.g., OHLCV >60s)
- Scheduler downtime (health endpoint returns 500)
- Staleness warnings (>24h old data)

---

**Last Updated:** Oct 2025
**Maintainer:** FastAPI Team
**Status:** ✅ Production Ready

