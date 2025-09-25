# AGENTS.md — Guide de travail pour agents (Crypto Rebal Starter)

Ce fichier est injecté automatiquement dans chaque prompt que Codex (ou autre agent code) reçoit.
Il définit les conventions, règles et fichiers clés du projet pour que l’agent produise un travail cohérent, sécurisé et adapté à l’environnement Windows 11.

---

## 0) Règles d’or

- Pas de secrets ni clés dans le code généré.
- Pas d’URL en dur pour les APIs → utiliser `static/global-config.js`.
- Pas de refactor massif : proposer uniquement des patchs/diffs minimaux, jamais des fichiers entiers.
- Ne pas renommer de fichiers sans demande explicite.
- Respect des perfs : batching, pagination, caches locaux.
- Tests obligatoires si du code backend est modifié.
- Sécurité : pas de nouveaux endpoints sensibles (`/realtime/publish`, `/broadcast`, etc.).

---

## 0bis) Environnement Windows (important)

- OS cible : Windows 11
- Shell : PowerShell (pas Bash)
- Environnement Python :
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- Versions minimales : Python >= 3.11, FastAPI >= 0.110, Pydantic >= 2.5

### Commandes utiles (PowerShell)

```powershell
# Lancer l’API
uvicorn api.main:app --reload --port 8000

# Accès front
http://localhost:8000/static/analytics-unified.html
http://localhost:8000/static/risk-dashboard.html

# Lancer les tests rapides
python -m pytest -q tests/unit
python -m pytest -q tests/integration
python tests\smoke_test_refactored_endpoints.py

# Créer une archive du projet
Compress-Archive -Path .\* -DestinationPath .\crypto-rebal-starter.zip -Force -Exclude .venv,**\__pycache__\,**\.ruff_cache\,**\*.tmp
```

### Wealth / Saxo
- Module Saxo = WIP (non bloquant).
- Ne pas lier à la navigation prod, limiter aux tests ciblés.

---

## 1) Stack technique

- Backend : FastAPI + Pydantic v2, orchestrateur ML en Python.
- Frontend : HTML statiques (`static/*.html`), JS ESM modules, Chart.js.
- ML : PyTorch, modèles stockés dans `services/ml`.
- Tests : Pytest, smoke tests PowerShell.
- Infra : Docker, Postgres, Redis (caching).

---

## 2) Fichiers clés

- `api/main.py` — routes FastAPI
- `services/ml/*` — modèles ML, orchestrateur
- `services/risk/*` — calculs risque
- `static/analytics-unified.html` — dashboard principal
- `static/risk-dashboard.html` — risk dashboard
- `static/modules/*` — modules front (risk, cycle, phase, on-chain)
- `static/global-config.js` — config endpoints
- `tests/*` — tests unitaires/intégration
- `tests\wealth_smoke.ps1` — smoke test Saxo/Wealth

---

## 3) Conventions & garde-fous

- Backend : exceptions propres, logs cohérents, pas d’URL en dur.
- Frontend : imports ESM (`type="module"`), imports dynamiques pour modules lourds.
- Styles : respecter la charte (Chart.js, `shared-theme.css`, `performance-optimizer.js`).
- CI : lint (ruff/black), mypy → tout doit passer en vert.

### Style de sortie attendu de l’agent
- Toujours produire des diffs unifiés (`git diff`) ou patchs minimaux.
- Jamais de dump complet de fichiers.
- Pas de commandes Bash, uniquement PowerShell.
- Réutiliser les namespaces existants (`/api/ml/*`, `/api/risk/*`, `/api/alerts/*`, `/execution/governance/*`).
- Interdiction d’ajouter `/realtime/publish` ou `/broadcast`.

---

## 4) Endpoints

### Endpoints actifs
- `/api/ml/*` — modèles ML (volatilité, décision, signaux, etc.)
- `/api/risk/*` — calculs de risque
- `/api/alerts/*` — alertes utilisateurs
- `/execution/governance/*` — gouvernance

### Endpoints supprimés (ne pas recréer)
- `/api/test/*`

### Endpoints de test (dev seulement, protégés)
- `/api/alerts/test/*` — disponibles uniquement en dev/staging, désactivés par défaut, activables via `ENABLE_ALERTS_TEST_ENDPOINTS=true` (toujours off en prod).

---

## 5) Realtime (lecture seule)

- Canaux supportés : SSE / WebSocket
- Topics autorisés (read-only) :
  - Risk scores (blended, CCS, on-chain)
  - Decision index
  - Phase engine state
- Pas d’écriture côté client (publish/broadcast interdits).

---

## 6) Caches & cross-tab

- Risk Dashboard publie des scores dans `localStorage`.
- Les dashboards doivent :
  - Lire les clés si récentes, sinon fallback `risk_scores_cache`.
  - Écouter l’événement `storage` pour la synchro cross-tab.
- TTL recommandé : 12h.
- Éviter les re-fetch permanents si le TTL reste valide.

---

## 7) Modèles ML & Registry

- Lazy-load avec LRU/TTL via `services/ml/orchestrator.py`.
- Schéma de réponse attendu :
  ```json
  {
    "predictions": {...},
    "std": {...},
    "horizon": "1d"
  }
  ```
- Pas de poids dans le repo : chargement depuis un dossier local prévu.

---

## 8) Phase Engine (Détection proactive des phases de marché)

- Phases possibles : Bull, Bear, Neutral, etc.
- Tilts appliqués dynamiquement aux allocations.
- Priorité & bornes :
  - Tilts s’additionnent aux macro targets.
  - Capés (Memecoins max 15%, Others max 20%).
  - Les floors définis par la gouvernance priment toujours.
  - Règle de priorité : `governance floors/caps > phase tilts > defaults`.

---

## 9) UI & Navigation

- Navigation unifiée : ne pas créer de nouvelles pages hors `static/`.
- Thèmes : respecter `shared-theme.css`.
- Iframes : interdits sauf cas documenté.
- Perf front : utiliser `performance-optimizer.js` (virtual scrolling, batching).

---

## 10) Tests

- Unit tests : `tests/unit/*`
- Integration : `tests/integration/*`
- Smoke tests : PowerShell (`tests\wealth_smoke.ps1`)
- Tout nouveau code backend doit être couvert par des tests.

## Règles UI pour l’alignement du cap d’exécution

- Toujours utiliser `selectCapPercent(state)` comme source unique pour l’UI (cap en %).
  - Priorité: `state.governance.active_policy.cap_daily` (0–1) → affichage %.
  - Fallback: `state.governance.engine_cap_daily`/`caps.engine_cap` si policy absente.
- Aides disponibles: `selectPolicyCapPercent(state)`, `selectEngineCapPercent(state)`.
- Badges: afficher “Cap {policy}% • SMART {engine}%” quand ils diffèrent; sinon “Cap {policy}%”.
- Convergence: `iterations = ceil(maxDelta / (capPct/100))`.
- Badge serré: montrer “🧊 Freeze/Cap serré (±X%)” si mode Freeze ou cap ≤ 2%.

## Bonnes pratiques

- Ne pas afficher “SMART” seul si la policy existe.
- Normaliser toute valeur de cap potentiellement en fraction (0–1) en %.
- En absence de policy et d’engine, afficher “—”.
