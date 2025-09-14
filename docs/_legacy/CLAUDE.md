# CLAUDE.md — Guide de travail pour agents (Crypto Rebal Starter)

> But: permettre à un agent (Claude/Code) d’intervenir vite et bien sans casser l’existant
> Périmètre: FastAPI `api/`, services Python `services/`, front HTML/JS `static/`, connecteurs `connectors/`, tests `tests/`.

---

## 0) Règles d’or (strict)

1. Secrets: ne jamais lire/committer `.env` ni publier des clés.
2. Navigation/UI: conserver le menu unifié `static/components/nav.js` + thèmes `shared-theme.css`/`theme-compat.css`. Ne pas réintroduire `static/shared-header.js` (archivé).
3. Config front: aucune URL API en dur. Toujours passer par `static/global-config.js` (détection `window.location.origin`).
4. Modifs minimales: patchs ciblés, pas de refontes/renommages massifs sans demande explicite.
5. Perf: favoriser endpoints batch, cache, lazy‑loading.
6. Terminologie: garder certains anglicismes (coin, wallet, airdrop…).
7. Sécurité: valider Pydantic, limiter tailles/paginer, penser rate‑limit sur endpoints sensibles.
8. Tests: tests unitaires pour logique non triviale + smoke test d’API pour tout nouvel endpoint.

Note endpoints de test/dev:
- Les routes `/api/alerts/test/*` sont désactivées par défaut et toujours désactivées en production.
- Pour activer en dev: définir `ENABLE_ALERTS_TEST_ENDPOINTS=true` dans l’environnement (non-prod uniquement).

---

## 1) Architecture (résumé)

- API: `api/main.py` (CORS/CSP/GZip/TrustedHost, montages `/static`, `/data`, `/tests`) + routers `api/*_endpoints.py`.
- Services: `services/*` (risk mgmt, execution, analytics, ML…).
- Governance: `services/execution/governance.py` (Decision Engine single-writer) + auto-init ML dans `api/main.py` 
- Connecteurs: `connectors/cointracking*.py`, autres.
- Front: `static/*` (dashboards, `components/nav.js`, `global-config.js`, `lazy-loader.js`, modules `static/modules/*.js`, store `static/core/risk-dashboard-store.js`).
- Config: `config/settings.py` (Pydantic settings)
- Constantes: `constants/*`
- Tests: `tests/unit`, `tests/integration`, `tests/e2e` (pytest)

Fichiers clés:

```
api/main.py (auto-init ML au startup)
api/execution_endpoints.py (governance routes unifiées)
api/risk_endpoints.py
api/alerts_endpoints.py (alertes centralisées)
api/unified_ml_endpoints.py (ML unifié)
api/realtime_endpoints.py
services/execution/governance.py (Decision Engine)
services/ml/orchestrator.py (MLOrchestrator)
services/risk_management.py
services/analytics/*.py
services/ml/*.py
static/components/nav.js
static/components/GovernancePanel.js (intégré dans risk-dashboard)
static/global-config.js
static/intelligence-dashboard.html (signaux ML temps réel)
static/analytics-unified.html
static/risk-dashboard.html (avec GovernancePanel intégré)
static/portfolio-optimization.html
static/modules/*.js
static/core/risk-dashboard-store.js (sync governance)
```

---

## 2) Playbooks

### A) Ajouter un endpoint FastAPI

1) Créer `api/<module>_endpoints.py` avec schémas Pydantic, tailles limitées.
2) Inclure le router dans `api/main.py` si nécessaire.
3) Logguer latence et taille d’entrée si pertinent.
4) Ajouter un smoke test simple.

Exemple:

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

router = APIRouter(prefix="/api/example", tags=["example"])
log = logging.getLogger(__name__)

class MyResponse(BaseModel):
    results: Dict[str, Any]
    meta: Dict[str, Any]

@router.get("/compute", response_model=MyResponse)
async def compute(assets: List[str] = Query(default=[], max_items=50)):
    try:
        return MyResponse(results={a: 1 for a in assets}, meta={"ok": True})
    except Exception:
        log.exception("compute failed")
        raise HTTPException(500, "internal_error")
```

### B) Exposer une prédiction ML batch (volatilité)

Objectif: endpoint batch, latence p95 < 100 ms (CPU), lazy‑loading + LRU des modèles.

Service (ex.): `services/ml/orchestrator.py` (cache LRU, TTL d'inactivité). Endpoint dans `api/unified_ml_endpoints.py`:

```python
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from services.ml.orchestrator import predict_vol_batch

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

class VolResponse(BaseModel):
    horizon: str
    predictions: Dict[str, float]
    std: Dict[str, float] = {}

@router.get("/volatility/predict", response_model=VolResponse)
async def vol_predict(assets: List[str] = Query(..., min_items=1, max_items=50), horizon: str = Query("1d")):
    try:
        preds, std = await predict_vol_batch(assets, horizon)
        return VolResponse(horizon=horizon, predictions=preds, std=std)
    except Exception:
        raise HTTPException(500, "ml_inference_error")
```

### C) Étendre le Risk Dashboard

- Utiliser le store `static/core/risk-dashboard-store.js`.
- Ajouter/modifier KPI dans `static/risk-dashboard.html` + modules sous `static/modules/*.js`.
- Respecter le système de cache persistant (voir “Caches & cross‑tab”).

### D) Intégrations front (iframes/nav)

- Pour embarquer une page dans une autre: utiliser une URL relative + `?nav=off` et lazy‑load l’iframe au clic d’onglet.
- Ne jamais dur‑coder `localhost` dans un `src`; préférer relative ou `window.location.origin + '/static/...'`.
- Le menu unifié ne s’injecte pas si `nav=off`.

### E) Écrire des tests

- Unit: logique pure (services).
- Integration: TestClient FastAPI (pinger endpoint + vérifier schémas/contrats).
- E2E: flux complet si nécessaire (utiliser tests/e2e existants ou tests/integration).
- Smoke: `tests/smoke_test_refactored_endpoints.py` pour validation post-refactoring.

---

## 3) Conventions & garde‑fous

- Python: FastAPI + Pydantic v2; exceptions propres; logs cohérents.
- JS: ESM (`type="module"`), imports dynamiques pour lourds; pas d’URL API en dur.
- CSS: variables `shared-theme.css` + compat `theme-compat.css`.
- API: `/api/...`, réponses typées; erreurs HTTP standard.
- Perf: batching, pagination, virtual scrolling (`performance-optimizer.js`).
- Sécurité headers: en dev autoriser `SAMEORIGIN` pour iframes; en prod garder une CSP stricte (frame‑ancestors).

---

## 4) Caches & cross‑tab (important)

- Le Risk Dashboard publie des scores dans localStorage:
  - Clés simples: `risk_score_onchain`, `risk_score_risk`, `risk_score_blended`, `risk_score_ccs`, `risk_score_timestamp`.
  - Cache persistant: entrée JSON `risk_scores_cache` (TTL 12h) via `CACHE_CONFIG`.
- Dashboards consommateurs (ex. `static/dashboard.html`) doivent:
  - Lire les clés simples si récentes; sinon tomber sur `risk_scores_cache`.
  - Écouter l’événement `storage` pour se mettre à jour.

---

## 5) Definition of Done (DoD)

- Tests unitaires verts + smoke test d’API (si endpoint).
- Lint OK; CI verte.
- Pas de secrets ni d’URL API en dur.
- UX/Thème inchangés (sauf demande).
- Doc courte (4–8 lignes) ajoutée dans `README.md`/`docs/` si pertinent.

---

## 6) Aides‑mémoire

Dev:

```bash
uvicorn api.main:app --reload --port 8000
# http://localhost:8000/static/analytics-unified.html
# http://localhost:8000/static/risk-dashboard.html
```

Tests:

```bash
pytest -q tests/unit
pytest -q tests/integration
python tests/smoke_test_refactored_endpoints.py
```

Docker:

```bash
docker build -t crypto-rebal .
docker run -p 8000:8000 --env-file .env crypto-rebal
```

---

## 7) Paramétrage agent (optionnel)

`.claude/settings.local.json` (déjà présent) doit inclure au minimum:

```json
{
  "readme": true,
  "include": [
    "CLAUDE.md",
    "CONFIGURATION.md",
    "README.md",
    "api/**",
    "services/**",
    "static/components/nav.js",
    "static/global-config.js",
    "static/analytics-unified.html",
    "static/risk-dashboard.html",
    "static/modules/**",
    "tests/unit/**"
  ],
  "exclude": ["**/.env", "**/data/**", "**/.ruff_cache/**"]
}
```

---

## 8) Architecture endpoints post-refactoring (important)

**Namespaces consolidés** (ne pas créer de nouveaux) :
- `/api/ml/*` - Toutes fonctions ML (remplace /api/ml-predictions, /api/ai)
- `/api/risk/*` - Risk management unifié (/api/risk/advanced/* pour fonctions avancées)
- `/api/alerts/*` - Alertes centralisées (acknowledge, resolve)
- `/api/governance/approve/{resource_id}` - Approbations unifiées (decisions + plans)

**Endpoints supprimés** (ne pas recréer) :
- `/api/test/*` et `/api/alerts/test/*` - Endpoints de test supprimés
- `/api/realtime/publish` et `/broadcast` - Supprimés pour sécurité
- `/api/advanced-risk/*` - Déplacé vers `/api/risk/advanced/*`

**Sécurité** :
- ML debug `/api/ml/debug/*` nécessite header `X-Admin-Key`
- Pas d'endpoints de test en production

**Dashboard existants** :
- `intelligence-dashboard.html` (pas ai-dashboard.html)
- GovernancePanel intégré dans `risk-dashboard.html` (ne pas créer séparément)

---

## 9) Notes spécifiques

- Réutiliser les patterns existants (cache, modèles Pydantic, `global-config.js`).
- Préférer nowcasting simple pour corrélations (fenêtre ~90j) avant des modèles séquentiels.
- Pour l'optimisation portefeuille, éviter d'exposer des chemins absolus; respecter `api_base_url` et `?nav=off`.

