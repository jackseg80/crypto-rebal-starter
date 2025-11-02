"""Patrimoine service - CRUD operations for unified wealth items - Multi-tenant."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from models.wealth import PatrimoineItemInput, PatrimoineItemOutput
from services.fx_service import convert as fx_convert
from services.wealth.patrimoine_migration import migrate_user_data

logger = logging.getLogger(__name__)


def _get_storage_path(user_id: str) -> Path:
    """Return user-specific storage path for patrimoine data."""
    return Path(f"data/users/{user_id}/wealth/patrimoine.json")


def _ensure_storage(user_id: str) -> None:
    """Ensure storage directory and file exist for user."""
    path = _get_storage_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Try migration first
        logger.info(f"[patrimoine] storage not found for user={user_id}, attempting migration")
        migrate_user_data(user_id)
        # If still doesn't exist, create empty
        if not path.exists():
            path.write_text(json.dumps({"items": []}), encoding="utf-8")


def _load_snapshot(user_id: str) -> dict:
    """Load patrimoine snapshot for specific user."""
    _ensure_storage(user_id)
    path = _get_storage_path(user_id)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                data.setdefault("items", [])
                return data
    except Exception as exc:
        logger.warning(f"[patrimoine] failed to load snapshot for user={user_id}: {exc}")
    return {"items": []}


def _save_snapshot(data: dict, user_id: str) -> None:
    """Save patrimoine snapshot for specific user (atomic write)."""
    _ensure_storage(user_id)
    path = _get_storage_path(user_id)

    # Atomic write: write to temp file, then rename
    temp_path = path.with_suffix(".tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        temp_path.replace(path)
        logger.info(
            f"[patrimoine] snapshot saved for user={user_id} with {len(data.get('items', []))} items"
        )
    except Exception as exc:
        logger.error(f"[patrimoine] failed to save snapshot for user={user_id}: {exc}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def list_items(
    user_id: str,
    category: Optional[str] = None,
    type: Optional[str] = None,
) -> List[PatrimoineItemOutput]:
    """
    List patrimoine items for user with optional filters.

    Args:
        user_id: User identifier
        category: Optional category filter (liquidity, tangible, liability, insurance)
        type: Optional type filter (bank_account, real_estate, etc.)

    Returns:
        List of PatrimoineItemOutput with USD conversions
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    # Apply filters
    if category:
        items = [item for item in items if item.get("category") == category]
    if type:
        items = [item for item in items if item.get("type") == type]

    # Build output with USD conversions
    result = []
    for item in items:
        value = item.get("value", 0)
        currency = item.get("currency", "USD").upper()
        value_usd = fx_convert(value, currency, "USD")

        result.append(
            PatrimoineItemOutput(
                id=item.get("id"),
                name=item.get("name"),
                category=item.get("category"),
                type=item.get("type"),
                value=value,
                currency=currency,
                value_usd=value_usd,
                acquisition_date=item.get("acquisition_date"),
                notes=item.get("notes"),
                metadata=item.get("metadata", {}),
            )
        )

    logger.info(
        f"[patrimoine] listed {len(result)} items for user={user_id} (category={category}, type={type})"
    )
    return result


def get_item(user_id: str, item_id: str) -> Optional[PatrimoineItemOutput]:
    """
    Get a specific patrimoine item by ID.

    Args:
        user_id: User identifier
        item_id: Item identifier

    Returns:
        PatrimoineItemOutput or None if not found
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    for item in items:
        if item.get("id") == item_id:
            value = item.get("value", 0)
            currency = item.get("currency", "USD").upper()
            value_usd = fx_convert(value, currency, "USD")

            return PatrimoineItemOutput(
                id=item.get("id"),
                name=item.get("name"),
                category=item.get("category"),
                type=item.get("type"),
                value=value,
                currency=currency,
                value_usd=value_usd,
                acquisition_date=item.get("acquisition_date"),
                notes=item.get("notes"),
                metadata=item.get("metadata", {}),
            )

    logger.warning(f"[patrimoine] item not found id={item_id} user={user_id}")
    return None


def create_item(user_id: str, item: PatrimoineItemInput) -> PatrimoineItemOutput:
    """
    Create a new patrimoine item for user.

    Args:
        user_id: User identifier
        item: Item data to create

    Returns:
        PatrimoineItemOutput with generated ID and USD conversion
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    # Generate unique ID
    item_id = str(uuid.uuid4())

    # Create new item dict
    new_item = {
        "id": item_id,
        "name": item.name,
        "category": item.category,
        "type": item.type,
        "value": item.value,
        "currency": item.currency.upper(),
        "acquisition_date": item.acquisition_date,
        "notes": item.notes,
        "metadata": item.metadata or {},
    }

    # Append and save
    items.append(new_item)
    _save_snapshot({"items": items}, user_id)

    # Calculate USD value for response
    value_usd = fx_convert(item.value, item.currency.upper(), "USD")

    logger.info(
        f"[patrimoine] item created id={item_id} user={user_id} category={item.category} type={item.type}"
    )

    return PatrimoineItemOutput(
        id=item_id,
        name=item.name,
        category=item.category,
        type=item.type,
        value=item.value,
        currency=item.currency.upper(),
        value_usd=value_usd,
        acquisition_date=item.acquisition_date,
        notes=item.notes,
        metadata=item.metadata or {},
    )


def update_item(user_id: str, item_id: str, item: PatrimoineItemInput) -> Optional[PatrimoineItemOutput]:
    """
    Update an existing patrimoine item.

    Args:
        user_id: User identifier
        item_id: Item ID to update
        item: Updated item data

    Returns:
        Updated PatrimoineItemOutput or None if not found
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    # Find and update item
    found = False
    for i, existing_item in enumerate(items):
        if existing_item.get("id") == item_id:
            items[i] = {
                "id": item_id,
                "name": item.name,
                "category": item.category,
                "type": item.type,
                "value": item.value,
                "currency": item.currency.upper(),
                "acquisition_date": item.acquisition_date,
                "notes": item.notes,
                "metadata": item.metadata or {},
            }
            found = True
            break

    if not found:
        logger.warning(f"[patrimoine] item not found for update id={item_id} user={user_id}")
        return None

    # Save updated snapshot
    _save_snapshot({"items": items}, user_id)

    # Calculate USD value for response
    value_usd = fx_convert(item.value, item.currency.upper(), "USD")

    logger.info(f"[patrimoine] item updated id={item_id} user={user_id}")

    return PatrimoineItemOutput(
        id=item_id,
        name=item.name,
        category=item.category,
        type=item.type,
        value=item.value,
        currency=item.currency.upper(),
        value_usd=value_usd,
        acquisition_date=item.acquisition_date,
        notes=item.notes,
        metadata=item.metadata or {},
    )


def delete_item(user_id: str, item_id: str) -> bool:
    """
    Delete a patrimoine item.

    Args:
        user_id: User identifier
        item_id: Item ID to delete

    Returns:
        True if deleted, False if not found
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    # Filter out item to delete
    initial_count = len(items)
    filtered_items = [item for item in items if item.get("id") != item_id]

    if len(filtered_items) == initial_count:
        logger.warning(f"[patrimoine] item not found for deletion id={item_id} user={user_id}")
        return False

    # Save updated snapshot
    _save_snapshot({"items": filtered_items}, user_id)

    logger.info(f"[patrimoine] item deleted id={item_id} user={user_id}")
    return True


def get_summary(user_id: str) -> dict:
    """
    Get patrimoine summary for user.

    Returns breakdown by category with total values in USD.

    Args:
        user_id: User identifier

    Returns:
        Dict with total_net_worth, breakdown by category, and counts
    """
    snapshot = _load_snapshot(user_id)
    items = snapshot.get("items", [])

    breakdown = {
        "liquidity": 0.0,
        "tangible": 0.0,
        "liability": 0.0,
        "insurance": 0.0,
    }

    counts = {
        "liquidity": 0,
        "tangible": 0,
        "liability": 0,
        "insurance": 0,
    }

    for item in items:
        category = item.get("category", "liquidity")
        value = item.get("value", 0)
        currency = item.get("currency", "USD").upper()
        value_usd = fx_convert(value, currency, "USD")

        breakdown[category] += value_usd
        counts[category] += 1

    total_assets = breakdown["liquidity"] + breakdown["tangible"] + breakdown["insurance"]
    total_liabilities = abs(breakdown["liability"])
    net_worth = total_assets - total_liabilities

    logger.info(f"[patrimoine] summary generated for user={user_id} net_worth={net_worth:.2f} USD")

    return {
        "net_worth": net_worth,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "breakdown": breakdown,
        "counts": counts,
        "user_id": user_id,
    }
