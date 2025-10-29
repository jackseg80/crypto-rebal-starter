"""
Risk Management Models - Dataclasses et Enums

Contient toutes les structures de données pour le système de risk management.
Extrait de services/risk_management.py pour améliorer la modularité.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Dict, List, Any, Optional


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
