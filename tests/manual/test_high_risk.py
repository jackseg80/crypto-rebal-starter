from services.risk.structural_score_v2 import compute_structural_score_v2

# Portfolio High_Risk_Contra.csv
# Composition: 55% memes, 31% SOL, 9% L1, 4% BTC, 1% ETH
# GRI: 7.4/10
# Effective assets: 8

# Calculer HHI approximatif
# PEPE 500000*0.00001 = 5000 (50%)
# DOGE 100000*0.08 = 8000 (80%?)
# Attendons, ça dépend des prix réels...
# Utilisons composition donnée: 55% memes, 31% SOL, 9% L1, 4% BTC, 1% ETH

import math

holdings = [
    0.55,  # Memecoins (concentré en 3 actifs)
    0.31,  # SOL
    0.09,  # L1/L0
    0.04,  # BTC
    0.01,  # ETH
]

# HHI = sum of squared weights
hhi = sum(w**2 for w in holdings)

print("=== PORTFOLIO HIGH_RISK_CONTRA.CSV ===")
print(f"Holdings weights: {holdings}")
print(f"HHI: {hhi:.4f}")
print(f"Memes %: 55.0%")
print(f"GRI: 7.4")
print(f"Effective assets: 8")
print()

# Calculer Structure Score V2
score, breakdown = compute_structural_score_v2(
    hhi=hhi,
    memes_pct=0.55,
    gri=7.4,
    effective_assets=8,
    total_value=49100
)

print("=== STRUCTURE SCORE V2 ===")
print(f"Score: {score:.1f}/100")
print()
print("Breakdown:")
print(f"  Base: {breakdown['base']}")
print(f"  HHI penalty: -{breakdown['hhi']:.2f}")
print(f"  Memes penalty: -{breakdown['memecoins']:.2f}")
print(f"  GRI penalty: -{breakdown['gri']:.2f}")
print(f"  Div penalty: -{breakdown['low_diversification']:.2f}")
print(f"  Total penalties: -{breakdown['total_penalties']:.2f}")
print()
print(f"Expected range for Degen: 20-35")
print(f"Result: {score:.1f} {'✅ OK' if 20 <= score <= 35 else '❌ HORS RANGE'}")
