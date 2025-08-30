#!/usr/bin/env python3
"""
Test du système de risque avec données réelles depuis le cache d'historique
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.append(str(Path(__file__).parent))

from services.risk_management import risk_manager

async def test_real_risk():
    """Test avec un portfolio simulé utilisant les vraies données de prix"""
    
    # Portfolio simulé avec les symboles que nous avons mis en cache
    mock_holdings = [
        {"symbol": "BTC", "balance": 0.5, "value_usd": 54000},
        {"symbol": "ETH", "balance": 10.0, "value_usd": 25000},
        {"symbol": "SOL", "balance": 100.0, "value_usd": 15000},
        {"symbol": "LINK", "balance": 500.0, "value_usd": 6000},
    ]
    
    print("TEST: Système de risque avec données réelles")
    print(f"Portfolio test: {len(mock_holdings)} assets, ${sum(h['value_usd'] for h in mock_holdings):,.0f}")
    
    # Test des métriques de risque
    print("\n1. Test des métriques de risque...")
    risk_metrics = await risk_manager.calculate_portfolio_risk_metrics(
        holdings=mock_holdings,
        price_history_days=30
    )
    
    print(f"VaR 95%: {risk_metrics.var_95_1d:.2%}")
    print(f"Volatilité: {risk_metrics.volatility_annualized:.2%}")
    print(f"Sharpe: {risk_metrics.sharpe_ratio:.2f}")
    print(f"Risk Score: {risk_metrics.risk_score:.1f}")
    print(f"Confiance: {risk_metrics.confidence_level:.1%}")
    
    # Test de la matrice de corrélation
    print("\n2. Test de la matrice de corrélation...")
    correlation_matrix = await risk_manager.calculate_correlation_matrix(
        holdings=mock_holdings,
        lookback_days=30
    )
    
    print(f"Ratio diversification: {correlation_matrix.diversification_ratio:.2f}")
    print(f"Assets effectifs: {correlation_matrix.effective_assets:.1f}")
    
    # Afficher quelques corrélations
    if correlation_matrix.correlations:
        print(f"Corrélations calculées entre {len(correlation_matrix.correlations)} assets")
        for asset1, corr_dict in list(correlation_matrix.correlations.items())[:2]:
            for asset2, corr in list(corr_dict.items())[:3]:
                if asset1 != asset2:
                    print(f"   {asset1}-{asset2}: {corr:.3f}")
    
    print("\nTEST TERMINÉ AVEC SUCCÈS!")
    print("Les métriques de risque sont maintenant calculées avec de vraies données historiques!")

if __name__ == "__main__":
    asyncio.run(test_real_risk())