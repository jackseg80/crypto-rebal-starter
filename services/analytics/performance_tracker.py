"""
Performance Tracker - Suivi avancé des performances

Ce module calcule et analyse les métriques de performance avancées
pour optimiser les stratégies de rebalancement.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

from statistics import mean, stdev

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Métriques de performance calculées"""
    period_start: datetime
    period_end: datetime
    
    # Returns
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    
    # Risk metrics
    volatility_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Rebalancing specific
    rebalancing_alpha_pct: float = 0.0  # Performance vs buy-and-hold
    avg_drift_before_rebal: float = 0.0
    avg_drift_after_rebal: float = 0.0
    
    # Execution efficiency
    avg_execution_slippage_bps: float = 0.0
    avg_fee_rate_pct: float = 0.0
    execution_success_rate: float = 0.0
    
    # Frequency metrics
    rebalancing_frequency_days: float = 0.0
    total_rebalance_sessions: int = 0

@dataclass
class StrategyPerformance:
    """Performance d'une stratégie spécifique"""
    strategy_name: str
    metrics: PerformanceMetrics
    
    # Paramètres de la stratégie
    avg_target_allocation: Dict[str, float] = field(default_factory=dict)
    ccs_score_range: Optional[Tuple[float, float]] = None
    
    # Comparaison
    vs_benchmark_pct: float = 0.0
    vs_manual_rebal_pct: float = 0.0
    
    # Confiance statistique
    sample_size: int = 0
    confidence_interval_95: Optional[Tuple[float, float]] = None

class PerformanceTracker:
    """Analyseur de performance avancé"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annuel par défaut
        
    def calculate_portfolio_performance(self, 
                                      value_history: List[Tuple[datetime, float]],
                                      benchmark_history: Optional[List[Tuple[datetime, float]]] = None) -> PerformanceMetrics:
        """
        Calculer les métriques de performance d'un portfolio
        
        Args:
            value_history: Liste de (timestamp, valeur_portfolio)
            benchmark_history: Historique benchmark pour comparaison
        """
        if len(value_history) < 2:
            logger.warning("Insufficient data for performance calculation")
            return PerformanceMetrics(
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc)
            )
        
        # Trier par date
        value_history.sort(key=lambda x: x[0])
        
        period_start = value_history[0][0]
        period_end = value_history[-1][0]
        
        # Calculer les returns quotidiens
        daily_returns = self._calculate_daily_returns(value_history)
        
        # Métriques de base
        total_return = ((value_history[-1][1] - value_history[0][1]) / value_history[0][1]) * 100
        
        # Annualiser le return
        days = (period_end - period_start).days
        years = max(days / 365.25, 1/365.25)  # Minimum 1 jour
        annualized_return = (((value_history[-1][1] / value_history[0][1]) ** (1/years)) - 1) * 100
        
        # Volatilité (écart-type annualisé)
        volatility = 0.0
        if len(daily_returns) > 1:
            sqrt_252 = 15.874 if not NUMPY_AVAILABLE else np.sqrt(252)  # Approximation
            volatility = stdev(daily_returns) * sqrt_252 * 100  # 252 jours de trading
        
        # Maximum Drawdown
        max_drawdown = self._calculate_max_drawdown(value_history)
        
        # Sharpe Ratio
        sharpe_ratio = 0.0
        if volatility > 0:
            excess_return = annualized_return - self.risk_free_rate * 100
            sharpe_ratio = excess_return / volatility
        
        return PerformanceMetrics(
            period_start=period_start,
            period_end=period_end,
            total_return_pct=total_return,
            annualized_return_pct=annualized_return,
            volatility_pct=volatility,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe_ratio
        )
    
    def _calculate_daily_returns(self, value_history: List[Tuple[datetime, float]]) -> List[float]:
        """Calculer les returns quotidiens"""
        returns = []
        
        for i in range(1, len(value_history)):
            prev_value = value_history[i-1][1]
            curr_value = value_history[i][1]
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        
        return returns
    
    def _calculate_max_drawdown(self, value_history: List[Tuple[datetime, float]]) -> float:
        """Calculer le maximum drawdown"""
        if len(value_history) < 2:
            return 0.0
        
        peak = value_history[0][1]
        max_dd = 0.0
        
        for _, value in value_history:
            if value > peak:
                peak = value
            
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd * 100
    
    def analyze_rebalancing_impact(self, sessions_history: List[Any]) -> Dict[str, Any]:
        """
        Analyser l'impact des rebalancement sur la performance
        
        Compare la performance avec et sans rebalancement
        """
        if not sessions_history:
            return {"error": "No rebalancing sessions to analyze"}
        
        # Grouper par stratégie
        strategy_groups = self._group_sessions_by_strategy(sessions_history)
        
        results = {}
        
        for strategy_name, sessions in strategy_groups.items():
            strategy_analysis = self._analyze_strategy_performance(strategy_name, sessions)
            results[strategy_name] = strategy_analysis
        
        # Analyse globale
        results["overall"] = self._calculate_overall_analysis(sessions_history)
        
        return results
    
    def _group_sessions_by_strategy(self, sessions: List[Any]) -> Dict[str, List[Any]]:
        """Grouper les sessions par stratégie"""
        groups = {
            "manual": [],
            "ccs_accumulation": [],
            "ccs_neutral": [],
            "ccs_euphoria": [],
            "unknown": []
        }
        
        for session in sessions:
            if not session.dynamic_targets_used:
                groups["manual"].append(session)
            elif session.ccs_score is not None:
                if session.ccs_score >= 70:
                    groups["ccs_accumulation"].append(session)
                elif session.ccs_score >= 30:
                    groups["ccs_neutral"].append(session)
                else:
                    groups["ccs_euphoria"].append(session)
            else:
                groups["unknown"].append(session)
        
        # Supprimer les groupes vides
        return {k: v for k, v in groups.items() if v}
    
    def _analyze_strategy_performance(self, strategy_name: str, sessions: List[Any]) -> StrategyPerformance:
        """Analyser la performance d'une stratégie spécifique"""
        
        if not sessions:
            return StrategyPerformance(
                strategy_name=strategy_name,
                metrics=PerformanceMetrics(
                    period_start=datetime.now(timezone.utc),
                    period_end=datetime.now(timezone.utc)
                )
            )
        
        # Calculer les métriques moyennes
        completed_sessions = [s for s in sessions if s.status.value == "completed"]
        
        avg_success_rate = 0.0
        avg_slippage = 0.0
        avg_fees = 0.0
        total_volume = 0.0
        
        if completed_sessions:
            avg_success_rate = mean([s.execution_success_rate for s in completed_sessions])
            avg_slippage = mean([s.total_slippage_bps for s in completed_sessions if s.total_slippage_bps > 0])
            
            # Calculer le taux de frais moyen
            for session in completed_sessions:
                total_volume += session.total_executed_volume
                avg_fees += session.total_fees
            
            avg_fee_rate = (avg_fees / total_volume * 100) if total_volume > 0 else 0.0
        
        # Période d'analyse
        period_start = min(s.created_at for s in sessions)
        period_end = max(s.completed_at for s in sessions if s.completed_at)
        
        # Métriques de rebalancement
        rebal_frequency = 0.0
        if len(sessions) > 1:
            total_days = (period_end - period_start).days
            rebal_frequency = total_days / len(sessions)
        
        # Range CCS si applicable
        ccs_scores = [s.ccs_score for s in sessions if s.ccs_score is not None]
        ccs_range = (min(ccs_scores), max(ccs_scores)) if ccs_scores else None
        
        # Allocation moyenne
        avg_allocation = {}
        if sessions:
            all_allocations = {}
            for session in sessions:
                for group, pct in session.target_allocations.items():
                    if group not in all_allocations:
                        all_allocations[group] = []
                    all_allocations[group].append(pct)
            
            for group, percentages in all_allocations.items():
                avg_allocation[group] = mean(percentages)
        
        # Créer les métriques
        metrics = PerformanceMetrics(
            period_start=period_start,
            period_end=period_end,
            execution_success_rate=avg_success_rate,
            avg_execution_slippage_bps=avg_slippage or 0.0,
            avg_fee_rate_pct=avg_fee_rate,
            rebalancing_frequency_days=rebal_frequency,
            total_rebalance_sessions=len(sessions)
        )
        
        return StrategyPerformance(
            strategy_name=strategy_name,
            metrics=metrics,
            avg_target_allocation=avg_allocation,
            ccs_score_range=ccs_range,
            sample_size=len(completed_sessions)
        )
    
    def _calculate_overall_analysis(self, sessions: List[Any]) -> Dict[str, Any]:
        """Calculer l'analyse globale"""
        
        completed_sessions = [s for s in sessions if s.status.value == "completed"]
        
        if not completed_sessions:
            return {"error": "No completed sessions for analysis"}
        
        # Efficacité d'exécution globale
        total_planned = sum(s.total_planned_volume for s in completed_sessions)
        total_executed = sum(s.total_executed_volume for s in completed_sessions)
        execution_efficiency = (total_executed / total_planned * 100) if total_planned > 0 else 0
        
        # Performance par période
        monthly_performance = self._calculate_periodic_performance(completed_sessions, "monthly")
        weekly_performance = self._calculate_periodic_performance(completed_sessions, "weekly")
        
        # Tendances
        success_rate_trend = self._calculate_success_rate_trend(completed_sessions)
        
        return {
            "total_sessions_analyzed": len(completed_sessions),
            "execution_efficiency_pct": execution_efficiency,
            "success_rate_trend": success_rate_trend,
            "periodic_performance": {
                "monthly": monthly_performance,
                "weekly": weekly_performance
            },
            "recommendations": self._generate_recommendations(completed_sessions)
        }
    
    def _calculate_periodic_performance(self, sessions: List[Any], period: str) -> Dict[str, float]:
        """Calculer la performance par période"""
        
        if period == "monthly":
            period_days = 30
        elif period == "weekly":
            period_days = 7
        else:
            period_days = 1
        
        # Grouper les sessions par période
        periods = {}
        
        for session in sessions:
            period_key = session.created_at.replace(day=1) if period == "monthly" else session.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if period_key not in periods:
                periods[period_key] = []
            periods[period_key].append(session)
        
        # Calculer les métriques par période
        avg_success_rates = []
        avg_volumes = []
        
        for period_sessions in periods.values():
            if period_sessions:
                avg_success_rate = mean([s.execution_success_rate for s in period_sessions])
                total_volume = sum(s.total_executed_volume for s in period_sessions)
                
                avg_success_rates.append(avg_success_rate)
                avg_volumes.append(total_volume)
        
        return {
            "avg_success_rate": mean(avg_success_rates) if avg_success_rates else 0,
            "avg_volume": mean(avg_volumes) if avg_volumes else 0,
            "period_count": len(periods)
        }
    
    def _calculate_success_rate_trend(self, sessions: List[Any]) -> str:
        """Calculer la tendance du taux de succès"""
        
        if len(sessions) < 3:
            return "insufficient_data"
        
        # Prendre les 10 dernières sessions vs les 10 précédentes
        recent_sessions = sorted(sessions, key=lambda s: s.created_at)[-10:]
        previous_sessions = sorted(sessions, key=lambda s: s.created_at)[-20:-10] if len(sessions) >= 20 else []
        
        if not previous_sessions:
            return "insufficient_data"
        
        recent_avg = mean([s.execution_success_rate for s in recent_sessions])
        previous_avg = mean([s.execution_success_rate for s in previous_sessions])
        
        if recent_avg > previous_avg + 5:
            return "improving"
        elif recent_avg < previous_avg - 5:
            return "declining"
        else:
            return "stable"
    
    def _generate_recommendations(self, sessions: List[Any]) -> List[str]:
        """Générer des recommandations d'optimisation"""
        
        recommendations = []
        
        # Analyser les taux de succès
        avg_success_rate = mean([s.execution_success_rate for s in sessions])
        
        if avg_success_rate < 80:
            recommendations.append("Consider reviewing execution parameters - success rate below 80%")
        
        # Analyser les frais
        total_fees = sum(s.total_fees for s in sessions)
        total_volume = sum(s.total_executed_volume for s in sessions)
        
        if total_volume > 0:
            fee_rate = (total_fees / total_volume) * 100
            if fee_rate > 0.5:
                recommendations.append("High fee rate detected - consider optimizing order sizes or platforms")
        
        # Analyser la fréquence de rebalancement
        if len(sessions) > 1:
            session_dates = [s.created_at for s in sessions]
            session_dates.sort()
            
            intervals = []
            for i in range(1, len(session_dates)):
                interval = (session_dates[i] - session_dates[i-1]).days
                intervals.append(interval)
            
            avg_interval = mean(intervals)
            
            if avg_interval < 7:
                recommendations.append("Very frequent rebalancing detected - consider increasing thresholds")
            elif avg_interval > 60:
                recommendations.append("Infrequent rebalancing - consider lowering drift thresholds")
        
        # Analyser les stratégies CCS
        ccs_sessions = [s for s in sessions if s.dynamic_targets_used and s.ccs_score is not None]
        manual_sessions = [s for s in sessions if not s.dynamic_targets_used]
        
        if ccs_sessions and manual_sessions:
            ccs_avg_success = mean([s.execution_success_rate for s in ccs_sessions])
            manual_avg_success = mean([s.execution_success_rate for s in manual_sessions])
            
            if ccs_avg_success > manual_avg_success + 10:
                recommendations.append("CCS-based rebalancing shows better execution - consider using more frequently")
            elif manual_avg_success > ccs_avg_success + 10:
                recommendations.append("Manual rebalancing outperforming CCS - review CCS parameters")
        
        if not recommendations:
            recommendations.append("Performance metrics look good - continue current strategy")
        
        return recommendations
    
    def generate_performance_report(self, sessions: List[Any], 
                                  portfolio_history: Optional[List[Tuple[datetime, float]]] = None) -> Dict[str, Any]:
        """Générer un rapport de performance complet"""
        
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_period": {
                "start": min(s.created_at for s in sessions).isoformat() if sessions else None,
                "end": max(s.completed_at for s in sessions if s.completed_at).isoformat() if sessions else None
            }
        }
        
        # Performance du portfolio si historique disponible
        if portfolio_history:
            portfolio_metrics = self.calculate_portfolio_performance(portfolio_history)
            report["portfolio_performance"] = {
                "total_return_pct": portfolio_metrics.total_return_pct,
                "annualized_return_pct": portfolio_metrics.annualized_return_pct,
                "volatility_pct": portfolio_metrics.volatility_pct,
                "max_drawdown_pct": portfolio_metrics.max_drawdown_pct,
                "sharpe_ratio": portfolio_metrics.sharpe_ratio
            }
        
        # Analyse des rebalancement
        if sessions:
            rebalancing_analysis = self.analyze_rebalancing_impact(sessions)
            report["rebalancing_analysis"] = rebalancing_analysis
        
        return report

# Instance globale du tracker de performance  
performance_tracker = PerformanceTracker()