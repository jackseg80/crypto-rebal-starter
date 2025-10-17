"""
Endpoints d'exécution des plans

Ces endpoints gèrent l'exécution, l'annulation et la connexion aux exchanges.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
import logging

from services.execution.execution_engine import execution_engine
from services.execution.exchange_adapter import exchange_registry
from .models import ExecutionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/execution", tags=["execution"])

# Instance locale du gestionnaire d'ordres
order_manager = execution_engine.order_manager


@router.post("/execute-plan", response_model=ExecutionResponse)
async def execute_plan(
    plan_id: str = Query(..., description="ID du plan à exécuter"),
    dry_run: bool = Query(default=True, description="Mode simulation"),
    max_parallel: int = Query(default=3, description="Ordres en parallèle max"),
    background_tasks: BackgroundTasks = None
):
    """
    Exécuter un plan de rebalancement

    L'exécution se fait en arrière-plan. Utilisez /execution/status/{plan_id}
    pour suivre le progrès.
    """
    try:
        # Vérifier que le plan existe
        if plan_id not in order_manager.execution_plans:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan = order_manager.execution_plans[plan_id]

        # Estimer la durée d'exécution
        estimated_duration = len(plan.orders) * 2.0  # 2 secondes par ordre environ

        # Lancer l'exécution en arrière-plan
        async def execute_in_background():
            try:
                stats = await execution_engine.execute_plan(
                    plan_id=plan_id,
                    dry_run=dry_run,
                    max_parallel=max_parallel
                )
                logger.info(f"Plan {plan_id} execution completed with {stats.success_rate:.1f}% success rate")
            except Exception as e:
                logger.error(f"Background execution failed for plan {plan_id}: {e}")

        background_tasks.add_task(execute_in_background)

        return ExecutionResponse(
            success=True,
            plan_id=plan_id,
            execution_id=plan_id,  # Pour l'instant, utiliser le même ID
            message=f"Execution started for {len(plan.orders)} orders",
            estimated_duration_seconds=estimated_duration
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{plan_id}")
async def cancel_execution(plan_id: str):
    """
    Annuler l'exécution d'un plan

    Les ordres déjà en cours vont se terminer, mais aucun nouvel ordre
    ne sera lancé.
    """
    try:
        success = await execution_engine.cancel_execution(plan_id)

        if not success:
            raise HTTPException(status_code=404, detail="Execution not found or not active")

        return {
            "success": True,
            "message": f"Execution {plan_id} cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exchanges")
async def list_exchanges():
    """
    Lister les exchanges disponibles

    Retourne la liste des adaptateurs d'exchange configurés
    et leur statut de connexion.
    """
    try:
        exchanges = []

        for name in exchange_registry.list_exchanges():
            adapter = exchange_registry.get_adapter(name)
            if adapter:
                exchanges.append({
                    "name": name,
                    "type": adapter.type.value,
                    "connected": adapter.connected,
                    "config": {
                        "fee_rate": adapter.config.fee_rate,
                        "min_order_size": adapter.config.min_order_size,
                        "sandbox": adapter.config.sandbox
                    }
                })

        return {"exchanges": exchanges}

    except Exception as e:
        logger.error(f"Error listing exchanges: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exchanges/connect")
async def connect_exchanges():
    """
    Connecter tous les exchanges configurés

    Tente de se connecter à tous les adaptateurs d'exchange.
    Utile pour initialiser les connexions avant exécution.
    """
    try:
        results = await exchange_registry.connect_all()

        success_count = sum(1 for connected in results.values() if connected)
        total_count = len(results)

        return {
            "success": True,
            "message": f"Connected to {success_count}/{total_count} exchanges",
            "results": results
        }

    except Exception as e:
        logger.error(f"Error connecting exchanges: {e}")
        raise HTTPException(status_code=500, detail=str(e))
