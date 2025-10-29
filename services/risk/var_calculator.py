"""
VaR Calculator - Calculs Value at Risk et métriques de risque

Gère tous les calculs de VaR, CVaR, volatilité, Sharpe/Sortino/Calmar ratios,
drawdown metrics et distribution analysis.

Extrait de services/risk_management.py pour améliorer la modularité.
"""

from __future__ import annotations
import logging
import numpy as np
from datetime import datetime
from scipy import stats
from typing import Dict, List, Any

from .models import RiskMetrics, RiskLevel

logger = logging.getLogger(__name__)


class VaRCalculator:
    """Calculateur de Value at Risk et métriques de risque associées"""

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Args:
            risk_free_rate: Taux sans risque annuel (défaut: 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.var_confidence_levels = [0.95, 0.99]

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

            # 4. Fenêtres intelligentes par métrique (cycle-aware)
            def tail(seq, n):
                n_eff = min(len(seq), max(0, int(n)))
                return seq[-n_eff:] if n_eff > 0 else []

            windows = {
                "var": 30,
                "cvar": 60,
                "vol": 45,
                "sharpe": 90,
                "sortino": 120,
                "dd": 180,
                "calmar": 365,
            }

            # VaR/CVaR
            var_returns = tail(portfolio_returns, windows["var"])
            cvar_returns = tail(portfolio_returns, windows["cvar"])

            var_metrics = self.calculate_var_cvar(var_returns)
            if len(cvar_returns) >= 10:
                cvar_only = self.calculate_var_cvar(cvar_returns)
                var_metrics["cvar_95"] = cvar_only.get("cvar_95", var_metrics["cvar_95"])
                var_metrics["cvar_99"] = cvar_only.get("cvar_99", var_metrics["cvar_99"])

            # Performance ajustée au risque
            vol_metrics = self.calculate_risk_adjusted_metrics(tail(portfolio_returns, windows["vol"]))
            sharpe_metrics = self.calculate_risk_adjusted_metrics(tail(portfolio_returns, windows["sharpe"]))
            sortino_metrics = self.calculate_risk_adjusted_metrics(tail(portfolio_returns, windows["sortino"]))
            calmar_metrics = self.calculate_risk_adjusted_metrics(tail(portfolio_returns, windows["calmar"]))

            perf_metrics = {
                "volatility": vol_metrics.get("volatility", 0.0),
                "sharpe": sharpe_metrics.get("sharpe", 0.0),
                "sortino": sortino_metrics.get("sortino", 0.0),
                "calmar": calmar_metrics.get("calmar", 0.0),
            }

            # Drawdowns
            drawdown_metrics = self.calculate_drawdown_metrics(tail(portfolio_returns, windows["dd"]))

            # Distribution (utiliser fenêtre sharpe par défaut)
            distribution_metrics = self.calculate_distribution_metrics(tail(portfolio_returns, windows["sharpe"]))

            # 8. Évaluation du niveau de risque global
            risk_assessment = self.assess_overall_risk_level(var_metrics, perf_metrics, drawdown_metrics)

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

        except (ValueError, RuntimeError) as e:
            logger.error(f"Erreur lors du calcul des métriques de risque: {e}")
            return RiskMetrics(confidence_level=0.0)
        except Exception as e:
            logger.exception(f"Erreur inattendue lors du calcul des métriques de risque: {e}")
            return RiskMetrics(confidence_level=0.0)

    async def _generate_historical_returns(
        self,
        holdings: List[Dict[str, Any]],
        days: int
    ) -> List[Dict[str, float]]:
        """Génère l'historique des returns depuis les vraies données de prix en cache"""

        # Extraire les symboles des holdings
        symbols = [h.get("symbol", "") for h in holdings if h.get("symbol")]
        if not symbols:
            logger.warning("Aucun symbole trouvé dans les holdings")
            return []

        # Importer le module de cache d'historique
        try:
            from services.price_history import get_cached_history, calculate_returns
        except ImportError as e:
            logger.error(f"Impossible d'importer price_history: {e}")
            return await self._generate_historical_returns_fallback(symbols, days)

        logger.info(f"📈 Calcul rendements réels depuis cache pour {len(symbols)} symboles ({days}j)")

        # Collecter l'historique pour tous les symboles
        symbol_histories = {}
        available_symbols = []

        for symbol in symbols:
            history = get_cached_history(symbol, days + 1)  # +1 pour calculer les rendements
            if history and len(history) >= 2:  # Minimum 2 points pour calculer 1 rendement
                symbol_histories[symbol] = history
                available_symbols.append(symbol)
                logger.debug(f"✅ {symbol}: {len(history)} points de prix")
            else:
                logger.warning(f"⚠️ {symbol}: historique insuffisant ou absent")

        if not available_symbols:
            logger.warning("❌ Aucun historique de prix disponible - fallback simulation")
            return await self._generate_historical_returns_fallback(symbols, days)

        # Calculer les rendements pour chaque symbole
        symbol_returns = {}
        for symbol in available_symbols:
            returns = calculate_returns(symbol_histories[symbol], log_returns=True)
            if returns:
                symbol_returns[symbol] = returns[-days:]  # Prendre les N derniers jours

        # Filtrer les séries trop courtes (<10 rendements) pour ne pas réduire la fenêtre globale
        MIN_RETURNS = 10
        symbol_returns = {s: r for s, r in symbol_returns.items() if len(r) >= MIN_RETURNS}
        if not symbol_returns:
            logger.warning("❌ Rendements insuffisants après filtrage - fallback simulation")
            return await self._generate_historical_returns_fallback(symbols, days)

        # Construire une fenêtre cible fixe sans la rétrécir à l'asset le plus court
        max_length = max(len(r) for r in symbol_returns.values())
        target_length = min(days, max_length)
        if target_length < MIN_RETURNS:
            logger.warning("❌ Fenêtre disponible < seuil après filtrage - fallback simulation")
            return await self._generate_historical_returns_fallback(symbols, days)

        # Aligner/padder toutes les séries sur la longueur cible (pad au début avec 0.0 si nécessaire)
        for symbol in list(symbol_returns.keys()):
            seq = symbol_returns[symbol][-target_length:]
            if len(seq) < target_length:
                pad = [0.0] * (target_length - len(seq))
                seq = pad + seq
            symbol_returns[symbol] = seq

        # Construire la série temporelle de rendements
        returns_series = []
        for i in range(target_length):
            day_returns = {}
            for symbol in symbol_returns.keys():
                day_returns[symbol] = symbol_returns[symbol][i]

            # Pour les symboles manquants (non couverts), utiliser 0.0
            for symbol in symbols:
                if symbol not in day_returns:
                    day_returns[symbol] = 0.0

            returns_series.append(day_returns)

        coverage = len(available_symbols) / len(symbols) * 100
        logger.info(f"✅ {len(returns_series)} jours de rendements réels générés ({coverage:.1f}% couverture)")

        # Log de quelques statistiques pour validation
        if returns_series:
            sample_returns = [day.get('BTC', 0.0) for day in returns_series[-30:]]  # 30 derniers jours BTC
            if sample_returns and any(r != 0 for r in sample_returns):
                vol_annualized = np.std(sample_returns) * np.sqrt(252)
                logger.debug(f"🔍 Validation BTC: volatilité 30j annualisée = {vol_annualized:.1%}")

        return returns_series

    async def _generate_historical_returns_fallback(
        self,
        symbols: List[str],
        days: int
    ) -> List[Dict[str, float]]:
        """Fallback avec simulation uniquement si données réelles indisponibles"""

        logger.warning(f"🟡 FALLBACK: Génération de rendements simulés pour {len(symbols)} symboles")

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

        logger.info(f"⚠️ Généré {len(returns_series)} jours de données simulées (FALLBACK)")
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

    def calculate_var_cvar(self, returns: List[float]) -> Dict[str, float]:
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

    def calculate_risk_adjusted_metrics(self, returns: List[float]) -> Dict[str, float]:
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

    def calculate_drawdown_metrics(self, returns: List[float]) -> Dict[str, Any]:
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

    def calculate_distribution_metrics(self, returns: List[float]) -> Dict[str, float]:
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

    def assess_overall_risk_level(
        self,
        var_metrics: Dict[str, float],
        perf_metrics: Dict[str, float],
        drawdown_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Évalue le niveau de risque global du portfolio.

        ✅ Sémantique Risk (docs/RISK_SEMANTICS.md):
        - Risk Score = indicateur POSITIF de robustesse [0-100]
        - Plus haut = plus robuste (risque perçu plus faible)
        - Donc: bonnes métriques → score augmente, mauvaises → score diminue
        """

        # Score basé sur différents critères (50 = neutre)
        score = 50.0

        # VaR impact (plus VaR est élevé, MOINS robuste → score diminue)
        var_95 = abs(var_metrics.get("var_95", 0.0))  # abs() car VaR est négatif
        if var_95 > 0.25:
            score -= 30  # ❌ VaR très élevé → score baisse
        elif var_95 > 0.15:
            score -= 20
        elif var_95 > 0.10:
            score -= 10
        elif var_95 < 0.05:
            score += 10  # ✅ VaR faible → score monte

        # Volatilité impact (plus vol est élevée, MOINS robuste → score diminue)
        vol = perf_metrics.get("volatility", 0.0)
        if vol > 1.0:
            score -= 25  # ❌ Volatilité extrême → score baisse
        elif vol > 0.6:
            score -= 15
        elif vol > 0.4:
            score -= 5
        elif vol < 0.2:
            score += 15  # ✅ Volatilité faible → score monte

        # Max drawdown impact (plus DD est élevé, MOINS robuste → score diminue)
        max_dd = abs(drawdown_metrics.get("max_drawdown", 0.0))  # abs() car DD est négatif
        if max_dd > 0.50:
            score -= 20  # ❌ Drawdown sévère → score baisse
        elif max_dd > 0.30:
            score -= 10
        elif max_dd < 0.10:
            score += 10  # ✅ Drawdown limité → score monte

        # Sharpe ratio impact (plus Sharpe est élevé, PLUS robuste → score augmente)
        sharpe = perf_metrics.get("sharpe", 0.0)
        if sharpe < 0:
            score -= 15  # ❌ Sharpe négatif → score baisse
        elif sharpe > 1.5:
            score += 15  # ✅ Excellent Sharpe → score monte
        elif sharpe > 1.0:
            score += 10  # ✅ Bon Sharpe → score monte

        # Normaliser le score [0-100]
        score = max(0, min(100, score))

        # ✅ Déterminer le niveau de risque INVERSÉ (score élevé = risque faible)
        # Attention: level représente le RISQUE, donc inverse du score
        if score >= 80:
            level = RiskLevel.VERY_LOW  # Score élevé = risque très faible
        elif score >= 65:
            level = RiskLevel.LOW
        elif score >= 50:
            level = RiskLevel.MEDIUM
        elif score >= 35:
            level = RiskLevel.HIGH
        elif score >= 20:
            level = RiskLevel.VERY_HIGH
        else:
            level = RiskLevel.CRITICAL  # Score faible = risque critique

        return {
            "level": level,
            "score": score
        }


# Instance globale pour réutilisation
_global_var_calculator = None


def get_var_calculator() -> VaRCalculator:
    """Retourne l'instance globale du calculateur VaR"""
    global _global_var_calculator
    if _global_var_calculator is None:
        _global_var_calculator = VaRCalculator()
    return _global_var_calculator
