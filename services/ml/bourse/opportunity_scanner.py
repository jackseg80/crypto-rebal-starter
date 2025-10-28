"""
Opportunity Scanner for Market Opportunities System

Scans S&P 500 sectors vs current portfolio to detect gaps and opportunities.
Scores each gap using 3-pillar approach: Momentum 40%, Value 30%, Diversification 30%.

Author: Crypto Rebalancer Team
Date: October 2025
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from services.ml.bourse.sector_analyzer import SectorAnalyzer

logger = logging.getLogger(__name__)


# GICS Level 1 Sectors (11 Standard S&P 500 Sectors)
STANDARD_SECTORS = {
    "Technology": {
        "target_range": (15, 30),
        "etf": "XLK",
        "description": "Information Technology"
    },
    "Healthcare": {
        "target_range": (10, 18),
        "etf": "XLV",
        "description": "Healthcare"
    },
    "Financials": {
        "target_range": (10, 18),
        "etf": "XLF",
        "description": "Financial Services"
    },
    "Consumer Discretionary": {
        "target_range": (8, 15),
        "etf": "XLY",
        "description": "Consumer Cyclical"
    },
    "Communication Services": {
        "target_range": (8, 15),
        "etf": "XLC",
        "description": "Communication Services"
    },
    "Industrials": {
        "target_range": (8, 15),
        "etf": "XLI",
        "description": "Industrials"
    },
    "Consumer Staples": {
        "target_range": (5, 12),
        "etf": "XLP",
        "description": "Consumer Defensive"
    },
    "Energy": {
        "target_range": (3, 10),
        "etf": "XLE",
        "description": "Energy"
    },
    "Utilities": {
        "target_range": (2, 8),
        "etf": "XLU",
        "description": "Utilities"
    },
    "Real Estate": {
        "target_range": (2, 8),
        "etf": "XLRE",
        "description": "Real Estate"
    },
    "Materials": {
        "target_range": (2, 8),
        "etf": "XLB",
        "description": "Materials"
    }
}


# Sector mapping (Yahoo Finance → GICS)
SECTOR_MAPPING = {
    # Technology
    "Technology": "Technology",
    "Information Technology": "Technology",
    "Software": "Technology",
    "Hardware": "Technology",
    "Semiconductors": "Technology",

    # Healthcare
    "Healthcare": "Healthcare",
    "Biotechnology": "Healthcare",
    "Medical Devices": "Healthcare",
    "Pharmaceuticals": "Healthcare",

    # Financials
    "Financial Services": "Financials",
    "Financials": "Financials",
    "Banks": "Financials",
    "Insurance": "Financials",
    "Capital Markets": "Financials",

    # Consumer Discretionary
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Discretionary": "Consumer Discretionary",
    "Retail": "Consumer Discretionary",
    "Automotive": "Consumer Discretionary",

    # Communication Services
    "Communication Services": "Communication Services",
    "Telecommunications": "Communication Services",
    "Media": "Communication Services",
    "Entertainment": "Communication Services",

    # Industrials
    "Industrials": "Industrials",
    "Aerospace & Defense": "Industrials",
    "Construction": "Industrials",
    "Machinery": "Industrials",

    # Consumer Staples
    "Consumer Defensive": "Consumer Staples",
    "Consumer Staples": "Consumer Staples",
    "Food & Beverage": "Consumer Staples",
    "Household Products": "Consumer Staples",

    # Energy
    "Energy": "Energy",
    "Oil & Gas": "Energy",
    "Renewable Energy": "Energy",

    # Utilities
    "Utilities": "Utilities",
    "Electric Utilities": "Utilities",
    "Water Utilities": "Utilities",

    # Real Estate
    "Real Estate": "Real Estate",
    "REITs": "Real Estate",
    "Real Estate Services": "Real Estate",

    # Materials
    "Basic Materials": "Materials",
    "Materials": "Materials",
    "Chemicals": "Materials",
    "Metals & Mining": "Materials"
}


# ETF Sector Mapping (Yahoo Finance doesn't return sector for ETFs)
# Maps base symbol (without exchange suffix) → sector classification
ETF_SECTOR_MAPPING = {
    # Diversified World ETFs
    "IWDA": "Diversified",      # iShares Core MSCI World UCITS ETF
    "ACWI": "Diversified",      # iShares MSCI ACWI ETF
    "WORLD": "Diversified",     # UBS MSCI World UCITS ETF

    # Sector-Specific ETFs
    "ITEK": "Technology",       # HAN-GINS Tech Megatrend Equal Weight UCITS ETF
    "BTEC": "Healthcare",       # iShares NASDAQ US Biotechnology UCITS ETF

    # Alternative Assets
    "AGGS": "Fixed Income",     # iShares Core Global Aggregate Bond UCITS ETF
    "XGDU": "Commodities",      # Xtrackers IE Physical Gold ETC
}


class OpportunityScanner:
    """
    Scans portfolio for sector gaps and scoring opportunities.

    Methodology:
    - Compare current sector allocation vs S&P 500 standard sectors
    - Detect gaps (0% or underweight sectors)
    - Score each gap: Momentum 40% + Value 30% + Diversification 30%
    """

    def __init__(self):
        """Initialize scanner with sector analyzer"""
        self.sector_analyzer = SectorAnalyzer()

    async def scan_opportunities(
        self,
        positions: List[Dict[str, Any]],
        horizon: str = "medium",
        min_gap_pct: float = 5.0
    ) -> Dict[str, Any]:
        """
        Scan portfolio for sector gaps and opportunities.

        Args:
            positions: List of portfolio positions with sector info
            horizon: Time horizon (short/medium/long)
            min_gap_pct: Minimum gap percentage to consider (default 5%)

        Returns:
            Dict with gaps, scored opportunities, and recommendations
        """
        try:
            logger.info(f"🔍 Scanning opportunities for {len(positions)} positions (horizon: {horizon})")

            # 1. Extract current sector allocation
            current_allocation = self._extract_sector_allocation(positions)
            logger.debug(f"Current allocation: {current_allocation}")

            # 2. Detect gaps vs standard sectors
            gaps = self._detect_gaps(current_allocation, min_gap_pct)
            logger.info(f"Detected {len(gaps)} sector gaps")

            # 3. Score each gap
            scored_gaps = []
            for gap in gaps:
                score = await self._score_gap(gap, horizon)
                scored_gaps.append({**gap, **score})

            # Sort by score (descending)
            scored_gaps.sort(key=lambda x: x.get("score", 0), reverse=True)

            # 4. Get top opportunities (top 5 gaps)
            top_gaps = scored_gaps[:5]

            logger.info(f"✅ Scan complete: {len(scored_gaps)} gaps scored, top {len(top_gaps)} selected")

            return {
                "all_gaps": scored_gaps,
                "top_gaps": top_gaps,
                "current_allocation": current_allocation,
                "scan_time": datetime.now().isoformat(),
                "horizon": horizon
            }

        except Exception as e:
            logger.error(f"❌ Error scanning opportunities: {e}", exc_info=True)
            raise

    def _enrich_position_with_sector(self, symbol: str) -> str:
        """
        Enrich position with sector from Yahoo Finance.
        Handles European stock symbols from Saxo Bank format (SYMBOL:xexchange).

        Args:
            symbol: Stock ticker (may be in Saxo format like "SLHn:xvtx")

        Returns:
            Sector name or "Unknown"
        """
        # Mapping Saxo exchange codes → Yahoo Finance suffixes
        SAXO_TO_YAHOO_EXCHANGE = {
            'xvtx': '.SW',   # Swiss (Zurich)
            'xswx': '.SW',   # Swiss (SIX)
            'xetr': '.DE',   # German (Xetra)
            'xwar': '.WA',   # Poland (Warsaw)
            'xpar': '.PA',   # France (Paris)
            'xams': '.AS',   # Netherlands (Amsterdam)
            'xmil': '.MI',   # Italy (Milan)
            'xmli': '.MI',   # Italy (Milan ETF)
            'xlon': '.L',    # UK (London)
            'xnas': '',      # US (NASDAQ - no suffix)
            'xnys': '',      # US (NYSE - no suffix)
        }

        try:
            import yfinance as yf

            # Parse Saxo format: "SYMBOL:xexchange" → (SYMBOL, xexchange)
            yahoo_symbol = symbol
            base_symbol = symbol.split(':')[0].upper() if ':' in symbol else symbol.upper()

            # Check ETF mapping FIRST (Yahoo Finance doesn't return sectors for ETFs)
            if base_symbol in ETF_SECTOR_MAPPING:
                sector = ETF_SECTOR_MAPPING[base_symbol]
                logger.info(f"🏦 {symbol} → {sector} (ETF mapping)")
                return sector

            if ':' in symbol:
                base_symbol, exchange = symbol.split(':', 1)
                exchange = exchange.lower()

                # Clean symbol (SLHn → SLHN, etc.)
                base_symbol = base_symbol.upper()

                # Special symbol mappings (Yahoo Finance exceptions)
                SYMBOL_EXCEPTIONS = {
                    'BRKB': 'BRK-B',  # Berkshire Hathaway Class B
                    'BRKA': 'BRK-A',  # Berkshire Hathaway Class A
                }
                base_symbol = SYMBOL_EXCEPTIONS.get(base_symbol, base_symbol)

                # Get Yahoo Finance suffix
                if exchange in SAXO_TO_YAHOO_EXCHANGE:
                    suffix = SAXO_TO_YAHOO_EXCHANGE[exchange]
                    yahoo_symbol = f"{base_symbol}{suffix}"
                    logger.info(f"🔄 Saxo '{symbol}' → Yahoo '{yahoo_symbol}'")
                else:
                    logger.info(f"⚠️ Unknown exchange '{exchange}' for {symbol}, trying as-is")

            # Try fetching with converted symbol
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info

            # Try different sector fields
            sector = info.get('sector') or info.get('sectorKey') or info.get('industry')

            if sector:
                logger.info(f"📍 {symbol} → {sector}")
                return sector
            else:
                logger.info(f"❓ {yahoo_symbol} → No sector found in Yahoo Finance")
                return "Unknown"

        except Exception as e:
            logger.info(f"❌ {symbol} → Error fetching sector: {e}")
            return "Unknown"

    def _extract_sector_allocation(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Extract sector allocation from portfolio positions.
        Automatically enriches positions with sectors from Yahoo Finance if missing.

        Args:
            positions: List of positions with sector info

        Returns:
            Dict mapping sector → allocation percentage
        """
        try:
            # Calculate total portfolio value
            # Note: Saxo positions use "market_value" field (already in USD)
            total_value = sum(p.get("market_value", 0) or p.get("market_value_usd", 0) for p in positions)

            if total_value == 0:
                logger.warning("Total portfolio value is 0")
                return {}

            # Group by sector
            sector_values = {}
            for pos in positions:
                # Try to get existing sector, otherwise enrich from Yahoo Finance
                sector_raw = pos.get("sector")

                if not sector_raw or sector_raw == "Unknown":
                    # Support both "symbol" and "instrument_id" field names
                    symbol = pos.get("symbol") or pos.get("instrument_id")
                    if symbol:
                        sector_raw = self._enrich_position_with_sector(symbol)
                        # Cache it in the position for future use
                        pos["sector"] = sector_raw

                # Map to GICS sector
                sector = SECTOR_MAPPING.get(sector_raw, sector_raw)

                # Skip if not a standard sector
                if sector not in STANDARD_SECTORS and sector != "Unknown":
                    # Try fuzzy match
                    matched = False
                    for key in SECTOR_MAPPING.keys():
                        if key.lower() in sector_raw.lower():
                            sector = SECTOR_MAPPING[key]
                            matched = True
                            break
                    if not matched:
                        sector = "Other"

                # Use "market_value" field (already in USD for Saxo positions)
                value = pos.get("market_value", 0) or pos.get("market_value_usd", 0)
                sector_values[sector] = sector_values.get(sector, 0) + value

            # Convert to percentages
            allocation = {
                sector: (value / total_value) * 100
                for sector, value in sector_values.items()
            }

            return allocation

        except Exception as e:
            logger.error(f"Error extracting sector allocation: {e}", exc_info=True)
            return {}

    def _detect_gaps(
        self,
        current_allocation: Dict[str, float],
        min_gap_pct: float
    ) -> List[Dict[str, Any]]:
        """
        Detect sector gaps (missing or underweight sectors).

        Args:
            current_allocation: Current sector allocation
            min_gap_pct: Minimum gap to consider

        Returns:
            List of gaps with sector info
        """
        gaps = []

        for sector, info in STANDARD_SECTORS.items():
            current = current_allocation.get(sector, 0.0)
            target_min, target_max = info["target_range"]
            target = (target_min + target_max) / 2  # Midpoint

            gap_pct = target - current

            # Only consider gaps above threshold
            if gap_pct >= min_gap_pct:
                gaps.append({
                    "sector": sector,
                    "current_pct": round(current, 2),
                    "target_pct": round(target, 2),
                    "gap_pct": round(gap_pct, 2),
                    "etf": info["etf"],
                    "description": info["description"]
                })

        return gaps

    async def _score_gap(
        self,
        gap: Dict[str, Any],
        horizon: str
    ) -> Dict[str, Any]:
        """
        Score a sector gap using 3-pillar approach.

        Pillars:
        - Momentum (40%): Price momentum, relative strength
        - Value (30%): Valuation metrics
        - Diversification (30%): Correlation with existing portfolio

        Args:
            gap: Gap info (sector, gap_pct, etc.)
            horizon: Time horizon

        Returns:
            Dict with score breakdown
        """
        try:
            sector = gap["sector"]
            etf = gap["etf"]

            # Analyze sector ETF to get metrics
            analysis = await self.sector_analyzer.analyze_sector(etf, horizon)

            if not analysis:
                logger.warning(f"No analysis available for {sector} ({etf})")
                return {
                    "momentum_score": 50,
                    "value_score": 50,
                    "diversification_score": 50,
                    "score": 50,
                    "confidence": 0.3
                }

            # Extract scores
            momentum_score = analysis.get("momentum_score", 50)
            value_score = analysis.get("value_score", 50)
            diversification_score = analysis.get("diversification_score", 50)

            # Weighted average (Momentum 40%, Value 30%, Diversification 30%)
            score = (
                momentum_score * 0.40 +
                value_score * 0.30 +
                diversification_score * 0.30
            )

            # Confidence based on data quality
            confidence = analysis.get("confidence", 0.7)

            return {
                "momentum_score": round(momentum_score, 1),
                "value_score": round(value_score, 1),
                "diversification_score": round(diversification_score, 1),
                "score": round(score, 1),
                "confidence": round(confidence, 2),
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"Error scoring gap {gap}: {e}", exc_info=True)
            # Return neutral scores on error
            return {
                "momentum_score": 50,
                "value_score": 50,
                "diversification_score": 50,
                "score": 50,
                "confidence": 0.3
            }
