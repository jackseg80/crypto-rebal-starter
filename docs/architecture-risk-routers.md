# Architecture Risk Routers - Séparation Intentionnelle

## Vue d'ensemble

Le domaine `/api/risk/*` est géré par **2 fichiers distincts** avec le **même prefix**.

```
/api/risk/*
├── risk_endpoints.py (prefix="/api/risk", tags=["risk-management"])
│   ├── GET /status          → Basic health check
│   ├── GET /metrics         → Portfolio risk metrics (VaR, CVaR, etc.)
│   ├── GET /correlation     → Correlation matrix & diversification
│   └── GET /stress-test/*   → Stress testing scenarios
│       ├── GET /stress-test/{scenario}
│       └── POST /stress-test/custom
│
└── risk_dashboard_endpoints.py (prefix="/api/risk", tags=["risk-management"])
    └── GET /dashboard       → Complex dashboard endpoint (331 lines)
                                - Real portfolio data resolution
                                - Price history loading (365+ days)
                                - Data quality validation
                                - Fallback strategies
                                - Centralized metrics calculation
```

## Pourquoi 2 fichiers ?

### ✅ **Raisons valides**

1. **Complexité isolée** : `/dashboard` contient 331 lignes de logique métier complexe
   - Helpers internes : `build_low_quality_dashboard()`, `_get_top_correlations()`
   - Constantes dédiées : `MIN_HISTORY_DAYS`, `COVERAGE_THRESHOLD`, `MIN_POINTS_FOR_METRICS`
   - Gestion data quality avec fallbacks multiples

2. **Responsabilités séparées**
   - `risk_endpoints.py` : Métriques de risque stateless (calculs purs)
   - `risk_dashboard_endpoints.py` : Orchestration stateful (lecture CSV, validation, agrégation)

3. **Aucun conflit de paths**
   - Tous les paths sont différents (`/status`, `/metrics`, `/dashboard`, `/stress-test/*`)
   - FastAPI monte les 2 routers sans collision

### ⚠️ **Inconvénients connus**

1. **OpenAPI confusion** : 2 tags identiques `["risk-management"]`
2. **Maintenance** : Devoir choisir où ajouter un nouveau endpoint `/api/risk/*`
3. **Import circulaire potentiel** : `risk_dashboard` importe `risk_manager` de `services/`

## Architecture recommandée (non implémentée)

### Option A: Sub-router sans prefix

```python
# risk_endpoints.py (canonical)
from fastapi import APIRouter
from .risk_dashboard_endpoints import router as dashboard_router

router = APIRouter(prefix="/api/risk", tags=["risk-management"])

@router.get("/status")
async def status(): ...

@router.get("/metrics")
async def metrics(): ...

router.include_router(dashboard_router)  # Monte le sub-router


# risk_dashboard_endpoints.py (sub-router)
from fastapi import APIRouter

router = APIRouter()  # Pas de prefix ici

@router.get("/dashboard")
async def dashboard(): ...
```

**Bénéfices:**
- ✅ Un seul tag OpenAPI
- ✅ Point d'entrée clair (`risk_endpoints.py`)
- ✅ Séparation logique préservée

### Option B: Prefix différent

```python
# risk_dashboard_endpoints.py
router = APIRouter(prefix="/api/risk/advanced", tags=["risk-dashboard"])
```

**Bénéfices:**
- ✅ Séparation visuelle claire
- ✅ Tags OpenAPI distincts
- ❌ URL change (breaking change)

## Statut actuel

**Décision** : Garder les 2 fichiers tel quel pour l'instant.

**Raison** : Le refactoring Option A nécessite:
1. Tester les 331 lignes de logique dashboard
2. Vérifier qu'aucun import circulaire n'apparaît
3. Valider que les tests existants passent

**ROI** : Faible (pas de bug, juste dette architecturale mineure)

## Références

- Commit 2de5a53: Analytics router dupliqué supprimé (cas différent)
- Audit externe Sept 2025: Recommandation de merge rejetée
- `api/main.py:1787-1788`: Montage des 2 routers

---

**Dernière mise à jour** : 2025-09-30
**Auteur** : Audit architecture cleanup