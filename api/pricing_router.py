"""
Pricing Router - Pricing Diagnostic Endpoints
Extracted from api/main.py for better organization
"""
import os
import logging
from typing import Dict
from fastapi import APIRouter, Query

logger = logging.getLogger("crypto-rebalancer")

router = APIRouter(tags=["pricing"])


@router.get(
    "/pricing/diagnostic",
    summary="Pricing diagnostic (local vs market)",
)
async def pricing_diagnostic(
    source: str = Query("cointracking", description="Source des balances (cointracking|stub|cointracking_api)"),
    min_usd: float = Query(1.0, description="Seuil minimum en USD pour filtrer les lignes"),
    mode: str = Query("auto", description="Mode pricing à diagnostiquer: local|auto"),
    limit: int = Query(50, ge=1, le=500, description="Nombre max de symboles à analyser")
):
    """Diagnostique la source de prix retenue par symbole selon la logique actuelle.

    Retourne, pour chaque symbole présent dans les holdings filtrés:
      - local_price
      - market_price
      - effective_price (selon la logique 'auto' actuelle assimilée à 'hybrid')
      - price_source (local|market)
    """
    # Import des helpers depuis price_enricher (évite dépendance circulaire)
    from api.services.price_enricher import get_data_age_minutes

    try:
        # Récupérer holdings unifiés avec filtrage homogène
        from api.unified_data import get_unified_filtered_balances
        unified = await get_unified_filtered_balances(source=source, min_usd=min_usd)
        rows = unified.get("items", [])
        source_used = unified.get("source_used", source)

        # Construire local price map (comme dans enrichissement)
        local_price_map: Dict[str, float] = {}
        for row in rows:
            sym = (row.get("symbol") or "").upper()
            if not sym:
                continue
            value_usd = float(row.get("value_usd") or 0.0)
            amount = float(row.get("amount") or 0.0)
            if value_usd > 0 and amount > 0:
                local_price_map[sym] = value_usd / amount

        # Choisir les symboles à diagnostiquer: top par valeur
        # Si 'value_usd' absent, on prend l'ordre existant et tronque à 'limit'
        symbols_sorted = sorted(
            [( (r.get("symbol") or "").upper(), float(r.get("value_usd") or 0.0)) for r in rows if r.get("symbol") ],
            key=lambda x: x[1], reverse=True
        )
        symbols = [s for s, _ in symbols_sorted[:limit]]
        symbols = list(dict.fromkeys(symbols))  # dédupe en gardant l'ordre

        # Fetch prix marché (async) quand nécessaire
        market_price_map: Dict[str, float] = {}
        if symbols:
            try:
                from services.pricing import aget_prices_usd
                market_price_map = await aget_prices_usd(symbols)
            except ImportError as e:
                logger.debug(f"Async pricing not available, falling back to sync: {e}")
                from services.pricing import get_prices_usd
                market_price_map = get_prices_usd(symbols)
            except Exception as e:
                logger.warning(f"Price fetch failed, using empty prices: {e}")
                market_price_map = {}

        # Décision effective (même logique que 'auto' => hybride)
        max_age_min = float(os.getenv("PRICE_HYBRID_MAX_AGE_MIN", "30"))
        data_age_min = get_data_age_minutes(source_used)
        needs_market_correction = data_age_min > max_age_min

        results = []
        for sym in symbols:
            local_p = local_price_map.get(sym)
            market_p = market_price_map.get(sym)

            if mode == "local":
                effective = local_p
                src = "local" if effective is not None else None
            else:
                # auto -> logique hybride: préférer local si frais et existant
                if needs_market_correction or (sym not in local_price_map):
                    effective = market_p if market_p else local_p
                    src = "market" if (market_p and (needs_market_correction or sym not in local_price_map)) else ("local" if local_p else None)
                else:
                    effective = local_p if local_p else market_p
                    src = "local" if local_p else ("market" if market_p else None)

            results.append({
                "symbol": sym,
                "local_price": local_p,
                "market_price": market_p,
                "effective_price": effective,
                "price_source": src
            })

        return {
            "ok": True,
            "mode": mode,
            "pricing_internal_mode": ("hybrid" if mode == "auto" else mode),
            "meta": {
                "source_used": source_used,
                "items_considered": len(rows),
                "symbols_analyzed": len(symbols),
                "data_age_min": data_age_min,
                "max_age_min": max_age_min,
            },
            "items": results
        }

    except Exception as e:
        # Import PricingException uniquement si disponible
        try:
            from api.exceptions import PricingException
            if isinstance(e, PricingException):
                logger.error(f"Pricing error in diagnostics: {e}")
                return {"ok": False, "error": f"Pricing error: {e.message}", "error_code": e.error_code.value if e.error_code else None}
        except ImportError:
            pass

        logger.error(f"Unexpected error in pricing diagnostics: {e}")
        return {"ok": False, "error": f"Diagnostic failed: {str(e)}"}


@router.get(
    "/api/pricing/diagnostic",
    summary="Pricing diagnostic (alias)",
)
async def pricing_diagnostic_alias(
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0),
    mode: str = Query("auto"),
    limit: int = Query(50, ge=1, le=500)
):
    """Alias endpoint for pricing diagnostic (compatibility)"""
    return await pricing_diagnostic(source=source, min_usd=min_usd, mode=mode, limit=limit)
