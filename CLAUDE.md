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
- **Crypto** (production ready):
  - UI : `dashboard.html`, `analytics-unified.html`, `risk-dashboard.html`, `rebalance.html`, `execution.html`, `execution_history.html`
  - API : `/balances/current`, `/rebalance/plan`, `/portfolio/metrics`, `/execution/*`, `/api/ml/*`, `/api/risk/*`
- **Bourse / Saxo** (Phase 2 complétée):
  - UI : `saxo-upload.html` (import), `saxo-dashboard.html` (consultation), `analytics-equities.html` (beta)
  - API : `/api/saxo/*` (upload/positions/accounts/instruments), `/api/wealth/*` (lecture legacy active)
  - Intégration : Tuile Saxo dans `dashboard.html` avec store partagé (`wealth-saxo-summary.js`)
- **Simulateur** (production ready):
  - UI : `simulations.html` (pipeline complet Decision → Execution avec 10 presets)
  - Engine : `static/modules/simulation-engine.js`, contrôles `static/components/SimControls.js`
- **Outils/Debug** : 60+ pages test/debug disponibles (préfixe `test-*`, `debug-*`, `clear-*`)

## 2) Wealth — statut (Phase 2 complétée ✅)
- Namespace `/api/wealth/*` : **opérationnel**, endpoints disponibles, lecture legacy active
- Pages existantes : `analytics-equities.html` (beta)
- Phase 3 à venir : `risk-equities.html`, `rebalance-equities.html`
- Roadmap complète : voir `docs/TODO_WEALTH_MERGE.md`

## 3) Windows 11 — conventions pratiques
- Utiliser les scripts `.ps1`/`.bat` fournis (éviter `bash` non portable).
- Chemins : supporter Windows (éviter `touch`, préférer PowerShell).

## 4) Architecture (résumé)

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
api/main.py (auto-init ML, routers, middleware, endpoints P&L)
api/execution_endpoints.py (governance routes unifiées)
api/execution_dashboard.py (dashboard execution temps réel)
api/execution_history.py (historique exécution)
api/risk_endpoints.py (risk management unifié)
api/alerts_endpoints.py (alertes centralisées)
api/unified_ml_endpoints.py (ML unifié, orchestrateur)
api/realtime_endpoints.py (SSE/WebSocket)
api/saxo_endpoints.py (Bourse/Saxo)
api/wealth_endpoints.py (Wealth cross-asset)
api/sources_endpoints.py (Sources System v2)
api/services/sources_resolver.py (SOT résolution données)
api/services/data_router.py (Router priorité sources)
models/wealth.py (modèles Wealth cross-asset)
services/execution/governance.py (Decision Engine single-writer)
services/ml/orchestrator.py (MLOrchestrator)
services/risk_management.py
services/portfolio.py (analytics portfolio + P&L tracking)
services/analytics/*.py
services/ml/*.py
static/components/nav.js (navigation unifiée)
static/components/GovernancePanel.js (intégré dans risk-dashboard)
static/global-config.js (config endpoints)
static/dashboard.html (tuile Saxo intégrée)
static/analytics-unified.html (ML temps réel, Sources injection)
static/risk-dashboard.html (GovernancePanel intégré)
static/rebalance.html (Priority/Proportional modes)
static/execution.html + execution_history.html
static/simulations.html (simulateur pipeline complet)
static/modules/wealth-saxo-summary.js (store partagé Saxo)
static/modules/simulation-engine.js (engine déterministe)
static/components/SimControls.js (contrôles UI)
static/components/SimInspector.js (arbre explication)
static/presets/sim_presets.json (10 scénarios prédéfinis)
static/core/risk-dashboard-store.js (sync governance)
static/core/phase-engine.js (détection phases market - production)
static/core/phase-engine-new.js (nouvelle version - dev)
static/core/phase-buffers.js (ring buffers time series)
static/core/phase-inputs-extractor.js (extraction données)
static/core/unified-insights-v2.js (intégration Phase Engine - production)
static/core/unified-insights.js (legacy)
static/core/allocation-engine.js (engine allocations)
static/core/strategy-api-adapter.js (adaptateur Strategy API v3)
static/test-phase-engine.html (suite tests 16 cases)
Note: versions *-backup, *-broken, *-clean sont des archives de développement
```

---

## 5) Playbooks

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

## 6) Conventions & garde‑fous

- Python: FastAPI + Pydantic v2; exceptions propres; logs cohérents.
- JS: ESM (`type="module"`), imports dynamiques pour lourds; pas d’URL API en dur.
- CSS: variables `shared-theme.css` + compat `theme-compat.css`.
- API: `/api/...`, réponses typées; erreurs HTTP standard.
- Perf: batching, pagination, virtual scrolling (`performance-optimizer.js`).
- Sécurité headers: en dev autoriser `SAMEORIGIN` pour iframes; en prod garder une CSP stricte (frame‑ancestors).

---

## 7) Caches & cross‑tab (important)

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
- **IMPORTANT** : Dossiers `data/users/*/csv/` sont legacy et ont été supprimés (Sep 2025)
- Tous les fichiers doivent être dans `cointracking/uploads/` ou `saxobank/uploads/`

**Monitoring temps réel** :
- `refreshSaxoStaleness()` : Fonction universelle avec gestion d'erreurs
- Indicateurs couleur selon âge : vert (minutes), jaune (heures), rouge (jours/erreur)
- Polling automatique 60s sur toutes les pages Bourse/Analytics
- Fallback gracieux en cas d'échec API

### 4.4) P&L Today - Tracking par (user_id, source)

**Objectif** : Calculer le P&L (Profit & Loss) Today en comparant la valeur actuelle du portfolio avec le dernier snapshot historique.

**Architecture** (Sep 2025) :
- `services/portfolio.py` : Gestion snapshots et calcul P&L
- `data/portfolio_history.json` : Fichier unique multi-tenant avec snapshots
- Endpoints : `/portfolio/metrics` (GET), `/portfolio/snapshot` (POST)
- Frontend : `static/dashboard.html` affiche P&L Today dans tuile Portfolio Overview

**Principe de fonctionnement** :
1. **Snapshots isolés par (user_id, source)** : Chaque combinaison user/source a son propre historique
2. **Stockage** : Tous les snapshots dans un seul fichier JSON avec filtrage dynamique
3. **Calcul P&L** : `current_value - latest_snapshot_value` pour la même combinaison (user_id, source)
4. **Limite** : 365 snapshots max par combinaison (user_id, source)

**Exemples d'utilisation** :
```bash
# Créer un snapshot
curl -X POST "http://localhost:8000/portfolio/snapshot?source=cointracking&user_id=jack"

# Consulter P&L
curl "http://localhost:8000/portfolio/metrics?source=cointracking&user_id=jack"
```

**Structure snapshot** :
```json
{
  "date": "2025-09-30T13:34:39.940690",
  "user_id": "jack",
  "source": "cointracking",
  "total_value_usd": 133100.00,
  "asset_count": 5,
  "group_count": 3,
  "diversity_score": 2,
  "top_holding_symbol": "ETH",
  "top_holding_percentage": 0.56,
  "group_distribution": {...}
}
```

**IMPORTANT** :
- Un snapshot = une photo à un instant T
- P&L nécessite au moins 2 snapshots pour la même source
- Sources différentes (CSV vs API) ont des P&L indépendants
- Exemple : `jack + cointracking` (CSV 5 assets) ≠ `jack + cointracking_api` (API 190 assets)

**Fichiers modifiés** :
- `services/portfolio.py:96` : `calculate_performance_metrics()` accepte `user_id` et `source`
- `services/portfolio.py:165` : `save_portfolio_snapshot()` sauvegarde avec `user_id` et `source`
- `services/portfolio.py:350` : `_load_historical_data()` filtre par `user_id` et `source`
- `api/main.py:1857` : `/portfolio/metrics` passe `user_id` à `calculate_performance_metrics()`
- `api/main.py:1881` : `/portfolio/snapshot` accepte `user_id` et `source`
- `static/dashboard.html:1186` : Appel API avec `user_id` et `source` depuis localStorage

---

## 8) Definition of Done (DoD)

- Tests unitaires verts + smoke test d’API (si endpoint).
- Lint OK; CI verte.
- Pas de secrets ni d’URL API en dur.
- UX/Thème inchangés (sauf demande).
- Doc courte (4–8 lignes) ajoutée dans `README.md`/`docs/` si pertinent.

---

## 9) Phase Engine (Détection Proactive de Phases Market)

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

## 10) Aides‑mémoire

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

## 11) Paramétrage agent (optionnel)

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

## 12) Architecture endpoints post-refactoring (important)

**Namespaces consolidés** (ne pas créer de nouveaux) :
- `/api/ml/*` - Toutes fonctions ML (remplace /api/ml-predictions, /api/ai)
- `/api/risk/*` - Risk management unifié (/api/risk/advanced/* pour fonctions avancées)
- `/api/alerts/*` - Alertes centralisées (acknowledge, resolve)
- `/execution/governance/approve/{resource_id}` - Approbations unifiées (decisions + plans)
- `/api/saxo/*` - Endpoints Bourse/Saxo
- `/api/wealth/*` - Endpoints Wealth cross-asset (lecture legacy active)
- `/api/sources/*` - Sources System v2 (upload, scan, import, test)

**Endpoints avancés** (disponibles mais optionnels) :
- `/api/strategy/*` - Strategy API v3 (allocations dynamiques)
- `/api/intelligence/*` - Intelligence endpoints
- `/api/backtesting/*` - Backtesting historique
- `/api/multi-asset/*` - Multi-asset analytics
- `/api/portfolio-optimization/*` - Optimisation portfolio
- `/api/advanced-analytics/*` - Analytics avancés
- `/api/unified-phase3/*` - Phase 3 unifiée (experimental)

**Endpoints supprimés** (ne pas recréer) :
- `/api/test/*` et `/api/alerts/test/*` - Endpoints de test supprimés
- `/api/realtime/publish` et `/broadcast` - Supprimés pour sécurité

