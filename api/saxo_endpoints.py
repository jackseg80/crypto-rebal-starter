"""Legacy Saxo endpoints delegating to Wealth namespace for compatibility."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile

from adapters.saxo_adapter import ingest_file, get_portfolio_detail, list_portfolios_overview
from api.deps import get_active_user
from connectors.saxo_import import SaxoImportConnector
from api.wealth_endpoints import (
    get_accounts as wealth_get_accounts,
    get_instruments as wealth_get_instruments,
    get_positions as wealth_get_positions,
    get_transactions as wealth_get_transactions,
    get_prices as wealth_get_prices,
    preview_rebalance as wealth_preview_rebalance,
)
from models.wealth import AccountModel, InstrumentModel, PositionModel, PricePoint, ProposedTrade, TransactionModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saxo", tags=["Saxo Bank"])

_MODULE = "saxo"


def _legacy_log(path: str) -> None:
    logger.info("[legacy-compat] %s -> /api/wealth/%s%s", path, _MODULE, path)


@router.post("/validate")
async def validate_portfolio(file: UploadFile = File(..., description="Saxo export file")) -> dict:
    """Validate Saxo payload before ingestion"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_file")

    suffix = Path(file.filename).suffix or ".csv"
    connector = SaxoImportConnector()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        result = connector.validate_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "valid": bool(result.get("valid")),
        "error": result.get("error"),
        "rows": result.get("rows"),
        "columns": result.get("columns", []),
        "required_columns": connector.required_columns,
    }


@router.post("/import")
async def import_portfolio(
    file: UploadFile = File(..., description="Saxo export file"),
    portfolio_name: str = Form("Saxo Portfolio"),
) -> dict:
    """Import Saxo CSV/XLSX and persist through the wealth adapter."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing_file")

    suffix = Path(file.filename).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)
    try:
        ingestion = ingest_file(str(tmp_path), portfolio_name=portfolio_name)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not ingestion or not ingestion.get('portfolio'):
        raise HTTPException(status_code=422, detail="import_failed")

    portfolio = ingestion['portfolio']
    summary = ingestion.get('summary') or {}
    errors = ingestion.get('errors') or []

    asset_allocation = summary.get('asset_allocation') or {}
    currency_exposure = summary.get('currency_exposure') or {}
    top_holdings = summary.get('top_holdings') or portfolio.get('positions', [])

    def _coerce_float(value: Optional[float]) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    top_payload = []
    for pos in top_holdings:
        instrument = pos.get('instrument') or pos.get('name') or pos.get('symbol')
        top_payload.append({
            'symbol': pos.get('symbol'),
            'instrument': instrument,
            'quantity': _coerce_float(pos.get('quantity')),
            'market_value_usd': _coerce_float(pos.get('market_value_usd') or pos.get('market_value')),
            'asset_class': pos.get('asset_class') or 'UNKNOWN',
        })
    top_payload = top_payload[:10]

    response = {
        'success': True,
        'portfolio_id': portfolio.get('portfolio_id'),
        'portfolio_name': portfolio.get('name'),
        'positions_count': len(portfolio.get('positions', [])),
        'total_value_usd': summary.get('total_value_usd', portfolio.get('total_value_usd', 0.0)),
        'asset_allocation': asset_allocation,
        'currency_exposure': currency_exposure,
        'top_holdings': top_payload,
        'errors': errors,
        'portfolio': portfolio,
        'summary': summary,
        'delegated': True,
    }

    _legacy_log('/import')
    return response


@router.get("/portfolios")
async def list_portfolios(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> dict:
    """Return lightweight overview of stored Saxo portfolios."""
    _legacy_log("/portfolios")
    portfolios = list_portfolios_overview(user_id=user, file_key=file_key)
    return {"portfolios": portfolios}


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> dict:
    """Return full detail for a given Saxo portfolio."""
    _legacy_log(f"/portfolios/{portfolio_id}")
    portfolio = get_portfolio_detail(portfolio_id, user_id=user, file_key=file_key)
    if not portfolio:
        raise HTTPException(status_code=404, detail="portfolio_not_found")
    return portfolio



@router.get("/accounts", response_model=List[AccountModel])
async def list_accounts(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> List[AccountModel]:
    _legacy_log("/accounts")
    return await wealth_get_accounts(module=_MODULE, user=user, file_key=file_key)


@router.get("/instruments", response_model=List[InstrumentModel])
async def list_instruments(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> List[InstrumentModel]:
    _legacy_log("/instruments")
    return await wealth_get_instruments(module=_MODULE, user=user, file_key=file_key)


@router.get("/positions")
async def list_positions(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    _legacy_log("/positions")
    wealth_positions = await wealth_get_positions(module=_MODULE, user=user, file_key=file_key)
    # wealth endpoint returns pydantic models; convert to plain dicts
    normalized = [p.model_dump() if isinstance(p, PositionModel) else p for p in wealth_positions]
    total = len(normalized)
    window = normalized[offset : offset + limit]
    return {
        "positions": window,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        },
    }


@router.get("/transactions", response_model=List[TransactionModel])
async def list_transactions(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load"),
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[TransactionModel]:
    _legacy_log("/transactions")
    return await wealth_get_transactions(module=_MODULE, user=user, file_key=file_key, start=start, end=end)


@router.get("/prices", response_model=List[PricePoint])
async def list_prices(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load"),
    ids: List[str] = Query(...),
    granularity: str = "daily"
) -> List[PricePoint]:
    if not ids:
        raise HTTPException(status_code=400, detail="missing_ids")
    _legacy_log("/prices")
    return await wealth_get_prices(module=_MODULE, user=user, file_key=file_key, ids=ids, granularity=granularity)


@router.post("/rebalance/preview", response_model=List[ProposedTrade])
async def preview_rebalance(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load"),
    payload: Optional[dict] = Body(default=None)
) -> List[ProposedTrade]:
    _legacy_log("/rebalance/preview")
    return await wealth_preview_rebalance(module=_MODULE, user=user, file_key=file_key, payload=payload)


# ==================== CASH / LIQUIDITIES MANAGEMENT ====================

@router.get("/cash")
async def get_portfolio_cash(
    user_id: str = Query(..., description="User ID"),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file identifier")
) -> dict:
    """
    Get saved cash/liquidities amount for a Saxo portfolio.

    Returns:
        {"cash_amount": float, "currency": "USD", "last_updated": "..."}
    """
    import json
    from datetime import datetime

    # Determine file identifier
    cash_key = file_key or "default"

    # Build cash file path
    cash_dir = Path(f"data/users/{user_id}/saxobank/cash")
    cash_file = cash_dir / f"{cash_key}_cash.json"

    if not cash_file.exists():
        # Return default 0 if no cash saved
        return {
            "cash_amount": 0.0,
            "currency": "USD",
            "last_updated": None
        }

    try:
        with open(cash_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return {
            "cash_amount": float(data.get("cash_amount", 0.0)),
            "currency": data.get("currency", "USD"),
            "last_updated": data.get("last_updated")
        }
    except Exception as e:
        logger.error(f"Failed to load cash amount for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load cash amount: {str(e)}")


@router.post("/cash")
async def save_portfolio_cash(
    user_id: str = Query(..., description="User ID"),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file identifier"),
    payload: dict = Body(..., description="Cash amount payload")
) -> dict:
    """
    Save cash/liquidities amount for a Saxo portfolio.

    Payload:
        {
            "cash_amount": float,
            "currency": str (optional, default: "USD")
        }
    """
    import json
    from datetime import datetime

    cash_amount = payload.get("cash_amount")
    if cash_amount is None:
        raise HTTPException(status_code=400, detail="cash_amount is required")

    try:
        cash_amount = float(cash_amount)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="cash_amount must be a number")

    if cash_amount < 0:
        raise HTTPException(status_code=400, detail="cash_amount cannot be negative")

    currency = payload.get("currency", "USD")

    # Determine file identifier
    cash_key = file_key or "default"

    # Build cash file path
    cash_dir = Path(f"data/users/{user_id}/saxobank/cash")
    cash_dir.mkdir(parents=True, exist_ok=True)

    cash_file = cash_dir / f"{cash_key}_cash.json"

    # Save cash amount with metadata
    data = {
        "cash_amount": cash_amount,
        "currency": currency,
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "file_key": cash_key
    }

    try:
        with open(cash_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Saved cash amount ${cash_amount} for user {user_id}, file_key={cash_key}")

        return {
            "success": True,
            "cash_amount": cash_amount,
            "currency": currency,
            "message": f"Cash amount saved successfully: ${cash_amount:,.2f}"
        }
    except Exception as e:
        logger.error(f"Failed to save cash amount for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save cash amount: {str(e)}")


# ==================== EXPORT LISTS ====================

@router.get("/export-lists")
async def export_saxo_lists(
    user: str = Depends(get_active_user),
    format: str = Query("json", regex="^(json|csv|markdown)$"),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
):
    """
    Export Saxo positions and sectors lists in multiple formats.

    Args:
        user: ID utilisateur (from authenticated context)
        format: Format de sortie (json, csv, markdown)
        file_key: Specific Saxo CSV file identifier

    Returns:
        Exported data in requested format with Content-Type header
    """
    try:
        from services.export_formatter import ExportFormatter
        from fastapi.responses import PlainTextResponse

        # 11 secteurs GICS standard
        GICS_SECTORS = [
            'Technology', 'Healthcare', 'Financials', 'Consumer Discretionary',
            'Communication Services', 'Industrials', 'Consumer Staples',
            'Energy', 'Utilities', 'Real Estate', 'Materials'
        ]

        # Sector mapping (from specialized_analytics.py)
        SECTOR_MAP = {
            # Tech
            'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
            'META': 'Technology', 'NVDA': 'Technology', 'TSLA': 'Technology', 'AMZN': 'Technology',
            'NFLX': 'Technology', 'AMD': 'Technology', 'INTC': 'Technology', 'CRM': 'Technology',
            'PLTR': 'Technology', 'COIN': 'Technology', 'CDR': 'Technology', 'IFX': 'Technology',
            # Financials
            'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials', 'GS': 'Financials',
            'MS': 'Financials', 'C': 'Financials', 'BLK': 'Financials', 'SCHW': 'Financials',
            'UBSG': 'Financials', 'BRKb': 'Financials', 'SLHn': 'Financials',
            # Healthcare
            'JNJ': 'Healthcare', 'UNH': 'Healthcare', 'PFE': 'Healthcare', 'ABBV': 'Healthcare',
            'TMO': 'Healthcare', 'ABT': 'Healthcare', 'LLY': 'Healthcare', 'MRK': 'Healthcare',
            'BAX': 'Healthcare', 'ROG': 'Healthcare',
            # Consumer
            'WMT': 'Consumer Staples', 'PG': 'Consumer Staples', 'KO': 'Consumer Staples',
            'PEP': 'Consumer Staples', 'MCD': 'Consumer Discretionary', 'NKE': 'Consumer Discretionary',
            'COST': 'Consumer Staples', 'SBUX': 'Consumer Discretionary', 'UHRN': 'Consumer Discretionary',
            # Energy
            'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'SLB': 'Energy',
            # Industrials
            'BA': 'Industrials', 'CAT': 'Industrials', 'GE': 'Industrials', 'MMM': 'Industrials',
        }

        def get_sector_from_symbol(symbol: str) -> str:
            """Extract ticker and map to GICS sector."""
            ticker = symbol.split(':')[0] if ':' in symbol else symbol
            return SECTOR_MAP.get(ticker, 'Unknown')

        # Récupérer les positions brutes depuis l'adapter (contient toutes les infos)
        from adapters import saxo_adapter

        # Accéder directement aux positions brutes avec toutes les métadonnées
        raw_positions = list(saxo_adapter._iter_positions(user_id=user, file_key=file_key))

        # Normaliser les positions
        positions_list = []
        sector_totals = {}
        total_portfolio_value = 0

        for pos in raw_positions:
            symbol = pos.get('symbol', '')
            instrument = pos.get('instrument', '') or pos.get('instrument_name', '')
            asset_class = pos.get('asset_class', 'Unknown')
            quantity = float(pos.get('quantity', 0))
            market_value = float(pos.get('market_value_usd', 0))
            currency = pos.get('currency', 'USD')

            # Get sector from mapping (extract ticker and map)
            sector = get_sector_from_symbol(symbol)

            entry_price = float(pos.get('avg_price', 0)) or float(pos.get('entry_price', 0))

            positions_list.append({
                'symbol': symbol,
                'instrument': instrument,
                'asset_class': asset_class,
                'quantity': quantity,
                'market_value': market_value,
                'currency': currency,
                'sector': sector,
                'entry_price': entry_price
            })

            # Calculer totaux par secteur
            if sector not in sector_totals:
                sector_totals[sector] = {'value_usd': 0, 'count': 0}
            sector_totals[sector]['value_usd'] += market_value
            sector_totals[sector]['count'] += 1

            total_portfolio_value += market_value

        # Construire la structure des secteurs (inclure tous les 11 secteurs GICS)
        sectors_list = []
        for sector_name in GICS_SECTORS:
            sector_data = sector_totals.get(sector_name, {'value_usd': 0, 'count': 0})
            value_usd = sector_data['value_usd']
            percentage = (value_usd / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

            sectors_list.append({
                'name': sector_name,
                'value_usd': value_usd,
                'percentage': percentage,
                'asset_count': sector_data['count']
            })

        # Ajouter les secteurs inconnus/autres
        for sector_name, sector_data in sector_totals.items():
            if sector_name not in GICS_SECTORS:
                value_usd = sector_data['value_usd']
                percentage = (value_usd / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

                sectors_list.append({
                    'name': sector_name,
                    'value_usd': value_usd,
                    'percentage': percentage,
                    'asset_count': sector_data['count']
                })

        # Structure finale
        export_data = {
            'positions': positions_list,
            'sectors': sectors_list,
            'summary': {
                'total_value_usd': total_portfolio_value,
                'positions_count': len(positions_list),
                'sectors_count': len(GICS_SECTORS)
            }
        }

        # Formater selon le format demandé
        formatter = ExportFormatter('saxo')

        if format == 'json':
            content = formatter.to_json(export_data)
            return PlainTextResponse(content, media_type="application/json")
        elif format == 'csv':
            content = formatter.to_csv(export_data)
            return PlainTextResponse(content, media_type="text/csv")
        elif format == 'markdown':
            content = formatter.to_markdown(export_data)
            return PlainTextResponse(content, media_type="text/markdown")

    except Exception as e:
        logger.exception("Error exporting Saxo lists")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

