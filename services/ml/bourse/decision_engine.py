"""
Decision Engine for Portfolio Recommendations

Converts scores into actionable recommendations:
- STRONG BUY / BUY / HOLD / SELL / STRONG SELL
- Generates rationale with emojis (✅/⚠️/❌)
- Provides tactical advice
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Convert scores to actionable recommendations"""

    # Decision thresholds (as per plan)
    THRESHOLDS = {
        "strong_buy": {"score": 0.65, "confidence": 0.70},
        "buy": {"score": 0.55, "confidence": 0.60},
        "hold_upper": 0.55,
        "hold_lower": 0.45,
        "sell": {"score": 0.45, "confidence": 0.60},
        "strong_sell": {"score": 0.35, "confidence": 0.70}
    }

    def __init__(self, market_regime: str = "Bull Market"):
        """
        Initialize decision engine

        Args:
            market_regime: Current market regime for context
        """
        self.market_regime = market_regime

    def make_decision(
        self,
        score: float,
        confidence: float,
        breakdown: Dict[str, float],
        technical_data: Dict[str, Any],
        sector_data: Optional[Dict[str, Any]] = None,
        risk_data: Optional[Dict[str, Any]] = None,
        position_sizing: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate recommendation with rationale

        Args:
            score: Final score (0-1)
            confidence: Confidence level (0-1)
            breakdown: Score breakdown by component
            technical_data: Technical indicators
            sector_data: Sector analysis (optional)
            risk_data: Risk metrics (optional)
            position_sizing: Position sizing info (optional)

        Returns:
            Dict with action, rationale, and tactical advice
        """
        # Determine action
        action = self._determine_action(score, confidence)

        # Generate rationale
        rationale = self._generate_rationale(
            action,
            breakdown,
            technical_data,
            sector_data,
            risk_data
        )

        # Generate tactical advice
        tactical_advice = self._generate_tactical_advice(
            action,
            score,
            technical_data,
            sector_data,
            position_sizing
        )

        return {
            "action": action,
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "rationale": rationale,
            "tactical_advice": tactical_advice,
            "market_regime": self.market_regime
        }

    def _determine_action(self, score: float, confidence: float) -> str:
        """Determine action based on score and confidence thresholds"""

        # STRONG BUY
        if score >= self.THRESHOLDS["strong_buy"]["score"] and \
           confidence >= self.THRESHOLDS["strong_buy"]["confidence"]:
            return "STRONG BUY"

        # BUY
        if score >= self.THRESHOLDS["buy"]["score"] and \
           confidence >= self.THRESHOLDS["buy"]["confidence"]:
            return "BUY"

        # STRONG SELL
        if score <= self.THRESHOLDS["strong_sell"]["score"] and \
           confidence >= self.THRESHOLDS["strong_sell"]["confidence"]:
            return "STRONG SELL"

        # SELL
        if score <= self.THRESHOLDS["sell"]["score"] and \
           confidence >= self.THRESHOLDS["sell"]["confidence"]:
            return "SELL"

        # HOLD (default)
        return "HOLD"

    def _generate_rationale(
        self,
        action: str,
        breakdown: Dict[str, float],
        technical_data: Dict[str, Any],
        sector_data: Optional[Dict[str, Any]],
        risk_data: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate rationale bullet points with emojis

        Returns:
            List of rationale strings
        """
        rationale = []

        # Technical rationale
        tech_score = breakdown.get("technical", 0.5)
        rsi = technical_data.get("rsi_14d", 50)
        macd_signal = technical_data.get("macd_signal", "neutral")
        vs_ma50 = technical_data.get("vs_ma50_pct")

        if tech_score > 0.6:
            rationale.append(f"✅ Technical: RSI {rsi:.0f} ({technical_data.get('rsi_signal', 'neutral')}), MACD {macd_signal}")
        elif tech_score < 0.4:
            rationale.append(f"❌ Technical: RSI {rsi:.0f} ({technical_data.get('rsi_signal', 'neutral')}), MACD {macd_signal}")
        else:
            rationale.append(f"⚠️ Technical: RSI {rsi:.0f} (neutral), MACD {macd_signal}")

        # MA trend
        if vs_ma50 is not None:
            if vs_ma50 > 5:
                rationale.append(f"✅ Above MA50 by {vs_ma50:.1f}%, uptrend intact")
            elif vs_ma50 < -5:
                rationale.append(f"❌ Below MA50 by {abs(vs_ma50):.1f}%, downtrend active")
            else:
                rationale.append(f"⚠️ Near MA50 ({vs_ma50:+.1f}%), trend unclear")

        # Regime alignment
        regime_score = breakdown.get("regime", 0.5)
        if regime_score > 0.6:
            rationale.append(f"✅ {self.market_regime} regime supports this asset")
        elif regime_score < 0.4:
            rationale.append(f"❌ {self.market_regime} regime unfavorable for this asset")
        else:
            rationale.append(f"⚠️ {self.market_regime} regime neutral for this asset")

        # Relative strength
        rel_str_score = breakdown.get("relative_strength", 0.5)
        if rel_str_score > 0.6:
            rationale.append(f"✅ Outperforming market benchmark")
        elif rel_str_score < 0.4:
            rationale.append(f"❌ Underperforming market benchmark")

        # Sector momentum (if available)
        if sector_data:
            sector_score = breakdown.get("sector", 0.5)
            sector_name = sector_data.get("sector", "Unknown")
            sector_momentum = sector_data.get("momentum", 1.0)

            if sector_score > 0.6:
                rationale.append(f"✅ {sector_name} sector showing strong momentum ({sector_momentum:.2f}x)")
            elif sector_score < 0.4:
                rationale.append(f"❌ {sector_name} sector weak momentum ({sector_momentum:.2f}x)")

        # Risk metrics (if available)
        if risk_data:
            risk_score = breakdown.get("risk", 0.5)
            volatility = risk_data.get("volatility", 0)
            drawdown = risk_data.get("drawdown_current", 0)

            if risk_score > 0.6:
                rationale.append(f"✅ Good risk profile (Vol {volatility*100:.0f}%, DD {abs(drawdown)*100:.0f}%)")
            elif risk_score < 0.4:
                rationale.append(f"❌ Elevated risk (Vol {volatility*100:.0f}%, DD {abs(drawdown)*100:.0f}%)")

        # Concentration warning (if available)
        if sector_data:
            weight_current = sector_data.get("weight_current", 0)
            if weight_current > 0.40 and action in ["STRONG BUY", "BUY"]:
                rationale.append(f"⚠️ Sector already {weight_current*100:.0f}% of portfolio (concentration risk)")

        return rationale

    def _generate_tactical_advice(
        self,
        action: str,
        score: float,
        technical_data: Dict[str, Any],
        sector_data: Optional[Dict[str, Any]],
        position_sizing: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate actionable tactical advice

        Args:
            position_sizing: Optional position sizing info with guidance

        Returns:
            Tactical advice string
        """
        rsi = technical_data.get("rsi_14d", 50)
        vs_ma50 = technical_data.get("vs_ma50_pct", 0)

        # Check if sector/position limits are reached
        sizing_guidance = position_sizing.get("guidance", "") if position_sizing else ""
        sector_limit_reached = "sector limit reached" in sizing_guidance.lower() or "no room to add" in sizing_guidance.lower()

        if action == "STRONG BUY":
            if sector_limit_reached:
                advice = "Strong buy signal, BUT sector/position limit reached. "
                advice += "Hold current position. Consider rotating from weaker positions in same sector if conviction is high."
            else:
                advice = "Strong buy signal. "
                if rsi < 40:
                    advice += f"Consider adding 3-5% to position on current weakness (RSI {rsi:.0f}). "
                else:
                    advice += "Consider adding 2-3% to position on dips. "

                if sector_data and sector_data.get("weight_current", 0) > 0.35:
                    advice += "Monitor sector concentration risk."
                else:
                    advice += "Good opportunity to increase allocation."

        elif action == "BUY":
            if sector_limit_reached:
                advice = "Buy signal with moderate confidence, BUT sector/position limit reached. "
                advice += "Hold current position. Monitor for sector rotation opportunities."
            else:
                advice = "Buy signal with moderate confidence. "
                if rsi < 50:
                    advice += f"Enter on current levels or wait for slight pullback (RSI {rsi:.0f}). "
                else:
                    advice += f"Wait for pullback before entering (RSI {rsi:.0f} elevated). "

                advice += "Consider adding 1-2% to position."

        elif action == "HOLD":
            advice = "Hold current position. "

            if score > 0.50:
                advice += "Slightly bullish, but not actionable yet. "
                if rsi > 70:
                    advice += f"Consider taking partial profits if RSI stays >70 (current {rsi:.0f})."
                else:
                    advice += "Monitor for BUY signal on further strength."
            else:
                advice += "Slightly bearish, but not actionable yet. "
                if vs_ma50 and vs_ma50 < -3:
                    advice += f"Consider trimming on rallies if trend weakens further (currently {vs_ma50:+.1f}% vs MA50)."
                else:
                    advice += "Monitor for improvement or deterioration."

        elif action == "SELL":
            advice = "Sell signal. "
            if rsi > 60:
                advice += f"Reduce position by 30-50% on current strength (RSI {rsi:.0f}). "
            else:
                advice += f"Reduce position by 30-50%. "

            advice += "Rotate capital to higher-conviction opportunities."

        elif action == "STRONG SELL":
            advice = "Strong sell signal. "
            advice += "Consider reducing position by 50-75% or exiting completely. "

            if vs_ma50 and vs_ma50 < -10:
                advice += f"Downtrend confirmed (MA50 {vs_ma50:+.1f}%), limit further losses."
            else:
                advice += "Multiple negative signals, protect capital."

        return advice

    def update_tactical_advice(
        self,
        action: str,
        score: float,
        technical_data: Dict[str, Any],
        sector_data: Optional[Dict[str, Any]],
        position_sizing: Dict[str, Any]
    ) -> str:
        """
        Update tactical advice with position sizing information

        This method regenerates tactical advice after position sizing is calculated,
        to ensure consistency between sizing guidance and tactical recommendations.

        Args:
            action: Recommendation action (BUY, SELL, etc.)
            score: Final score
            technical_data: Technical indicators
            sector_data: Sector info
            position_sizing: Position sizing with guidance

        Returns:
            Updated tactical advice string
        """
        return self._generate_tactical_advice(
            action,
            score,
            technical_data,
            sector_data,
            position_sizing
        )

    def generate_summary(
        self,
        recommendations: List[Dict[str, Any]],
        market_regime: str
    ) -> Dict[str, Any]:
        """
        Generate portfolio-level summary

        Args:
            recommendations: List of position recommendations
            market_regime: Current market regime

        Returns:
            Summary dict with counts and suggested allocation
        """
        action_counts = {
            "STRONG BUY": 0,
            "BUY": 0,
            "HOLD": 0,
            "SELL": 0,
            "STRONG SELL": 0
        }

        for rec in recommendations:
            action = rec.get("action", "HOLD")
            action_counts[action] = action_counts.get(action, 0) + 1

        total_positions = len(recommendations)
        buy_signals = action_counts["STRONG BUY"] + action_counts["BUY"]
        sell_signals = action_counts["STRONG SELL"] + action_counts["SELL"]

        # Overall posture
        if buy_signals > sell_signals * 2:
            overall_posture = "Risk-On"
        elif sell_signals > buy_signals * 2:
            overall_posture = "Risk-Off"
        else:
            overall_posture = "Neutral"

        # Suggested allocation based on regime and posture
        allocation = self._suggest_allocation(market_regime, overall_posture)

        return {
            "total_positions": total_positions,
            "action_counts": action_counts,
            "buy_signals": buy_signals,
            "hold_signals": action_counts["HOLD"],
            "sell_signals": sell_signals,
            "market_regime": market_regime,
            "overall_posture": overall_posture,
            "suggested_allocation": allocation
        }

    def _suggest_allocation(
        self,
        market_regime: str,
        posture: str
    ) -> Dict[str, str]:
        """Suggest portfolio allocation ranges"""

        # Base allocation by regime
        if market_regime in ["Expansion", "Bull Market"]:
            base_equities = "70-80%"
            base_defensive = "10-15%"
            base_cash = "10-15%"
        elif market_regime == "Correction":
            base_equities = "50-60%"
            base_defensive = "20-30%"
            base_cash = "15-25%"
        else:  # Bear Market
            base_equities = "30-40%"
            base_defensive = "30-40%"
            base_cash = "25-35%"

        # Adjust based on posture
        if posture == "Risk-On":
            equities = base_equities.replace("70", "75").replace("80", "85")
        elif posture == "Risk-Off":
            equities = base_equities.replace("70", "60").replace("80", "70")
        else:
            equities = base_equities

        return {
            "equities": equities,
            "defensive": base_defensive,
            "cash": base_cash
        }
