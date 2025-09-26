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
from .multi_timeframe import MultiTimeframeAnalyzer, TemporalGatingMatrix, Timeframe, TimeframeSignal
from .cross_asset_correlation import CrossAssetCorrelationAnalyzer, create_cross_asset_analyzer
from ..execution.phase_engine import PhaseEngine, Phase, PhaseState
from ..streaming.realtime_engine import RealtimeEngine

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
            "freeze_seconds_total": {},      # fixed: should be dict like others
            "alerts_ack_total": {},          # fixed: should be dict like others
            "alerts_snoozed_total": {}       # fixed: should be dict like others
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
                 prometheus_registry = None,
                 realtime_engine: Optional[RealtimeEngine] = None):
        
        self.governance_engine = governance_engine
        self.storage = storage or AlertStorage(redis_url=redis_url)
        
        # Phase 3B: Real-time streaming integration
        self.realtime_engine = realtime_engine or RealtimeEngine(redis_url=redis_url)
        
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
            
            # Phase 2B1: Multi-timeframe analyzer
            multi_tf_config = self.config.get("alerting_config", {}).get("multi_timeframe", {})
            self.multi_timeframe_enabled = multi_tf_config.get("enabled", True)
            if self.multi_timeframe_enabled:
                self.multi_timeframe_analyzer = MultiTimeframeAnalyzer(multi_tf_config)
                
                # Temporal gating matrix
                base_gating = phase_config.get("gating_matrix", {})
                self.temporal_gating = TemporalGatingMatrix(base_gating)
                
                logger.info("Multi-timeframe analysis enabled with temporal gating")
            else:
                self.multi_timeframe_analyzer = None
                self.temporal_gating = None
                logger.info("Multi-timeframe analysis disabled")
            
            # Initialize Phase 2A metrics
            self.prometheus_metrics.update_phase_aware_config(True, lag_minutes, persistence_ticks)
            
            # Initialize Phase 2B1 metrics
            if self.multi_timeframe_enabled:
                self.prometheus_metrics.update_multi_timeframe_config(True)
            
            # Phase 2B2: Cross-Asset Correlation analyzer
            cross_asset_config = self.config.get("alerting_config", {}).get("cross_asset_correlation", {})
            self.cross_asset_enabled = cross_asset_config.get("enabled", True)
            if self.cross_asset_enabled:
                self.cross_asset_analyzer = create_cross_asset_analyzer(cross_asset_config)
                logger.info("Cross-asset correlation analysis enabled")
            else:
                self.cross_asset_analyzer = None
                logger.info("Cross-asset correlation analysis disabled")
            
            # Phase 2C: ML Alert Predictor
            ml_predictor_config = self.config.get("alerting_config", {}).get("ml_alert_predictor", {})
            self.ml_predictor_enabled = ml_predictor_config.get("enabled", False)
            if self.ml_predictor_enabled:
                from .ml_alert_predictor import create_ml_alert_predictor
                self.ml_alert_predictor = create_ml_alert_predictor(ml_predictor_config)
                if self.ml_alert_predictor:
                    logger.info("ML Alert Predictor enabled - predictive alerts active")
                else:
                    logger.warning("ML Alert Predictor failed to initialize")
                    self.ml_predictor_enabled = False
            else:
                self.ml_alert_predictor = None
                logger.info("ML Alert Predictor disabled")
            
            # Phase 3A: Advanced Risk Engine
            risk_engine_config = self.config.get("alerting_config", {}).get("advanced_risk", {})
            self.risk_engine_enabled = risk_engine_config.get("enabled", False)
            if self.risk_engine_enabled:
                from services.risk.advanced_risk_engine import create_advanced_risk_engine
                self.risk_engine = create_advanced_risk_engine(risk_engine_config)
                if self.risk_engine:
                    logger.info("Advanced Risk Engine enabled - VaR/Stress testing active")
                else:
                    logger.warning("Advanced Risk Engine failed to initialize")
                    self.risk_engine_enabled = False
            else:
                self.risk_engine = None
                logger.info("Advanced Risk Engine disabled")
            
            # Phase 3B: Real-time Streaming Integration
            streaming_config = self.config.get("alerting_config", {}).get("realtime_streaming", {})
            self.streaming_enabled = streaming_config.get("enabled", True)  # Default enabled
            if self.streaming_enabled:
                logger.info("Phase 3B Real-time alert streaming enabled")
            else:
                logger.info("Phase 3B Real-time alert streaming disabled")
            
            logger.info(f"Phase-aware alerting enabled: lag={lag_minutes}min, persistence={persistence_ticks}")
        else:
            self.phase_context = None
            self.phase_engine = None
            self.multi_timeframe_analyzer = None
            self.temporal_gating = None
            self.cross_asset_analyzer = None  # Phase 2B2: Pas d'analyzer si phase-aware désactivé
            
            # Record disabled state in metrics
            self.prometheus_metrics.update_phase_aware_config(False, 0, 0)
            self.prometheus_metrics.update_multi_timeframe_config(False)
            
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
    
    def get_multi_timeframe_status(self) -> Dict[str, Any]:
        """Retourne le status du système multi-timeframe (Phase 2B1)"""
        if not self.multi_timeframe_enabled or not self.multi_timeframe_analyzer:
            return {
                "enabled": False,
                "reason": "Multi-timeframe analysis disabled"
            }
        
        status = self.multi_timeframe_analyzer.get_timeframe_status()
        status["enabled"] = True
        status["coherence_thresholds"] = self.multi_timeframe_analyzer.coherence_thresholds
        status["temporal_gating_enabled"] = self.temporal_gating is not None
        
        return status
    
    def is_phase_stable(self) -> bool:
        """Vérifie si la phase laggée est stable (pour gating)"""
        if self.phase_aware_enabled and self.phase_context:
            return self.phase_context.is_phase_stable()
        return False
    
    def _extract_assets_data_from_signals(self, signals: Dict[str, Any]) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Extrait les données d'assets (prix, volume) depuis les signaux ML
        
        Format attendu par CrossAssetCorrelationAnalyzer:
        {"BTC": {"price": 45000, "volume": 1000000}, "ETH": {...}}
        """
        try:
            assets_data = {}
            
            # Extraire depuis différentes sources dans les signaux
            if "prices" in signals:
                # Format direct: {"prices": {"BTC": 45000, "ETH": 3200, ...}}
                prices = signals["prices"]
                for asset, price in prices.items():
                    if isinstance(price, (int, float)) and price > 0:
                        assets_data[asset] = {
                            "price": float(price),
                            "volume": 1.0  # Volume par défaut si pas disponible
                        }
            
            elif "market_data" in signals:
                # Format market_data: {"market_data": {"BTC": {"price": 45000, "volume": 1000}, ...}}
                market_data = signals["market_data"]
                for asset, data in market_data.items():
                    if isinstance(data, dict):
                        price = data.get("price", 0)
                        volume = data.get("volume", 1.0)
                        if price > 0:
                            assets_data[asset] = {
                                "price": float(price),
                                "volume": float(volume)
                            }
            
            elif "volatility" in signals:
                # Fallback: générer prix simulé depuis volatility (pour tests)
                # Format: {"volatility": {"BTC": 0.45, "ETH": 0.52, ...}}
                base_prices = {"BTC": 45000, "ETH": 3200, "SOL": 110, "AVAX": 35, "ADA": 0.45}
                volatility_data = signals["volatility"]
                
                for asset, vol in volatility_data.items():
                    if asset in base_prices and isinstance(vol, (int, float)):
                        # Prix simulé avec variation basée sur volatilité
                        price_variation = 1.0 + (vol - 0.5) * 0.1  # ±5% variation max
                        simulated_price = base_prices[asset] * price_variation
                        
                        assets_data[asset] = {
                            "price": float(simulated_price),
                            "volume": 1000000.0  # Volume simulé
                        }
            
            return assets_data if assets_data else None
            
        except Exception as e:
            logger.warning(f"Error extracting assets data from signals: {e}")
            return None

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
        Ã‰valuation principale des alertes
        
        Consomme les signaux ML depuis governance_engine (cache Phase 0)
        """
        import time
        start_time = time.time()
        
        try:
            if not self.governance_engine:
                logger.warning("No governance engine available for alert evaluation")
                return
            
            # RÃ©cupÃ©rer signaux ML depuis cache Phase 0 (pas de re-inference)
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
            
            # Mettre Ã  jour la phase laggÃ©e si phase-aware activÃ©
            if self.phase_aware_enabled and self.phase_engine and self.phase_context:
                try:
                    # Obtenir la phase actuelle
                    current_phase_state = await self.phase_engine.get_current_phase()
                    if current_phase_state:
                        contradiction_index = signals_dict.get('contradiction_index', 0.0)
                        lagged_phase = self.phase_context.update_phase(current_phase_state, contradiction_index)
                        
                        if lagged_phase:
                            logger.debug(f"Phase laggÃ©e active: {lagged_phase.phase.value} "
                                       f"(persistance: {lagged_phase.persistence_count}, "
                                       f"contradiction: {lagged_phase.contradiction_index:.2f})")
                        else:
                            logger.debug("Aucune phase laggÃ©e stable disponible")
                except Exception as e:
                    logger.warning(f"Erreur mise Ã  jour phase laggÃ©e: {e}")
            
            logger.debug(f"Evaluating alerts with signals: contradiction={signals_dict.get('contradiction_index', 0):.3f}, "
                        f"confidence={signals_dict.get('confidence', 0):.3f}")
            
            # Ã‰valuer chaque type d'alerte
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
        """Évalue un type d'alerte spécifique avec analyse multi-timeframe"""
        try:
            # Phase 2B1: Multi-timeframe coherence check
            multi_timeframe_metadata = {}
            if self.multi_timeframe_enabled and self.multi_timeframe_analyzer:
                # Simuler signaux multi-timeframe pour cette évaluation
                # Dans un vrai système, ces signaux viendraient de data feeds temps réel
                current_timeframes = [Timeframe.H1, Timeframe.H4, Timeframe.D1]  # Timeframes principaux
                
                for tf in current_timeframes:
                    # Créer signal simulé pour ce timeframe
                    tf_signal = TimeframeSignal(
                        timeframe=tf,
                        alert_type=alert_type,
                        severity=AlertSeverity.S2,  # À déterminer par la logique réelle
                        threshold_value=0.75,
                        actual_value=signals.get('volatility', {}).get('BTC', 0.5),
                        confidence=signals.get('confidence', 0.7),
                        timestamp=datetime.utcnow(),
                        phase=self.get_lagged_phase().phase if self.get_lagged_phase() else None
                    )
                    self.multi_timeframe_analyzer.add_signal(tf_signal)
                
                # Vérifier cohérence multi-timeframe
                should_trigger, tf_metadata = self.multi_timeframe_analyzer.should_trigger_alert(
                    alert_type, AlertSeverity.S2
                )
                
                multi_timeframe_metadata = tf_metadata
                
                # Enregistrer métriques multi-timeframe
                coherence_score = tf_metadata.get("coherence_score", 0.5)
                self.prometheus_metrics.record_coherence_score(alert_type.value, coherence_score)
                
                # Déterminer le niveau de cohérence pour les métriques
                if coherence_score >= 0.80:
                    coherence_level = "high"
                elif coherence_score >= 0.60:
                    coherence_level = "medium"  
                elif coherence_score >= 0.40:
                    coherence_level = "low"
                else:
                    coherence_level = "divergent"
                
                if not should_trigger:
                    logger.debug(f"Alert {alert_type.value} suppressed by multi-timeframe analysis: {tf_metadata.get('reason')}")
                    self.metrics.increment("alerts_suppressed_total", {"reason": "multi_timeframe"})
                    
                    # Enregistrer suppression multi-timeframe
                    self.prometheus_metrics.record_multi_timeframe_suppression(
                        reason=tf_metadata.get("reason", "unknown"),
                        alert_type=alert_type.value,
                        coherence_level=coherence_level
                    )
                    return
                else:
                    # Enregistrer déclenchement multi-timeframe
                    self.prometheus_metrics.record_multi_timeframe_trigger(
                        reason=tf_metadata.get("reason", "unknown"),
                        alert_type=alert_type.value,
                        coherence_level=coherence_level
                    )
                    
                    # Enregistrer ratio d'accord des timeframes
                    agreement_ratio = tf_metadata.get("timeframe_agreement", 0.0)
                    self.prometheus_metrics.update_timeframe_agreement_ratio(
                        alert_type.value, agreement_ratio
                    )
            
            # Phase 2B2: Cross-asset correlation analysis
            cross_asset_metadata = {}
            if self.cross_asset_enabled and self.cross_asset_analyzer:
                # Mettre à jour les données prix/volumes pour l'analyzer
                assets_data = self._extract_assets_data_from_signals(signals)
                if assets_data:
                    self.cross_asset_analyzer.update_price_data(assets_data)
                
                # Analyser spécifiquement CORR_HIGH et CORR_SPIKE
                if alert_type == AlertType.CORR_HIGH:
                    # Calculer score de risque systémique pour CORR_HIGH
                    systemic_risk = self.cross_asset_analyzer.calculate_systemic_risk_score()
                    correlation_status = self.cross_asset_analyzer.get_status()
                    
                    cross_asset_metadata = {
                        "systemic_risk_score": systemic_risk,
                        "avg_correlation": correlation_status.avg_correlation,
                        "max_correlation": correlation_status.max_correlation,
                        "active_clusters": len(correlation_status.active_clusters)
                    }
                    
                    # Enrichir les signaux avec données cross-asset
                    if "correlation" not in signals:
                        signals["correlation"] = {}
                    signals["correlation"]["avg_correlation"] = correlation_status.avg_correlation
                    signals["correlation"]["systemic_risk"] = systemic_risk
                    
                elif alert_type == AlertType.CORR_SPIKE:
                    # Détecter spikes de corrélation
                    spikes = self.cross_asset_analyzer.detect_correlation_spikes()
                    
                    if spikes:
                        cross_asset_metadata = {
                            "spikes_count": len(spikes),
                            "max_spike_severity": max(s.severity for s in spikes),
                            "affected_pairs": [f"{s.asset_pair[0]}-{s.asset_pair[1]}" for s in spikes[:3]]
                        }
                        
                        # Enrichir signaux avec spikes détectés
                        signals["correlation_spikes"] = [
                            {
                                "asset_pair": f"{s.asset_pair[0]}-{s.asset_pair[1]}",
                                "absolute_change": s.absolute_change,
                                "relative_change": s.relative_change,
                                "severity": s.severity,
                                "timeframe": s.timeframe
                            }
                            for s in spikes
                        ]
                        
                        logger.info(f"Detected {len(spikes)} correlation spikes: {cross_asset_metadata['affected_pairs']}")
                    else:
                        # Pas de spikes détectés, pas besoin de déclencher
                        if alert_type == AlertType.CORR_SPIKE:
                            logger.debug("No correlation spikes detected, suppressing CORR_SPIKE alert")
                            return
            
            # Phase 2C: ML Alert Predictions
            ml_prediction_metadata = {}
            if self.ml_predictor_enabled and self.ml_alert_predictor:
                # Évaluer seulement les alertes prédictives
                predictive_types = {
                    AlertType.SPIKE_LIKELY, 
                    AlertType.REGIME_CHANGE_PENDING,
                    AlertType.CORRELATION_BREAKDOWN, 
                    AlertType.VOLATILITY_SPIKE_IMMINENT
                }
                
                if alert_type in predictive_types:
                    try:
                        # Extraire features pour prédiction ML
                        correlation_data = self._extract_correlation_data(signals)
                        price_data = self._extract_price_data(signals) 
                        market_data = self._extract_market_data(signals)
                        
                        features = self.ml_alert_predictor.extract_features(
                            correlation_data, price_data, market_data
                        )
                        
                        # Générer prédictions
                        default_horizon = self.config.get("alerting_config", {}).get("ml_alert_predictor", {}).get("default_horizon", "24h")
                        predictions = self.ml_alert_predictor.predict_alerts(
                            features, horizons=[default_horizon]
                        )
                        
                        # Chercher prédiction pour ce type d'alerte
                        matching_prediction = None
                        for pred in predictions:
                            if pred.alert_type.value == alert_type.value:
                                matching_prediction = pred
                                break
                        
                        if matching_prediction:
                            # Enrichir signaux avec prédiction ML
                            signals["ml_prediction"] = {
                                "probability": matching_prediction.probability,
                                "confidence": matching_prediction.confidence,
                                "horizon": matching_prediction.horizon.value,
                                "target_time": matching_prediction.target_time,
                                "severity_estimate": matching_prediction.severity_estimate,
                                "model_version": matching_prediction.model_version,
                                "features": matching_prediction.features
                            }

                            ml_prediction_metadata = {
                                "prediction_probability": matching_prediction.probability,
                                "model_confidence": matching_prediction.confidence,
                                "prediction_horizon": matching_prediction.horizon.value,
                                "assets_affected": matching_prediction.assets
                            }

                            logger.info(f"ML prediction for {alert_type.value}: "
                                      f"prob={matching_prediction.probability:.0%}, "
                                      f"confidence={matching_prediction.confidence:.0%}, "
                                      f"horizon={matching_prediction.horizon.value}")
                        else:
                            # Pas de prédiction pour ce type - suppresion
                            logger.debug(f"No ML prediction for {alert_type.value}, suppressing predictive alert")
                            return

                    except Exception as e:
                        logger.error(f"ML prediction error for {alert_type.value}: {e}")
                        return
            
            # Phase 3A: Advanced Risk Analysis
            risk_analysis_metadata = {}
            if self.risk_engine_enabled and self.risk_engine:
                # Évaluer seulement les alertes de risque avancé
                advanced_risk_types = {
                    AlertType.VAR_BREACH, 
                    AlertType.STRESS_TEST_FAILED,
                    AlertType.MONTE_CARLO_EXTREME, 
                    AlertType.RISK_CONCENTRATION
                }
                
                if alert_type in advanced_risk_types:
                    try:
                        # Obtenir portfolio actuel depuis governance
                        current_state = await self.governance_engine.get_current_state()
                        portfolio_weights: Dict[str, float] = {}
                        if current_state:
                            plan = getattr(current_state, "current_plan", None) or getattr(current_state, "proposed_plan", None)
                            if plan and getattr(plan, "targets", None):
                                cleaned_weights: Dict[str, float] = {}
                                for target in plan.targets:
                                    symbol = getattr(target, "symbol", None)
                                    raw_weight = getattr(target, "weight", None)
                                    if not symbol or raw_weight is None:
                                        continue
                                    try:
                                        cleaned_weights[symbol] = float(raw_weight)
                                    except (TypeError, ValueError):
                                        logger.debug(f"Skipping target {symbol} with invalid weight {raw_weight!r}")
                                if cleaned_weights:
                                    portfolio_weights = cleaned_weights
                        if not portfolio_weights and current_state and hasattr(current_state.execution_policy, "target_allocation"):
                            maybe_targets = getattr(current_state.execution_policy, "target_allocation", {})
                            if isinstance(maybe_targets, dict):
                                try:
                                    portfolio_weights = {k: float(v) for k, v in maybe_targets.items() if v is not None}
                                except (TypeError, ValueError):
                                    portfolio_weights = {}
                        if not portfolio_weights:
                            logger.debug("Advanced risk analysis skipped: no portfolio targets available")
                            return
                        portfolio_value = 100000  # TODO: Récupérer valeur réelle

                        if alert_type == AlertType.VAR_BREACH:
                            # Calculer VaR et vérifier limites
                            from services.risk.advanced_risk_engine import VaRMethod
                            var_result = self.risk_engine.calculate_var(
                                portfolio_weights, portfolio_value,
                                method=VaRMethod.PARAMETRIC, confidence_level=0.95
                            )

                            # Limites VaR (configurables)
                            var_limits = self.config.get("alerting_config", {}).get("advanced_risk", {}).get("var_limits", {
                                "daily_95": 0.05,  # 5% du portfolio
                                "daily_99": 0.08   # 8% du portfolio
                            })

                            var_limit_95 = portfolio_value * var_limits["daily_95"]
                            var_breach = var_result.var_absolute > var_limit_95

                            if var_breach:
                                signals["var_breach"] = {
                                    "var_current": var_result.var_absolute,
                                    "var_limit": var_limit_95,
                                    "var_method": var_result.method.value,
                                    "confidence_level": var_result.confidence_level,
                                    "var_ratio": var_result.var_absolute / var_limit_95,
                                    "horizon": var_result.horizon.value
                                }

                                risk_analysis_metadata = {
                                    "var_breach_severity": "critical" if var_result.var_absolute > var_limit_95 * 2 else "major",
                                    "var_excess": var_result.var_absolute - var_limit_95
                                }
                            else:
                                logger.debug("VaR within limits, suppressing VAR_BREACH alert")
                                return

                        elif alert_type == AlertType.STRESS_TEST_FAILED:
                            # Run stress tests
                            stress_results = self.risk_engine.run_stress_test(
                                portfolio_weights, portfolio_value
                            )

                            # Trouver le pire scénario
                            worst_scenario = min(stress_results, key=lambda x: x.portfolio_pnl_pct)
                            stress_threshold = -0.15  # -15% max acceptable loss

                            if worst_scenario.portfolio_pnl_pct < stress_threshold:
                                signals["stress_test_failed"] = {
                                    "stress_scenario": worst_scenario.scenario,
                                    "stress_loss": abs(worst_scenario.portfolio_pnl),
                                    "stress_loss_pct": abs(worst_scenario.portfolio_pnl_pct),
                                    "worst_asset": worst_scenario.worst_asset,
                                    "recovery_days": worst_scenario.recovery_time_days
                                }

                                risk_analysis_metadata = {
                                    "failed_scenarios": len([r for r in stress_results if r.portfolio_pnl_pct < stress_threshold]),
                                    "worst_loss_pct": abs(worst_scenario.portfolio_pnl_pct)
                                }
                            else:
                                logger.debug("All stress tests passed, suppressing STRESS_TEST_FAILED alert")
                                return

                        elif alert_type == AlertType.MONTE_CARLO_EXTREME:
                            # Monte Carlo simulation
                            mc_result = self.risk_engine.run_monte_carlo_simulation(
                                portfolio_weights, portfolio_value, horizon_days=30
                            )

                            # Seuil extrême (P5 outcome)
                            extreme_threshold = -0.25  # -25% loss
                            extreme_prob = mc_result.confidence_intervals["P5"] < extreme_threshold

                            if extreme_prob or mc_result.confidence_intervals["P1"] < -0.40:
                                signals["monte_carlo_extreme"] = {
                                    "mc_extreme_prob": abs(mc_result.confidence_intervals["P5"]),
                                    "mc_threshold": portfolio_value * 0.25,  # 25% threshold
                                    "max_dd_p99": mc_result.max_drawdown_p99,
                                    "horizon": mc_result.horizon_days
                                }

                                risk_analysis_metadata = {
                                    "simulation_count": mc_result.simulations_count,
                                    "worst_p1": mc_result.confidence_intervals["P1"]
                                }
                            else:
                                logger.debug("Monte Carlo within acceptable range, suppressing alert")
                                return

                        elif alert_type == AlertType.RISK_CONCENTRATION:
                            concentration = signals.get("concentration", 0.0)
                            top_assets = signals.get("top_contributors", [])
                            if concentration > 0.25:
                                signals["risk_concentration"] = {
                                    "concentration_ratio": concentration,
                                    "top_assets": top_assets[:5]
                                }
                                risk_analysis_metadata = {
                                    "concentration_ratio": concentration,
                                    "top_assets": top_assets[:3]
                                }
                            else:
                                logger.debug("Risk concentration within tolerance, suppressing alert")
                                return

                        else:
                            logger.debug(f"Unsupported advanced risk alert type: {alert_type}")
                            return
                    except Exception as e:
                        logger.error(f"Advanced risk analysis error for {alert_type.value}: {e}")
                        return
            
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
            
            # Générer l'alerte avec traçabilité gating et multi-timeframe
            alert_data.update({
                "gating_reason": gating_reason,
                "phase_snapshot": self.get_lagged_phase().__dict__ if self.get_lagged_phase() else None,
                "contradiction_index": signals.get('contradiction_index', 0.0),
                "multi_timeframe": multi_timeframe_metadata
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
        """Crée une instance d'alerte avec action suggérée et intégration governance caps"""

        alert_id = f"ALR-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"

        # Récupérer action suggérée depuis règles
        rule = self.evaluator.alert_rules.get(alert_type)
        suggested_action = {}

        if rule:
            suggested_action = rule.suggested_actions.get(severity.value, {}).copy()
            if suggested_action.get("type") == "freeze":
                suggested_action["reason"] = f"Alert {alert_id} suggested freeze"

        alert = Alert(
            id=alert_id,
            alert_type=alert_type,
            severity=severity,
            data=alert_data,
            suggested_action=suggested_action
        )

        # Phase 1B: Intégration AlertEngine → caps pour alertes systémiques
        self._apply_systemic_alert_cap_reduction(alert, alert_data)

        # Phase 3B: Broadcast alert en temps réel
        asyncio.create_task(self._broadcast_alert_realtime(alert))

        return alert

    def _apply_systemic_alert_cap_reduction(self, alert: Alert, alert_data: Dict[str, Any]) -> None:
        """
        Phase 1B: Applique réduction cap pour alertes systémiques
        Conditions: VaR95>4% OU Contradiction>55% OU Backend stale>60min
        """
        try:
            if not self.governance_engine:
                return

            # Définir les conditions systémiques qui déclenchent réduction cap
            systemic_conditions = []

            # Condition 1: VaR95 > 4%
            var_95 = alert_data.get("current_value")
            if alert.alert_type in [AlertType.VAR_BREACH] and isinstance(var_95, (int, float)) and var_95 > 0.04:
                systemic_conditions.append(f"VaR95>{var_95:.1%}")

            # Condition 2: Contradiction > 55%
            contradiction = alert_data.get("contradiction_index", alert_data.get("current_value"))
            if alert.alert_type in [AlertType.CONTRADICTION_SPIKE] and isinstance(contradiction, (int, float)) and contradiction > 0.55:
                systemic_conditions.append(f"Contradiction>{contradiction:.1%}")

            # Condition 3: Backend stale > 60min (simulé avec execution cost spike pour l'instant)
            if alert.alert_type in [AlertType.EXEC_COST_SPIKE] and alert.severity in [AlertSeverity.S2, AlertSeverity.S3]:
                # Simuler détection backend stale via cost spike persistant
                systemic_conditions.append("Backend_stale_60min")

            # Appliquer réduction cap si conditions systémiques remplies
            if systemic_conditions:
                reduction_percentage = 0.03  # -3 points
                reason = " OU ".join(systemic_conditions)

                success = self.governance_engine.apply_alert_cap_reduction(
                    reduction_percentage=reduction_percentage,
                    alert_id=alert.id,
                    reason=reason
                )

                if success:
                    logger.warning(f"Systemic alert cap reduction applied: -3pts by {alert.id} ({reason})")
                    # Ajouter metadata à l'alerte pour traçabilité
                    alert.data["cap_reduction_applied"] = {
                        "percentage": reduction_percentage,
                        "reason": reason,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    logger.info(f"Systemic alert cap reduction not applied for {alert.id} (cooldown ou plus forte réduction active)")

        except Exception as e:
            logger.error(f"Error applying systemic alert cap reduction for {alert.id}: {e}")
    
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
    
    # Phase 2C: Helper methods for ML data extraction
    
    def _extract_correlation_data(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait données de corrélation pour features ML"""
        if self.cross_asset_enabled and self.cross_asset_analyzer:
            try:
                # Obtenir status corrélation actuel
                status = self.cross_asset_analyzer.get_correlation_status("1h")
                return {
                    "correlation_matrices": {
                        "1h": status.get("matrix", {}).get("correlation_matrix", np.array([])),
                        "4h": np.array([]),  # TODO: implémenter multi-timeframe 
                        "1d": np.array([])
                    },
                    "correlation_history": getattr(self.cross_asset_analyzer, '_correlation_history', {}),
                    "systemic_risk": status.get("risk_assessment", {}),
                    "assets": status.get("matrix", {}).get("assets", [])
                }
            except Exception as e:
                logger.warning(f"Error extracting correlation data: {e}")
        
        # Données par défaut si cross-asset désactivé
        return {
            "correlation_matrices": {"1h": np.array([]), "4h": np.array([]), "1d": np.array([])},
            "correlation_history": {},
            "systemic_risk": {"concentration": 0.0},
            "assets": []
        }
    
    def _extract_price_data(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait données de prix pour features ML"""
        # Pour MVP, utiliser données simplifiées depuis signaux
        price_data = {}
        
        # Extraire volatilités comme proxy des prix
        volatility_signals = signals.get("volatility", {})
        if isinstance(volatility_signals, dict):
            for asset, vol in volatility_signals.items():
                # Simuler données prix basées sur volatilité
                price_data[asset] = {
                    "current_price": vol * 50000,  # Normalisation approximative
                    "volatility_1h": vol,
                    "volatility_4h": vol * 1.2,
                    "historical_prices": [vol * 50000 * (1 + 0.01 * i) for i in range(-10, 1)]
                }
        
        return price_data
    
    def _extract_market_data(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """Extrait données macro pour features ML"""
        return {
            "fear_greed_index": 50,  # Neutre par défaut
            "funding_rates": {"BTC": 0.01, "ETH": 0.01},
            "market_sentiment": signals.get("sentiment", {}).get("composite", 0.5),
            "regime_state": signals.get("regime", {}).get("current_regime", "normal"),
            "decision_confidence": signals.get("confidence", 0.75)
        }
    
    # Phase 3B: Real-time Streaming Integration Methods
    
    async def _get_realtime_broadcaster(self):
        """Get Phase 3B RealtimeEngine for broadcasting"""
        if not self.streaming_enabled:
            return None
            
        if self.realtime_engine is None:
            logger.warning("Phase 3B RealtimeEngine not available")
            return None
            
        # Initialize if needed
        try:
            if not hasattr(self.realtime_engine, '_initialized') or not self.realtime_engine._initialized:
                await self.realtime_engine.initialize()
                logger.debug("Phase 3B RealtimeEngine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Phase 3B RealtimeEngine: {e}")
            return None
                
        return self.realtime_engine
    
    async def _broadcast_alert_realtime(self, alert: Alert):
        """Diffuse une alerte en temps réel via Phase 3B WebSocket + Redis Streams"""
        if not self.streaming_enabled:
            return
        
        try:
            realtime_engine = await self._get_realtime_broadcaster()
            if realtime_engine:
                # Create stream event for the alert
                event_data = {
                    "alert_id": alert.id,
                    "type": alert.alert_type.value,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "context": alert.context,
                    "timestamp": alert.created_at.isoformat(),
                    "source": "alert_engine"
                }
                
                # Broadcast via Phase 3B streaming
                success = await realtime_engine.broadcast_event(
                    event_type="alert_triggered",
                    data=event_data,
                    stream_name="alerts"
                )
                
                if success:
                    logger.debug(f"Successfully broadcasted alert {alert.id} via Phase 3B streaming")
                    self.metrics.increment("streaming_broadcasts_success")
                else:
                    logger.warning(f"Failed to broadcast alert {alert.id} via Phase 3B streaming")
                    self.metrics.increment("streaming_broadcasts_failed")
            
        except Exception as e:
            logger.error(f"Error broadcasting alert {alert.id} via Phase 3B: {e}")
            self.metrics.increment("streaming_broadcasts_failed")
    
    async def broadcast_risk_event(self, event_type: str, data: Dict[str, Any], severity: str = "S2"):
        """
        API publique pour broadcaster des événements de risque personnalisés
        Utilisé notamment par Phase 3A Advanced Risk Engine
        """
        if not self.streaming_enabled:
            return False
        
        try:
            realtime_engine = await self._get_realtime_broadcaster()
            if realtime_engine:
                # Create stream event for risk event
                event_data = {
                    "event_type": event_type,
                    "severity": severity,
                    "timestamp": datetime.now().isoformat(),
                    "source": "risk_engine",
                    **data
                }
                
                success = await realtime_engine.broadcast_event(
                    event_type="risk_event",
                    data=event_data,
                    stream_name="risk_events"
                )
                
                if success:
                    self.metrics.increment("streaming_risk_events_success")
                    logger.debug(f"Broadcasted risk event via Phase 3B: {event_type}")
                else:
                    self.metrics.increment("streaming_risk_events_failed")
                return success
            
        except Exception as e:
            logger.error(f"Error broadcasting risk event {event_type} via Phase 3B: {e}")
            self.metrics.increment("streaming_risk_events_failed")
        
        return False
    
    async def broadcast_system_status(self, additional_data: Dict[str, Any] = None):
        """Diffuse le status du système d'alertes"""
        if not self.streaming_enabled:
            return False
        
        try:
            realtime_engine = await self._get_realtime_broadcaster()
            if realtime_engine:
                status_data = {
                    "alert_engine": {
                        "is_scheduler": self.is_scheduler,
                        "last_evaluation": self.last_evaluation.isoformat() if self.last_evaluation != datetime.min else None,
                        "active_alerts_count": len(self.get_active_alerts()),
                        "phase_aware_enabled": self.phase_aware_enabled,
                        "multi_timeframe_enabled": getattr(self, 'multi_timeframe_enabled', False),
                        "cross_asset_enabled": getattr(self, 'cross_asset_enabled', False),
                        "ml_predictor_enabled": getattr(self, 'ml_predictor_enabled', False),
                        "risk_engine_enabled": getattr(self, 'risk_engine_enabled', False),
                        "realtime_streaming_enabled": self.streaming_enabled
                    },
                    "timestamp": datetime.now().isoformat(),
                    "source": "alert_engine"
                }
                
                if additional_data:
                    status_data.update(additional_data)
                
                return await realtime_engine.broadcast_event(
                    event_type="system_status",
                    data=status_data,
                    stream_name="system_status"
                )
            
        except Exception as e:
            logger.error(f"Error broadcasting system status: {e}")
        
        return False
