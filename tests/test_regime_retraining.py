"""
Test script to force regime model retraining with class balancing.
Run this AFTER restarting the server to verify class balancing works.
"""

import asyncio
import logging
from services.ml.bourse.stocks_adapter import StocksMLAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_regime_training():
    """Test regime detection with forced retraining"""
    print("\n" + "="*60)
    print("🧪 Testing Regime Detection with Class Balancing")
    print("="*60 + "\n")

    adapter = StocksMLAdapter()

    # Force regime detection (will trigger training if model missing)
    print("📊 Detecting market regime (SPY benchmark)...")
    result = await adapter.detect_market_regime(
        benchmark="SPY",
        lookback_days=365
    )

    print("\n" + "-"*60)
    print("📈 RESULTS:")
    print("-"*60)
    print(f"Current Regime: {result['current_regime']}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Model Type: {result.get('model_type', 'ML Neural Network')}")

    print("\n🎲 Regime Probabilities:")
    probs = result.get('regime_probabilities', {})
    for regime, prob in sorted(probs.items(), key=lambda x: -x[1]):
        bar = "█" * int(prob * 50)
        print(f"  {regime:20s} {prob:6.1%} {bar}")

    # Check for absurd probabilities
    prob_values = list(probs.values())
    has_absurd = any(p == 1.0 for p in prob_values) and sum(1 for p in prob_values if p == 0) >= 3

    print("\n" + "-"*60)
    if has_absurd:
        print("❌ PROBLÈME: Probabilités absurdes détectées!")
        print("   → Le modèle prédit toujours la même classe")
        print("   → Class balancing n'a pas fonctionné")
    else:
        print("✅ SUCCÈS: Probabilités réalistes!")
        print("   → Class balancing fonctionne correctement")
        print("   → Le modèle est bien calibré")
    print("-"*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_regime_training())
