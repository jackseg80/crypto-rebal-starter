"""
P&L Snapshot Script - Python Native (Cross-Platform)
Created: Oct 2025

Creates portfolio snapshots for P&L tracking via API.
Replaces PowerShell scripts/daily_snapshot.ps1 with pure Python.

Usage:
    python scripts/pnl_snapshot.py
    python scripts/pnl_snapshot.py --user_id jack --source cointracking_api --min_usd 1.0

Environment Variables:
    SNAPSHOT_USER_ID: User ID (default: jack)
    SNAPSHOT_SOURCE: Data source (default: cointracking_api)
    SNAPSHOT_MIN_USD: Minimum USD threshold (default: 1.0)
    API_BASE_URL: API base URL (default: http://localhost:8000)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def create_snapshot(
    user_id: str = "jack",
    source: str = "cointracking_api",
    min_usd: float = 1.0,
    is_eod: bool = False,
    base_url: str = "http://localhost:8000"
) -> Dict[str, Any]:
    """
    Create a portfolio snapshot via API.

    Args:
        user_id: User ID
        source: Data source (cointracking, cointracking_api, saxobank)
        min_usd: Minimum USD value threshold
        is_eod: Whether this is an end-of-day snapshot
        base_url: API base URL

    Returns:
        dict: Response with 'ok' status and optional 'error'
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_type = "EOD" if is_eod else "intraday"

    logger.info(f"📸 Creating {snapshot_type} portfolio snapshot - {timestamp}")
    logger.info(f"   User: {user_id}")
    logger.info(f"   Source: {source}")
    logger.info(f"   Min USD: {min_usd}")

    try:
        # Build API URL
        url = f"{base_url}/portfolio/snapshot"
        params = {
            "source": source,
            "user_id": user_id,
            "min_usd": min_usd
        }

        # Call API with timeout
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params)

            # Parse response
            if response.status_code == 200:
                data = response.json()

                if data.get("ok"):
                    logger.info("✅ Snapshot created successfully")

                    # Log to file
                    await _log_snapshot_success(timestamp, user_id, source, snapshot_type)

                    return {"ok": True, "data": data}
                else:
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"❌ Snapshot creation failed: {error_msg}")

                    await _log_snapshot_error(timestamp, user_id, source, snapshot_type, error_msg)

                    return {"ok": False, "error": error_msg}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ API call failed: {error_msg}")

                await _log_snapshot_error(timestamp, user_id, source, snapshot_type, error_msg)

                return {"ok": False, "error": error_msg}

    except httpx.TimeoutException:
        error_msg = "Request timeout (>30s)"
        logger.error(f"❌ {error_msg}")

        await _log_snapshot_error(timestamp, user_id, source, snapshot_type, error_msg)

        return {"ok": False, "error": error_msg}

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"❌ Error calling API: {error_msg}")

        await _log_snapshot_error(timestamp, user_id, source, snapshot_type, error_msg)

        return {"ok": False, "error": error_msg}


async def _log_snapshot_success(timestamp: str, user_id: str, source: str, snapshot_type: str):
    """Log successful snapshot to file"""
    try:
        log_dir = Path("data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "snapshots.log"
        log_entry = f"[{timestamp}] {snapshot_type} OK - user={user_id} source={source}\n"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except Exception as e:
        logger.warning(f"Failed to write success log: {e}")


async def _log_snapshot_error(timestamp: str, user_id: str, source: str, snapshot_type: str, error: str):
    """Log failed snapshot to file"""
    try:
        log_dir = Path("data/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "snapshots.log"
        log_entry = f"[{timestamp}] {snapshot_type} ERROR - user={user_id} source={source} - {error}\n"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except Exception as e:
        logger.warning(f"Failed to write error log: {e}")


async def main():
    """Main entry point for CLI usage"""
    parser = argparse.ArgumentParser(
        description="Create portfolio snapshot for P&L tracking"
    )

    parser.add_argument(
        "--user_id",
        type=str,
        default=os.getenv("SNAPSHOT_USER_ID", "jack"),
        help="User ID (default: jack or SNAPSHOT_USER_ID env)"
    )

    parser.add_argument(
        "--source",
        type=str,
        default=os.getenv("SNAPSHOT_SOURCE", "cointracking_api"),
        help="Data source (default: cointracking_api or SNAPSHOT_SOURCE env)"
    )

    parser.add_argument(
        "--min_usd",
        type=float,
        default=float(os.getenv("SNAPSHOT_MIN_USD", "1.0")),
        help="Minimum USD threshold (default: 1.0 or SNAPSHOT_MIN_USD env)"
    )

    parser.add_argument(
        "--eod",
        action="store_true",
        help="Mark as end-of-day snapshot"
    )

    parser.add_argument(
        "--base_url",
        type=str,
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000 or API_BASE_URL env)"
    )

    args = parser.parse_args()

    # Create snapshot
    result = await create_snapshot(
        user_id=args.user_id,
        source=args.source,
        min_usd=args.min_usd,
        is_eod=args.eod,
        base_url=args.base_url
    )

    # Exit with appropriate code
    if result.get("ok"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
