"""
Test rapide pour vérifier que Risk Score V2 diverge du Legacy sur portfolio degen

NOTE: Ce script utilise un user_id configurable pour test manual.
Pour tests automatisés, utiliser la fixture test_user_id de conftest.py
"""

import asyncio
import json
import sys
from api.unified_data import get_unified_filtered_balances
from services.portfolio_metrics import portfolio_metrics_service
from services.price_history import get_cached_history
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_risk_divergence(user_id="demo"):
    """
    Test avec un portfolio réel pour voir si V2 diverge de Legacy

    Args:
        user_id: User ID pour isolation multi-tenant (défaut: "demo")
    """
    # Charger les balances actuelles
    unified = await get_unified_filtered_balances(source="cointracking", min_usd=1.0, user_id=user_id)
    balances = unified.get("items", [])

    logger.info(f"🔍 Testing risk divergence for user: {user_id}")

    logger.info(f"📦 Loaded {len(balances)} assets")

    # Récupérer price data
    price_data = {}
    price_history_days = 180

    for balance in balances:
        symbol = balance.get('symbol', '').upper()
        if symbol:
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

    # Calcul LEGACY (single window)
    logger.info("\n🔷 CALCUL LEGACY (Single Window)...")
    legacy_metrics = portfolio_metrics_service.calculate_portfolio_metrics(
        price_data=price_df,
        balances=balances,
        confidence_level=0.95
    )

    logger.info(f"✅ Legacy Risk Score: {legacy_metrics.risk_score:.1f}")
    logger.info(f"   Sharpe: {legacy_metrics.sharpe_ratio:.2f}")
    logger.info(f"   Vol: {legacy_metrics.volatility_annualized:.2%}")

    # Calcul V2 (Dual-Window avec pénalités)
    logger.info("\n🔶 CALCUL V2 (Dual-Window + Pénalités)...")
    dual_result = portfolio_metrics_service.calculate_dual_window_metrics(
        price_data=price_df,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=5,
        confidence_level=0.95
    )

    long_term = dual_result.get('long_term')
    full_inter = dual_result['full_intersection']
    exclusions = dual_result.get('exclusions_metadata', {})

    # Recalculer le blend comme dans risk_endpoints.py
    coverage_long_term = long_term.get('coverage_pct', 0.0) if long_term else 0.0
    w_long = coverage_long_term * 0.4
    w_full = 1 - w_long

    # Pénalités
    excluded_pct = exclusions.get('excluded_pct', 0.0)
    penalty_excluded = -75 * max(0.0, (excluded_pct - 0.20) / 0.80) if excluded_pct > 0.20 else 0.0

    excluded_assets = exclusions.get('excluded_assets', [])
    meme_keywords = ['PEPE', 'BONK', 'DOGE', 'SHIB', 'WIF', 'FLOKI']
    young_memes = [a for a in excluded_assets if any(kw in str(a.get('symbol', '')).upper() for kw in meme_keywords)]

    if young_memes and len(young_memes) >= 2:
        total_value = sum(float(b.get('value_usd', 0)) for b in balances)
        young_memes_value = sum(float(a.get('value_usd', 0)) for a in young_memes)
        young_memes_pct = young_memes_value / total_value if total_value > 0 else 0
        penalty_memes_age = -min(25, 80 * young_memes_pct) if young_memes_pct > 0.30 else 0.0
    else:
        penalty_memes_age = 0.0
        young_memes_pct = 0.0

    # Calculer Risk Score V2
    if long_term and full_inter['window_days'] >= 120 and coverage_long_term >= 0.80:
        risk_score_full = full_inter['metrics'].risk_score
        risk_score_long = long_term['metrics'].risk_score
        blended_risk_score = w_full * risk_score_full + w_long * risk_score_long
        final_risk_score_v2 = max(0, min(100, blended_risk_score + penalty_excluded + penalty_memes_age))
        mode = "blend"
    elif long_term:
        base_risk_score = long_term['metrics'].risk_score
        final_risk_score_v2 = max(0, min(100, base_risk_score + penalty_excluded + penalty_memes_age))
        mode = "long_term_only"
    else:
        base_risk_score = full_inter['metrics'].risk_score
        final_risk_score_v2 = max(0, min(100, base_risk_score + penalty_excluded + penalty_memes_age))
        mode = "full_intersection_only"

    logger.info(f"✅ Risk Score V2: {final_risk_score_v2:.1f} (mode: {mode})")
    logger.info(f"   w_full={w_full:.2f}, w_long={w_long:.2f}")
    logger.info(f"   Penalty Excluded: {penalty_excluded:.1f}")
    logger.info(f"   Penalty Young Memes: {penalty_memes_age:.1f} ({len(young_memes)} memes, {young_memes_pct*100:.1f}% value)")
    logger.info(f"   Excluded %: {excluded_pct*100:.1f}%")

    # Divergence
    divergence = final_risk_score_v2 - legacy_metrics.risk_score
    logger.info(f"\n📊 DIVERGENCE: {divergence:+.1f} points")

    if abs(divergence) < 5:
        logger.info("✅ Portfolio sain : Legacy ≈ V2 (écart < 5 points)")
    elif divergence < -10:
        logger.info("⚠️  Portfolio DEGEN détecté : V2 << Legacy (pénalités actives)")
    else:
        logger.info("ℹ️  Écart modéré entre Legacy et V2")

    # Afficher assets exclus
    if excluded_assets:
        logger.info(f"\n🚫 Assets exclus de Long-Term cohort ({len(excluded_assets)}):")
        for asset in excluded_assets[:5]:  # Top 5
            logger.info(f"   - {asset.get('symbol')}: {asset.get('reason')}")

if __name__ == "__main__":
    # Accepter user_id depuis argument CLI ou utiliser défaut "demo"
    # Usage: python test_risk_score_v2_divergence.py [user_id]
    user_id = sys.argv[1] if len(sys.argv) > 1 else "demo"
    asyncio.run(test_risk_divergence(user_id=user_id))
