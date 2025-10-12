"""
Risk Management Endpoints pour Bourse/Saxo

Fournit les mêmes métriques de risque que crypto (VaR, CVaR, Sharpe, DD, etc.)
mais pour les portfolios actions/ETF/obligations.

IMPORTANT: Multi-tenant strict - tous les endpoints acceptent user_id obligatoire.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from adapters import saxo_adapter
from services.risk_management import risk_manager
from services.pricing_service import get_prices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk/bourse", tags=["risk-management-bourse"])


class RiskDashboardResponse(BaseModel):
    """Response model for bourse risk dashboard"""
    ok: bool
    coverage: float = Field(description="Coverage ratio (0.0-1.0)")
    positions_count: int
    total_value_usd: float
    risk: Dict[str, Any]
    asof: str
    user_id: str


@router.get("/dashboard", response_model=RiskDashboardResponse)
async def bourse_risk_dashboard(
    user_id: str = Query("demo", description="User ID for multi-tenant isolation"),
    min_usd: float = Query(1.0, ge=0.0, description="Minimum position value in USD"),
    price_history_days: int = Query(365, ge=30, le=730, description="Days of price history for metrics")
) -> RiskDashboardResponse:
    """
    Calculer les métriques de risque pour un portfolio Bourse/Saxo.

    Réutilise le pipeline risque existant (VaR, CVaR, Sharpe, DD, etc.) avec des prix d'instruments bourse.

    Args:
        user_id: ID utilisateur (isolation multi-tenant)
        min_usd: Valeur minimum position USD à inclure
        price_history_days: Jours d'historique prix pour calculs

    Returns:
        RiskDashboardResponse avec score + métriques complètes

    Example:
        GET /api/risk/bourse/dashboard?user_id=jack&min_usd=100&price_history_days=365
    """
    try:
        logger.info(f"[risk-bourse] Computing risk dashboard for user {user_id}")

        # 1) Positions bourse pour cet utilisateur
        positions = await saxo_adapter.list_positions(user_id=user_id)

        if not positions:
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=0,
                total_value_usd=0.0,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": "No positions found for this user"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # Filtrer par seuil minimum
        positions_filtered = [p for p in positions if (p.market_value or 0.0) >= min_usd]

        if not positions_filtered:
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=len(positions),
                total_value_usd=sum((p.market_value or 0.0) for p in positions),
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": f"All positions below ${min_usd} threshold"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        total_value = sum((p.market_value or 0.0) for p in positions_filtered)

        # 2) Convertir positions vers format holdings pour risk_manager
        holdings = _positions_to_holdings(positions_filtered, total_value)

        # 3) Calcul métriques risque (réutilise le risk_manager existant)
        risk_metrics_obj = await risk_manager.calculate_portfolio_risk_metrics(
            holdings=holdings,
            price_history_days=price_history_days
        )

        # 4) Extraire métriques clés
        risk_metrics_dict = {
            "var_95_1d": risk_metrics_obj.var_95_1d,
            "cvar_95_1d": risk_metrics_obj.cvar_95_1d,
            "var_99_1d": risk_metrics_obj.var_99_1d,
            "cvar_99_1d": risk_metrics_obj.cvar_99_1d,
            "volatility_annualized": risk_metrics_obj.volatility_annualized,
            "sharpe_ratio": risk_metrics_obj.sharpe_ratio,
            "sortino_ratio": risk_metrics_obj.sortino_ratio,
            "calmar_ratio": risk_metrics_obj.calmar_ratio,
            "max_drawdown": risk_metrics_obj.max_drawdown,
            "current_drawdown": risk_metrics_obj.current_drawdown,
            "ulcer_index": risk_metrics_obj.ulcer_index,
            "skewness": risk_metrics_obj.skewness,
            "kurtosis": risk_metrics_obj.kurtosis,
            "data_points": risk_metrics_obj.data_points,
            "confidence_level": risk_metrics_obj.confidence_level,
        }

        # 5) Score risque canonique (0-100, plus haut = plus robuste)
        risk_score = _compute_risk_score(risk_metrics_dict)
        risk_level = _risk_score_to_level(risk_score)

        coverage = risk_metrics_obj.confidence_level  # Utiliser confidence_level comme proxy de coverage

        return RiskDashboardResponse(
            ok=True,
            coverage=coverage,
            positions_count=len(positions_filtered),
            total_value_usd=total_value,
            risk={
                "score": risk_score,
                "level": risk_level,
                "metrics": risk_metrics_dict
            },
            asof=datetime.utcnow().isoformat(),
            user_id=user_id
        )

    except Exception as e:
        logger.exception(f"[risk-bourse] Error computing risk dashboard for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Risk dashboard computation failed: {str(e)}"
        )


def _positions_to_holdings(positions: List[Any], total_value: float) -> List[Dict[str, Any]]:
    """
    Convertir positions Saxo vers format holdings pour risk_manager.

    Args:
        positions: Liste de PositionModel Saxo
        total_value: Valeur totale du portfolio

    Returns:
        Liste de dicts au format holdings (symbol, value_usd, weight, asset_class)
    """
    holdings = []
    for pos in positions:
        value_usd = pos.market_value or 0.0
        weight = (value_usd / total_value) if total_value > 0 else 0.0

        holdings.append({
            "symbol": pos.instrument_id,
            "value_usd": value_usd,
            "weight": weight,
            "quantity": pos.quantity,
            "asset_class": pos.tags[0].split(":")[-1] if pos.tags else "EQUITY",  # Extract from tags
        })

    return holdings


def _compute_risk_score(metrics: Dict[str, float]) -> float:
    """
    Calculer score de risque canonique (0-100, plus haut = plus robuste).

    Formule inspirée de la sémantique Risk canonique (voir docs/RISK_SEMANTICS.md).

    Args:
        metrics: Dict avec VaR, CVaR, Sharpe, DD, volatilité

    Returns:
        Score 0-100 (100 = très robuste, 0 = très risqué)
    """
    # Pénalités basées sur métriques négatives
    var_penalty = min(abs(metrics.get("var_95_1d", 0.0)), 20.0)  # Max -20 points
    cvar_penalty = min(abs(metrics.get("cvar_95_1d", 0.0)), 25.0)  # Max -25 points
    dd_penalty = min(abs(metrics.get("max_drawdown", 0.0)) / 2.0, 30.0)  # Max -30 points
    vol_penalty = min(metrics.get("volatility_annualized", 0.0) / 5.0, 15.0)  # Max -15 points

    # Bonus pour Sharpe positif
    sharpe = metrics.get("sharpe_ratio", 0.0)
    sharpe_bonus = min(max(sharpe * 5, 0.0), 20.0)  # Max +20 points

    # Score de base 70 (neutre)
    base_score = 70.0
    score = base_score - var_penalty - cvar_penalty - dd_penalty - vol_penalty + sharpe_bonus

    # Clamp [0, 100]
    return max(0.0, min(100.0, score))


def _risk_score_to_level(score: float) -> str:
    """
    Convertir score numérique en niveau textuel.

    Args:
        score: Score 0-100

    Returns:
        Niveau: VERY_LOW / LOW / MEDIUM / HIGH / VERY_HIGH / CRITICAL
    """
    if score >= 80:
        return "VERY_LOW"
    elif score >= 60:
        return "LOW"
    elif score >= 40:
        return "MEDIUM"
    elif score >= 20:
        return "HIGH"
    elif score >= 10:
        return "VERY_HIGH"
    else:
        return "CRITICAL"
