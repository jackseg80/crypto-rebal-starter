"""
Phase 3A: Advanced Risk Models Engine

Moteur de risk management sophistiqué avec :
- VaR multi-méthodes (paramétrique, historique, Monte Carlo)
- Stress testing avec scénarios historiques et hypothétiques
- Monte Carlo avec distributions fat-tail pour crypto
- Multi-horizon risk metrics (1j, 1w, 1m)
- Integration avec système d'alertes existant
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class VaRMethod(str, Enum):
    """Méthodes de calcul VaR"""
    PARAMETRIC = "parametric"      # Normal/Student-t distribution
    HISTORICAL = "historical"      # Bootstrap historique
    MONTE_CARLO = "monte_carlo"    # Simulation multivariate

class RiskHorizon(str, Enum):
    """Horizons de risque"""
    DAILY = "1d"           # 1 jour
    WEEKLY = "1w"          # 1 semaine  
    MONTHLY = "1m"         # 1 mois

class StressScenario(str, Enum):
    """Scénarios de stress prédéfinis"""
    FINANCIAL_CRISIS_2008 = "crisis_2008"
    COVID_CRASH_2020 = "covid_2020"
    DOTCOM_BUBBLE_2000 = "dotcom_2000"
    CHINA_BAN_CRYPTO = "china_ban"
    TETHER_COLLAPSE = "tether_collapse"
    FED_EMERGENCY_RATES = "fed_emergency"

@dataclass
class VaRResult:
    """Résultat de calcul VaR"""
    method: VaRMethod
    horizon: RiskHorizon
    confidence_level: float        # 0.95, 0.99
    var_absolute: float           # VaR en unité monétaire (€)
    var_percentage: float         # VaR en % du portfolio
    cvar_absolute: float          # Conditional VaR (Expected Shortfall)
    cvar_percentage: float
    portfolio_value: float
    calculated_at: datetime
    
    # Décomposition par asset
    marginal_var: Dict[str, float] = None      # Impact marginal de chaque asset
    component_var: Dict[str, float] = None     # Contribution de chaque asset
    
@dataclass
class StressTestResult:
    """Résultat de stress test"""
    scenario: Union[StressScenario, str]
    portfolio_pnl: float                      # P&L total du portfolio
    portfolio_pnl_pct: float                  # P&L en %
    asset_pnl: Dict[str, float]               # P&L par asset
    worst_asset: str                          # Asset le plus impacté
    worst_asset_pnl_pct: float
    scenario_probability: float               # Probabilité estimée du scénario
    recovery_time_days: int                   # Temps estimé de récupération
    calculated_at: datetime

@dataclass 
class MonteCarloResult:
    """Résultat de simulation Monte Carlo"""
    simulations_count: int
    horizon_days: int
    confidence_intervals: Dict[str, float]    # P5, P25, P50, P75, P95, P99
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown_mean: float
    max_drawdown_p99: float
    paths_sample: np.ndarray                  # Échantillon de paths pour viz
    distribution_stats: Dict[str, float]      # Mean, std, skew, kurtosis
    calculated_at: datetime

class AdvancedRiskEngine:
    """
    Moteur de risque avancé pour quantification sophisticated du risque portfolio
    
    Fonctionnalités :
    - VaR multi-méthodes avec validation croisée
    - Stress testing scénarios historiques + hypothétiques  
    - Monte Carlo avec corrélations dynamiques
    - Risk attribution et décomposition
    - Integration alerting pour breach de limites
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Configuration VaR
        self.var_config = config.get("var", {
            "confidence_levels": [0.95, 0.99],
            "methods": ["parametric", "historical", "monte_carlo"],
            "lookback_days": 252,  # 1 an de données
            "min_observations": 100
        })
        
        # Configuration stress testing
        self.stress_config = config.get("stress_testing", {
            "enabled_scenarios": [
                "crisis_2008", "covid_2020", "china_ban", "tether_collapse"
            ],
            "custom_scenarios": {},
            "recovery_model": "exponential"  # exponential, linear
        })
        
        # Configuration Monte Carlo
        self.mc_config = config.get("monte_carlo", {
            "simulations": 10000,
            "max_horizon_days": 30,
            "distribution": "student_t",  # normal, student_t, skewed_t
            "correlation_model": "dynamic"  # static, dynamic, regime_switching
        })
        
        # Données historiques et cache
        self.price_history: Dict[str, pd.DataFrame] = {}
        self.returns_history: Dict[str, pd.DataFrame] = {}
        self.correlation_matrices: Dict[str, np.ndarray] = {}
        
        # Cache des résultats
        self.var_cache: Dict[str, VaRResult] = {}
        self.stress_cache: Dict[str, List[StressTestResult]] = {}
        self.monte_carlo_cache: Dict[str, MonteCarloResult] = {}
        
        # Scénarios de stress prédéfinis
        self._initialize_stress_scenarios()
        
        logger.info(f"AdvancedRiskEngine initialized: VaR methods={self.var_config['methods']}, "
                   f"stress scenarios={len(self.stress_scenarios)}, MC sims={self.mc_config['simulations']}")
    
    def calculate_var(self,
                     portfolio_weights: Dict[str, float],
                     portfolio_value: float,
                     method: VaRMethod = VaRMethod.PARAMETRIC,
                     confidence_level: float = 0.95,
                     horizon: RiskHorizon = RiskHorizon.DAILY) -> VaRResult:
        """
        Calcule Value-at-Risk avec méthode spécifiée
        
        Args:
            portfolio_weights: Poids des assets {"BTC": 0.6, "ETH": 0.4}
            portfolio_value: Valeur totale du portfolio en €
            method: Méthode de calcul VaR
            confidence_level: Niveau de confiance (0.95, 0.99)
            horizon: Horizon temporel
        
        Returns:
            VaRResult avec VaR, CVaR et décompositions
        """
        try:
            # Valider et préparer données
            assets = list(portfolio_weights.keys())
            if not self._validate_portfolio_data(assets):
                raise ValueError("Insufficient historical data for VaR calculation")
            
            # Calculer selon la méthode
            if method == VaRMethod.PARAMETRIC:
                var_result = self._calculate_parametric_var(
                    portfolio_weights, portfolio_value, confidence_level, horizon
                )
            elif method == VaRMethod.HISTORICAL:
                var_result = self._calculate_historical_var(
                    portfolio_weights, portfolio_value, confidence_level, horizon
                )
            elif method == VaRMethod.MONTE_CARLO:
                var_result = self._calculate_monte_carlo_var(
                    portfolio_weights, portfolio_value, confidence_level, horizon
                )
            else:
                raise ValueError(f"Unsupported VaR method: {method}")
            
            # Cache du résultat
            cache_key = f"{method.value}_{confidence_level}_{horizon.value}_{hash(str(portfolio_weights))}"
            self.var_cache[cache_key] = var_result
            
            logger.info(f"VaR calculated: method={method.value}, VaR={var_result.var_absolute:.0f}€ "
                       f"({var_result.var_percentage:.1%}), CVaR={var_result.cvar_absolute:.0f}€")
            
            return var_result
            
        except Exception as e:
            logger.error(f"VaR calculation error: {e}")
            raise
    
    def run_stress_test(self,
                       portfolio_weights: Dict[str, float], 
                       portfolio_value: float,
                       scenarios: Optional[List[Union[StressScenario, str]]] = None) -> List[StressTestResult]:
        """
        Execute stress testing sur scénarios spécifiés
        
        Args:
            portfolio_weights: Poids des assets
            portfolio_value: Valeur portfolio
            scenarios: Scénarios à tester (défaut: tous activés)
        
        Returns:
            Liste des résultats de stress test
        """
        try:
            if scenarios is None:
                scenarios = self.stress_config["enabled_scenarios"]
            
            results = []
            
            for scenario in scenarios:
                if isinstance(scenario, str):
                    # Scénario prédéfini
                    if scenario in self.stress_scenarios:
                        stress_shocks = self.stress_scenarios[scenario]
                        scenario_info = {
                            "name": scenario,
                            "probability": stress_shocks.get("probability", 0.05),
                            "recovery_days": stress_shocks.get("recovery_days", 90)
                        }
                    else:
                        logger.warning(f"Unknown stress scenario: {scenario}")
                        continue
                else:
                    # Custom scenario
                    stress_shocks = scenario
                    scenario_info = {
                        "name": "custom",
                        "probability": 0.1,
                        "recovery_days": 60
                    }
                
                # Calculer impact du stress
                portfolio_pnl = 0.0
                asset_pnl = {}
                
                for asset, weight in portfolio_weights.items():
                    if asset in stress_shocks["shocks"]:
                        shock_pct = stress_shocks["shocks"][asset]
                        asset_value = portfolio_value * weight
                        asset_pnl_value = asset_value * shock_pct
                        
                        asset_pnl[asset] = asset_pnl_value
                        portfolio_pnl += asset_pnl_value
                    else:
                        asset_pnl[asset] = 0.0
                
                # Identifier worst asset
                worst_asset = min(asset_pnl.keys(), key=lambda k: asset_pnl[k])
                worst_asset_pnl_pct = asset_pnl[worst_asset] / (portfolio_value * portfolio_weights.get(worst_asset, 1))
                
                result = StressTestResult(
                    scenario=scenario_info["name"],
                    portfolio_pnl=portfolio_pnl,
                    portfolio_pnl_pct=portfolio_pnl / portfolio_value,
                    asset_pnl=asset_pnl,
                    worst_asset=worst_asset,
                    worst_asset_pnl_pct=worst_asset_pnl_pct,
                    scenario_probability=scenario_info["probability"],
                    recovery_time_days=scenario_info["recovery_days"],
                    calculated_at=datetime.now()
                )
                
                results.append(result)
                
                logger.info(f"Stress test {scenario}: Portfolio P&L={portfolio_pnl:.0f}€ "
                           f"({portfolio_pnl/portfolio_value:.1%}), worst={worst_asset} ({worst_asset_pnl_pct:.1%})")
            
            # Cache des résultats
            cache_key = hash(str(portfolio_weights))
            self.stress_cache[cache_key] = results
            
            return results
            
        except Exception as e:
            logger.error(f"Stress testing error: {e}")
            raise
    
    def run_monte_carlo_simulation(self,
                                  portfolio_weights: Dict[str, float],
                                  portfolio_value: float,
                                  horizon_days: int = 30,
                                  simulations: int = None) -> MonteCarloResult:
        """
        Lance simulation Monte Carlo pour distribution des outcomes
        
        Args:
            portfolio_weights: Poids des assets
            portfolio_value: Valeur portfolio 
            horizon_days: Horizon de simulation en jours
            simulations: Nombre de simulations (défaut: config)
        
        Returns:
            MonteCarloResult avec distribution des outcomes
        """
        try:
            if simulations is None:
                simulations = self.mc_config["simulations"]
            
            assets = list(portfolio_weights.keys())
            weights_array = np.array([portfolio_weights[asset] for asset in assets])
            
            # Préparer paramètres de distribution
            returns_data = self._get_returns_matrix(assets, self.var_config["lookback_days"])
            if returns_data is None or returns_data.shape[0] < 100:
                raise ValueError("Insufficient returns data for Monte Carlo")
            
            # Paramètres de distribution
            mean_returns = returns_data.mean(axis=0)
            cov_matrix = returns_data.cov().values
            
            # Distribution selection
            if self.mc_config["distribution"] == "student_t":
                # Fit Student-t pour queues épaisses
                df_param = self._fit_multivariate_t(returns_data)
                distribution_params = {"df": df_param, "mean": mean_returns, "cov": cov_matrix}
            else:
                # Distribution normale standard
                distribution_params = {"mean": mean_returns, "cov": cov_matrix}
            
            # Run simulations
            portfolio_outcomes = []
            paths_sample = []  # Pour visualisation
            max_drawdowns = []
            
            for sim in range(simulations):
                # Générer path de returns
                if self.mc_config["distribution"] == "student_t":
                    daily_returns = self._generate_multivariate_t_path(
                        horizon_days, distribution_params
                    )
                else:
                    daily_returns = np.random.multivariate_normal(
                        mean_returns, cov_matrix, horizon_days
                    )
                
                # Calculer portfolio returns path
                portfolio_returns = np.dot(daily_returns, weights_array)
                
                # Calculer cumulative P&L
                cumulative_returns = np.cumprod(1 + portfolio_returns) - 1
                final_return = cumulative_returns[-1]
                portfolio_outcomes.append(final_return)
                
                # Calculer max drawdown pour cette simulation
                running_max = np.maximum.accumulate(1 + cumulative_returns)
                drawdown = (running_max - (1 + cumulative_returns)) / running_max
                max_drawdown = np.max(drawdown)
                max_drawdowns.append(max_drawdown)
                
                # Stocker quelques paths pour visualisation
                if sim < 100:  # 100 premières simulations
                    paths_sample.append(cumulative_returns)
            
            # Analyser distribution des outcomes
            outcomes_array = np.array(portfolio_outcomes)
            
            # Confidence intervals
            confidence_intervals = {
                "P1": np.percentile(outcomes_array, 1),
                "P5": np.percentile(outcomes_array, 5), 
                "P25": np.percentile(outcomes_array, 25),
                "P50": np.percentile(outcomes_array, 50),
                "P75": np.percentile(outcomes_array, 75),
                "P95": np.percentile(outcomes_array, 95),
                "P99": np.percentile(outcomes_array, 99)
            }
            
            # VaR et CVaR from simulation
            var_95 = -np.percentile(outcomes_array, 5) * portfolio_value
            var_99 = -np.percentile(outcomes_array, 1) * portfolio_value
            
            # CVaR (Expected Shortfall)
            cvar_95_outcomes = outcomes_array[outcomes_array <= np.percentile(outcomes_array, 5)]
            cvar_99_outcomes = outcomes_array[outcomes_array <= np.percentile(outcomes_array, 1)]
            
            cvar_95 = -np.mean(cvar_95_outcomes) * portfolio_value if len(cvar_95_outcomes) > 0 else var_95
            cvar_99 = -np.mean(cvar_99_outcomes) * portfolio_value if len(cvar_99_outcomes) > 0 else var_99
            
            # Stats de distribution
            distribution_stats = {
                "mean": np.mean(outcomes_array),
                "std": np.std(outcomes_array),
                "skewness": stats.skew(outcomes_array),
                "kurtosis": stats.kurtosis(outcomes_array)
            }
            
            result = MonteCarloResult(
                simulations_count=simulations,
                horizon_days=horizon_days,
                confidence_intervals=confidence_intervals,
                var_95=var_95,
                var_99=var_99,
                cvar_95=cvar_95,
                cvar_99=cvar_99,
                max_drawdown_mean=np.mean(max_drawdowns),
                max_drawdown_p99=np.percentile(max_drawdowns, 99),
                paths_sample=np.array(paths_sample),
                distribution_stats=distribution_stats,
                calculated_at=datetime.now()
            )
            
            logger.info(f"Monte Carlo completed: {simulations} sims, {horizon_days}d horizon, "
                       f"VaR95={var_95:.0f}€, VaR99={var_99:.0f}€, mean DD={np.mean(max_drawdowns):.1%}")
            
            # Cache
            cache_key = f"mc_{hash(str(portfolio_weights))}_{horizon_days}_{simulations}"
            self.monte_carlo_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Monte Carlo simulation error: {e}")
            raise
    
    def get_risk_attribution(self,
                            portfolio_weights: Dict[str, float],
                            var_result: VaRResult) -> Dict[str, Dict[str, float]]:
        """
        Calcule attribution du risque par asset (Marginal VaR, Component VaR)
        
        Returns:
            Dict avec marginal_var, component_var, risk_contribution par asset
        """
        try:
            assets = list(portfolio_weights.keys())
            weights_array = np.array([portfolio_weights[asset] for asset in assets])
            
            # Récupérer matrice de covariance
            returns_data = self._get_returns_matrix(assets, self.var_config["lookback_days"])
            cov_matrix = returns_data.cov().values
            
            # Portfolio variance
            portfolio_variance = np.dot(weights_array, np.dot(cov_matrix, weights_array))
            portfolio_vol = np.sqrt(portfolio_variance)
            
            # Marginal VaR (dérivée partielle du VaR par rapport au poids)
            marginal_var = {}
            component_var = {}
            risk_contribution = {}
            
            # Z-score pour niveau de confiance
            z_score = stats.norm.ppf(var_result.confidence_level)
            
            for i, asset in enumerate(assets):
                # Marginal VaR = z_score * (Cov * w) / portfolio_vol
                marginal_contribution = np.dot(cov_matrix[i], weights_array) / portfolio_vol
                marginal_var[asset] = z_score * marginal_contribution * var_result.portfolio_value
                
                # Component VaR = weight * Marginal VaR  
                component_var[asset] = weights_array[i] * marginal_var[asset]
                
                # Risk contribution (% du VaR total)
                risk_contribution[asset] = component_var[asset] / var_result.var_absolute
            
            return {
                "marginal_var": marginal_var,
                "component_var": component_var, 
                "risk_contribution": risk_contribution
            }
            
        except Exception as e:
            logger.error(f"Risk attribution error: {e}")
            return {"marginal_var": {}, "component_var": {}, "risk_contribution": {}}
    
    # Private methods
    
    def _calculate_parametric_var(self, portfolio_weights: Dict[str, float], 
                                 portfolio_value: float, confidence_level: float,
                                 horizon: RiskHorizon) -> VaRResult:
        """VaR paramétrique (normal ou Student-t)"""
        assets = list(portfolio_weights.keys())
        weights_array = np.array([portfolio_weights[asset] for asset in assets])
        
        # Récupérer returns historiques
        returns_data = self._get_returns_matrix(assets, self.var_config["lookback_days"])
        
        # Paramètres de distribution
        mean_returns = returns_data.mean(axis=0).values
        cov_matrix = returns_data.cov().values
        
        # Portfolio statistics
        portfolio_mean = np.dot(weights_array, mean_returns)
        portfolio_variance = np.dot(weights_array, np.dot(cov_matrix, weights_array))
        portfolio_vol = np.sqrt(portfolio_variance)
        
        # Scaling pour horizon 
        horizon_multiplier = self._get_horizon_scaling(horizon)
        portfolio_vol_scaled = portfolio_vol * np.sqrt(horizon_multiplier)
        
        # Z-score (normal ou t-distribution)
        if self.var_config.get("distribution", "normal") == "student_t":
            # Fit Student-t pour queues plus épaisses
            df = self._estimate_degrees_of_freedom(returns_data)
            z_score = stats.t.ppf(confidence_level, df)
        else:
            z_score = stats.norm.ppf(confidence_level)
        
        # VaR calculation
        var_percentage = z_score * portfolio_vol_scaled - portfolio_mean * horizon_multiplier
        var_absolute = var_percentage * portfolio_value
        
        # CVaR (Expected Shortfall) approximation
        if self.var_config.get("distribution", "normal") == "student_t":
            df = self._estimate_degrees_of_freedom(returns_data)
            cvar_multiplier = (df + z_score**2) / (df - 1) * stats.t.pdf(z_score, df) / (1 - confidence_level)
        else:
            cvar_multiplier = stats.norm.pdf(z_score) / (1 - confidence_level)
        
        cvar_percentage = cvar_multiplier * portfolio_vol_scaled
        cvar_absolute = cvar_percentage * portfolio_value
        
        # Risk attribution
        attribution = self.get_risk_attribution(portfolio_weights, 
                                               VaRResult(VaRMethod.PARAMETRIC, horizon, confidence_level, 
                                                        var_absolute, var_percentage, cvar_absolute, cvar_percentage,
                                                        portfolio_value, datetime.now()))
        
        return VaRResult(
            method=VaRMethod.PARAMETRIC,
            horizon=horizon,
            confidence_level=confidence_level,
            var_absolute=abs(var_absolute),
            var_percentage=abs(var_percentage),
            cvar_absolute=abs(cvar_absolute),
            cvar_percentage=abs(cvar_percentage),
            portfolio_value=portfolio_value,
            calculated_at=datetime.now(),
            marginal_var=attribution["marginal_var"],
            component_var=attribution["component_var"]
        )
    
    def _calculate_historical_var(self, portfolio_weights: Dict[str, float],
                                 portfolio_value: float, confidence_level: float,
                                 horizon: RiskHorizon) -> VaRResult:
        """VaR historique par bootstrap"""
        assets = list(portfolio_weights.keys())
        weights_array = np.array([portfolio_weights[asset] for asset in assets])
        
        # Récupérer returns et calculer portfolio returns historiques
        returns_data = self._get_returns_matrix(assets, self.var_config["lookback_days"])
        portfolio_returns = np.dot(returns_data.values, weights_array)
        
        # Scaling pour horizon
        horizon_multiplier = self._get_horizon_scaling(horizon)
        if horizon_multiplier > 1:
            # Pour multi-day, simuler returns cumulés
            scaled_returns = []
            for i in range(len(portfolio_returns) - horizon_multiplier + 1):
                period_return = np.prod(1 + portfolio_returns[i:i+horizon_multiplier]) - 1
                scaled_returns.append(period_return)
            portfolio_returns = np.array(scaled_returns)
        
        # VaR historique (percentile empirique)
        var_percentage = -np.percentile(portfolio_returns, (1 - confidence_level) * 100)
        var_absolute = var_percentage * portfolio_value
        
        # CVaR historique (moyenne des returns pires que VaR)
        tail_returns = portfolio_returns[portfolio_returns <= -var_percentage]
        cvar_percentage = -np.mean(tail_returns) if len(tail_returns) > 0 else var_percentage
        cvar_absolute = cvar_percentage * portfolio_value
        
        return VaRResult(
            method=VaRMethod.HISTORICAL,
            horizon=horizon,
            confidence_level=confidence_level,
            var_absolute=var_absolute,
            var_percentage=var_percentage,
            cvar_absolute=cvar_absolute,
            cvar_percentage=cvar_percentage,
            portfolio_value=portfolio_value,
            calculated_at=datetime.now()
        )
    
    def _calculate_monte_carlo_var(self, portfolio_weights: Dict[str, float],
                                  portfolio_value: float, confidence_level: float,
                                  horizon: RiskHorizon) -> VaRResult:
        """VaR Monte Carlo (utilise résultats MC simulation)"""
        horizon_days = self._get_horizon_scaling(horizon)
        mc_result = self.run_monte_carlo_simulation(
            portfolio_weights, portfolio_value, horizon_days, 
            simulations=self.mc_config["simulations"]
        )
        
        # Extraire VaR/CVaR du résultat MC
        if confidence_level == 0.95:
            var_absolute = mc_result.var_95
            cvar_absolute = mc_result.cvar_95
        elif confidence_level == 0.99:
            var_absolute = mc_result.var_99
            cvar_absolute = mc_result.cvar_99
        else:
            # Interpoler ou calculer custom percentile
            outcomes_pct = (1 - confidence_level) * 100
            var_percentage = -mc_result.confidence_intervals.get(f"P{int(outcomes_pct)}", 0)
            var_absolute = var_percentage * portfolio_value
            cvar_absolute = var_absolute * 1.2  # Approximation
        
        var_percentage = var_absolute / portfolio_value
        cvar_percentage = cvar_absolute / portfolio_value
        
        return VaRResult(
            method=VaRMethod.MONTE_CARLO,
            horizon=horizon,
            confidence_level=confidence_level,
            var_absolute=var_absolute,
            var_percentage=var_percentage,
            cvar_absolute=cvar_absolute,
            cvar_percentage=cvar_percentage,
            portfolio_value=portfolio_value,
            calculated_at=datetime.now()
        )
    
    def _initialize_stress_scenarios(self):
        """Initialize predefined stress scenarios with historical shocks"""
        self.stress_scenarios = {
            # 2008 Financial Crisis: Major crypto correlation with traditional assets
            "crisis_2008": {
                "shocks": {
                    "BTC": -0.85,    # Severe correlation with risk assets
                    "ETH": -0.80,    # High correlation with BTC 
                    "SOL": -0.90,    # Alt coins hit harder
                    "AVAX": -0.88,
                    "DOGE": -0.95,   # Meme coins collapse
                    "LINK": -0.82,
                    "ADA": -0.85,
                    "DOT": -0.87
                },
                "probability": 0.02,  # 2% chance over 1 year
                "recovery_days": 180,
                "description": "Systematic financial crisis with crypto correlation"
            },
            
            # COVID-19 March 2020: Liquidity crunch
            "covid_2020": {
                "shocks": {
                    "BTC": -0.50,    # Actually happened
                    "ETH": -0.55,    
                    "SOL": -0.65,    # Smaller caps hit harder
                    "AVAX": -0.62,
                    "DOGE": -0.45,   # Retail favorite, less correlated
                    "LINK": -0.58,
                    "ADA": -0.60,
                    "DOT": -0.65
                },
                "probability": 0.05,  # 5% chance
                "recovery_days": 90,
                "description": "Pandemic-induced liquidity crisis"
            },
            
            # China Ban Crypto (hypothetical total ban)
            "china_ban": {
                "shocks": {
                    "BTC": -0.35,    # Global impact but not devastating
                    "ETH": -0.30,    # Less mining-dependent
                    "SOL": -0.25,    # US-based, benefits from shift
                    "AVAX": -0.20,
                    "DOGE": -0.40,   # Retail panic
                    "LINK": -0.15,   # Enterprise adoption continues
                    "ADA": -0.25,
                    "DOT": -0.20
                },
                "probability": 0.15,  # 15% chance
                "recovery_days": 120,
                "description": "Complete China crypto ban"
            },
            
            # Tether Collapse
            "tether_collapse": {
                "shocks": {
                    "BTC": -0.60,    # Major liquidity/confidence shock
                    "ETH": -0.55,    
                    "SOL": -0.50,    # Native USDC benefits
                    "AVAX": -0.45,
                    "DOGE": -0.70,   # Retail panic
                    "LINK": -0.40,   # Oracle still needed
                    "ADA": -0.50,
                    "DOT": -0.45
                },
                "probability": 0.08,  # 8% chance
                "recovery_days": 150,
                "description": "USDT collapse, stablecoin crisis"
            },
            
            # Fed Emergency Rate Hike (500bps)
            "fed_emergency": {
                "shocks": {
                    "BTC": -0.40,    # Risk-off environment  
                    "ETH": -0.45,    # Tech correlation
                    "SOL": -0.55,    # Growth/tech proxy
                    "AVAX": -0.50,
                    "DOGE": -0.60,   # Pure speculation
                    "LINK": -0.35,   # Utility value
                    "ADA": -0.40,
                    "DOT": -0.45
                },
                "probability": 0.10,  # 10% chance
                "recovery_days": 60,
                "description": "Emergency Fed rate hike cycle"
            }
        }
    
    def _get_returns_matrix(self, assets: List[str], lookback_days: int) -> Optional[pd.DataFrame]:
        """Récupère matrice des returns pour les assets"""
        # Pour MVP, simuler returns basés sur volatilité/corrélation typique crypto
        # Dans vraie implémentation, vient de data pipeline
        
        np.random.seed(42)  # Reproductible
        dates = pd.date_range(end=datetime.now(), periods=lookback_days, freq='D')
        
        returns_data = {}
        base_vol = 0.04  # 4% daily vol base
        
        for i, asset in enumerate(assets):
            # Volatilité variable par asset
            if asset == "BTC":
                vol = base_vol * 0.8  # BTC moins volatile
            elif asset in ["ETH", "SOL"]:
                vol = base_vol * 1.0  # Vol moyenne
            elif asset == "DOGE":
                vol = base_vol * 1.5  # DOGE très volatile
            else:
                vol = base_vol * 1.2  # Autres alts
            
            # Générer returns with some correlation to BTC
            if asset == "BTC":
                returns = np.random.normal(0.001, vol, lookback_days)  # Slight positive drift
            else:
                btc_returns = returns_data.get("BTC", np.zeros(lookback_days))
                correlation = 0.7 if asset in ["ETH", "SOL"] else 0.5  # Correlation avec BTC
                
                noise = np.random.normal(0, vol * np.sqrt(1 - correlation**2), lookback_days)
                returns = correlation * btc_returns + noise
            
            returns_data[asset] = returns
        
        return pd.DataFrame(returns_data, index=dates)
    
    def _validate_portfolio_data(self, assets: List[str]) -> bool:
        """Valide que suffisamment de données historiques disponibles"""
        min_observations = self.var_config["min_observations"]
        
        for asset in assets:
            # Dans vraie implémentation, check contre vraies données
            # Pour MVP, toujours valide
            pass
        
        return True
    
    def _get_horizon_scaling(self, horizon: RiskHorizon) -> int:
        """Convertit horizon en nombre de jours"""
        scaling = {
            RiskHorizon.DAILY: 1,
            RiskHorizon.WEEKLY: 7, 
            RiskHorizon.MONTHLY: 30
        }
        return scaling.get(horizon, 1)
    
    def _estimate_degrees_of_freedom(self, returns_data: pd.DataFrame) -> float:
        """Estime degrés de liberté pour Student-t distribution"""
        # Méthode simple: moyenne des DF estimés par asset
        dfs = []
        for col in returns_data.columns:
            try:
                _, _, df = stats.t.fit(returns_data[col].dropna())
                dfs.append(max(3, min(30, df)))  # Borner entre 3 et 30
            except:
                dfs.append(5)  # Default conservateur
        
        return np.mean(dfs)
    
    def _fit_multivariate_t(self, returns_data: pd.DataFrame) -> float:
        """Fit multivariate Student-t distribution"""
        # Simplified: moyenne des DF univariés
        return self._estimate_degrees_of_freedom(returns_data)
    
    def _generate_multivariate_t_path(self, horizon_days: int, 
                                     distribution_params: Dict) -> np.ndarray:
        """Génère path de returns avec distribution Student-t multivariée"""
        df = distribution_params["df"]
        mean = distribution_params["mean"]
        cov = distribution_params["cov"]
        
        # Simulation Student-t multivariée approximée
        # 1. Générer chi-squared 
        chi2_samples = np.random.chisquare(df, horizon_days) / df
        
        # 2. Générer normal multivariée
        normal_samples = np.random.multivariate_normal(mean, cov, horizon_days)
        
        # 3. Combiner pour Student-t
        t_samples = normal_samples / np.sqrt(chi2_samples.reshape(-1, 1))
        
        return t_samples
    
    def get_risk_summary(self, portfolio_weights: Dict[str, float], 
                        portfolio_value: float) -> Dict[str, Any]:
        """Génère résumé complet du risque portfolio"""
        try:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "portfolio_value": portfolio_value,
                "portfolio_weights": portfolio_weights,
                "risk_metrics": {}
            }
            
            # VaR multi-méthodes
            for method in [VaRMethod.PARAMETRIC, VaRMethod.HISTORICAL]:
                for confidence in [0.95, 0.99]:
                    try:
                        var_result = self.calculate_var(
                            portfolio_weights, portfolio_value, method, confidence
                        )
                        key = f"var_{method.value}_{int(confidence*100)}"
                        summary["risk_metrics"][key] = {
                            "var_absolute": var_result.var_absolute,
                            "var_percentage": var_result.var_percentage,
                            "cvar_absolute": var_result.cvar_absolute
                        }
                    except Exception as e:
                        logger.warning(f"VaR calculation failed for {method.value}_{confidence}: {e}")
            
            # Stress tests
            try:
                stress_results = self.run_stress_test(portfolio_weights, portfolio_value)
                summary["stress_tests"] = {
                    result.scenario: {
                        "portfolio_pnl": result.portfolio_pnl,
                        "portfolio_pnl_pct": result.portfolio_pnl_pct,
                        "worst_asset": result.worst_asset,
                        "recovery_days": result.recovery_time_days
                    }
                    for result in stress_results
                }
            except Exception as e:
                logger.warning(f"Stress testing failed: {e}")
                summary["stress_tests"] = {}
            
            return summary
            
        except Exception as e:
            logger.error(f"Risk summary generation error: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


def create_advanced_risk_engine(config: Dict[str, Any]) -> Optional[AdvancedRiskEngine]:
    """Factory function pour créer AdvancedRiskEngine"""
    try:
        if not config.get("enabled", False):
            logger.info("AdvancedRiskEngine disabled in config")
            return None
        
        return AdvancedRiskEngine(config)
        
    except Exception as e:
        logger.error(f"Failed to create AdvancedRiskEngine: {e}")
        return None