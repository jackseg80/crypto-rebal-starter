"""
Types d'alertes et définitions pour le système prédictif

Définit les 6 types d'alertes principaux avec leurs seuils adaptatifs
et le mapping gravité → actions suggérées.
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

class AlertSeverity(str, Enum):
    """Niveaux de gravité des alertes"""
    S1 = "S1"  # Info - ACK uniquement
    S2 = "S2"  # Majeur - Suggère Slow policy
    S3 = "S3"  # Critique - Suggère Freeze

class AlertType(str, Enum):
    """Types d'alertes prédictives basées sur les signaux ML"""
    VOL_Q90_CROSS = "VOL_Q90_CROSS"           # Volatilité dépasse Q90
    REGIME_FLIP = "REGIME_FLIP"               # Changement de régime marché  
    CORR_HIGH = "CORR_HIGH"                   # Corrélation systémique élevée
    CONTRADICTION_SPIKE = "CONTRADICTION_SPIKE" # Index de contradiction élevé
    DECISION_DROP = "DECISION_DROP"           # Chute de confiance decision score
    EXEC_COST_SPIKE = "EXEC_COST_SPIKE"       # Coûts d'exécution anormaux

class AlertRule(BaseModel):
    """Règle de déclenchement pour un type d'alerte"""
    alert_type: AlertType
    base_threshold: float = Field(..., description="Seuil de base")
    adaptive_multiplier: float = Field(default=1.0, description="Multiplicateur adaptatif")
    hysteresis_minutes: int = Field(default=5, ge=1, le=60, description="Persistance requise")
    severity_thresholds: Dict[str, float] = Field(..., description="Seuils par gravité")
    suggested_actions: Dict[str, Dict[str, Any]] = Field(..., description="Actions suggérées")

class Alert(BaseModel):
    """Instance d'alerte générée"""
    id: str = Field(..., description="ID unique alerte")
    alert_type: AlertType
    severity: AlertSeverity
    created_at: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(default_factory=dict, description="Données contextuelles")
    
    # État de l'alerte
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    snooze_until: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Action suggérée
    suggested_action: Dict[str, Any] = Field(default_factory=dict)
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None
    
    # Escalade
    escalation_sources: list[str] = Field(default_factory=list, description="IDs alertes sources")
    escalation_count: int = Field(default=0, description="Nombre d'escalades")

class AlertEvaluator:
    """Évaluateur de règles d'alertes avec hystérésis et seuils adaptatifs"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alert_rules = self._load_alert_rules()
        self._evaluation_history = {}  # Pour hystérésis
        
    def _load_alert_rules(self) -> Dict[AlertType, AlertRule]:
        """Charge les règles d'alertes depuis la config"""
        rules = {}
        
        # VOL_Q90_CROSS - Volatilité dépasse quantile 90
        rules[AlertType.VOL_Q90_CROSS] = AlertRule(
            alert_type=AlertType.VOL_Q90_CROSS,
            base_threshold=0.15,  # 15% volatilité de base
            adaptive_multiplier=0.5,  # Ajustement selon moyenne
            hysteresis_minutes=5,
            severity_thresholds={
                "S1": 0.20,  # 20% vol
                "S2": 0.35,  # 35% vol  
                "S3": 0.50   # 50% vol
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.04, "ramp_hours": 24},
                "S3": {"type": "freeze", "ttl_minutes": 360}
            }
        )
        
        # REGIME_FLIP - Changement de régime marché
        rules[AlertType.REGIME_FLIP] = AlertRule(
            alert_type=AlertType.REGIME_FLIP,
            base_threshold=0.6,  # 60% probabilité minimum
            adaptive_multiplier=1.0,
            hysteresis_minutes=10,  # Plus long pour éviter faux positifs
            severity_thresholds={
                "S1": 0.65,  # Changement modéré
                "S2": 0.80,  # Changement fort
                "S3": 0.90   # Changement très fort
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.05, "ramp_hours": 36},
                "S3": {"type": "freeze", "ttl_minutes": 720}  # 12h pour régime
            }
        )
        
        # CORR_HIGH - Corrélation systémique élevée  
        rules[AlertType.CORR_HIGH] = AlertRule(
            alert_type=AlertType.CORR_HIGH,
            base_threshold=0.70,  # 70% corrélation moyenne
            adaptive_multiplier=1.0,
            hysteresis_minutes=5,
            severity_thresholds={
                "S1": 0.75,
                "S2": 0.85,
                "S3": 0.95   # Corrélation quasi-parfaite = risque systémique
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.03, "ramp_hours": 48},
                "S3": {"type": "freeze", "ttl_minutes": 180}
            }
        )
        
        # CONTRADICTION_SPIKE - Index de contradiction élevé
        rules[AlertType.CONTRADICTION_SPIKE] = AlertRule(
            alert_type=AlertType.CONTRADICTION_SPIKE,
            base_threshold=0.50,  # 50% contradiction de base
            adaptive_multiplier=1.0,
            hysteresis_minutes=3,
            severity_thresholds={
                "S1": 0.60,
                "S2": 0.75,
                "S3": 0.85
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.06, "ramp_hours": 12},
                "S3": {"type": "freeze", "ttl_minutes": 240}
            }
        )
        
        # DECISION_DROP - Chute de confiance decision score
        rules[AlertType.DECISION_DROP] = AlertRule(
            alert_type=AlertType.DECISION_DROP,
            base_threshold=0.15,  # Drop de 15 points minimum
            adaptive_multiplier=1.0,
            hysteresis_minutes=5,
            severity_thresholds={
                "S1": 0.20,  # Drop 20 points
                "S2": 0.35,  # Drop 35 points
                "S3": 0.50   # Drop 50 points
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Normal", "cap_daily": 0.06, "ramp_hours": 18},
                "S3": {"type": "apply_policy", "mode": "Freeze", "cap_daily": 0.01, "ramp_hours": 48}
            }
        )
        
        # EXEC_COST_SPIKE - Coûts d'exécution anormaux
        rules[AlertType.EXEC_COST_SPIKE] = AlertRule(
            alert_type=AlertType.EXEC_COST_SPIKE,
            base_threshold=25,  # 25 bps de base
            adaptive_multiplier=1.2,
            hysteresis_minutes=3,
            severity_thresholds={
                "S1": 35,   # 35 bps
                "S2": 60,   # 60 bps
                "S3": 100   # 100 bps
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.04, "ramp_hours": 24},
                "S3": {"type": "apply_policy", "mode": "Freeze", "cap_daily": 0.01, "ramp_hours": 72}
            }
        )
        
        return rules
    
    def evaluate_alert(self, alert_type: AlertType, signals: Dict[str, Any]) -> Optional[Tuple[AlertSeverity, Dict[str, Any]]]:
        """
        Évalue si une alerte doit être déclenchée avec hystérésis
        
        Returns:
            Tuple[AlertSeverity, data] si alerte à déclencher, None sinon
        """
        try:
            if alert_type not in self.alert_rules:
                return None
                
            rule = self.alert_rules[alert_type]
            current_value = self._extract_signal_value(alert_type, signals)
            
            if current_value is None:
                return None
            
            # Calculer seuil adaptatif
            adaptive_threshold = self._calculate_adaptive_threshold(rule, signals)
            
            # Vérifier si condition remplie
            triggered = self._check_trigger_condition(alert_type, current_value, adaptive_threshold)
            
            if not triggered:
                # Reset hystérésis si plus déclenché
                self._evaluation_history.pop(alert_type, None)
                return None
                
            # Hystérésis - vérifier persistance temporelle
            if not self._check_hysteresis(alert_type, rule.hysteresis_minutes):
                return None
            
            # Déterminer gravité
            severity = self._determine_severity(rule, current_value)
            
            # Données contextuelles pour l'alerte
            alert_data = {
                "current_value": current_value,
                "adaptive_threshold": adaptive_threshold,
                "base_threshold": rule.base_threshold,
                "signals_snapshot": signals,
                "evaluation_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Alert triggered: {alert_type} severity {severity} value {current_value}")
            return severity, alert_data
            
        except Exception as e:
            logger.error(f"Error evaluating alert {alert_type}: {e}")
            return None
    
    def _extract_signal_value(self, alert_type: AlertType, signals: Dict[str, Any]) -> Optional[float]:
        """Extrait la valeur pertinente depuis les signaux ML"""
        try:
            if alert_type == AlertType.VOL_Q90_CROSS:
                volatility = signals.get("volatility", {})
                if volatility:
                    return max(volatility.values())  # Volatilité max
                    
            elif alert_type == AlertType.REGIME_FLIP:
                regime = signals.get("regime", {})
                if regime:
                    # Calculer "force" du changement (écart max entre probabilités)
                    probs = list(regime.values())
                    return max(probs) - min(probs)
                    
            elif alert_type == AlertType.CORR_HIGH:
                correlation = signals.get("correlation", {})
                return correlation.get("avg_correlation", 0.0)
                
            elif alert_type == AlertType.CONTRADICTION_SPIKE:
                return signals.get("contradiction_index", 0.0)
                
            elif alert_type == AlertType.DECISION_DROP:
                # Pour cet type, on a besoin d'historique (implémentation simplifiée)
                current_score = signals.get("decision_score", 0.5)
                # Dans une vraie implémentation, comparer avec score précédent
                return max(0, 0.8 - current_score)  # Simulé : drop depuis 0.8
                
            elif alert_type == AlertType.EXEC_COST_SPIKE:
                # Extraire coût estimé depuis les signaux
                return signals.get("execution_cost_bps", 15)
                
            return None
            
        except Exception as e:
            logger.error(f"Error extracting signal value for {alert_type}: {e}")
            return None
    
    def _calculate_adaptive_threshold(self, rule: AlertRule, signals: Dict[str, Any]) -> float:
        """Calcule le seuil adaptatif basé sur les conditions de marché"""
        base = rule.base_threshold
        
        try:
            # Ajustement selon volatilité moyenne
            volatility = signals.get("volatility", {})
            if volatility:
                avg_vol = sum(volatility.values()) / len(volatility)
                adjustment = avg_vol * rule.adaptive_multiplier
                return base * (1 + adjustment)
                
        except Exception:
            pass
            
        return base
    
    def _check_trigger_condition(self, alert_type: AlertType, value: float, threshold: float) -> bool:
        """Vérifie si la condition de déclenchement est remplie"""
        if alert_type in [AlertType.VOL_Q90_CROSS, AlertType.CORR_HIGH, 
                         AlertType.CONTRADICTION_SPIKE, AlertType.EXEC_COST_SPIKE]:
            return value > threshold
        elif alert_type in [AlertType.REGIME_FLIP, AlertType.DECISION_DROP]:
            return value > threshold
            
        return False
    
    def _check_hysteresis(self, alert_type: AlertType, required_minutes: int) -> bool:
        """Vérifie si la condition persiste depuis assez longtemps"""
        now = datetime.now()
        
        if alert_type not in self._evaluation_history:
            self._evaluation_history[alert_type] = now
            return False  # Premier déclenchement
            
        first_trigger = self._evaluation_history[alert_type]
        elapsed = (now - first_trigger).total_seconds() / 60
        
        return elapsed >= required_minutes
    
    def _determine_severity(self, rule: AlertRule, value: float) -> AlertSeverity:
        """Détermine la gravité en fonction de la valeur et des seuils"""
        thresholds = rule.severity_thresholds
        
        if value >= thresholds.get("S3", float('inf')):
            return AlertSeverity.S3
        elif value >= thresholds.get("S2", float('inf')):
            return AlertSeverity.S2
        else:
            return AlertSeverity.S1