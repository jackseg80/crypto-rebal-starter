"""
Risk Management Endpoints pour Bourse/Saxo

Fournit les métriques de risque pour portfolios actions/ETF/obligations.
Utilise le nouveau BourseRiskCalculator avec support yfinance.

IMPORTANT: Multi-tenant strict - tous les endpoints acceptent user_id obligatoire.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field

from services.risk.bourse.calculator import BourseRiskCalculator
from api.deps import get_active_user

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
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo file to use"),
    min_usd: float = Query(1.0, ge=0.0, description="Minimum position value in USD"),
    lookback_days: int = Query(252, ge=30, le=730, description="Days of price history for metrics"),
    risk_free_rate: float = Query(0.03, ge=0.0, le=0.20, description="Annual risk-free rate"),
    var_method: str = Query("historical", description="VaR calculation method")
) -> RiskDashboardResponse:
    """
    Calculer les métriques de risque pour un portfolio Bourse/Saxo.

    Utilise le nouveau BourseRiskCalculator avec support yfinance pour données historiques.

    Args:
        user_id: ID utilisateur (isolation multi-tenant)
        file_key: Clé du fichier Saxo spécifique (optionnel)
        min_usd: Valeur minimum position USD à inclure
        lookback_days: Jours d'historique prix pour calculs
        risk_free_rate: Taux sans risque annuel pour Sharpe/Sortino
        var_method: Méthode VaR (historical|parametric|montecarlo)

    Returns:
        RiskDashboardResponse avec score + métriques complètes

    Example:
        GET /api/risk/bourse/dashboard?user_id=jack&file_key=portfolio.csv&min_usd=100&lookback_days=252
    """
    try:
        logger.info(f"[risk-bourse] Computing risk dashboard for user {user_id}")

        # 1) Récupérer positions Saxo via l'adaptateur
        # Importer ici pour éviter circulaire
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail

        # Lister les portfolios de l'utilisateur
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)

        if not portfolios:
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=0,
                total_value_usd=0.0,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": "No Saxo portfolios found for this user"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # Prendre le premier portfolio (ou filtrer selon besoin)
        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)

        positions = portfolio_data.get("positions", [])

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
                    "message": "No positions found in portfolio"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # Filtrer par seuil minimum
        positions_filtered = [p for p in positions if p.get("market_value_usd", 0.0) >= min_usd]

        if not positions_filtered:
            total_value = sum(p.get("market_value_usd", 0.0) for p in positions)
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=len(positions),
                total_value_usd=total_value,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": f"All positions below ${min_usd} threshold"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # 2) Calculer risque avec BourseRiskCalculator
        calculator = BourseRiskCalculator(data_source="yahoo")

        risk_result = await calculator.calculate_portfolio_risk(
            positions=positions_filtered,
            benchmark="SPY",  # S&P500 par défaut
            lookback_days=lookback_days,
            risk_free_rate=risk_free_rate,
            var_method=var_method
        )

        # 3) Formater réponse
        total_value = risk_result["metadata"]["portfolio_value"]
        risk_score = risk_result["risk_score"]["risk_score"]
        risk_level = risk_result["risk_score"]["risk_level"]

        # Métriques détaillées
        metrics = risk_result["traditional_risk"]

        # Coverage (proxy basé sur disponibilité données)
        coverage = min(1.0, len(positions_filtered) / max(1, len(positions)))

        return RiskDashboardResponse(
            ok=True,
            coverage=coverage,
            positions_count=len(positions_filtered),
            total_value_usd=total_value,
            risk={
                "score": risk_score,
                "level": risk_level,
                "metrics": metrics
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


# Helper functions removed - now handled by BourseRiskCalculator
