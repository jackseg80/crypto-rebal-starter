"""
History Manager - Gestionnaire de l'historique des rebalancement

Ce module gère l'historique complet des sessions de rebalancement,
permettant l'analyse des performances et l'optimisation des stratégies.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class SessionStatus(Enum):
    """Statuts d'une session de rebalancement"""
    PLANNED = "planned"           # Plan créé mais pas exécuté
    EXECUTING = "executing"       # En cours d'exécution
    COMPLETED = "completed"       # Exécution terminée avec succès
    FAILED = "failed"            # Exécution échouée
    CANCELLED = "cancelled"       # Annulé par l'utilisateur

@dataclass
class RebalanceAction:
    """Action de rebalancement avec résultats d'exécution"""
    # Informations de base
    group: str
    alias: str
    symbol: str
    action: str  # "buy" ou "sell"
    
    # Plan initial
    planned_usd: float
    planned_quantity: float
    target_price: Optional[float] = None
    exec_hint: str = ""
    
    # Résultats d'exécution
    executed: bool = False
    executed_usd: float = 0.0
    executed_quantity: float = 0.0
    execution_price: Optional[float] = None
    fees: float = 0.0
    
    # Statut et erreurs
    status: str = "pending"
    error_message: Optional[str] = None
    
    # Métadonnées
    platform: str = ""
    execution_time: Optional[datetime] = None
    
    @property
    def execution_variance_pct(self) -> float:
        """Variance entre planifié et exécuté en %"""
        if not self.executed or self.planned_usd == 0:
            return 0.0
        return ((self.executed_usd - self.planned_usd) / abs(self.planned_usd)) * 100
    
    @property
    def price_impact_pct(self) -> float:
        """Impact du prix d'exécution vs target"""
        if not self.target_price or not self.execution_price:
            return 0.0
        return ((self.execution_price - self.target_price) / self.target_price) * 100

@dataclass
class PortfolioSnapshot:
    """Snapshot de l'état du portfolio à un moment donné"""
    timestamp: datetime
    total_usd: float
    
    # Répartition par groupe
    allocations: Dict[str, float]  # {"BTC": 35.5, "ETH": 25.2, ...}
    values_usd: Dict[str, float]   # {"BTC": 150000, "ETH": 106000, ...}
    
    # Métriques de performance
    performance_24h_pct: Optional[float] = None
    performance_7d_pct: Optional[float] = None
    performance_30d_pct: Optional[float] = None
    
    # Métriques de risque
    volatility_score: Optional[float] = None
    diversification_score: Optional[float] = None
    
    def calculate_drift_from_targets(self, targets: Dict[str, float]) -> Dict[str, float]:
        """Calculer la dérive par rapport aux targets"""
        drift = {}
        for group, target_pct in targets.items():
            current_pct = self.allocations.get(group, 0.0)
            drift[group] = current_pct - target_pct
        return drift

@dataclass
class RebalanceSession:
    """Session complète de rebalancement avec historique"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Configuration
    source: str = "unknown"
    pricing_mode: str = "auto"
    min_trade_usd: float = 25.0
    
    # Targets et stratégie
    target_allocations: Dict[str, float] = field(default_factory=dict)
    dynamic_targets_used: bool = False
    ccs_score: Optional[float] = None
    strategy_notes: str = ""
    
    # États du portfolio
    portfolio_before: Optional[PortfolioSnapshot] = None
    portfolio_after: Optional[PortfolioSnapshot] = None
    
    # Actions de rebalancement
    actions: List[RebalanceAction] = field(default_factory=list)
    
    # Statut et métriques d'exécution
    status: SessionStatus = SessionStatus.PLANNED
    total_planned_volume: float = 0.0
    total_executed_volume: float = 0.0
    total_fees: float = 0.0
    
    # Résultats de performance
    execution_success_rate: float = 0.0
    avg_execution_variance_pct: float = 0.0
    total_slippage_bps: float = 0.0  # en basis points
    
    # Métadonnées
    error_message: Optional[str] = None
    user_notes: str = ""
    
    def update_execution_metrics(self) -> None:
        """Mettre à jour les métriques d'exécution"""
        executed_actions = [a for a in self.actions if a.executed]
        total_actions = len(self.actions)
        
        if total_actions > 0:
            self.execution_success_rate = (len(executed_actions) / total_actions) * 100
        
        # Volume exécuté
        self.total_executed_volume = sum(abs(a.executed_usd) for a in executed_actions)
        self.total_fees = sum(a.fees for a in self.actions)
        
        # Variance moyenne
        variances = [a.execution_variance_pct for a in executed_actions if a.execution_variance_pct != 0]
        if variances:
            self.avg_execution_variance_pct = sum(variances) / len(variances)
        
        # Slippage (approximation basée sur price impact)
        price_impacts = [abs(a.price_impact_pct) for a in executed_actions if a.price_impact_pct != 0]
        if price_impacts:
            self.total_slippage_bps = (sum(price_impacts) / len(price_impacts)) * 100  # Convert to bps
    
    def calculate_performance_impact(self) -> Dict[str, float]:
        """Calculer l'impact performance du rebalancement"""
        if not self.portfolio_before or not self.portfolio_after:
            return {}
        
        return {
            "total_value_change_usd": self.portfolio_after.total_usd - self.portfolio_before.total_usd,
            "total_value_change_pct": ((self.portfolio_after.total_usd - self.portfolio_before.total_usd) / 
                                     self.portfolio_before.total_usd) * 100,
            "allocation_improvement": self._calculate_allocation_improvement(),
            "risk_adjusted_return": self._calculate_risk_adjusted_return()
        }
    
    def _calculate_allocation_improvement(self) -> float:
        """Calculer l'amélioration de l'allocation"""
        if not self.portfolio_before or not self.portfolio_after:
            return 0.0
        
        # Dérive avant rebalancement
        drift_before = self.portfolio_before.calculate_drift_from_targets(self.target_allocations)
        total_drift_before = sum(abs(d) for d in drift_before.values())
        
        # Dérive après rebalancement
        drift_after = self.portfolio_after.calculate_drift_from_targets(self.target_allocations)
        total_drift_after = sum(abs(d) for d in drift_after.values())
        
        # Amélioration (réduction de la dérive)
        if total_drift_before > 0:
            return ((total_drift_before - total_drift_after) / total_drift_before) * 100
        return 0.0
    
    def _calculate_risk_adjusted_return(self) -> float:
        """Calculer le retour ajusté au risque (Sharpe approximé)"""
        if not self.portfolio_before or not self.portfolio_after:
            return 0.0
        
        # Approximation simple basée sur la diversification
        before_div = self.portfolio_before.diversification_score or 0.0
        after_div = self.portfolio_after.diversification_score or 0.0
        
        return after_div - before_div

class HistoryManager:
    """Gestionnaire de l'historique des rebalancement"""
    
    def __init__(self, storage_path: str = "data/rebalance_history.json"):
        self.storage_path = Path(storage_path)
        self.sessions: Dict[str, RebalanceSession] = {}
        
        # Créer le répertoire si nécessaire
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Charger l'historique existant
        self._load_history()
    
    def _load_history(self) -> None:
        """Charger l'historique depuis le fichier"""
        if not self.storage_path.exists():
            logger.info("No existing history file found")
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for session_data in data.get('sessions', []):
                session = self._deserialize_session(session_data)
                self.sessions[session.id] = session
            
            logger.info(f"Loaded {len(self.sessions)} rebalance sessions from history")
            
        except Exception as e:
            logger.error(f"Error loading history: {e}")
    
    def _save_history(self) -> None:
        """Sauvegarder l'historique dans le fichier"""
        try:
            # Sérialiser toutes les sessions
            serialized_sessions = []
            for session in self.sessions.values():
                serialized_sessions.append(self._serialize_session(session))
            
            data = {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "total_sessions": len(serialized_sessions),
                "sessions": serialized_sessions
            }
            
            # Créer un backup de l'ancien fichier
            if self.storage_path.exists():
                backup_path = self.storage_path.with_suffix('.json.bak')
                self.storage_path.rename(backup_path)
            
            # Sauvegarder
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.sessions)} sessions to history")
            
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def _serialize_session(self, session: RebalanceSession) -> Dict[str, Any]:
        """Sérialiser une session pour stockage JSON"""
        data = asdict(session)
        
        # Convertir les dates en ISO strings
        for field in ['created_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        
        # Sérialiser les snapshots
        if data['portfolio_before']:
            data['portfolio_before']['timestamp'] = data['portfolio_before']['timestamp'].isoformat()
        if data['portfolio_after']:
            data['portfolio_after']['timestamp'] = data['portfolio_after']['timestamp'].isoformat()
        
        # Sérialiser les actions
        for action in data['actions']:
            if action['execution_time']:
                action['execution_time'] = action['execution_time'].isoformat()
        
        # Convertir enum
        data['status'] = data['status'].value if hasattr(data['status'], 'value') else data['status']
        
        return data
    
    def _deserialize_session(self, data: Dict[str, Any]) -> RebalanceSession:
        """Désérialiser une session depuis JSON"""
        # Convertir les dates
        for field in ['created_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = datetime.fromisoformat(data[field])
        
        # Désérialiser les snapshots
        if data['portfolio_before']:
            snapshot_data = data['portfolio_before']
            snapshot_data['timestamp'] = datetime.fromisoformat(snapshot_data['timestamp'])
            data['portfolio_before'] = PortfolioSnapshot(**snapshot_data)
        
        if data['portfolio_after']:
            snapshot_data = data['portfolio_after']
            snapshot_data['timestamp'] = datetime.fromisoformat(snapshot_data['timestamp'])
            data['portfolio_after'] = PortfolioSnapshot(**snapshot_data)
        
        # Désérialiser les actions
        actions = []
        for action_data in data['actions']:
            if action_data['execution_time']:
                action_data['execution_time'] = datetime.fromisoformat(action_data['execution_time'])
            actions.append(RebalanceAction(**action_data))
        data['actions'] = actions
        
        # Convertir enum
        data['status'] = SessionStatus(data['status'])
        
        return RebalanceSession(**data)
    
    def create_session(self, target_allocations: Dict[str, float],
                      source: str = "unknown", pricing_mode: str = "auto",
                      dynamic_targets_used: bool = False,
                      ccs_score: Optional[float] = None,
                      min_trade_usd: float = 25.0) -> RebalanceSession:
        """Créer une nouvelle session de rebalancement"""
        
        session = RebalanceSession(
            target_allocations=target_allocations,
            source=source,
            pricing_mode=pricing_mode,
            dynamic_targets_used=dynamic_targets_used,
            ccs_score=ccs_score,
            min_trade_usd=min_trade_usd
        )
        
        self.sessions[session.id] = session
        logger.info(f"Created rebalance session {session.id}")
        
        return session
    
    def add_portfolio_snapshot(self, session_id: str, snapshot: PortfolioSnapshot, 
                             is_before: bool = True) -> bool:
        """Ajouter un snapshot de portfolio à une session"""
        if session_id not in self.sessions:
            return False
        
        if is_before:
            self.sessions[session_id].portfolio_before = snapshot
        else:
            self.sessions[session_id].portfolio_after = snapshot
        
        logger.debug(f"Added {'before' if is_before else 'after'} snapshot to session {session_id}")
        return True
    
    def add_rebalance_actions(self, session_id: str, actions: List[Dict[str, Any]]) -> bool:
        """Ajouter les actions de rebalancement à une session"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        for action_data in actions:
            action = RebalanceAction(
                group=action_data.get('group', ''),
                alias=action_data.get('alias', ''),
                symbol=action_data.get('symbol', ''),
                action=action_data.get('action', ''),
                planned_usd=float(action_data.get('usd', 0.0)),
                planned_quantity=float(action_data.get('est_quantity', 0.0)) if action_data.get('est_quantity') else 0.0,
                target_price=float(action_data.get('price_used', 0.0)) if action_data.get('price_used') else None,
                exec_hint=action_data.get('exec_hint', '')
            )
            session.actions.append(action)
        
        # Calculer le volume total planifié
        session.total_planned_volume = sum(abs(a.planned_usd) for a in session.actions)
        
        logger.info(f"Added {len(actions)} actions to session {session_id}")
        return True
    
    def update_execution_results(self, session_id: str, order_results: List[Dict[str, Any]]) -> bool:
        """Mettre à jour les résultats d'exécution"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        # Créer un mapping par alias pour retrouver les actions
        action_map = {action.alias: action for action in session.actions}
        
        for result in order_results:
            alias = result.get('alias')
            if alias in action_map:
                action = action_map[alias]
                action.executed = result.get('success', False)
                action.executed_usd = float(result.get('filled_usd', 0.0))
                action.executed_quantity = float(result.get('filled_quantity', 0.0))
                action.execution_price = float(result.get('avg_price', 0.0)) if result.get('avg_price') else None
                action.fees = float(result.get('fees', 0.0))
                action.status = result.get('status', 'unknown')
                action.error_message = result.get('error_message')
                action.platform = result.get('platform', '')
                action.execution_time = datetime.now(timezone.utc)
        
        # Mettre à jour les métriques de la session
        session.update_execution_metrics()
        
        logger.info(f"Updated execution results for session {session_id}")
        return True
    
    def complete_session(self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED,
                        error_message: Optional[str] = None) -> bool:
        """Marquer une session comme terminée"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.status = status
        session.completed_at = datetime.now(timezone.utc)
        
        if error_message:
            session.error_message = error_message
        
        # Sauvegarder l'historique
        self._save_history()
        
        logger.info(f"Completed session {session_id} with status {status.value}")
        return True
    
    def get_session(self, session_id: str) -> Optional[RebalanceSession]:
        """Obtenir une session par ID"""
        return self.sessions.get(session_id)
    
    def get_recent_sessions(self, limit: int = 50, 
                          days_back: Optional[int] = None) -> List[RebalanceSession]:
        """Obtenir les sessions récentes"""
        sessions = list(self.sessions.values())
        
        # Filtrer par date si demandé
        if days_back:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            sessions = [s for s in sessions if s.created_at >= cutoff]
        
        # Trier par date de création (plus récent d'abord)
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        
        return sessions[:limit]
    
    def get_performance_summary(self, days_back: int = 30) -> Dict[str, Any]:
        """Obtenir un résumé des performances"""
        sessions = self.get_recent_sessions(days_back=days_back)
        completed_sessions = [s for s in sessions if s.status == SessionStatus.COMPLETED]
        
        if not completed_sessions:
            return {"error": "No completed sessions found"}
        
        # Métriques d'exécution
        avg_success_rate = sum(s.execution_success_rate for s in completed_sessions) / len(completed_sessions)
        total_volume = sum(s.total_executed_volume for s in completed_sessions)
        total_fees = sum(s.total_fees for s in completed_sessions)
        
        # Analyse des performances
        performance_impacts = []
        for session in completed_sessions:
            impact = session.calculate_performance_impact()
            if impact:
                performance_impacts.append(impact)
        
        avg_performance_impact = 0.0
        if performance_impacts:
            avg_performance_impact = sum(p.get('total_value_change_pct', 0) for p in performance_impacts) / len(performance_impacts)
        
        # Analyse des stratégies CCS
        ccs_sessions = [s for s in completed_sessions if s.dynamic_targets_used and s.ccs_score is not None]
        ccs_performance = {}
        
        if ccs_sessions:
            # Grouper par ranges CCS
            ccs_ranges = {
                "accumulation": (70, 100),
                "neutral": (30, 70),
                "euphoria": (0, 30)
            }
            
            for range_name, (min_ccs, max_ccs) in ccs_ranges.items():
                range_sessions = [s for s in ccs_sessions if min_ccs <= s.ccs_score <= max_ccs]
                if range_sessions:
                    avg_performance = sum(
                        s.calculate_performance_impact().get('total_value_change_pct', 0) 
                        for s in range_sessions
                    ) / len(range_sessions)
                    ccs_performance[range_name] = {
                        "sessions_count": len(range_sessions),
                        "avg_performance_pct": avg_performance,
                        "avg_success_rate": sum(s.execution_success_rate for s in range_sessions) / len(range_sessions)
                    }
        
        return {
            "period_days": days_back,
            "total_sessions": len(sessions),
            "completed_sessions": len(completed_sessions),
            "success_rate_pct": (len(completed_sessions) / len(sessions)) * 100 if sessions else 0,
            "execution_metrics": {
                "avg_execution_success_rate": avg_success_rate,
                "total_volume_usd": total_volume,
                "total_fees_usd": total_fees,
                "fee_rate_pct": (total_fees / total_volume) * 100 if total_volume > 0 else 0
            },
            "performance_metrics": {
                "avg_performance_impact_pct": avg_performance_impact,
                "sessions_with_performance_data": len(performance_impacts)
            },
            "ccs_analysis": ccs_performance,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

# Instance globale du gestionnaire d'historique
history_manager = HistoryManager()