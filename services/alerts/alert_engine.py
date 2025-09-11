"""
Moteur d'alertes prédictives principal

Orchestre l'évaluation des alertes, l'escalade automatique, et la coordination
avec le système de gouvernance. Conçu pour être production-ready avec
anti-bruit robuste et observabilité complète.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import socket
import random
import json
import os
from pathlib import Path

from .alert_types import AlertEvaluator, Alert, AlertType, AlertSeverity
from .alert_storage import AlertStorage
from .prometheus_metrics import get_alert_metrics
from ..execution.phase_engine import PhaseEngine, Phase, PhaseState

logger = logging.getLogger(__name__)

@dataclass
class PhaseSnapshot:
    """Snapshot de phase avec timestamp pour le lag"""
    phase: Phase
    confidence: float
    persistence_count: int
    captured_at: datetime
    contradiction_index: float = 0.0

class PhaseAwareContext:
    """Gestionnaire de phase laggée avec persistance pour anti-oscillation"""
    
    def __init__(self, lag_minutes: int = 15, persistence_ticks: int = 3, metrics=None):
        self.lag_minutes = lag_minutes
        self.persistence_ticks = persistence_ticks
        self.phase_history: List[PhaseSnapshot] = []
        self.current_lagged_phase: Optional[PhaseSnapshot] = None
        self.metrics = metrics
        
    def update_phase(self, phase_state: PhaseState, contradiction_index: float = 0.0):
        """Met à jour l'historique de phase et calcule la phase laggée"""
        now = datetime.utcnow()
        
        # Ajouter le snapshot actuel
        snapshot = PhaseSnapshot(
            phase=phase_state.phase_now,
            confidence=phase_state.confidence,
            persistence_count=phase_state.persistence_count,
            captured_at=now,
            contradiction_index=contradiction_index
        )
        
        self.phase_history.append(snapshot)
        
        # Nettoyer l'historique > 2 * lag_minutes
        cutoff = now - timedelta(minutes=self.lag_minutes * 2)
        self.phase_history = [s for s in self.phase_history if s.captured_at > cutoff]
        
        # Calculer la phase laggée
        lag_cutoff = now - timedelta(minutes=self.lag_minutes)
        lagged_snapshots = [s for s in self.phase_history if s.captured_at <= lag_cutoff]
        
        if lagged_snapshots:
            # Prendre le plus récent dans la fenêtre laggée
            candidate = max(lagged_snapshots, key=lambda x: x.captured_at)
            
            # Vérifier la persistance: phases similaires consécutives
            if candidate.persistence_count >= self.persistence_ticks:
                # Record phase transition if phase changed
                if self.current_lagged_phase and self.current_lagged_phase.phase != candidate.phase:
                    if self.metrics:
                        self.metrics.record_phase_transition(
                            self.current_lagged_phase.phase.value.lower(),
                            candidate.phase.value.lower()
                        )
                
                self.current_lagged_phase = candidate
                
                # Update current phase metrics
                if self.metrics:
                    self.metrics.update_current_lagged_phase(
                        candidate.phase.value.lower(),
                        candidate.persistence_count
                    )
                
                logger.debug(f"Phase laggée mise à jour: {candidate.phase.value} "
                           f"(persistance: {candidate.persistence_count}, "
                           f"contradiction: {candidate.contradiction_index:.2f})")
        
        return self.current_lagged_phase
    
    def get_lagged_phase(self) -> Optional[PhaseSnapshot]:
        """Retourne la phase laggée actuelle"""
        return self.current_lagged_phase
    
    def is_phase_stable(self) -> bool:
        """Vérifie si la phase laggée est stable (persistance suffisante)"""
        if not self.current_lagged_phase:
            return False
        return self.current_lagged_phase.persistence_count >= self.persistence_ticks

class AlertMetrics:
    """Collecteur de métriques pour observabilité"""
    
    def __init__(self):
        self.counters = {
            "alerts_emitted_total": {},      # {type:severity: count}
            "alerts_suppressed_total": {},   # {reason: count}
            "policy_changes_total": {},      # {mode: count}
            "freeze_seconds_total": 0,
            "alerts_ack_total": 0,
            "alerts_snoozed_total": 0
        }
        
        self.gauges = {
            "last_alert_eval_ts": 0,
            "last_policy_change_ts": 0,
            "active_alerts_count": 0
        }
        
        self.labels = {
            "policy_origin": "manual"  # manual|alert|api
        }
    
    def increment(self, metric: str, labels: Dict[str, str] = None, value: int = 1):
        """Incrémente un compteur"""
        if labels:
            key = f"{metric}:{':'.join(f'{k}={v}' for k, v in labels.items())}"
        else:
            key = metric
        
        if metric not in self.counters:
            self.counters[metric] = {}
        
        self.counters[metric][key] = self.counters[metric].get(key, 0) + value
    
    def set_gauge(self, metric: str, value: float):
        """Met à jour une gauge"""
        self.gauges[metric] = value
    
    def set_label(self, label: str, value: str):
        """Met à jour un label"""
        self.labels[label] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne toutes les métriques au format JSON"""
        return {
            "counters": self.counters,
            "gauges": self.gauges,
            "labels": self.labels,
            "timestamp": datetime.now().isoformat()
        }

class AlertEngine:
    """
    Moteur d'alertes prédictives production-ready
    
    Features:
    - Évaluation périodique des signaux ML (consomme Phase 0)
    - Anti-bruit: hystérésis, rate-limit, dedup, budget quotidien
    - Escalade automatique (2x S2 → S3)
    - Snooze intelligent par type d'alerte
    - Single scheduler avec protection multi-worker
    - Observabilité complète (métriques Prometheus-compatibles)
    """
    
    def __init__(self, 
                 governance_engine = None,
                 storage: AlertStorage = None,
                 config: Dict[str, Any] = None,
                 config_file_path: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 prometheus_registry = None):
        
        self.governance_engine = governance_engine
        self.storage = storage or AlertStorage(redis_url=redis_url)
        
        # Configuration avec hot-reload
        self.config_file_path = config_file_path or os.path.join(os.path.dirname(__file__), "../../config/alerts_rules.json")
        self._config_mtime = 0
        self.config = config or self._load_config()
        
        # Métriques pour observabilité
        self.metrics = AlertMetrics()
        
        # Prometheus metrics pour monitoring externe
        self.prometheus_metrics = get_alert_metrics(registry=prometheus_registry)
        
        # Évaluateur de règles avec config
        self.evaluator = AlertEvaluator(self.config, metrics=self.prometheus_metrics)
        
        # Phase-aware context pour lag et persistance
        phase_config = self.config.get("alerting_config", {}).get("phase_aware", {})
        self.phase_aware_enabled = phase_config.get("enabled", True)
        if self.phase_aware_enabled:
            lag_minutes = phase_config.get("phase_lag_minutes", 15)
            persistence_ticks = phase_config.get("phase_persistence_ticks", 3)
            self.phase_context = PhaseAwareContext(lag_minutes, persistence_ticks, metrics=self.prometheus_metrics)
            self.phase_engine = PhaseEngine()
            
            # Initialize Phase 2A metrics
            self.prometheus_metrics.update_phase_aware_config(True, lag_minutes, persistence_ticks)
            
            logger.info(f"Phase-aware alerting enabled: lag={lag_minutes}min, persistence={persistence_ticks}")
        else:
            self.phase_context = None
            self.phase_engine = None
            
            # Record disabled state in metrics
            self.prometheus_metrics.update_phase_aware_config(False, 0, 0)
            
            logger.info("Phase-aware alerting disabled")
        
        # État interne
        self.host_id = f"{socket.gethostname()}:{os.getpid()}"
        self.is_scheduler = False
        self.scheduler_task = None
        self.last_evaluation = datetime.min
        
        # Cache pour éviter re-calculs
        self._escalation_cache = {}
        
        logger.info(f"AlertEngine initialized for host {self.host_id} with config: {self.config_file_path}")
    
    def get_lagged_phase(self) -> Optional[PhaseSnapshot]:
        """Retourne la phase laggée actuelle pour utilisation dans gating"""
        if self.phase_aware_enabled and self.phase_context:
            return self.phase_context.get_lagged_phase()
        return None
    
    def is_phase_stable(self) -> bool:
        """Vérifie si la phase laggée est stable (pour gating)"""
        if self.phase_aware_enabled and self.phase_context:
            return self.phase_context.is_phase_stable()
        return False
    
    def _check_phase_gating(self, alert_type: AlertType, signals: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Vérifie si l'alerte est gatée par la phase actuelle ou neutralisée par contradiction
        Retourne (allowed, reason)
        """
        if not self.phase_aware_enabled or not self.phase_context:
            return True, "phase_aware_disabled"
        
        lagged_phase = self.phase_context.get_lagged_phase()
        if not lagged_phase:
            return True, "no_stable_phase"
        
        # Vérifier neutralisation par contradiction
        contradiction_threshold = self.config.get("alerting_config", {}).get("phase_aware", {}).get("contradiction_neutralize_threshold", 0.70)
        contradiction_index = signals.get('contradiction_index', 0.0)
        
        if contradiction_index > contradiction_threshold:
            # Record contradiction neutralization metric
            self.prometheus_metrics.record_contradiction_neutralization(alert_type.value)
            logger.debug(f"Phase gating neutralized by high contradiction: {contradiction_index:.2f} > {contradiction_threshold}")
            return True, f"contradiction_neutralized_{contradiction_index:.2f}"
        
        # Récupérer la matrice de gating
        gating_matrix = self.config.get("alerting_config", {}).get("phase_aware", {}).get("gating_matrix", {})
        phase_config = gating_matrix.get(lagged_phase.phase.value, {})
        alert_gating = phase_config.get(alert_type.value, "enabled")
        
        if alert_gating == "disabled":
            # Record gating matrix block
            self.prometheus_metrics.record_gating_matrix_block(
                lagged_phase.phase.value.lower(),
                alert_type.value,
                "disabled"
            )
            return False, f"phase_gate_{lagged_phase.phase.value}"
        elif alert_gating == "attenuated":
            # Record gating matrix attenuation
            self.prometheus_metrics.record_gating_matrix_block(
                lagged_phase.phase.value.lower(),
                alert_type.value,
                "attenuated"
            )
            # Pour l'atténuation, on laisse passer mais avec un facteur réduit
            # (sera appliqué dans le calcul des seuils adaptatifs)
            return True, f"phase_attenuated_{lagged_phase.phase.value}"
        else:  # "enabled"
            return True, f"phase_enabled_{lagged_phase.phase.value}"
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier JSON avec fallback"""
        try:
            config_path = Path(self.config_file_path)
            
            if config_path.exists():
                self._config_mtime = config_path.stat().st_mtime
                
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # Validation basique de la structure
                if 'alerting_config' in file_config and 'alert_types' in file_config:
                    logger.info(f"Loaded configuration from {config_path}")
                    return file_config
                else:
                    logger.error(f"Invalid config structure in {config_path}, using defaults")
                    
            else:
                logger.warning(f"Config file {config_path} not found, using defaults")
                
        except Exception as e:
            logger.error(f"Error loading config from {self.config_file_path}: {e}, using defaults")
        
        return self._default_config()
    
    def _check_config_reload(self) -> bool:
        """Vérifie si le fichier de config a été modifié et le recharge"""
        try:
            config_path = Path(self.config_file_path)
            
            if not config_path.exists():
                return False
                
            current_mtime = config_path.stat().st_mtime
            
            if current_mtime > self._config_mtime:
                logger.info("Config file modified, reloading...")
                old_config_version = self.config.get('metadata', {}).get('config_version', 'unknown')
                
                self.config = self._load_config()
                
                # Recrée l'évaluateur avec nouvelle config
                self.evaluator = AlertEvaluator(self.config, metrics=self.prometheus_metrics)
                
                new_config_version = self.config.get('metadata', {}).get('config_version', 'unknown')
                logger.info(f"Config reloaded: {old_config_version} → {new_config_version}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking config reload: {e}")
            
        return False
    
    def _default_config(self) -> Dict[str, Any]:
        """Configuration par défaut (fallback)"""
        return {
            "alerting_config": {
                "enabled": True,
                "global_rate_limit_per_hour": 20,
                "escalation_window_minutes": 30,
                "dedup_window_minutes": 15,
                "daily_budgets": {"S1": 50, "S2": 12, "S3": 5}
            },
            "alert_types": {
                "VOL_Q90_CROSS": {"enabled": True, "thresholds": {"S2": 0.75, "S3": 0.85}},
                "REGIME_FLIP": {"enabled": True, "thresholds": {"S2": 0.70, "S3": 0.85}},
                "CORR_HIGH": {"enabled": True, "thresholds": {"S2": 0.80, "S3": 0.90}},
                "CONTRADICTION_SPIKE": {"enabled": True, "thresholds": {"S2": 0.65, "S3": 0.80}},
                "DECISION_DROP": {"enabled": True, "thresholds": {"S2": 0.60, "S3": 0.40}},
                "EXEC_COST_SPIKE": {"enabled": True, "thresholds": {"S2": 2.0, "S3": 3.5}}
            },
            "evaluation_interval_seconds": 60,
            "jitter_max_seconds": 10,
            "scheduler_lock_ttl_seconds": 90,
            "metadata": {"config_version": "default", "description": "Fallback configuration"}
        }
    
    async def start(self) -> bool:
        """
        Démarre le moteur d'alertes
        
        Tente d'acquérir le verrou scheduler. Un seul instance active par cluster.
        """
        try:
            # Tenter d'acquérir le verrou scheduler
            acquired = self.storage.acquire_scheduler_lock(
                self.host_id, 
                self.config["scheduler_lock_ttl_seconds"]
            )
            
            if not acquired:
                logger.info(f"Scheduler lock not acquired by {self.host_id}, running in standby mode")
                return False
            
            self.is_scheduler = True
            logger.info(f"Alert scheduler active on {self.host_id}")
            
            # Démarrer la boucle d'évaluation
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting alert engine: {e}")
            return False
    
    async def stop(self):
        """Arrête proprement le moteur d'alertes"""
        try:
            if self.scheduler_task and not self.scheduler_task.done():
                self.scheduler_task.cancel()
                try:
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass
            
            if self.is_scheduler:
                self.storage.release_scheduler_lock(self.host_id)
                logger.info(f"Alert scheduler stopped on {self.host_id}")
            
        except Exception as e:
            logger.error(f"Error stopping alert engine: {e}")
    
    async def _scheduler_loop(self):
        """
        Boucle principale d'évaluation des alertes
        
        Exécute périodiquement avec jitter anti-alignement
        """
        try:
            while True:
                start_time = datetime.now()
                
                try:
                    # Vérifier hot-reload config
                    self._check_config_reload()
                    
                    await self._evaluate_alerts()
                    await self._check_escalations()
                    await self._maintenance_tasks()
                    
                    self.metrics.set_gauge("last_alert_eval_ts", start_time.timestamp())
                    
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
                    self.metrics.increment("alerts_suppressed_total", {"reason": "evaluation_error"})
                
                # Sleep avec jitter pour éviter alignement multi-instances
                base_interval = self.config.get("evaluation_interval_seconds", 60)
                jitter = random.uniform(0, self.config.get("jitter_max_seconds", 10))
                sleep_time = base_interval + jitter
                
                await asyncio.sleep(sleep_time)
                
        except asyncio.CancelledError:
            logger.info("Alert scheduler loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Critical error in scheduler loop: {e}")
            raise
    
    async def _evaluate_alerts(self):
        """
        Évaluation principale des alertes
        
        Consomme les signaux ML depuis governance_engine (cache Phase 0)
        """
        import time
        start_time = time.time()
        
        try:
            if not self.governance_engine:
                logger.warning("No governance engine available for alert evaluation")
                return
            
            # Récupérer signaux ML depuis cache Phase 0 (pas de re-inference)
            current_state = await self.governance_engine.get_current_state()
            if not current_state or not current_state.signals:
                logger.warning("No ML signals available for alert evaluation")
                return
            
            signals_dict = {
                "volatility": current_state.signals.volatility,
                "regime": current_state.signals.regime,
                "correlation": current_state.signals.correlation,
                "sentiment": current_state.signals.sentiment,
                "decision_score": current_state.signals.decision_score,
                "confidence": current_state.signals.confidence,
                "contradiction_index": current_state.signals.contradiction_index,
                "execution_cost_bps": current_state.execution_policy.execution_cost_bps if current_state.execution_policy else 15
            }
            
            # Mettre à jour la phase laggée si phase-aware activé
            if self.phase_aware_enabled and self.phase_engine and self.phase_context:
                try:
                    # Obtenir la phase actuelle
                    current_phase_state = await self.phase_engine.get_current_phase()
                    if current_phase_state:
                        contradiction_index = signals_dict.get('contradiction_index', 0.0)
                        lagged_phase = self.phase_context.update_phase(current_phase_state, contradiction_index)
                        
                        if lagged_phase:
                            logger.debug(f"Phase laggée active: {lagged_phase.phase.value} "
                                       f"(persistance: {lagged_phase.persistence_count}, "
                                       f"contradiction: {lagged_phase.contradiction_index:.2f})")
                        else:
                            logger.debug("Aucune phase laggée stable disponible")
                except Exception as e:
                    logger.warning(f"Erreur mise à jour phase laggée: {e}")
            
            logger.debug(f"Evaluating alerts with signals: contradiction={signals_dict.get('contradiction_index', 0):.3f}, "
                        f"confidence={signals_dict.get('confidence', 0):.3f}")
            
            # Évaluer chaque type d'alerte
            for alert_type in AlertType:
                await self._evaluate_alert_type(alert_type, signals_dict)
            
            self.last_evaluation = datetime.now()
            
            # Record Prometheus metrics for evaluation run
            evaluation_duration = time.time() - start_time
            self.prometheus_metrics.record_engine_run(evaluation_duration)
            
        except Exception as e:
            logger.error(f"Error evaluating alerts: {e}")
            raise
    
    async def _evaluate_alert_type(self, alert_type: AlertType, signals: Dict[str, Any]):
        """Évalue un type d'alerte spécifique"""
        try:
            # Vérifier le gating par phase (incluant neutralisation contradiction)
            allowed, gating_reason = self._check_phase_gating(alert_type, signals)
            if not allowed:
                logger.debug(f"Alert {alert_type.value} suppressed by phase gating: {gating_reason}")
                self.metrics.increment("alerts_suppressed_total", {"reason": "phase_gate"})
                return
            
            # Préparer le contexte phase-aware pour seuils adaptatifs
            phase_context = None
            if self.phase_aware_enabled and self.phase_context:
                lagged_phase = self.phase_context.get_lagged_phase()
                if lagged_phase:
                    phase_context = {
                        "phase": lagged_phase.phase,
                        "gating_reason": gating_reason,
                        "contradiction_index": signals.get('contradiction_index', 0.0),
                        "phase_factors": self.config.get("alerting_config", {}).get("phase_aware", {}).get("phase_factors", {})
                    }
            
            # Évaluer avec hystérésis et seuils adaptatifs
            result = self.evaluator.evaluate_alert(alert_type, signals, phase_context)
            
            if not result:
                return  # Pas d'alerte à déclencher
            
            severity, alert_data = result
            
            # Vérifier budget quotidien
            if not self._check_daily_budget():
                logger.warning("Daily alert budget exceeded, suppressing alert")
                self.metrics.increment("alerts_suppressed_total", {"reason": "daily_budget"})
                return
            
            # Vérifier quiet hours
            if self._is_quiet_hours():
                logger.debug(f"Quiet hours active, suppressing {alert_type}:{severity}")
                self.metrics.increment("alerts_suppressed_total", {"reason": "quiet_hours"})
                return
            
            # Vérifier rate limit
            if not self.storage.check_rate_limit(alert_type, severity):
                logger.warning(f"Rate limit exceeded for {alert_type}:{severity}")
                self.metrics.increment("alerts_suppressed_total", {"reason": "rate_limit"})
                return
            
            # Générer l'alerte avec traçabilité gating
            alert_data.update({
                "gating_reason": gating_reason,
                "phase_snapshot": self.get_lagged_phase().__dict__ if self.get_lagged_phase() else None,
                "contradiction_index": signals.get('contradiction_index', 0.0)
            })
            alert = self._create_alert(alert_type, severity, alert_data)
            
            # Stocker avec dedup
            if self.storage.store_alert(alert):
                logger.info(f"Alert generated: {alert.id} ({alert_type}:{severity})")
                self.metrics.increment("alerts_emitted_total", 
                                     {"type": alert_type.value, "severity": severity.value})
                # Record Prometheus metrics
                self.prometheus_metrics.record_alert_generated(
                    alert_type=alert_type.value,
                    severity=severity.value,
                    source="ml_signals"
                )
            else:
                logger.debug(f"Alert {alert.id} deduplicated")
                self.metrics.increment("alerts_suppressed_total", {"reason": "dedup"})
            
        except Exception as e:
            logger.error(f"Error evaluating alert type {alert_type}: {e}")
    
    def _create_alert(self, alert_type: AlertType, severity: AlertSeverity, alert_data: Dict[str, Any]) -> Alert:
        """Crée une instance d'alerte avec action suggérée"""
        
        alert_id = f"ALR-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        # Récupérer action suggérée depuis règles
        rule = self.evaluator.alert_rules.get(alert_type)
        suggested_action = {}
        
        if rule:
            suggested_action = rule.suggested_actions.get(severity.value, {}).copy()
            if suggested_action.get("type") == "freeze":
                suggested_action["reason"] = f"Alert {alert_id} suggested freeze"
        
        return Alert(
            id=alert_id,
            alert_type=alert_type,
            severity=severity,
            data=alert_data,
            suggested_action=suggested_action
        )
    
    async def _check_escalations(self):
        """Vérifie et applique les règles d'escalade automatique"""
        try:
            escalation_config = self.config["escalation_rules"]
            s2_to_s3_config = escalation_config.get("S2_to_S3", {})
            threshold = s2_to_s3_config.get("count_threshold", 2)
            window_minutes = s2_to_s3_config.get("window_minutes", 30)
            
            # Récupérer alertes récentes S2
            active_alerts = self.storage.get_active_alerts(include_snoozed=False)
            now = datetime.now()
            cutoff = now - timedelta(minutes=window_minutes)
            
            # Grouper par type d'alerte
            s2_alerts_by_type = {}
            
            for alert in active_alerts:
                if (alert.severity == AlertSeverity.S2 and 
                    alert.created_at > cutoff and
                    not alert.escalation_count):  # Pas déjà escaladée
                    
                    alert_type = alert.alert_type
                    if alert_type not in s2_alerts_by_type:
                        s2_alerts_by_type[alert_type] = []
                    s2_alerts_by_type[alert_type].append(alert)
            
            # Vérifier seuils d'escalade
            for alert_type, alerts in s2_alerts_by_type.items():
                if len(alerts) >= threshold:
                    await self._escalate_to_s3(alert_type, alerts)
            
        except Exception as e:
            logger.error(f"Error checking escalations: {e}")
    
    async def _escalate_to_s3(self, alert_type: AlertType, source_alerts: List[Alert]):
        """Escalade automatique vers S3"""
        try:
            # Créer alerte S3 d'escalade
            escalation_data = {
                "escalation": True,
                "source_alert_count": len(source_alerts),
                "source_alert_ids": [alert.id for alert in source_alerts],
                "escalation_reason": f"{len(source_alerts)} {alert_type}:S2 alerts in window"
            }
            
            escalation_alert = Alert(
                id=f"ESC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}",
                alert_type=alert_type,
                severity=AlertSeverity.S3,
                data=escalation_data,
                escalation_sources=[alert.id for alert in source_alerts],
                escalation_count=1,
                suggested_action={
                    "type": "freeze",
                    "ttl_minutes": 360,
                    "reason": f"Escalated from {len(source_alerts)} S2 alerts"
                }
            )
            
            # Stocker l'alerte d'escalade
            if self.storage.store_alert(escalation_alert):
                logger.warning(f"ESCALATION: {alert_type} → S3 from {len(source_alerts)} S2 alerts")
                self.metrics.increment("alerts_emitted_total", 
                                     {"type": alert_type.value, "severity": "S3_escalation"})
                
                # Marquer alertes sources comme escaladées
                for source_alert in source_alerts:
                    self.storage._update_alert_field(source_alert.id, {
                        "escalation_count": 1,
                        "escalated_to": escalation_alert.id
                    })
            
        except Exception as e:
            logger.error(f"Error escalating to S3: {e}")
    
    async def _maintenance_tasks(self):
        """Tâches de maintenance périodiques"""
        try:
            # Purge automatique des alertes anciennes (une fois par heure)
            if datetime.now().minute == 0:
                purged = self.storage.purge_old_alerts()
                if purged > 0:
                    logger.info(f"Auto-purged {purged} old alerts")
            
            # Mettre à jour métriques
            active_alerts = self.storage.get_active_alerts()
            self.metrics.set_gauge("active_alerts_count", len(active_alerts))
            
        except Exception as e:
            logger.error(f"Error in maintenance tasks: {e}")
    
    def _check_daily_budget(self) -> bool:
        """Vérifie le budget quotidien d'alertes"""
        try:
            daily_budgets = self.config.get("alerting_config", {}).get("daily_budgets", {"S1": 50, "S2": 12, "S3": 5})
            total_budget = sum(daily_budgets.values())
            
            # Compter alertes émises aujourd'hui
            today = datetime.now().date()
            active_alerts = self.storage.get_active_alerts(include_snoozed=True)
            
            today_alerts = [
                alert for alert in active_alerts
                if alert.created_at.date() == today
            ]
            
            return len(today_alerts) < total_budget
            
        except Exception as e:
            logger.error(f"Error checking daily budget: {e}")
            return True  # En cas d'erreur, autoriser
    
    def _is_quiet_hours(self) -> bool:
        """Vérifie si on est en quiet hours"""
        try:
            # Pour l'instant, pas de quiet hours configurées - toujours retourner False
            # TODO: Ajouter quiet_hours dans la configuration si nécessaire
            return False
                
        except Exception as e:
            logger.error(f"Error checking quiet hours: {e}")
            return False
    
    # API publique pour actions manuelles
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acquitte manuellement une alerte"""
        success = self.storage.acknowledge_alert(alert_id, acknowledged_by)
        if success:
            self.metrics.increment("alerts_ack_total")
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return success
    
    async def snooze_alert(self, alert_id: str, minutes: int) -> bool:
        """Snooze une alerte pour X minutes"""
        success = self.storage.snooze_alert(alert_id, minutes)
        if success:
            self.metrics.increment("alerts_snoozed_total")
            logger.info(f"Alert {alert_id} snoozed for {minutes} minutes")
        return success
    
    async def mark_alert_applied(self, alert_id: str, applied_by: str) -> bool:
        """Marque une alerte comme appliquée (action exécutée)"""
        success = self.storage.mark_alert_applied(alert_id, applied_by)
        if success:
            logger.info(f"Alert {alert_id} marked as applied by {applied_by}")
            self.metrics.set_gauge("last_policy_change_ts", datetime.now().timestamp())
            self.metrics.set_label("policy_origin", "alert")
        return success
    
    def get_active_alerts(self) -> List[Alert]:
        """Retourne les alertes actives"""
        return self.storage.get_active_alerts()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne métriques complètes pour monitoring"""
        engine_metrics = self.metrics.get_metrics()
        storage_metrics = self.storage.get_metrics()
        
        return {
            "alert_engine": engine_metrics,
            "storage": storage_metrics,
            "host_info": {
                "host_id": self.host_id,
                "is_scheduler": self.is_scheduler,
                "last_evaluation": self.last_evaluation.isoformat() if self.last_evaluation != datetime.min else None
            }
        }