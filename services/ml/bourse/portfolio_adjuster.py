"""
Portfolio Adjuster for Recommendations

Applies portfolio-level constraints:
- Sector concentration limits (downgrade BUY if sector >40%)
- Correlation limits (keep only best if 3+ correlated positions with BUY)
- Position size limits
- Risk budget constraints
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PortfolioAdjuster:
    """Adjust recommendations based on portfolio constraints"""

    def __init__(
        self,
        max_sector_pct: float = 0.40,
        max_position_pct: float = 0.05,
        max_correlated_buys: int = 3,
        correlation_threshold: float = 0.80
    ):
        """
        Initialize portfolio adjuster

        Args:
            max_sector_pct: Maximum sector allocation (default 40%)
            max_position_pct: Maximum single position (default 5%)
            max_correlated_buys: Max correlated positions with BUY signal
            correlation_threshold: Correlation threshold (default 0.80)
        """
        self.max_sector_pct = max_sector_pct
        self.max_position_pct = max_position_pct
        self.max_correlated_buys = max_correlated_buys
        self.correlation_threshold = correlation_threshold

    def adjust_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        sector_weights: Dict[str, float],
        correlations: Optional[Dict[str, Dict[str, float]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Adjust recommendations based on portfolio constraints

        Args:
            recommendations: List of position recommendations
            sector_weights: Current sector allocations {sector: weight}
            correlations: Optional correlation matrix {symbol1: {symbol2: corr}}

        Returns:
            Adjusted recommendations list
        """
        adjusted = []

        # Step 0: Consolidate duplicate positions (P0 Enhancement - Oct 2025)
        adjusted = self._consolidate_duplicate_positions(recommendations)

        # Step 1: Apply sector concentration limits
        adjusted = self._apply_sector_limits(adjusted, sector_weights)

        # Step 2: Apply Risk/Reward filter (downgrade BUY if R/R < 1.5)
        adjusted = self._apply_risk_reward_filter(adjusted, min_rr_ratio=1.5)

        # Step 3: Apply correlation limits (if data available)
        if correlations:
            adjusted = self._apply_correlation_limits(adjusted, correlations)

        # Step 4: Add adjustment notes
        for rec in adjusted:
            if rec.get("adjusted"):
                rec["adjustment_note"] = self._get_adjustment_note(rec)

        return adjusted

    def _consolidate_duplicate_positions(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Consolidate duplicate positions (e.g., 7x AMD → 1x AMD aggregate)

        P0 Enhancement - Oct 2025

        Handles Saxo double-counting: CSV contains both aggregate + detail lines for multi-lot positions.
        Detects and removes aggregate line if detail lines exist.

        Args:
            recommendations: List of position recommendations

        Returns:
            List with duplicates consolidated
        """
        # Group by symbol
        by_symbol = {}
        for rec in recommendations:
            symbol = rec.get('symbol', 'UNKNOWN')
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(rec)

        consolidated = []

        for symbol, recs in by_symbol.items():
            if len(recs) == 1:
                # Single position, no consolidation needed
                consolidated.append(recs[0])
            else:
                # Multiple positions for same symbol → check for Saxo double-counting
                logger.info(f"Analyzing {len(recs)} positions for {symbol}")

                # Separate lines with and without position_id (from original CSV metadata)
                # In Saxo CSV: aggregate lines have no Position ID, detail lines have numeric Position ID
                lines_with_id = []
                lines_without_id = []

                for rec in recs:
                    # Check if this rec came from a CSV line with Position ID
                    # We need to add this metadata in saxo_import connector
                    # For now, use heuristic: if multiple lines and one has significantly more value, it's aggregate
                    lines_without_id.append(rec)  # Fallback: treat all as without ID

                # Heuristic detection: if sum of smaller values ≈ largest value, it's double-counting
                values = sorted([r.get('current_value', 0) for r in recs], reverse=True)
                largest = values[0]
                sum_others = sum(values[1:])

                # If largest ≈ sum of others (within 5%), it's a Saxo aggregate + details situation
                if len(values) > 1 and abs(largest - sum_others) / max(largest, 1) < 0.05:
                    logger.info(f"{symbol}: Detected Saxo aggregate (${largest:.0f}) + details (${sum_others:.0f}) - keeping only detail lines")
                    # Remove the largest value (aggregate line) and keep detail lines
                    recs_sorted = sorted(recs, key=lambda x: x.get('current_value', 0), reverse=True)
                    detail_recs = recs_sorted[1:]  # All except largest
                    recs = detail_recs

                # Multiple positions remaining → consolidate normally
                logger.info(f"Consolidating {len(recs)} detail positions for {symbol}")

                # Aggregate metrics
                total_value = sum(r.get('current_value', 0) for r in recs)
                avg_score = sum(r.get('score', 0) for r in recs) / len(recs)
                avg_confidence = sum(r.get('confidence', 0) for r in recs) / len(recs)

                # Use first position as template
                consolidated_rec = recs[0].copy()

                # Override with aggregated values
                consolidated_rec['current_value'] = total_value
                consolidated_rec['score'] = avg_score
                consolidated_rec['confidence'] = avg_confidence
                consolidated_rec['positions_count'] = len(recs)
                consolidated_rec['fragmentation_warning'] = True

                # Update tactical advice
                original_advice = consolidated_rec.get('tactical_advice', '')
                consolidated_rec['tactical_advice'] = (
                    f"⚠️ {len(recs)} lots d'achat séparés détectés (total consolidé: ${total_value:,.0f}). "
                    f"CSV Saxo contient {len(recs)} lignes distinctes pour ce symbole (achats à différentes dates/prix). "
                    f"Recommandation: Garder tels quels dans broker, mais tracker comme position unique dans votre suivi. "
                    f"{original_advice}"
                )

                # Collect all position IDs for reference
                consolidated_rec['fragmented_position_ids'] = [
                    r.get('symbol', '') + '_' + str(i) for i, r in enumerate(recs)
                ]

                consolidated.append(consolidated_rec)

                logger.info(
                    f"Consolidated {symbol}: {len(recs)} positions → 1 position "
                    f"(total value: ${total_value:,.2f}, avg score: {avg_score:.2f})"
                )

        return consolidated

    def _apply_sector_limits(
        self,
        recommendations: List[Dict[str, Any]],
        sector_weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Apply sector concentration limits in 2 passes for immediate rebalancing

        Strategy (2-pass approach):

        Pass 1: Handle BUY signals
        - If sector >40% AND multiple BUY signals:
          - Keep only the highest-score BUY as is
          - Downgrade others: STRONG BUY → BUY, BUY → HOLD

        Pass 2: Handle ALL HOLD signals (including freshly downgraded from Pass 1)
        - If sector >45%:
          - Downgrade bottom 30% of HOLDs to SELL
        - If sector 40-45%:
          - Add concentration warning flag
        """
        # PASS 1: Downgrade BUY signals
        adjusted_pass1 = self._apply_sector_limits_pass1_buys(recommendations, sector_weights)

        # PASS 2: Downgrade HOLD signals (including those downgraded from BUY in Pass 1)
        adjusted_pass2 = self._apply_sector_limits_pass2_holds(adjusted_pass1, sector_weights)

        return adjusted_pass2

    def _apply_sector_limits_pass1_buys(
        self,
        recommendations: List[Dict[str, Any]],
        sector_weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Pass 1: Downgrade BUY signals in overweight sectors
        """
        adjusted = []

        # Group by sector
        by_sector = {}
        for rec in recommendations:
            sector = rec.get("sector", "Unknown")
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(rec)

        # Check each sector
        for sector, recs in by_sector.items():
            sector_weight = sector_weights.get(sector, 0.0)

            # Check if sector over-allocated
            if sector_weight > self.max_sector_pct:
                # Find BUY signals in this sector
                buy_signals = [
                    r for r in recs
                    if r.get("action") in ["STRONG BUY", "BUY"]
                ]

                # Handle BUY signals
                if len(buy_signals) > 0:
                    # Sort by score (keep best)
                    buy_signals.sort(key=lambda x: x.get("score", 0), reverse=True)

                    # Downgrade ALL BUY signals when sector is overweight
                    # Rationale: Don't add to overweight sector, even for best signal
                    for i, rec in enumerate(buy_signals):
                        original_action = rec["action"]

                        # Downgrade based on original action
                        if original_action == "STRONG BUY":
                            rec["action"] = "HOLD"  # STRONG BUY → HOLD (not BUY)
                        elif original_action == "BUY":
                            rec["action"] = "HOLD"

                        rec["adjusted"] = True
                        rec["adjustment_reason"] = "sector_concentration"
                        rec["original_action"] = original_action
                        rec["sector_weight"] = sector_weight

                        logger.info(
                            f"Pass 1: {rec.get('symbol')}: Downgraded {original_action} → {rec['action']} "
                            f"(sector {sector} at {sector_weight*100:.0f}% > {self.max_sector_pct*100:.0f}%)"
                        )

                        adjusted.append(rec)

                # Add non-BUY positions as is (will be processed in Pass 2)
                for rec in recs:
                    if rec not in buy_signals:
                        adjusted.append(rec)
            else:
                # Sector OK, no adjustment
                adjusted.extend(recs)

        return adjusted

    def _apply_sector_limits_pass2_holds(
        self,
        recommendations: List[Dict[str, Any]],
        sector_weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Pass 2: Downgrade HOLD signals (including those just downgraded from BUY) in overweight sectors
        """
        adjusted = []

        # Group by sector
        by_sector = {}
        for rec in recommendations:
            sector = rec.get("sector", "Unknown")
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(rec)

        # Check each sector
        for sector, recs in by_sector.items():
            sector_weight = sector_weights.get(sector, 0.0)

            # Check if sector over-allocated
            if sector_weight > self.max_sector_pct:
                # Find ALL HOLD signals in this sector (including freshly downgraded from Pass 1)
                hold_signals = [
                    r for r in recs
                    if r.get("action") == "HOLD"
                ]

                # Handle HOLD signals
                if len(hold_signals) > 0:
                    # If sector >45%, downgrade weakest HOLDs to SELL
                    if sector_weight > 0.45:
                        # Sort HOLD by score (ascending, weakest first)
                        hold_signals.sort(key=lambda x: x.get("score", 0))

                        # Downgrade bottom 30% of HOLDs to SELL
                        num_to_downgrade = max(1, int(len(hold_signals) * 0.3))

                        for i, rec in enumerate(hold_signals):
                            if i < num_to_downgrade:
                                # Downgrade weakest to SELL
                                original_action = rec.get("original_action", "HOLD")
                                rec["action"] = "SELL"
                                rec["adjusted"] = True
                                rec["adjustment_reason"] = "sector_concentration_high"
                                if not rec.get("original_action"):
                                    rec["original_action"] = "HOLD"
                                rec["sector_weight"] = sector_weight

                                logger.info(
                                    f"Pass 2: {rec.get('symbol')}: Downgraded HOLD → SELL "
                                    f"(sector {sector} at {sector_weight*100:.0f}% > 45%, score {rec.get('score', 0):.2f})"
                                )
                            else:
                                # Add concentration warning to other HOLDs
                                rec["concentration_warning"] = True
                                rec["sector_weight"] = sector_weight

                            adjusted.append(rec)
                    else:
                        # Sector >40% but <45%, just add warning
                        for rec in hold_signals:
                            rec["concentration_warning"] = True
                            rec["sector_weight"] = sector_weight
                            adjusted.append(rec)

                # Add non-HOLD positions as is
                for rec in recs:
                    if rec not in hold_signals:
                        adjusted.append(rec)
            else:
                # Sector OK, no adjustment
                adjusted.extend(recs)

        return adjusted

    def _apply_risk_reward_filter(
        self,
        recommendations: List[Dict[str, Any]],
        min_rr_ratio: float = 1.5
    ) -> List[Dict[str, Any]]:
        """
        Downgrade BUY signals with insufficient Risk/Reward ratio

        Strategy:
        - BUY or STRONG BUY with R/R < 1.5 → downgrade to HOLD
        - Rationale: Don't recommend buying if risk > reward

        Args:
            recommendations: List of recommendations
            min_rr_ratio: Minimum acceptable R/R ratio (default 1.5)

        Returns:
            Adjusted recommendations
        """
        adjusted = []

        for rec in recommendations:
            action = rec.get("action", "HOLD")

            # Only check BUY signals
            if action in ["STRONG BUY", "BUY"]:
                price_targets = rec.get("price_targets", {})
                rr_tp1 = price_targets.get("risk_reward_tp1", 0)

                # If R/R insufficient, downgrade to HOLD
                if rr_tp1 < min_rr_ratio:
                    original_action = rec["action"]
                    rec["action"] = "HOLD"
                    rec["adjusted"] = True
                    rec["adjustment_reason"] = "insufficient_risk_reward"
                    rec["original_action"] = original_action
                    rec["risk_reward_tp1"] = rr_tp1

                    logger.info(
                        f"{rec.get('symbol')}: Downgraded {original_action} → HOLD "
                        f"(R/R {rr_tp1:.2f} < {min_rr_ratio})"
                    )

            adjusted.append(rec)

        return adjusted

    def _apply_correlation_limits(
        self,
        recommendations: List[Dict[str, Any]],
        correlations: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Limit highly correlated positions with BUY signals

        Strategy:
        - Find clusters of 3+ positions with correlation >0.80
        - If cluster has multiple BUY signals:
          - Keep only the highest-score BUY
          - Downgrade others to HOLD
        """
        adjusted = []

        # Get all BUY signals
        buy_signals = [
            r for r in recommendations
            if r.get("action") in ["STRONG BUY", "BUY"]
        ]

        # Find correlated clusters
        clusters = self._find_correlated_clusters(
            [r["symbol"] for r in buy_signals],
            correlations
        )

        # Track which positions to downgrade
        downgrade_symbols = set()

        for cluster in clusters:
            if len(cluster) >= self.max_correlated_buys:
                # Get recommendations for this cluster
                cluster_recs = [
                    r for r in buy_signals
                    if r["symbol"] in cluster
                ]

                # Sort by score (keep best)
                cluster_recs.sort(key=lambda x: x.get("score", 0), reverse=True)

                # Mark all except best for downgrade
                for rec in cluster_recs[1:]:
                    downgrade_symbols.add(rec["symbol"])

        # Apply downgrades
        for rec in recommendations:
            if rec["symbol"] in downgrade_symbols:
                original_action = rec["action"]
                if original_action == "STRONG BUY":
                    rec["action"] = "BUY"
                elif original_action == "BUY":
                    rec["action"] = "HOLD"

                rec["adjusted"] = True
                rec["adjustment_reason"] = "correlation_limit"
                rec["original_action"] = original_action

            adjusted.append(rec)

        return adjusted

    def _find_correlated_clusters(
        self,
        symbols: List[str],
        correlations: Dict[str, Dict[str, float]]
    ) -> List[List[str]]:
        """
        Find clusters of highly correlated symbols

        Returns:
            List of clusters (each cluster is a list of symbols)
        """
        clusters = []
        visited = set()

        for symbol in symbols:
            if symbol in visited:
                continue

            # Find all symbols correlated with this one
            cluster = [symbol]
            visited.add(symbol)

            symbol_corrs = correlations.get(symbol, {})

            for other_symbol in symbols:
                if other_symbol == symbol or other_symbol in visited:
                    continue

                corr = symbol_corrs.get(other_symbol, 0.0)
                if abs(corr) >= self.correlation_threshold:
                    cluster.append(other_symbol)
                    visited.add(other_symbol)

            if len(cluster) >= self.max_correlated_buys:
                clusters.append(cluster)

        return clusters

    def _get_adjustment_note(self, rec: Dict[str, Any]) -> str:
        """Generate human-readable adjustment note"""

        reason = rec.get("adjustment_reason", "unknown")
        original = rec.get("original_action", "")

        if reason == "sector_concentration":
            sector_weight = rec.get("sector_weight", 0) * 100
            return f"Downgraded from {original} due to sector concentration ({sector_weight:.0f}% > {self.max_sector_pct*100:.0f}%)"

        elif reason == "sector_concentration_high":
            sector_weight = rec.get("sector_weight", 0) * 100
            return f"Downgraded from {original} due to high sector concentration ({sector_weight:.0f}% > 45%)"

        elif reason == "insufficient_risk_reward":
            rr_ratio = rec.get("risk_reward_tp1", 0)
            return f"Downgraded from {original} due to insufficient Risk/Reward ratio ({rr_ratio:.2f} < 1.5)"

        elif reason == "correlation_limit":
            return f"Downgraded from {original} due to high correlation with other BUY signals"

        elif reason == "position_size":
            return f"Downgraded from {original} due to position size limit"

        else:
            return f"Adjusted from {original}"

    def calculate_sector_targets(
        self,
        current_weights: Dict[str, float],
        market_regime: str,
        sector_momentum: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Calculate target sector allocations based on regime and momentum

        Args:
            current_weights: Current sector weights
            market_regime: Current market regime
            sector_momentum: Optional sector momentum scores

        Returns:
            Dict of target weights {sector: target_weight}
        """
        # Base allocations by regime
        base_allocations = self._get_base_allocations(market_regime)

        # Adjust based on momentum if available
        if sector_momentum:
            base_allocations = self._adjust_for_momentum(
                base_allocations,
                sector_momentum
            )

        return base_allocations

    def _get_base_allocations(self, market_regime: str) -> Dict[str, float]:
        """Get base sector allocations by market regime"""

        if market_regime in ["Expansion", "Bull Market"]:
            return {
                "Technology": 0.35,
                "Finance": 0.15,
                "Healthcare": 0.10,
                "Consumer": 0.15,
                "Energy": 0.05,
                "Industrials": 0.10,
                "Defensive": 0.05,
                "Cash": 0.05
            }
        elif market_regime == "Correction":
            return {
                "Technology": 0.25,
                "Finance": 0.15,
                "Healthcare": 0.15,
                "Consumer": 0.10,
                "Energy": 0.05,
                "Industrials": 0.05,
                "Defensive": 0.15,
                "Cash": 0.10
            }
        else:  # Bear Market
            return {
                "Technology": 0.15,
                "Finance": 0.10,
                "Healthcare": 0.15,
                "Consumer": 0.05,
                "Energy": 0.05,
                "Industrials": 0.05,
                "Defensive": 0.30,
                "Cash": 0.15
            }

    def _adjust_for_momentum(
        self,
        base_allocations: Dict[str, float],
        momentum: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Adjust allocations based on sector momentum

        Increase allocation to sectors with momentum >1.05
        Decrease allocation to sectors with momentum <0.95
        """
        adjusted = {}
        adjustment_pool = 0.0

        for sector, base_weight in base_allocations.items():
            sector_momentum = momentum.get(sector, 1.0)

            if sector_momentum > 1.05:
                # Increase by up to 5%
                increase = min(0.05, (sector_momentum - 1.0) * 0.5)
                adjusted[sector] = base_weight + increase
                adjustment_pool -= increase

            elif sector_momentum < 0.95:
                # Decrease by up to 5%
                decrease = min(0.05, (1.0 - sector_momentum) * 0.5)
                adjusted[sector] = max(0, base_weight - decrease)
                adjustment_pool += decrease

            else:
                adjusted[sector] = base_weight

        # Normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted
