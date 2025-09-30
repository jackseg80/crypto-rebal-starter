# CLAUDE.md — Guide de travail pour agents (Crypto Rebal Starter)

> Objectif : permettre à un agent (Claude/Code) d’intervenir vite et bien **sur l’état ACTUEL** du repo.
> Périmètre: FastAPI `api/`, services Python `services/`, front HTML/JS `static/`, connecteurs `connectors/`, tests `tests/`.

---

## 0) Règles d'or (strict)
1. Secrets: ne jamais committer `.env`/clés.
2. Navigation/UI: **ne pas inventer** de nouvelles pages; travailler avec **celles existantes**.
3. Config front: aucune URL API en dur → `static/global-config.js`.
4. Modifs minimales: patchs ciblés, pas de refontes/renommages massifs sans demande explicite.
5. Perf: attention aux appels répétés; privilégier caches/ETag si dispo.
6. **Sémantique Risk** : Risk est un score **positif** (0..100, plus haut = mieux). **Ne jamais inverser** avec `100 - risk` dans les calculs ou visualisations.

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

## 3) Système Multi-Utilisateurs (CRITIQUE ⚠️)

**LE PROJET EST MULTI-TENANT** — Ne JAMAIS coder comme s'il n'y avait qu'un seul utilisateur !

### Architecture Complète

**Frontend (localStorage)** :
- `localStorage.getItem('activeUser')` → ID utilisateur actif (défaut: 'demo')
- Sélecteur dans `static/components/nav.js` → dropdown en haut de chaque page
- Liste users dans `config/users.json` : demo, jack, donato, elda, roberto, clea
- Changement user → purge caches + reload page automatique

**Backend (isolation filesystem)** :
- `api/services/user_fs.py` → `UserScopedFS` classe de sécurité
- Chaque user a son dossier : `data/users/{user_id}/`
- Structure par user :
  ```
  data/users/{user_id}/
    ├── cointracking/
    │   ├── uploads/       # CSV uploadés
    │   ├── imports/       # CSV validés/importés
    │   └── snapshots/     # Snapshots actifs (latest.csv)
    ├── saxobank/
    │   ├── uploads/
    │   ├── imports/
    │   └── snapshots/
    └── config.json        # Config user (data_source, api_keys, etc.)
  ```

**Clé primaire partout** : `(user_id, source)`
- `source` = type de données : "cointracking" (CSV), "cointracking_api" (API externe), "saxobank", etc.
- **Exemple** : jack a 2 portefeuilles complètement séparés :
  - `jack + cointracking` (CSV local, 5 assets, 133k USD)
  - `jack + cointracking_api` (API CoinTracking réelle, 190 assets, 423k USD)

### Règles pour le Code

**1. Endpoints API** : TOUJOURS accepter `user_id` comme paramètre Query
```python
@app.get("/portfolio/metrics")
async def portfolio_metrics(
    source: str = Query("cointracking"),
    user_id: str = Query("demo")  # ← OBLIGATOIRE
):
    res = await resolve_current_balances(source=source, user_id=user_id)
```

**2. Services Python** : Passer `user_id` à toutes les fonctions de données
```python
def calculate_performance_metrics(
    self,
    current_data: Dict[str, Any],
    user_id: str = "demo",  # ← OBLIGATOIRE
    source: str = "cointracking"
):
    historical_data = self._load_historical_data(user_id=user_id, source=source)
```

**3. Frontend** : Lire `activeUser` depuis localStorage
```javascript
const activeUser = localStorage.getItem('activeUser') || 'demo';
const url = `/api/endpoint?source=${source}&user_id=${activeUser}`;
```

**4. Fichiers partagés multi-tenant** : Filtrer par `user_id` et `source`
```python
# Exemple: data/portfolio_history.json contient tous les users
def _load_historical_data(self, user_id: str, source: str):
    all_data = json.load(open('data/portfolio_history.json'))
    return [e for e in all_data
            if e.get('user_id') == user_id
            and e.get('source') == source]
```

### Fonction Unifiée de Chargement (OBLIGATOIRE)

**⚠️ CRITIQUE:** TOUJOURS utiliser `window.loadBalanceData()` pour charger les données de portfolio!

**Pourquoi?**
- ✅ Gère automatiquement le header `X-User` (isolation multi-tenant)
- ✅ Cache intelligent par user (TTL 2 minutes)
- ✅ Support transparent CSV + API
- ✅ Fallback robuste en cas d'erreur

**Exemple correct (dashboard.html, risk-dashboard.html, simulations.html):**
```javascript
const activeUser = localStorage.getItem('activeUser') || 'demo';
const balanceResult = await window.loadBalanceData(true); // forceRefresh=true

// Parse selon format
let balances;
if (balanceResult.csvText) {
  // CSV source
  balances = parseCSVBalancesAuto(balanceResult.csvText, { thresholdUSD: minThreshold });
} else if (balanceResult.data?.items) {
  // API source
  balances = balanceResult.data.items;
}
```

**❌ NE JAMAIS faire de fetch() direct:**
```javascript
// ❌ MAUVAIS - Ne passe pas X-User correctement
const response = await fetch(`/balances/current?source=${source}&user_id=${userId}`);
```

**Détails techniques:** Voir [docs/SIMULATOR_USER_ISOLATION_FIX.md](docs/SIMULATOR_USER_ISOLATION_FIX.md)

### Pièges Fréquents (À ÉVITER !)

❌ **Oublier user_id dans endpoint** → toujours user 'demo' par défaut
❌ **Hardcoder user_id = 'demo'** dans le code
❌ **Mélanger données de différents users** dans caches/fichiers
❌ **Ne pas filtrer par (user_id, source)** lors de lecture données partagées
❌ **Faire fetch() direct au lieu d'utiliser window.loadBalanceData()** (Sept 2025 fix)

### Tests Multi-User

```bash
# Tester avec différents users
curl "http://localhost:8000/balances/current?source=cointracking&user_id=demo"
curl "http://localhost:8000/balances/current?source=cointracking&user_id=jack"

# Vérifier isolation
curl "http://localhost:8000/portfolio/metrics?source=cointracking&user_id=jack"
curl "http://localhost:8000/portfolio/metrics?source=cointracking_api&user_id=jack"
# ↑ Doivent retourner données DIFFÉRENTES (portfolios distincts)
```

### Ajout Nouveau User

1. Ajouter dans `config/users.json` :
```json
{"id": "nouveau_user", "label": "Nouveau User"}
```

2. Le dossier `data/users/nouveau_user/` sera créé automatiquement par `UserScopedFS`

3. Uploader fichiers CSV via Sources Manager ou déposer dans `data/users/nouveau_user/cointracking/uploads/`

---

## 4) Environnement virtuel Python (.venv)

**OBLIGATOIRE** : Toujours travailler dans l'environnement virtuel `.venv` pour l'isolation des dépendances.

### Activation
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate
```

### Installation dépendances
```bash
# Activer .venv d'abord, puis :
pip install -r requirements.txt

# Ou installer un package spécifique :
pip install <package-name>
```

### Vérification
```bash
# Vérifier que .venv est actif (prompt doit afficher (.venv))
python --version
pip list
```

### Commandes courantes
```bash
# Lancer le serveur (avec .venv activé)
python -m uvicorn api.main:app --reload --port 8000

# Ou utiliser le script fourni
.\start-dev.ps1  # Windows
./start-dev.sh   # Linux/Mac

# Tests (avec .venv activé)
pytest -q tests/unit
pytest -q tests/integration
```

**IMPORTANT** :
- Ne jamais installer de packages en dehors de `.venv`
- Toujours activer `.venv` avant toute commande Python/pip
- Le dossier `.venv/` est exclu du Git (voir `.gitignore`)
- Recréer `.venv` si corrompu : `python -m venv .venv`

---

## 5) Windows 11 — conventions pratiques
- Utiliser les scripts `.ps1`/`.bat` fournis (éviter `bash` non portable).
- Chemins : supporter Windows (éviter `touch`, préférer PowerShell).
- **Toujours activer `.venv` avant de travailler** (voir section précédente).

## 6) Architecture (résumé)

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
static/components/decision-index-panel.js (panneau DI réutilisable Chart.js)
static/components/decision-index-panel.css (style compact dark mode)
static/components/UnifiedInsights.js (intégration DI + weights post-adaptatifs)
static/global-config.js (config endpoints)
static/dashboard.html (tuile Saxo intégrée)
static/analytics-unified.html (ML temps réel, Sources injection, panneau DI)
static/risk-dashboard.html (GovernancePanel intégré)
static/rebalance.html (Priority/Proportional modes)
static/execution.html + execution_history.html
static/simulations.html (simulateur pipeline complet, panneau DI)
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
static/modules/simulation-engine.js (réplique unified-insights-v2 - aligné Sep 2025)
static/test-phase-engine.html (suite tests 16 cases)
Note: versions *-backup, *-broken, *-clean sont des archives de développement
Note: simulation-engine.js maintient la parité avec unified-insights-v2.js (voir docs/SIMULATION_ENGINE_ALIGNMENT.md)
```

---

## 7) Playbooks

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
- Respecter le système de cache persistant (voir "Caches & cross‑tab").

### D) Utiliser le panneau Decision Index

**Objectif** : Afficher DI + contributions + sparkline dans analytics/simulations.

**Composant** : `static/components/decision-index-panel.js` + `.css`

**Règles critiques** :
1. **Formule contributions** : `(weight × score) / Σ(weight × score)` — **PAS d'inversion Risk**
2. **Weights post-adaptatifs** : Passer les poids APRÈS adjustements (ex: Cycle≥90 → wCycle=0.65)
3. **Sparkline** : N'affiche que si `history.length ≥ 6` (sinon placeholder)
4. **Labels barre** : Affichés si segment ≥10% ET ≥52px largeur
5. **Tooltip** : Format complet `Cycle — 83.1% (score 100, w 0.65, w×s 65.0)`

**Exemple intégration** :
```javascript
import { renderDecisionIndexPanel } from './components/decision-index-panel.js';

const data = {
  di: 65,
  weights: { cycle: 0.65, onchain: 0.25, risk: 0.10 },  // Post-adaptatifs
  scores: { cycle: 100, onchain: 41, risk: 57 },
  history: [60, 62, 65, 67, 65],  // < 6 → placeholder
  meta: {
    confidence: 0.82,
    contradiction: 0.15,
    cap: 0.15,
    mode: 'Priority',
    source: 'V2',
    live: true
  }
};

const container = document.getElementById('di-container');
renderDecisionIndexPanel(container, data);
```

**Injection weights dans unified-insights-v2.js** (lignes 357-362, 388-392) :
```javascript
decision.weights = {
  cycle: adaptiveWeights.wCycle,
  onchain: adaptiveWeights.wOnchain,
  risk: adaptiveWeights.wRisk
};
```

**Normalisation clés dans UnifiedInsights.js** (lignes 1206-1219) :
```javascript
const weights = {
  cycle:   (eff && (eff.cycle   ?? eff.wCycle))   ?? 0.5,
  onchain: (eff && (eff.onchain ?? eff.wOnchain)) ?? 0.3,
  risk:    (eff && (eff.risk    ?? eff.wRisk))    ?? 0.2,
};
```

### E) Intégrations front (iframes/nav)

- Pour embarquer une page dans une autre: utiliser une URL relative + `?nav=off` et lazy‑load l'iframe au clic d'onglet.
- Ne jamais dur‑coder `localhost` dans un `src`; préférer relative ou `window.location.origin + '/static/...'`.
- Le menu unifié ne s'injecte pas si `nav=off`.

### F) Écrire des tests

- Unit: logique pure (services).
- Integration: TestClient FastAPI (pinger endpoint + vérifier schémas/contrats).
- E2E: flux complet si nécessaire (utiliser tests/e2e existants ou tests/integration).
- Smoke: `tests/smoke_test_refactored_endpoints.py` pour validation post-refactoring.

---

## 8) Conventions & garde‑fous

- Python: FastAPI + Pydantic v2; exceptions propres; logs cohérents.
- JS: ESM (`type="module"`), imports dynamiques pour lourds; pas d’URL API en dur.
- CSS: variables `shared-theme.css` + compat `theme-compat.css`.
- API: `/api/...`, réponses typées; erreurs HTTP standard.
- Perf: batching, pagination, virtual scrolling (`performance-optimizer.js`).
- Sécurité headers: en dev autoriser `SAMEORIGIN` pour iframes; en prod garder une CSP stricte (frame‑ancestors).

---

## 9) Caches & cross‑tab (important)

- Le Risk Dashboard publie des scores dans localStorage:
  - Clés simples: `risk_score_onchain`, `risk_score_risk`, `risk_score_blended`, `risk_score_ccs`, `risk_score_timestamp`.
  - Cache persistant: entrée JSON `risk_scores_cache` (TTL 12h) via `CACHE_CONFIG`.
- Dashboards consommateurs (ex. `static/dashboard.html`) doivent:
  - Lire les clés simples si récentes; sinon tomber sur `risk_scores_cache`.
  - Écouter l'événement `storage` pour se mettre à jour.

### 9.1) Sources System - Store Injection & Fallback

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

### 9.2) Sources System v2 - Architecture Unifiée

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

### 9.3) Sources System - Finition UX & Legacy Cleanup

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

### 9.4) P&L Today - Tracking par (user_id, source)

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

## 10) Definition of Done (DoD)

- Tests unitaires verts + smoke test d’API (si endpoint).
- Lint OK; CI verte.
- Pas de secrets ni d’URL API en dur.
- UX/Thème inchangés (sauf demande).
- Doc courte (4–8 lignes) ajoutée dans `README.md`/`docs/` si pertinent.

---

## 11) Phase Engine (Détection Proactive de Phases Market)

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

## 12) Aides‑mémoire

Dev:

```bash
# TOUJOURS activer .venv d'abord (voir section 4)
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Puis lancer le serveur
uvicorn api.main:app --reload --port 8000
# http://localhost:8000/static/analytics-unified.html
# http://localhost:8000/static/risk-dashboard.html
```

Tests:

```bash
# TOUJOURS activer .venv d'abord
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Puis lancer les tests
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

## 13) Paramétrage agent (optionnel)

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

## 14) Architecture endpoints post-refactoring (important)

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

