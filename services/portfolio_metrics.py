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

    # ✅ Risk Assessment (docs/RISK_SEMANTICS.md)
    # overall_risk_level: str  # "very_low", "low", "medium", "high", "very_high", "critical"
    # risk_score: float        # Score 0-100 (robustesse: plus haut = moins risqué)
    overall_risk_level: str = "medium"
    risk_score: float = 50.0

    # Métadonnées
    data_points: int = 0
    calculation_date: datetime = None
    confidence_level: float = 0.95

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

        # 🆕 Calculate structural metrics for risk scoring
        memecoins_pct = 0.0
        hhi = 0.0
        gri = 5.0  # Default neutral
        diversification_ratio = 1.0  # Default neutral

        if balances:
            # Calculate memecoins %
            from services.taxonomy import Taxonomy
            taxonomy = Taxonomy.load()
            total_value = sum(float(b.get('value_usd', 0)) for b in balances)

            if total_value > 0:
                # Memecoins %
                memes_value = sum(
                    float(b.get('value_usd', 0))
                    for b in balances
                    if taxonomy.group_for_alias(str(b.get('symbol', '')).upper()) == 'Memecoins'
                )
                memecoins_pct = memes_value / total_value

                # HHI (concentration)
                weights = [float(b.get('value_usd', 0)) / total_value for b in balances]
                hhi = sum(w * w for w in weights)

                # GRI (Group Risk Index)
                GROUP_RISK_LEVELS = {
                    'Stablecoins': 0,
                    'BTC': 2,
                    'ETH': 3,
                    'L2/Scaling': 5,
                    'DeFi': 5,
                    'AI/Data': 5,
                    'SOL': 6,
                    'L1/L0 majors': 6,
                    'Gaming/NFT': 6,
                    'Others': 7,
                    'Memecoins': 9,
                }
                exposure_by_group = {}
                for b in balances:
                    symbol = str(b.get('symbol', '')).upper()
                    group = taxonomy.group_for_alias(symbol)
                    weight = float(b.get('value_usd', 0)) / total_value
                    exposure_by_group[group] = exposure_by_group.get(group, 0.0) + weight

                gri_raw = sum(
                    exposure_by_group.get(g, 0.0) * GROUP_RISK_LEVELS.get(g, 6)
                    for g in exposure_by_group
                )
                gri = max(0.0, min(10.0, gri_raw))

        # Calculate correlation metrics for diversification ratio
        correlation_metrics = self.calculate_correlation_metrics(
            price_data=price_data,
            min_correlation_threshold=0.7
        )
        diversification_ratio = correlation_metrics.diversification_ratio

        # ✅ Risk Assessment (docs/RISK_SEMANTICS.md)
        # Risk Score = indicateur POSITIF de robustesse [0-100]
        # Plus haut = plus robuste (risque perçu plus faible)
        # IMPORTANT: Utilise la fonction centralisée pour éviter duplication
        from services.risk_scoring import assess_risk_level
        risk_assessment = assess_risk_level(
            var_metrics=var_metrics,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=drawdown_metrics['max_drawdown'],
            volatility=volatility,
            # 🆕 Structural penalties (V2+ scoring)
            memecoins_pct=memecoins_pct,
            hhi=hhi,
            gri=gri,
            diversification_ratio=diversification_ratio
        )

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
            overall_risk_level=risk_assessment["level"],
            risk_score=risk_assessment["score"],
            data_points=len(portfolio_returns),
            calculation_date=datetime.now(),
            confidence_level=confidence_level
        )

    def calculate_dual_window_metrics(
        self,
        price_data: pd.DataFrame,
        balances: List[Dict[str, Any]],
        min_history_days: int = 180,
        min_coverage_pct: float = 0.80,
        min_asset_count: int = 5,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Calcule les métriques sur deux fenêtres temporelles :
        1. Long-Term Window : Cohorte stable avec historique ≥ min_history_days
        2. Full Intersection : Tous les assets (fenêtre commune courte)

        Args:
            price_data: DataFrame avec les prix historiques
            balances: Liste des holdings actuels
            min_history_days: Jours minimum pour cohorte long-term (défaut: 180)
            min_coverage_pct: % minimum de valeur couverte (défaut: 0.80 = 80%)
            min_asset_count: Nombre minimum d'assets dans cohorte (défaut: 5)
            confidence_level: Niveau de confiance pour VaR

        Returns:
            Dict avec 'long_term', 'full_intersection', 'exclusions_metadata'
        """
        logger.info(f"🔍 Dual Window: min_history={min_history_days}d, min_coverage={min_coverage_pct*100}%, min_assets={min_asset_count}")

        # Calculer la valeur totale du portfolio
        total_portfolio_value = sum(float(b.get('value_usd', 0)) for b in balances)

        # Cascade fallback thresholds
        cascade_configs = [
            (365, 0.80),  # 365 jours, 80% couverture
            (180, 0.70),  # 180 jours, 70% couverture
            (120, 0.60),  # 120 jours, 60% couverture
            (90, 0.50),   # 90 jours, 50% couverture
        ]

        long_term_result = None
        exclusions_metadata = {
            'excluded_assets': [],
            'excluded_value_usd': 0.0,
            'excluded_pct': 0.0,
            'included_assets': [],
            'included_value_usd': 0.0,
            'included_pct': 0.0,
            'target_days': min_history_days,
            'achieved_days': 0,
            'reason': 'pending'
        }

        # Essayer cascade fallback
        for target_days, min_cov in cascade_configs:
            if target_days > len(price_data):
                logger.warning(f"⏭️  Skip cascade {target_days}d (only {len(price_data)} points available)")
                continue

            # Construire la cohorte pour cette fenêtre
            cohort_balances = []
            cohort_value = 0.0
            excluded_balances = []
            excluded_value = 0.0

            for balance in balances:
                symbol = (balance.get('symbol') or '').upper()
                value_usd = float(balance.get('value_usd', 0))

                if symbol not in price_data.columns:
                    excluded_balances.append({**balance, 'reason': 'not_in_price_data'})
                    excluded_value += value_usd
                    continue

                # Vérifier historique disponible
                asset_history = price_data[symbol].dropna()
                if len(asset_history) < target_days:
                    excluded_balances.append({**balance, 'reason': f'history_{len(asset_history)}d_<_{target_days}d'})
                    excluded_value += value_usd
                else:
                    cohort_balances.append(balance)
                    cohort_value += value_usd

            # Vérifier si la cohorte satisfait les critères
            coverage_pct = cohort_value / total_portfolio_value if total_portfolio_value > 0 else 0

            if coverage_pct >= min_cov and len(cohort_balances) >= min_asset_count:
                logger.info(f"✅ Cohort found: {target_days}d, {len(cohort_balances)} assets, {coverage_pct*100:.1f}% value")

                # Calculer les métriques sur cette cohorte
                # ⚠️ IMPORTANT: Filtrer les colonnes de la cohorte AVANT de nettoyer les NaN
                cohort_symbols = [b.get('symbol', '').upper() for b in cohort_balances]
                cohort_price_data = price_data[cohort_symbols].dropna().tail(target_days)
                try:
                    long_term_metrics = self.calculate_portfolio_metrics(
                        cohort_price_data,
                        cohort_balances,
                        confidence_level
                    )

                    long_term_result = {
                        'metrics': long_term_metrics,
                        'window_days': target_days,
                        'asset_count': len(cohort_balances),
                        'coverage_pct': coverage_pct
                    }

                    exclusions_metadata.update({
                        'excluded_assets': excluded_balances,
                        'excluded_value_usd': excluded_value,
                        'excluded_pct': excluded_value / total_portfolio_value if total_portfolio_value > 0 else 0,
                        'included_assets': cohort_balances,
                        'included_value_usd': cohort_value,
                        'included_pct': coverage_pct,
                        'target_days': target_days,
                        'achieved_days': target_days,
                        'reason': 'success'
                    })

                    break  # Sortir de la cascade

                except Exception as e:
                    logger.warning(f"⚠️  Cohort {target_days}d failed calculation: {e}")
                    continue
            else:
                logger.warning(f"❌ Cohort {target_days}d insufficient: {len(cohort_balances)} assets, {coverage_pct*100:.1f}% (need {min_cov*100}%)")

        # Fallback si aucune cohorte trouvée
        if long_term_result is None:
            logger.warning("⚠️  No valid long-term cohort found, using full intersection as fallback")
            exclusions_metadata['reason'] = 'no_valid_cohort_found'

        # Calculer la fenêtre Full Intersection (tous les assets)
        try:
            # ⚠️ IMPORTANT: dropna() pour éliminer les lignes avec NaN (intersection temporelle)
            full_intersection_price_data = price_data.dropna()
            full_intersection_metrics = self.calculate_portfolio_metrics(
                full_intersection_price_data,
                balances,
                confidence_level
            )

            full_intersection_result = {
                'metrics': full_intersection_metrics,
                'window_days': len(full_intersection_price_data),  # ✅ Utiliser le DataFrame nettoyé
                'asset_count': len(balances),
                'coverage_pct': 1.0
            }
        except Exception as e:
            logger.error(f"❌ Full intersection calculation failed: {e}")
            raise

        return {
            'long_term': long_term_result,
            'full_intersection': full_intersection_result,
            'exclusions_metadata': exclusions_metadata,
            'risk_score_source': 'long_term' if long_term_result else 'full_intersection'
        }

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
        """Calcule les rendements ponderes du portfolio"""
        
        weights: Dict[str, float] = {}
        for balance in balances:
            symbol = (balance.get('symbol') or '').upper()
            value_usd = float(balance.get('value_usd', 0))
            if symbol in price_data.columns and value_usd > 0:
                weights[symbol] = weights.get(symbol, 0.0) + value_usd
        
        total_value = sum(weights.values())
        if total_value <= 0:
            raise ValueError("No matching symbols found between balances and price data")
        
        weights = {symbol: value / total_value for symbol, value in weights.items()}
        logger.info(
            "Portfolio weights: %s assets, total weight after normalization: %.3f",
            len(weights),
            sum(weights.values()),
        )
        
        returns_data = price_data.sort_index().pct_change(fill_method=None)
        weight_series = pd.Series(weights, dtype=float)
        weighted_points = []
        
        for timestamp, row in returns_data.iterrows():
            valid_returns = row.dropna()
            if valid_returns.empty:
                continue
            available_weights = weight_series.reindex(valid_returns.index).dropna()
            weight_sum = available_weights.sum()
            if available_weights.empty or weight_sum <= 0:
                continue
            normalized_weights = available_weights / weight_sum
            weighted_return = float((valid_returns.reindex(normalized_weights.index) * normalized_weights).sum())
            weighted_points.append((timestamp, weighted_return))
        
        if not weighted_points:
            logger.warning("Portfolio returns calculation produced no valid points; price coverage too sparse")
            return pd.Series(dtype=float)
        
        return pd.Series(
            data=[value for _, value in weighted_points],
            index=[ts for ts, _ in weighted_points],
        )
    
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

    # ⚠️ REMOVED: _assess_overall_risk_level() is now centralized in services/risk_scoring.py
    # Import from there to avoid duplication and ensure consistency across the codebase


# Instance globale du service
portfolio_metrics_service = PortfolioMetricsService()

# Fonctions utilitaires pour compatibilité
def calculate_portfolio_metrics(price_data: pd.DataFrame, balances: List[Dict[str, Any]], **kwargs) -> PortfolioMetrics:
    """Fonction utilitaire pour calculer les métriques de portfolio"""
    return portfolio_metrics_service.calculate_portfolio_metrics(price_data, balances, **kwargs)

def calculate_correlation_metrics(price_data: pd.DataFrame, **kwargs) -> CorrelationMetrics:
    """Fonction utilitaire pour calculer les métriques de corrélation"""
    return portfolio_metrics_service.calculate_correlation_metrics(price_data, **kwargs)