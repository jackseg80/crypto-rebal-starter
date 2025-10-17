"""
Endpoints de validation des plans d'exécution

Ces endpoints permettent de valider les plans avant leur exécution
et de vérifier les changements d'allocation.
"""

from fastapi import APIRouter, HTTPException
import logging
from datetime import datetime

from services.execution.execution_engine import execution_engine
from services.execution.governance import governance_engine
from .models import ExecutionRequest, ValidationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["validation"])

# Instance locale du gestionnaire d'ordres
order_manager = execution_engine.order_manager


@router.post("/validate-plan", response_model=ValidationResponse)
async def validate_execution_plan(request: ExecutionRequest):
    """
    Valider un plan d'exécution avant lancement

    Vérifie:
    - Équilibrage des montants
    - Cohérence des données
    - Disponibilité des pairs de trading
    - Limites de taille d'ordre
    """
    try:
        # Créer le plan d'exécution
        plan = order_manager.create_execution_plan(
            rebalance_actions=request.rebalance_actions,
            metadata=request.metadata
        )

        # Valider le plan
        validation = order_manager.validate_plan(plan.id)

        return ValidationResponse(
            valid=validation["valid"],
            errors=validation["errors"],
            warnings=validation["warnings"],
            plan_id=plan.id,
            total_orders=validation["total_orders"],
            total_volume=validation["total_volume"],
            large_orders_count=validation["large_orders_count"]
        )

    except Exception as e:
        logger.error(f"Error validating plan: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/governance/validate-allocation")
async def validate_allocation_change(request: dict):
    """
    Valide un changement d'allocation avant exécution

    Vérifie no-trade zone et estime les coûts d'exécution
    """
    try:
        current_weights = request.get("current_weights", {})
        target_weights = request.get("target_weights", {})
        portfolio_usd = request.get("portfolio_usd", 100000)

        # Vérifier no-trade zone
        within_zone, changes = governance_engine.is_change_within_no_trade_zone(current_weights, target_weights)

        # Estimer coûts d'exécution
        cost_estimate = governance_engine.estimate_execution_cost(target_weights, portfolio_usd)

        # Recommandation basée sur l'analyse
        recommendation = "approve"
        if not within_zone:
            recommendation = "review"  # Changements significatifs
        if not cost_estimate.get('cost_efficient', True):
            recommendation = "reject"  # Coûts trop élevés

        return {
            "valid": within_zone,
            "recommendation": recommendation,
            "no_trade_analysis": {
                "within_zone": within_zone,
                "changes": changes
            },
            "cost_analysis": cost_estimate,
            "summary": {
                "total_changes": len([c for c in changes.values() if not c['within_zone']]),
                "largest_change_pct": max([c['change'] for c in changes.values()]) * 100 if changes else 0,
                "estimated_cost_pct": cost_estimate.get('cost_percentage', 0),
                "cost_efficient": cost_estimate.get('cost_efficient', True)
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error validating allocation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
