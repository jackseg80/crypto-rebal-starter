"""
Sector Analyzer for Market Opportunities System

Analyzes sectors using 3-pillar approach:
- Momentum (40%): Price momentum, RSI, relative strength vs SPY
- Value (30%): P/E ratio, PEG ratio, dividend yield
- Diversification (30%): Correlation with existing portfolio

Author: Crypto Rebalancer Team
Date: October 2025
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from services.ml.bourse.data_sources import StocksDataSource
from services.ml.bourse.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


# Static mapping of top blue-chip stocks per sector (S&P 500)
# Format: {ETF_ticker: [(symbol, company_name, rationale), ...]}
SECTOR_TOP_STOCKS = {
    # Technology
    "XLK": [
        ("AAPL", "Apple Inc.", "Leading tech hardware & services company"),
        ("MSFT", "Microsoft Corp.", "Cloud computing & software leader"),
        ("NVDA", "NVIDIA Corp.", "AI & GPU semiconductor leader"),
        ("AVGO", "Broadcom Inc.", "Diversified semiconductor & infrastructure")
    ],
    # Healthcare
    "XLV": [
        ("UNH", "UnitedHealth Group", "Healthcare insurance & services leader"),
        ("JNJ", "Johnson & Johnson", "Diversified healthcare & pharmaceuticals"),
        ("LLY", "Eli Lilly", "Pharmaceutical innovation leader"),
        ("ABBV", "AbbVie Inc.", "Biopharmaceutical research & development")
    ],
    # Financials
    "XLF": [
        ("JPM", "JPMorgan Chase", "Leading global investment bank"),
        ("BAC", "Bank of America", "Diversified financial services"),
        ("WFC", "Wells Fargo", "Consumer & commercial banking"),
        ("GS", "Goldman Sachs", "Investment banking & asset management")
    ],
    # Consumer Discretionary
    "XLY": [
        ("AMZN", "Amazon.com", "E-commerce & cloud services leader"),
        ("TSLA", "Tesla Inc.", "Electric vehicles & clean energy"),
        ("HD", "Home Depot", "Home improvement retail leader"),
        ("MCD", "McDonald's", "Global quick-service restaurant chain")
    ],
    # Communication Services
    "XLC": [
        ("META", "Meta Platforms", "Social media & metaverse leader"),
        ("GOOGL", "Alphabet Inc.", "Search, advertising & cloud services"),
        ("NFLX", "Netflix Inc.", "Streaming entertainment leader"),
        ("DIS", "Walt Disney", "Entertainment & media conglomerate")
    ],
    # Industrials
    "XLI": [
        ("HON", "Honeywell", "Diversified industrial & aerospace"),
        ("UNP", "Union Pacific", "Leading railroad transportation"),
        ("CAT", "Caterpillar", "Construction & mining equipment"),
        ("BA", "Boeing", "Aerospace & defense manufacturer")
    ],
    # Consumer Staples
    "XLP": [
        ("PG", "Procter & Gamble", "Consumer goods & household products"),
        ("KO", "Coca-Cola", "Global beverage leader"),
        ("PEP", "PepsiCo", "Food & beverage conglomerate"),
        ("WMT", "Walmart", "Retail & e-commerce leader")
    ],
    # Energy
    "XLE": [
        ("XOM", "Exxon Mobil", "Integrated oil & gas major"),
        ("CVX", "Chevron", "Global energy & chemicals"),
        ("COP", "ConocoPhillips", "Exploration & production leader"),
        ("SLB", "Schlumberger", "Oilfield services & technology")
    ],
    # Utilities
    "XLU": [
        ("NEE", "NextEra Energy", "Renewable energy & utilities leader"),
        ("DUK", "Duke Energy", "Electric utilities & infrastructure"),
        ("SO", "Southern Company", "Electric & gas utility services"),
        ("D", "Dominion Energy", "Diversified energy infrastructure")
    ],
    # Real Estate
    "XLRE": [
        ("AMT", "American Tower", "Cell tower & infrastructure REITs"),
        ("PLD", "Prologis", "Logistics real estate leader"),
        ("CCI", "Crown Castle", "Wireless infrastructure provider"),
        ("EQIX", "Equinix", "Data center REITs leader")
    ],
    # Materials
    "XLB": [
        ("LIN", "Linde plc", "Industrial gases & engineering"),
        ("APD", "Air Products", "Industrial gases & chemicals"),
        ("SHW", "Sherwin-Williams", "Paint & coatings leader"),
        ("ECL", "Ecolab", "Water treatment & hygiene services")
    ]
}


class SectorAnalyzer:
    """
    Analyzes sector performance and identifies best opportunities.

    Uses Yahoo Finance (free) to fetch:
    - Price data (OHLCV)
    - Fundamental data (P/E, PEG, etc.)
    - ETF and constituent stocks
    """

    def __init__(self):
        """Initialize analyzer with data source"""
        self.data_source = StocksDataSource()
        self.tech_indicators = TechnicalIndicators()

    async def analyze_individual_stock(
        self,
        symbol: str,
        horizon: str = "medium",
        benchmark: str = "SPY"
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an individual stock (similar to analyze_sector but for stocks).

        Args:
            symbol: Stock ticker (e.g., "AAPL", "JPM")
            horizon: Time horizon (short/medium/long)
            benchmark: Benchmark ticker (default SPY)

        Returns:
            Dict with momentum, value, diversification scores
        """
        try:
            logger.info(f"📈 Analyzing individual stock: {symbol} (horizon: {horizon})")

            # Get lookback days based on horizon
            lookback_days = self._get_lookback_days(horizon)

            # Fetch stock data
            stock_data = await self.data_source.get_ohlcv_data(
                symbol=symbol,
                lookback_days=lookback_days
            )

            if stock_data is None or stock_data.empty:
                logger.warning(f"No data available for {symbol}")
                return None

            # Fetch benchmark data
            benchmark_data = await self.data_source.get_ohlcv_data(
                symbol=benchmark,
                lookback_days=lookback_days
            )

            # Calculate scores (reuse existing methods)
            momentum_score = self._calculate_momentum_score(
                stock_data, benchmark_data, horizon
            )
            value_score = await self._calculate_value_score(symbol)
            diversification_score = self._calculate_diversification_score(stock_data)

            # Data quality confidence
            confidence = min(len(stock_data) / lookback_days, 1.0)

            # Calculate composite score (40% momentum, 30% value, 30% diversification)
            composite_score = (
                momentum_score * 0.40 +
                value_score * 0.30 +
                diversification_score * 0.30
            )

            return {
                "symbol": symbol,
                "momentum_score": round(momentum_score, 1),
                "value_score": round(value_score, 1),
                "diversification_score": round(diversification_score, 1),
                "composite_score": round(composite_score, 1),
                "confidence": round(confidence, 2),
                "data_points": len(stock_data),
                "analysis_date": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}", exc_info=True)
            return None

    async def analyze_sector(
        self,
        sector_etf: str,
        horizon: str = "medium",
        benchmark: str = "SPY"
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a sector using its representative ETF.

        Args:
            sector_etf: Sector ETF ticker (e.g., "XLK", "XLF")
            horizon: Time horizon (short/medium/long)
            benchmark: Benchmark ticker (default SPY)

        Returns:
            Dict with momentum, value, diversification scores
        """
        try:
            logger.info(f"📊 Analyzing sector ETF: {sector_etf} (horizon: {horizon})")

            # Get lookback days based on horizon
            lookback_days = self._get_lookback_days(horizon)

            # Fetch ETF data
            etf_data = await self.data_source.get_ohlcv_data(
                symbol=sector_etf,
                lookback_days=lookback_days
            )

            if etf_data is None or etf_data.empty:
                logger.warning(f"No data available for {sector_etf}")
                return None

            # Fetch benchmark data
            benchmark_data = await self.data_source.get_ohlcv_data(
                symbol=benchmark,
                lookback_days=lookback_days
            )

            # Calculate scores
            momentum_score = self._calculate_momentum_score(
                etf_data, benchmark_data, horizon
            )
            value_score = await self._calculate_value_score(sector_etf)
            diversification_score = self._calculate_diversification_score(etf_data)

            # Data quality confidence
            confidence = min(len(etf_data) / lookback_days, 1.0)

            return {
                "etf": sector_etf,
                "momentum_score": momentum_score,
                "value_score": value_score,
                "diversification_score": diversification_score,
                "confidence": confidence,
                "data_points": len(etf_data),
                "analysis_date": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing sector {sector_etf}: {e}", exc_info=True)
            return None

    def _get_lookback_days(self, horizon: str) -> int:
        """Get lookback days based on horizon"""
        lookback_map = {
            "short": 90,    # 1-3 months
            "medium": 180,  # 6 months
            "long": 365     # 1 year
        }
        return lookback_map.get(horizon, 180)

    def _calculate_momentum_score(
        self,
        etf_data: pd.DataFrame,
        benchmark_data: Optional[pd.DataFrame],
        horizon: str
    ) -> float:
        """
        Calculate momentum score (0-100).

        Components:
        - Price momentum (3M, 6M)
        - RSI (Relative Strength Index)
        - Relative strength vs benchmark

        Args:
            etf_data: ETF OHLCV data
            benchmark_data: Benchmark OHLCV data
            horizon: Time horizon

        Returns:
            Momentum score (0-100)
        """
        try:
            if etf_data.empty:
                return 50.0

            scores = []

            # 1. Price momentum (simple return)
            if len(etf_data) >= 20:
                periods = {"short": 20, "medium": 60, "long": 90}
                period = periods.get(horizon, 60)
                period = min(period, len(etf_data))

                price_return = (
                    (etf_data['close'].iloc[-1] / etf_data['close'].iloc[-period] - 1) * 100
                )

                # Normalize to 0-100 (assume ±30% is max/min)
                momentum_pct = np.clip(50 + price_return * (50/30), 0, 100)
                scores.append(momentum_pct)

            # 2. RSI (14-day)
            if len(etf_data) >= 14:
                rsi_series = self.tech_indicators.calculate_rsi(etf_data['close'], period=14)
                # Extract last value from Series
                if isinstance(rsi_series, pd.Series) and len(rsi_series) > 0:
                    rsi = rsi_series.iloc[-1]
                else:
                    rsi = rsi_series

                if not pd.isna(rsi) and not np.isnan(rsi):
                    # RSI 30-70 is neutral, <30 oversold (opportunity), >70 overbought
                    # Convert to score: 30 → 100, 50 → 50, 70 → 0
                    if rsi < 50:
                        rsi_score = 50 + (50 - rsi) * (50/20)  # 30 → 100, 50 → 50
                    else:
                        rsi_score = 50 - (rsi - 50) * (50/20)  # 50 → 50, 70 → 0
                    rsi_score = np.clip(rsi_score, 0, 100)
                    scores.append(rsi_score)

            # 3. Relative strength vs benchmark
            if benchmark_data is not None and not benchmark_data.empty:
                min_len = min(len(etf_data), len(benchmark_data))
                if min_len >= 20:
                    etf_return = (
                        etf_data['close'].iloc[-1] / etf_data['close'].iloc[-min_len] - 1
                    ) * 100
                    bench_return = (
                        benchmark_data['close'].iloc[-1] / benchmark_data['close'].iloc[-min_len] - 1
                    ) * 100

                    relative_strength = etf_return - bench_return

                    # Normalize: ±15% outperformance is max/min
                    rs_score = np.clip(50 + relative_strength * (50/15), 0, 100)
                    scores.append(rs_score)

            # Average scores
            if scores:
                return round(np.mean(scores), 1)
            else:
                return 50.0

        except Exception as e:
            logger.error(f"Error calculating momentum score: {e}", exc_info=True)
            return 50.0

    async def _calculate_value_score(self, sector_etf: str) -> float:
        """
        Calculate value score (0-100).

        Components:
        - P/E ratio (vs market average)
        - PEG ratio (if available)
        - Dividend yield

        Note: Yahoo Finance API limits - use simple heuristics if data unavailable

        Args:
            sector_etf: Sector ETF ticker

        Returns:
            Value score (0-100)
        """
        try:
            # Try to fetch fundamental data from yfinance
            import yfinance as yf

            ticker = yf.Ticker(sector_etf)
            info = ticker.info

            scores = []

            # 1. P/E Ratio (market avg ≈ 20)
            pe_ratio = info.get('trailingPE') or info.get('forwardPE')
            if pe_ratio and pe_ratio > 0:
                # Lower P/E = better value
                # Assume 10 (undervalued) → 100, 20 (fair) → 50, 40+ (overvalued) → 0
                if pe_ratio <= 20:
                    pe_score = 50 + (20 - pe_ratio) * (50/10)
                else:
                    pe_score = 50 - (pe_ratio - 20) * (50/20)
                pe_score = np.clip(pe_score, 0, 100)
                scores.append(pe_score)

            # 2. PEG Ratio (if available)
            peg_ratio = info.get('pegRatio')
            if peg_ratio and peg_ratio > 0:
                # PEG < 1 = undervalued, 1-2 = fair, >2 = overvalued
                if peg_ratio <= 1:
                    peg_score = 100
                elif peg_ratio <= 2:
                    peg_score = 100 - (peg_ratio - 1) * 50
                else:
                    peg_score = 50 - min((peg_ratio - 2) * 25, 50)
                peg_score = np.clip(peg_score, 0, 100)
                scores.append(peg_score)

            # 3. Dividend Yield
            div_yield = info.get('dividendYield')
            if div_yield and div_yield > 0:
                # Convert to percentage
                div_pct = div_yield * 100
                # Assume 0% → 0, 2% → 50, 4%+ → 100
                div_score = np.clip(div_pct * 25, 0, 100)
                scores.append(div_score)

            # Average scores or default to 50
            if scores:
                return round(np.mean(scores), 1)
            else:
                # No fundamental data available, return neutral
                return 50.0

        except Exception as e:
            logger.error(f"Error calculating value score for {sector_etf}: {e}", exc_info=True)
            return 50.0

    def _calculate_diversification_score(self, etf_data: pd.DataFrame) -> float:
        """
        Calculate diversification score (0-100).

        Higher score = better diversification (lower correlation with existing assets).

        Note: This is a placeholder. In production, would calculate correlation
        with existing portfolio assets. For now, use volatility as proxy:
        - Higher volatility = lower diversification score
        - Lower volatility = higher diversification score

        Args:
            etf_data: ETF OHLCV data

        Returns:
            Diversification score (0-100)
        """
        try:
            if etf_data.empty or len(etf_data) < 20:
                return 50.0

            # Calculate daily returns
            returns = etf_data['close'].pct_change().dropna()

            if len(returns) < 10:
                return 50.0

            # Calculate annualized volatility
            volatility = returns.std() * np.sqrt(252)

            # Normalize: assume 15% vol = neutral (50), 10% = high score (80), 25% = low score (20)
            # Lower vol → better diversification benefit (assuming portfolio is tech-heavy)
            if volatility <= 0.15:
                score = 50 + (0.15 - volatility) * (30 / 0.05)  # 10% → 80
            else:
                score = 50 - (volatility - 0.15) * (30 / 0.10)  # 25% → 20

            score = np.clip(score, 0, 100)

            return round(score, 1)

        except Exception as e:
            logger.error(f"Error calculating diversification score: {e}", exc_info=True)
            return 50.0

    async def get_top_stocks_in_sector(
        self,
        sector_etf: str,
        top_n: int = 3,
        horizon: str = "medium",
        score_individually: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get top N stocks in a sector plus the sector ETF.

        Returns ETF + top blue-chip stocks from SECTOR_TOP_STOCKS mapping,
        optionally with individual scores for each stock.

        Args:
            sector_etf: Sector ETF ticker (e.g., "XLK", "XLF")
            top_n: Number of individual stocks to return (default 3)
            horizon: Time horizon for scoring (default "medium")
            score_individually: If True, score each stock separately (default True)

        Returns:
            List of recommendations: [ETF, Stock1, Stock2, Stock3] with scores
        """
        try:
            recommendations = []

            # 1. Always include the sector ETF first (diversified exposure)
            recommendations.append({
                "symbol": sector_etf,
                "type": "ETF",
                "name": f"Sector ETF {sector_etf}",
                "weight": 100.0,  # Will be normalized later
                "rationale": f"Diversified exposure to sector via {sector_etf} ETF"
            })

            # 2. Add top N individual stocks from static mapping
            if sector_etf in SECTOR_TOP_STOCKS:
                stocks = SECTOR_TOP_STOCKS[sector_etf][:top_n]  # Limit to top_n

                if score_individually:
                    # Score each stock in parallel for performance
                    import asyncio
                    stock_symbols = [symbol for symbol, _, _ in stocks]

                    # Fetch scores in parallel using asyncio.gather
                    score_tasks = [
                        self.analyze_individual_stock(symbol, horizon=horizon)
                        for symbol in stock_symbols
                    ]
                    scores_results = await asyncio.gather(*score_tasks, return_exceptions=True)

                    # Combine stocks with their scores
                    for (symbol, name, rationale), score_result in zip(stocks, scores_results):
                        if isinstance(score_result, Exception):
                            logger.warning(f"Failed to score {symbol}: {score_result}")
                            # Fallback to no score
                            recommendations.append({
                                "symbol": symbol,
                                "type": "Stock",
                                "name": name,
                                "weight": 80.0,
                                "rationale": rationale
                            })
                        elif score_result is None:
                            # No data available
                            recommendations.append({
                                "symbol": symbol,
                                "type": "Stock",
                                "name": name,
                                "weight": 80.0,
                                "rationale": rationale
                            })
                        else:
                            # Add score data
                            recommendations.append({
                                "symbol": symbol,
                                "type": "Stock",
                                "name": name,
                                "weight": score_result.get("composite_score", 80.0),
                                "rationale": rationale,
                                "momentum_score": score_result.get("momentum_score"),
                                "value_score": score_result.get("value_score"),
                                "diversification_score": score_result.get("diversification_score"),
                                "composite_score": score_result.get("composite_score"),
                                "confidence": score_result.get("confidence")
                            })
                else:
                    # No individual scoring - just return static data
                    for symbol, name, rationale in stocks:
                        recommendations.append({
                            "symbol": symbol,
                            "type": "Stock",
                            "name": name,
                            "weight": 80.0,
                            "rationale": rationale
                        })

                logger.info(f"✅ Found {len(stocks)} stocks for {sector_etf}")
            else:
                logger.warning(f"⚠️ No stocks mapped for {sector_etf}, returning ETF only")

            return recommendations

        except Exception as e:
            logger.error(f"Error getting top stocks for {sector_etf}: {e}", exc_info=True)
            # Fallback: return ETF only
            return [{
                "symbol": sector_etf,
                "type": "ETF",
                "name": f"Sector ETF {sector_etf}",
                "weight": 100.0,
                "rationale": f"Diversified exposure to sector via {sector_etf} ETF"
            }]
