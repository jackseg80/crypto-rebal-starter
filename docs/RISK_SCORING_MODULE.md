# Risk Scoring Module — Documentation Technique

> 📁 **Module** : `services/risk_scoring.py`
> 🎯 **Rôle** : Single Source of Truth pour le calcul Risk Score et mapping score→level
> 📅 **Créé** : Octobre 2025 (centralisation anti-duplication)

---

## 🏛️ Architecture

### Responsabilité Unique

Ce module centralise **toute** la logique de scoring de risque pour éviter la duplication et garantir la cohérence.

**❌ Anti-pattern** : Dupliquer cette logique dans d'autres services (`portfolio_metrics.py`, `risk_management.py`, endpoints).

### Dépendances

```python
from services.risk_scoring import assess_risk_level, score_to_level, RISK_LEVEL_THRESHOLDS
```

**Modules consommateurs** :
- `services/portfolio_metrics.py` : Calcul métriques portfolio
- `services/risk_management.py` : Legacy risk assessment (à migrer)
- `api/risk_endpoints.py` : Endpoints Risk Dashboard

---

## 📊 API Publique

### `score_to_level(score: float) -> str`

Mapping canonique Risk Score → Risk Level.

**Arguments** :
- `score` (float) : Risk score [0..100], clamped automatiquement

**Retour** :
- `str` : Niveau de risque (`"very_low"`, `"low"`, `"medium"`, `"high"`, `"very_high"`, `"critical"`)

**Mapping** :
```python
score >= 80  → "very_low"     # Très robuste
score >= 65  → "low"          # Robuste
score >= 50  → "medium"       # Modéré
score >= 35  → "high"         # Fragile
score >= 20  → "very_high"    # Très fragile
score < 20   → "critical"     # Critique
```

**Exemples** :
```python
>>> score_to_level(85)
'very_low'
>>> score_to_level(40)
'high'
>>> score_to_level(150)  # Clamped to 100
'very_low'
```

---

### `assess_risk_level(...) -> Dict[str, Any]`

Calcul autoritaire du Risk Score selon Option A (robustesse).

**Arguments** :
```python
assess_risk_level(
    var_metrics: Dict[str, float],  # {'var_95': 0.12, 'var_99': 0.18, ...}
    sharpe_ratio: float,            # Sharpe ratio (risk-adjusted return)
    max_drawdown: float,            # Maximum drawdown (valeur négative)
    volatility: float               # Volatilité annualisée
) -> Dict[str, Any]
```

**Retour** :
```python
{
    "score": 65.0,              # Score final [0..100]
    "level": "low",             # Niveau mappé
    "breakdown": {              # Détail contributions (audit)
        "var_95": -8.0,
        "sharpe": 10.0,
        "drawdown": 5.0,
        "volatility": 5.0
    }
}
```

**Logique** :

1. **Baseline neutre** : `score = 50.0`

2. **VaR impact** (inversé : VaR ↑ → robustesse ↓ → score ↓)
   - `var_95 > 0.25` → score **-30**
   - `var_95 > 0.15` → score **-15**
   - `var_95 < 0.05` → score **+10**
   - `var_95 < 0.10` → score **+5**

3. **Sharpe impact** (direct : Sharpe ↑ → robustesse ↑ → score ↑)
   - `sharpe < 0` → score **-15**
   - `sharpe > 2.0` → score **+20**
   - `sharpe > 1.5` → score **+15**
   - `sharpe > 1.0` → score **+10**
   - `sharpe > 0.5` → score **+5**

4. **Drawdown impact** (inversé : DD ↑ → robustesse ↓ → score ↓)
   - `|dd| > 0.50` → score **-25**
   - `|dd| > 0.30` → score **-15**
   - `|dd| < 0.10` → score **+10**
   - `|dd| < 0.20` → score **+5**

5. **Volatility impact** (inversé : Vol ↑ → robustesse ↓ → score ↓)
   - `vol > 1.0` → score **-10**
   - `vol > 0.60` → score **-5**
   - `vol < 0.20` → score **+10**
   - `vol < 0.40` → score **+5**

6. **Clamp & Map** : `score = clamp(score, 0, 100)` puis `level = score_to_level(score)`

---

### `RISK_LEVEL_THRESHOLDS` (constante)

Configuration des seuils de mapping.

```python
RISK_LEVEL_THRESHOLDS = {
    "very_low": 80,
    "low": 65,
    "medium": 50,
    "high": 35,
    "very_high": 20,
    "critical": 0
}
```

**Usage** : Externaliser dans fichier config si nécessaire (YAML).

---

## 🧪 Tests

**Fichier** : `tests/unit/test_risk_scoring.py`

### Coverage

- ✅ **Mapping score→level** (15 cas de test)
  - Thresholds exacts (80, 65, 50, 35, 20)
  - Clamping hors bornes (-50 → 0, 150 → 100)

- ✅ **Sémantique Option A**
  - VaR ↑ → score ↓ (robustesse inverse)
  - Sharpe ↑ → score ↑ (robustesse directe)

- ✅ **Breakdown validation**
  - Sum contributions = (score - 50)
  - Tous composants présents (var_95, sharpe, drawdown, volatility)

- ✅ **Edge cases**
  - Métriques nulles
  - Valeurs extrêmes (VaR 50%, Sharpe -10)

### Exécution

```bash
# Activer .venv d'abord
.venv\Scripts\Activate.ps1

# Lancer tests
pytest tests/unit/test_risk_scoring.py -v
```

**Résultat attendu** : 15+ tests PASSED

---

## 🔧 Migration & Maintenance

### Checklist Migration

Si vous trouvez du code dupliqué ailleurs :

1. ❌ **Supprimer** la duplication (ex: `_assess_overall_risk_level()` dans `portfolio_metrics.py`)
2. ✅ **Importer** depuis `risk_scoring.py`
3. ✅ **Tester** que le comportement reste identique
4. ✅ **Documenter** le changement dans commit message

### Évolution Future

**Si modification des seuils ou formule** :

1. Modifier **uniquement** dans `services/risk_scoring.py`
2. Mettre à jour `RISK_LEVEL_THRESHOLDS` ou logique `assess_risk_level()`
3. Lancer tests : `pytest tests/unit/test_risk_scoring.py`
4. Mettre à jour cette doc + `docs/RISK_SEMANTICS.md`

**Si ajout d'un nouveau score** (ex: `risk_score_alternative`) :

1. Créer nouvelle fonction `assess_risk_level_alternative()` dans ce module
2. Ajouter tests dédiés
3. Documenter usage et différences

---

## 📚 Références

- **Sémantique** : [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)
- **Tests** : [tests/unit/test_risk_scoring.py](../tests/unit/test_risk_scoring.py)
- **API Endpoint** : [api/risk_endpoints.py](../api/risk_endpoints.py)
- **Service Portfolio** : [services/portfolio_metrics.py](../services/portfolio_metrics.py)

---

## ⚠️ Avertissements

1. **Ne JAMAIS dupliquer** la logique de ce module ailleurs
2. **Ne JAMAIS inverser** le score avec `100 - score` (violé la sémantique Option A)
3. **Ne JAMAIS re-mapper** `overall_risk_level` dans les endpoints (utiliser la valeur du service)
4. **Toujours passer** les tests après modification

**En cas de doute** : Consulter [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)
