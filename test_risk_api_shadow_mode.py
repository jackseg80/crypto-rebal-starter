"""
Test de l'API /api/risk/dashboard en mode Shadow (v2_shadow)
"""

import asyncio
import httpx
import json

async def test_shadow_mode():
    """
    Appeler l'API en mode v2_shadow et vérifier qu'on a bien Legacy + V2
    """
    url = "http://localhost:8080/api/risk/dashboard"
    params = {
        "source": "cointracking",
        "user_id": "demo",
        "risk_version": "v2_shadow",  # ← Mode Shadow
        "use_dual_window": "true",
        "min_history_days": 180,
        "min_coverage_pct": 0.80
    }

    print(f"🔗 GET {url}")
    print(f"📋 Params: {json.dumps(params, indent=2)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params, headers={"X-User": "demo"})

    if response.status_code != 200:
        print(f"❌ HTTP {response.status_code}")
        print(response.text)
        return

    data = response.json()

    if not data.get("success"):
        print(f"❌ API error: {data.get('message')}")
        return

    print(f"✅ API Success")

    # Vérifier risk_version_info
    version_info = data.get("risk_metrics", {}).get("risk_version_info")

    if not version_info:
        print("❌ Pas de risk_version_info dans la réponse !")
        return

    print(f"\n📊 RISK VERSION INFO:")
    print(f"   Active Version: {version_info.get('active_version')}")
    print(f"   Requested Version: {version_info.get('requested_version')}")
    print(f"\n🔷 LEGACY:")
    print(f"   Risk Score: {version_info.get('risk_score_legacy')}")
    print(f"   Sharpe: {version_info.get('sharpe_legacy')}")
    print(f"\n🔶 V2:")
    print(f"   Risk Score: {version_info.get('risk_score_v2')}")
    print(f"   Sharpe: {version_info.get('sharpe_v2')}")
    print(f"\n📐 STRUCTURAL:")
    print(f"   Portfolio Structure (Pure): {version_info.get('portfolio_structure_score')}")
    print(f"   Integrated Structural (Legacy): {version_info.get('integrated_structural_legacy')}")

    # Vérifier blend_metadata
    blend_meta = version_info.get("blend_metadata")
    if blend_meta:
        print(f"\n🔀 BLEND METADATA:")
        print(f"   Mode: {blend_meta.get('mode')}")
        print(f"   w_full: {blend_meta.get('w_full'):.2f}, w_long: {blend_meta.get('w_long'):.2f}")
        print(f"   Risk Score Full: {blend_meta.get('risk_score_full')}")
        print(f"   Risk Score Long: {blend_meta.get('risk_score_long')}")
        print(f"   Blended (before penalties): {blend_meta.get('blended_risk_score'):.1f}")
        print(f"   Final V2 (after penalties): {blend_meta.get('final_risk_score_v2'):.1f}")
        print(f"   Penalty Excluded: {blend_meta.get('penalty_excluded'):.1f}")
        print(f"   Penalty Memes: {blend_meta.get('penalty_memes'):.1f}")
        print(f"   Young Memes: {blend_meta.get('young_memes_count')} ({blend_meta.get('young_memes_pct')*100:.1f}%)")
        print(f"   Excluded %: {blend_meta.get('excluded_pct')*100:.1f}%")

    # Divergence
    legacy = version_info.get('risk_score_legacy')
    v2 = version_info.get('risk_score_v2')

    if legacy is not None and v2 is not None:
        divergence = v2 - legacy
        print(f"\n📊 DIVERGENCE Legacy → V2: {divergence:+.1f} points")

        if abs(divergence) < 5:
            print("✅ Portfolio sain : Legacy ≈ V2")
        elif divergence < -10:
            print("⚠️  Portfolio DEGEN : V2 << Legacy (pénalités actives)")
        else:
            print("ℹ️  Écart modéré")

if __name__ == "__main__":
    asyncio.run(test_shadow_mode())

