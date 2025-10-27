# Prompt de Reprise : Tests Unitaires pour Trailing Stop

## 🎯 Objectif de cette Session

Créer des **tests unitaires pytest** complets pour valider le système de **Trailing Stop** récemment implémenté pour les positions legacy avec gains élevés.

---

## 📋 Contexte du Projet

**Projet :** Crypto Rebal Starter - Système de gestion de portfolio crypto/bourse
**Technologie :** Python (FastAPI backend) + JavaScript (frontend)
**Dernière Feature :** Trailing Stop adaptatif pour positions legacy (Oct 2025)

**Ce qui a été fait (commit `1eafcca`) :**
- ✅ Implémentation complète du système de trailing stop
- ✅ Extraction du prix d'achat (`avg_price`) depuis CSV Saxo
- ✅ Calculateur générique réutilisable (`TrailingStopCalculator`)
- ✅ Intégration dans le flux de données (9 fichiers modifiés)
- ✅ UI avec badge 🏆 pour positions legacy
- ✅ Documentation complète (569 lignes)
- ✅ Testé manuellement avec position AAPL réelle (+186% gain)

**Ce qui reste à faire :**
- ❌ Tests unitaires automatisés (pytest)
- ❌ Tests d'intégration
- ❌ Tests de régression

---

## 🔑 Fichiers Clés à Tester

### 1. Module Principal à Tester
**Fichier :** `services/stop_loss/trailing_stop_calculator.py`
**Classe :** `TrailingStopCalculator`

**Méthodes à tester :**
```python
class TrailingStopCalculator:
    def calculate_trailing_stop(
        current_price: float,
        avg_price: Optional[float],
        ath: Optional[float] = None,
        price_history: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]

    def _estimate_ath(
        price_history: pd.DataFrame,
        current_price: float
    ) -> float

    def _find_tier(gain_ratio: float) -> Tuple[Tuple[float, float], Optional[float]]

    def is_legacy_position(
        current_price: float,
        avg_price: Optional[float],
        legacy_threshold: float = 1.0
    ) -> bool
```

### 2. Intégration à Tester
**Fichiers :**
- `connectors/saxo_import.py` - Extraction `avg_price`
- `adapters/saxo_adapter.py` - Propagation `avg_price`
- `services/ml/bourse/stop_loss_calculator.py` - Intégration Method #6

---

## 🧪 Cas de Test à Implémenter

### Test Suite 1 : `TrailingStopCalculator` (Unitaire)

**Fichier à créer :** `tests/unit/test_trailing_stop_calculator.py`

#### Test 1.1 : Calcul par Tier
```python
def test_trailing_stop_tier_20_to_50():
    """Test tier 20-50% : -15% from ATH"""
    calc = TrailingStopCalculator()
    result = calc.calculate_trailing_stop(
        current_price=135.0,
        avg_price=100.0,  # +35% gain
        ath=140.0
    )
    assert result['applicable'] == True
    assert result['unrealized_gain_pct'] == 35.0
    assert result['tier'] == (0.20, 0.50)
    assert result['trail_pct'] == 0.15
    assert result['stop_loss'] == 119.0  # 140 × 0.85

def test_trailing_stop_tier_50_to_100():
    """Test tier 50-100% : -20% from ATH"""
    # +75% gain → tier 3

def test_trailing_stop_tier_100_to_500():
    """Test tier 100-500% : -25% from ATH"""
    # +186% gain (comme AAPL) → tier 4

def test_trailing_stop_tier_above_500():
    """Test tier >500% : -30% from ATH"""
    # +600% gain → tier 5 (legacy)
```

#### Test 1.2 : Seuil Minimum (20%)
```python
def test_trailing_stop_below_threshold():
    """Position avec <20% gain : pas de trailing stop"""
    calc = TrailingStopCalculator()
    result = calc.calculate_trailing_stop(
        current_price=110.0,
        avg_price=100.0,  # +10% gain
        ath=110.0
    )
    assert result['applicable'] == False
    assert 'min_threshold' in result
```

#### Test 1.3 : Estimation ATH
```python
def test_estimate_ath_from_high_column():
    """ATH estimé depuis colonne 'high' du DataFrame"""
    calc = TrailingStopCalculator()
    price_data = pd.DataFrame({
        'high': [100, 150, 200, 180, 170],
        'close': [95, 145, 195, 175, 165]
    })
    result = calc.calculate_trailing_stop(
        current_price=170.0,
        avg_price=100.0,
        price_history=price_data
    )
    assert result['ath'] == 200.0  # Max de 'high'
    assert result['ath_estimated'] == True

def test_estimate_ath_fallback_close():
    """ATH depuis 'close' si pas de 'high'"""
    # DataFrame sans colonne 'high'

def test_ath_minimum_is_current_price():
    """ATH ne peut pas être < current_price"""
    # Historique avec max=180, current=200 → ATH=200
```

#### Test 1.4 : Edge Cases
```python
def test_trailing_stop_no_avg_price():
    """Sans avg_price : retourne None"""

def test_trailing_stop_invalid_avg_price():
    """avg_price <= 0 : retourne None"""

def test_trailing_stop_no_price_history():
    """Sans historique : utilise current_price comme ATH"""

def test_is_legacy_position():
    """Test détection position legacy"""
```

---

### Test Suite 2 : Extraction `avg_price` (Intégration)

**Fichier à créer :** `tests/integration/test_saxo_import_avg_price.py`

#### Test 2.1 : Extraction depuis CSV
```python
def test_extract_avg_price_from_csv():
    """Vérifie extraction du prix d'entrée depuis CSV Saxo"""
    from connectors.saxo_import import SaxoImportConnector

    # Utiliser le vrai CSV de test : 20251025_103840_Positions...
    connector = SaxoImportConnector()
    result = connector.process_saxo_file(
        'data/users/jack/saxobank/data/20251025_103840_Positions_25-oct.-2025_10_37_13.csv',
        user_id='jack'
    )

    # Trouver AAPL
    aapl = next(p for p in result['positions'] if 'AAPL' in p['symbol'])

    assert 'avg_price' in aapl
    assert aapl['avg_price'] == pytest.approx(91.90, rel=0.01)
    assert aapl['avg_price'] > 0

def test_avg_price_aliases():
    """Test tous les aliases : 'Prix entrée', 'Prix revient', etc."""
```

#### Test 2.2 : Propagation dans Adapter
```python
def test_avg_price_preserved_in_normalization():
    """avg_price préservé dans saxo_adapter.ingest_file()"""

def test_avg_price_in_list_positions():
    """avg_price présent dans saxo_adapter.list_positions()"""
```

---

### Test Suite 3 : Intégration StopLossCalculator

**Fichier à créer :** `tests/integration/test_stop_loss_integration.py`

#### Test 3.1 : Méthode #6 Ajoutée
```python
def test_trailing_stop_method_present():
    """Méthode trailing_stop présente dans résultats"""
    from services.ml.bourse.stop_loss_calculator import StopLossCalculator

    calc = StopLossCalculator()
    result = calc.calculate_all_methods(
        current_price=500.0,
        price_data=mock_price_data,
        avg_price=200.0  # +150% gain
    )

    assert 'trailing_stop' in result['stop_loss_levels']
    assert len(result['stop_loss_levels']) == 6  # Pas 5

def test_trailing_stop_priority():
    """Trailing stop prioritaire pour positions legacy"""
    result = calc.calculate_all_methods(
        current_price=500.0,
        price_data=mock_price_data,
        avg_price=200.0  # +150% gain
    )

    assert result['recommended_method'] == 'trailing_stop'

def test_fallback_to_fixed_variable():
    """Sans avg_price : fallback sur Fixed Variable"""
    result = calc.calculate_all_methods(
        current_price=500.0,
        price_data=mock_price_data,
        avg_price=None  # Pas de prix d'achat
    )

    assert 'trailing_stop' not in result['stop_loss_levels']
    assert result['recommended_method'] == 'fixed_variable'
```

---

### Test Suite 4 : API Endpoints (E2E)

**Fichier à créer :** `tests/e2e/test_recommendations_api.py`

#### Test 4.1 : Endpoint Recommendations
```python
@pytest.mark.asyncio
async def test_recommendations_includes_trailing_stop():
    """API /portfolio-recommendations retourne trailing stop pour AAPL"""
    from httpx import AsyncClient
    from api.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": "jack",
                "file_key": "20251025_103840_Positions_25-oct.-2025_10_37_13.csv",
                "timeframe": "medium"
            }
        )

    assert response.status_code == 200
    data = response.json()

    # Trouver AAPL
    aapl = next(r for r in data['recommendations'] if 'AAPL' in r['symbol'])

    analysis = aapl['price_targets']['stop_loss_analysis']
    assert 'trailing_stop' in analysis['stop_loss_levels']
    assert analysis['recommended_method'] == 'trailing_stop'

    ts = analysis['stop_loss_levels']['trailing_stop']
    assert ts['gain_pct'] == pytest.approx(186.0, rel=0.1)
    assert ts['is_legacy'] == True
```

---

## 📦 Structure des Tests à Créer

```
tests/
├── unit/
│   └── test_trailing_stop_calculator.py      # Suite 1 (15-20 tests)
├── integration/
│   ├── test_saxo_import_avg_price.py          # Suite 2 (5-8 tests)
│   └── test_stop_loss_integration.py          # Suite 3 (8-10 tests)
└── e2e/
    └── test_recommendations_api.py             # Suite 4 (3-5 tests)

Total estimé : ~35-45 tests
```

---

## 🛠️ Setup Pytest

**Fichier à créer/modifier :** `pytest.ini` ou `pyproject.toml`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --tb=short
    --strict-markers
    --cov=services/stop_loss
    --cov=services/ml/bourse
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
```

---

## 📊 Commandes de Test

```bash
# Tous les tests
pytest

# Tests unitaires seulement
pytest tests/unit/ -v

# Tests avec coverage
pytest --cov=services/stop_loss --cov-report=html

# Tests spécifiques
pytest tests/unit/test_trailing_stop_calculator.py::test_trailing_stop_tier_100_to_500 -v

# Tests marqués
pytest -m unit  # Seulement unit tests
pytest -m "not slow"  # Exclure tests lents
```

---

## 🎯 Critères de Succès

**Coverage attendu :**
- ✅ `trailing_stop_calculator.py` : **>95% coverage**
- ✅ `stop_loss_calculator.py` (nouvelles lignes) : **>90% coverage**
- ✅ `saxo_import.py` (avg_price) : **>85% coverage**

**Validation :**
- ✅ Tous les tests passent (green)
- ✅ Pas de régression sur les tests existants
- ✅ Coverage HTML généré (`htmlcov/index.html`)
- ✅ Tests documentés (docstrings claires)

---

## 📚 Documentation de Référence

**Fichiers à lire AVANT de commencer :**
1. `docs/TRAILING_STOP_IMPLEMENTATION.md` - Documentation complète (569 lignes)
2. `services/stop_loss/trailing_stop_calculator.py` - Code source à tester
3. `tests/unit/test_stop_loss_calculator.py` - Tests existants pour inspiration
4. `CLAUDE.md` - Guide général du projet

**Gain Tiers (à tester) :**
```python
TRAILING_TIERS = {
    (0.0, 0.20): None,           # 0-20%: N/A
    (0.20, 0.50): 0.15,          # 20-50%: -15%
    (0.50, 1.00): 0.20,          # 50-100%: -20%
    (1.00, 5.00): 0.25,          # 100-500%: -25%
    (5.00, float('inf')): 0.30   # >500%: -30%
}
```

---

## 🚀 Plan d'Action Suggéré

### Étape 1 : Setup (15 min)
1. Lire `docs/TRAILING_STOP_IMPLEMENTATION.md` (sections Tests)
2. Vérifier environnement pytest : `pytest --version`
3. Créer structure de dossiers tests/

### Étape 2 : Tests Unitaires (1h30)
1. `test_trailing_stop_calculator.py` - Commencer par les tests de tier
2. Ajouter tests edge cases
3. Vérifier coverage : `pytest --cov`

### Étape 3 : Tests Intégration (1h)
1. `test_saxo_import_avg_price.py` - Extraction CSV
2. `test_stop_loss_integration.py` - Prioritisation

### Étape 4 : Tests E2E (45 min)
1. `test_recommendations_api.py` - API complète
2. Valider avec vrai CSV de Jack

### Étape 5 : Validation (30 min)
1. Run complet : `pytest -v`
2. Coverage report : `pytest --cov --cov-report=html`
3. Commit : `git add tests/ && git commit -m "test: add comprehensive test suite for trailing stop system"`

**Temps total estimé : ~4 heures**

---

## 💡 Conseils pour la Session

1. **Fixtures réutilisables :**
   ```python
   @pytest.fixture
   def mock_price_data():
       return pd.DataFrame({
           'high': [100, 150, 200, 180, 170],
           'close': [95, 145, 195, 175, 165]
       })
   ```

2. **Parametrize pour tester plusieurs cas :**
   ```python
   @pytest.mark.parametrize("current,avg,expected_tier", [
       (135, 100, (0.20, 0.50)),    # +35%
       (175, 100, (0.50, 1.00)),    # +75%
       (300, 100, (1.00, 5.00)),    # +200%
   ])
   def test_tier_detection(current, avg, expected_tier):
       # ...
   ```

3. **Mocks minimaux :**
   - Ne pas mocker `TrailingStopCalculator` lui-même
   - Mocker seulement les appels externes (API, fichiers si nécessaire)

4. **Tests isolés :**
   - Chaque test doit passer indépendamment
   - Pas de dépendance entre tests
   - Clean state à chaque test

---

## ✅ Checklist Finale

Avant de finir la session :

- [ ] Tests créés pour les 5 tiers de gain
- [ ] Tests edge cases (no avg_price, invalid values)
- [ ] Tests estimation ATH (high/close/fallback)
- [ ] Tests extraction avg_price depuis CSV
- [ ] Tests prioritisation trailing_stop vs fixed_variable
- [ ] Tests API endpoint complet
- [ ] Coverage >95% sur trailing_stop_calculator.py
- [ ] Tous les tests passent (green)
- [ ] Coverage HTML généré
- [ ] Commit créé avec message descriptif

---

**🎯 Objectif Final :** Une suite de tests robuste qui valide complètement le système de trailing stop et empêche toute régression future.

**📝 Note :** Le système est déjà fonctionnel et testé manuellement. Ces tests automatisés servent à garantir la qualité et faciliter la maintenance future.
