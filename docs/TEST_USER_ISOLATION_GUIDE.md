# Guide d'Isolation Multi-Tenant pour Tests

**Créé**: Octobre 2025
**Objectif**: Garantir l'isolation des tests pour éviter conflits de données entre users

---

## 🎯 Problème

Les tests utilisaient des `user_id` hardcodés (`"demo"`, `"jack"`) causant:
- ❌ Conflits entre tests parallèles
- ❌ Corruption de données de test
- ❌ Faux positifs/négatifs aléatoires
- ❌ Violation du principe multi-tenant

## ✅ Solution: Fixtures pytest

### Fixtures Disponibles (`tests/conftest.py`)

#### 1. `test_user_id` - User ID unique par test

```python
@pytest.fixture
def test_user_id(request) -> str:
    """Génère un user_id unique: test_{nom_fonction}_{uuid8}"""
    ...
```

**Usage:**
```python
async def test_balance_resolution(test_user_id):
    # ✅ User ID unique, isolé
    result = await balance_service.resolve_current_balances(
        source="cointracking",
        user_id=test_user_id
    )
    assert result["ok"]
```

#### 2. `test_user_config` - Config complète (user_id + source)

```python
@pytest.fixture
def test_user_config(test_user_id) -> Dict[str, str]:
    """Retourne {"user_id": "test_xxx_yyy", "source": "cointracking"}"""
    ...
```

**Usage:**
```python
def test_portfolio_metrics(test_client, test_user_config):
    # ✅ Passe directement le dict comme params
    response = test_client.get(
        "/portfolio/metrics",
        params=test_user_config
    )
    assert response.status_code == 200
```

---

## 📋 Migration des Tests Existants

### Pattern 1: Tests unitaires async

**❌ Avant (hardcodé):**
```python
async def test_snapshot_creation():
    result = await create_snapshot(
        user_id="demo",  # ❌ Hardcodé
        source="cointracking"
    )
    assert result["ok"]
```

**✅ Après (isolé):**
```python
async def test_snapshot_creation(test_user_id):
    result = await create_snapshot(
        user_id=test_user_id,  # ✅ Unique
        source="cointracking"
    )
    assert result["ok"]
```

### Pattern 2: Tests API avec TestClient

**❌ Avant:**
```python
def test_get_metrics(test_client):
    response = test_client.get(
        "/portfolio/metrics?user_id=jack&source=cointracking"  # ❌ Hardcodé
    )
    assert response.status_code == 200
```

**✅ Après (Option A - params dict):**
```python
def test_get_metrics(test_client, test_user_config):
    response = test_client.get(
        "/portfolio/metrics",
        params=test_user_config  # ✅ user_id + source
    )
    assert response.status_code == 200
```

**✅ Après (Option B - query string):**
```python
def test_get_metrics(test_client, test_user_id):
    response = test_client.get(
        f"/portfolio/metrics?user_id={test_user_id}&source=cointracking"
    )
    assert response.status_code == 200
```

### Pattern 3: Tests avec setup/teardown

**✅ Avec cleanup automatique:**
```python
@pytest.fixture
def test_portfolio_data(test_user_id):
    """Setup portfolio data, cleanup après test"""
    # Setup
    portfolio = create_test_portfolio(user_id=test_user_id)

    yield portfolio

    # Teardown automatique
    cleanup_user_data(user_id=test_user_id)

def test_portfolio_rebalance(test_portfolio_data):
    # Test utilise données isolées
    result = rebalance(test_portfolio_data)
    assert result["ok"]
    # Cleanup automatique après le test
```

---

## 🔍 Fichiers à Migrer (40+ occurrences)

### Priorité Haute
- [ ] `tests/test_portfolio_pnl.py` (14 occurrences)
- [ ] `tests/integration/test_balance_resolution.py` (8 occurrences)
- [ ] `test_risk_score_v2_divergence.py` (1 occurrence)

### Priorité Moyenne
- [ ] Tous les tests dans `tests/unit/`
- [ ] Tous les tests dans `tests/integration/`
- [ ] Scripts de test manuels dans `scripts/`

### Commande de détection
```bash
# Trouver tous les user_id hardcodés dans tests
grep -rn 'user_id.*=.*["'"'"']demo["'"'"']' tests/
grep -rn 'user_id.*=.*["'"'"']jack["'"'"']' tests/
```

---

## ⚙️ Configuration Scheduler

Les jobs schedulés ont également été sécurisés ([scheduler.py](../api/scheduler.py)):

**Variables d'environnement:**
```bash
# .env
SNAPSHOT_USER_ID=jack      # User pour P&L snapshots
WARMUP_USER_ID=demo        # User pour API warmers
```

**Validation automatique:**
- ✅ Appel `is_allowed_user()` avant exécution
- ✅ Skip jobs si user_id invalide
- ✅ Log warning + status update
- ✅ Pas de hardcode `user_id=demo` dans code

---

## 📊 Impact Attendu

### Avant
```
Tests parallèles: ❌ Échouent aléatoirement
Isolation: ❌ Données partagées entre tests
Multi-tenant: ❌ Violé (hardcode demo/jack)
Debugging: ❌ Difficile (conflits intermittents)
```

### Après
```
Tests parallèles: ✅ Stables, indépendants
Isolation: ✅ Chaque test = user unique
Multi-tenant: ✅ Respecté
Debugging: ✅ Facile (logs montrent user_id unique)
```

---

## 🚀 Quick Start

1. **Nouveau test unitaire:**
```python
async def test_my_feature(test_user_id):
    result = await my_service.do_something(user_id=test_user_id)
    assert result["ok"]
```

2. **Nouveau test API:**
```python
def test_my_endpoint(test_client, test_user_config):
    response = test_client.get("/my/endpoint", params=test_user_config)
    assert response.status_code == 200
```

3. **Test avec données persistantes:**
```python
@pytest.fixture
def my_test_data(test_user_id):
    data = setup_data(user_id=test_user_id)
    yield data
    cleanup_data(user_id=test_user_id)

def test_with_data(my_test_data):
    assert process(my_test_data)
```

---

## 📚 Références

- **Fixtures pytest**: [conftest.py](../tests/conftest.py#L244-L304)
- **Validation scheduler**: [scheduler.py](../api/scheduler.py#L27)
- **Config users**: [api/config/users.py](../api/config/users.py)
- **Guide multi-tenant**: [SIMULATOR_USER_ISOLATION_FIX.md](SIMULATOR_USER_ISOLATION_FIX.md)

---

**Note**: Migration progressive recommandée. Priorité aux tests qui échouent en parallèle.
