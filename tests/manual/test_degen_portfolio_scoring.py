"""
Test du Risk Score avec le portfolio degen High_Risk_Contra.csv
"""

import asyncio
import pandas as pd
from services.portfolio_metrics import portfolio_metrics_service
from services.price_history import get_cached_history
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_degen_scoring():
    """
    Test avec portfolio degen (55% memecoins)
    """
    # Balances du fichier High_Risk_Contra.csv
    balances = [
        {"symbol": "BTC", "value_usd": 2100},
        {"symbol": "ETH", "value_usd": 600},
        {"symbol": "DOGE", "value_usd": 8000},   # Memecoin
        {"symbol": "SHIB", "value_usd": 14000},  # Memecoin
        {"symbol": "PEPE", "value_usd": 5000},   # Memecoin
        {"symbol": "SOL", "value_usd": 15000},
        {"symbol": "AVAX", "value_usd": 3200},
        {"symbol": "APT", "value_usd": 1200},
    ]

    total_value = sum(b['value_usd'] for b in balances)
    memes_value = 8000 + 14000 + 5000  # DOGE + SHIB + PEPE
    memes_pct = memes_value / total_value

    logger.info(f"📦 Portfolio Total: ${total_value:,.0f}")
    logger.info(f"🎭 Memecoins: ${memes_value:,.0f} ({memes_pct*100:.1f}%)")
    logger.info(f"   - DOGE: $8,000")
    logger.info(f"   - SHIB: $14,000")
    logger.info(f"   - PEPE: $5,000")

    # Récupérer price data
    price_data = {}
    price_history_days = 90

    for balance in balances:
        symbol = balance['symbol'].upper()
        try:
            prices = get_cached_history(symbol, days=price_history_days)
            if prices and len(prices) > 10:
                timestamps = [pd.Timestamp.fromtimestamp(p[0]) for p in prices]
                values = [p[1] for p in prices]
                price_data[symbol] = pd.Series(values, index=timestamps)
        except Exception as e:
            logger.warning(f"⚠️  Failed to get price data for {symbol}: {e}")

    if len(price_data) < 2:
        logger.error("❌ Insufficient price data")
        return

    price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()
    logger.info(f"📊 Price DataFrame: {len(price_df)} rows, {len(price_df.columns)} assets")

    # Calcul des métriques
    metrics = portfolio_metrics_service.calculate_portfolio_metrics(
        price_data=price_df,
        balances=balances,
        confidence_level=0.95
    )

    logger.info(f"\n🎯 RESULTATS :")
    logger.info(f"   Risk Score: {metrics.risk_score:.1f}/100")
    logger.info(f"   Risk Level: {metrics.overall_risk_level.upper()}")
    logger.info(f"   Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    logger.info(f"   Volatility: {metrics.volatility_annualized*100:.1f}%")
    logger.info(f"   Max Drawdown: {metrics.max_drawdown*100:.1f}%")

    # Analyse
    logger.info(f"\n📊 ANALYSE :")
    if metrics.risk_score >= 65:
        logger.info(f"   ❌ PROBLEME : Risk Score trop élevé pour un portfolio avec {memes_pct*100:.0f}% de memecoins !")
        logger.info(f"   Devrait être < 40/100 (high/very_high risk)")
    elif metrics.risk_score >= 50:
        logger.info(f"   ⚠️  Risk Score modéré mais devrait être plus bas pour {memes_pct*100:.0f}% memecoins")
    else:
        logger.info(f"   ✅ Risk Score correctement pénalisé (< 50/100)")

    # Attendu vs Réel
    logger.info(f"\n📋 ATTENDU vs REEL :")
    logger.info(f"   Memecoins: {memes_pct*100:.0f}% → Pénalité attendue: -30 points")
    logger.info(f"   Risk Score attendu: ~25-35/100 (high/very_high)")
    logger.info(f"   Risk Score réel: {metrics.risk_score:.1f}/100 ({metrics.overall_risk_level})")

if __name__ == "__main__":
    asyncio.run(test_degen_scoring())
