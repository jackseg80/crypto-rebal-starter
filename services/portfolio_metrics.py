"""
Service centralisé pour tous les calculs de métriques de portfolio
Utilisé par tous les modules pour garantir la cohérence des calculs

Modules qui utilisent ce service:
- Risk Dashboard
- Advanced Analytics  
- Portfolio Optimization
- Performance Tracking
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta
import logging
import math
import statistics
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PortfolioMetrics:
    """Structure standardisée pour toutes les métriques de portfolio"""
    # Rendements
    total_return_pct: float
    annualized_return_pct: float
    
    # Risque
    volatility_annualized: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # Drawdown
    max_drawdown: float
    current_drawdown: float
    max_drawdown_duration_days: int
    
    # Distribution des rendements
    skewness: float
    kurtosis: float
    
    # Value at Risk
    var_95_1d: float
    var_99_1d: float
    cvar_95_1d: float
    cvar_99_1d: float
    
    # Métriques supplémentaires
    ulcer_index: float
    positive_months_pct: float
    win_loss_ratio: float
    
    # Métadonnées
    data_points: int
    calculation_date: datetime
    confidence_level: float

@dataclass
class CorrelationMetrics:
    """Métriques de corrélation standardisées"""
    diversification_ratio: float
    effective_assets: float
    top_correlations: List[Dict[str, Any]]
    correlation_matrix: Optional[pd.DataFrame] = None

class PortfolioMetricsService:
    """Service centralisé pour tous les calculs de métriques de portfolio"""
    
    def __init__(self):
        self.risk_free_rate = 0.02  # 2% annuel
        
    def calculate_portfolio_metrics(
        self, 
        price_data: pd.DataFrame,
        balances: List[Dict[str, Any]],
        confidence_level: float = 0.95
    ) -> PortfolioMetrics:
        """
        Calcule TOUTES les métriques de portfolio de manière centralisée
        
        Args:
            price_data: DataFrame avec les prix historiques (index: dates, colonnes: symbols)
            balances: Liste des holdings actuels avec symbol, balance, value_usd
            confidence_level: Niveau de confiance pour VaR (0.95 par défaut)
            
        Returns:
            PortfolioMetrics: Toutes les métriques calculées
        """
        logger.info(f"Calculating portfolio metrics for {len(price_data)} data points")
        
        # Calculer les rendements pondérés du portfolio
        portfolio_returns = self._calculate_weighted_portfolio_returns(price_data, balances)
        
        if len(portfolio_returns) < 30:
            raise ValueError("Insufficient data points for reliable metrics calculation")
        
        # Calculs de base
        total_return = self._calculate_total_return(portfolio_returns)
        annualized_return = self._calculate_annualized_return(portfolio_returns)
        volatility = self._calculate_volatility(portfolio_returns)
        
        # Ratios de risque
        sharpe_ratio = self._calculate_sharpe_ratio(annualized_return, volatility)
        sortino_ratio = self._calculate_sortino_ratio(portfolio_returns, annualized_return)
        
        # Drawdown analysis
        drawdown_metrics = self._calculate_drawdown_metrics(portfolio_returns)
        calmar_ratio = annualized_return / max(abs(drawdown_metrics['max_drawdown']), 0.01)
        
        # Distribution metrics
        skewness = self._calculate_skewness(portfolio_returns)
        kurtosis = self._calculate_kurtosis(portfolio_returns)
        
        # VaR calculations
        var_metrics = self._calculate_var_metrics(portfolio_returns, confidence_level)
        
        # Additional metrics
        ulcer_index = self._calculate_ulcer_index(portfolio_returns)
        positive_months = self._calculate_positive_months_pct(portfolio_returns)
        win_loss_ratio = self._calculate_win_loss_ratio(portfolio_returns)
        
        return PortfolioMetrics(
            total_return_pct=total_return * 100,
            annualized_return_pct=annualized_return * 100,
            volatility_annualized=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=drawdown_metrics['max_drawdown'],
            current_drawdown=drawdown_metrics['current_drawdown'],
            max_drawdown_duration_days=drawdown_metrics['max_duration_days'],
            skewness=skewness,
            kurtosis=kurtosis,
            var_95_1d=var_metrics['var_95'],
            var_99_1d=var_metrics['var_99'],
            cvar_95_1d=var_metrics['cvar_95'],
            cvar_99_1d=var_metrics['cvar_99'],
            ulcer_index=ulcer_index,
            positive_months_pct=positive_months,
            win_loss_ratio=win_loss_ratio,
            data_points=len(portfolio_returns),
            calculation_date=datetime.now(),
            confidence_level=confidence_level
        )
    
    def calculate_correlation_metrics(
        self, 
        price_data: pd.DataFrame,
        min_correlation_threshold: float = 0.7
    ) -> CorrelationMetrics:
        """Calcule les métriques de corrélation de manière centralisée"""
        
        # Calculer la matrice de corrélation
        returns = price_data.pct_change().dropna()
        correlation_matrix = returns.corr()
        
        # Diversification ratio
        portfolio_weights = np.ones(len(returns.columns)) / len(returns.columns)  # Equal weight pour simplification
        diversification_ratio = self._calculate_diversification_ratio(returns, portfolio_weights)
        
        # Effective number of assets
        effective_assets = self._calculate_effective_assets(correlation_matrix, portfolio_weights)
        
        # Top correlations
        top_correlations = self._get_top_correlations(correlation_matrix, min_correlation_threshold)
        
        return CorrelationMetrics(
            diversification_ratio=diversification_ratio,
            effective_assets=effective_assets,
            top_correlations=top_correlations,
            correlation_matrix=correlation_matrix
        )
    
    def _calculate_weighted_portfolio_returns(
        self, 
        price_data: pd.DataFrame, 
        balances: List[Dict[str, Any]]
    ) -> pd.Series:
        """Calcule les rendements pondérés du portfolio"""
        
        # Créer un dictionnaire des poids par symbol
        total_value = sum(float(b.get('value_usd', 0)) for b in balances)
        weights = {}
        
        for balance in balances:
            symbol = balance.get('symbol', '').upper()
            value_usd = float(balance.get('value_usd', 0))
            if total_value > 0 and symbol in price_data.columns:
                weights[symbol] = value_usd / total_value
        
        if not weights:
            raise ValueError("No matching symbols found between balances and price data")
        
        logger.info(f"Portfolio weights: {len(weights)} assets, total weight: {sum(weights.values()):.3f}")
        
        # Calculer les rendements pour chaque asset
        returns_data = price_data.pct_change().dropna()
        
        # Calculer les rendements pondérés du portfolio
        portfolio_returns = pd.Series(0.0, index=returns_data.index)
        
        for symbol, weight in weights.items():
            if symbol in returns_data.columns:
                portfolio_returns += returns_data[symbol] * weight
        
        return portfolio_returns.dropna()
    
    def _calculate_total_return(self, returns: pd.Series) -> float:
        """Calcule le rendement total"""
        return (1 + returns).prod() - 1
    
    def _calculate_annualized_return(self, returns: pd.Series) -> float:
        """Calcule le rendement annualisé"""
        days = len(returns)
        total_return = self._calculate_total_return(returns)
        return (1 + total_return) ** (252 / days) - 1
    
    def _calculate_volatility(self, returns: pd.Series) -> float:
        """Calcule la volatilité annualisée"""
        return returns.std() * np.sqrt(252)
    
    def _calculate_sharpe_ratio(self, annualized_return: float, volatility: float) -> float:
        """Calcule le ratio de Sharpe"""
        if volatility == 0:
            return 0
        return (annualized_return - self.risk_free_rate) / volatility
    
    def _calculate_sortino_ratio(self, returns: pd.Series, annualized_return: float) -> float:
        """Calcule le ratio de Sortino"""
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_deviation = downside_returns.std() * np.sqrt(252)
        if downside_deviation == 0:
            return float('inf')
        
        return (annualized_return - self.risk_free_rate) / downside_deviation
    
    def _calculate_drawdown_metrics(self, returns: pd.Series) -> Dict[str, float]:
        """Calcule toutes les métriques de drawdown"""
        # Calculer la courbe de valeur du portfolio
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdowns = (cumulative_returns - running_max) / running_max
        
        max_drawdown = drawdowns.min()
        current_drawdown = drawdowns.iloc[-1]
        
        # Calculer la durée maximale de drawdown
        in_drawdown = drawdowns < -0.005  # Seuil de 0.5%
        drawdown_duration = 0
        max_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                drawdown_duration += 1
                max_duration = max(max_duration, drawdown_duration)
            else:
                drawdown_duration = 0
        
        return {
            'max_drawdown': max_drawdown,
            'current_drawdown': current_drawdown,
            'max_duration_days': max_duration
        }
    
    def _calculate_skewness(self, returns: pd.Series) -> float:
        """Calcule l'asymétrie (skewness)"""
        return returns.skew()
    
    def _calculate_kurtosis(self, returns: pd.Series) -> float:
        """Calcule l'aplatissement (kurtosis)"""
        return returns.kurtosis()
    
    def _calculate_var_metrics(self, returns: pd.Series, confidence_level: float) -> Dict[str, float]:
        """Calcule Value at Risk et Conditional VaR"""
        var_95 = returns.quantile(1 - 0.95)
        var_99 = returns.quantile(1 - 0.99)
        
        # Conditional VaR (Expected Shortfall)
        cvar_95 = returns[returns <= var_95].mean()
        cvar_99 = returns[returns <= var_99].mean()
        
        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99
        }
    
    def _calculate_ulcer_index(self, returns: pd.Series) -> float:
        """Calcule l'index Ulcer (mesure alternative de drawdown)"""
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdowns = (cumulative_returns - running_max) / running_max
        
        # Ulcer Index = sqrt(moyenne des drawdowns au carré)
        ulcer_index = np.sqrt((drawdowns ** 2).mean())
        return ulcer_index
    
    def _calculate_positive_months_pct(self, returns: pd.Series) -> float:
        """Calcule le pourcentage de périodes positives"""
        positive_periods = (returns > 0).sum()
        return (positive_periods / len(returns)) * 100
    
    def _calculate_win_loss_ratio(self, returns: pd.Series) -> float:
        """Calcule le ratio gain/perte"""
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) == 0:
            return float('inf')
        
        avg_gain = positive_returns.mean() if len(positive_returns) > 0 else 0
        avg_loss = abs(negative_returns.mean())
        
        return avg_gain / avg_loss if avg_loss > 0 else 0
    
    def _calculate_diversification_ratio(self, returns: pd.DataFrame, weights: np.ndarray) -> float:
        """Calcule le ratio de diversification"""
        # Volatilité pondérée des actifs individuels
        individual_vols = returns.std() * np.sqrt(252)
        weighted_avg_vol = np.sum(weights * individual_vols)
        
        # Volatilité du portfolio
        portfolio_vol = (returns @ weights).std() * np.sqrt(252)
        
        return weighted_avg_vol / max(portfolio_vol, 0.01)
    
    def _calculate_effective_assets(self, correlation_matrix: pd.DataFrame, weights: np.ndarray) -> float:
        """Calcule le nombre effectif d'actifs"""
        # Effective N = 1 / sum(w_i^2) ajusté pour les corrélations
        # Approximation simplifiée
        return 1 / np.sum(weights ** 2)
    
    def _get_top_correlations(self, correlation_matrix: pd.DataFrame, threshold: float) -> List[Dict[str, Any]]:
        """Extrait les corrélations les plus élevées"""
        correlations = []
        
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr_value = correlation_matrix.iloc[i, j]
                if abs(corr_value) >= threshold:
                    correlations.append({
                        'asset1': correlation_matrix.columns[i],
                        'asset2': correlation_matrix.columns[j],
                        'correlation': corr_value
                    })
        
        # Trier par corrélation décroissante
        correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        return correlations[:10]  # Top 10


# Instance globale du service
portfolio_metrics_service = PortfolioMetricsService()

# Fonctions utilitaires pour compatibilité
def calculate_portfolio_metrics(price_data: pd.DataFrame, balances: List[Dict[str, Any]], **kwargs) -> PortfolioMetrics:
    """Fonction utilitaire pour calculer les métriques de portfolio"""
    return portfolio_metrics_service.calculate_portfolio_metrics(price_data, balances, **kwargs)

def calculate_correlation_metrics(price_data: pd.DataFrame, **kwargs) -> CorrelationMetrics:
    """Fonction utilitaire pour calculer les métriques de corrélation"""
    return portfolio_metrics_service.calculate_correlation_metrics(price_data, **kwargs)