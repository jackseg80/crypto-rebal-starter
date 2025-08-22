"""
Order Management System - Gestion intelligente des ordres de rebalancement

Ce module gère la validation, l'optimisation et le tracking des ordres
générés par le système de rebalancement.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    """Statuts possibles d'un ordre"""
    PENDING = "pending"           # En attente de validation
    VALIDATED = "validated"       # Validé, prêt pour exécution
    QUEUED = "queued"            # En file d'attente
    EXECUTING = "executing"       # En cours d'exécution
    PARTIALLY_FILLED = "partial" # Partiellement exécuté
    FILLED = "filled"            # Complètement exécuté  
    CANCELLED = "cancelled"       # Annulé
    FAILED = "failed"            # Échec d'exécution
    EXPIRED = "expired"          # Expiré

class OrderType(Enum):
    """Types d'ordres supportés"""
    MARKET = "market"            # Ordre au marché
    LIMIT = "limit"              # Ordre à cours limité
    STOP_LOSS = "stop_loss"      # Stop loss
    SMART = "smart"              # Ordre intelligent (TWAP, etc.)

@dataclass
class Order:
    """Représentation d'un ordre de trading"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Informations de base
    symbol: str = ""
    alias: str = ""
    group: str = ""
    action: str = ""  # "buy" ou "sell"
    
    # Quantités et prix
    quantity: float = 0.0
    usd_amount: float = 0.0
    target_price: Optional[float] = None
    limit_price: Optional[float] = None
    
    # Configuration d'ordre
    order_type: OrderType = OrderType.MARKET
    time_in_force: str = "GTC"  # Good Till Cancelled
    
    # Exécution
    platform: str = ""           # "CEX Binance", "DEX Uniswap", etc.
    exec_hint: str = ""          # Suggestion du système de rebalancement
    priority: int = 5            # 1=haute, 10=basse
    
    # Tracking
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Résultats d'exécution
    filled_quantity: float = 0.0
    filled_usd: float = 0.0
    avg_fill_price: Optional[float] = None
    fees: float = 0.0
    
    # Métadonnées
    rebalance_session_id: Optional[str] = None
    notes: str = ""
    error_message: Optional[str] = None

@dataclass
class ExecutionPlan:
    """Plan d'exécution complet pour un rebalancement"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    orders: List[Order] = field(default_factory=list)
    total_orders: int = 0
    total_usd_volume: float = 0.0
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Méta-informations
    source_plan: Optional[Dict[str, Any]] = None
    dynamic_targets_used: bool = False
    ccs_score: Optional[float] = None
    
    # Statut global
    status: str = "pending"      # pending, executing, completed, failed
    completion_percentage: float = 0.0

class OrderManager:
    """Gestionnaire principal des ordres"""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.execution_plans: Dict[str, ExecutionPlan] = {}
        
    def create_execution_plan(self, rebalance_actions: List[Dict[str, Any]], 
                            metadata: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """
        Créer un plan d'exécution à partir des actions de rebalancement
        
        Args:
            rebalance_actions: Actions générées par le service de rebalancement
            metadata: Métadonnées additionnelles (CCS score, etc.)
            
        Returns:
            ExecutionPlan: Plan d'exécution optimisé
        """
        plan = ExecutionPlan()
        
        if metadata:
            plan.dynamic_targets_used = metadata.get('dynamic_targets_used', False)
            plan.ccs_score = metadata.get('ccs_score')
            plan.source_plan = metadata.get('source_plan')
        
        total_volume = 0.0
        
        # Convertir les actions en ordres
        for action in rebalance_actions:
            order = self._action_to_order(action, plan.id)
            plan.orders.append(order)
            total_volume += abs(order.usd_amount)
            
            # Enregistrer l'ordre
            self.orders[order.id] = order
        
        # Optimiser l'ordre d'exécution
        plan.orders = self._optimize_execution_order(plan.orders)
        
        plan.total_orders = len(plan.orders)
        plan.total_usd_volume = total_volume
        
        self.execution_plans[plan.id] = plan
        
        logger.info(f"Created execution plan {plan.id} with {plan.total_orders} orders, "
                   f"${plan.total_usd_volume:,.2f} total volume")
        
        return plan
    
    def _action_to_order(self, action: Dict[str, Any], plan_id: str) -> Order:
        """Convertir une action de rebalancement en ordre"""
        
        order = Order(
            symbol=action.get('symbol', ''),
            alias=action.get('alias', ''),
            group=action.get('group', ''),
            action=action.get('action', ''),
            usd_amount=float(action.get('usd', 0.0)),
            quantity=float(action.get('est_quantity', 0.0)) if action.get('est_quantity') else 0.0,
            target_price=float(action.get('price_used', 0.0)) if action.get('price_used') else None,
            exec_hint=action.get('exec_hint', ''),
            rebalance_session_id=plan_id
        )
        
        # Déterminer la plateforme depuis exec_hint
        if order.exec_hint:
            order.platform = self._extract_platform_from_hint(order.exec_hint)
        
        # Déterminer la priorité (les ventes d'abord pour libérer des liquidités)
        if order.action == "sell":
            order.priority = 2  # Haute priorité
        else:
            order.priority = 7  # Priorité plus basse
            
        # Ajuster le type d'ordre selon la taille
        if abs(order.usd_amount) > 1000:  # Gros ordres
            order.order_type = OrderType.SMART
        else:
            order.order_type = OrderType.MARKET
            
        return order
    
    def _extract_platform_from_hint(self, exec_hint: str) -> str:
        """Extraire la plateforme recommandée depuis exec_hint"""
        hint_lower = exec_hint.lower()
        
        if "binance" in hint_lower:
            return "binance"
        elif "coinbase" in hint_lower:
            return "coinbase"
        elif "kraken" in hint_lower:
            return "kraken"
        elif "dex" in hint_lower or "uniswap" in hint_lower:
            return "dex"
        elif "cex" in hint_lower:
            return "cex_generic"
        else:
            return "unknown"
    
    def _optimize_execution_order(self, orders: List[Order]) -> List[Order]:
        """
        Optimiser l'ordre d'exécution des ordres
        
        Stratégie:
        1. Ventes d'abord (pour libérer liquidités)
        2. Ordre par priorité
        3. Gros ordres avant petits ordres pour même priorité
        """
        def sort_key(order: Order) -> Tuple[int, int, float]:
            # 1. Action: ventes d'abord (0), puis achats (1)
            action_priority = 0 if order.action == "sell" else 1
            
            # 2. Priorité custom
            priority = order.priority
            
            # 3. Taille (négatif pour avoir les plus gros d'abord)
            size = -abs(order.usd_amount)
            
            return (action_priority, priority, size)
        
        optimized = sorted(orders, key=sort_key)
        
        logger.info(f"Optimized execution order: {len(optimized)} orders")
        return optimized
    
    def validate_plan(self, plan_id: str) -> Dict[str, Any]:
        """
        Valider un plan d'exécution
        
        Vérifications:
        - Équilibrage des montants (somme = 0)
        - Disponibilité des pairs de trading
        - Limites de taille d'ordre
        - Cohérence des données
        """
        if plan_id not in self.execution_plans:
            return {"valid": False, "errors": ["Plan not found"]}
        
        plan = self.execution_plans[plan_id]
        errors = []
        warnings = []
        
        # 1. Vérifier l'équilibrage
        total_usd = sum(order.usd_amount for order in plan.orders)
        if abs(total_usd) > 1.0:  # Tolérance de $1
            errors.append(f"Plan not balanced: total USD = {total_usd:.2f}")
        
        # 2. Vérifier les ordres individuels
        for order in plan.orders:
            # Quantité positive (toujours positive, indépendamment de l'action)
            if order.quantity != 0 and order.quantity <= 0:
                warnings.append(f"Order {order.alias}: quantity must be positive")
            
            # Prix cohérent
            if order.target_price and order.target_price <= 0:
                errors.append(f"Order {order.alias}: invalid target price {order.target_price}")
            
            # Plateforme identifiée
            if not order.platform or order.platform == "unknown":
                warnings.append(f"Order {order.alias}: no platform identified")
        
        # 3. Vérifier les gros ordres
        large_orders = [o for o in plan.orders if abs(o.usd_amount) > 10000]
        if large_orders:
            warnings.append(f"{len(large_orders)} large orders (>$10K) detected - consider splitting")
        
        # Marquer comme validé si pas d'erreurs
        if not errors:
            plan.status = "validated"
            for order in plan.orders:
                order.status = OrderStatus.VALIDATED
                order.updated_at = datetime.now(timezone.utc)
            plan.updated_at = datetime.now(timezone.utc)
        
        result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_orders": len(plan.orders),
            "total_volume": plan.total_usd_volume,
            "large_orders_count": len(large_orders)
        }
        
        logger.info(f"Plan {plan_id} validation: {'PASSED' if result['valid'] else 'FAILED'}")
        if errors:
            logger.error(f"Validation errors: {errors}")
        if warnings:
            logger.warning(f"Validation warnings: {warnings}")
        
        return result
    
    def get_plan_status(self, plan_id: str) -> Dict[str, Any]:
        """Obtenir le statut détaillé d'un plan"""
        if plan_id not in self.execution_plans:
            return {"error": "Plan not found"}
        
        plan = self.execution_plans[plan_id]
        
        # Statistiques des ordres
        order_stats = {}
        for status in OrderStatus:
            count = sum(1 for o in plan.orders if o.status == status)
            if count > 0:
                order_stats[status.value] = count
        
        # Progression
        filled_orders = sum(1 for o in plan.orders if o.status == OrderStatus.FILLED)
        progress = (filled_orders / len(plan.orders)) * 100 if plan.orders else 0
        
        return {
            "plan_id": plan.id,
            "status": plan.status,
            "progress_percent": progress,
            "total_orders": plan.total_orders,
            "total_volume": plan.total_usd_volume,
            "order_stats": order_stats,
            "created_at": plan.created_at.isoformat(),
            "updated_at": plan.updated_at.isoformat(),
            "dynamic_targets_used": plan.dynamic_targets_used,
            "ccs_score": plan.ccs_score
        }
    
    def update_order_status(self, order_id: str, status: OrderStatus, 
                           fill_info: Optional[Dict[str, Any]] = None) -> bool:
        """Mettre à jour le statut d'un ordre"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        old_status = order.status
        order.status = status
        order.updated_at = datetime.now(timezone.utc)
        
        # Mettre à jour les informations de fill si disponibles
        if fill_info:
            order.filled_quantity = fill_info.get('filled_quantity', order.filled_quantity)
            order.filled_usd = fill_info.get('filled_usd', order.filled_usd)
            order.avg_fill_price = fill_info.get('avg_fill_price')
            order.fees = fill_info.get('fees', order.fees)
            
            if 'error_message' in fill_info:
                order.error_message = fill_info['error_message']
        
        logger.info(f"Order {order.alias} status: {old_status.value} → {status.value}")
        return True