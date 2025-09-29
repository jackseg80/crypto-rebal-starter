# CLAUDE.md — Guide de travail pour agents (Crypto Rebal Starter)

> Objectif : permettre à un agent (Claude/Code) d’intervenir vite et bien **sur l’état ACTUEL** du repo.
> Périmètre: FastAPI `api/`, services Python `services/`, front HTML/JS `static/`, connecteurs `connectors/`, tests `tests/`.

---

## 0) Règles d’or (strict)
1. Secrets: ne jamais committer `.env`/clés.
2. Navigation/UI: **ne pas inventer** de nouvelles pages; travailler avec **celles existantes**.
3. Config front: aucune URL API en dur → `static/global-config.js`.
4. Modifs minimales: patchs ciblés, pas de refontes/renommages massifs sans demande explicite.
5. Perf: attention aux appels répétés; privilégier caches/ETag si dispo.

## 1) Aujourd'hui : quelles pages/endpoints utiliser ?
- **Crypto** :
  - UI : `dashboard.html`, `analytics-unified.html`, `risk-dashboard.html`, `rebalance.html`
  - API : `/balances/current`, `/rebalance/plan`, `/portfolio/metrics`, …
- **Bourse / Saxo** :
  - UI : `saxo-upload.html` (import), `saxo-dashboard.html` (consultation)
  - API : `/api/saxo/*` (upload/positions/accounts/instruments …)

## 2) Wealth — statut
- Namespace `/api/wealth/*` : **en cours**, ne pas basculer par défaut.
- Ne pas créer `analytics-equities.html` / `risk-equities.html` / `rebalance-equities.html` sans instruction explicite.
- Pour la cible à venir : lire `docs/TODO_WEALTH_MERGE.md`.

## 2) Windows 11 — conventions pratiques
- Utiliser les scripts `.ps1`/`.bat` fournis (éviter `bash` non portable).
- Chemins : supporter Windows (éviter `touch`, préférer PowerShell).

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
  - Écouter l'événement `storage` pour se mettre à jour.

### 4.1) Sources System - Store Injection & Fallback

**Problème résolu (Sep 2025)** : Race condition entre injection store et getCurrentAllocationByGroup causant $0 dans "Objectifs Théoriques".

**Solution implémentée** :
- `analytics-unified.html` : Injection forcée des données dans `window.store` avec logs détaillés
- `UnifiedInsights.js` : Fallback robuste Store → API → loadBalanceData avec retry pattern
- Cache invalidation : Ne pas retourner `_allocCache.data` si `grand = 0`
- Cache bust dynamique : Import avec `?v=${timestamp}` pour forcer rechargement modules

**Architecture de fallback** :
1. **Store immediate** : Lecture directe `store.get('wallet.balances')`
2. **Store retry** : 3 tentatives × 500ms si données pas encore injectées
3. **API fallback** : `/balances/current` si store vide (peut 429)
4. **loadBalanceData** : Cache legacy en dernier recours

### 4.2) Sources System v2 - Architecture Unifiée

**Composants principaux** :
- `api/services/sources_resolver.py` : SOT unique pour résolution des chemins de données
- `api/services/data_router.py` : Router avec priorité Sources First
- `api/sources_endpoints.py` : Endpoints upload, scan, import, test
- `static/sources-manager.js` : Interface utilisateur complète

**Priorité de résolution** : snapshots → imports → legacy → API → stub

**Fonctionnalités avancées** :
- Upload de fichiers avec validation par module (CSV, JSON, XLSX)
- Test de sources en temps réel avec feedback détaillé
- Sélection active de sources avec sauvegarde automatique
- Scan et import automatisés par module
- Interface dépréciée pour l'ancien système (lecture seule)

### 4.3) Sources System - Finition UX & Legacy Cleanup

**Migration UI complète** (Sep 2025) :
- Suppression définitive des boutons import legacy (`saxo-upload.html`)
- Bandeaux staleness temps réel avec polling 60s et indicateurs visuels
- Ancien onglet "Source" complètement masqué (`display: none`)
- Navigation unifiée vers `settings.html#tab-sources`

**Détection legacy étendue** :
- Patterns legacy automatiques : `csv/CoinTracking*.csv`, `csv/saxo*.csv`, `csv/positions*.csv`
- Marquage `is_legacy=true` dans `/api/sources/list`
- Priorité dans `effective_path` : legacy files → autres fichiers détectés
- Compatibilité totale avec fichiers utilisateurs existants

**Monitoring temps réel** :
- `refreshSaxoStaleness()` : Fonction universelle avec gestion d'erreurs
- Indicateurs couleur selon âge : vert (minutes), jaune (heures), rouge (jours/erreur)
- Polling automatique 60s sur toutes les pages Bourse/Analytics
- Fallback gracieux en cas d'échec API

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

