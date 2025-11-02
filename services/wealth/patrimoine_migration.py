"""Migration service for banks.json → patrimoine.json - Multi-tenant."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_banks_path(user_id: str) -> Path:
    """Return path to legacy banks snapshot."""
    return Path(f"data/users/{user_id}/banks/snapshot.json")


def _get_patrimoine_path(user_id: str) -> Path:
    """Return path to new patrimoine storage."""
    return Path(f"data/users/{user_id}/wealth/patrimoine.json")


def _migrate_account_to_item(account: dict) -> dict:
    """
    Migrate a legacy bank account to patrimoine item format.

    Legacy format:
        {
            "id": "uuid",
            "bank_name": "UBS",
            "account_type": "current",
            "balance": 5000.0,
            "currency": "CHF"
        }

    New format:
        {
            "id": "uuid",
            "name": "UBS (current)",
            "category": "liquidity",
            "type": "bank_account",
            "value": 5000.0,
            "currency": "CHF",
            "acquisition_date": null,
            "notes": null,
            "metadata": {
                "bank_name": "UBS",
                "account_type": "current"
            }
        }
    """
    bank_name = account.get("bank_name", "Unknown Bank")
    account_type = account.get("account_type", "other")

    return {
        "id": account.get("id"),
        "name": f"{bank_name} ({account_type})",
        "category": "liquidity",
        "type": "bank_account",
        "value": account.get("balance", 0.0),
        "currency": account.get("currency", "USD").upper(),
        "acquisition_date": None,
        "notes": None,
        "metadata": {
            "bank_name": bank_name,
            "account_type": account_type,
        },
    }


def migrate_user_data(user_id: str, force: bool = False) -> dict:
    """
    Migrate user's banks data to patrimoine format.

    Args:
        user_id: User identifier
        force: If True, re-migrate even if patrimoine.json already exists

    Returns:
        Migration result dict with status and counts

    Migration strategy:
        1. Check if patrimoine.json already exists (skip unless force=True)
        2. Load banks/snapshot.json if exists
        3. Transform accounts → patrimoine items (category=liquidity, type=bank_account)
        4. Write to wealth/patrimoine.json
        5. Keep original banks/snapshot.json (read-only, no deletion)
    """
    banks_path = _get_banks_path(user_id)
    patrimoine_path = _get_patrimoine_path(user_id)

    # Check if already migrated
    if patrimoine_path.exists() and not force:
        logger.info(f"[migration] patrimoine.json already exists for user={user_id}, skipping")
        return {
            "status": "skipped",
            "reason": "already_migrated",
            "user_id": user_id,
        }

    # Check if legacy data exists
    if not banks_path.exists():
        logger.info(f"[migration] no banks data found for user={user_id}, creating empty patrimoine")
        patrimoine_path.parent.mkdir(parents=True, exist_ok=True)
        patrimoine_path.write_text(json.dumps({"items": []}, indent=2), encoding="utf-8")
        return {
            "status": "success",
            "reason": "no_legacy_data",
            "user_id": user_id,
            "migrated_count": 0,
        }

    # Load legacy data
    try:
        with banks_path.open("r", encoding="utf-8") as f:
            banks_data = json.load(f)
    except Exception as exc:
        logger.error(f"[migration] failed to load banks data for user={user_id}: {exc}")
        return {
            "status": "error",
            "reason": "load_failed",
            "user_id": user_id,
            "error": str(exc),
        }

    # Transform accounts
    legacy_accounts = banks_data.get("accounts", [])
    migrated_items = [_migrate_account_to_item(acc) for acc in legacy_accounts]

    # Write new format
    try:
        patrimoine_path.parent.mkdir(parents=True, exist_ok=True)
        with patrimoine_path.open("w", encoding="utf-8") as f:
            json.dump({"items": migrated_items}, f, indent=2, ensure_ascii=False)
        logger.info(
            f"[migration] migrated {len(migrated_items)} accounts to patrimoine for user={user_id}"
        )
        return {
            "status": "success",
            "reason": "migrated",
            "user_id": user_id,
            "migrated_count": len(migrated_items),
        }
    except Exception as exc:
        logger.error(f"[migration] failed to write patrimoine data for user={user_id}: {exc}")
        return {
            "status": "error",
            "reason": "write_failed",
            "user_id": user_id,
            "error": str(exc),
        }


def migrate_all_users(force: bool = False) -> list[dict]:
    """
    Migrate all users found in data/users/.

    Args:
        force: If True, re-migrate all users even if already migrated

    Returns:
        List of migration results for each user
    """
    users_dir = Path("data/users")
    if not users_dir.exists():
        logger.warning("[migration] data/users directory not found")
        return []

    results = []
    for user_dir in users_dir.iterdir():
        if user_dir.is_dir():
            user_id = user_dir.name
            result = migrate_user_data(user_id, force=force)
            results.append(result)

    logger.info(
        f"[migration] completed migration for {len(results)} users: "
        f"{sum(1 for r in results if r['status'] == 'success')} success, "
        f"{sum(1 for r in results if r['status'] == 'error')} errors"
    )
    return results
