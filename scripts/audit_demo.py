import requests
import json

# Fetch data
resp = requests.get("http://localhost:8080/api/risk/dashboard?source=cointracking&user_id=demo&risk_version=v2_shadow")
d = resp.json()

rm = d['risk_metrics']
rv = rm['risk_version_info']

print('=== PORTFOLIO DEMO - AUDIT STRUCTUREL ===\n')
print(f"Total assets: {d['portfolio_summary']['num_assets']}")
print(f"Total value: ${d['portfolio_summary']['total_value']:,.2f}")
print(f"\nGRI: {rm['group_risk_index']:.2f}")

# Exposure par groupe
exp = rm['exposure_by_group']
print(f"\n--- Exposure by Group ---")
for group, pct in sorted(exp.items(), key=lambda x: -x[1])[:10]:
    print(f"  {group}: {pct*100:.1f}%")

# Memecoins %
memes_pct = exp.get('Memecoins', 0.0)
print(f"\nMemecoins: {memes_pct*100:.1f}%")

# Correlation metrics
corr = d.get('correlation_metrics', {})
print(f"\n--- Diversification ---")
print(f"  Effective assets: {corr.get('effective_assets', 'N/A')}")
print(f"  Diversification ratio: {corr.get('diversification_ratio', 'N/A'):.2f}" if corr.get('diversification_ratio') else "  Diversification ratio: N/A")

# Structural scores
print(f"\n--- STRUCTURAL SCORES ---")
print(f"  Legacy: {rv['structural_score_legacy']}")
print(f"  V2: {rv['structural_score_v2']:.2f}")
print(f"  Écart: +{rv['structural_score_v2'] - rv['structural_score_legacy']:.1f} pts ({(rv['structural_score_v2'] / rv['structural_score_legacy'] - 1)*100:.0f}%)")

# Breakdown V2
breakdown = rv.get('structural_breakdown_v2', {})
if breakdown:
    print(f"\n--- V2 Breakdown (pénalités) ---")
    print(f"  Base: {breakdown.get('base', 100)}")
    print(f"  Pénalité HHI: -{breakdown.get('hhi', 0):.2f}")
    print(f"  Pénalité Memecoins: -{breakdown.get('memecoins', 0):.2f}")
    print(f"  Pénalité GRI: -{breakdown.get('gri', 0):.2f}")
    print(f"  Pénalité Low Div: -{breakdown.get('low_diversification', 0):.2f}")
    print(f"  Total pénalités: -{breakdown.get('total_penalties', 0):.2f}")

    # Inputs
    inputs = breakdown.get('inputs', {})
    print(f"\n--- V2 Inputs ---")
    print(f"  HHI: {inputs.get('hhi', 'N/A'):.4f}" if inputs.get('hhi') else "  HHI: N/A")
    print(f"  Memes %: {inputs.get('memes_pct', 0)*100:.1f}%")
    print(f"  GRI: {inputs.get('gri', 'N/A'):.2f}" if inputs.get('gri') else "  GRI: N/A")
    print(f"  Effective assets: {inputs.get('effective_assets', 'N/A'):.1f}" if inputs.get('effective_assets') else "  Effective assets: N/A")

# Breakdown Legacy
breakdown_leg = rv.get('structural_breakdown_legacy', {})
if breakdown_leg:
    print(f"\n--- Legacy Breakdown ---")
    for key, val in breakdown_leg.items():
        print(f"  {key}: {val:.2f}" if isinstance(val, float) else f"  {key}: {val}")

print("\n=== CALCUL MANUEL V2 ===")
if inputs:
    hhi = inputs.get('hhi', 0)
    memes = inputs.get('memes_pct', 0)
    gri = inputs.get('gri', 0)
    eff = inputs.get('effective_assets', 999)

    base = 100.0
    p_hhi = max(0, (hhi - 0.25)) * 100 if hhi > 0.25 else 0
    p_memes = memes * 40
    p_gri = gri * 5
    p_div = 10 if eff < 5 else 0

    total_pen = p_hhi + p_memes + p_gri + p_div
    score_calc = max(0, min(100, base - total_pen))

    print(f"Base: {base}")
    print(f"  - HHI penalty ({hhi:.4f} - 0.25) × 100 = -{p_hhi:.2f}")
    print(f"  - Memes penalty {memes*100:.1f}% × 40 = -{p_memes:.2f}")
    print(f"  - GRI penalty {gri:.2f} × 5 = -{p_gri:.2f}")
    print(f"  - Div penalty (eff={eff:.1f}) = -{p_div:.2f}")
    print(f"Total penalties: -{total_pen:.2f}")
    print(f"Score calculé: {score_calc:.2f}")
    print(f"Score API: {rv['structural_score_v2']:.2f}")
    print(f"Match: {'✅ OUI' if abs(score_calc - rv['structural_score_v2']) < 0.1 else '❌ NON'}")

