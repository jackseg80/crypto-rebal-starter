"""
Endpoints de monitoring de l'exécution

Ces endpoints permettent de surveiller l'état et le progrès des plans d'exécution.
"""

from fastapi import APIRouter, HTTPException, Query
import logging
from datetime import datetime

from services.execution.execution_engine import execution_engine
from .models import ExecutionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["monitoring"])

# Instance locale du gestionnaire d'ordres
order_manager = execution_engine.order_manager


@router.get("/status/{plan_id}", response_model=ExecutionStatus)
async def get_execution_status(plan_id: str):
    """
    Obtenir le statut d'exécution d'un plan

    Retourne le progrès en temps réel, les statistiques d'exécution,
    et le statut de chaque ordre.
    """
    try:
        progress = execution_engine.get_execution_progress(plan_id)

        if "error" in progress:
            raise HTTPException(status_code=404, detail=progress["error"])

        return ExecutionStatus(**progress)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans")
async def list_execution_plans(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Lister les plans d'exécution

    Retourne la liste des plans avec leur statut actuel.
    """
    try:
        plans_data = []

        # Obtenir tous les plans du gestionnaire d'ordres
        all_plans = list(order_manager.execution_plans.values())

        # Pagination
        paginated_plans = all_plans[offset:offset + limit]

        for plan in paginated_plans:
            plan_status = order_manager.get_plan_status(plan.id)
            plans_data.append(plan_status)

        return {
            "plans": plans_data,
            "total": len(all_plans),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error listing plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/{plan_id}")
async def get_plan_orders(plan_id: str):
    """
    Obtenir la liste détaillée des ordres d'un plan

    Retourne tous les ordres avec leur statut, résultats d'exécution,
    et détails techniques.
    """
    try:
        if plan_id not in order_manager.execution_plans:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan = order_manager.execution_plans[plan_id]

        orders_data = []
        for order in plan.orders:
            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "alias": order.alias,
                "group": order.group,
                "action": order.action,
                "quantity": order.quantity,
                "usd_amount": order.usd_amount,
                "target_price": order.target_price,
                "platform": order.platform,
                "exec_hint": order.exec_hint,
                "priority": order.priority,
                "status": order.status.value,
                "order_type": order.order_type.value,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),

                # Résultats d'exécution
                "filled_quantity": order.filled_quantity,
                "filled_usd": order.filled_usd,
                "avg_fill_price": order.avg_fill_price,
                "fees": order.fees,
                "error_message": order.error_message
            }
            orders_data.append(order_data)

        return {
            "plan_id": plan_id,
            "orders": orders_data,
            "total_orders": len(orders_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline-status")
async def get_pipeline_status():
    """
    Obtenir le statut global du pipeline d'exécution

    Vue d'ensemble de tous les plans actifs, statistiques globales,
    et santé des exchanges.
    """
    try:
        # Plans actifs
        active_plans = [
            plan_id for plan_id, is_active in execution_engine.active_executions.items()
            if is_active
        ]

        # Statistiques globales
        all_plans = order_manager.execution_plans
        total_plans = len(all_plans)

        completed_plans = sum(1 for plan in all_plans.values() if plan.status == "completed")
        failed_plans = sum(1 for plan in all_plans.values() if plan.status == "failed")

        # Santé des exchanges
        from services.execution.exchange_adapter import exchange_registry
        exchange_health = []
        for name in exchange_registry.list_exchanges():
            adapter = exchange_registry.get_adapter(name)
            if adapter:
                exchange_health.append({
                    "name": name,
                    "connected": adapter.connected,
                    "type": adapter.type.value
                })

        return {
            "pipeline_status": "active" if active_plans else "idle",
            "active_executions": len(active_plans),
            "active_plan_ids": active_plans,
            "statistics": {
                "total_plans": total_plans,
                "completed_plans": completed_plans,
                "failed_plans": failed_plans,
                "success_rate": (completed_plans / max(total_plans, 1)) * 100
            },
            "exchange_health": exchange_health,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
