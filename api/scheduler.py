"""
API Scheduler - Periodic Task Orchestration
Created: Oct 2025

Handles:
- P&L snapshots (intraday 15min, EOD 23:59)
- OHLCV updates (daily 03:10, hourly :05)
- Staleness monitoring (hourly)
- API warmers (startup + periodic 5-10min)

Configuration:
- RUN_SCHEDULER=1 to enable (prevents double execution in dev)
- Timezone: Europe/Zurich
- Guards: coalesce=True, max_instances=1, misfire_grace_time=300s
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from api.config.users import is_allowed_user, validate_user_id

logger = logging.getLogger(__name__)

# Singleton scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None
_job_status: Dict[str, Dict[str, Any]] = {}


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the singleton scheduler instance"""
    return _scheduler


def get_job_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all scheduled jobs (for health endpoint)"""
    return _job_status.copy()


async def _update_job_status(job_id: str, status: str, duration_ms: Optional[float] = None, error: Optional[str] = None):
    """Update job execution status"""
    _job_status[job_id] = {
        "last_run": datetime.now().isoformat(),
        "status": status,
        "duration_ms": duration_ms,
        "error": error
    }


# ============================================================================
# JOB IMPLEMENTATIONS
# ============================================================================

async def job_pnl_intraday():
    """P&L snapshot intraday (every 15 min, 07:00-23:59 Europe/Zurich)"""
    job_id = "pnl_intraday"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting P&L intraday snapshot...")

        # Import here to avoid circular dependencies
        from scripts.pnl_snapshot import create_snapshot

        # Default params (can be overridden via env vars)
        user_id = os.getenv("SNAPSHOT_USER_ID", "jack")
        source = os.getenv("SNAPSHOT_SOURCE", "cointracking_api")
        min_usd = float(os.getenv("SNAPSHOT_MIN_USD", "1.0"))

        # Validate user_id for security (multi-tenant isolation)
        if not is_allowed_user(user_id):
            error_msg = f"Invalid or unauthorized user_id: {user_id}"
            logger.error(f"❌ [{job_id}] {error_msg}")
            await _update_job_status(job_id, "failed", 0, error_msg)
            return

        result = await create_snapshot(user_id=user_id, source=source, min_usd=min_usd)

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        if result.get("ok"):
            logger.info(f"✅ [{job_id}] P&L snapshot completed in {duration_ms:.0f}ms")
            await _update_job_status(job_id, "success", duration_ms)
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ [{job_id}] P&L snapshot failed: {error_msg}")
            await _update_job_status(job_id, "failed", duration_ms, error_msg)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] P&L snapshot exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_pnl_eod():
    """P&L snapshot EOD (daily at 23:59 Europe/Zurich)"""
    job_id = "pnl_eod"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting P&L EOD snapshot...")

        from scripts.pnl_snapshot import create_snapshot

        user_id = os.getenv("SNAPSHOT_USER_ID", "jack")
        source = os.getenv("SNAPSHOT_SOURCE", "cointracking_api")
        min_usd = float(os.getenv("SNAPSHOT_MIN_USD", "1.0"))

        # Validate user_id for security (multi-tenant isolation)
        if not is_allowed_user(user_id):
            error_msg = f"Invalid or unauthorized user_id: {user_id}"
            logger.error(f"❌ [{job_id}] {error_msg}")
            await _update_job_status(job_id, "failed", 0, error_msg)
            return

        result = await create_snapshot(user_id=user_id, source=source, min_usd=min_usd, is_eod=True)

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        if result.get("ok"):
            logger.info(f"✅ [{job_id}] P&L EOD snapshot completed in {duration_ms:.0f}ms")
            await _update_job_status(job_id, "success", duration_ms)
        else:
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ [{job_id}] P&L EOD snapshot failed: {error_msg}")
            await _update_job_status(job_id, "failed", duration_ms, error_msg)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] P&L EOD snapshot exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_ohlcv_daily():
    """OHLCV update daily (03:10 Europe/Zurich)"""
    job_id = "ohlcv_daily"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting OHLCV daily update...")

        # Import and run the existing script
        import sys
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "update_price_history.py"

        # Run as subprocess to avoid import side-effects
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 min max
        )

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        if result.returncode == 0:
            logger.info(f"✅ [{job_id}] OHLCV daily update completed in {duration_ms:.0f}ms")
            await _update_job_status(job_id, "success", duration_ms)
        else:
            logger.error(f"❌ [{job_id}] OHLCV daily update failed:\n{result.stderr}")
            await _update_job_status(job_id, "failed", duration_ms, result.stderr[:200])

    except subprocess.TimeoutExpired:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.error(f"❌ [{job_id}] OHLCV daily update timeout (>5min)")
        await _update_job_status(job_id, "timeout", duration_ms, "Timeout after 5 minutes")

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] OHLCV daily update exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_ohlcv_hourly():
    """OHLCV update hourly (every hour at :05)"""
    job_id = "ohlcv_hourly"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting OHLCV hourly update...")

        import sys
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "update_price_history.py"

        # Run update_price_history.py (incremental by default)
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120  # 2 min max for update
        )

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        if result.returncode == 0:
            logger.info(f"✅ [{job_id}] OHLCV hourly update completed in {duration_ms:.0f}ms")
            await _update_job_status(job_id, "success", duration_ms)
        else:
            logger.error(f"❌ [{job_id}] OHLCV hourly update failed:\n{result.stderr}")
            await _update_job_status(job_id, "failed", duration_ms, result.stderr[:200])

    except subprocess.TimeoutExpired:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.error(f"❌ [{job_id}] OHLCV hourly update timeout (>2min)")
        await _update_job_status(job_id, "timeout", duration_ms, "Timeout after 2 minutes")

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] OHLCV hourly update exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_staleness_monitor():
    """Staleness monitoring (hourly)"""
    job_id = "staleness_monitor"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting staleness monitoring...")

        # Check Saxo data staleness
        from api.services.sources_resolver import get_effective_source_info
        from api.services.user_fs import UserScopedFS

        # Get all users and check their Saxo sources
        saxo_issues = []

        try:
            from pathlib import Path
            import json
            import time

            users_config = Path("config/users.json")
            if users_config.exists():
                users = json.loads(users_config.read_text())

                for user in users:
                    user_id = user.get("id")
                    if not user_id:
                        continue

                    # Check Saxo source
                    try:
                        # Create user filesystem
                        project_root = Path(__file__).parent.parent
                        user_fs = UserScopedFS(str(project_root), user_id)

                        # Get source info
                        result = get_effective_source_info(user_fs, "saxobank")

                        # Calculate staleness in hours
                        if result.get("modified_at"):
                            staleness_hours = (time.time() - result["modified_at"]) / 3600

                            if staleness_hours > 24:
                                saxo_issues.append({
                                    "user_id": user_id,
                                    "staleness_hours": staleness_hours,
                                    "path": result.get("effective_path")
                                })
                    except Exception as e:
                        logger.warning(f"Failed to check Saxo staleness for user {user_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to load users config: {e}")

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        if saxo_issues:
            logger.warning(f"⚠️ [{job_id}] Found {len(saxo_issues)} stale Saxo sources")
            for issue in saxo_issues:
                logger.warning(f"   - {issue['user_id']}: {issue['staleness_hours']:.1f}h stale")
            await _update_job_status(job_id, "warning", duration_ms, f"{len(saxo_issues)} stale sources")
        else:
            logger.info(f"✅ [{job_id}] Staleness check completed in {duration_ms:.0f}ms - all fresh")
            await _update_job_status(job_id, "success", duration_ms)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] Staleness monitoring exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_api_warmers():
    """API warmers - keep caches warm (every 5-10 min)"""
    job_id = "api_warmers"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting API warmers...")

        import httpx

        # Get warmup user_id from env and validate
        warmup_user = os.getenv("WARMUP_USER_ID", "demo")

        # Validate user_id for security (multi-tenant isolation)
        if not is_allowed_user(warmup_user):
            error_msg = f"Invalid warmup user_id: {warmup_user}, skipping warmers"
            logger.warning(f"⚠️ [{job_id}] {error_msg}")
            await _update_job_status(job_id, "skipped", 0, error_msg)
            return

        # Warm up critical endpoints with validated user
        endpoints = [
            f"/balances/current?source=cointracking&user_id={warmup_user}",
            f"/portfolio/metrics?source=cointracking&user_id={warmup_user}",
            f"/api/risk/dashboard?source=cointracking&user_id={warmup_user}",
        ]

        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        logger.debug(f"   ✅ Warmed: {endpoint}")
                    else:
                        logger.warning(f"   ⚠️ Warm failed ({response.status_code}): {endpoint}")

                except Exception as e:
                    logger.warning(f"   ❌ Warm error: {endpoint} - {e}")

                # Small delay between requests
                await asyncio.sleep(0.5)

        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.info(f"✅ [{job_id}] API warmers completed in {duration_ms:.0f}ms")
        await _update_job_status(job_id, "success", duration_ms)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] API warmers exception")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_crypto_toolbox_refresh():
    """
    Refresh crypto-toolbox indicators (2x daily: 08:00 & 20:00)
    Scrapes 30+ on-chain indicators from crypto-toolbox.vercel.app
    """
    job_id = "crypto_toolbox_refresh"
    start = datetime.now()

    try:
        logger.info(f"🔄 [{job_id}] Starting crypto-toolbox indicators refresh...")

        import httpx

        # Call the FastAPI crypto-toolbox endpoint with force refresh
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        url = f"{base_url}/api/crypto-toolbox?force=true"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        indicators_count = data.get("total_count", 0)
        critical_count = data.get("critical_count", 0)

        logger.info(f"✅ [{job_id}] Crypto-toolbox refresh completed in {duration_ms:.0f}ms")
        logger.info(f"   📊 {indicators_count} indicators scraped ({critical_count} critical)")
        await _update_job_status(job_id, "success", duration_ms)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] Crypto-toolbox refresh failed")
        await _update_job_status(job_id, "error", duration_ms, str(e))


async def job_weekly_ml_training():
    """
    Entraîne les modèles ML lourds chaque dimanche à 3h du matin.

    - Regime detection (20 ans, ~60-90s)
    - Correlation forecaster (20 ans, ~30-40s)

    Total: ~2 minutes par semaine
    """
    job_id = "weekly_ml_training"
    start = datetime.now()

    try:
        logger.info(f"🤖 [{job_id}] Starting weekly ML training (20 years data)...")

        from services.ml.bourse.stocks_adapter import StocksMLAdapter

        adapter = StocksMLAdapter()

        # Force retrain regime detection with 20 years of data
        regime_result = await adapter.detect_market_regime(
            benchmark="SPY",
            lookback_days=7300,  # 20 ans
            force_retrain=True   # Ignore cache age
        )

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        logger.info(f"✅ [{job_id}] Regime model trained: {regime_result['current_regime']} "
                   f"({regime_result['confidence']:.1%} confidence) in {duration_ms:.0f}ms")

        await _update_job_status(job_id, "success", duration_ms)

        # TODO: Ajouter correlation forecaster si nécessaire
        # await adapter.forecast_correlation([...], force_retrain=True)

    except Exception as e:
        duration_ms = (datetime.now() - start).total_seconds() * 1000
        logger.exception(f"❌ [{job_id}] Weekly ML training failed")
        await _update_job_status(job_id, "error", duration_ms, str(e))
        # Ne pas lever exception - retry next week


# ============================================================================
# SCHEDULER LIFECYCLE
# ============================================================================

async def initialize_scheduler() -> bool:
    """
    Initialize and start the APScheduler.

    Returns:
        bool: True if scheduler started successfully
    """
    global _scheduler

    # Check if scheduler is enabled
    if os.getenv("RUN_SCHEDULER", "0") != "1":
        logger.info("⏸️ Scheduler disabled (RUN_SCHEDULER != 1)")
        return False

    if _scheduler is not None:
        logger.warning("⚠️ Scheduler already initialized")
        return True

    try:
        logger.info("🚀 Initializing APScheduler...")

        # Create scheduler with timezone
        _scheduler = AsyncIOScheduler(timezone="Europe/Zurich")

        # Common job defaults
        job_defaults = {
            "coalesce": True,  # Merge missed runs
            "max_instances": 1,  # Prevent overlapping executions
            "misfire_grace_time": 300,  # 5 min grace for missed jobs
        }

        # Add jobs with cron triggers

        # P&L intraday: every 15 min, 07:00-23:59
        _scheduler.add_job(
            job_pnl_intraday,
            CronTrigger(minute="*/15", hour="7-23", timezone="Europe/Zurich", jitter=60),
            id="pnl_intraday",
            name="P&L Snapshot Intraday",
            **job_defaults
        )

        # P&L EOD: daily at 23:59
        _scheduler.add_job(
            job_pnl_eod,
            CronTrigger(hour=23, minute=59, timezone="Europe/Zurich", jitter=60),
            id="pnl_eod",
            name="P&L Snapshot EOD",
            **job_defaults
        )

        # OHLCV daily: 03:10
        _scheduler.add_job(
            job_ohlcv_daily,
            CronTrigger(hour=3, minute=10, timezone="Europe/Zurich", jitter=60),
            id="ohlcv_daily",
            name="OHLCV Update Daily",
            **job_defaults
        )

        # OHLCV hourly: every hour at :05
        _scheduler.add_job(
            job_ohlcv_hourly,
            CronTrigger(minute=5, timezone="Europe/Zurich", jitter=30),
            id="ohlcv_hourly",
            name="OHLCV Update Hourly",
            **job_defaults
        )

        # Staleness monitor: every hour at :15
        _scheduler.add_job(
            job_staleness_monitor,
            CronTrigger(minute=15, timezone="Europe/Zurich"),
            id="staleness_monitor",
            name="Staleness Monitor",
            **job_defaults
        )

        # API warmers: every 10 minutes
        _scheduler.add_job(
            job_api_warmers,
            IntervalTrigger(minutes=10, jitter=60),
            id="api_warmers",
            name="API Warmers",
            **job_defaults
        )

        # Crypto-Toolbox refresh: 2x daily at 08:00 and 20:00
        _scheduler.add_job(
            job_crypto_toolbox_refresh,
            CronTrigger(hour='8,20', minute=0, timezone="Europe/Zurich", jitter=120),
            id="crypto_toolbox_refresh",
            name="Crypto-Toolbox Indicators Refresh (2x daily)",
            **job_defaults
        )

        # Weekly ML training: every Sunday at 03:00
        _scheduler.add_job(
            job_weekly_ml_training,
            CronTrigger(day_of_week='sun', hour=3, minute=0, timezone="Europe/Zurich", jitter=300),
            id="weekly_ml_training",
            name="Weekly ML Training (20y data)",
            **job_defaults
        )

        # Start scheduler
        _scheduler.start()

        # Log scheduled jobs
        jobs = _scheduler.get_jobs()
        logger.info(f"✅ APScheduler started with {len(jobs)} jobs:")
        for job in jobs:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z") if job.next_run_time else "N/A"
            logger.info(f"   - {job.id}: next run at {next_run}")

        return True

    except Exception as e:
        logger.exception(f"❌ Failed to initialize scheduler: {e}")
        _scheduler = None
        return False


async def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    global _scheduler

    if _scheduler is None:
        logger.info("⏸️ Scheduler not running, nothing to shutdown")
        return

    try:
        logger.info("🛑 Shutting down APScheduler...")

        # Shutdown with grace period
        _scheduler.shutdown(wait=True)
        _scheduler = None

        logger.info("✅ APScheduler shutdown complete")

    except Exception as e:
        logger.exception(f"❌ Failed to shutdown scheduler: {e}")
