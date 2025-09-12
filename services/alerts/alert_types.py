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
    CORR_SPIKE = "CORR_SPIKE"                 # Phase 2B2: Spike corrélation brutal
    CONTRADICTION_SPIKE = "CONTRADICTION_SPIKE" # Index de contradiction élevé
    DECISION_DROP = "DECISION_DROP"           # Chute de confiance decision score
    EXEC_COST_SPIKE = "EXEC_COST_SPIKE"       # Coûts d'exécution anormaux
    
    # Phase 2C: Alertes prédictives ML
    SPIKE_LIKELY = "SPIKE_LIKELY"             # Spike corrélation probable 24-48h
    REGIME_CHANGE_PENDING = "REGIME_CHANGE_PENDING"   # Changement régime attendu
    CORRELATION_BREAKDOWN = "CORRELATION_BREAKDOWN"   # Décorrélation majeure prédite
    VOLATILITY_SPIKE_IMMINENT = "VOLATILITY_SPIKE_IMMINENT"  # Spike volatilité imminent
    
    # Phase 3A: Advanced Risk Models
    VAR_BREACH = "VAR_BREACH"                 # VaR limite dépassée
    STRESS_TEST_FAILED = "STRESS_TEST_FAILED" # Échec stress test critique
    MONTE_CARLO_EXTREME = "MONTE_CARLO_EXTREME" # Scénario extrême détecté MC
    RISK_CONCENTRATION = "RISK_CONCENTRATION" # Concentration risque excessive

class AlertFormatter:
    """
    Formateur d'alertes avec micro-copy français
    Format : Action → Impact € → 2 raisons → Détails
    """
    
    def __init__(self):
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[AlertType, Dict[str, Dict[str, Any]]]:
        """Charge les templates de micro-copy par type et gravité"""
        return {
            AlertType.VOL_Q90_CROSS: {
                "S1": {
                    "action": "Surveillance volatilité",
                    "impact_base": 0.5,  # % impact estimé
                    "reasons": ["Volatilité Q90 dépassée", "Conditions de marché agitées"],
                    "details": "La volatilité {current_vol:.1%} dépasse le seuil adaptatif {threshold:.1%}. Phase {phase} - Confiance {confidence:.0%}"
                },
                "S2": {
                    "action": "Réduction exposition (mode Slow)", 
                    "impact_base": 2.0,
                    "reasons": ["Volatilité critique détectée", "Risque de drawdown majoré"],
                    "details": "Volatilité {current_vol:.1%} très élevée. Mode Slow recommandé (cap 4%/jour, ramp 24h). Phase {phase}"
                },
                "S3": {
                    "action": "Arrêt immédiat trading (Freeze)",
                    "impact_base": 8.0,
                    "reasons": ["Volatilité extrême mesurée", "Protection capital prioritaire"],
                    "details": "Volatilité {current_vol:.1%} extrême! Freeze 6h recommandé. Phase {phase} - Signal d'urgence"
                }
            },
            AlertType.REGIME_FLIP: {
                "S1": {
                    "action": "Surveillance changement régime",
                    "impact_base": 1.0,
                    "reasons": ["Probabilité shift régime détectée", "Signaux ML mixtes observés"],
                    "details": "Flip régime probabilité {regime_prob:.0%}. Phase transition {phase}. Monitoring renforcé"
                },
                "S2": {
                    "action": "Adaptation allocation (mode Slow)",
                    "impact_base": 3.5,
                    "reasons": ["Régime market confirmé changé", "Corrélations historiques caduques"],
                    "details": "Régime flip confirmé (prob {regime_prob:.0%}). Slow policy 36h recommandée. Phase {phase}"
                },
                "S3": {
                    "action": "Freeze temporaire (12h)",
                    "impact_base": 12.0,
                    "reasons": ["Changement régime majeur confirmé", "Incertitude paramètres allocation"],
                    "details": "Flip régime critique! Prob {regime_prob:.0%}. Freeze 12h - recalibration nécessaire"
                }
            },
            AlertType.CORR_HIGH: {
                "S1": {
                    "action": "Monitoring corrélations systémiques",
                    "impact_base": 0.8,
                    "reasons": ["Corrélation inter-assets élevée", "Réduction bénéfice diversification"],
                    "details": "Corrélation moyenne {correlation:.0%}. Diversification réduite. Phase {phase}"
                },
                "S2": {
                    "action": "Réduction taille positions (mode Slow)",
                    "impact_base": 2.8,
                    "reasons": ["Corrélation systémique confirmée", "Risque concentration de facto"],
                    "details": "Corrélation {correlation:.0%} critique. Mode Slow 48h - cap 3%/jour. Risque systémique"
                },
                "S3": {
                    "action": "Pause trading (Freeze 3h)",
                    "impact_base": 6.0,
                    "reasons": ["Corrélation quasi-parfaite détectée", "Diversification totalement compromise"],
                    "details": "Corrélation {correlation:.0%}! Diversification nulle. Freeze immédiat 3h"
                }
            },
            AlertType.CORR_SPIKE: {
                "S1": {
                    "action": "Surveillance spike corrélation",
                    "impact_base": 1.2,
                    "reasons": ["Choc corrélation détecté", "Variation brutale liens assets"],
                    "details": "Spike {asset_pair}: {corr_before:.2f}→{corr_after:.2f} (Δ{delta:.1%}) en {timeframe}. Changement régime possible"
                },
                "S2": {
                    "action": "Ajustement allocation (mode Slow)",
                    "impact_base": 3.5,
                    "reasons": ["Spike corrélation majeur confirmé", "Instabilité structure portfolio"],
                    "details": "Spike critique {asset_pair}: Δ{delta:.1%} en {timeframe}. Mode Slow 24h. Recalibration matrice risque nécessaire"
                },
                "S3": {
                    "action": "Pause trading (Freeze 6h)",
                    "impact_base": 8.0,
                    "reasons": ["Choc corrélation extrême", "Rupture structure marché - instabilité systémique"],
                    "details": "SPIKE CRITIQUE {asset_pair}! Δ{delta:.1%} brutal. Freeze 6h - analyse contagion. Risque cascade systémique"
                }
            },
            AlertType.CONTRADICTION_SPIKE: {
                "S1": {
                    "action": "Vérification cohérence signaux",
                    "impact_base": 0.3,
                    "reasons": ["Index contradiction élevé détecté", "Signaux ML partiellement divergents"],
                    "details": "Contradiction {contradiction:.0%}. Signaux ML mixtes. Surveillance phase {phase}"
                },
                "S2": {
                    "action": "Prudence exécution (mode Slow)",
                    "impact_base": 1.8,
                    "reasons": ["Signaux très contradictoires", "Confiance prédictions dégradée"],
                    "details": "Contradiction {contradiction:.0%} préoccupante. Mode Slow 12h - cap 6%/jour"
                },
                "S3": {
                    "action": "Pause décisions (Freeze 4h)",
                    "impact_base": 5.0,
                    "reasons": ["Contradiction signaux majeure", "Fiabilité ML compromise temporairement"],
                    "details": "Contradiction {contradiction:.0%}! ML peu fiable. Freeze 4h - diagnostic requis"
                }
            },
            AlertType.DECISION_DROP: {
                "S1": {
                    "action": "Monitoring confiance décision",
                    "impact_base": 0.4,
                    "reasons": ["Score décision en baisse", "Confiance allocation réduite"],
                    "details": "Score décision drop {decision_drop:.0%}pts. Confiance {confidence:.0%}. Phase {phase}"
                },
                "S2": {
                    "action": "Mode prudent allocation",
                    "impact_base": 2.2,
                    "reasons": ["Chute confiante décision significative", "Qualité allocation dégradée"],
                    "details": "Decision score drop {decision_drop:.0%}pts! Mode Normal 18h - cap 6%/jour"
                },
                "S3": {
                    "action": "Mode ultra-conservateur (Freeze)",
                    "impact_base": 9.0,
                    "reasons": ["Effondrement confiance décision", "Allocations potentiellement erronées"],
                    "details": "Decision drop {decision_drop:.0%}pts critiques! Mode Freeze - cap 1%/jour sur 48h"
                }
            },
            AlertType.EXEC_COST_SPIKE: {
                "S1": {
                    "action": "Surveillance coûts exécution",
                    "impact_base": 0.2,
                    "reasons": ["Coûts trading légèrement élevés", "Conditions liquidité moyennes"],
                    "details": "Coûts {exec_cost:.0f}bps vs normal {normal_cost:.0f}bps. Phase {phase}"
                },
                "S2": {
                    "action": "Ralentissement trading (mode Slow)",
                    "impact_base": 1.5,
                    "reasons": ["Coûts exécution anormalement hauts", "Liquidité marché dégradée"],
                    "details": "Coûts {exec_cost:.0f}bps élevés! Mode Slow 24h - étalement positions"
                },
                "S3": {
                    "action": "Arrêt trading (mode Freeze)",
                    "impact_base": 4.0,
                    "reasons": ["Coûts exécution prohibitifs", "Liquidité marché très dégradée"],
                    "details": "Coûts {exec_cost:.0f}bps prohibitifs! Freeze - étalement sur 72h max"
                }
            },
            
            # Phase 2C: Templates pour alertes prédictives ML
            AlertType.SPIKE_LIKELY: {
                "S1": {
                    "action": "Préparation spike corrélation",
                    "impact_base": 0.8,
                    "reasons": ["ML prédit spike corrélation probable", "Horizon {horizon} - probabilité {probability:.0%}"],
                    "details": "Spike {asset_pair} prédit dans {horizon} (prob {probability:.0%}, confiance {confidence:.0%}). Préparatifs: réduction allocation"
                },
                "S2": {
                    "action": "Réduction préventive positions", 
                    "impact_base": 2.5,
                    "reasons": ["Spike corrélation très probable", "Anticipation choc systémique ML"],
                    "details": "SPIKE PROBABLE {asset_pair} dans {horizon}! Prob {probability:.0%}. Mode Slow préventif 24h - cap 2%/jour"
                },
                "S3": {
                    "action": "Protection préventive (mode Freeze)",
                    "impact_base": 5.0,
                    "reasons": ["ML prédit spike critique imminent", "Protection proactive capital"],
                    "details": "SPIKE CRITIQUE prédit {asset_pair} dans {horizon}! Prob {probability:.0%} - Freeze préventif recommandé"
                }
            },
            AlertType.REGIME_CHANGE_PENDING: {
                "S1": {
                    "action": "Surveillance changement régime ML",
                    "impact_base": 1.0,
                    "reasons": ["ML détecte transition régime probable", "Signaux précurseurs identifiés"],
                    "details": "Régime flip prédit dans {horizon} (prob {probability:.0%}). Préparation recalibration matrice risque"
                },
                "S2": {
                    "action": "Adaptation anticipée allocation",
                    "impact_base": 3.2,
                    "reasons": ["Changement régime imminent ML", "Paramètres actuels obsolètes prévus"],
                    "details": "Régime change IMMINENT dans {horizon}! Prob {probability:.0%}. Transition mode Slow 36h - anticipation paramètres"
                },
                "S3": {
                    "action": "Arrêt préventif trading",
                    "impact_base": 7.0,
                    "reasons": ["Flip régime critique prédit ML", "Incertitude majeure paramètres"],
                    "details": "RÉGIME FLIP critique prédit {horizon}! Prob {probability:.0%} - Freeze total jusqu'à confirmation"
                }
            },
            AlertType.CORRELATION_BREAKDOWN: {
                "S1": {
                    "action": "Monitoring décorrélation prédite",
                    "impact_base": 1.5,
                    "reasons": ["ML prédit breakdown corrélations", "Diversification attendue améliorée"],
                    "details": "Décorrélation prédite dans {horizon} (prob {probability:.0%}). Opportunité diversification - surveillance"
                },
                "S2": {
                    "action": "Repositionnement anticipé portfolio", 
                    "impact_base": 2.8,
                    "reasons": ["Breakdown corrélation majeur prédit", "Restructuration portfolio requise"],
                    "details": "DÉCORRÉLATION majeure prédite dans {horizon}! Prob {probability:.0%}. Repositionnement actif recommandé"
                },
                "S3": {
                    "action": "Reconfiguration majeure positions",
                    "impact_base": 6.5,
                    "reasons": ["Breakdown systémique prédit", "Révision complète allocation nécessaire"],
                    "details": "BREAKDOWN SYSTÉMIQUE prédit {horizon}! Prob {probability:.0%} - Révision allocation complète urgente"
                }
            },
            AlertType.VOLATILITY_SPIKE_IMMINENT: {
                "S1": {
                    "action": "Préparation spike volatilité",
                    "impact_base": 0.6,
                    "reasons": ["ML prédit spike volatilité probable", "Conditions marché précurseurs"],
                    "details": "Spike vol prédit dans {horizon} (prob {probability:.0%}). Préparatifs réduction exposition recommandés"
                },
                "S2": {
                    "action": "Réduction anticipée exposition",
                    "impact_base": 3.8,
                    "reasons": ["Spike volatilité imminent ML", "Protection drawdown préventive"],
                    "details": "SPIKE VOLATILITÉ imminent dans {horizon}! Prob {probability:.0%}. Mode Slow immédiat - cap 3%/jour"
                },
                "S3": {
                    "action": "Protection maximale (Freeze)",
                    "impact_base": 9.0,
                    "reasons": ["Spike volatilité extrême prédit", "Protection capitale priorité absolue"],
                    "details": "VOLATILITÉ EXTRÊME prédite {horizon}! Prob {probability:.0%} - FREEZE TOTAL jusqu'à passage"
                }
            },
            
            # Phase 3A: Templates pour Advanced Risk Models
            AlertType.VAR_BREACH: {
                "S1": {
                    "action": "Surveillance dépassement VaR",
                    "impact_base": 1.2,
                    "reasons": ["Perte potentielle dépasse VaR {confidence_level:.0%}", "Niveau de risque élevé détecté"],
                    "details": "VaR {method} breached: {var_current:.0f}€ vs limite {var_limit:.0f}€. Horizon {horizon} - Confiance {confidence_level:.0%}"
                },
                "S2": {
                    "action": "Réduction immédiate exposition",
                    "impact_base": 3.0,
                    "reasons": ["VaR critique largement dépassée", "Protection capital nécessaire"],
                    "details": "VaR BREACH majeur! {var_current:.0f}€ vs {var_limit:.0f}€ ({var_ratio:.1f}x). Réduction positions immédiate recommandée"
                },
                "S3": {
                    "action": "Liquidation partielle urgente",
                    "impact_base": 8.5,
                    "reasons": ["VaR extrême - risque systémique", "Protection capitale critique"],
                    "details": "VaR EXTREME! {var_current:.0f}€ ({var_ratio:.1f}x limite). LIQUIDATION partielle urgente - risque majeur détecté"
                }
            },
            AlertType.STRESS_TEST_FAILED: {
                "S1": {
                    "action": "Révision allocation stress",
                    "impact_base": 1.8,
                    "reasons": ["Échec stress test {scenario}", "Vulnérabilité scenario identifiée"],
                    "details": "Stress test {scenario}: perte {stress_loss:.0f}€ ({stress_loss_pct:.1%}). Vulnérabilité détectée - ajustements requis"
                },
                "S2": {
                    "action": "Hedging défensif immédiat",
                    "impact_base": 4.2,
                    "reasons": ["Stress test critique failed", "Exposition dangereuse scenario {scenario}"],
                    "details": "STRESS FAIL critique {scenario}! Perte simulée {stress_loss:.0f}€ ({stress_loss_pct:.1%}). Hedging immédiat requis"
                },
                "S3": {
                    "action": "Restructuration portfolio urgente",
                    "impact_base": 12.0,
                    "reasons": ["Stress test catastrophique", "Survie portfolio menacée scenario {scenario}"],
                    "details": "STRESS CATASTROPHIQUE {scenario}! Perte {stress_loss:.0f}€ ({stress_loss_pct:.1%}). RESTRUCTURATION totale urgente"
                }
            },
            AlertType.MONTE_CARLO_EXTREME: {
                "S1": {
                    "action": "Monitoring scénarios extrêmes",
                    "impact_base": 1.0,
                    "reasons": ["Monte Carlo détecte outcomes négatifs", "Probabilité events extrêmes élevée"],
                    "details": "MC simulation: {mc_extreme_prob:.1%} chance perte >{mc_threshold:.0f}€. Horizon {horizon}j - monitoring renforcé"
                },
                "S2": {
                    "action": "Réduction risque préventive",
                    "impact_base": 3.8,
                    "reasons": ["Scénarios extrêmes MC très probables", "Tail risk significatif détecté"],
                    "details": "MC EXTREME: {mc_extreme_prob:.1%} chance perte >{mc_threshold:.0f}€! Max DD P99: {max_dd_p99:.1%}. Action préventive requise"
                },
                "S3": {
                    "action": "Protection tail risk maximale",
                    "impact_base": 10.0,
                    "reasons": ["Monte Carlo prédit catastrophe possible", "Tail risk inacceptable"],
                    "details": "MC CATASTROPHIQUE! {mc_extreme_prob:.1%} risque perte >{mc_threshold:.0f}€. Max DD P99: {max_dd_p99:.1%}. PROTECTION maximale"
                }
            },
            AlertType.RISK_CONCENTRATION: {
                "S1": {
                    "action": "Surveillance concentration risque",
                    "impact_base": 0.8,
                    "reasons": ["Concentration risque élevée détectée", "Diversification insuffisante"],
                    "details": "Risk concentration: {concentrated_asset} représente {concentration_pct:.1%} du risque total. Marginal VaR: {marginal_var:.0f}€"
                },
                "S2": {
                    "action": "Rééquilibrage diversification",
                    "impact_base": 2.5,
                    "reasons": ["Concentration critique sur {concentrated_asset}", "Risque portfolio non diversifié"],
                    "details": "CONCENTRATION critique! {concentrated_asset}: {concentration_pct:.1%} du risque. Marginal VaR {marginal_var:.0f}€. Rééquilibrage requis"
                },
                "S3": {
                    "action": "Diversification urgente portfolio",
                    "impact_base": 6.0,
                    "reasons": ["Concentration extrême {concentrated_asset}", "Portfolio mono-risque dangereux"],
                    "details": "CONCENTRATION EXTRÊME! {concentrated_asset}: {concentration_pct:.1%} risque total! Marginal VaR {marginal_var:.0f}€ - diversification URGENTE"
                }
            }
        }
    
    def format_alert(self, alert: 'Alert') -> Dict[str, Any]:
        """
        Formate une alerte selon le template unifié
        Returns: {action, impact, reasons, details}
        """
        try:
            template = self.templates.get(alert.alert_type, {}).get(alert.severity.value, {})
            if not template:
                return self._fallback_format(alert)
            
            # Extraction des données contextuelles
            data = alert.data or {}
            
            # Calcul impact € estimé
            portfolio_value = data.get("portfolio_value", 100000)  # €100k par défaut
            impact_pct = template["impact_base"] / 100
            impact_euro = portfolio_value * impact_pct
            
            # Formatage des détails avec interpolation
            details = template["details"].format(
                # Variables existantes
                current_vol=data.get("current_value", 0.0),
                threshold=data.get("adaptive_threshold", 0.0),
                phase=data.get("phase", "unknown"),
                confidence=data.get("confidence", 0.75),
                regime_prob=data.get("current_value", 0.0),
                correlation=data.get("current_value", 0.0),
                contradiction=data.get("current_value", 0.0) * 100,
                decision_drop=data.get("current_value", 0.0) * 100,
                exec_cost=data.get("current_value", 30),
                normal_cost=data.get("normal_cost", 15),
                
                # Variables Phase 2B2 (CORR_SPIKE)
                asset_pair=data.get("asset_pair", "BTC/ETH"),
                corr_before=data.get("correlation_before", 0.0),
                corr_after=data.get("correlation_after", 0.0),
                delta=data.get("relative_change", 0.0),
                timeframe=data.get("timeframe", "1h"),
                
                # Variables Phase 2C (alertes prédictives ML)
                horizon=data.get("horizon", "24h"),
                probability=data.get("probability", 0.0) * 100,  # Convertir 0-1 en %
                model_confidence=data.get("model_confidence", 0.75),
                
                # Variables Phase 3A (Advanced Risk Models)
                method=data.get("var_method", "parametric"),
                confidence_level=data.get("confidence_level", 0.95) * 100,  # 95%
                var_current=data.get("var_current", 0),
                var_limit=data.get("var_limit", 10000),
                var_ratio=data.get("var_current", 0) / max(data.get("var_limit", 1), 1),
                scenario=data.get("stress_scenario", "unknown"),
                stress_loss=abs(data.get("stress_loss", 0)),
                stress_loss_pct=abs(data.get("stress_loss_pct", 0.0)) * 100,
                mc_extreme_prob=data.get("mc_extreme_prob", 0.05) * 100,
                mc_threshold=data.get("mc_threshold", 50000),
                max_dd_p99=data.get("max_dd_p99", 0.0) * 100,
                concentrated_asset=data.get("concentrated_asset", "BTC"),
                concentration_pct=data.get("concentration_pct", 0.0) * 100,
                marginal_var=data.get("marginal_var", 0)
            )
            
            return {
                "action": template["action"],
                "impact": f"€{impact_euro:,.0f}" if impact_euro >= 1 else f"€{impact_euro:.2f}",
                "reasons": template["reasons"],
                "details": details,
                "severity": alert.severity.value,
                "alert_type": alert.alert_type.value
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert template: {e}")
            return self._fallback_format(alert)
    
    def _fallback_format(self, alert: 'Alert') -> Dict[str, Any]:
        """Format de secours en cas d'erreur"""
        return {
            "action": f"Alerte {alert.alert_type.value}",
            "impact": "€ inconnu",
            "reasons": ["Situation détectée", "Action recommandée"],
            "details": f"Alerte {alert.severity.value} - {alert.created_at.strftime('%H:%M:%S')}"
        }

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
    
    def format_unified_message(self) -> Dict[str, str]:
        """
        Format unifié : Action → Impact € → 2 raisons → Détails
        Retourne un dict avec les sections formatées
        """
        try:
            formatter = AlertFormatter()
            return formatter.format_alert(self)
        except Exception as e:
            logger.error(f"Error formatting alert {self.id}: {e}")
            return {
                "action": "Erreur de formatage",
                "impact": "€ inconnu", 
                "reasons": ["Erreur technique", "Contacter support"],
                "details": f"Alert {self.alert_type.value} - {self.severity.value}"
            }

class AlertEvaluator:
    """Évaluateur de règles d'alertes avec hystérésis et seuils adaptatifs"""
    
    def __init__(self, config: Dict[str, Any], metrics=None):
        self.config = config
        self.metrics = metrics
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
        
        # CORR_SPIKE - Phase 2B2: Spike corrélation brutal
        rules[AlertType.CORR_SPIKE] = AlertRule(
            alert_type=AlertType.CORR_SPIKE,
            base_threshold=0.20,  # 20% variation absolue minimum
            adaptive_multiplier=1.0,
            hysteresis_minutes=2,  # Réaction rapide pour spikes
            severity_thresholds={
                "S1": 0.25,  # Δ≥25% (minor spike)
                "S2": 0.35,  # Δ≥35% (major spike) 
                "S3": 0.50   # Δ≥50% (critical spike)
            },
            suggested_actions={
                "S1": {"type": "acknowledge"},
                "S2": {"type": "apply_policy", "mode": "Slow", "cap_daily": 0.02, "ramp_hours": 24},
                "S3": {"type": "freeze", "ttl_minutes": 360}  # 6h freeze pour spike critique
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
    
    def evaluate_alert(self, alert_type: AlertType, signals: Dict[str, Any], phase_context: Optional[Dict[str, Any]] = None) -> Optional[Tuple[AlertSeverity, Dict[str, Any]]]:
        """
        Évalue si une alerte doit être déclenchée avec hystérésis et seuils adaptatifs phase-aware
        
        Args:
            alert_type: Type d'alerte à évaluer
            signals: Signaux ML actuels
            phase_context: Contexte de phase pour adaptation des seuils
        
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
            
            # Calculer seuil adaptatif (incluant phase_factor)
            adaptive_threshold = self._calculate_adaptive_threshold(rule, signals, phase_context)
            
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
                
            elif alert_type == AlertType.CORR_SPIKE:
                # Phase 2B2: Extraire max absolute change des spikes détectés
                spikes = signals.get("correlation_spikes", [])
                if spikes:
                    return max(spike.get("absolute_change", 0.0) for spike in spikes)
                return 0.0
                
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
    
    def _calculate_adaptive_threshold(self, rule: AlertRule, signals: Dict[str, Any], phase_context: Optional[Dict[str, Any]] = None) -> float:
        """
        Calcule le seuil adaptatif: adaptive = base × phase_factor × market_factor
        
        Args:
            rule: Règle d'alerte avec seuil de base
            signals: Signaux ML actuels  
            phase_context: Contexte de phase (phase, factors, contradiction)
        
        Returns:
            Seuil adaptatif calculé
        """
        base = rule.base_threshold
        
        try:
            # 1. Phase Factor
            phase_factor = 1.0
            if phase_context and "phase" in phase_context and "phase_factors" in phase_context:
                alert_type_str = rule.alert_type.value
                phase_str = phase_context["phase"].value
                phase_factors = phase_context.get("phase_factors", {})
                
                if alert_type_str in phase_factors and phase_str in phase_factors[alert_type_str]:
                    phase_factor = phase_factors[alert_type_str][phase_str]
                    
                    # Neutraliser le phase_factor si contradiction élevée
                    contradiction_index = phase_context.get("contradiction_index", 0.0)
                    if contradiction_index > 0.70:
                        phase_factor = 1.0  # Fallback à market-only
                        logger.debug(f"Phase factor neutralized due to high contradiction: {contradiction_index:.2f}")
            
            # 2. Market Factor (volatilité, corrélation, confiance)
            market_factor = 1.0
            
            # Vol Q90 élevé → +10-30% sur seuils VOL_HIGH (plus strict)
            volatility = signals.get("volatility", {})
            if volatility and rule.alert_type == AlertType.VOL_Q90_CROSS:
                if isinstance(volatility, dict):
                    avg_vol = sum(volatility.values()) / len(volatility) if volatility else 0.15
                    if avg_vol > 0.25:  # Volatilité élevée
                        market_factor *= 1.2  # 20% plus strict
                    
            # Corrélation "high" → +10-20% sur EXEC_COST (plus strict)  
            correlation = signals.get("correlation", {})
            avg_correlation = correlation.get("avg_correlation", 0.5) if isinstance(correlation, dict) else correlation
            if avg_correlation > 0.8 and rule.alert_type == AlertType.EXEC_COST_SPIKE:
                market_factor *= 1.15  # 15% plus strict
                
            # Confidence faible (<0.6) → -10% (moins sensible pour éviter bruit)
            confidence = signals.get("confidence", 0.75)
            if confidence < 0.6:
                market_factor *= 0.9  # 10% moins strict
                
            # 3. Calcul final: adaptive = base × phase_factor × market_factor
            adaptive_threshold = base * phase_factor * market_factor
            
            # Record adaptive threshold adjustment if phase factor was applied
            if phase_factor != 1.0 and self.metrics and phase_context:
                phase_str = phase_context.get("phase", "unknown")
                if hasattr(phase_str, 'value'):
                    phase_str = phase_str.value.lower()
                self.metrics.record_adaptive_threshold_adjustment(
                    rule.alert_type.value,
                    phase_str
                )
            
            logger.debug(f"Adaptive threshold for {rule.alert_type.value}: "
                        f"base={base:.3f} × phase={phase_factor:.2f} × market={market_factor:.2f} "
                        f"= {adaptive_threshold:.3f}")
            
            return adaptive_threshold
                
        except Exception as e:
            logger.warning(f"Error calculating adaptive threshold: {e}")
            return base
    
    def _check_trigger_condition(self, alert_type: AlertType, value: float, threshold: float) -> bool:
        """Vérifie si la condition de déclenchement est remplie"""
        if alert_type in [AlertType.VOL_Q90_CROSS, AlertType.CORR_HIGH, AlertType.CORR_SPIKE,
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