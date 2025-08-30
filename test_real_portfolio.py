#!/usr/bin/env python3
"""
Test du système de risque avec le vrai portfolio depuis CSV
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.append(str(Path(__file__).parent))

from api.unified_data import get_unified_filtered_balances
from services.risk_management import risk_manager

async def test_real_portfolio():
    """Test avec le vrai portfolio depuis CSV"""
    
    print("TEST: Système de risque avec VRAI portfolio depuis CSV")
    
    # Récupérer les vraies données depuis CSV
    portfolio_data = await get_unified_filtered_balances(source="cointracking", min_usd=1.0)
    items = portfolio_data.get("items", [])
    
    if not items:
        print("❌ Aucun holding trouvé dans le portfolio")
        return
    
    # Convertir au format attendu par le risk manager
    real_holdings = []
    for item in items:
        symbol = item.get("symbol", "").upper()
        value_usd = float(item.get("value_usd", 0))
        balance = float(item.get("amount", 0))
        
        if value_usd > 0:  # Filtrer les holdings avec valeur positive
            real_holdings.append({
                "symbol": symbol,
                "balance": balance,
                "value_usd": value_usd
            })
    
    if not real_holdings:
        print("❌ Aucun holding avec valeur positive")
        return
    
    total_value = sum(h['value_usd'] for h in real_holdings)
    print(f"Portfolio RÉEL: {len(real_holdings)} assets, ${total_value:,.0f}")
    
    # Afficher les top 10 holdings
    real_holdings_sorted = sorted(real_holdings, key=lambda x: x['value_usd'], reverse=True)
    print("\\nTop holdings:")
    for i, h in enumerate(real_holdings_sorted[:10], 1):
        print(f"  {i:2d}. {h['symbol']:8} ${h['value_usd']:>10,.0f} ({h['value_usd']/total_value*100:5.1f}%)")
    
    # Test des métriques de risque
    print("\\n1. Test des métriques de risque...")
    try:
        risk_metrics = await risk_manager.calculate_portfolio_risk_metrics(
            holdings=real_holdings,
            price_history_days=30
        )
        
        print(f"VaR 95%: {risk_metrics.var_95_1d:.2%}")
        print(f"Volatilité: {risk_metrics.volatility_annualized:.2%}")
        print(f"Sharpe: {risk_metrics.sharpe_ratio:.2f}")
        print(f"Risk Score: {risk_metrics.risk_score:.1f}")
        print(f"Confiance: {risk_metrics.confidence_level:.1%}")
        
    except Exception as e:
        print(f"❌ Erreur calcul risque: {e}")
        return
    
    # Test de la matrice de corrélation
    print("\\n2. Test de la matrice de corrélation...")
    try:
        correlation_matrix = await risk_manager.calculate_correlation_matrix(
            holdings=real_holdings,
            lookback_days=30
        )
        
        print(f"Ratio diversification: {correlation_matrix.diversification_ratio:.2f}")
        print(f"Assets effectifs: {correlation_matrix.effective_assets:.1f}")
        
        # Afficher quelques corrélations
        if correlation_matrix.correlations:
            print(f"Corrélations calculées entre {len(correlation_matrix.correlations)} assets")
            # Trouver les corrélations les plus fortes
            correlations = []
            for asset1, corr_dict in correlation_matrix.correlations.items():
                for asset2, corr in corr_dict.items():
                    if asset1 != asset2 and abs(corr) > 0.5:  # Seulement les corrélations significatives
                        correlations.append((asset1, asset2, corr))
            
            # Trier par corrélation absolue décroissante
            correlations.sort(key=lambda x: abs(x[2]), reverse=True)
            for asset1, asset2, corr in correlations[:5]:
                print(f"   {asset1}-{asset2}: {corr:.3f}")
        
    except Exception as e:
        print(f"❌ Erreur corrélation: {e}")
        return
    
    print("\\n✅ TEST TERMINÉ AVEC SUCCÈS!")
    print("Les métriques de risque sont calculées avec vos VRAIES données de portfolio!")

if __name__ == "__main__":
    asyncio.run(test_real_portfolio())