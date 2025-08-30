"""
Execution Engine - Moteur principal d'exécution des ordres

Ce module orchestre l'exécution complète d'un plan de rebalancement,
en gérant la validation, l'exécution séquentielle, et le monitoring.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import asyncio
import logging

from .order_manager import OrderManager, Order, OrderStatus, ExecutionPlan
from .exchange_adapter import ExchangeRegistry, exchange_registry

logger = logging.getLogger(__name__)

@dataclass
class ExecutionStats:
    """Statistiques d'exécution"""
    total_orders: int = 0
    completed_orders: int = 0
    failed_orders: int = 0
    total_volume_planned: float = 0.0
    total_volume_executed: float = 0.0
    total_fees: float = 0.0
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Taux de succès en pourcentage"""
        if self.total_orders == 0:
            return 0.0
        return (self.completed_orders / self.total_orders) * 100
    
    @property
    def execution_time_seconds(self) -> float:
        """Durée d'exécution en secondes"""
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

@dataclass
class ExecutionEvent:
    """Événement d'exécution pour le monitoring"""
    type: str  # "order_start", "order_complete", "order_fail", "plan_complete"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: Optional[str] = None
    plan_id: Optional[str] = None
    message: str = ""
    data: Optional[Dict[str, Any]] = None

class ExecutionEngine:
    """Moteur principal d'exécution"""
    
    def __init__(self, order_manager: OrderManager, exchange_registry: ExchangeRegistry):
        self.order_manager = order_manager
        self.exchange_registry = exchange_registry
        self.active_executions: Dict[str, bool] = {}
        self.execution_stats: Dict[str, ExecutionStats] = {}
        
        # Callbacks pour monitoring
        self.event_callbacks: List[Callable[[ExecutionEvent], None]] = []
        
    def add_event_callback(self, callback: Callable[[ExecutionEvent], None]) -> None:
        """Ajouter un callback pour les événements d'exécution"""
        self.event_callbacks.append(callback)
    
    def _emit_event(self, event: ExecutionEvent) -> None:
        """Émettre un événement vers tous les callbacks"""
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    async def execute_plan(self, plan_id: str, dry_run: bool = False, 
                          max_parallel: int = 3) -> ExecutionStats:
        """
        Exécuter un plan de rebalancement
        
        Args:
            plan_id: ID du plan à exécuter
            dry_run: Si True, simule l'exécution sans vraies transactions
            max_parallel: Nombre maximum d'ordres en parallèle
            
        Returns:
            ExecutionStats: Statistiques d'exécution
        """
        if plan_id not in self.order_manager.execution_plans:
            raise ValueError(f"Plan {plan_id} not found")
        
        if plan_id in self.active_executions:
            raise ValueError(f"Plan {plan_id} is already executing")
        
        plan = self.order_manager.execution_plans[plan_id]
        
        # Validation préalable
        validation = self.order_manager.validate_plan(plan_id)
        if not validation['valid']:
            raise ValueError(f"Plan validation failed: {validation['errors']}")
        
        # Initialiser les statistiques
        stats = ExecutionStats(
            total_orders=len(plan.orders),
            total_volume_planned=plan.total_usd_volume,
            start_time=datetime.now(timezone.utc)
        )
        self.execution_stats[plan_id] = stats
        self.active_executions[plan_id] = True
        
        logger.info(f"Starting execution of plan {plan_id} - {stats.total_orders} orders, "
                   f"${stats.total_volume_planned:,.2f} volume, dry_run={dry_run}")
        
        self._emit_event(ExecutionEvent(
            type="plan_start",
            plan_id=plan_id,
            message=f"Execution started - {stats.total_orders} orders",
            data={"dry_run": dry_run, "max_parallel": max_parallel}
        ))
        
        try:
            # Exécution séquentielle avec parallélisme limité
            await self._execute_orders_sequential(plan, stats, dry_run, max_parallel)
            
            stats.end_time = datetime.now(timezone.utc)
            plan.status = "completed"
            plan.completion_percentage = 100.0
            
            self._emit_event(ExecutionEvent(
                type="plan_complete",
                plan_id=plan_id,
                message=f"Execution completed - {stats.success_rate:.1f}% success rate",
                data={"stats": stats.__dict__}
            ))
            
            logger.info(f"Plan {plan_id} execution completed - "
                       f"{stats.success_rate:.1f}% success rate, "
                       f"{stats.execution_time_seconds:.1f}s duration")
            
        except Exception as e:
            stats.end_time = datetime.now(timezone.utc)
            plan.status = "failed"
            logger.error(f"Plan {plan_id} execution failed: {e}")
            
            self._emit_event(ExecutionEvent(
                type="plan_error",
                plan_id=plan_id,
                message=f"Execution failed: {str(e)}",
                data={"error": str(e)}
            ))
            raise
        
        finally:
            self.active_executions.pop(plan_id, None)
        
        return stats
    
    async def _execute_orders_sequential(self, plan: ExecutionPlan, stats: ExecutionStats, 
                                       dry_run: bool, max_parallel: int) -> None:
        """Exécuter les ordres de manière séquentielle avec parallélisme limité"""
        
        # Grouper les ordres par phase (ventes d'abord, puis achats)
        sell_orders = [o for o in plan.orders if o.action == "sell"]
        buy_orders = [o for o in plan.orders if o.action == "buy"]
        
        # Phase 1: Ventes (pour libérer des liquidités)
        if sell_orders:
            logger.info(f"Phase 1: Executing {len(sell_orders)} sell orders")
            await self._execute_order_batch(sell_orders, stats, dry_run, max_parallel)
        
        # Pause entre les phases pour laisser les ventes se confirmer
        if sell_orders and buy_orders:
            logger.info("Pausing between sell and buy phases...")
            await asyncio.sleep(2.0)
        
        # Phase 2: Achats
        if buy_orders:
            logger.info(f"Phase 2: Executing {len(buy_orders)} buy orders")
            await self._execute_order_batch(buy_orders, stats, dry_run, max_parallel)
    
    async def _execute_order_batch(self, orders: List[Order], stats: ExecutionStats, 
                                 dry_run: bool, max_parallel: int) -> None:
        """Exécuter un lot d'ordres avec parallélisme limité"""

        # Créer un semaphore pour limiter le parallélisme
        semaphore = asyncio.Semaphore(max_parallel)
        
        # Créer les tâches d'exécution
        tasks = []
        for order in orders:
            task = asyncio.create_task(
                self._execute_single_order_with_semaphore(semaphore, order, stats, dry_run)
            )
            tasks.append(task)
        
        # Attendre que tous les ordres soient traités
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_single_order_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                                 order: Order, stats: ExecutionStats, 
                                                 dry_run: bool) -> None:
        """Exécuter un ordre unique avec gestion du semaphore"""
        async with semaphore:
            # Arrêt coopératif si l'exécution a été annulée
            plan_id = order.rebalance_session_id
            if plan_id and not self.active_executions.get(plan_id, True):
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now(timezone.utc)
                self._emit_event(ExecutionEvent(
                    type="order_cancelled",
                    order_id=order.id,
                    plan_id=plan_id,
                    message="Order cancelled before execution"
                ))
                return
            await self._execute_single_order(order, stats, dry_run)
    
    async def _execute_single_order(self, order: Order, stats: ExecutionStats, 
                                   dry_run: bool) -> None:
        """Exécuter un ordre unique"""

        # Arrêt coopératif juste avant le démarrage effectif
        plan_id = order.rebalance_session_id
        if plan_id and not self.active_executions.get(plan_id, True):
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            self._emit_event(ExecutionEvent(
                type="order_cancelled",
                order_id=order.id,
                plan_id=plan_id,
                message="Order cancelled (cooperative check)"
            ))
            return

        self._emit_event(ExecutionEvent(
            type="order_start",
            order_id=order.id,
            plan_id=order.rebalance_session_id,
            message=f"Starting execution: {order.action} {order.alias}"
        ))
        
        order.status = OrderStatus.EXECUTING
        order.updated_at = datetime.now(timezone.utc)
        
        try:
            # Déterminer l'exchange à utiliser
            exchange_name = self._select_exchange(order, dry_run)
            adapter = self.exchange_registry.get_adapter(exchange_name)
            
            if not adapter:
                raise ValueError(f"Exchange adapter not found: {exchange_name}")
            
            if not adapter.connected:
                await adapter.connect()
            
            # Validation de l'ordre sur l'exchange
            validation_errors = adapter.validate_order(order)
            if validation_errors:
                raise ValueError(f"Order validation failed: {', '.join(validation_errors)}")
            
            # Arrêt coopératif juste avant placement d'ordre (point réseau)
            if plan_id and not self.active_executions.get(plan_id, True):
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now(timezone.utc)
                self._emit_event(ExecutionEvent(
                    type="order_cancelled",
                    order_id=order.id,
                    plan_id=plan_id,
                    message="Order cancelled before placement"
                ))
                return

            # Exécution de l'ordre
            logger.info(f"Executing order {order.alias}: {order.action} "
                       f"${abs(order.usd_amount):,.2f} on {exchange_name}")
            
            result = await adapter.place_order(order)
            
            # Traitement du résultat
            if result.success:
                order.status = OrderStatus.FILLED
                order.filled_quantity = result.filled_quantity
                order.filled_usd = result.filled_usd
                order.avg_fill_price = result.avg_price
                order.fees = result.fees
                
                stats.completed_orders += 1
                stats.total_volume_executed += abs(result.filled_usd)
                stats.total_fees += result.fees
                
                self._emit_event(ExecutionEvent(
                    type="order_complete",
                    order_id=order.id,
                    plan_id=order.rebalance_session_id,
                    message=f"Order completed: {order.alias} @ ${result.avg_price:.2f}",
                    data={"result": result.__dict__}
                ))
                
                logger.info(f"Order {order.alias} completed successfully: "
                           f"{result.filled_quantity:.6f} @ ${result.avg_price:.2f}")
            
            else:
                order.status = OrderStatus.FAILED
                order.error_message = result.error_message
                stats.failed_orders += 1
                
                self._emit_event(ExecutionEvent(
                    type="order_fail",
                    order_id=order.id,
                    plan_id=order.rebalance_session_id,
                    message=f"Order failed: {order.alias} - {result.error_message}",
                    data={"error": result.error_message}
                ))
                
                logger.error(f"Order {order.alias} failed: {result.error_message}")
        
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            stats.failed_orders += 1
            
            self._emit_event(ExecutionEvent(
                type="order_error",
                order_id=order.id,
                plan_id=order.rebalance_session_id,
                message=f"Order error: {order.alias} - {str(e)}",
                data={"error": str(e)}
            ))
            
            logger.error(f"Error executing order {order.alias}: {e}")
        
        finally:
            order.updated_at = datetime.now(timezone.utc)
    
    def _select_exchange(self, order: Order, dry_run: bool) -> str:
        """Sélectionner l'exchange pour un ordre"""
        
        # En mode dry_run, toujours utiliser le simulateur
        if dry_run:
            return "simulator"
        
        # Utiliser l'hint de plateforme si disponible
        if order.platform and order.platform != "unknown":
            available = self.exchange_registry.list_exchanges()
            
            # Mapping des hints vers les exchanges
            platform_mapping = {
                "binance": "binance",
                "coinbase": "coinbase", 
                "kraken": "kraken",
                "cex_generic": "binance"  # Fallback CEX
            }
            
            exchange_name = platform_mapping.get(order.platform)
            if exchange_name and exchange_name in available:
                return exchange_name
        
        # Fallback: simulateur pour les tests
        return "simulator"
    
    async def cancel_execution(self, plan_id: str) -> bool:
        """Annuler l'exécution d'un plan"""
        if plan_id not in self.active_executions:
            return False
        
        logger.warning(f"Cancelling execution of plan {plan_id}")
        
        # Marquer comme non actif (les ordres en cours vont se terminer)
        self.active_executions[plan_id] = False
        
        # Marquer tous les ordres PENDING/QUEUED comme CANCELLED
        plan = self.order_manager.execution_plans.get(plan_id)
        if plan:
            for order in plan.orders:
                if order.status in [OrderStatus.PENDING, OrderStatus.QUEUED]:
                    order.status = OrderStatus.CANCELLED
                    order.updated_at = datetime.now(timezone.utc)
        
        self._emit_event(ExecutionEvent(
            type="plan_cancelled",
            plan_id=plan_id,
            message="Execution cancelled by user"
        ))
        
        return True
    
    def get_execution_progress(self, plan_id: str) -> Dict[str, Any]:
        """Obtenir le progrès d'exécution en temps réel"""
        if plan_id not in self.execution_stats:
            return {"error": "Execution not found"}
        
        stats = self.execution_stats[plan_id]
        plan = self.order_manager.execution_plans.get(plan_id)
        
        progress = {
            "plan_id": plan_id,
            "status": plan.status if plan else "unknown",
            "is_active": self.active_executions.get(plan_id, False),
            "total_orders": stats.total_orders,
            "completed_orders": stats.completed_orders,
            "failed_orders": stats.failed_orders,
            "success_rate": stats.success_rate,
            "volume_planned": stats.total_volume_planned,
            "volume_executed": stats.total_volume_executed,
            "total_fees": stats.total_fees,
            "execution_time": stats.execution_time_seconds,
            "start_time": stats.start_time.isoformat() if stats.start_time else None,
            "end_time": stats.end_time.isoformat() if stats.end_time else None
        }
        
        if plan:
            progress["completion_percentage"] = plan.completion_percentage
        
        return progress

# Instance globale du moteur d'exécution
execution_engine = ExecutionEngine(
    order_manager=OrderManager(),
    exchange_registry=exchange_registry
)
