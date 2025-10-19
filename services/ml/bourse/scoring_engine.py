"""
Scoring Engine for Portfolio Recommendations

Combines multiple signals with adaptive weights based on timeframe:
- Technical indicators
- Market regime alignment
- Relative strength vs benchmark
- Risk metrics
- Sector momentum
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Calculate recommendation scores with adaptive timeframe weights"""

    # Pondérations par timeframe (conformément au plan)
    WEIGHTS = {
        "short": {  # 1-2 weeks: Trading tactique
            "technical": 0.35,
            "regime": 0.25,
            "relative_strength": 0.20,
            "risk": 0.10,
            "sector": 0.10
        },
        "medium": {  # 1 month: Rotation sectorielle
            "technical": 0.25,
            "regime": 0.25,
            "sector": 0.20,
            "risk": 0.15,
            "relative_strength": 0.15
        },
        "long": {  # 3-6 months: Positionnement stratégique
            "regime": 0.30,
            "risk": 0.20,
            "technical": 0.15,
            "relative_strength": 0.15,
            "sector": 0.20
        }
    }

    def __init__(self, timeframe: str = "medium"):
        """
        Initialize scoring engine

        Args:
            timeframe: "short" (1-2w), "medium" (1m), or "long" (3-6m)
        """
        if timeframe not in self.WEIGHTS:
            logger.warning(f"Invalid timeframe '{timeframe}', defaulting to 'medium'")
            timeframe = "medium"

        self.timeframe = timeframe
        self.weights = self.WEIGHTS[timeframe]

    def calculate_score(
        self,
        technical_score: float,
        regime_score: float,
        relative_strength_score: float,
        risk_score: float,
        sector_score: float
    ) -> Dict[str, Any]:
        """
        Calculate weighted recommendation score

        Args:
            technical_score: Technical indicators score (0-1)
            regime_score: Market regime alignment score (0-1)
            relative_strength_score: Performance vs benchmark (0-1)
            risk_score: Risk metrics score (0-1)
            sector_score: Sector momentum score (0-1)

        Returns:
            Dict with final score, breakdown, and confidence
        """
        # Weighted average
        final_score = (
            technical_score * self.weights["technical"] +
            regime_score * self.weights["regime"] +
            relative_strength_score * self.weights["relative_strength"] +
            risk_score * self.weights["risk"] +
            sector_score * self.weights["sector"]
        )

        # Confidence calculation
        # Higher when scores are consistent (low variance)
        scores = [
            technical_score,
            regime_score,
            relative_strength_score,
            risk_score,
            sector_score
        ]
        variance = sum((s - final_score) ** 2 for s in scores) / len(scores)
        confidence = 1.0 - min(variance * 2, 0.4)  # Cap confidence reduction at 40%

        return {
            "final_score": round(final_score, 3),
            "confidence": round(confidence, 3),
            "breakdown": {
                "technical": round(technical_score, 3),
                "regime": round(regime_score, 3),
                "relative_strength": round(relative_strength_score, 3),
                "risk": round(risk_score, 3),
                "sector": round(sector_score, 3)
            },
            "weights": self.weights,
            "timeframe": self.timeframe
        }

    def calculate_regime_score(
        self,
        asset_type: str,
        market_regime: str,
        regime_probabilities: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate regime alignment score based on asset type

        Args:
            asset_type: "equity", "etf", "commodity", "bond", "crypto", etc.
            market_regime: Current market regime
            regime_probabilities: Optional regime probabilities for nuance

        Returns:
            Score 0-1 (higher = better aligned)
        """
        # Regime favorability matrix
        favorability = {
            "Expansion": {  # Violent rebounds post-crash
                "equity": 0.9,
                "etf_tech": 0.95,
                "etf_growth": 0.9,
                "commodity": 0.6,
                "bond": 0.3,
                "gold": 0.2
            },
            "Bull Market": {  # Stable uptrend
                "equity": 0.8,
                "etf_tech": 0.85,
                "etf_growth": 0.8,
                "commodity": 0.5,
                "bond": 0.4,
                "gold": 0.3
            },
            "Correction": {  # Pullbacks, slow bears
                "equity": 0.4,
                "etf_tech": 0.35,
                "etf_growth": 0.3,
                "commodity": 0.5,
                "bond": 0.7,
                "gold": 0.6
            },
            "Bear Market": {  # Crashes
                "equity": 0.2,
                "etf_tech": 0.15,
                "etf_growth": 0.1,
                "commodity": 0.4,
                "bond": 0.9,
                "gold": 0.95
            }
        }

        base_score = favorability.get(market_regime, {}).get(asset_type, 0.5)

        # Adjust with regime probabilities if available
        if regime_probabilities and market_regime in regime_probabilities:
            regime_confidence = regime_probabilities[market_regime]
            # If regime confidence is low, pull score toward neutral (0.5)
            base_score = base_score * regime_confidence + 0.5 * (1 - regime_confidence)

        return base_score

    def calculate_relative_strength_score(
        self,
        asset_return: float,
        benchmark_return: float
    ) -> float:
        """
        Calculate relative strength score vs benchmark

        Args:
            asset_return: Asset return (e.g., 30-day %)
            benchmark_return: Benchmark return (e.g., SPY 30-day %)

        Returns:
            Score 0-1 (higher = outperforming)
        """
        # Relative performance
        relative_perf = asset_return - benchmark_return

        # Score mapping:
        # +15% outperformance = 1.0
        # 0% relative = 0.5
        # -15% underperformance = 0.0

        if relative_perf >= 15:
            return 1.0
        elif relative_perf <= -15:
            return 0.0
        else:
            # Linear mapping
            return 0.5 + (relative_perf / 30.0)

    def calculate_risk_score(
        self,
        volatility: float,
        drawdown_current: float,
        sharpe_ratio: Optional[float] = None
    ) -> float:
        """
        Calculate risk quality score

        Args:
            volatility: Annualized volatility (e.g., 0.25 = 25%)
            drawdown_current: Current drawdown from ATH (e.g., -0.10 = -10%)
            sharpe_ratio: Optional Sharpe ratio

        Returns:
            Score 0-1 (higher = better risk profile)
        """
        score = 0.0

        # Volatility component (40%)
        # Lower vol = higher score
        if volatility < 0.15:  # <15% vol
            vol_score = 1.0
        elif volatility < 0.25:  # 15-25%
            vol_score = 0.7
        elif volatility < 0.40:  # 25-40%
            vol_score = 0.5
        else:  # >40%
            vol_score = 0.2
        score += vol_score * 0.4

        # Drawdown component (40%)
        # Smaller drawdown = higher score
        drawdown_abs = abs(drawdown_current)
        if drawdown_abs < 0.05:  # <5% from ATH
            dd_score = 1.0
        elif drawdown_abs < 0.10:  # 5-10%
            dd_score = 0.8
        elif drawdown_abs < 0.20:  # 10-20%
            dd_score = 0.5
        else:  # >20%
            dd_score = 0.2
        score += dd_score * 0.4

        # Sharpe component (20%)
        if sharpe_ratio is not None:
            if sharpe_ratio > 1.5:
                sharpe_score = 1.0
            elif sharpe_ratio > 1.0:
                sharpe_score = 0.8
            elif sharpe_ratio > 0.5:
                sharpe_score = 0.6
            elif sharpe_ratio > 0:
                sharpe_score = 0.4
            else:
                sharpe_score = 0.2
            score += sharpe_score * 0.2
        else:
            score += 0.5 * 0.2  # Neutral if no Sharpe

        return score

    def calculate_sector_score(
        self,
        sector_momentum: float,
        sector_weight_current: float,
        sector_weight_target: float
    ) -> float:
        """
        Calculate sector rotation score

        Args:
            sector_momentum: Sector performance vs market (e.g., 0.95 = -5% vs SPY)
            sector_weight_current: Current portfolio weight in sector (e.g., 0.25 = 25%)
            sector_weight_target: Target weight (e.g., 0.20 = 20%)

        Returns:
            Score 0-1 (higher = buy in sector, lower = sell)
        """
        # Momentum component (60%)
        if sector_momentum > 1.05:  # Outperforming by >5%
            momentum_score = 0.9
        elif sector_momentum > 1.0:  # Outperforming
            momentum_score = 0.7
        elif sector_momentum > 0.95:  # Slight underperformance
            momentum_score = 0.5
        else:  # Underperforming >5%
            momentum_score = 0.3

        # Allocation component (40%)
        # If overweight, penalize BUY; if underweight, favor BUY
        weight_diff = sector_weight_current - sector_weight_target

        if weight_diff > 0.10:  # Overweight by >10%
            allocation_score = 0.2  # Don't add more
        elif weight_diff > 0.05:  # Slightly overweight
            allocation_score = 0.4
        elif weight_diff > -0.05:  # At target
            allocation_score = 0.6
        else:  # Underweight
            allocation_score = 0.8  # Room to add

        return momentum_score * 0.6 + allocation_score * 0.4

    def explain_score(
        self,
        score_data: Dict[str, Any],
        include_weights: bool = True
    ) -> str:
        """
        Generate human-readable explanation of score

        Args:
            score_data: Output from calculate_score()
            include_weights: Whether to include weight details

        Returns:
            Explanation string
        """
        breakdown = score_data["breakdown"]
        weights = score_data["weights"]

        explanation = f"Score: {score_data['final_score']:.2f} (Confidence: {score_data['confidence']:.0%})\n"

        if include_weights:
            explanation += f"\nTimeframe: {self.timeframe.upper()}\n"
            explanation += "Components:\n"

            for component in ["technical", "regime", "relative_strength", "risk", "sector"]:
                score_val = breakdown[component]
                weight_val = weights[component]
                contribution = score_val * weight_val

                explanation += f"  • {component.replace('_', ' ').title()}: "
                explanation += f"{score_val:.2f} × {weight_val:.0%} = {contribution:.3f}\n"

        return explanation
