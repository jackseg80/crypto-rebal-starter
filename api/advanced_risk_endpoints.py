"""
Advanced Risk Management API Endpoints - Phase 3A
Provides VaR, stress testing, Monte Carlo, and risk attribution via REST API
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
from datetime import datetime

from services.risk.advanced_risk_engine import (
    AdvancedRiskEngine, create_advanced_risk_engine, 
    VaRMethod, RiskHorizon, StressScenario, VaRResult, 
    StressTestResult, MonteCarloResult
)

router = APIRouter(prefix="/api/risk/advanced", tags=["risk-management"])
log = logging.getLogger(__name__)

# Response Models
class VaRResponse(BaseModel):
    var_value: float = Field(..., description="Value-at-Risk en devise de base")
    expected_shortfall: float = Field(..., description="Expected Shortfall (CVaR)")
    confidence_level: float = Field(..., description="Niveau de confiance (0.95, 0.99)")
    method: str = Field(..., description="Méthode utilisée")
    horizon: str = Field(..., description="Horizon temporel")
    portfolio_value: float = Field(..., description="Valeur du portefeuille")
    timestamp: datetime = Field(..., description="Timestamp du calcul")

class StressTestResponse(BaseModel):
    scenario: str = Field(..., description="Nom du scénario de stress")
    portfolio_loss: float = Field(..., description="Perte absolue du portefeuille")
    portfolio_loss_pct: float = Field(..., description="Perte en pourcentage")
    asset_impacts: Dict[str, float] = Field(..., description="Impact par actif")
    shock_applied: Dict[str, float] = Field(..., description="Chocs appliqués par actif")
    recovery_estimate_days: Optional[int] = Field(None, description="Estimation de récupération en jours")
    timestamp: datetime = Field(..., description="Timestamp du calcul")

class MonteCarloResponse(BaseModel):
    simulations: int = Field(..., description="Nombre de simulations")
    var_estimates: Dict[str, float] = Field(..., description="Estimations VaR par niveau de confiance")
    expected_return: float = Field(..., description="Retour espéré")
    volatility: float = Field(..., description="Volatilité estimée")
    skewness: float = Field(..., description="Asymétrie")
    kurtosis: float = Field(..., description="Kurtosis")
    extreme_scenarios: Dict[str, float] = Field(..., description="Scénarios extrêmes (percentiles)")
    tail_expectation: float = Field(..., description="Espérance de queue")
    timestamp: datetime = Field(..., description="Timestamp du calcul")

class RiskAttributionResponse(BaseModel):
    marginal_var: Dict[str, float] = Field(..., description="VaR marginale par actif")
    component_var: Dict[str, float] = Field(..., description="VaR composant par actif")
    concentration_risk: float = Field(..., description="Score de concentration")
    diversification_ratio: float = Field(..., description="Ratio de diversification")
    risk_contribution_pct: Dict[str, float] = Field(..., description="Contribution au risque en %")
    timestamp: datetime = Field(..., description="Timestamp du calcul")

class AdvancedRiskSummaryResponse(BaseModel):
    portfolio_value: float
    var_daily_95: float
    var_daily_99: float
    stress_test_worst: Dict[str, Any]
    monte_carlo_summary: Dict[str, Any]
    concentration_risk: float
    risk_score: float = Field(..., description="Score de risque global (0-100)")
    alerts_triggered: List[str] = Field(default_factory=list)
    timestamp: datetime

# Request Models
class PortfolioRequest(BaseModel):
    weights: Dict[str, float] = Field(..., description="Poids du portefeuille par asset")
    value: float = Field(..., gt=0, description="Valeur totale du portefeuille")
    
    @validator('weights')
    def weights_must_sum_to_one(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f'Poids doivent sommer à 1.0, trouvé: {total:.4f}')
        return v

# Dependency to get risk engine
def get_risk_engine() -> AdvancedRiskEngine:
    """Create risk engine instance for request"""
    try:
        # Default config if not available
        config = {
            "enabled": True,
            "var": {"lookback_days": 252, "min_observations": 100},
            "monte_carlo": {"simulations": 10000, "distribution": "student_t"}
        }
        return create_advanced_risk_engine(config)
    except Exception as e:
        log.error(f"Failed to create risk engine: {e}")
        raise HTTPException(500, "risk_engine_initialization_failed")

@router.post("/var/calculate", response_model=VaRResponse)
async def calculate_var(
    portfolio: PortfolioRequest,
    method: str = Query("parametric", description="Méthode: parametric, historical, monte_carlo"),
    confidence_level: float = Query(0.95, ge=0.9, le=0.999, description="Niveau de confiance"),
    horizon: str = Query("daily", description="Horizon: daily, weekly, monthly"),
    risk_engine: AdvancedRiskEngine = Depends(get_risk_engine)
):
    """Calcule Value-at-Risk pour un portefeuille donné"""
    try:
        # Parse method and horizon
        var_method = VaRMethod(method)
        risk_horizon = RiskHorizon(horizon)
        
        # Calculate VaR
        result = await risk_engine.calculate_var(
            portfolio_weights=portfolio.weights,
            portfolio_value=portfolio.value,
            method=var_method,
            confidence_level=confidence_level,
            horizon=risk_horizon
        )
        
        return VaRResponse(
            var_value=result.var_value,
            expected_shortfall=result.expected_shortfall,
            confidence_level=result.confidence_level,
            method=result.method.value,
            horizon=result.horizon.value,
            portfolio_value=result.portfolio_value,
            timestamp=result.timestamp
        )
        
    except ValueError as e:
        raise HTTPException(400, f"invalid_parameter: {str(e)}")
    except Exception as e:
        log.exception(f"VaR calculation failed: {e}")
        raise HTTPException(500, "var_calculation_failed")

@router.post("/stress-test/run", response_model=StressTestResponse)
async def run_stress_test(
    portfolio: PortfolioRequest,
    scenario: str = Query(..., description="Scénario: crisis_2008, covid_2020, china_ban, tether_collapse, fed_emergency"),
    risk_engine: AdvancedRiskEngine = Depends(get_risk_engine)
):
    """Execute un test de stress sur le portefeuille"""
    try:
        # Parse scenario
        stress_scenario = StressScenario(scenario)
        
        # Run stress test
        result = await risk_engine.run_stress_test(
            portfolio_weights=portfolio.weights,
            portfolio_value=portfolio.value,
            scenario=stress_scenario
        )
        
        return StressTestResponse(
            scenario=result.scenario.value,
            portfolio_loss=result.portfolio_loss,
            portfolio_loss_pct=result.portfolio_loss_pct,
            asset_impacts=result.asset_impacts,
            shock_applied=result.shock_applied,
            recovery_estimate_days=result.recovery_estimate_days,
            timestamp=result.timestamp
        )
        
    except ValueError as e:
        raise HTTPException(400, f"invalid_scenario: {str(e)}")
    except Exception as e:
        log.exception(f"Stress test failed: {e}")
        raise HTTPException(500, "stress_test_failed")

@router.post("/monte-carlo/simulate", response_model=MonteCarloResponse)
async def monte_carlo_simulation(
    portfolio: PortfolioRequest,
    simulations: int = Query(10000, ge=1000, le=100000, description="Nombre de simulations"),
    horizon_days: int = Query(30, ge=1, le=365, description="Horizon en jours"),
    distribution: str = Query("student_t", description="Distribution: normal, student_t"),
    risk_engine: AdvancedRiskEngine = Depends(get_risk_engine)
):
    """Execute simulation Monte Carlo pour scénarios extrêmes"""
    try:
        result = await risk_engine.run_monte_carlo_simulation(
            portfolio_weights=portfolio.weights,
            portfolio_value=portfolio.value,
            num_simulations=simulations,
            horizon_days=horizon_days,
            distribution=distribution
        )
        
        return MonteCarloResponse(
            simulations=result.simulations,
            var_estimates=result.var_estimates,
            expected_return=result.expected_return,
            volatility=result.volatility,
            skewness=result.skewness,
            kurtosis=result.kurtosis,
            extreme_scenarios=result.extreme_scenarios,
            tail_expectation=result.tail_expectation,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        log.exception(f"Monte Carlo simulation failed: {e}")
        raise HTTPException(500, "monte_carlo_simulation_failed")

@router.post("/attribution/analyze", response_model=RiskAttributionResponse)
async def analyze_risk_attribution(
    portfolio: PortfolioRequest,
    confidence_level: float = Query(0.95, ge=0.9, le=0.999),
    risk_engine: AdvancedRiskEngine = Depends(get_risk_engine)
):
    """Analyse d'attribution du risque par composant"""
    try:
        result = await risk_engine.get_risk_attribution(
            portfolio_weights=portfolio.weights,
            portfolio_value=portfolio.value,
            confidence_level=confidence_level
        )
        
        return RiskAttributionResponse(
            marginal_var=result.marginal_var,
            component_var=result.component_var,
            concentration_risk=result.concentration_risk,
            diversification_ratio=result.diversification_ratio,
            risk_contribution_pct=result.risk_contribution_pct,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        log.exception(f"Risk attribution analysis failed: {e}")
        raise HTTPException(500, "risk_attribution_failed")

@router.post("/summary", response_model=AdvancedRiskSummaryResponse)
async def get_risk_summary(
    portfolio: PortfolioRequest,
    include_stress_tests: bool = Query(True, description="Inclure les tests de stress"),
    include_monte_carlo: bool = Query(True, description="Inclure Monte Carlo"),
    risk_engine: AdvancedRiskEngine = Depends(get_risk_engine)
):
    """Résumé complet des métriques de risque avancées"""
    try:
        # Calculate VaR daily 95% and 99%
        var_95 = await risk_engine.calculate_var(
            portfolio.weights, portfolio.value, 
            VaRMethod.PARAMETRIC, 0.95, RiskHorizon.DAILY
        )
        var_99 = await risk_engine.calculate_var(
            portfolio.weights, portfolio.value,
            VaRMethod.PARAMETRIC, 0.99, RiskHorizon.DAILY
        )
        
        # Risk attribution for concentration
        attribution = await risk_engine.get_risk_attribution(
            portfolio.weights, portfolio.value, 0.95
        )
        
        # Stress test (worst case)
        stress_result = None
        if include_stress_tests:
            stress_result = await risk_engine.run_stress_test(
                portfolio.weights, portfolio.value, StressScenario.CRISIS_2008
            )
        
        # Monte Carlo summary
        mc_result = None
        if include_monte_carlo:
            mc_result = await risk_engine.run_monte_carlo_simulation(
                portfolio.weights, portfolio.value, 5000, 30
            )
        
        # Calculate global risk score (0-100)
        risk_score = min(100, max(0, 
            (var_99.var_value / portfolio.value) * 1000 + 
            attribution.concentration_risk * 20
        ))
        
        # Check for alerts
        alerts_triggered = []
        if var_95.var_value / portfolio.value > 0.05:
            alerts_triggered.append("VAR_95_BREACH")
        if var_99.var_value / portfolio.value > 0.08:
            alerts_triggered.append("VAR_99_BREACH")
        if attribution.concentration_risk > 0.8:
            alerts_triggered.append("HIGH_CONCENTRATION")
        
        return AdvancedRiskSummaryResponse(
            portfolio_value=portfolio.value,
            var_daily_95=var_95.var_value,
            var_daily_99=var_99.var_value,
            stress_test_worst={
                "scenario": stress_result.scenario.value if stress_result else None,
                "loss_pct": stress_result.portfolio_loss_pct if stress_result else None
            },
            monte_carlo_summary={
                "var_95": mc_result.var_estimates.get("95%") if mc_result else None,
                "tail_expectation": mc_result.tail_expectation if mc_result else None
            },
            concentration_risk=attribution.concentration_risk,
            risk_score=risk_score,
            alerts_triggered=alerts_triggered,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        log.exception(f"Risk summary calculation failed: {e}")
        raise HTTPException(500, "risk_summary_failed")

@router.get("/scenarios/list")
async def list_stress_scenarios():
    """Liste des scénarios de stress disponibles"""
    return {
        "scenarios": [
            {
                "id": "crisis_2008",
                "name": "Crise Financière 2008",
                "description": "Chocs basés sur la crise des subprimes"
            },
            {
                "id": "covid_2020", 
                "name": "Crash COVID-19 2020",
                "description": "Effondrement des marchés mars 2020"
            },
            {
                "id": "china_ban",
                "name": "Interdiction Crypto Chine",
                "description": "Impact des annonces gouvernementales chinoises"
            },
            {
                "id": "tether_collapse",
                "name": "Effondrement Tether",
                "description": "Scénario de dépegging USDT"
            },
            {
                "id": "fed_emergency",
                "name": "Taux d'Urgence Fed",
                "description": "Hausse brutale des taux directeurs"
            }
        ]
    }

@router.get("/methods/info")
async def get_methods_info():
    """Information sur les méthodes disponibles"""
    return {
        "var_methods": {
            "parametric": {
                "name": "VaR Paramétrique",
                "description": "Basé sur distribution normale/Student-t",
                "performance": "Très rapide",
                "accuracy": "Bonne pour marchés normaux"
            },
            "historical": {
                "name": "VaR Historique", 
                "description": "Basé sur données historiques",
                "performance": "Rapide",
                "accuracy": "Bonne capture des queues de distribution"
            },
            "monte_carlo": {
                "name": "VaR Monte Carlo",
                "description": "Simulation stochastique",
                "performance": "Plus lent",
                "accuracy": "Très précis pour scénarios complexes"
            }
        },
        "horizons": {
            "daily": "Risque sur 1 jour",
            "weekly": "Risque sur 1 semaine", 
            "monthly": "Risque sur 1 mois"
        },
        "distributions": {
            "normal": "Distribution normale (Gaussienne)",
            "student_t": "Distribution Student-t (queues épaisses, recommandée crypto)"
        }
    }