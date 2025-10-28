"""
Recommendations Orchestrator

Orchestrates portfolio recommendations by combining:
- Technical indicators
- Market regime detection
- Sector rotation analysis
- Risk metrics
- Scoring engine
- Decision engine
- Price targets
- Portfolio adjustments
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from services.ml.bourse.technical_indicators import TechnicalIndicators
from services.ml.bourse.scoring_engine import ScoringEngine
from services.ml.bourse.decision_engine import DecisionEngine
from services.ml.bourse.price_targets import PriceTargets
from services.ml.bourse.portfolio_adjuster import PortfolioAdjuster
from services.ml.bourse.data_sources import StocksDataSource
from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics
from services.risk.bourse.data_fetcher import BourseDataFetcher

logger = logging.getLogger(__name__)


class RecommendationsOrchestrator:
    """Orchestrate portfolio recommendations generation"""

    def __init__(self):
        """Initialize orchestrator with all components"""
        self.data_source = StocksDataSource()

    async def generate_recommendations(
        self,
        positions: List[Dict[str, Any]],
        market_regime: str,
        regime_probabilities: Optional[Dict[str, float]] = None,
        sector_analysis: Optional[Dict[str, Any]] = None,
        benchmark: str = "SPY",
        timeframe: str = "medium",
        lookback_days: int = 90
    ) -> Dict[str, Any]:
        """
        Generate comprehensive portfolio recommendations

        Args:
            positions: List of current positions
            market_regime: Current market regime
            regime_probabilities: Regime probability distribution
            sector_analysis: Sector rotation analysis results
            benchmark: Benchmark symbol (default SPY)
            timeframe: short/medium/long
            lookback_days: Days of historical data

        Returns:
            Dict with recommendations for each position and summary
        """
        try:
            logger.info(f"Generating {timeframe} recommendations for {len(positions)} positions")

            # Initialize components
            technical = TechnicalIndicators(market_regime=market_regime)
            scoring = ScoringEngine(timeframe=timeframe)
            decision = DecisionEngine(market_regime=market_regime)
            targets = PriceTargets(timeframe=timeframe, market_regime=market_regime)
            adjuster = PortfolioAdjuster()

            # Get benchmark data
            benchmark_data = await self._get_benchmark_data(benchmark, lookback_days)
            benchmark_return = self._calculate_return(benchmark_data['close'], 30) if benchmark_data is not None else 0

            # Calculate total portfolio value
            total_value = sum(pos.get('market_value', 0) or 0 for pos in positions)

            # Generate sector analysis directly if not provided
            if sector_analysis is None:
                logger.info("Computing sector analysis directly from positions...")
                sector_analysis = await self._compute_sector_analysis(positions, lookback_days)

            # Calculate sector weights
            sector_weights = self._calculate_sector_weights(positions, sector_analysis)

            # Generate recommendations for each position
            recommendations = []
            for pos in positions:
                try:
                    rec = await self._analyze_position(
                        position=pos,
                        technical=technical,
                        scoring=scoring,
                        decision=decision,
                        targets=targets,
                        market_regime=market_regime,
                        regime_probabilities=regime_probabilities,
                        sector_analysis=sector_analysis,
                        benchmark_return=benchmark_return,
                        lookback_days=lookback_days,
                        total_portfolio_value=total_value
                    )

                    if rec:
                        recommendations.append(rec)

                except Exception as e:
                    logger.error(f"Error analyzing position {pos.get('symbol', 'unknown')}: {e}")
                    continue

            # Apply portfolio-level adjustments
            recommendations = adjuster.adjust_recommendations(
                recommendations=recommendations,
                sector_weights=sector_weights
            )

            # Generate summary
            summary = decision.generate_summary(recommendations, market_regime)

            return {
                "recommendations": recommendations,
                "summary": summary,
                "timeframe": timeframe,
                "market_regime": market_regime,
                "benchmark": benchmark,
                "generated_at": datetime.now().isoformat(),
                "total_positions": len(recommendations)
            }

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            raise

    async def _analyze_position(
        self,
        position: Dict[str, Any],
        technical: TechnicalIndicators,
        scoring: ScoringEngine,
        decision: DecisionEngine,
        targets: PriceTargets,
        market_regime: str,
        regime_probabilities: Optional[Dict[str, float]],
        sector_analysis: Optional[Dict[str, Any]],
        benchmark_return: float,
        lookback_days: int,
        total_portfolio_value: float
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze single position and generate recommendation

        Returns:
            Dict with recommendation details or None if error
        """
        # Get symbol from instrument_id (Saxo positions use this field)
        symbol = position.get('instrument_id', position.get('symbol', position.get('ticker', 'UNKNOWN')))

        # Get historical data
        hist_data = await self.data_source.get_ohlcv_data(
            symbol=symbol,
            lookback_days=lookback_days
        )

        if hist_data is None or len(hist_data) < 20:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Technical analysis
        tech_analysis = technical.analyze_stock(hist_data, symbol)

        # Asset type detection (extract from tags if present)
        asset_class = ''
        tags = position.get('tags', [])
        for tag in tags:
            if tag.startswith('asset_class:'):
                asset_class = tag.split(':')[1]
                break

        # Detect asset type + CFD status (P0 Enhancement - Oct 2025)
        asset_type, is_cfd, leverage = self._detect_asset_type(symbol, asset_class, position)

        # Regime score
        regime_score = scoring.calculate_regime_score(
            asset_type=asset_type,
            market_regime=market_regime,
            regime_probabilities=regime_probabilities
        )

        # Relative strength
        asset_return = self._calculate_return(hist_data['close'], 30)
        rel_strength_score = scoring.calculate_relative_strength_score(
            asset_return=asset_return,
            benchmark_return=benchmark_return
        )

        # Risk score
        volatility = hist_data['close'].pct_change().std() * np.sqrt(252)
        drawdown = self._calculate_current_drawdown(hist_data['close'])
        risk_score = scoring.calculate_risk_score(
            volatility=volatility,
            drawdown_current=drawdown
        )

        # Sector score
        sector_score = 0.5  # Default
        sector_data = None
        if sector_analysis:
            sector_info = self._get_sector_info(symbol, sector_analysis)
            if sector_info:
                sector_score = scoring.calculate_sector_score(
                    sector_momentum=sector_info.get('momentum', 1.0),
                    sector_weight_current=sector_info.get('weight', 0),
                    sector_weight_target=sector_info.get('target_weight', 0.20)
                )
                sector_data = sector_info

        # Calculate final score
        score_result = scoring.calculate_score(
            technical_score=tech_analysis.get('technical_score', 0.5),
            regime_score=regime_score,
            relative_strength_score=rel_strength_score,
            risk_score=risk_score,
            sector_score=sector_score
        )

        # Make decision
        decision_result = decision.make_decision(
            score=score_result['final_score'],
            confidence=score_result['confidence'],
            breakdown=score_result['breakdown'],
            technical_data=tech_analysis,
            sector_data=sector_data,
            risk_data={
                'volatility': volatility,
                'drawdown_current': drawdown
            }
        )

        # Extract avg_price from position (for trailing stop calculation)
        avg_price = position.get('avg_price', None)

        # Calculate price targets (with CFD leverage adjustment if applicable)
        sr_levels = tech_analysis.get('support_resistance', {})
        price_targets = targets.calculate_targets(
            current_price=hist_data['close'].iloc[-1],
            action=decision_result['action'],
            support_resistance=sr_levels,
            volatility=volatility,
            price_data=hist_data,  # Pass historical data for advanced stop loss calculation
            avg_price=avg_price,  # Pass avg_price for trailing stop calculation
            leverage=leverage if is_cfd else None  # Pass leverage for CFD stop adjustment (P0 Enhancement)
        )

        # Calculate position sizing
        current_value = position.get('market_value', 0) or 0
        current_weight = current_value / total_portfolio_value if total_portfolio_value > 0 else 0
        sector_weight = sector_data.get('weight', 0) if sector_data else 0

        position_sizing = targets.calculate_position_size(
            action=decision_result['action'],
            confidence=score_result['confidence'],
            portfolio_value=total_portfolio_value,
            current_allocation=current_weight,
            sector_weight=sector_weight
        )

        # Update tactical advice with position sizing info
        decision_result['tactical_advice'] = decision.update_tactical_advice(
            action=decision_result['action'],
            score=score_result['final_score'],
            technical_data=tech_analysis,
            sector_data=sector_data,
            position_sizing=position_sizing
        )

        # CFD-specific tactical advice adjustment (P0 Enhancement - Oct 2025)
        if is_cfd:
            cfd_warning = f"⚠️ CFD/Leveraged Position ({leverage:.0f}x) - Use tighter stops. "
            if decision_result['action'] in ['STRONG BUY', 'BUY']:
                cfd_warning += "Reduce position size by 50% due to leverage risk. "
            elif decision_result['action'] == 'HOLD':
                cfd_warning += "Monitor closely, consider partial exit on volatility. "
            decision_result['tactical_advice'] = cfd_warning + decision_result['tactical_advice']

        # Compile recommendation
        return {
            "symbol": symbol,
            "name": position.get('name', symbol),  # Saxo doesn't have name, will use symbol
            "current_value": current_value,
            "weight_pct": round(current_weight * 100, 1),
            "sector": sector_data.get('sector', 'Unknown') if sector_data else 'Unknown',
            "action": decision_result['action'],
            "confidence": decision_result['confidence'],
            "score": score_result['final_score'],
            "rationale": decision_result['rationale'],
            "tactical_advice": decision_result['tactical_advice'],
            "technical": {
                "rsi_14d": tech_analysis.get('rsi_14d'),
                "macd_signal": tech_analysis.get('macd_signal'),
                "vs_ma50_pct": tech_analysis.get('vs_ma50_pct'),
                "vs_spy_30d": round(asset_return - benchmark_return, 1) if asset_return else None
            },
            "price_targets": price_targets,
            "position_sizing": position_sizing,
            "score_breakdown": score_result['breakdown'],
            # CFD metadata (P0 Enhancement - Oct 2025)
            "is_cfd": is_cfd,
            "leverage": leverage if is_cfd else None,
            "cfd_warning": is_cfd  # Flag for frontend badge
        }

    async def _get_benchmark_data(
        self,
        benchmark: str,
        lookback_days: int
    ) -> Optional[pd.DataFrame]:
        """Get benchmark historical data"""
        try:
            return await self.data_source.get_ohlcv_data(
                symbol=benchmark,
                lookback_days=lookback_days
            )
        except Exception as e:
            logger.error(f"Error fetching benchmark {benchmark}: {e}")
            return None

    def _calculate_return(self, prices: pd.Series, days: int) -> float:
        """Calculate percentage return over N days"""
        if len(prices) < days:
            return 0.0

        return ((prices.iloc[-1] / prices.iloc[-days]) - 1) * 100

    def _calculate_current_drawdown(self, prices: pd.Series) -> float:
        """Calculate current drawdown from ATH"""
        ath = prices.max()
        current = prices.iloc[-1]
        return (current / ath) - 1

    def _detect_asset_type(self, symbol: str, asset_class: str, position: Optional[Dict[str, Any]] = None) -> tuple:
        """
        Detect asset type for regime alignment

        Returns:
            tuple: (asset_type, is_cfd, leverage_multiplier)
            - asset_type: 'equity', 'etf_tech', 'gold', 'bond', etc.
            - is_cfd: True if CFD/leveraged product
            - leverage_multiplier: Estimated leverage (1.0 for normal, 5.0 for CFD, etc.)
        """
        is_cfd = False
        leverage = 1.0

        # CFD Detection (P0 Enhancement - Oct 2025)
        if position:
            # Check tags for CFD
            tags = position.get('tags', [])
            for tag in tags:
                if 'cfd' in tag.lower() or 'contract_for_difference' in tag.lower():
                    is_cfd = True
                    leverage = 5.0  # Default CFD leverage
                    logger.info(f"CFD detected via tags: {symbol}")
                    break

            # Check instrument_type
            instrument_type = position.get('instrument_type', '').lower()
            if 'cfd' in instrument_type:
                is_cfd = True
                leverage = 5.0
                logger.info(f"CFD detected via instrument_type: {symbol}")

            # Check asset_class
            if asset_class and 'cfd' in asset_class.lower():
                is_cfd = True
                leverage = 5.0
                logger.info(f"CFD detected via asset_class: {symbol}")

        # Check symbol for CFD indicators
        symbol_upper = symbol.upper()
        if 'CFD' in symbol_upper or symbol_upper.endswith(':CFD'):
            is_cfd = True
            leverage = 5.0
            logger.info(f"CFD detected via symbol: {symbol}")

        # Detect leveraged ETFs (TQQQ = 3x leverage)
        if symbol_upper in ['TQQQ', 'SQQQ', 'UPRO', 'SPXL']:
            is_cfd = True
            leverage = 3.0
            logger.info(f"Leveraged ETF detected: {symbol} (3x)")

        # Asset type detection (unchanged)
        asset_type = 'equity'  # Default

        if symbol_upper in ['QQQ', 'TQQQ', 'XLK', 'VGT', 'SOXX']:
            asset_type = 'etf_tech'
        elif symbol_upper in ['SPY', 'IVV', 'VOO', 'VTI', 'ACWI', 'WORLD']:
            asset_type = 'etf_growth'
        elif symbol_upper in ['GLD', 'IAU', 'XGDU', 'GOLD']:
            asset_type = 'gold'
        elif symbol_upper in ['TLT', 'AGG', 'AGGS', 'BND']:
            asset_type = 'bond'
        elif asset_class and 'stock' in asset_class.lower():
            asset_type = 'equity'

        return (asset_type, is_cfd, leverage)

    def _calculate_sector_weights(
        self,
        positions: List[Dict[str, Any]],
        sector_analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate current sector weights"""
        if not sector_analysis or 'sectors' not in sector_analysis:
            return {}

        total_value = sum(pos.get('market_value', 0) or 0 for pos in positions)
        if total_value == 0:
            return {}

        sector_weights = {}
        sectors = sector_analysis.get('sectors', {})

        # sectors is a dict {sector_name: {metrics}}
        for sector_name, sector_data in sectors.items():
            weight = sector_data.get('weight', 0)  # Already in percentage
            sector_weights[sector_name] = weight / 100.0

        return sector_weights

    async def _compute_sector_analysis(
        self,
        positions: List[Dict[str, Any]],
        lookback_days: int
    ) -> Dict[str, Any]:
        """
        Compute sector analysis directly from positions

        Returns:
            Dict with sector rotation analysis
        """
        try:
            data_fetcher = BourseDataFetcher()
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=lookback_days + 30)

            positions_returns = {}
            positions_values = {}

            for pos in positions:
                symbol = pos.get('instrument_id', pos.get('symbol', pos.get('ticker')))
                if not symbol:
                    continue

                # Store position value
                value = pos.get('market_value', 0) or 0
                if value > 0:
                    positions_values[symbol] = float(value)

                # Fetch historical data
                try:
                    price_data = await data_fetcher.fetch_historical_prices(symbol, start_date, end_date)
                    if len(price_data) >= 30:
                        returns = price_data['close'].pct_change().dropna()
                        positions_returns[symbol] = returns
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")

            if len(positions_returns) < 2:
                logger.warning("Not enough positions with data for sector analysis")
                return {}

            # Compute sector rotation using existing service
            analytics = SpecializedBourseAnalytics()
            result = analytics.detect_sector_rotation(
                positions_returns=positions_returns,
                lookback_days=lookback_days,
                positions_values=positions_values
            )

            # Add symbol_to_sector mapping for easier lookup
            symbol_to_sector = {}
            for symbol in positions_returns.keys():
                symbol_to_sector[symbol] = analytics.sector_map.get(symbol, 'Unknown')

            result['symbol_to_sector'] = symbol_to_sector

            return result

        except Exception as e:
            logger.error(f"Error computing sector analysis: {e}")
            return {}

    def _get_sector_info(
        self,
        symbol: str,
        sector_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get sector info for a symbol from sector analysis"""
        if not sector_analysis or 'sectors' not in sector_analysis:
            return None

        # Find which sector this symbol belongs to
        sectors = sector_analysis.get('sectors', {})  # Dict, not list!
        symbol_to_sector = sector_analysis.get('symbol_to_sector', {})

        # Try to find the sector for this symbol
        sector_name = symbol_to_sector.get(symbol)

        if sector_name and sector_name in sectors:
            # Get sector data directly from dict
            sector_data = sectors[sector_name]
            return {
                'sector': sector_name,
                'momentum': sector_data.get('momentum', 1.0),
                'weight': sector_data.get('weight', 0) / 100.0,  # weight is already in %
                'target_weight': 0.20  # Default target
            }

        return None
