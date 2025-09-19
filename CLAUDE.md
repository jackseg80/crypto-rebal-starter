# CLAUDE.md — Guide de travail pour agents (Crypto Rebal Starter)

> But: permettre à un agent (Claude/Code) d’intervenir vite et bien sans casser l’existant  
> Périmètre: FastAPI `api/`, services Python `services/`, front HTML/JS `static/`, connecteurs `connectors/`, tests `tests/`.

---

## 0) Règles d’or (strict)

1. Secrets: ne jamais lire/committer `.env` ni publier des clés.
2. Navigation/UI: conserver le menu unifié `static/components/nav.js` + thèmes `shared-theme.css`/`theme-compat.css`. Ne pas réintroduire `static/shared-header.js` (archivé).
3. Config front: aucune URL API en dur. Toujours passer par `static/global-config.js` (détection `window.location.origin`).
4. Modifs minimales: patchs ciblés, pas de refontes/renommages massifs sans demande explicite.
5. Perf: favoriser endpoints batch, cache, lazy-loading.
6. Terminologie: garder certains anglicismes (coin, wallet, airdrop…).
7. Sécurité: valider Pydantic, limiter tailles/paginer, penser rate-limit sur endpoints sensibles.
8. Tests: tests unitaires pour logique non triviale + smoke test d’API pour tout nouvel endpoint.
9. **Realtime (sécurité)**: `api/realtime_endpoints.py` ne doit fournir que des flux **read-only** (SSE/WS).  
   **Interdit** d’ajouter `/realtime/publish` et `/broadcast`.  
   Toute écriture d’événements temps réel se fait côté serveur via la gouvernance.
10. **GovernancePanel**: déjà intégré dans `static/risk-dashboard.html`. **Ne pas créer** de panneau standalone ni le dupliquer.

Note endpoints de test/dev:  
- Les routes `/api/alerts/test/*` sont désactivées par défaut et toujours désactivées en production.  
- Pour activer en dev: définir `ENABLE_ALERTS_TEST_ENDPOINTS=true` dans l’environnement (non-prod uniquement).

## 0bis) Environnement Windows (important)

- OS cible : **Windows 11**
- Shell : **PowerShell** (pas Bash)
- Environnement Python : `.\.venv\Scripts\activate` (et pas `. ./venv/bin/activate`)
- Commandes à utiliser :
  - Copier : `copy` (ou `cp` via PowerShell Core, mais préférer `copy`)
  - Supprimer : `Remove-Item` (au lieu de `rm`)
  - Lister fichiers : `dir` (au lieu de `ls`)
- Chemins : utiliser `\` (ex. `D:\Python\crypto-rebal-starter`) et pas `/`.
- Encodage : UTF-8 simple, éviter les caractères spéciaux non supportés dans les noms de fichiers Windows.

---

## 1) Architecture (résumé)

- API: `api/main.py` (CORS/CSP/GZip/TrustedHost, montages `/static`, `/data`, `/tests`) + routers `api/*_endpoints.py`.
- Services: `services/*` (risk mgmt, execution, analytics, ML…).
- Governance: `services/execution/governance.py` (Decision Engine single-writer) + auto-init ML dans `api/main.py` 
- Connecteurs: `connectors/cointracking*.py`, autres.
- Front: `static/*` (dashboards, `components/nav.js`, `global-config.js`, `lazy-loader.js`, modules `static/modules/*.js`, store `static/core/risk-dashboard-store.js`)
- Simulateur: `static/simulations.html` + `modules/simulation-engine.js` + `components/SimControls.js` + `presets/sim_presets.json`
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
services/analytics/.py
services/ml/.py
static/components/nav.js
static/components/GovernancePanel.js (intégré dans risk-dashboard)
static/global-config.js
static/analytics-unified.html (section ML temps réel)
static/risk-dashboard.html (avec GovernancePanel intégré)
static/portfolio-optimization.html
static/simulations.html (simulateur pipeline complet)
static/modules/*.js
static/modules/simulation-engine.js (engine simulation avec fixes deterministes)
static/components/SimControls.js (controles UI)
static/components/SimInspector.js (arbre explication)
static/presets/sim_presets.json (10 scenarios predefinis)
static/core/risk-dashboard-store.js (sync governance)
static/core/phase-engine.js (détection de phases market)
static/core/phase-buffers.js (ring buffers pour time series)
static/core/phase-inputs-extractor.js (extraction données phases)
static/core/unified-insights-v2.js (intégration Phase Engine)
static/test-phase-engine.html (suite de tests complète)
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

## 6) Phase Engine (Détection Proactive de Phases Market)

**Objectif :** Appliquer des tilts d'allocation proactifs selon les phases market détectées (ETH expansion, altseason, risk-off).

### Architecture
- **`static/core/phase-engine.js`** : Core détection & tilts logic
- **`static/core/phase-buffers.js`** : Ring buffers time series (60 samples max)
- **`static/core/phase-inputs-extractor.js`** : Extraction données normalized
- **`static/test-phase-engine.html`** : Suite tests complète (16 test cases)

### Modes
- **Off** : Phase Engine désactivé
- **Shadow** (défaut) : Détection + logs, objectifs inchangés
- **Apply** : Détection + application réelle des tilts

### Contrôles Debug (localhost uniquement)
```javascript
// Forcer une phase pour tests
window.debugPhaseEngine.forcePhase('eth_expansion')
window.debugPhaseEngine.forcePhase('full_altseason')
window.debugPhaseEngine.forcePhase('risk_off')
window.debugPhaseEngine.clearForcePhase() // Normal detection

// État actuel
window.debugPhaseEngine.getCurrentForce()
window._phaseEngineAppliedResult // Résultats détaillés
```

### Phases & Tilts
- **Risk-off** : Stables +15%, alts -15% à -50%
- **ETH Expansion** : ETH +5%, L2/Scaling +3%, stables -2%
- **Large-cap Altseason** : L1/majors +8%, SOL +6%, Others +20%
- **Full Altseason** : Memecoins +150%, Others +100%, stables -15%
- **Neutral** : Aucun tilt

### Feature Flags
```javascript
// Changer le mode
localStorage.setItem('PHASE_ENGINE_ENABLED', 'shadow') // ou 'apply', 'off'
localStorage.setItem('PHASE_ENGINE_DEBUG_FORCE', 'eth_expansion') // Force phase
```

---

## 7) Aides‑mémoire

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
    "docs/configuration.md",
    "README.md",
    "docs/**/*.md",
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
- `/execution/governance/approve/{resource_id}` - Approbations unifiées (decisions + plans)

**Endpoints supprimés** (ne pas recréer) :
- `/api/test/*` et `/api/alerts/test/*` - Endpoints de test supprimés
- `/api/realtime/publish` et `/broadcast` - Supprimés pour sécurité

