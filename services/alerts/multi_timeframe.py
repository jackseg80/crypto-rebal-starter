"""
Multi-Timeframe Alert Analysis System - Phase 2B1

Système d'analyse multi-timeframe pour alertes coordonnées avec détection
de divergences temporelles et scoring de cohérence.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import statistics
import json

from .alert_types import AlertType, AlertSeverity, Alert
from ..execution.phase_engine import Phase

logger = logging.getLogger(__name__)

class Timeframe(Enum):
    """Timeframes supportés pour analyse multi-temporelle"""
    M1 = "1m"
    M5 = "5m" 
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

@dataclass
class TimeframeSignal:
    """Signal d'alerte sur un timeframe spécifique"""
    timeframe: Timeframe
    alert_type: AlertType
    severity: AlertSeverity
    threshold_value: float
    actual_value: float
    confidence: float
    timestamp: datetime
    phase: Optional[Phase] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CoherenceScore:
    """Score de cohérence entre timeframes pour un type d'alerte"""
    alert_type: AlertType
    overall_score: float  # 0-1, 1 = parfaitement cohérent
    timeframe_agreement: float  # % de timeframes en accord
    divergence_severity: float  # 0-1, mesure les divergences
    dominant_timeframe: Optional[Timeframe]
    conflicting_signals: List[Tuple[Timeframe, Timeframe]]
    calculated_at: datetime

class MultiTimeframeAnalyzer:
    """Analyseur multi-timeframe avec détection de divergences"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timeframes = [
            Timeframe.M1, Timeframe.M5, Timeframe.M15, 
            Timeframe.H1, Timeframe.H4, Timeframe.D1
        ]
        
        # Configuration des poids par timeframe (H1/H4 dominants)
        self.timeframe_weights = {
            Timeframe.M1: 0.05,
            Timeframe.M5: 0.10, 
            Timeframe.M15: 0.15,
            Timeframe.H1: 0.30,   # Timeframe principal
            Timeframe.H4: 0.25,   # Timeframe principal 
            Timeframe.D1: 0.15
        }
        
        # Seuils de cohérence
        self.coherence_thresholds = {
            "high_coherence": 0.80,
            "medium_coherence": 0.60,
            "low_coherence": 0.40,
            "divergence_alert": 0.30
        }
        
        # Histoire des signaux par timeframe
        self.signal_history: Dict[Timeframe, List[TimeframeSignal]] = {
            tf: [] for tf in self.timeframes
        }
        
    def add_signal(self, signal: TimeframeSignal):
        """Ajoute un signal à l'historique du timeframe"""
        if signal.timeframe not in self.signal_history:
            self.signal_history[signal.timeframe] = []
            
        self.signal_history[signal.timeframe].append(signal)
        
        # Nettoyer l'historique (garder 24h max)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.signal_history[signal.timeframe] = [
            s for s in self.signal_history[signal.timeframe] 
            if s.timestamp > cutoff
        ]
        
    def calculate_coherence_score(self, alert_type: AlertType, 
                                lookback_minutes: int = 60) -> CoherenceScore:
        """Calcule le score de cohérence pour un type d'alerte"""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=lookback_minutes)
        
        # Collecter les signaux récents par timeframe
        recent_signals: Dict[Timeframe, List[TimeframeSignal]] = {}
        for tf in self.timeframes:
            recent_signals[tf] = [
                s for s in self.signal_history[tf]
                if s.timestamp > cutoff and s.alert_type == alert_type
            ]
        
        if not any(recent_signals.values()):
            return CoherenceScore(
                alert_type=alert_type,
                overall_score=0.5,  # Neutre si pas de données
                timeframe_agreement=0.0,
                divergence_severity=0.0,
                dominant_timeframe=None,
                conflicting_signals=[],
                calculated_at=now
            )
            
        # Analyser l'accord entre timeframes
        timeframe_severities = {}
        timeframe_directions = {}  # 1 = bullish/up, -1 = bearish/down, 0 = neutral
        
        for tf, signals in recent_signals.items():
            if signals:
                # Prendre le signal le plus récent
                latest_signal = max(signals, key=lambda x: x.timestamp)
                timeframe_severities[tf] = latest_signal.severity
                
                # Déterminer la direction basée sur actual_value vs threshold
                if latest_signal.actual_value > latest_signal.threshold_value:
                    timeframe_directions[tf] = 1
                elif latest_signal.actual_value < latest_signal.threshold_value:
                    timeframe_directions[tf] = -1
                else:
                    timeframe_directions[tf] = 0
        
        # Calculer l'accord directionnel
        if timeframe_directions:
            directions = list(timeframe_directions.values())
            dominant_direction = max(set(directions), key=directions.count)
            agreement_count = sum(1 for d in directions if d == dominant_direction)
            timeframe_agreement = agreement_count / len(directions)
        else:
            timeframe_agreement = 0.0
            
        # Déterminer le timeframe dominant (plus de poids + direction majoritaire)
        dominant_timeframe = None
        max_weighted_influence = 0
        
        for tf, direction in timeframe_directions.items():
            if direction == dominant_direction:
                weighted_influence = self.timeframe_weights.get(tf, 0.1)
                if weighted_influence > max_weighted_influence:
                    max_weighted_influence = weighted_influence
                    dominant_timeframe = tf
        
        # Détecter les conflits entre timeframes importants
        conflicting_signals = []
        important_timeframes = [Timeframe.H1, Timeframe.H4, Timeframe.D1]
        
        for i, tf1 in enumerate(important_timeframes):
            for tf2 in important_timeframes[i+1:]:
                if (tf1 in timeframe_directions and tf2 in timeframe_directions and
                    timeframe_directions[tf1] != timeframe_directions[tf2] and
                    timeframe_directions[tf1] != 0 and timeframe_directions[tf2] != 0):
                    conflicting_signals.append((tf1, tf2))
        
        # Calculer la sévérité des divergences
        divergence_severity = len(conflicting_signals) / len(important_timeframes)
        
        # Score de cohérence global
        overall_score = (
            timeframe_agreement * 0.6 +  # Accord directionnel
            (1 - divergence_severity) * 0.3 +  # Absence de divergences
            (max_weighted_influence * 2) * 0.1  # Force du timeframe dominant
        )
        
        return CoherenceScore(
            alert_type=alert_type,
            overall_score=min(overall_score, 1.0),
            timeframe_agreement=timeframe_agreement,
            divergence_severity=divergence_severity,
            dominant_timeframe=dominant_timeframe,
            conflicting_signals=conflicting_signals,
            calculated_at=now
        )
        
    def should_trigger_alert(self, alert_type: AlertType, 
                           base_severity: AlertSeverity) -> Tuple[bool, Dict[str, Any]]:
        """Détermine si une alerte doit être déclenchée basée sur cohérence multi-timeframe"""
        coherence = self.calculate_coherence_score(alert_type)
        
        # Logique de décision basée sur la cohérence
        trigger_decision = False
        adjustment_factors = {}
        
        if coherence.overall_score >= self.coherence_thresholds["high_coherence"]:
            # Haute cohérence - déclencher avec confiance élevée
            trigger_decision = True
            adjustment_factors["confidence_boost"] = 0.2
            adjustment_factors["reason"] = "high_timeframe_coherence"
            
        elif coherence.overall_score >= self.coherence_thresholds["medium_coherence"]:
            # Cohérence moyenne - déclencher si timeframe dominant agree
            if coherence.dominant_timeframe and coherence.timeframe_agreement >= 0.6:
                trigger_decision = True
                adjustment_factors["confidence_neutral"] = 0.0
                adjustment_factors["reason"] = "dominant_timeframe_agreement"
            else:
                trigger_decision = False
                adjustment_factors["reason"] = "insufficient_agreement"
                
        elif coherence.overall_score >= self.coherence_thresholds["low_coherence"]:
            # Faible cohérence - déclencher seulement pour S3 (critiques)
            if base_severity == AlertSeverity.S3:
                trigger_decision = True
                adjustment_factors["confidence_penalty"] = -0.1
                adjustment_factors["reason"] = "low_coherence_critical_only"
            else:
                trigger_decision = False
                adjustment_factors["reason"] = "low_coherence_suppressed"
                
        else:
            # Divergence significative - supprimer les alertes non-critiques
            if base_severity == AlertSeverity.S3 and coherence.divergence_severity < 0.8:
                trigger_decision = True
                adjustment_factors["confidence_penalty"] = -0.2
                adjustment_factors["reason"] = "divergence_critical_override"
            else:
                trigger_decision = False
                adjustment_factors["reason"] = "high_divergence_suppressed"
        
        # Métadonnées pour debugging et metrics
        metadata = {
            "coherence_score": coherence.overall_score,
            "timeframe_agreement": coherence.timeframe_agreement,
            "divergence_severity": coherence.divergence_severity,
            "dominant_timeframe": coherence.dominant_timeframe.value if coherence.dominant_timeframe else None,
            "conflicting_signals": [
                (tf1.value, tf2.value) for tf1, tf2 in coherence.conflicting_signals
            ],
            "adjustment_factors": adjustment_factors
        }
        
        # Ajouter les adjustment_factors directement dans metadata pour les tests
        for key, value in adjustment_factors.items():
            metadata[key] = value
        
        return trigger_decision, metadata
        
    def get_timeframe_status(self) -> Dict[str, Any]:
        """Retourne le status actuel de tous les timeframes"""
        now = datetime.utcnow()
        status = {
            "timestamp": now.isoformat(),
            "timeframes": {},
            "overall_health": "healthy"
        }
        
        for tf in self.timeframes:
            recent_signals = [
                s for s in self.signal_history[tf]
                if s.timestamp > now - timedelta(minutes=30)
            ]
            
            status["timeframes"][tf.value] = {
                "signal_count_30min": len(recent_signals),
                "last_signal": recent_signals[-1].timestamp.isoformat() if recent_signals else None,
                "active_alert_types": list(set(s.alert_type.value for s in recent_signals))
            }
        
        # Détecter les timeframes silencieux (problème potentiel)
        silent_timeframes = [
            tf.value for tf in self.timeframes
            if len([s for s in self.signal_history[tf] 
                   if s.timestamp > now - timedelta(hours=1)]) == 0
        ]
        
        if len(silent_timeframes) > 2:
            status["overall_health"] = "degraded"
            status["silent_timeframes"] = silent_timeframes
            
        return status

class TemporalGatingMatrix:
    """Extension de la gating matrix avec dimension temporelle"""
    
    def __init__(self, base_gating_matrix: Dict[str, Dict[str, str]]):
        self.base_matrix = base_gating_matrix
        
        # Règles temporelles: certain timeframes peuvent override la base matrix
        self.temporal_overrides = {
            # Pour les alertes de volatilité, timeframes courts plus restrictifs
            "VOL_Q90_CROSS": {
                Timeframe.M1: "attenuated",  # M1 souvent bruyant
                Timeframe.M5: "attenuated",  # M5 souvent bruyant
                Timeframe.H1: "enabled",     # H1 timeframe de référence
                Timeframe.H4: "enabled",     # H4 timeframe de référence
                Timeframe.D1: "enabled"      # D1 signal fort
            },
            
            # Pour les signaux de régime, timeframes longs plus fiables
            "REGIME_FLIP": {
                Timeframe.M1: "disabled",    # Trop de bruit
                Timeframe.M5: "disabled",    # Trop de bruit
                Timeframe.M15: "attenuated", 
                Timeframe.H1: "enabled",
                Timeframe.H4: "enabled",
                Timeframe.D1: "enabled"      # Signal le plus fiable
            }
        }
    
    def check_temporal_gating(self, phase: str, alert_type: str, 
                            timeframe: Timeframe) -> Tuple[bool, str]:
        """Vérifie le gating avec dimension temporelle"""
        
        # Commencer par la règle de base
        base_rule = self.base_matrix.get(phase, {}).get(alert_type, "enabled")
        
        # Appliquer les overrides temporels si présents
        temporal_rule = None
        if alert_type in self.temporal_overrides:
            temporal_rule = self.temporal_overrides[alert_type].get(timeframe)
        
        # La règle la plus restrictive gagne
        if temporal_rule:
            if base_rule == "disabled" or temporal_rule == "disabled":
                final_rule = "disabled"
            elif base_rule == "attenuated" or temporal_rule == "attenuated":
                final_rule = "attenuated"
            else:
                final_rule = "enabled"
        else:
            final_rule = base_rule
            
        # Déterminer si l'alerte doit passer
        allowed = final_rule in ["enabled", "attenuated"]
        
        reason = f"phase:{phase},timeframe:{timeframe.value},base:{base_rule}"
        if temporal_rule:
            reason += f",temporal:{temporal_rule},final:{final_rule}"
        else:
            reason += f",final:{final_rule}"
            
        return allowed, reason