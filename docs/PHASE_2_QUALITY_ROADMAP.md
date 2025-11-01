# Phase 2 Quality Roadmap - Amélioration Code & Architecture

**Date de début**: 29 Octobre 2025
**Objectif**: Améliorer la qualité du code, la couverture de tests, et la cohérence UI/UX
**Priorité**: High (suite Migration Tests Phase 1)

---

## 🎯 Vue d'Ensemble

**Phase 1 (Complétée)**: ✅ Migration tests multi-tenant (95% conformité)
**Phase 2 (En cours)**: Qualité code, tests manquants, formatters, UI/UX

### Objectifs Mesurables

| Métrique | Actuel | Cible | Impact |
|----------|--------|-------|--------|
| **Coverage tests critiques** | ~40% | 80% | +40 pts |
| **Endpoints avec formatters** | 85% | 100% | +15% |
| **Pages full responsive** | 75% | 100% | +25% |
| **Fichiers >1000 lignes** | 5 | 2 | -3 |
| **Code Quality Score** | B+ | A | ⬆️ |

---

## 📋 Tâches Prioritaires

### **🔴 Priorité 1 - Tests Unitaires Critiques** (Effort: 3-4h)

#### 1.1 Tests pour `services/risk_scoring.py` (CRITIQUE)

**Pourquoi critique?**
- Code canonique du Risk Score
- Pas de tests unitaires actuellement
- Utilisé partout dans le système
- Contient logique complexe (hystérésis, pénalités)

**Tests à créer**: `tests/unit/test_risk_scoring.py`

```python
# Tests essentiels à couvrir
class TestRiskScoring:
    def test_risk_score_always_positive_0_100()
    def test_memecoin_penalty_hysteresis_48_52()
    def test_exclusion_penalty_threshold_20_pct()
    def test_young_memes_detection()
    def test_structure_score_penalty()
    def test_risk_score_reproducible()  # Même input = même output
    def test_edge_cases_empty_portfolio()
    def test_edge_cases_all_stablecoins()
```

**Couverture visée**: 80%+

---

#### 1.2 Tests pour `services/balance_service.py` (CRITIQUE)

**Pourquoi critique?**
- Service central de résolution balances
- Multi-tenant (déjà audité mais pas testé unitairement)
- Gestion sources multiples (CSV, API, Saxo)

**Tests à créer**: `tests/unit/test_balance_service.py`

```python
class TestBalanceService:
    def test_resolve_csv_source(test_user_id)
    def test_resolve_api_source(test_user_id)
    def test_resolve_saxo_source(test_user_id)
    def test_fallback_on_missing_csv(test_user_id)
    def test_user_isolation(test_user_id)
    def test_error_handling_invalid_csv()
    def test_cache_behavior()  # Si applicable
```

**Couverture visée**: 75%+

---

#### 1.3 Tests pour `api/scheduler.py` (IMPORTANT)

**Pourquoi important?**
- Jobs critiques (P&L snapshots, OHLCV updates)
- Déjà sécurisé (validation user_id Phase 1)
- Besoin validation comportement

**Tests à créer**: `tests/unit/test_scheduler_jobs.py`

```python
class TestSchedulerJobs:
    @pytest.mark.asyncio
    async def test_pnl_intraday_job(test_user_id)

    @pytest.mark.asyncio
    async def test_pnl_eod_job(test_user_id)

    @pytest.mark.asyncio
    async def test_api_warmers_job(test_user_id)

    def test_invalid_user_id_rejected()
    def test_job_status_tracking()
```

**Couverture visée**: 70%+

---

### **🟠 Priorité 2 - Response Formatters (15% restants)** (Effort: 2-3h)

**Problème**: Inconsistance dans les réponses API

**❌ Pattern actuel (certains endpoints)**:
```python
@router.get("/endpoint")
async def get_data():
    return {"ok": True, "data": {...}}  # Raw dict
```

**✅ Pattern cible (uniformisé)**:
```python
from api.utils import success_response, error_response

@router.get("/endpoint")
async def get_data():
    try:
        data = compute_data()
        return success_response(data, meta={"computed_at": now()})
    except Exception as e:
        return error_response(str(e), code=500)
```

**Endpoints à migrer** (identifiés dans audit):

| Fichier | Endpoints | Effort |
|---------|-----------|--------|
| `api/analytics_endpoints.py` | 3-4 endpoints | 30 min |
| `api/execution_dashboard.py` | 2-3 endpoints | 20 min |
| `api/kraken_endpoints.py` | 2 endpoints | 15 min |

**Total**: 7-9 endpoints (~1h)

**Validation**:
```bash
# Chercher patterns sans formatters
grep -rn "return {" api/*.py | grep -v "success_response\|error_response"
```

---

### **🟡 Priorité 3 - Harmonisation Max-Width** (Effort: 1h)

**Problème**: 4 pages avec `max-width` fixe violant règle "full responsive"

**Pages à corriger**:

1. **static/banks-manager.html:15** (max-width: 1200px)
2. **static/analytics-equities.html:25** (max-width: 1200px)
3. **static/performance-monitor.html:18** (max-width: 1400px)
4. **static/performance-monitor-unified.html:19** (max-width: 1600px)

**Pattern de correction**:

```css
/* ❌ Avant */
.wrap {
    max-width: 1200px;
    margin: 0 auto;
}

/* ✅ Après (selon CLAUDE.md) */
.wrap {
    max-width: none;  /* Ou 95vw pour breathing room sur XL screens */
    margin: 0 auto;
    padding: clamp(1rem, 2vw, 3rem);  /* Adaptive padding */
}

/* Breakpoints cohérents */
@media (min-width: 768px) { /* Mobile */ }
@media (min-width: 1024px) { /* Tablet */ }
@media (min-width: 1400px) { /* Desktop */ }
@media (min-width: 2000px) { /* XL - plus d'espace */ }
```

**Validation**:
```bash
# Chercher max-width fixes
grep -rn "max-width:.*px" static/*.html | grep -v "none\|95vw"
```

---

### **🟢 Priorité 4 - Documentation Inline** (Effort: 1-2h)

**Problème**: Code complexe sans docstrings (ex: hystérésis dans risk_scoring.py)

**Fichiers à documenter**:

1. **services/risk_scoring.py:186-200** - Hystérésis memecoins
```python
def _apply_memecoin_penalty(memecoins_pct: float) -> float:
    """
    Apply memecoin penalty with hysteresis to avoid flip-flop.

    Transition zone 48-52%: Linear interpolation from -10 to -15 pts
    to prevent oscillation between thresholds (Cap Stability fix).

    Args:
        memecoins_pct: Percentage of portfolio in memecoins (0.0-1.0)

    Returns:
        Penalty in points (negative value, typically -10 to -15)

    See: docs/CAP_STABILITY_FIX.md
    """
    if memecoins_pct >= 0.48 and memecoins_pct <= 0.52:
        t = (memecoins_pct - 0.48) / 0.04  # 0.0 to 1.0
        return -10 + t * (-15 - (-10))  # Smooth -10 → -15
    # ... reste
```

2. **services/execution/governance.py** - Freeze semantics
3. **static/core/allocation-engine.js** - Topdown hierarchical

---

## 🗓️ Planning Suggéré

### **Semaine 1 - Tests Critiques** (3-4 jours)

| Jour | Tâche | Durée |
|------|-------|-------|
| J1 | Tests `risk_scoring.py` | 2-3h |
| J2 | Tests `balance_service.py` | 2h |
| J3 | Tests `scheduler.py` | 1-2h |
| J4 | Review & validation | 1h |

**Livrable**: +200 lignes de tests, coverage 40% → 70%+

---

### **Semaine 2 - Formatters & UI** (2-3 jours)

| Jour | Tâche | Durée |
|------|-------|-------|
| J5 | Migrer endpoints formatters | 1-2h |
| J6 | Harmoniser max-width (4 pages) | 1h |
| J7 | Documentation inline | 1-2h |

**Livrable**: 100% endpoints uniformisés, 100% pages responsive

---

## 📊 Métriques de Succès

### Tests Unitaires

```bash
# Avant Phase 2
pytest tests/unit --cov=services/risk_scoring --cov=services/balance_service
# Coverage: ~40%

# Après Phase 2 (Cible)
pytest tests/unit --cov=services/risk_scoring --cov=services/balance_service
# Coverage: 75-80%
```

### Response Formatters

```bash
# Avant
grep -rn "return {" api/*.py | grep -v "success_response" | wc -l
# → 15-20 occurrences

# Après
grep -rn "return {" api/*.py | grep -v "success_response" | wc -l
# → 0-2 occurrences (legacy endpoints acceptables)
```

### UI Responsive

```bash
# Avant
grep -rn "max-width:.*px" static/*.html | wc -l
# → 4 occurrences

# Après
grep -rn "max-width:.*px" static/*.html | wc -l
# → 0 occurrences
```

---

## 🔧 Outils & Commandes

### Lancer Tests avec Coverage

```bash
# Test un module spécifique avec coverage
pytest tests/unit/test_risk_scoring.py -v --cov=services/risk_scoring --cov-report=html

# Ouvrir rapport HTML
start htmlcov/index.html  # Windows
```

### Trouver Endpoints Sans Formatters

```bash
# Chercher patterns raw dict return
rg "return \{['\"]ok['\"]:" api/ --type py
```

### Valider Max-Width

```bash
# Trouver max-width fixes
rg "max-width:\s*\d+px" static/ --type html
```

---

## 📚 Ressources

### Documentation Existante

- **CLAUDE.md** - Règles design & responsive
- **AUDIT_REPORT_2025-10-19.md** - Audit initial
- **TEST_MIGRATION_COMPLETE_REPORT.md** - Phase 1 résultats

### Fichiers Références

- **api/utils/formatters.py** - `success_response()`, `error_response()`
- **tests/conftest.py** - Fixtures réutilisables
- **docs/RISK_SEMANTICS.md** - Documentation Risk Score
- **docs/CAP_STABILITY_FIX.md** - Hystérésis expliquée

---

## 🚀 Quick Start - Phase 2

```bash
# 1. Créer premier test unitaire
touch tests/unit/test_risk_scoring.py

# 2. Utiliser template avec fixtures
cat > tests/unit/test_risk_scoring.py << 'EOF'
"""
Unit tests for Risk Scoring service.
Tests canonical risk score calculation with penalties and hysteresis.
"""
import pytest
from services.risk_scoring import calculate_risk_score

class TestRiskScoring:
    def test_risk_score_always_positive(self):
        """Risk score should always be between 0-100"""
        # TODO: Implement
        pass
EOF

# 3. Lancer tests
pytest tests/unit/test_risk_scoring.py -v
```

---

## 🎯 Objectif Final Phase 2

| Aspect | Avant | Après |
|--------|-------|-------|
| **Coverage tests** | 40% | **80%** |
| **Response formatters** | 85% | **100%** |
| **Pages responsive** | 75% | **100%** |
| **Code quality** | B+ | **A** |
| **Production confidence** | ⚠️ Bon | ✅ **Excellent** |

---

**Phase 2 = Transformer un système "Bon" en système "Excellent"** avec tests solides, API cohérente, et UI/UX uniformisée.

**Prêt à commencer ?** Je recommande de débuter par les tests `risk_scoring.py` (impact le plus élevé).
