"""
Advanced Portfolio Risk Management - Système de gestion des risques de niveau institutionnel

Ce module implémente des métriques de risque sophistiquées :
- VaR (Value at Risk) et CVaR (Conditional VaR) 
- Matrice de corrélation temps réel entre assets
- Stress testing avec scénarios crypto historiques
- Métriques avancées : Sortino, Calmar, Maximum Drawdown, Ulcer Index
- Attribution de performance par asset/stratégie
- Monitoring temps réel avec alertes intelligentes
"""

from __future__ import annotations
import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import math
from scipy import stats
from collections import deque

from services.taxonomy import Taxonomy
from services.pricing import get_prices_usd
from services.portfolio import portfolio_analytics

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Niveaux de risque pour alertes"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"

class StressScenario(Enum):
    """Scénarios de stress test historiques crypto"""
    BEAR_MARKET_2018 = "bear_2018"          # Crash 2018: BTC -84%, Altcoins -95%
    COVID_CRASH_2020 = "covid_2020"         # Mars 2020: BTC -50% en 2 semaines  
    LUNA_COLLAPSE_2022 = "luna_2022"        # Mai 2022: Terra Luna collapse
    FTX_COLLAPSE_2022 = "ftx_2022"          # Nov 2022: FTX bankruptcy
    CUSTOM_SCENARIO = "custom"               # Scénario personnalisé

@dataclass
class RiskMetrics:
    """Métriques de risque complètes pour un portfolio"""
    
    # VaR/CVaR 
    var_95_1d: float = 0.0           # VaR 95% 1 jour
    var_99_1d: float = 0.0           # VaR 99% 1 jour  
    cvar_95_1d: float = 0.0          # CVaR 95% 1 jour
    cvar_99_1d: float = 0.0          # CVaR 99% 1 jour
    
    # Métriques classiques
    volatility_annualized: float = 0.0      # Volatilité annualisée
    sharpe_ratio: float = 0.0               # Sharpe ratio
    sortino_ratio: float = 0.0              # Sortino ratio (downside deviation)
    calmar_ratio: float = 0.0               # Calmar ratio (return/max drawdown)
    
    # Drawdown analysis
    max_drawdown: float = 0.0               # Maximum drawdown
    max_drawdown_duration_days: int = 0     # Durée max drawdown
    current_drawdown: float = 0.0           # Drawdown actuel
    ulcer_index: float = 0.0                # Ulcer index (drawdown pain)
    
    # Distribution analysis
    skewness: float = 0.0                   # Asymétrie des returns
    kurtosis: float = 0.0                   # Aplatissement (fat tails)
    
    # Risk level assessment
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.0                 # Score 0-100
    
    # Metadata
    calculation_date: datetime = field(default_factory=datetime.now)
    data_points: int = 0                    # Nombre de points de données
    confidence_level: float = 0.0           # Niveau de confiance des calculs

@dataclass  
class CorrelationMatrix:
    """Matrice de corrélation entre assets"""
    correlations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    eigen_values: List[float] = field(default_factory=list)
    eigen_vectors: List[List[float]] = field(default_factory=list) 
    principal_components: Dict[str, float] = field(default_factory=dict)
    diversification_ratio: float = 0.0      # Ratio de diversification
    effective_assets: float = 0.0           # Nombre effectif d'assets indépendants
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class StressTestResult:
    """Résultat d'un stress test"""
    scenario_name: str
    scenario_description: str
    portfolio_loss_pct: float               # Perte portfolio en %
    portfolio_loss_usd: float               # Perte portfolio en USD
    worst_performing_assets: List[Dict[str, Any]]  # Top 3 pires performances
    best_performing_assets: List[Dict[str, Any]]   # Top 3 meilleures performances
    var_breach: bool                        # VaR dépassé ou non
    recovery_time_estimate_days: int        # Temps de récupération estimé
    risk_contribution: Dict[str, float]     # Contribution au risque par asset

@dataclass
class PerformanceAttribution:
    """Attribution de performance détaillée du portfolio"""
    total_return: float                     # Return total du portfolio
    total_return_usd: float                 # Return en USD
    
    # Attribution par asset individuel
    asset_contributions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Attribution par groupe d'assets
    group_contributions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Métriques d'attribution
    selection_effect: float = 0.0          # Effet de sélection d'assets
    allocation_effect: float = 0.0         # Effet d'allocation entre groupes
    interaction_effect: float = 0.0        # Effet d'interaction
    
    # Analyse temporelle
    period_start: datetime = field(default_factory=datetime.now)
    period_end: datetime = field(default_factory=datetime.now) 
    analysis_period_days: int = 0
    
    # Métadonnées
    calculation_date: datetime = field(default_factory=datetime.now)
    benchmark_used: Optional[str] = None    # Benchmark utilisé pour comparaison

@dataclass
class BacktestResult:
    """Résultats d'un backtest de stratégie"""
    strategy_name: str
    strategy_description: str
    
    # Performance globale
    total_return: float                     # Return total de la stratégie
    annualized_return: float               # Return annualisé
    volatility: float                      # Volatilité annualisée
    sharpe_ratio: float                    # Sharpe ratio
    max_drawdown: float                    # Maximum drawdown
    
    # Comparaison vs benchmark
    benchmark_return: float                # Return du benchmark
    active_return: float                   # Return actif (stratégie - benchmark)
    information_ratio: float               # Information ratio
    tracking_error: float                  # Tracking error vs benchmark
    
    # Métriques de risque
    var_95: float                          # VaR 95%
    downside_deviation: float              # Déviation downside
    sortino_ratio: float                   # Sortino ratio
    calmar_ratio: float                    # Calmar ratio
    
    # Statistiques de trading
    num_rebalances: int                    # Nombre de rebalancing
    avg_turnover: float                    # Turnover moyen par rebalancing
    total_costs: float                     # Coûts totaux de transaction
    
    # Historique détaillé
    portfolio_values: List[float] = field(default_factory=list)  # Valeur portfolio dans le temps
    benchmark_values: List[float] = field(default_factory=list)  # Valeur benchmark dans le temps
    dates: List[datetime] = field(default_factory=list)          # Dates correspondantes
    rebalancing_dates: List[datetime] = field(default_factory=list)  # Dates de rebalancing
    
    # Métadonnées
    backtest_start: datetime = field(default_factory=datetime.now)
    backtest_end: datetime = field(default_factory=datetime.now)
    backtest_days: int = 0

class AlertSeverity(Enum):
    """Niveaux de sévérité des alertes"""
    INFO = "info"
    LOW = "low" 
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertCategory(Enum):
    """Catégories d'alertes"""
    RISK_THRESHOLD = "risk_threshold"           # Dépassement de seuils de risque
    PERFORMANCE = "performance"                 # Alertes de performance
    CORRELATION = "correlation"                 # Alertes de corrélation
    CONCENTRATION = "concentration"             # Alertes de concentration
    MARKET_STRESS = "market_stress"            # Alertes de stress marché
    REBALANCING = "rebalancing"                # Alertes de rebalancing
    DATA_QUALITY = "data_quality"              # Alertes qualité des données

@dataclass
class RiskAlert:
    """Alerte de risque intelligente"""
    id: str                                    # ID unique de l'alerte
    severity: AlertSeverity                    # Niveau de sévérité
    category: AlertCategory                    # Catégorie
    title: str                                 # Titre court
    message: str                               # Message descriptif
    recommendation: str                        # Recommandation d'action
    
    # Données contextuelles
    current_value: float                       # Valeur actuelle du métrique
    threshold_value: float                     # Seuil dépassé
    affected_assets: List[str] = field(default_factory=list)  # Assets concernés
    
    # Métadonnées
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None      # Expiration de l'alerte
    is_active: bool = True                     # Alerte active ou résolue
    resolution_note: Optional[str] = None      # Note de résolution
    
    # Historique
    first_triggered: datetime = field(default_factory=datetime.now)
    trigger_count: int = 1                     # Nombre de déclenchements

@dataclass 
class AlertSystem:
    """Système d'alertes intelligent avec historique et règles configurables"""
    
    # Configuration des seuils
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Historique des alertes
    alert_history: List[RiskAlert] = field(default_factory=list)
    active_alerts: Dict[str, RiskAlert] = field(default_factory=dict)
    
    # Paramètres système
    max_alert_history: int = 1000
    alert_cooldown_hours: int = 24
    
    def __post_init__(self):
        """Initialise les seuils par défaut"""
        self.thresholds = self._get_default_thresholds()
    
    def _get_default_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Définit les seuils par défaut pour chaque type d'alerte"""
        return {
            "var_95": {
                "medium": 0.10,    # VaR 95% > 10%
                "high": 0.15,      # VaR 95% > 15% 
                "critical": 0.25   # VaR 95% > 25%
            },
            "volatility": {
                "medium": 0.60,    # Volatilité > 60%
                "high": 0.80,      # Volatilité > 80%
                "critical": 1.20   # Volatilité > 120%
            },
            "max_drawdown": {
                "medium": 0.20,    # Max DD > 20%
                "high": 0.35,      # Max DD > 35%
                "critical": 0.50   # Max DD > 50%
            },
            "current_drawdown": {
                "medium": 0.15,    # Drawdown actuel > 15%
                "high": 0.25,      # Drawdown actuel > 25%
                "critical": 0.40   # Drawdown actuel > 40%
            },
            "diversification_ratio": {
                "medium": 1.3,     # Ratio < 1.3 (faible)
                "high": 1.1        # Ratio < 1.1 (très faible)
            },
            "concentration": {
                "medium": 0.60,    # Plus de 60% dans un asset
                "high": 0.75,      # Plus de 75% dans un asset
                "critical": 0.90   # Plus de 90% dans un asset
            },
            "sharpe_ratio": {
                "medium": 0.0,     # Sharpe < 0 (négatif)
                "high": -0.5       # Sharpe < -0.5 (très négatif)
            }
        }
    
    def generate_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        recommendation: str,
        current_value: float,
        threshold_value: float,
        affected_assets: List[str] = None
    ) -> RiskAlert:
        """Génère une nouvelle alerte"""
        
        alert_id = f"{category.value}_{alert_type}_{int(datetime.now().timestamp())}"
        
        # Vérifier si alerte existe déjà (cooldown)
        existing_alert = self._find_existing_alert(alert_type, category)
        if existing_alert:
            # Mettre à jour l'alerte existante
            existing_alert.trigger_count += 1
            existing_alert.current_value = current_value
            existing_alert.created_at = datetime.now()
            return existing_alert
        
        # Créer nouvelle alerte
        alert = RiskAlert(
            id=alert_id,
            severity=severity,
            category=category,
            title=title,
            message=message,
            recommendation=recommendation,
            current_value=current_value,
            threshold_value=threshold_value,
            affected_assets=affected_assets or []
        )
        
        # Ajouter à l'historique et aux alertes actives
        self.alert_history.append(alert)
        self.active_alerts[alert_id] = alert
        
        # Nettoyer l'historique si nécessaire
        if len(self.alert_history) > self.max_alert_history:
            self.alert_history = self.alert_history[-self.max_alert_history:]
        
        return alert
    
    def _find_existing_alert(self, alert_type: str, category: AlertCategory) -> Optional[RiskAlert]:
        """Trouve une alerte existante du même type dans la période de cooldown"""
        
        cooldown_threshold = datetime.now() - timedelta(hours=self.alert_cooldown_hours)
        
        for alert in self.active_alerts.values():
            if (alert.category == category and 
                alert_type in alert.id and 
                alert.created_at > cooldown_threshold and
                alert.is_active):
                return alert
        
        return None
    
    def resolve_alert(self, alert_id: str, resolution_note: str = "") -> bool:
        """Résout une alerte active"""
        
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.is_active = False
            alert.resolution_note = resolution_note
            alert.expires_at = datetime.now()
            
            # Retirer des alertes actives
            del self.active_alerts[alert_id]
            return True
        
        return False
    
    def get_active_alerts(self, severity_filter: Optional[AlertSeverity] = None) -> List[RiskAlert]:
        """Récupère les alertes actives, optionnellement filtrées par sévérité"""
        
        alerts = list(self.active_alerts.values())
        
        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]
        
        # Trier par sévérité et date
        severity_order = {
            AlertSeverity.CRITICAL: 5,
            AlertSeverity.HIGH: 4,
            AlertSeverity.MEDIUM: 3,
            AlertSeverity.LOW: 2,
            AlertSeverity.INFO: 1
        }
        
        alerts.sort(key=lambda x: (severity_order[x.severity], x.created_at), reverse=True)
        
        return alerts
    
    def cleanup_expired_alerts(self):
        """Nettoie les alertes expirées"""
        
        now = datetime.now()
        expired_ids = []
        
        for alert_id, alert in self.active_alerts.items():
            if alert.expires_at and alert.expires_at < now:
                expired_ids.append(alert_id)
        
        for alert_id in expired_ids:
            del self.active_alerts[alert_id]

class AdvancedRiskManager:
    """Gestionnaire de risques avancé avec métriques institutionnelles"""
    
    def __init__(self):
        # Cache de données historiques simulées (en production: vraies données)
        self.price_history_cache: Dict[str, deque] = {}
        self.max_history_days = 365
        
        # Paramètres des modèles
        self.var_confidence_levels = [0.95, 0.99]
        self.risk_free_rate = 0.02  # Taux sans risque annuel (2%)
        
        # Scénarios de stress prédéfinis
        self.stress_scenarios = self._build_stress_scenarios()
        
        # Cache des résultats
        self.risk_metrics_cache: Dict[str, RiskMetrics] = {}
        self.correlation_cache: Optional[CorrelationMatrix] = None
        self.cache_ttl = timedelta(hours=1)
        
        # Alertes et seuils
        self.risk_thresholds = {
            RiskLevel.VERY_LOW: {"var_95": 0.02, "volatility": 0.1},
            RiskLevel.LOW: {"var_95": 0.05, "volatility": 0.2},
            RiskLevel.MEDIUM: {"var_95": 0.10, "volatility": 0.4},
            RiskLevel.HIGH: {"var_95": 0.15, "volatility": 0.6},
            RiskLevel.VERY_HIGH: {"var_95": 0.25, "volatility": 1.0},
            RiskLevel.CRITICAL: {"var_95": 0.40, "volatility": 1.5}
        }
        
        # Système d'alertes intelligent
        self.alert_system = AlertSystem()
    
    def _build_stress_scenarios(self) -> Dict[StressScenario, Dict[str, Any]]:
        """Construit les scénarios de stress test basés sur l'historique crypto"""
        
        return {
            StressScenario.BEAR_MARKET_2018: {
                "name": "Bear Market 2018",
                "description": "Crash crypto 2018: BTC -84%, ETH -94%, Altcoins -95%",
                "asset_shocks": {
                    "BTC": -0.84,
                    "ETH": -0.94, 
                    "Stablecoins": 0.0,
                    "L1/L0 majors": -0.95,
                    "L2/Scaling": -0.98,  # N'existaient pas encore
                    "DeFi": -0.98,        # N'existait pas encore
                    "AI/Data": -0.98,
                    "Gaming/NFT": -0.98,
                    "Memecoins": -0.99,
                    "Others": -0.96
                },
                "correlation_increase": 0.3,  # Corrélations augmentent en crise
                "duration_days": 365,
                "volatility_multiplier": 3.0
            },
            
            StressScenario.COVID_CRASH_2020: {
                "name": "COVID Crash Mars 2020", 
                "description": "Liquidation massive: BTC -50% en 2 semaines, tout corrélé",
                "asset_shocks": {
                    "BTC": -0.50,
                    "ETH": -0.60,
                    "Stablecoins": 0.05,  # Flight to safety
                    "L1/L0 majors": -0.65,
                    "L2/Scaling": -0.70,
                    "DeFi": -0.80,        # DeFi panic
                    "AI/Data": -0.75,
                    "Gaming/NFT": -0.80,
                    "Memecoins": -0.85,
                    "Others": -0.70
                },
                "correlation_increase": 0.5,  # Tout devient corrélé
                "duration_days": 14,
                "volatility_multiplier": 5.0
            },
            
            StressScenario.LUNA_COLLAPSE_2022: {
                "name": "Terra Luna Collapse Mai 2022",
                "description": "Effondrement UST/LUNA, contagion DeFi et stablecoins",
                "asset_shocks": {
                    "BTC": -0.30,
                    "ETH": -0.35,
                    "Stablecoins": -0.05,  # Doute sur stablecoins
                    "L1/L0 majors": -0.45,
                    "L2/Scaling": -0.50,
                    "DeFi": -0.70,        # Contagion DeFi forte
                    "AI/Data": -0.40,
                    "Gaming/NFT": -0.55,
                    "Memecoins": -0.60,
                    "Others": -0.50
                },
                "correlation_increase": 0.2,
                "duration_days": 30,
                "volatility_multiplier": 2.5
            },
            
            StressScenario.FTX_COLLAPSE_2022: {
                "name": "FTX Collapse Novembre 2022",
                "description": "Bankruptcy FTX, crise de confiance, liquidité gelée",
                "asset_shocks": {
                    "BTC": -0.25,
                    "ETH": -0.30,
                    "Stablecoins": 0.02,  # Flight to quality stables
                    "L1/L0 majors": -0.35,
                    "L2/Scaling": -0.40,
                    "DeFi": -0.50,        # Liquidité DeFi touchée
                    "AI/Data": -0.30,
                    "Gaming/NFT": -0.45,
                    "Memecoins": -0.55,
                    "Others": -0.40
                },
                "correlation_increase": 0.25,
                "duration_days": 45,
                "volatility_multiplier": 2.0
            }
        }
    
    async def calculate_portfolio_risk_metrics(
        self, 
        holdings: List[Dict[str, Any]],
        price_history_days: int = 30
    ) -> RiskMetrics:
        """
        Calcule les métriques de risque complètes pour un portfolio
        
        Args:
            holdings: Holdings actuels du portfolio
            price_history_days: Nombre de jours d'historique pour calculs
            
        Returns:
            RiskMetrics avec tous les indicateurs de risque
        """
        try:
            logger.info(f"Calcul métriques risque pour {len(holdings)} holdings")
            
            # 1. Préparation des données
            portfolio_value = sum(h.get("value_usd", 0) for h in holdings)
            if portfolio_value <= 0:
                return RiskMetrics()
            
            # 2. Génération historique des prix (simulation - en production: vraies données)
            returns_data = await self._generate_historical_returns(holdings, price_history_days)
            
            if len(returns_data) < 10:  # Minimum de données requis
                logger.warning("Pas assez de données historiques pour calculs fiables")
                return RiskMetrics(confidence_level=0.0)
            
            # 3. Calcul des returns du portfolio
            portfolio_returns = self._calculate_portfolio_returns(holdings, returns_data)
            
            # 4. Calcul VaR/CVaR
            var_metrics = self._calculate_var_cvar(portfolio_returns)
            
            # 5. Métriques de performance ajustées au risque
            perf_metrics = self._calculate_risk_adjusted_metrics(portfolio_returns)
            
            # 6. Analyse des drawdowns
            drawdown_metrics = self._calculate_drawdown_metrics(portfolio_returns)
            
            # 7. Analyse de distribution
            distribution_metrics = self._calculate_distribution_metrics(portfolio_returns)
            
            # 8. Évaluation du niveau de risque global
            risk_assessment = self._assess_overall_risk_level(var_metrics, perf_metrics, drawdown_metrics)
            
            # 9. Construction du résultat final
            metrics = RiskMetrics(
                # VaR/CVaR
                var_95_1d=var_metrics["var_95"],
                var_99_1d=var_metrics["var_99"],
                cvar_95_1d=var_metrics["cvar_95"],
                cvar_99_1d=var_metrics["cvar_99"],
                
                # Performance ajustée au risque
                volatility_annualized=perf_metrics["volatility"],
                sharpe_ratio=perf_metrics["sharpe"],
                sortino_ratio=perf_metrics["sortino"],
                calmar_ratio=perf_metrics["calmar"],
                
                # Drawdowns
                max_drawdown=drawdown_metrics["max_drawdown"],
                max_drawdown_duration_days=drawdown_metrics["max_duration"],
                current_drawdown=drawdown_metrics["current_drawdown"],
                ulcer_index=drawdown_metrics["ulcer_index"],
                
                # Distribution
                skewness=distribution_metrics["skewness"],
                kurtosis=distribution_metrics["kurtosis"],
                
                # Assessment global
                overall_risk_level=risk_assessment["level"],
                risk_score=risk_assessment["score"],
                
                # Metadata
                calculation_date=datetime.now(),
                data_points=len(returns_data),
                confidence_level=min(1.0, len(returns_data) / 30.0)  # Plus de données = plus de confiance
            )
            
            logger.info(f"Métriques calculées: VaR 95%={metrics.var_95_1d:.1%}, "
                       f"Volatilité={metrics.volatility_annualized:.1%}, "
                       f"Risque={risk_assessment['level'].value}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Erreur calcul métriques risque: {e}")
            return RiskMetrics(confidence_level=0.0)
    
    async def _generate_historical_returns(
        self, 
        holdings: List[Dict[str, Any]], 
        days: int
    ) -> List[Dict[str, float]]:
        """Génère l'historique des returns (simulation - en production: vraies données)"""
        
        # Extraire les symboles des holdings
        symbols = [h.get("symbol", "") for h in holdings if h.get("symbol")]
        if not symbols:
            logger.warning("Aucun symbole trouvé dans les holdings")
            return []
        
        # Pour la démo, retourner des données de test réalistes
        returns_series = []
        
        # Générer des returns aléatoires mais réalistes pour chaque jour
        np.random.seed(42)  # Reproductibilité
        
        for day in range(days):
            day_returns = {}
            
            for symbol in symbols:
                # Générer des returns réalistes basés sur le type d'asset
                if symbol == "BTC":
                    return_val = np.random.normal(0.0005, 0.04)  # BTC: moyenne 0.05%, volatilité 4%
                elif symbol == "ETH":
                    return_val = np.random.normal(0.0008, 0.05)  # ETH: moyenne 0.08%, volatilité 5%
                elif symbol in ["USDT", "USDC", "DAI"]:
                    return_val = np.random.normal(0.0001, 0.002)  # Stablecoins: très faible volatilité
                else:
                    return_val = np.random.normal(0.0010, 0.08)  # Altcoins: plus volatile
                
                day_returns[symbol] = float(return_val)
            
            returns_series.append(day_returns)
        
        logger.info(f"Généré {len(returns_series)} jours de données historiques simulées pour {len(symbols)} symboles")
        return returns_series
    
    def _calculate_portfolio_returns(
        self, 
        holdings: List[Dict[str, Any]], 
        returns_data: List[Dict[str, float]]
    ) -> List[float]:
        """Calcule les returns du portfolio basé sur les poids et returns des assets"""
        
        total_value = sum(h.get("value_usd", 0) for h in holdings)
        if total_value <= 0:
            return []
        
        # Calcul des poids
        weights = {}
        for holding in holdings:
            symbol = holding.get("symbol", "")
            weight = holding.get("value_usd", 0) / total_value
            weights[symbol] = weight
        
        # Calcul des returns pondérés du portfolio
        portfolio_returns = []
        
        for day_returns in returns_data:
            portfolio_return = 0.0
            
            for symbol, weight in weights.items():
                asset_return = day_returns.get(symbol, 0.0)
                portfolio_return += weight * asset_return
            
            portfolio_returns.append(portfolio_return)
        
        return portfolio_returns
    
    def _calculate_var_cvar(self, returns: List[float]) -> Dict[str, float]:
        """Calcule Value at Risk et Conditional VaR"""
        
        if len(returns) < 10:
            return {"var_95": 0.0, "var_99": 0.0, "cvar_95": 0.0, "cvar_99": 0.0}
        
        returns_array = np.array(returns)
        
        # VaR historique (percentiles)
        var_95 = -np.percentile(returns_array, 5)   # 5% pire cas
        var_99 = -np.percentile(returns_array, 1)   # 1% pire cas
        
        # CVaR (Expected Shortfall) - moyenne des returns au-delà du VaR
        cvar_95 = -np.mean(returns_array[returns_array <= -var_95]) if var_95 > 0 else 0.0
        cvar_99 = -np.mean(returns_array[returns_array <= -var_99]) if var_99 > 0 else 0.0
        
        return {
            "var_95": var_95,
            "var_99": var_99, 
            "cvar_95": cvar_95,
            "cvar_99": cvar_99
        }
    
    def _calculate_risk_adjusted_metrics(self, returns: List[float]) -> Dict[str, float]:
        """Calcule Sharpe, Sortino, Calmar ratios"""
        
        if len(returns) < 10:
            return {"volatility": 0.0, "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0}
        
        returns_array = np.array(returns)
        
        # Métriques de base
        mean_return = np.mean(returns_array)
        volatility = np.std(returns_array) * np.sqrt(252)  # Annualisé
        
        # Sharpe ratio
        risk_free_daily = self.risk_free_rate / 252
        excess_return = mean_return - risk_free_daily
        sharpe = (excess_return * 252) / volatility if volatility > 0 else 0.0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns_array[returns_array < 0]
        downside_deviation = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0.0
        sortino = (excess_return * 252) / downside_deviation if downside_deviation > 0 else 0.0
        
        # Calmar ratio nécessite max drawdown (calculé séparément)
        cumulative_returns = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        
        annual_return = mean_return * 252
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        
        return {
            "volatility": volatility,
            "sharpe": sharpe,
            "sortino": sortino, 
            "calmar": calmar
        }
    
    def _calculate_drawdown_metrics(self, returns: List[float]) -> Dict[str, Any]:
        """Calcule les métriques de drawdown"""
        
        if len(returns) < 10:
            return {
                "max_drawdown": 0.0,
                "max_duration": 0,
                "current_drawdown": 0.0,
                "ulcer_index": 0.0
            }
        
        returns_array = np.array(returns)
        
        # Calcul des drawdowns
        cumulative_returns = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        
        # Max drawdown
        max_drawdown = abs(np.min(drawdowns))
        
        # Durée du max drawdown
        max_dd_duration = 0
        current_duration = 0
        
        for dd in drawdowns:
            if dd < -0.001:  # Seuil de drawdown significatif
                current_duration += 1
            else:
                max_dd_duration = max(max_dd_duration, current_duration)
                current_duration = 0
        max_dd_duration = max(max_dd_duration, current_duration)
        
        # Current drawdown
        current_drawdown = abs(drawdowns[-1]) if len(drawdowns) > 0 else 0.0
        
        # Ulcer Index (pain index)
        squared_drawdowns = drawdowns ** 2
        ulcer_index = np.sqrt(np.mean(squared_drawdowns))
        
        return {
            "max_drawdown": max_drawdown,
            "max_duration": max_dd_duration,
            "current_drawdown": current_drawdown,
            "ulcer_index": ulcer_index
        }
    
    def _calculate_distribution_metrics(self, returns: List[float]) -> Dict[str, float]:
        """Calcule skewness et kurtosis"""
        
        if len(returns) < 10:
            return {"skewness": 0.0, "kurtosis": 0.0}
        
        returns_array = np.array(returns)
        
        skewness = stats.skew(returns_array)
        kurtosis = stats.kurtosis(returns_array)  # Excess kurtosis
        
        return {
            "skewness": skewness,
            "kurtosis": kurtosis
        }
    
    def _assess_overall_risk_level(
        self, 
        var_metrics: Dict[str, float],
        perf_metrics: Dict[str, float], 
        drawdown_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Évalue le niveau de risque global du portfolio"""
        
        # Score basé sur différents critères
        score = 50.0  # Score de base
        
        # VaR impact
        var_95 = var_metrics.get("var_95", 0.0)
        if var_95 > 0.25:
            score += 30
        elif var_95 > 0.15:
            score += 20
        elif var_95 > 0.10:
            score += 10
        elif var_95 < 0.05:
            score -= 10
        
        # Volatilité impact
        vol = perf_metrics.get("volatility", 0.0)
        if vol > 1.0:
            score += 25
        elif vol > 0.6:
            score += 15
        elif vol > 0.4:
            score += 5
        elif vol < 0.2:
            score -= 15
        
        # Max drawdown impact
        max_dd = drawdown_metrics.get("max_drawdown", 0.0)
        if max_dd > 0.50:
            score += 20
        elif max_dd > 0.30:
            score += 10
        elif max_dd < 0.10:
            score -= 10
        
        # Sharpe ratio impact (inverse)
        sharpe = perf_metrics.get("sharpe", 0.0)
        if sharpe < 0:
            score += 15
        elif sharpe > 1.5:
            score -= 15
        elif sharpe > 1.0:
            score -= 10
        
        # Normaliser le score
        score = max(0, min(100, score))
        
        # Déterminer le niveau de risque
        if score >= 80:
            level = RiskLevel.CRITICAL
        elif score >= 65:
            level = RiskLevel.VERY_HIGH
        elif score >= 50:
            level = RiskLevel.HIGH
        elif score >= 35:
            level = RiskLevel.MEDIUM
        elif score >= 20:
            level = RiskLevel.LOW
        else:
            level = RiskLevel.VERY_LOW
        
        return {
            "level": level,
            "score": score
        }
    
    async def calculate_correlation_matrix(
        self, 
        holdings: List[Dict[str, Any]],
        lookback_days: int = 30
    ) -> CorrelationMatrix:
        """Calcule la matrice de corrélation entre assets avec analyse en composantes principales"""
        
        try:
            logger.info(f"Calcul matrice corrélation pour {len(holdings)} assets")
            
            # Générer historique de returns
            returns_data = await self._generate_historical_returns(holdings, lookback_days)
            
            if len(returns_data) < 10:
                return CorrelationMatrix()
            
            # Construire matrice des returns
            symbols = [h.get("symbol", "") for h in holdings]
            returns_matrix = []
            
            for day_returns in returns_data:
                day_row = [day_returns.get(symbol, 0.0) for symbol in symbols]
                returns_matrix.append(day_row)
            
            returns_df = pd.DataFrame(returns_matrix, columns=symbols)
            
            # Calcul de la matrice de corrélation
            corr_matrix = returns_df.corr()
            
            # Conversion en dictionnaire
            correlations = {}
            for symbol1 in symbols:
                correlations[symbol1] = {}
                for symbol2 in symbols:
                    correlations[symbol1][symbol2] = corr_matrix.loc[symbol1, symbol2]
            
            # Analyse en composantes principales
            eigen_values, eigen_vectors = np.linalg.eigh(corr_matrix.values)
            eigen_values = eigen_values.tolist()
            eigen_vectors = eigen_vectors.tolist()
            
            # Principal components (variance expliquée)
            total_variance = sum(eigen_values)
            principal_components = {}
            for i, eigenval in enumerate(eigen_values):
                principal_components[f"PC{i+1}"] = eigenval / total_variance if total_variance > 0 else 0
            
            # Ratio de diversification
            portfolio_weights = np.array([h.get("value_usd", 0) for h in holdings])
            portfolio_weights = portfolio_weights / np.sum(portfolio_weights)
            
            portfolio_variance = np.dot(portfolio_weights, np.dot(corr_matrix.values, portfolio_weights))
            weighted_avg_variance = np.dot(portfolio_weights**2, np.ones(len(symbols)))
            diversification_ratio = np.sqrt(weighted_avg_variance / portfolio_variance) if portfolio_variance > 0 else 1.0
            
            # Nombre effectif d'assets (inverse participation ratio)
            effective_assets = 1.0 / np.sum(portfolio_weights**4) if len(portfolio_weights) > 0 else 1.0
            
            correlation_matrix = CorrelationMatrix(
                correlations=correlations,
                eigen_values=eigen_values,
                eigen_vectors=eigen_vectors,
                principal_components=principal_components,
                diversification_ratio=diversification_ratio,
                effective_assets=effective_assets,
                last_updated=datetime.now()
            )
            
            logger.info(f"Corrélation calculée: ratio diversification={diversification_ratio:.2f}, "
                       f"assets effectifs={effective_assets:.1f}")
            
            return correlation_matrix
            
        except Exception as e:
            logger.error(f"Erreur calcul matrice corrélation: {e}")
            return CorrelationMatrix()
    
    async def run_stress_test(
        self, 
        holdings: List[Dict[str, Any]], 
        scenario: StressScenario,
        custom_shocks: Optional[Dict[str, float]] = None
    ) -> StressTestResult:
        """Exécute un stress test sur le portfolio"""
        
        try:
            scenario_config = self.stress_scenarios.get(scenario, {})
            if not scenario_config and not custom_shocks:
                raise ValueError(f"Scénario {scenario} non trouvé et pas de shocks personnalisés")
            
            logger.info(f"Stress test: {scenario.value}")
            
            # Utiliser shocks personnalisés ou prédéfinis
            if custom_shocks:
                asset_shocks = custom_shocks
                scenario_name = "Custom Scenario"
                scenario_desc = "Scénario personnalisé défini par l'utilisateur"
            else:
                asset_shocks = scenario_config["asset_shocks"]
                scenario_name = scenario_config["name"]
                scenario_desc = scenario_config["description"]
            
            # Calcul des impacts par asset
            taxonomy = Taxonomy.load()
            total_portfolio_value = sum(h.get("value_usd", 0) for h in holdings)
            
            asset_impacts = []
            total_loss = 0.0
            
            for holding in holdings:
                symbol = holding.get("symbol", "")
                alias = holding.get("alias", symbol)
                group = taxonomy.group_for_alias(alias)
                value = holding.get("value_usd", 0)
                
                # Trouver le shock applicable
                shock = asset_shocks.get(group, asset_shocks.get("Others", -0.30))
                
                # Calculer l'impact
                loss_amount = value * abs(shock)
                loss_pct = shock
                
                asset_impacts.append({
                    "symbol": symbol,
                    "group": group,
                    "value_before": value,
                    "shock_pct": loss_pct,
                    "loss_usd": loss_amount,
                    "value_after": value * (1 + shock)
                })
                
                total_loss += loss_amount
            
            # Trier par impact (pires performances)
            asset_impacts.sort(key=lambda x: x["shock_pct"])
            
            worst_performers = asset_impacts[:3]
            best_performers = asset_impacts[-3:]
            
            # Calcul du loss total du portfolio
            portfolio_loss_pct = total_loss / total_portfolio_value if total_portfolio_value > 0 else 0.0
            
            # Vérifier si VaR est dépassé (nécessite calcul préalable)
            current_metrics = await self.calculate_portfolio_risk_metrics(holdings)
            var_breach = portfolio_loss_pct > current_metrics.var_99_1d
            
            # Estimation temps de récupération (basé sur scénarios historiques)
            if scenario_config:
                base_recovery = scenario_config.get("duration_days", 90)
                # Ajustement selon la sévérité
                severity_multiplier = min(3.0, portfolio_loss_pct / 0.20)  # 20% = 1x
                recovery_time = int(base_recovery * severity_multiplier)
            else:
                recovery_time = int(90 * (portfolio_loss_pct / 0.20))  # Estimation basique
            
            # Contribution au risque par asset
            risk_contributions = {}
            for impact in asset_impacts:
                contribution = abs(impact["loss_usd"]) / total_loss if total_loss > 0 else 0.0
                risk_contributions[impact["symbol"]] = contribution
            
            result = StressTestResult(
                scenario_name=scenario_name,
                scenario_description=scenario_desc,
                portfolio_loss_pct=portfolio_loss_pct,
                portfolio_loss_usd=total_loss,
                worst_performing_assets=worst_performers,
                best_performing_assets=best_performers,
                var_breach=var_breach,
                recovery_time_estimate_days=recovery_time,
                risk_contribution=risk_contributions
            )
            
            logger.info(f"Stress test terminé: perte {portfolio_loss_pct:.1%} (${total_loss:,.0f})")
            return result
            
        except Exception as e:
            logger.error(f"Erreur stress test: {e}")
            return StressTestResult(
                scenario_name="Error",
                scenario_description=f"Erreur: {str(e)}",
                portfolio_loss_pct=0.0,
                portfolio_loss_usd=0.0,
                worst_performing_assets=[],
                best_performing_assets=[],
                var_breach=False,
                recovery_time_estimate_days=0,
                risk_contribution={}
            )

    async def calculate_performance_attribution(
        self,
        holdings: List[Dict[str, Any]],
        analysis_days: int = 30,
        benchmark_portfolio: Optional[List[Dict[str, Any]]] = None
    ) -> PerformanceAttribution:
        """
        Calcule l'attribution de performance détaillée du portfolio
        
        Décompose la performance en contributions individuelles par asset et par groupe,
        incluant les effets de sélection, allocation et interaction
        
        Args:
            holdings: Holdings actuels du portfolio
            analysis_days: Période d'analyse en jours
            benchmark_portfolio: Portfolio de référence pour comparaison (optionnel)
            
        Returns:
            PerformanceAttribution avec analyse détaillée
        """
        try:
            logger.info(f"Calcul attribution performance sur {analysis_days} jours")
            
            # 1. Validation des données
            portfolio_value = sum(h.get("value_usd", 0) for h in holdings)
            if portfolio_value <= 0:
                return PerformanceAttribution(total_return=0.0, total_return_usd=0.0)
            
            # 2. Génération historique des returns
            returns_data = await self._generate_historical_returns(holdings, analysis_days)
            if len(returns_data) < 2:
                return PerformanceAttribution(total_return=0.0, total_return_usd=0.0)
            
            # 3. Calcul des returns et contributions individuelles par asset
            asset_contributions = self._calculate_asset_contributions(holdings, returns_data, portfolio_value)
            
            # 4. Agrégation par groupe d'assets
            group_contributions = self._calculate_group_contributions(holdings, asset_contributions)
            
            # 5. Calcul des effets d'attribution (sélection, allocation, interaction)
            attribution_effects = self._calculate_attribution_effects(
                asset_contributions, 
                group_contributions,
                benchmark_portfolio,
                returns_data
            )
            
            # 6. Calcul du return total du portfolio
            total_return_pct = sum(contrib["contribution_pct"] for contrib in asset_contributions)
            total_return_usd = sum(contrib["contribution_usd"] for contrib in asset_contributions)
            
            # 7. Construction du résultat
            period_end = datetime.now()
            period_start = period_end - timedelta(days=analysis_days)
            
            attribution = PerformanceAttribution(
                total_return=total_return_pct,
                total_return_usd=total_return_usd,
                asset_contributions=asset_contributions,
                group_contributions=group_contributions,
                selection_effect=attribution_effects["selection"],
                allocation_effect=attribution_effects["allocation"], 
                interaction_effect=attribution_effects["interaction"],
                period_start=period_start,
                period_end=period_end,
                analysis_period_days=analysis_days,
                calculation_date=datetime.now(),
                benchmark_used="Equal Weight" if benchmark_portfolio is None else "Custom"
            )
            
            logger.info(f"Attribution calculée: return total {total_return_pct:.2%} "
                       f"(${total_return_usd:,.0f}) sur {analysis_days} jours")
            
            return attribution
            
        except Exception as e:
            logger.error(f"Erreur calcul attribution performance: {e}")
            return PerformanceAttribution(total_return=0.0, total_return_usd=0.0)
    
    def _calculate_asset_contributions(
        self,
        holdings: List[Dict[str, Any]],
        returns_data: List[Dict[str, float]],
        portfolio_value: float
    ) -> List[Dict[str, Any]]:
        """Calcule les contributions individuelles de chaque asset"""
        
        asset_contributions = []
        
        for holding in holdings:
            symbol = holding.get("symbol", "")
            value = holding.get("value_usd", 0)
            weight = value / portfolio_value if portfolio_value > 0 else 0
            
            # Calculer le return de l'asset sur la période
            asset_returns = [day.get(symbol, 0.0) for day in returns_data]
            if len(asset_returns) == 0:
                continue
                
            # Return cumulé de l'asset
            cumulative_return = np.prod([1 + r for r in asset_returns]) - 1
            
            # Contribution à la performance du portfolio = poids × return
            contribution_pct = weight * cumulative_return
            contribution_usd = value * cumulative_return
            
            # Volatilité et Sharpe de l'asset
            asset_volatility = np.std(asset_returns) * np.sqrt(252) if len(asset_returns) > 1 else 0.0
            asset_sharpe = (np.mean(asset_returns) * 252) / asset_volatility if asset_volatility > 0 else 0.0
            
            # Classification taxonomique
            from services.taxonomy import Taxonomy
            taxonomy = Taxonomy.load()
            alias = holding.get("alias", symbol)
            group = taxonomy.group_for_alias(alias)
            
            asset_contributions.append({
                "symbol": symbol,
                "alias": alias,
                "group": group,
                "weight": weight,
                "value_usd": value,
                "asset_return": cumulative_return,
                "contribution_pct": contribution_pct,
                "contribution_usd": contribution_usd,
                "volatility": asset_volatility,
                "sharpe_ratio": asset_sharpe,
                "daily_returns": asset_returns
            })
        
        # Trier par contribution décroissante
        asset_contributions.sort(key=lambda x: x["contribution_pct"], reverse=True)
        
        return asset_contributions
    
    def _calculate_group_contributions(
        self,
        holdings: List[Dict[str, Any]],
        asset_contributions: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Agrège les contributions par groupe d'assets"""
        
        group_stats = {}
        
        # Regrouper par groupe taxonomique
        for contrib in asset_contributions:
            group = contrib["group"]
            
            if group not in group_stats:
                group_stats[group] = {
                    "group_name": group,
                    "num_assets": 0,
                    "total_weight": 0.0,
                    "total_value_usd": 0.0,
                    "group_return": 0.0,
                    "contribution_pct": 0.0,
                    "contribution_usd": 0.0,
                    "average_volatility": 0.0,
                    "group_sharpe": 0.0,
                    "assets": []
                }
            
            # Accumulation des statistiques
            stats = group_stats[group]
            stats["num_assets"] += 1
            stats["total_weight"] += contrib["weight"]
            stats["total_value_usd"] += contrib["value_usd"]
            stats["contribution_pct"] += contrib["contribution_pct"]
            stats["contribution_usd"] += contrib["contribution_usd"]
            stats["assets"].append(contrib["symbol"])
        
        # Calcul des métriques moyennes par groupe
        for group, stats in group_stats.items():
            if stats["num_assets"] > 0:
                # Return moyen pondéré du groupe
                if stats["total_weight"] > 0:
                    weighted_return = stats["contribution_pct"] / stats["total_weight"]
                    stats["group_return"] = weighted_return
                
                # Volatilité moyenne du groupe
                group_assets = [c for c in asset_contributions if c["group"] == group]
                if group_assets:
                    weighted_volatilities = sum(c["weight"] * c["volatility"] for c in group_assets)
                    stats["average_volatility"] = weighted_volatilities / stats["total_weight"] if stats["total_weight"] > 0 else 0.0
                    
                    # Sharpe moyen du groupe
                    weighted_sharpes = sum(c["weight"] * c["sharpe_ratio"] for c in group_assets if not np.isnan(c["sharpe_ratio"]))
                    stats["group_sharpe"] = weighted_sharpes / stats["total_weight"] if stats["total_weight"] > 0 else 0.0
        
        return group_stats
    
    def _calculate_attribution_effects(
        self,
        asset_contributions: List[Dict[str, Any]],
        group_contributions: Dict[str, Dict[str, Any]], 
        benchmark_portfolio: Optional[List[Dict[str, Any]]],
        returns_data: List[Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Calcule les effets d'attribution Brinson-style:
        - Selection Effect: Impact du choix d'assets spécifiques dans chaque groupe
        - Allocation Effect: Impact de la sur/sous-pondération de groupes
        - Interaction Effect: Effet combiné allocation × sélection
        """
        
        # Benchmark par défaut: equal weight sur tous les groupes
        if benchmark_portfolio is None:
            # Créer un benchmark equal-weight
            unique_groups = set(contrib["group"] for contrib in asset_contributions)
            benchmark_weight_per_group = 1.0 / len(unique_groups) if unique_groups else 0.0
            benchmark_weights = {group: benchmark_weight_per_group for group in unique_groups}
        else:
            # Utiliser le benchmark fourni (non implémenté pour la démo)
            benchmark_weights = {}
        
        # Calcul des returns de benchmark par groupe (moyenne des assets du groupe)
        benchmark_returns = {}
        for group in group_contributions.keys():
            group_assets = [c for c in asset_contributions if c["group"] == group]
            if group_assets:
                # Return moyen non-pondéré des assets du groupe (benchmark)
                avg_return = np.mean([c["asset_return"] for c in group_assets])
                benchmark_returns[group] = avg_return
            else:
                benchmark_returns[group] = 0.0
        
        # Calcul des effets
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0
        
        for group, stats in group_contributions.items():
            portfolio_weight = stats["total_weight"]
            benchmark_weight = benchmark_weights.get(group, portfolio_weight)
            portfolio_return = stats["group_return"]
            benchmark_return = benchmark_returns.get(group, 0.0)
            
            # Allocation Effect = (Portfolio Weight - Benchmark Weight) × Benchmark Return
            allocation_effect += (portfolio_weight - benchmark_weight) * benchmark_return
            
            # Selection Effect = Benchmark Weight × (Portfolio Return - Benchmark Return)
            selection_effect += benchmark_weight * (portfolio_return - benchmark_return)
            
            # Interaction Effect = (Portfolio Weight - Benchmark Weight) × (Portfolio Return - Benchmark Return)
            interaction_effect += (portfolio_weight - benchmark_weight) * (portfolio_return - benchmark_return)
        
        return {
            "allocation": allocation_effect,
            "selection": selection_effect,
            "interaction": interaction_effect
        }
    
    async def run_strategy_backtest(
        self,
        strategy_name: str,
        target_allocations: Dict[str, float],
        backtest_days: int = 180,
        rebalance_frequency_days: int = 30,
        transaction_cost_pct: float = 0.001  # 0.1% de coût par transaction
    ) -> BacktestResult:
        """
        Exécute un backtest d'une stratégie d'allocation sur historique simulé
        
        Args:
            strategy_name: Nom de la stratégie
            target_allocations: Allocations cibles par groupe d'assets (ex: {"BTC": 0.4, "ETH": 0.3, "DeFi": 0.3})
            backtest_days: Nombre de jours de backtest
            rebalance_frequency_days: Fréquence de rebalancing en jours
            transaction_cost_pct: Coût de transaction en % du volume tradé
            
        Returns:
            BacktestResult avec performance et métriques détaillées
        """
        try:
            logger.info(f"Début backtest stratégie '{strategy_name}' sur {backtest_days} jours")
            
            # 1. Validation des allocations cibles
            total_allocation = sum(target_allocations.values())
            if abs(total_allocation - 1.0) > 0.01:
                raise ValueError(f"Allocations cibles doivent sommer à 100% (actuellement {total_allocation:.1%})")
            
            # 2. Génération de l'univers d'assets et historique de prix
            universe_holdings = self._generate_asset_universe(target_allocations)
            price_history = await self._generate_historical_returns(universe_holdings, backtest_days + 30)
            
            if len(price_history) < backtest_days:
                raise ValueError("Pas assez de données historiques pour le backtest")
            
            # 3. Simulation du backtest jour par jour
            backtest_result = await self._simulate_backtest(
                strategy_name=strategy_name,
                target_allocations=target_allocations, 
                universe_holdings=universe_holdings,
                price_history=price_history[-backtest_days:],  # Prendre les derniers jours
                rebalance_frequency=rebalance_frequency_days,
                transaction_cost=transaction_cost_pct
            )
            
            logger.info(f"Backtest terminé: return {backtest_result.total_return:.2%}, "
                       f"Sharpe {backtest_result.sharpe_ratio:.2f}, "
                       f"Max DD {backtest_result.max_drawdown:.2%}")
            
            return backtest_result
            
        except Exception as e:
            logger.error(f"Erreur backtest: {e}")
            return BacktestResult(
                strategy_name=strategy_name,
                strategy_description=f"Erreur: {str(e)}",
                total_return=0.0,
                annualized_return=0.0,
                volatility=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                benchmark_return=0.0,
                active_return=0.0,
                information_ratio=0.0,
                tracking_error=0.0,
                var_95=0.0,
                downside_deviation=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                num_rebalances=0,
                avg_turnover=0.0,
                total_costs=0.0,
                backtest_days=0
            )
    
    def _generate_asset_universe(self, target_allocations: Dict[str, float]) -> List[Dict[str, Any]]:
        """Génère un univers d'assets représentatifs pour chaque groupe d'allocation"""
        
        universe = []
        
        # Mapping des groupes vers des assets représentatifs
        group_representatives = {
            "BTC": [{"symbol": "BTC", "alias": "bitcoin", "value_usd": 10000}],
            "ETH": [{"symbol": "ETH", "alias": "ethereum", "value_usd": 10000}],
            "Stablecoins": [
                {"symbol": "USDT", "alias": "tether", "value_usd": 5000},
                {"symbol": "USDC", "alias": "usd-coin", "value_usd": 5000}
            ],
            "L1/L0 majors": [
                {"symbol": "SOL", "alias": "solana", "value_usd": 3000},
                {"symbol": "ADA", "alias": "cardano", "value_usd": 3000},
                {"symbol": "DOT", "alias": "polkadot", "value_usd": 2000}
            ],
            "L2/Scaling": [
                {"symbol": "MATIC", "alias": "polygon", "value_usd": 2000},
                {"symbol": "AVAX", "alias": "avalanche", "value_usd": 2000}
            ],
            "DeFi": [
                {"symbol": "UNI", "alias": "uniswap", "value_usd": 2000},
                {"symbol": "AAVE", "alias": "aave", "value_usd": 2000},
                {"symbol": "LINK", "alias": "chainlink", "value_usd": 2000}
            ],
            "AI/Data": [
                {"symbol": "FET", "alias": "fetch-ai", "value_usd": 1000},
                {"symbol": "OCEAN", "alias": "ocean-protocol", "value_usd": 1000}
            ],
            "Gaming/NFT": [
                {"symbol": "AXS", "alias": "axie-infinity", "value_usd": 1000},
                {"symbol": "SAND", "alias": "the-sandbox", "value_usd": 1000}
            ],
            "Memecoins": [
                {"symbol": "DOGE", "alias": "dogecoin", "value_usd": 500},
                {"symbol": "SHIB", "alias": "shiba-inu", "value_usd": 500}
            ]
        }
        
        # Créer l'univers basé sur les allocations cibles
        for group, allocation in target_allocations.items():
            if group in group_representatives:
                universe.extend(group_representatives[group])
            else:
                # Groupe inconnu, créer un asset générique
                universe.append({
                    "symbol": f"{group}_REP", 
                    "alias": group.lower().replace(" ", "-"),
                    "value_usd": allocation * 10000  # Base 10k portfolio
                })
        
        return universe
    
    async def _simulate_backtest(
        self,
        strategy_name: str,
        target_allocations: Dict[str, float],
        universe_holdings: List[Dict[str, Any]],
        price_history: List[Dict[str, float]], 
        rebalance_frequency: int,
        transaction_cost: float
    ) -> BacktestResult:
        """Simule le backtest jour par jour avec rebalancing périodique"""
        
        # Initialisation
        initial_portfolio_value = 100000.0  # Portfolio de 100k$ initial
        portfolio_values = [initial_portfolio_value]
        benchmark_values = [initial_portfolio_value]
        dates = []
        rebalancing_dates = []
        
        # État du portfolio et benchmark
        current_holdings = {}  # symbol -> quantity
        current_cash = 0.0
        total_costs = 0.0
        num_rebalances = 0
        
        # Benchmark: equal weight sur tous les assets
        benchmark_weights = {h["symbol"]: 1.0 / len(universe_holdings) for h in universe_holdings}
        benchmark_holdings = {}
        
        # Classification taxonomique pour mappage
        from services.taxonomy import Taxonomy
        taxonomy = Taxonomy.load()
        
        # Initialisation des holdings (jour 0)
        for holding in universe_holdings:
            symbol = holding["symbol"]
            alias = holding.get("alias", symbol)
            group = taxonomy.group_for_alias(alias)
            
            # Allocation cible pour ce groupe
            target_weight = target_allocations.get(group, 0.0)
            target_value = initial_portfolio_value * target_weight / sum(
                1 for h in universe_holdings 
                if taxonomy.group_for_alias(h.get("alias", h["symbol"])) == group
            )
            
            # Prix initial (jour 0 = référence)
            initial_price = 100.0  # Prix de référence
            quantity = target_value / initial_price
            
            current_holdings[symbol] = quantity
            benchmark_holdings[symbol] = (initial_portfolio_value * benchmark_weights[symbol]) / initial_price
        
        # Simulation jour par jour
        for day_idx, day_returns in enumerate(price_history):
            current_date = datetime.now() - timedelta(days=len(price_history) - day_idx - 1)
            dates.append(current_date)
            
            # Calcul de la valeur actuelle du portfolio et benchmark
            portfolio_value = current_cash
            benchmark_value = 0.0
            
            for symbol, quantity in current_holdings.items():
                if symbol in day_returns and quantity > 0:
                    # Prix actuel = prix initial × prod(1 + return_daily) 
                    cumulative_return = np.prod([1 + price_history[i].get(symbol, 0.0) for i in range(day_idx + 1)])
                    current_price = 100.0 * cumulative_return
                    portfolio_value += quantity * current_price
            
            for symbol, quantity in benchmark_holdings.items():
                if symbol in day_returns and quantity > 0:
                    cumulative_return = np.prod([1 + price_history[i].get(symbol, 0.0) for i in range(day_idx + 1)])
                    current_price = 100.0 * cumulative_return
                    benchmark_value += quantity * current_price
            
            portfolio_values.append(portfolio_value)
            benchmark_values.append(benchmark_value)
            
            # Rebalancing périodique
            if day_idx > 0 and day_idx % rebalance_frequency == 0:
                rebalancing_dates.append(current_date)
                
                # Calculer les nouveaux targets
                for holding in universe_holdings:
                    symbol = holding["symbol"]
                    alias = holding.get("alias", symbol)
                    group = taxonomy.group_for_alias(alias)
                    
                    target_weight = target_allocations.get(group, 0.0)
                    assets_in_group = sum(
                        1 for h in universe_holdings 
                        if taxonomy.group_for_alias(h.get("alias", h["symbol"])) == group
                    )
                    target_value = portfolio_value * target_weight / max(1, assets_in_group)
                    
                    # Prix actuel
                    cumulative_return = np.prod([1 + price_history[i].get(symbol, 0.0) for i in range(day_idx + 1)])
                    current_price = 100.0 * cumulative_return
                    
                    target_quantity = target_value / current_price if current_price > 0 else 0
                    current_quantity = current_holdings.get(symbol, 0)
                    
                    # Trade et coûts
                    trade_quantity = abs(target_quantity - current_quantity)
                    trade_cost = trade_quantity * current_price * transaction_cost
                    total_costs += trade_cost
                    
                    current_holdings[symbol] = target_quantity
                
                num_rebalances += 1
        
        # Calcul des métriques finales
        portfolio_returns = [
            (portfolio_values[i] / portfolio_values[i-1] - 1) 
            for i in range(1, len(portfolio_values))
        ]
        
        benchmark_returns = [
            (benchmark_values[i] / benchmark_values[i-1] - 1) 
            for i in range(1, len(benchmark_values))
        ]
        
        # Performance metrics
        total_return = (portfolio_values[-1] / portfolio_values[0]) - 1
        benchmark_total_return = (benchmark_values[-1] / benchmark_values[0]) - 1
        
        trading_days = len(portfolio_returns)
        annualized_return = (1 + total_return) ** (252 / trading_days) - 1 if trading_days > 0 else 0.0
        volatility = np.std(portfolio_returns) * np.sqrt(252) if len(portfolio_returns) > 1 else 0.0
        
        # Sharpe ratio
        risk_free_rate = 0.02
        excess_return = annualized_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0.0
        
        # Max drawdown
        portfolio_series = np.array(portfolio_values)
        running_max = np.maximum.accumulate(portfolio_series)
        drawdowns = (portfolio_series - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        
        # Active return et tracking error
        active_returns = [p_ret - b_ret for p_ret, b_ret in zip(portfolio_returns, benchmark_returns)]
        active_return = annualized_return - ((1 + benchmark_total_return) ** (252 / trading_days) - 1)
        tracking_error = np.std(active_returns) * np.sqrt(252) if len(active_returns) > 1 else 0.0
        information_ratio = active_return / tracking_error if tracking_error > 0 else 0.0
        
        # Risk metrics
        var_95 = -np.percentile(portfolio_returns, 5) if len(portfolio_returns) >= 20 else 0.0
        downside_returns = [r for r in portfolio_returns if r < 0]
        downside_deviation = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 1 else 0.0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0.0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0.0
        
        # Turnover moyen
        avg_turnover = total_costs / (num_rebalances * np.mean(portfolio_values)) if num_rebalances > 0 else 0.0
        
        return BacktestResult(
            strategy_name=strategy_name,
            strategy_description=f"Allocation cible: {target_allocations}",
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            benchmark_return=benchmark_total_return,
            active_return=active_return,
            information_ratio=information_ratio,
            tracking_error=tracking_error,
            var_95=var_95,
            downside_deviation=downside_deviation,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            num_rebalances=num_rebalances,
            avg_turnover=avg_turnover,
            total_costs=total_costs,
            portfolio_values=portfolio_values[1:],  # Exclure valeur initiale
            benchmark_values=benchmark_values[1:],
            dates=dates,
            rebalancing_dates=rebalancing_dates,
            backtest_start=dates[0] if dates else datetime.now(),
            backtest_end=dates[-1] if dates else datetime.now(),
            backtest_days=len(dates)
        )
    
    async def generate_intelligent_alerts(
        self,
        holdings: List[Dict[str, Any]],
        risk_metrics: Optional[RiskMetrics] = None,
        correlation_matrix: Optional[CorrelationMatrix] = None
    ) -> List[RiskAlert]:
        """
        Génère des alertes intelligentes basées sur l'analyse complète du portfolio
        
        Args:
            holdings: Holdings actuels
            risk_metrics: Métriques de risque (calculées si non fournies)
            correlation_matrix: Matrice de corrélation (calculée si non fournie)
            
        Returns:
            Liste des alertes générées
        """
        try:
            logger.info("Génération d'alertes intelligentes")
            
            # Calcul des métriques si non fournies
            if risk_metrics is None:
                risk_metrics = await self.calculate_portfolio_risk_metrics(holdings)
            
            if correlation_matrix is None:
                correlation_matrix = await self.calculate_correlation_matrix(holdings)
            
            # Nettoyer les alertes expirées
            self.alert_system.cleanup_expired_alerts()
            
            alerts = []
            
            # 1. Alertes de seuils de risque
            alerts.extend(self._check_risk_threshold_alerts(risk_metrics))
            
            # 2. Alertes de performance
            alerts.extend(self._check_performance_alerts(risk_metrics))
            
            # 3. Alertes de corrélation/diversification
            alerts.extend(self._check_correlation_alerts(correlation_matrix))
            
            # 4. Alertes de concentration
            alerts.extend(self._check_concentration_alerts(holdings))
            
            # 5. Alertes de qualité de données
            alerts.extend(self._check_data_quality_alerts(risk_metrics, correlation_matrix))
            
            # 6. Alertes de rebalancing (si applicable)
            alerts.extend(await self._check_rebalancing_alerts(holdings))
            
            logger.info(f"Générées {len(alerts)} nouvelles alertes")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Erreur génération alertes: {e}")
            return []
    
    def _check_risk_threshold_alerts(self, risk_metrics: RiskMetrics) -> List[RiskAlert]:
        """Vérifie les dépassements de seuils de risque"""
        
        alerts = []
        thresholds = self.alert_system.thresholds
        
        # VaR 95%
        var_95 = risk_metrics.var_95_1d
        if var_95 > thresholds["var_95"]["critical"]:
            alerts.append(self.alert_system.generate_alert(
                "var_95_critical", AlertSeverity.CRITICAL, AlertCategory.RISK_THRESHOLD,
                "VaR Critique Dépassé",
                f"VaR 95% à {var_95:.1%} dépasse le seuil critique de {thresholds['var_95']['critical']:.1%}",
                "Réduction immédiate de l'exposition au risque recommandée",
                var_95, thresholds["var_95"]["critical"]
            ))
        elif var_95 > thresholds["var_95"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "var_95_high", AlertSeverity.HIGH, AlertCategory.RISK_THRESHOLD,
                "VaR Élevé",
                f"VaR 95% à {var_95:.1%} dépasse le seuil élevé de {thresholds['var_95']['high']:.1%}",
                "Surveiller étroitement et considérer réduction du risque",
                var_95, thresholds["var_95"]["high"]
            ))
        elif var_95 > thresholds["var_95"]["medium"]:
            alerts.append(self.alert_system.generate_alert(
                "var_95_medium", AlertSeverity.MEDIUM, AlertCategory.RISK_THRESHOLD,
                "VaR Modéré",
                f"VaR 95% à {var_95:.1%} dépasse le seuil modéré de {thresholds['var_95']['medium']:.1%}",
                "Révision de la stratégie de risque conseillée",
                var_95, thresholds["var_95"]["medium"]
            ))
        
        # Volatilité
        volatility = risk_metrics.volatility_annualized
        if volatility > thresholds["volatility"]["critical"]:
            alerts.append(self.alert_system.generate_alert(
                "volatility_critical", AlertSeverity.CRITICAL, AlertCategory.RISK_THRESHOLD,
                "Volatilité Extrême",
                f"Volatilité annualisée à {volatility:.1%} dépasse le seuil critique",
                "Rebalancing vers assets moins volatils urgent",
                volatility, thresholds["volatility"]["critical"]
            ))
        elif volatility > thresholds["volatility"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "volatility_high", AlertSeverity.HIGH, AlertCategory.RISK_THRESHOLD,
                "Volatilité Élevée",
                f"Volatilité à {volatility:.1%} indique un portfolio très risqué",
                "Considérer diversification vers assets moins volatils",
                volatility, thresholds["volatility"]["high"]
            ))
        
        # Drawdown actuel
        current_dd = risk_metrics.current_drawdown
        if current_dd > thresholds["current_drawdown"]["critical"]:
            alerts.append(self.alert_system.generate_alert(
                "drawdown_critical", AlertSeverity.CRITICAL, AlertCategory.RISK_THRESHOLD,
                "Drawdown Critique",
                f"Drawdown actuel de {current_dd:.1%} nécessite action immédiate",
                "Stop-loss ou hedging recommandé pour limiter les pertes",
                current_dd, thresholds["current_drawdown"]["critical"]
            ))
        elif current_dd > thresholds["current_drawdown"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "drawdown_high", AlertSeverity.HIGH, AlertCategory.RISK_THRESHOLD,
                "Drawdown Important", 
                f"Drawdown de {current_dd:.1%} indique des pertes significatives",
                "Surveillance rapprochée et préparation de mesures défensives",
                current_dd, thresholds["current_drawdown"]["high"]
            ))
        
        return alerts
    
    def _check_performance_alerts(self, risk_metrics: RiskMetrics) -> List[RiskAlert]:
        """Vérifie les alertes liées à la performance"""
        
        alerts = []
        thresholds = self.alert_system.thresholds
        
        # Sharpe ratio négatif
        sharpe = risk_metrics.sharpe_ratio
        if sharpe < thresholds["sharpe_ratio"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "sharpe_very_negative", AlertSeverity.HIGH, AlertCategory.PERFORMANCE,
                "Sharpe Ratio Très Négatif",
                f"Sharpe ratio de {sharpe:.2f} indique performance très mauvaise vs risque",
                "Révision complète de la stratégie d'investissement nécessaire",
                sharpe, thresholds["sharpe_ratio"]["high"]
            ))
        elif sharpe < thresholds["sharpe_ratio"]["medium"]:
            alerts.append(self.alert_system.generate_alert(
                "sharpe_negative", AlertSeverity.MEDIUM, AlertCategory.PERFORMANCE,
                "Performance Négative",
                f"Sharpe ratio négatif ({sharpe:.2f}) indique rendement inférieur au risque libre",
                "Optimisation du ratio risque/rendement recommandée",
                sharpe, thresholds["sharpe_ratio"]["medium"]
            ))
        
        # Max drawdown excessif
        max_dd = risk_metrics.max_drawdown
        if max_dd > thresholds["max_drawdown"]["critical"]:
            alerts.append(self.alert_system.generate_alert(
                "max_drawdown_critical", AlertSeverity.CRITICAL, AlertCategory.PERFORMANCE,
                "Drawdown Historique Extrême",
                f"Maximum drawdown de {max_dd:.1%} indique risque de ruine élevé",
                "Révision fondamentale de la gestion du risque requise",
                max_dd, thresholds["max_drawdown"]["critical"]
            ))
        elif max_dd > thresholds["max_drawdown"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "max_drawdown_high", AlertSeverity.HIGH, AlertCategory.PERFORMANCE,
                "Drawdown Historique Élevé",
                f"Max drawdown de {max_dd:.1%} suggère stratégie trop agressive",
                "Implémentation de stop-loss et diversification renforcée",
                max_dd, thresholds["max_drawdown"]["high"]
            ))
        
        return alerts
    
    def _check_correlation_alerts(self, correlation_matrix: CorrelationMatrix) -> List[RiskAlert]:
        """Vérifie les alertes de corrélation et diversification"""
        
        alerts = []
        thresholds = self.alert_system.thresholds
        
        # Faible diversification
        div_ratio = correlation_matrix.diversification_ratio
        if div_ratio < thresholds["diversification_ratio"]["high"]:
            alerts.append(self.alert_system.generate_alert(
                "diversification_very_low", AlertSeverity.HIGH, AlertCategory.CORRELATION,
                "Diversification Très Faible",
                f"Ratio de diversification de {div_ratio:.2f} indique assets très corrélés",
                "Ajout urgent d'assets non-corrélés ou de classes d'actifs différentes",
                div_ratio, thresholds["diversification_ratio"]["high"]
            ))
        elif div_ratio < thresholds["diversification_ratio"]["medium"]:
            alerts.append(self.alert_system.generate_alert(
                "diversification_low", AlertSeverity.MEDIUM, AlertCategory.CORRELATION,
                "Diversification Insuffisante",
                f"Ratio de {div_ratio:.2f} suggère un manque de diversification",
                "Rechercher des assets moins corrélés pour améliorer la diversification",
                div_ratio, thresholds["diversification_ratio"]["medium"]
            ))
        
        # Corrélations extrêmes (>90% entre assets principaux)
        high_correlations = []
        for asset1, correlations in correlation_matrix.correlations.items():
            for asset2, corr in correlations.items():
                if asset1 != asset2 and abs(corr) > 0.90:
                    high_correlations.append((asset1, asset2, corr))
        
        if len(high_correlations) > 2:  # Plus de 2 paires très corrélées
            affected_assets = list(set([pair[0] for pair in high_correlations] + [pair[1] for pair in high_correlations]))
            alerts.append(self.alert_system.generate_alert(
                "extreme_correlations", AlertSeverity.MEDIUM, AlertCategory.CORRELATION,
                "Corrélations Extrêmes Détectées",
                f"Plusieurs paires d'assets avec corrélation >90%: {len(high_correlations)} paires",
                "Remplacer certains assets par des alternatives moins corrélées",
                len(high_correlations), 2,
                affected_assets
            ))
        
        return alerts
    
    def _check_concentration_alerts(self, holdings: List[Dict[str, Any]]) -> List[RiskAlert]:
        """Vérifie les alertes de concentration"""
        
        alerts = []
        thresholds = self.alert_system.thresholds
        
        total_value = sum(h.get("value_usd", 0) for h in holdings)
        if total_value <= 0:
            return alerts
        
        # Vérifier concentration par asset individuel
        for holding in holdings:
            weight = holding.get("value_usd", 0) / total_value
            symbol = holding.get("symbol", "Unknown")
            
            if weight > thresholds["concentration"]["critical"]:
                alerts.append(self.alert_system.generate_alert(
                    f"concentration_{symbol}_critical", AlertSeverity.CRITICAL, AlertCategory.CONCENTRATION,
                    "Concentration Critique",
                    f"{symbol} représente {weight:.1%} du portfolio (seuil critique dépassé)",
                    "Diversification immédiate requise pour réduire le risque de concentration",
                    weight, thresholds["concentration"]["critical"],
                    [symbol]
                ))
            elif weight > thresholds["concentration"]["high"]:
                alerts.append(self.alert_system.generate_alert(
                    f"concentration_{symbol}_high", AlertSeverity.HIGH, AlertCategory.CONCENTRATION,
                    "Forte Concentration",
                    f"{symbol} représente {weight:.1%} du portfolio",
                    "Considérer réduire l'exposition pour améliorer la diversification",
                    weight, thresholds["concentration"]["high"],
                    [symbol]
                ))
        
        # Vérifier concentration par groupe
        from services.taxonomy import Taxonomy
        taxonomy = Taxonomy.load()
        
        group_weights = {}
        for holding in holdings:
            alias = holding.get("alias", holding.get("symbol", ""))
            group = taxonomy.group_for_alias(alias)
            weight = holding.get("value_usd", 0) / total_value
            group_weights[group] = group_weights.get(group, 0) + weight
        
        for group, weight in group_weights.items():
            if weight > thresholds["concentration"]["high"]:
                group_assets = [h.get("symbol", "") for h in holdings 
                              if taxonomy.group_for_alias(h.get("alias", h.get("symbol", ""))) == group]
                
                alerts.append(self.alert_system.generate_alert(
                    f"group_concentration_{group}", AlertSeverity.MEDIUM, AlertCategory.CONCENTRATION,
                    f"Concentration Groupe {group}",
                    f"Groupe {group} représente {weight:.1%} du portfolio",
                    "Diversifier vers d'autres groupes d'assets pour réduire le risque sectoriel",
                    weight, thresholds["concentration"]["high"],
                    group_assets
                ))
        
        return alerts
    
    def _check_data_quality_alerts(self, risk_metrics: RiskMetrics, correlation_matrix: CorrelationMatrix) -> List[RiskAlert]:
        """Vérifie la qualité et fiabilité des données"""
        
        alerts = []
        
        # Confiance faible dans les calculs
        if risk_metrics.confidence_level < 0.5:
            alerts.append(self.alert_system.generate_alert(
                "data_confidence_low", AlertSeverity.MEDIUM, AlertCategory.DATA_QUALITY,
                "Confiance Faible dans les Données",
                f"Niveau de confiance de {risk_metrics.confidence_level:.1%} indique données insuffisantes",
                "Collecter plus de données historiques pour améliorer la fiabilité",
                risk_metrics.confidence_level, 0.5
            ))
        
        # Données manquantes
        if risk_metrics.data_points < 10:
            alerts.append(self.alert_system.generate_alert(
                "insufficient_data", AlertSeverity.HIGH, AlertCategory.DATA_QUALITY,
                "Données Insuffisantes",
                f"Seulement {risk_metrics.data_points} points de données disponibles",
                "Minimum 30 points recommandés pour des calculs de risque fiables",
                risk_metrics.data_points, 30
            ))
        
        return alerts
    
    async def _check_rebalancing_alerts(self, holdings: List[Dict[str, Any]]) -> List[RiskAlert]:
        """Vérifie si un rebalancing est nécessaire"""
        
        alerts = []
        
        try:
            # Calculer la dérive par rapport aux allocations cibles (exemple simple)
            # En pratique, il faudrait avoir des allocations cibles définies
            
            # Pour la démo, vérifier si certains assets ont beaucoup évolué
            total_value = sum(h.get("value_usd", 0) for h in holdings)
            if total_value <= 0:
                return alerts
            
            # Générer returns récents simulés pour estimer la dérive
            recent_returns = await self._generate_historical_returns(holdings, 7)  # 7 derniers jours
            
            large_moves = []
            for holding in holdings:
                symbol = holding.get("symbol", "")
                if symbol in recent_returns[-1]:  # Dernier jour
                    recent_return = sum(day.get(symbol, 0.0) for day in recent_returns[-7:])  # Return 7 jours
                    if abs(recent_return) > 0.20:  # Mouvement > 20% en 7 jours
                        large_moves.append((symbol, recent_return))
            
            if len(large_moves) >= 3:  # Plus de 3 assets avec gros mouvements
                affected_symbols = [move[0] for move in large_moves]
                alerts.append(self.alert_system.generate_alert(
                    "rebalancing_needed", AlertSeverity.MEDIUM, AlertCategory.REBALANCING,
                    "Rebalancing Recommandé",
                    f"{len(large_moves)} assets ont eu des mouvements >20% cette semaine",
                    "Considérer un rebalancing pour maintenir les allocations cibles",
                    len(large_moves), 3,
                    affected_symbols
                ))
            
        except Exception as e:
            logger.warning(f"Erreur vérification rebalancing: {e}")
        
        return alerts

# Instance globale du gestionnaire de risques
risk_manager = AdvancedRiskManager()
