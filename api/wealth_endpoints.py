"""Wealth namespace endpoints unifying holdings across providers."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Depends

from adapters import banks_adapter, crypto_adapter, saxo_adapter
from api.deps import get_active_user
from models.wealth import (
    AccountModel,
    InstrumentModel,
    PositionModel,
    TransactionModel,
    PricePoint,
    ProposedTrade,
    BankAccountInput,
    BankAccountOutput,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wealth", tags=["Wealth"])
_SUPPORTED_MODULES = {"crypto", "saxo", "banks"}


async def _module_available(module: str, user_id: Optional[str] = None) -> bool:
    """Vérifie si un module wealth a des données disponibles pour l'utilisateur."""
    try:
        if module == "crypto":
            return await crypto_adapter.has_data(user_id)
        if module == "saxo":
            return await saxo_adapter.has_data(user_id)
        if module == "banks":
            return await banks_adapter.has_data(user_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("[wealth] availability probe failed for %s: %s", module, exc)
        return False
    return False


def _ensure_module(module: str) -> None:
    if module not in _SUPPORTED_MODULES:
        raise HTTPException(status_code=404, detail="unknown_module")


# ===== Banks CRUD Endpoints (MUST be before generic /{module} routes) =====


@router.get("/banks/accounts", response_model=list[BankAccountOutput])
async def list_bank_accounts(
    user: str = Depends(get_active_user)
) -> list[BankAccountOutput]:
    """
    List all bank accounts for user with balance_usd calculated.

    Args:
        user: Active user ID (injected via Depends)

    Returns:
        List of BankAccountOutput with USD conversions
    """
    from services.fx_service import convert as fx_convert

    # Load snapshot
    snapshot = banks_adapter.load_snapshot(user)
    accounts = snapshot.get("accounts", [])

    # Build output with USD conversions
    result = []
    for account in accounts:
        balance = account.get("balance", 0)
        currency = account.get("currency", "USD").upper()
        balance_usd = fx_convert(balance, currency, "USD")

        result.append(BankAccountOutput(
            id=account.get("id"),
            bank_name=account.get("bank_name"),
            account_type=account.get("account_type"),
            balance=balance,
            currency=currency,
            balance_usd=balance_usd
        ))

    logger.info("[wealth][banks] listed %s accounts for user=%s", len(result), user)
    return result


@router.post("/banks/accounts", response_model=BankAccountOutput, status_code=201)
async def create_bank_account(
    account: BankAccountInput,
    user: str = Depends(get_active_user)
) -> BankAccountOutput:
    """
    Create a new bank account for the user.

    Args:
        account: Bank account data (bank_name, account_type, balance, currency)
        user: Active user ID (injected via Depends)

    Returns:
        BankAccountOutput with generated ID and USD conversion

    Example:
        POST /api/wealth/banks/accounts
        {
            "bank_name": "UBS",
            "account_type": "current",
            "balance": 5000.0,
            "currency": "CHF"
        }
    """
    import uuid
    from services.fx_service import convert as fx_convert

    # Load current snapshot
    snapshot = banks_adapter.load_snapshot(user)
    accounts = snapshot.get("accounts", [])

    # Generate unique ID
    account_id = str(uuid.uuid4())

    # Create new account dict
    new_account = {
        "id": account_id,
        "bank_name": account.bank_name,
        "account_type": account.account_type,
        "balance": account.balance,
        "currency": account.currency.upper(),
    }

    # Append and save
    accounts.append(new_account)
    banks_adapter.save_snapshot({"accounts": accounts}, user)

    # Calculate USD value for response
    balance_usd = fx_convert(account.balance, account.currency.upper(), "USD")

    logger.info(
        "[wealth][banks] account created id=%s user=%s bank=%s",
        account_id,
        user,
        account.bank_name
    )

    return BankAccountOutput(
        id=account_id,
        bank_name=account.bank_name,
        account_type=account.account_type,
        balance=account.balance,
        currency=account.currency.upper(),
        balance_usd=balance_usd,
    )


@router.put("/banks/accounts/{account_id}", response_model=BankAccountOutput)
async def update_bank_account(
    account_id: str,
    account: BankAccountInput,
    user: str = Depends(get_active_user)
) -> BankAccountOutput:
    """
    Update an existing bank account.

    Args:
        account_id: Account ID to update
        account: Updated account data
        user: Active user ID (injected via Depends)

    Returns:
        Updated BankAccountOutput

    Raises:
        HTTPException 404 if account not found
    """
    from services.fx_service import convert as fx_convert

    # Load current snapshot
    snapshot = banks_adapter.load_snapshot(user)
    accounts = snapshot.get("accounts", [])

    # Find and update account
    found = False
    for i, acc in enumerate(accounts):
        if acc.get("id") == account_id:
            accounts[i] = {
                "id": account_id,
                "bank_name": account.bank_name,
                "account_type": account.account_type,
                "balance": account.balance,
                "currency": account.currency.upper(),
            }
            found = True
            break

    if not found:
        logger.warning("[wealth][banks] account not found id=%s user=%s", account_id, user)
        raise HTTPException(status_code=404, detail="account_not_found")

    # Save updated snapshot
    banks_adapter.save_snapshot({"accounts": accounts}, user)

    # Calculate USD value for response
    balance_usd = fx_convert(account.balance, account.currency.upper(), "USD")

    logger.info(
        "[wealth][banks] account updated id=%s user=%s bank=%s",
        account_id,
        user,
        account.bank_name
    )

    return BankAccountOutput(
        id=account_id,
        bank_name=account.bank_name,
        account_type=account.account_type,
        balance=account.balance,
        currency=account.currency.upper(),
        balance_usd=balance_usd,
    )


@router.delete("/banks/accounts/{account_id}", status_code=204)
async def delete_bank_account(
    account_id: str,
    user: str = Depends(get_active_user)
):
    """
    Delete a bank account.

    Args:
        account_id: Account ID to delete
        user: Active user ID (injected via Depends)

    Returns:
        204 No Content on success

    Raises:
        HTTPException 404 if account not found
    """
    # Load current snapshot
    snapshot = banks_adapter.load_snapshot(user)
    accounts = snapshot.get("accounts", [])

    # Filter out account to delete
    initial_count = len(accounts)
    filtered_accounts = [acc for acc in accounts if acc.get("id") != account_id]

    if len(filtered_accounts) == initial_count:
        logger.warning("[wealth][banks] account not found for deletion id=%s user=%s", account_id, user)
        raise HTTPException(status_code=404, detail="account_not_found")

    # Save updated snapshot
    banks_adapter.save_snapshot({"accounts": filtered_accounts}, user)

    logger.info("[wealth][banks] account deleted id=%s user=%s", account_id, user)


# ===== Generic Wealth Endpoints =====


@router.get("/modules", response_model=List[str])
async def list_modules(user: str = Depends(get_active_user)) -> List[str]:
    """Liste les modules wealth disponibles pour l'utilisateur."""
    discovered = []
    for module in _SUPPORTED_MODULES:
        if await _module_available(module, user):
            discovered.append(module)
    if not discovered:
        discovered = sorted(_SUPPORTED_MODULES)
    logger.info("[wealth] modules_available=%s for user=%s", discovered, user)
    return discovered


@router.get("/{module}/accounts", response_model=List[AccountModel])
async def get_accounts(
    module: str,
    user: str = Depends(get_active_user),
    source: str = Query("auto", description="Crypto source resolver"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
) -> List[AccountModel]:
    """Liste les comptes pour un module (lecture seule depuis sources)."""
    _ensure_module(module)

    # Vérifier que l'utilisateur a des données pour ce module
    if not await _module_available(module, user):
        logger.warning("[wealth] no data available for module=%s user=%s", module, user)
        return []

    if module == "crypto":
        accounts = await crypto_adapter.list_accounts(user_id=user, source=source)
    elif module == "saxo":
        accounts = await saxo_adapter.list_accounts(user_id=user, file_key=file_key)
    else:
        accounts = await banks_adapter.list_accounts(user_id=user)

    logger.info("[wealth] served %s accounts for module=%s user=%s", len(accounts), module, user)
    return accounts


@router.get("/{module}/instruments", response_model=List[InstrumentModel])
async def get_instruments(
    module: str,
    user: str = Depends(get_active_user),
    source: str = Query("auto"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
) -> List[InstrumentModel]:
    _ensure_module(module)
    if module == "crypto":
        instruments = await crypto_adapter.list_instruments(user_id=user, source=source)
    elif module == "saxo":
        instruments = await saxo_adapter.list_instruments(user_id=user, file_key=file_key)
    else:
        instruments = await banks_adapter.list_instruments(user_id=user)
    logger.info("[wealth] served %s instruments for module=%s", len(instruments), module)
    return instruments


@router.get("/{module}/positions", response_model=List[PositionModel])
async def get_positions(
    module: str,
    user: str = Depends(get_active_user),
    source: str = Query("auto"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
    min_usd_threshold: float = Query(1.0, description="Minimum USD value to filter dust assets"),
    asof: Optional[str] = Query(None, description="Date override (yyyy-mm-dd)")
) -> List[PositionModel]:
    _ensure_module(module)
    if module == "crypto":
        positions = await crypto_adapter.list_positions(user_id=user, source=source, min_usd_threshold=min_usd_threshold)
    elif module == "saxo":
        positions = await saxo_adapter.list_positions(user_id=user, file_key=file_key)
    else:
        positions = await banks_adapter.list_positions(user_id=user)
    logger.info("[wealth] served %s positions for module=%s asof=%s", len(positions), module, asof or "latest")
    return positions


@router.get("/{module}/transactions", response_model=List[TransactionModel])
async def get_transactions(
    module: str,
    user: str = Depends(get_active_user),
    source: str = Query("auto"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
    start: Optional[str] = Query(None, alias="from"),
    end: Optional[str] = Query(None, alias="to"),
) -> List[TransactionModel]:
    _ensure_module(module)
    if module == "crypto":
        transactions = await crypto_adapter.list_transactions(user_id=user, source=source, start=start, end=end)
    elif module == "saxo":
        transactions = await saxo_adapter.list_transactions(user_id=user, file_key=file_key, start=start, end=end)
    else:
        transactions = await banks_adapter.list_transactions(start=start, end=end, user_id=user)
    logger.info(
        "[wealth] served %s transactions for module=%s window=%s/%s",
        len(transactions),
        module,
        start or "*",
        end or "*",
    )
    return transactions


@router.get("/{module}/prices", response_model=List[PricePoint])
async def get_prices(
    module: str,
    ids: List[str] = Query(..., description="Instrument identifiers"),
    granularity: str = Query("daily", regex="^(daily|intraday)$"),
    user: str = Depends(get_active_user),
    source: str = Query("auto"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
) -> List[PricePoint]:
    _ensure_module(module)
    if not ids:
        raise HTTPException(status_code=400, detail="missing_ids")
    if module == "crypto":
        prices = await crypto_adapter.get_prices(ids, granularity=granularity)
    elif module == "saxo":
        prices = await saxo_adapter.get_prices(ids, granularity=granularity, user_id=user, file_key=file_key)
    else:
        prices = await banks_adapter.get_prices(ids, granularity=granularity, user_id=user)
    logger.info("[wealth] served %s price points for module=%s", len(prices), module)
    return prices


@router.post("/{module}/rebalance/preview", response_model=List[ProposedTrade])
async def preview_rebalance(
    module: str,
    payload: Optional[dict] = Body(default=None, description="Module-specific preview payload"),
    user: str = Depends(get_active_user),
    source: str = Query("auto"),
    file_key: Optional[str] = Query(None, description="Specific file to load (for Saxo)"),
) -> List[ProposedTrade]:
    _ensure_module(module)
    if module == "crypto":
        trades = await crypto_adapter.preview_rebalance(user_id=user, source=source)
    elif module == "saxo":
        trades = await saxo_adapter.preview_rebalance(user_id=user, file_key=file_key)
    else:
        trades = await banks_adapter.preview_rebalance(user_id=user)
    logger.info(
        "[wealth] rebalance preview module=%s payload_keys=%s returned=%s",
        module,
        sorted(list(payload.keys())) if payload else [],
        len(trades),
    )
    return trades


@router.get("/global/summary")
async def global_summary(
    user: str = Depends(get_active_user),
    source: str = Query("auto", description="Crypto source resolver"),
    min_usd_threshold: float = Query(1.0, description="Minimum USD value to filter dust assets"),
    bourse_file_key: Optional[str] = Query(None, description="Bourse file key for specific CSV selection")
) -> dict:
    """
    Agrégation globale de tous les modules wealth (crypto + saxo + banks).

    Retourne un summary unifié avec total_value_usd et breakdown par module.

    Args:
        user: ID utilisateur (from authenticated context)
        source: Source resolver pour crypto
        bourse_file_key: Optional file key for specific Bourse CSV selection

    Returns:
        Dict avec total_value_usd, breakdown, et metadata

    Example:
        GET /api/wealth/global/summary?source=auto&bourse_file_key=saxo_25-09-2025.csv
        {
            "total_value_usd": 556100.0,
            "breakdown": {
                "crypto": 133100.0,
                "saxo": 423000.0,
                "banks": 0.0
            },
            "user_id": "jack",
            "timestamp": "2025-10-12T..."
        }
    """
    from datetime import datetime

    breakdown = {
        "crypto": 0.0,
        "saxo": 0.0,
        "banks": 0.0
    }

    # 1) Crypto
    try:
        logger.info(f"[wealth][global] 🔍 Checking Crypto availability for user={user}")
        crypto_available = await _module_available("crypto", user)
        logger.info(f"[wealth][global] 💰 Crypto available: {crypto_available}")

        if crypto_available:
            logger.info(f"[wealth][global] 📂 Loading Crypto positions with source={source}")
            crypto_positions = await crypto_adapter.list_positions(user_id=user, source=source, min_usd_threshold=min_usd_threshold)
            logger.info(f"[wealth][global] 📋 Got {len(crypto_positions)} Crypto positions")
            breakdown["crypto"] = sum((p.market_value or 0.0) for p in crypto_positions)
            logger.info(f"[wealth][global] ✅ crypto={breakdown['crypto']:.2f} USD for user={user} (threshold={min_usd_threshold})")
        else:
            logger.warning(f"[wealth][global] ⚠️ Crypto module not available for user={user}")
    except Exception as e:
        logger.error(f"[wealth][global] ❌ crypto failed for user={user}: {e}", exc_info=True)

    # 2) Saxo (with file_key support)
    try:
        logger.info(f"[wealth][global] 🔍 Checking Saxo availability for user={user}")
        saxo_available = await _module_available("saxo", user)
        logger.info(f"[wealth][global] 📊 Saxo available: {saxo_available}")

        if saxo_available:
            logger.info(f"[wealth][global] 📂 Loading Saxo positions with file_key={bourse_file_key}")
            saxo_positions = await saxo_adapter.list_positions(user_id=user, file_key=bourse_file_key)
            logger.info(f"[wealth][global] 📋 Got {len(saxo_positions)} Saxo positions")
            breakdown["saxo"] = sum((p.market_value or 0.0) for p in saxo_positions)
            logger.info(f"[wealth][global] ✅ saxo={breakdown['saxo']:.2f} USD for user={user} file_key={bourse_file_key}")
        else:
            logger.warning(f"[wealth][global] ⚠️ Saxo module not available for user={user}")
    except Exception as e:
        logger.error(f"[wealth][global] ❌ saxo failed for user={user}: {e}", exc_info=True)

    # 3) Banks
    try:
        if await _module_available("banks", user):
            banks_positions = await banks_adapter.list_positions(user_id=user)
            breakdown["banks"] = sum((p.market_value or 0.0) for p in banks_positions)
            logger.info(f"[wealth][global] banks={breakdown['banks']:.2f} USD for user={user}")
    except Exception as e:
        logger.warning(f"[wealth][global] banks failed for user={user}: {e}")

    total_value_usd = sum(breakdown.values())

    return {
        "total_value_usd": total_value_usd,
        "breakdown": breakdown,
        "user_id": user,
        "timestamp": datetime.utcnow().isoformat(),
    }
