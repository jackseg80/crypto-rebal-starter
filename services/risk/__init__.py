"""
Risk Management Package - Module de gestion des risques

Architecture modulaire extraite de services/risk_management.py pour améliorer
la maintenabilité et réduire la complexité.

Modules:
- models: Dataclasses et enums (RiskMetrics, CorrelationMatrix, etc.)
- alert_system: Système d'alertes intelligent
- var_calculator: Calculs VaR/CVaR et métriques de risque

Usage:
    from services.risk import VaRCalculator, AlertSystem, RiskMetrics

    # Ou pour backward compatibility:
    from services.risk_management import AdvancedRiskManager  # Wrapper
"""

# Exports des modèles
from .models import (
    RiskLevel,
    StressScenario,
    AlertSeverity,
    AlertCategory,
    RiskMetrics,
    CorrelationMatrix,
    StressTestResult,
    PerformanceAttribution,
    BacktestResult,
    RiskAlert,
)

# Exports des classes fonctionnelles
from .alert_system import AlertSystem, get_alert_system
from .var_calculator import VaRCalculator, get_var_calculator

# Pour backward compatibility, réexporter les noms courants
__all__ = [
    # Enums
    "RiskLevel",
    "StressScenario",
    "AlertSeverity",
    "AlertCategory",

    # Dataclasses
    "RiskMetrics",
    "CorrelationMatrix",
    "StressTestResult",
    "PerformanceAttribution",
    "BacktestResult",
    "RiskAlert",

    # Classes fonctionnelles
    "AlertSystem",
    "VaRCalculator",

    # Fonctions helper
    "get_alert_system",
    "get_var_calculator",
]
