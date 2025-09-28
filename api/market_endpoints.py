"""
API Endpoints pour les données de marché

Ces endpoints fournissent les données de prix et de marché nécessaires
pour l'analyse des phases de rotation et force relative.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta
import asyncio

# Stub implementation for missing data sources
class StubCoinGeckoClient:
    @staticmethod
    async def get_historical_prices(symbols, days):
        return {symbol: [{"timestamp": datetime.now(), "price": 45000.0 + i * 100}] for i, symbol in enumerate(symbols)}

class StubCryptoToolboxClient:
    @staticmethod
    async def get_market_data(symbols):
        return {"status": "success", "data": []}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])

class MarketPricesResponse(BaseModel):
    """Réponse des prix de marché avec force relative"""
    prices: Dict[str, List[Dict[str, Any]]] = Field(description="Prix historiques par asset")
    relative_strength: Dict[str, float] = Field(description="Force relative calculée")
    meta: Dict[str, Any] = Field(description="Métadonnées")

@router.get("/prices", response_model=MarketPricesResponse)
async def get_market_prices(
    days: int = Query(30, description="Nombre de jours d'historique", le=90),
    symbols: Optional[str] = Query(None, description="Symboles séparés par virgule (par défaut: BTC,ETH,SOL,ADA,DOT)")
):
    """
    Récupérer les prix de marché et calculer la force relative

    Cette API fournit les données nécessaires pour l'analyse des phases
    de rotation crypto (BTC → ETH → Large → Alt).
    """
    try:
        # Symboles par défaut pour l'analyse de rotation
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
        else:
            symbol_list = ["BTC", "ETH", "SOL", "ADA", "DOT", "MATIC", "LINK", "UNI", "AVAX", "ATOM"]

        logger.info(f"Fetching market prices for {len(symbol_list)} symbols over {days} days")

        # Utiliser CoinGecko pour les données de prix (stub)
        coingecko = StubCoinGeckoClient()
        prices_data = {}

        # Mapping des symboles vers les IDs CoinGecko
        symbol_to_id = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "ADA": "cardano",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "AVAX": "avalanche-2",
            "ATOM": "cosmos"
        }

        # Récupérer les prix pour chaque actif
        for symbol in symbol_list:
            coin_id = symbol_to_id.get(symbol)
            if not coin_id:
                logger.warning(f"No CoinGecko ID mapping for symbol {symbol}")
                continue

            try:
                price_history = await coingecko.get_historical_prices(coin_id, days=days)
                if price_history:
                    prices_data[symbol] = price_history
            except Exception as e:
                logger.error(f"Failed to fetch prices for {symbol}: {e}")
                continue

        # Calculer la force relative
        relative_strength = _calculate_relative_strength(prices_data, days)

        response = MarketPricesResponse(
            prices=prices_data,
            relative_strength=relative_strength,
            meta={
                "symbols_requested": symbol_list,
                "symbols_available": list(prices_data.keys()),
                "days": days,
                "timestamp": datetime.now().isoformat(),
                "source": "coingecko"
            }
        )

        logger.info(f"Market prices returned for {len(prices_data)} symbols")
        return response

    except Exception as e:
        logger.error(f"Error fetching market prices: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market prices: {str(e)}")


def _calculate_relative_strength(prices_data: Dict[str, List], days: int) -> Dict[str, float]:
    """
    Calculer la force relative des actifs vs BTC

    Returns:
        Dict avec les ratios de force relative (>1 = surperformance, <1 = sous-performance)
    """
    try:
        if "BTC" not in prices_data or len(prices_data["BTC"]) < 2:
            logger.warning("BTC data not available for relative strength calculation")
            return {}

        btc_prices = prices_data["BTC"]
        btc_start = btc_prices[0]["price"] if btc_prices else 1
        btc_end = btc_prices[-1]["price"] if btc_prices else 1
        btc_return = (btc_end / btc_start) if btc_start > 0 else 0

        relative_strength = {}

        for symbol, price_history in prices_data.items():
            if symbol == "BTC" or len(price_history) < 2:
                continue

            try:
                start_price = price_history[0]["price"]
                end_price = price_history[-1]["price"]

                if start_price > 0:
                    asset_return = end_price / start_price
                    # Force relative = performance de l'actif / performance BTC
                    rs = asset_return / btc_return if btc_return > 0 else 1.0
                    relative_strength[f"{symbol.lower()}_btc_{days}d"] = round(rs, 4)

                    # Ajouter aussi les RS pour 7j si on a assez de données
                    if len(price_history) >= 7:
                        btc_7d_start = btc_prices[-7]["price"] if len(btc_prices) >= 7 else btc_start
                        btc_7d_return = (btc_end / btc_7d_start) if btc_7d_start > 0 else 0

                        asset_7d_start = price_history[-7]["price"]
                        asset_7d_return = end_price / asset_7d_start if asset_7d_start > 0 else 0

                        rs_7d = asset_7d_return / btc_7d_return if btc_7d_return > 0 else 1.0
                        relative_strength[f"{symbol.lower()}_btc_7d"] = round(rs_7d, 4)

            except Exception as e:
                logger.error(f"Error calculating relative strength for {symbol}: {e}")
                continue

        # Calculer quelques agrégations pour les groupes
        eth_rs = relative_strength.get("eth_btc_30d", 1.0)

        # Large caps (top 10-50): moyenne de SOL, ADA, DOT, MATIC, LINK
        large_caps = ["sol", "ada", "dot", "matic", "link"]
        large_rs_values = [relative_strength.get(f"{symbol}_btc_30d", 1.0) for symbol in large_caps
                          if f"{symbol}_btc_30d" in relative_strength]
        large_rs = sum(large_rs_values) / len(large_rs_values) if large_rs_values else 1.0

        # Altcoins: moyenne des autres
        alt_caps = ["uni", "avax", "atom"]
        alt_rs_values = [relative_strength.get(f"{symbol}_btc_30d", 1.0) for symbol in alt_caps
                        if f"{symbol}_btc_30d" in relative_strength]
        alt_rs = sum(alt_rs_values) / len(alt_rs_values) if alt_rs_values else 1.0

        # Ajouter les agrégations
        relative_strength.update({
            "eth_btc_30d": round(eth_rs, 4),
            "large_btc_30d": round(large_rs, 4),
            "alt_btc_30d": round(alt_rs, 4)
        })

        return relative_strength

    except Exception as e:
        logger.error(f"Error in relative strength calculation: {e}")
        return {}