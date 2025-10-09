"""
Tests unitaires pour le système Dual Window Metrics
Tests cohorte building, cascade fallback, et métadonnées
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from services.portfolio_metrics import PortfolioMetricsService


@pytest.fixture
def portfolio_service():
    """Service de métriques de portfolio"""
    return PortfolioMetricsService()


@pytest.fixture
def create_price_data():
    """Factory pour créer des données de prix avec historiques variables"""
    def _create(asset_configs):
        """
        asset_configs = [
            {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
            {'symbol': 'ETH', 'days': 200, 'base_price': 3000},
            {'symbol': 'SOL', 'days': 55, 'base_price': 100}
        ]
        """
        max_days = max(cfg['days'] for cfg in asset_configs)
        dates = pd.date_range(end=datetime.now(), periods=max_days, freq='D')

        price_data = {}
        for cfg in asset_configs:
            symbol = cfg['symbol']
            days = cfg['days']
            base_price = cfg['base_price']

            # Générer prix synthétiques avec volatilité
            np.random.seed(hash(symbol) % 2**32)
            returns = np.random.normal(0.001, 0.02, days)  # 0.1% drift, 2% vol
            prices = base_price * np.exp(np.cumsum(returns))

            # Aligner sur les derniers jours
            price_series = pd.Series(index=dates[-days:], data=prices)
            price_data[symbol] = price_series

        return pd.DataFrame(price_data)

    return _create


@pytest.fixture
def create_balances():
    """Factory pour créer des balances"""
    def _create(holdings):
        """
        holdings = [
            {'symbol': 'BTC', 'value_usd': 50000},
            {'symbol': 'ETH', 'value_usd': 30000},
        ]
        """
        balances = []
        for h in holdings:
            balances.append({
                'symbol': h['symbol'],
                'balance': h['value_usd'] / 1000,  # dummy quantity
                'value_usd': h['value_usd']
            })
        return balances

    return _create


# ============================================================================
# Test 1: Cohort Long-Term Disponible (cas nominal)
# ============================================================================

def test_dual_window_long_term_available(portfolio_service, create_price_data, create_balances):
    """Test cas nominal : cohorte long-term disponible (365j, 80% couverture)"""

    # Setup : 3 assets, 2 avec historique 365j (80% valeur), 1 récent (20% valeur)
    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'ETH', 'days': 365, 'base_price': 3000},
        {'symbol': 'SOL', 'days': 55, 'base_price': 100}
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 50000},  # 50%
        {'symbol': 'ETH', 'value_usd': 30000},  # 30%
        {'symbol': 'SOL', 'value_usd': 20000}   # 20% (récent)
    ])

    # Execute
    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=2
    )

    # Assert
    assert result['long_term'] is not None, "Long-term window devrait être disponible"
    assert result['long_term']['window_days'] == 365, "Devrait utiliser 365j"
    assert result['long_term']['asset_count'] == 2, "BTC + ETH = 2 assets"
    assert result['long_term']['coverage_pct'] >= 0.80, "Couverture ≥ 80%"

    assert result['full_intersection'] is not None
    # Note: full_intersection utilise l'intersection temporelle (après dropna())
    # Ici, SOL n'a que 55j, donc l'intersection complète = 55j (pas 365j)
    assert result['full_intersection']['window_days'] == 55, "Intersection temporelle = 55j (SOL limite)"
    assert result['full_intersection']['asset_count'] == 3, "Tous les assets"

    assert result['risk_score_source'] == 'long_term', "Source autoritaire = long_term"

    # Vérifier exclusions
    excl = result['exclusions_metadata']
    assert len(excl['excluded_assets']) == 1, "SOL exclu"
    assert excl['excluded_assets'][0]['symbol'] == 'SOL'
    assert excl['excluded_pct'] == 0.20, "20% valeur exclue"


# ============================================================================
# Test 2: Cascade Fallback (365 → 180j)
# ============================================================================

def test_dual_window_cascade_fallback(portfolio_service, create_price_data, create_balances):
    """Test cascade : 365j insuffisant, fallback 180j OK"""

    # Setup : 365j insuffisant (1 asset), 180j OK (2 assets, 75% valeur)
    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'ETH', 'days': 180, 'base_price': 3000},
        {'symbol': 'SOL', 'days': 55, 'base_price': 100}
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 40000},  # 40%
        {'symbol': 'ETH', 'value_usd': 35000},  # 35%
        {'symbol': 'SOL', 'value_usd': 25000}   # 25%
    ])

    # Execute avec min_coverage=0.70 (70%)
    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.70,  # 70% requis
        min_asset_count=2
    )

    # Assert
    assert result['long_term'] is not None
    assert result['long_term']['window_days'] == 180, "Cascade fallback à 180j"
    assert result['long_term']['asset_count'] == 2, "BTC + ETH"
    assert result['long_term']['coverage_pct'] >= 0.70, "Couverture ≥ 70%"


# ============================================================================
# Test 3: Aucune Cohorte Valide (Fallback Full Intersection)
# ============================================================================

def test_dual_window_no_valid_cohort(portfolio_service, create_price_data, create_balances):
    """Test échec cascade : aucune cohorte valide, fallback full intersection"""

    # Setup : tous assets avec historique court (< 90j)
    price_data = create_price_data([
        {'symbol': 'SOL', 'days': 55, 'base_price': 100},
        {'symbol': 'AVAX', 'days': 60, 'base_price': 50},
        {'symbol': 'MATIC', 'days': 50, 'base_price': 1.5}
    ])

    balances = create_balances([
        {'symbol': 'SOL', 'value_usd': 40000},
        {'symbol': 'AVAX', 'value_usd': 30000},
        {'symbol': 'MATIC', 'value_usd': 30000}
    ])

    # Execute
    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=5
    )

    # Assert
    assert result['long_term'] is None, "Aucune cohorte long-term valide"
    assert result['full_intersection'] is not None, "Full intersection toujours disponible"
    assert result['risk_score_source'] == 'full_intersection', "Fallback à full_intersection"
    assert result['exclusions_metadata']['reason'] == 'no_valid_cohort_found'


# ============================================================================
# Test 4: Divergence Sharpe Entre Fenêtres
# ============================================================================

def test_dual_window_sharpe_divergence(portfolio_service, create_price_data, create_balances):
    """Test détection divergence Sharpe entre long-term et full intersection"""

    # Setup : Asset ancien stable, récent volatil
    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'PEPE', 'days': 60, 'base_price': 0.00001}  # Récent volatil (60j pour > 30 après dropna)
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 70000},  # 70%
        {'symbol': 'PEPE', 'value_usd': 30000}  # 30% (récent)
    ])

    # Execute
    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.70,
        min_asset_count=1
    )

    # Assert
    assert result['long_term'] is not None
    lt_sharpe = result['long_term']['metrics'].sharpe_ratio
    fi_sharpe = result['full_intersection']['metrics'].sharpe_ratio

    # Note : Sharpe peut diverger significativement
    # (le test vérifie juste que les deux sont calculés, pas l'écart exact car aléatoire)
    assert lt_sharpe is not None
    assert fi_sharpe is not None

    # Note: avec BTC=70% et couverture min=70%, la cascade peut fallback à 180j
    # (car 365j avec 1 seul asset ne satisfait pas toujours la couverture selon cascade)
    assert result['long_term']['window_days'] >= 180, "Au moins 180j"
    assert result['full_intersection']['window_days'] == 60, "Intersection temporelle = 60j (PEPE limite)"


# ============================================================================
# Test 5: Exclusions Metadata Précises
# ============================================================================

def test_dual_window_exclusions_metadata(portfolio_service, create_price_data, create_balances):
    """Test précision des métadonnées d'exclusion"""

    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'ETH', 'days': 365, 'base_price': 3000},
        {'symbol': 'SOL', 'days': 55, 'base_price': 100},
        {'symbol': 'AVAX', 'days': 60, 'base_price': 50}
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 40000},   # 40%
        {'symbol': 'ETH', 'value_usd': 40000},   # 40%
        {'symbol': 'SOL', 'value_usd': 10000},   # 10%
        {'symbol': 'AVAX', 'value_usd': 10000}   # 10%
    ])

    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=2
    )

    excl = result['exclusions_metadata']

    # Assert structure complète
    assert 'excluded_assets' in excl
    assert 'excluded_value_usd' in excl
    assert 'excluded_pct' in excl
    assert 'included_assets' in excl
    assert 'included_value_usd' in excl
    assert 'included_pct' in excl
    assert 'target_days' in excl
    assert 'achieved_days' in excl
    assert 'reason' in excl

    # Assert valeurs
    assert len(excl['excluded_assets']) == 2, "SOL + AVAX exclus"
    assert excl['excluded_value_usd'] == 20000, "10k + 10k = 20k"
    assert excl['excluded_pct'] == 0.20, "20% exclu"
    assert len(excl['included_assets']) == 2, "BTC + ETH inclus"
    assert excl['included_value_usd'] == 80000, "40k + 40k = 80k"
    assert excl['included_pct'] == 0.80, "80% inclus"
    assert excl['reason'] == 'success'


# ============================================================================
# Test 6: Edge Case - Asset Count Insuffisant
# ============================================================================

def test_dual_window_insufficient_asset_count(portfolio_service, create_price_data, create_balances):
    """Test échec : couverture OK mais nombre d'assets insuffisant"""

    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'SOL', 'days': 55, 'base_price': 100}
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 90000},  # 90% (couverture OK)
        {'symbol': 'SOL', 'value_usd': 10000}   # 10%
    ])

    # Execute avec min_asset_count=5 (impossible avec 1 seul asset long-term)
    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=5  # ⚠️ Trop élevé
    )

    # Assert
    assert result['long_term'] is None, "1 asset < 5 requis, échec"
    assert result['risk_score_source'] == 'full_intersection'


# ============================================================================
# Test 7: Métriques Identiques Quand Tous Assets Ont Historique Long
# ============================================================================

def test_dual_window_identical_when_all_long_history(portfolio_service, create_price_data, create_balances):
    """Test cas limite : tous assets ont historique long → fenêtres identiques"""

    price_data = create_price_data([
        {'symbol': 'BTC', 'days': 365, 'base_price': 50000},
        {'symbol': 'ETH', 'days': 365, 'base_price': 3000},
        {'symbol': 'SOL', 'days': 365, 'base_price': 100}
    ])

    balances = create_balances([
        {'symbol': 'BTC', 'value_usd': 40000},
        {'symbol': 'ETH', 'value_usd': 30000},
        {'symbol': 'SOL', 'value_usd': 30000}
    ])

    result = portfolio_service.calculate_dual_window_metrics(
        price_data=price_data,
        balances=balances,
        min_history_days=180,
        min_coverage_pct=0.80,
        min_asset_count=3
    )

    # Assert : long-term et full_intersection doivent être très similaires
    assert result['long_term'] is not None
    assert result['long_term']['window_days'] == 365
    assert result['full_intersection']['window_days'] == 365
    assert result['long_term']['asset_count'] == 3
    assert result['full_intersection']['asset_count'] == 3

    # Scores devraient être identiques (même cohort, même fenêtre)
    lt_score = result['long_term']['metrics'].risk_score
    fi_score = result['full_intersection']['metrics'].risk_score
    assert abs(lt_score - fi_score) < 0.1, "Scores quasi-identiques"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
