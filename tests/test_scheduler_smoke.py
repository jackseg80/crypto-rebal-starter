"""
Smoke Test for Task Scheduler
Tests basic scheduler initialization and health endpoint.
"""

import os
import pytest
from fastapi.testclient import TestClient


def test_scheduler_disabled_by_default():
    """Test that scheduler is disabled by default (RUN_SCHEDULER != 1)"""
    # Ensure RUN_SCHEDULER is not set
    os.environ.pop("RUN_SCHEDULER", None)

    # Import app (must be after env var cleared)
    from api.main import app
    from api.scheduler import get_scheduler

    # Scheduler should not be initialized
    scheduler = get_scheduler()
    assert scheduler is None, "Scheduler should be None when RUN_SCHEDULER != 1"


def test_scheduler_health_endpoint_disabled():
    """Test health endpoint when scheduler is disabled"""
    os.environ.pop("RUN_SCHEDULER", None)

    from api.main import app

    client = TestClient(app)
    response = client.get("/api/scheduler/health")

    assert response.status_code == 200
    data = response.json()

    assert data["ok"] is False
    assert data["enabled"] is False
    assert "not running" in data["message"].lower()
    assert data["jobs"] == {}


def test_pnl_snapshot_script_exists():
    """Test that P&L snapshot script exists and is importable"""
    from pathlib import Path

    script_path = Path("scripts/pnl_snapshot.py")
    assert script_path.exists(), "scripts/pnl_snapshot.py should exist"

    # Test import
    from scripts.pnl_snapshot import create_snapshot
    assert callable(create_snapshot), "create_snapshot should be callable"


def test_scheduler_module_importable():
    """Test that scheduler module can be imported"""
    from api.scheduler import (
        initialize_scheduler,
        shutdown_scheduler,
        get_scheduler,
        get_job_status
    )

    assert callable(initialize_scheduler)
    assert callable(shutdown_scheduler)
    assert callable(get_scheduler)
    assert callable(get_job_status)


@pytest.mark.asyncio
async def test_scheduler_initialization_with_flag():
    """Test scheduler initialization when RUN_SCHEDULER=1"""
    # Set flag
    os.environ["RUN_SCHEDULER"] = "1"

    try:
        from api.scheduler import initialize_scheduler, shutdown_scheduler, get_scheduler

        # Initialize
        result = await initialize_scheduler()
        assert result is True, "Scheduler should initialize successfully"

        # Check scheduler instance
        scheduler = get_scheduler()
        assert scheduler is not None, "Scheduler should be initialized"

        # Check jobs are registered
        jobs = scheduler.get_jobs()
        assert len(jobs) == 6, f"Expected 6 jobs, got {len(jobs)}"

        job_ids = [job.id for job in jobs]
        expected_jobs = [
            "pnl_intraday",
            "pnl_eod",
            "ohlcv_daily",
            "ohlcv_hourly",
            "staleness_monitor",
            "api_warmers"
        ]

        for expected_job in expected_jobs:
            assert expected_job in job_ids, f"Job {expected_job} should be registered"

        # Cleanup
        await shutdown_scheduler()

    finally:
        # Reset env
        os.environ.pop("RUN_SCHEDULER", None)


def test_scheduler_job_names():
    """Test that job names are descriptive"""
    os.environ["RUN_SCHEDULER"] = "1"

    try:
        import asyncio
        from api.scheduler import initialize_scheduler, shutdown_scheduler, get_scheduler

        # Initialize
        asyncio.run(initialize_scheduler())

        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()

        job_names = {job.id: job.name for job in jobs}

        expected_names = {
            "pnl_intraday": "P&L Snapshot Intraday",
            "pnl_eod": "P&L Snapshot EOD",
            "ohlcv_daily": "OHLCV Update Daily",
            "ohlcv_hourly": "OHLCV Update Hourly",
            "staleness_monitor": "Staleness Monitor",
            "api_warmers": "API Warmers"
        }

        for job_id, expected_name in expected_names.items():
            assert job_names[job_id] == expected_name, f"Job {job_id} name mismatch"

        # Cleanup
        asyncio.run(shutdown_scheduler())

    finally:
        os.environ.pop("RUN_SCHEDULER", None)


def test_scheduler_timezone():
    """Test that scheduler uses Europe/Zurich timezone"""
    os.environ["RUN_SCHEDULER"] = "1"

    try:
        import asyncio
        from api.scheduler import initialize_scheduler, shutdown_scheduler, get_scheduler

        asyncio.run(initialize_scheduler())

        scheduler = get_scheduler()

        # Check scheduler timezone
        assert str(scheduler.timezone) == "Europe/Zurich", "Scheduler should use Europe/Zurich timezone"

        # Cleanup
        asyncio.run(shutdown_scheduler())

    finally:
        os.environ.pop("RUN_SCHEDULER", None)


if __name__ == "__main__":
    """Run smoke tests"""
    import sys

    print("Running scheduler smoke tests...\n")

    try:
        # Test 1: Scheduler disabled
        print("1. Testing scheduler disabled by default...")
        test_scheduler_disabled_by_default()
        print("   [PASS]\n")

        # Test 2: Health endpoint
        print("2. Testing health endpoint (scheduler disabled)...")
        test_scheduler_health_endpoint_disabled()
        print("   [PASS]\n")

        # Test 3: Script exists
        print("3. Testing P&L snapshot script exists...")
        test_pnl_snapshot_script_exists()
        print("   [PASS]\n")

        # Test 4: Module import
        print("4. Testing scheduler module import...")
        test_scheduler_module_importable()
        print("   [PASS]\n")

        # Test 5: Initialization
        print("5. Testing scheduler initialization (RUN_SCHEDULER=1)...")
        import asyncio
        asyncio.run(test_scheduler_initialization_with_flag())
        print("   [PASS]\n")

        # Test 6: Job names
        print("6. Testing job names...")
        test_scheduler_job_names()
        print("   [PASS]\n")

        # Test 7: Timezone
        print("7. Testing scheduler timezone...")
        test_scheduler_timezone()
        print("   [PASS]\n")

        print("[OK] All scheduler smoke tests passed!")
        sys.exit(0)

    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
