"""
API Endpoints pour les Analytics Avancés
Métriques de performance sophistiquées et analyse de drawdown
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
import math
import statistics
from api.utils.cache import cache_get, cache_set, cache_clear_expired

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/advanced", tags=["advanced-analytics"])

# Cache pour les analytics avancés
_advanced_cache = {}

class DrawdownPeriod(BaseModel):
    """Période de drawdown détaillée"""
    start_date: datetime
    end_date: Optional[datetime] = None
    peak_value: float
    trough_value: float
    drawdown_pct: float
    duration_days: int
    recovery_days: Optional[int] = None
    is_recovered: bool = False

class AdvancedMetrics(BaseModel):
    """Métriques de performance avancées"""
    # Métriques de base
    total_return_pct: float
    annualized_return_pct: float
    volatility_pct: float
    sharpe_ratio: float
    
    # Métriques de drawdown
    max_drawdown_pct: float
    avg_drawdown_pct: float
    max_drawdown_duration_days: int
    avg_drawdown_duration_days: float
    drawdown_periods: List[DrawdownPeriod]
    
    # Ratios avancés
    calmar_ratio: float  # Annualized return / Max Drawdown
    sortino_ratio: float  # Return vs downside deviation
    omega_ratio: float    # Probability weighted ratio
    
    # Métriques de distribution
    skewness: float
    kurtosis: float
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    
    # Métriques de timing
    best_month_pct: float
    worst_month_pct: float
    positive_months_pct: float
    win_loss_ratio: float

class TimeSeriesData(BaseModel):
    """Données de série temporelle pour graphiques"""
    dates: List[str]
    portfolio_values: List[float]
    returns: List[float]
    cumulative_returns: List[float]
    drawdowns: List[float]
    rolling_sharpe: List[float]
    rolling_volatility: List[float]

@router.get("/metrics", response_model=AdvancedMetrics)
async def get_advanced_metrics(
    days: int = Query(365, description="Nombre de jours d'historique"),
    benchmark: Optional[str] = Query(None, description="Symbol de benchmark (BTC, ETH, etc.)")
):
    """
    Calculer les métriques de performance avancées
    """
    # Vérifier le cache (TTL de 15 minutes pour les métriques complexes)
    cache_key = f"advanced_metrics_{days}_{benchmark or 'none'}"
    cached_result = cache_get(_advanced_cache, cache_key, 900)
    if cached_result:
        logger.info(f"Returning cached advanced metrics for {days} days")
        return cached_result
    
    try:
        # Générer des données simulées pour la démo
        mock_data = _generate_mock_performance_data(days)
        
        # Calculer les métriques avancées
        metrics = _calculate_advanced_metrics(mock_data)
        
        # Mettre en cache le résultat
        cache_set(_advanced_cache, cache_key, metrics)
        cache_clear_expired(_advanced_cache, 900)
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating advanced metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error calculating metrics")

@router.get("/timeseries", response_model=TimeSeriesData)
async def get_timeseries_data(
    days: int = Query(365, description="Nombre de jours d'historique"),
    granularity: str = Query("daily", description="Granularité: daily, weekly, monthly")
):
    """
    Récupérer les données de série temporelle pour les graphiques
    """
    # Vérifier le cache (TTL de 10 minutes pour les données de série)
    cache_key = f"timeseries_{days}_{granularity}"
    cached_result = cache_get(_advanced_cache, cache_key, 600)
    if cached_result:
        logger.info(f"Returning cached timeseries data for {days} days")
        return cached_result
    
    try:
        mock_data = _generate_mock_performance_data(days)
        
        timeseries = TimeSeriesData(
            dates=[d.strftime("%Y-%m-%d") for d, _ in mock_data["price_history"]],
            portfolio_values=[v for _, v in mock_data["price_history"]],
            returns=mock_data["daily_returns"],
            cumulative_returns=mock_data["cumulative_returns"],
            drawdowns=mock_data["drawdowns"],
            rolling_sharpe=mock_data["rolling_sharpe"],
            rolling_volatility=mock_data["rolling_volatility"]
        )
        
        # Mettre en cache le résultat
        cache_set(_advanced_cache, cache_key, timeseries)
        cache_clear_expired(_advanced_cache, 600)
        
        return timeseries
        
    except Exception as e:
        logger.error(f"Error getting timeseries data: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting timeseries data")

@router.get("/drawdown-analysis")
async def analyze_drawdowns(
    days: int = Query(365, description="Nombre de jours d'historique"),
    min_duration: int = Query(5, description="Durée minimum en jours")
):
    """
    Analyser les périodes de drawdown en détail
    """
    try:
        mock_data = _generate_mock_performance_data(days)
        drawdown_periods = _analyze_drawdown_periods(mock_data, min_duration)
        
        # Statistiques des drawdowns
        if drawdown_periods:
            avg_drawdown = sum(d.drawdown_pct for d in drawdown_periods) / len(drawdown_periods)
            avg_duration = sum(d.duration_days for d in drawdown_periods) / len(drawdown_periods)
            max_duration = max(d.duration_days for d in drawdown_periods)
            recovery_rate = sum(1 for d in drawdown_periods if d.is_recovered) / len(drawdown_periods)
        else:
            avg_drawdown = avg_duration = max_duration = recovery_rate = 0
        
        return {
            "summary": {
                "total_drawdown_periods": len(drawdown_periods),
                "avg_drawdown_pct": avg_drawdown,
                "avg_duration_days": avg_duration,
                "max_duration_days": max_duration,
                "recovery_rate": recovery_rate
            },
            "periods": drawdown_periods
        }
        
    except Exception as e:
        logger.error(f"Error analyzing drawdowns: {str(e)}")
        raise HTTPException(status_code=500, detail="Error analyzing drawdowns")

@router.get("/strategy-comparison")
async def compare_strategies(
    strategies: List[str] = Query(["rebalancing", "buy_hold", "momentum"], description="Stratégies à comparer"),
    days: int = Query(365, description="Période d'analyse")
):
    """
    Comparer les performances de différentes stratégies
    """
    try:
        comparison = {}
        
        for strategy in strategies:
            mock_data = _generate_mock_performance_data(days, strategy_bias=strategy)
            metrics = _calculate_advanced_metrics(mock_data)
            
            comparison[strategy] = {
                "total_return": metrics.total_return_pct,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown_pct,
                "volatility": metrics.volatility_pct,
                "calmar_ratio": metrics.calmar_ratio,
                "positive_months": metrics.positive_months_pct
            }
        
        # Calculer les rankings
        rankings = {}
        for metric in ["total_return", "sharpe_ratio", "calmar_ratio", "positive_months"]:
            rankings[metric] = sorted(
                strategies, 
                key=lambda s: comparison[s][metric], 
                reverse=True
            )
        
        # Pour max_drawdown et volatility, plus bas = mieux
        for metric in ["max_drawdown", "volatility"]:
            rankings[metric] = sorted(
                strategies,
                key=lambda s: abs(comparison[s][metric]),
                reverse=False
            )
        
        return {
            "comparison": comparison,
            "rankings": rankings,
            "best_overall": _calculate_overall_score(comparison, strategies)
        }
        
    except Exception as e:
        logger.error(f"Error comparing strategies: {str(e)}")
        raise HTTPException(status_code=500, detail="Error comparing strategies")

@router.get("/risk-metrics")
async def get_risk_metrics(
    days: int = Query(365, description="Période d'analyse"),
    confidence_level: float = Query(0.95, description="Niveau de confiance pour VaR")
):
    """
    Calculer les métriques de risque avancées
    """
    try:
        mock_data = _generate_mock_performance_data(days)
        returns = mock_data["daily_returns"]
        
        # VaR et CVaR
        var_95 = _calculate_var(returns, confidence_level)
        cvar_95 = _calculate_cvar(returns, confidence_level)
        
        # Mesures de queue de distribution
        skewness = _calculate_skewness(returns)
        kurtosis = _calculate_kurtosis(returns)
        
        # Drawdown metrics
        max_dd = min(mock_data["drawdowns"])
        avg_dd = sum(d for d in mock_data["drawdowns"] if d < 0) / max(1, sum(1 for d in mock_data["drawdowns"] if d < 0))
        
        return {
            "value_at_risk": {
                f"var_{int(confidence_level*100)}": var_95,
                f"cvar_{int(confidence_level*100)}": cvar_95
            },
            "distribution_metrics": {
                "skewness": skewness,
                "kurtosis": kurtosis,
                "is_normal_distribution": abs(skewness) < 0.5 and abs(kurtosis - 3) < 1
            },
            "drawdown_metrics": {
                "max_drawdown_pct": max_dd,
                "avg_drawdown_pct": avg_dd,
                "time_in_drawdown_pct": sum(1 for d in mock_data["drawdowns"] if d < -1) / len(mock_data["drawdowns"]) * 100
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error calculating risk metrics")

def _generate_mock_performance_data(days: int, strategy_bias: str = "rebalancing") -> Dict[str, Any]:
    """Générer des données de performance simulées"""
    import random
    from datetime import datetime, timedelta
    
    # Paramètres selon la stratégie
    params = {
        "rebalancing": {"mean_return": 0.0008, "volatility": 0.025, "trend": 0.0002},
        "buy_hold": {"mean_return": 0.0006, "volatility": 0.035, "trend": 0.0001},
        "momentum": {"mean_return": 0.0012, "volatility": 0.040, "trend": 0.0003}
    }
    
    param = params.get(strategy_bias, params["rebalancing"])
    
    # Générer l'historique de prix
    price_history = []
    current_price = 10000.0
    current_date = datetime.now() - timedelta(days=days)
    
    daily_returns = []
    cumulative_returns = []
    cum_return = 0
    
    for i in range(days):
        # Return quotidien avec tendance et volatilité
        daily_return = random.normalvariate(param["mean_return"] + param["trend"], param["volatility"])
        current_price *= (1 + daily_return)
        
        price_history.append((current_date, current_price))
        daily_returns.append(daily_return * 100)  # En pourcentage
        
        cum_return = ((current_price / 10000.0) - 1) * 100
        cumulative_returns.append(cum_return)
        
        current_date += timedelta(days=1)
    
    # Calculer les drawdowns
    drawdowns = []
    peak = 10000.0
    
    for _, price in price_history:
        if price > peak:
            peak = price
        drawdown = ((price - peak) / peak) * 100
        drawdowns.append(drawdown)
    
    # Sharpe ratio rolling (30 jours)
    rolling_sharpe = []
    rolling_volatility = []
    
    for i in range(len(daily_returns)):
        if i < 30:
            rolling_sharpe.append(0)
            rolling_volatility.append(0)
        else:
            window_returns = daily_returns[i-30:i]
            avg_return = sum(window_returns) / 30
            vol = statistics.stdev(window_returns) * math.sqrt(252)  # Annualisé
            sharpe = (avg_return * 252) / max(vol, 0.1)
            
            rolling_sharpe.append(sharpe)
            rolling_volatility.append(vol)
    
    return {
        "price_history": price_history,
        "daily_returns": daily_returns,
        "cumulative_returns": cumulative_returns,
        "drawdowns": drawdowns,
        "rolling_sharpe": rolling_sharpe,
        "rolling_volatility": rolling_volatility
    }

def _calculate_advanced_metrics(data: Dict[str, Any]) -> AdvancedMetrics:
    """Calculer toutes les métriques avancées"""
    returns = data["daily_returns"]
    drawdowns = data["drawdowns"]
    price_history = data["price_history"]
    
    # Métriques de base
    total_return = data["cumulative_returns"][-1]
    days = len(returns)
    annualized_return = ((1 + total_return/100) ** (365/days) - 1) * 100
    
    volatility = statistics.stdev(returns) * math.sqrt(252)
    
    # Ratios de risque
    risk_free_rate = 2.0  # 2% annuel
    sharpe_ratio = (annualized_return - risk_free_rate) / max(volatility, 0.1)
    
    # Drawdown metrics
    max_drawdown = min(drawdowns)
    avg_drawdown = sum(d for d in drawdowns if d < 0) / max(1, sum(1 for d in drawdowns if d < 0))
    
    # Ratios avancés
    calmar_ratio = annualized_return / max(abs(max_drawdown), 1)
    
    # Sortino ratio (vs downside deviation)
    downside_returns = [r for r in returns if r < 0]
    downside_deviation = statistics.stdev(downside_returns) * math.sqrt(252) if downside_returns else volatility
    sortino_ratio = (annualized_return - risk_free_rate) / max(downside_deviation, 0.1)
    
    # Métriques de distribution
    skewness = _calculate_skewness(returns)
    kurtosis = _calculate_kurtosis(returns)
    var_95 = _calculate_var(returns, 0.95)
    cvar_95 = _calculate_cvar(returns, 0.95)
    
    # Métriques temporelles (simulées)
    positive_returns = [r for r in returns if r > 0]
    negative_returns = [r for r in returns if r < 0]
    
    return AdvancedMetrics(
        total_return_pct=total_return,
        annualized_return_pct=annualized_return,
        volatility_pct=volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown_pct=max_drawdown,
        avg_drawdown_pct=avg_drawdown,
        max_drawdown_duration_days=30,  # Simulé
        avg_drawdown_duration_days=12,  # Simulé
        drawdown_periods=[],  # Calculé séparément
        calmar_ratio=calmar_ratio,
        sortino_ratio=sortino_ratio,
        omega_ratio=1.5,  # Simulé
        skewness=skewness,
        kurtosis=kurtosis,
        var_95=var_95,
        cvar_95=cvar_95,
        best_month_pct=max(returns) if returns else 0,
        worst_month_pct=min(returns) if returns else 0,
        positive_months_pct=len(positive_returns) / len(returns) * 100,
        win_loss_ratio=abs(sum(positive_returns) / max(sum(negative_returns), -1)) if negative_returns else 0
    )

def _analyze_drawdown_periods(data: Dict[str, Any], min_duration: int) -> List[DrawdownPeriod]:
    """Analyser les périodes de drawdown"""
    drawdowns = data["drawdowns"]
    price_history = data["price_history"]
    
    periods = []
    in_drawdown = False
    current_period = None
    
    for i, (date, price) in enumerate(price_history):
        dd = drawdowns[i]
        
        if dd < -1 and not in_drawdown:  # Début de drawdown
            in_drawdown = True
            current_period = {
                "start_date": date,
                "start_idx": i,
                "peak_value": price / (1 + dd/100),  # Reconstituer le pic
                "trough_value": price,
                "max_dd": dd
            }
        
        elif in_drawdown:
            if dd < current_period["max_dd"]:  # Nouveau creux
                current_period["trough_value"] = price
                current_period["max_dd"] = dd
            
            if dd >= -0.5:  # Sortie de drawdown
                duration = i - current_period["start_idx"]
                
                if duration >= min_duration:
                    periods.append(DrawdownPeriod(
                        start_date=current_period["start_date"],
                        end_date=date,
                        peak_value=current_period["peak_value"],
                        trough_value=current_period["trough_value"],
                        drawdown_pct=current_period["max_dd"],
                        duration_days=duration,
                        is_recovered=True
                    ))
                
                in_drawdown = False
                current_period = None
    
    return periods

def _calculate_var(returns: List[float], confidence_level: float) -> float:
    """Calculer Value at Risk"""
    sorted_returns = sorted(returns)
    index = int((1 - confidence_level) * len(sorted_returns))
    return sorted_returns[index] if sorted_returns else 0

def _calculate_cvar(returns: List[float], confidence_level: float) -> float:
    """Calculer Conditional Value at Risk"""
    var = _calculate_var(returns, confidence_level)
    tail_returns = [r for r in returns if r <= var]
    return sum(tail_returns) / len(tail_returns) if tail_returns else 0

def _calculate_skewness(returns: List[float]) -> float:
    """Calculer l'asymétrie (skewness)"""
    if len(returns) < 3:
        return 0
    
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 0
    
    skew_sum = sum(((r - mean_return) / std_dev) ** 3 for r in returns)
    return skew_sum / len(returns)

def _calculate_kurtosis(returns: List[float]) -> float:
    """Calculer l'aplatissement (kurtosis)"""
    if len(returns) < 4:
        return 3  # Distribution normale
    
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 3
    
    kurt_sum = sum(((r - mean_return) / std_dev) ** 4 for r in returns)
    return kurt_sum / len(returns)

def _calculate_overall_score(comparison: Dict, strategies: List[str]) -> str:
    """Calculer le score global pour le classement"""
    scores = {}
    
    for strategy in strategies:
        metrics = comparison[strategy]
        # Score pondéré (plus haut = mieux)
        score = (
            metrics["total_return"] * 0.3 +
            metrics["sharpe_ratio"] * 20 * 0.25 +
            metrics["calmar_ratio"] * 20 * 0.2 +
            (100 - abs(metrics["max_drawdown"])) * 0.15 +
            metrics["positive_months"] * 0.1
        )
        scores[strategy] = score
    
    return max(scores.items(), key=lambda x: x[1])[0]