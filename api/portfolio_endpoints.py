"""
Portfolio Analytics Endpoints
Extracted from api/main.py (Phase 2 refactoring)

Endpoints:
- GET /portfolio/metrics - Métriques portfolio + P&L
- POST /portfolio/snapshot - Sauvegarder snapshot historique
- GET /portfolio/trend - Données tendance graphiques
- GET /portfolio/alerts - Alertes dérive vs targets
"""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Dict, Any
import logging

from services.portfolio import PortfolioAnalytics
from api.deps import get_active_user
from api.utils.formatters import success_response, error_response

# Use BalanceService instead of importing from api.main to avoid circular dependency
# No TYPE_CHECKING needed anymore since we use the service directly

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Portfolio"])

# Shared instances
portfolio_analytics = PortfolioAnalytics()

# Configuration
COMPUTE_ON_STUB_SOURCES = False

# Helper to get resolve function dynamically
def _get_resolve_balances():
    """Dynamic import to avoid circular dependency"""
    from api.unified_data import get_unified_filtered_balances
    return get_unified_filtered_balances


def _to_rows(items):
    """Convert items to rows format for compatibility"""
    if not items:
        return []
    return [
        {
            "symbol": item.get("symbol", ""),
            "amount": item.get("amount", 0),
            "usd_value": item.get("value_usd", 0) or item.get("usd_value", 0),  # Support both formats
            "group": item.get("group", "Others")
        }
        for item in items
    ]


@router.get("/portfolio/metrics")
async def portfolio_metrics(
    user: str = Depends(get_active_user),
    source: str = Query("cointracking"),
    anchor: str = Query("prev_snapshot"),  # "midnight", "prev_snapshot", "prev_close"
    window: str = Query("24h"),  # "24h", "7d", "30d", "ytd"
    min_usd: float = Query(1.0)  # Default 1.0 to match dashboard behavior
):
    """
    Métriques calculées du portfolio avec P&L configurable.

    Args:
        user: ID utilisateur (from authenticated context)
        source: Source de données (cointracking, cointracking_api, saxobank, etc.)
        anchor: Type d'ancre pour P&L ("midnight", "prev_snapshot", "prev_close")
        window: Fenêtre temporelle ("24h", "7d", "30d", "ytd")
        min_usd: Seuil minimal USD (1.0 par défaut pour match dashboard)

    Returns:
        Métriques portfolio + performance vs ancre choisie
    """
    try:
        # Récupérer les données de balance actuelles avec le même seuil que le dashboard
        resolve_func = _get_resolve_balances()
        res = await resolve_func(source=source, user_id=user, min_usd=min_usd)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}

        # Do not compute on stub sources unless explicitly allowed
        if ((balances.get('source_used') or '').startswith('stub') or balances.get('source_used') == 'none') and not COMPUTE_ON_STUB_SOURCES:
            return error_response("No real data: stub source in use", code=400)

        # Calculer les métriques
        metrics = portfolio_analytics.calculate_portfolio_metrics(balances)
        performance = portfolio_analytics.calculate_performance_metrics(
            metrics,
            user_id=user,
            source=source,
            anchor=anchor,
            window=window
        )

        return success_response(
            data={"metrics": metrics, "performance": performance},
            meta={"source": source, "anchor": anchor, "window": window}
        )
    except Exception as e:
        logger.exception("Error calculating portfolio metrics")
        return error_response(str(e), code=500)


@router.post("/portfolio/snapshot")
async def save_portfolio_snapshot(
    user: str = Depends(get_active_user),
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0)  # Default 1.0 to match dashboard behavior
):
    """Sauvegarde un snapshot du portfolio pour suivi historique"""
    try:
        # Récupérer les données actuelles avec le même seuil que le dashboard
        resolve_func = _get_resolve_balances()
        res = await resolve_func(source=source, user_id=user, min_usd=min_usd)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}

        # Sauvegarder le snapshot
        saved = portfolio_analytics.save_portfolio_snapshot(balances, user_id=user, source=source)

        if saved:
            return success_response(
                data={"saved": True},
                meta={"user": user, "source": source, "message": "Snapshot sauvegardé"}
            )
        else:
            return error_response("Erreur lors de la sauvegarde", code=500)
    except Exception as e:
        logger.exception("Error saving portfolio snapshot")
        return error_response(str(e), code=500)


@router.get("/portfolio/trend")
async def portfolio_trend(days: int = Query(30, ge=1, le=365)):
    """Données de tendance du portfolio pour graphiques"""
    try:
        trend_data = portfolio_analytics.get_portfolio_trend(days)
        return success_response(data=trend_data, meta={"days": days})
    except Exception as e:
        logger.exception("Error getting portfolio trend")
        return error_response(str(e), code=500)


@router.get("/portfolio/alerts")
async def get_portfolio_alerts(
    user: str = Depends(get_active_user),
    source: str = Query("cointracking"),
    drift_threshold: float = Query(10.0)
):
    """
    Calcule les alertes de dérive du portfolio par rapport aux targets.

    Args:
        user: ID utilisateur (from authenticated context)
        source: Source de données (cointracking, cointracking_api, etc.)
        drift_threshold: Seuil de dérive en % pour déclencher alerte (défaut: 10%)

    Returns:
        Alertes avec niveaux (ok/warning/critical) et actions recommandées
    """
    try:
        # Récupérer les données de portfolio
        resolve_func = _get_resolve_balances()
        res = await resolve_func(source=source, user_id=user)
        rows = _to_rows(res.get("items", []))
        balances = {"source_used": res.get("source_used"), "items": rows}

        # Calculer les métriques actuelles
        metrics = portfolio_analytics.calculate_portfolio_metrics(balances)

        if not metrics.get("ok"):
            return error_response("Impossible de calculer les métriques", code=500)

        current_distribution = metrics["metrics"]["group_distribution"]
        total_value = metrics["metrics"]["total_value_usd"]

        # Targets par défaut (peuvent être dynamiques dans le futur)
        default_targets = {
            "BTC": 35,
            "ETH": 25,
            "Stablecoins": 10,
            "SOL": 10,
            "L1/L0 majors": 10,
            "Others": 10
        }

        # Calculer les déviations
        alerts = []
        max_drift = 0
        critical_count = 0
        warning_count = 0

        for group, target_pct in default_targets.items():
            current_value = current_distribution.get(group, 0)
            current_pct = (current_value / total_value * 100) if total_value > 0 else 0

            drift = abs(current_pct - target_pct)
            drift_direction = "over" if current_pct > target_pct else "under"

            # Déterminer le niveau d'alerte
            if drift > drift_threshold * 1.5:  # > 15% par défaut
                level = "critical"
                critical_count += 1
            elif drift > drift_threshold:  # > 10% par défaut
                level = "warning"
                warning_count += 1
            else:
                level = "ok"

            if drift > max_drift:
                max_drift = drift

            # Calculer l'action recommandée
            value_diff = (target_pct - current_pct) / 100 * total_value
            action = "buy" if value_diff > 0 else "sell"
            action_amount = abs(value_diff)

            alerts.append({
                "group": group,
                "target_pct": target_pct,
                "current_pct": round(current_pct, 2),
                "current_value": current_value,
                "drift": round(drift, 2),
                "drift_direction": drift_direction,
                "level": level,
                "action": action,
                "action_amount": round(action_amount, 2)
            })

        # Statut global
        if critical_count > 0:
            overall_status = "critical"
            message = f"{critical_count} groupe(s) en dérive critique"
        elif warning_count > 0:
            overall_status = "warning"
            message = f"{warning_count} groupe(s) en dérive modérée"
        else:
            overall_status = "ok"
            message = "Portfolio aligné avec les targets"

        return success_response(
            data={
                "status": overall_status,
                "message": message,
                "max_drift": round(max_drift, 2),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "alerts": alerts
            },
            meta={
                "total_value": total_value,
                "drift_threshold": drift_threshold,
                "user": user,
                "source": source
            }
        )
    except Exception as e:
        logger.exception("Error calculating portfolio alerts")
        return error_response(str(e), code=500)
