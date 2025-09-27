# AGENTS.md — Guide de travail pour agents (Crypto Rebal Starter)

Ce fichier est injecté automatiquement (Codex/Claude/IA code).
Il décrit l'**état ACTUEL** du projet et les **règles de contribution** (Windows 11).

---

## 0) Règles d'or
- Pas d'URL en dur pour les APIs → utiliser `static/global-config.js`.
- Pas de refactor massif : proposer uniquement des patchs/diffs minimaux, jamais des fichiers entiers.
- Ne pas renommer de fichiers sans demande explicite.
- Respect des perfs : batching, pagination, caches locaux.
- Tests obligatoires si du code backend est modifié.
- Sécurité : pas de nouveaux endpoints sensibles (`/realtime/...`) sans validation.

### 0.1 Contexte Windows 11
- Scripts PowerShell `.ps1`/`.bat` : préférer ces outils aux commandes Linux non-portables.
- Chemins : éviter `touch/sed -i`; utiliser `New-Item`, `Out-File`, etc.

### 0.2 Pages et endpoints **actuels**
- **Crypto** :
  - UI : `dashboard.html`, `analytics-unified.html`, `risk-dashboard.html`, `rebalance.html`
  - API : `/balances/current`, `/rebalance/plan`, `/portfolio/metrics`, etc.
- **Bourse / Saxo** :
  - UI : `saxo-upload.html`, `saxo-dashboard.html`
  - API : `/api/saxo/*` (upload/positions/accounts/instruments …)

### 0.3 Wealth (roadmap — ne pas supposer existant)
- Ne **pas** créer/utiliser de pages `analytics-equities.html`, `risk-equities.html`, `rebalance-equities.html` tant qu'elles ne sont pas demandées.
- Ne **pas** imposer `/api/wealth/*` si l'existant `/api/saxo/*` couvre le besoin.
- Les détails du futur Wealth sont dans `docs/TODO_WEALTH_MERGE.md` (référence, pas à implémenter sans consigne).

## 1) Où commencer (lecture rapide)
- Architecture : `docs/architecture.md` (si présent), `docs/user-guide.md`
- API : `docs/api.md` (sections Crypto + Saxo actuelles)
- UI : `static/dashboard.html`, `static/saxo-dashboard.html`, `static/saxo-upload.html`
- Settings : `static/settings.html`

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
