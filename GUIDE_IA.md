# Guide IA — Travailler avec ce projet

> **Objectif** : Guide complet pour IA et humains travaillant sur crypto-rebal-starter.
> Ce document explique le workflow, les sources de vérité, les commandes essentielles et la régénération de documentation.

---

## 0. Politique de Workflow (obligatoire)

### Règle d'or
Je pose un problème → l'IA travaille → quand la solution est correcte et complète, elle met à jour la doc & commit.
**❌ Pas de commits intermédiaires** sauf demande explicite (hotfix/POC).

### Definition of Ready (DoR)
Une tâche démarre seulement si :
- ✅ **Objectif clair** (1 phrase)
- ✅ **Critères d'acceptation mesurables**
- ✅ **Fichiers/chemins concernés** identifiés
- ✅ **Contraintes précisées** (perf, compat, sécurité)

### Definition of Done (DoD)
Avant commit, l'IA vérifie :
- ✅ **Critères d'acceptation atteints**
- ✅ **Tests/essais basiques OK** (ou plan écrit)
- ✅ **Documentation mise à jour** (à la fin seulement)
- ✅ **Liens non cassés**
- ✅ **Risk score respecté** (jamais inversé avec `100 - scoreRisk`)
- ✅ **Multi-tenant** (`user_id`) préservé si applicable

### Politique de commits
- **1 tâche = 1 commit final**
- Message template :
```
feat|fix|docs(scope): courte description

Contexte: …
Changement clé: …
Docs: fichiers mis à jour
Tests: résumé (ou N/A)
```
- **❌ Pas de WIP** sauf si explicitement demandé

### Quand poser une question
L'IA doit **stopper et demander** si :
- La règle métier est ambiguë
- La source de vérité n'est pas claire
- Un point de sémantique Risk est en jeu

👉 **Toujours proposer 1–2 options + recommandation**

### Checkpoints (chantiers > 1h)
- **Milieu de tâche** : courte note d'avancement + questions
- **Avant commit final** : récapitulatif (fait / pas fait / doc impactée)

---

## 1. Points d'entrée (par contexte)

### Documentation IA
- **Brief canonique (injectable en prompt)** : [`agent.md`](agent.md) — 2-3 pages, règles d'or, architecture, endpoints clés
- **Tips modèle spécifiques** : [`CLAUDE.md`](CLAUDE.md), [`GEMINI.md`](GEMINI.md) — pointent vers `agent.md` + spécificités modèle
- **Guide complet (ce document)** : `GUIDE_IA.md` — workflow, commandes, régénération docs

### Documentation technique
- **Vue d'ensemble projet** : [`README.md`](README.md) — installation, démarrage rapide, structure
- **Portail documentation** : [`docs/README.md`](docs/README.md) — index organisé de tous les docs
- **Architecture système** : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — composants, flux, design

### Inventaires
- **Pages frontend (101 HTML)** : [`docs/FRONTEND_PAGES.md`](docs/FRONTEND_PAGES.md)
- **Modules JS (70 modules)** : [`docs/MODULE_MAP.md`](docs/MODULE_MAP.md)
- **API (325 endpoints)** : [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) — auto-généré

---

## 2. Sources de vérité canoniques

### Règles critiques
- **Risk Semantics** : [`docs/RISK_SEMANTICS.md`](docs/RISK_SEMANTICS.md)
  - Risk Score ∈ [0..100], **plus haut = plus robuste**
  - **❌ Interdit** : jamais inverser avec `100 - scoreRisk`
  - Utilisé dans DI, gouvernance, allocations

- **Multi-tenant** : [`CLAUDE.md#3-système-multi-utilisateurs`](CLAUDE.md)
  - Toujours propager `user_id` (API, stores, caches)
  - Isolation filesystem via `UserScopedFS`
  - Clé primaire : `(user_id, source)`

### Mécaniques système
- **Decision Index (DI)** : [`docs/UNIFIED_INSIGHTS_V2.md`](docs/UNIFIED_INSIGHTS_V2.md)
  - Formule : `DI = wCycle·scoreCycle + wOnchain·scoreOnchain + wRisk·scoreRisk`
  - Poids adaptatifs selon phase marché

- **Simulation Engine** : [`docs/SIMULATION_ENGINE.md`](docs/SIMULATION_ENGINE.md)
  - Réplique unified-insights-v2 en mode déterministe
  - Alignment avec production (voir `SIMULATION_ENGINE_ALIGNMENT.md`)

- **P&L Today** : [`docs/PNL_TODAY.md`](docs/PNL_TODAY.md)
  - Tracking par `(user_id, source)`
  - Calcul : `current_value - latest_snapshot_value`

### Archivé
- **Legacy docs** : [`docs/_archive/`](docs/_archive/) — documents obsolètes conservés pour historique

---

## 3. Workflow IA recommandé

### Flux de travail standard
1. **Lire** : problème posé + fichiers docs de référence
   - Consulter [`agent.md`](agent.md) pour règles d'or
   - Lire docs spécifiques au périmètre (API, frontend, services)

2. **Pointer** : vers sources canoniques
   - Risk → [`docs/RISK_SEMANTICS.md`](docs/RISK_SEMANTICS.md)
   - Multi-tenant → [`CLAUDE.md#3`](CLAUDE.md)
   - API → [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)

3. **Coder** : appliquer les règles
   - **Risk positif** : jamais `100 - scoreRisk`
   - **Multi-tenant** : propager `user_id` partout
   - **Pas d'URL en dur** : utiliser `global-config.js`
   - **Venv activé** : toujours travailler dans `.venv`

4. **Vérifier** : tests de base ou logs
   - Tests unitaires : `pytest -q tests/unit`
   - Tests intégration : `pytest -q tests/integration`
   - Smoke tests : `python tests/smoke_test_refactored_endpoints.py`

5. **Commit** : uniquement quand DONE
   - Message conventionnel : `feat|fix|docs(scope): résumé`
   - Doc mise à jour **à la fin**
   - Un seul commit par tâche complète

### Checkpoints critiques
- **Multi-tenant** : `user_id` présent dans tous les endpoints/services/stores
- **Risk** : jamais inverser, toujours positif [0..100]
- **Doc** : lien vers source, pas de duplication de contenu
- **Venv** : `.venv` activé avant toute commande Python/pip
- **Sources System** : utiliser `window.loadBalanceData()` au lieu de `fetch()` direct

---

## 4. Commandes essentielles

### Hooks pre-commit (optionnel mais recommandé)

Le projet utilise des hooks pour éviter les erreurs fréquentes :

**Installation** :
```bash
pip install pre-commit
pre-commit install
```

**Vérification** :
```bash
# Tester sur tous les fichiers
pre-commit run --all-files
```

**Ce que bloque le hook** :
- ❌ **Risk inversion** : `100 - risk` dans `.py/.js/.ts/.tsx` → voir [`docs/RISK_SEMANTICS.md`](docs/RISK_SEMANTICS.md)
- ❌ **Commits non conformes** : messages ne suivant pas `feat|fix|docs(scope): description`
- ❌ **Commits WIP** : messages contenant "WIP" → voir [Section 0 - Politique Workflow](#0-politique-de-workflow-obligatoire)

**Contournement exceptionnel** :
```bash
git commit --no-verify
```
⚠️ **À éviter**. Préférez poser une question si doute (voir Section 0).

**Dépannage** :
- Si le hook ne se lance pas : `pre-commit install --install-hooks`
- Si un faux positif "Risk inversion" apparaît : préciser le code et ouvrir une PR avec contexte

---

### Raccourcis Make (qualité dev rapide)

Le projet fournit un `Makefile` pour exécuter les tâches courantes :

```bash
# Première installation complète
make setup

# Exécuter tous les checks qualité
make qa

# Régénérer documentation API
make docs

# Lancer tests unitaires
make test

# Nettoyer fichiers temporaires
make clean
```

**Note** : `make qa` exécute :
1. Régénération `API_REFERENCE.md`
2. Scan liens cassés (`gen_broken_refs.py`)
3. Hooks pre-commit sur tous fichiers

---

### Environnement virtuel
```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate

# Vérifier activation (prompt doit afficher (.venv))
python --version
pip list
```

### Développement
```bash
# TOUJOURS activer .venv d'abord !

# Lancer serveur backend (port 8000)
uvicorn api.main:app --reload

# Ou utiliser le script fourni
.\start-dev.ps1  # Windows
./start-dev.sh   # Linux/Mac

# URL principal
# http://localhost:8000/static/dashboard.html
```

### Tests
```bash
# TOUJOURS activer .venv d'abord !

# Tests unitaires
pytest -q tests/unit

# Tests intégration
pytest -q tests/integration

# Smoke tests
python tests/smoke_test_refactored_endpoints.py

# Tests avec coverage
pytest --cov=services --cov=api tests/
```

### Docker
```bash
# Build image
docker build -t crypto-rebal .

# Run container
docker run -p 8000:8000 --env-file .env crypto-rebal
```

---

## 5. Régénération documentation

### API Reference (325 endpoints)
```bash
# Activer .venv d'abord
.venv\Scripts\Activate.ps1

# Regénérer docs/API_REFERENCE.md
python tools/gen_api_reference.py

# Résultat : 325 endpoints across 19 namespaces
# Note : intro/conventions sont éditables, tableaux auto-générés
```

### Références cassées
```bash
# Activer .venv d'abord
.venv\Scripts\Activate.ps1

# Scanner tous les liens markdown
python tools/gen_broken_refs.py

# Résultat : broken_refs_actions.csv avec priorités (HIGH/MEDIUM/LOW/IGNORE)
```

### Inventaires manuels
- **FRONTEND_PAGES.md** : mettre à jour manuellement si ajout/suppression pages HTML
- **MODULE_MAP.md** : mettre à jour manuellement si ajout/suppression modules JS
- **SIMULATION_ENGINE.md** : mettre à jour si changements alignement unified-insights-v2

---

## 6. Pièges fréquents & solutions

### ❌ Oublier user_id dans endpoint
```python
# MAUVAIS
@app.get("/portfolio/metrics")
async def portfolio_metrics(source: str = Query("cointracking")):
    ...

# BON
@app.get("/portfolio/metrics")
async def portfolio_metrics(
    source: str = Query("cointracking"),
    user_id: str = Query("demo")  # ← OBLIGATOIRE
):
    ...
```

### ❌ Inverser Risk Score
```javascript
// MAUVAIS
const riskDisplay = 100 - scoreRisk;

// BON
const riskDisplay = scoreRisk;  // Déjà positif [0..100]
```

### ❌ Hardcoder URL API
```javascript
// MAUVAIS
const url = 'http://localhost:8000/api/risk/score';

// BON
import { API_BASE_URL } from './global-config.js';
const url = `${API_BASE_URL}/api/risk/score`;
```

### ❌ Fetch direct au lieu de loadBalanceData
```javascript
// MAUVAIS (race condition, pas de header X-User)
const response = await fetch(`/balances/current?source=${source}`);

// BON (cache intelligent, isolation multi-tenant)
const balanceResult = await window.loadBalanceData(true);
```

### ❌ Oublier d'activer .venv
```bash
# MAUVAIS
pip install requests  # Installe dans Python système

# BON
.venv\Scripts\Activate.ps1
pip install requests  # Installe dans .venv isolé
```

---

## 7. Conventions de code

### Python (backend)
- **FastAPI + Pydantic v2** : typage strict, validation automatique
- **Logs structurés** : `logging.getLogger(__name__)`
- **Exceptions propres** : `HTTPException(status_code, detail)`
- **Tests** : pytest avec fixtures, isolation complète

### JavaScript (frontend)
- **ESM** : `type="module"`, imports dynamiques pour gros modules
- **Pas d'URL en dur** : `global-config.js`
- **Cache intelligent** : `window.loadBalanceData()` pour balances
- **Multi-tenant** : `localStorage.getItem('activeUser')`

### CSS
- **Variables** : `shared-theme.css` + `theme-compat.css`
- **Dark mode** : par défaut
- **Responsive** : mobile-first

---

## 8. Definition of Done (DoD)

Avant de committer, vérifier :

- [ ] Tests unitaires verts + smoke test API (si endpoint)
- [ ] Lint OK (Ruff pour Python, ESLint si configuré pour JS)
- [ ] Pas de secrets (`COINTRACKING_API_KEY`, `.env` non commité)
- [ ] Pas d'URL API en dur (utiliser `global-config.js`)
- [ ] Multi-tenant : `user_id` propagé partout
- [ ] Risk semantics : jamais `100 - scoreRisk`
- [ ] Venv : commandes exécutées dans `.venv`
- [ ] UX/Thème inchangés (sauf demande explicite)
- [ ] Doc courte (4-8 lignes) ajoutée dans doc pertinent si nouveau concept

---

## 9. Outils de développement

### Scripts fournis
- **`start-dev.ps1`** (Windows) : lance uvicorn en mode reload
- **`start-dev.sh`** (Linux/Mac) : lance uvicorn en mode reload
- **`zip_project.py`** : génère archive projet pour backup/partage

### Outils Python
- **`tools/gen_api_reference.py`** : régénère API_REFERENCE.md (325 endpoints)
- **`tools/gen_broken_refs.py`** : détecte liens markdown cassés

### Configuration
- **`.claude/settings.local.json`** : config agent Claude Code
- **`config/settings.py`** : Pydantic settings backend
- **`static/global-config.js`** : config frontend (API_BASE_URL)

---

## 10. Ressources complémentaires

### Documentation externe
- **FastAPI** : https://fastapi.tiangolo.com/
- **Pydantic V2** : https://docs.pydantic.dev/latest/
- **Pytest** : https://docs.pytest.org/
- **Chart.js** : https://www.chartjs.org/docs/latest/

### Pages clés du projet
- **Dashboard principal** : `http://localhost:8000/static/dashboard.html`
- **Analytics ML** : `http://localhost:8000/static/analytics-unified.html`
- **Risk Dashboard** : `http://localhost:8000/static/risk-dashboard.html`
- **Simulateur** : `http://localhost:8000/static/simulations.html`
- **Saxo (Bourse)** : `http://localhost:8000/static/saxo-dashboard.html`

### Support
- **Issues projet** : (si GitHub public, ajouter lien)
- **Questions IA** : relire `agent.md` + docs spécifiques au problème

---

## 11. Historique des phases documentation

### Phase 1 — Normalisation (✅ complétée)
- Renommages : `contributing.md → CONTRIBUTING.md`, `_legacy/ → _archive/`
- Création : `agent.md`, `docs/README.md`, `docs/RISK_SEMANTICS.md`
- Mise à jour : liens vers `PNL_TODAY.md` (ancien `PERFORMANCE_PNL_SYSTEM.md`)

### Phase 2 — Consolidation (✅ complétée)
- Création inventaires : `FRONTEND_PAGES.md` (101 pages), `MODULE_MAP.md` (70 modules)
- Consolidation : `SIMULATION_ENGINE.md` (depuis `SIMULATION_ENGINE_ALIGNMENT.md`)
- Encart Risk : inséré dans 7 docs clés (CLAUDE.md, README.md, ARCHITECTURE.md, etc.)

### Phase 3 — Auto-génération (✅ complétée)
- `gen_api_reference.py` : v2 regex-based, 325 endpoints détectés (19 namespaces)
- `gen_broken_refs.py` : scanner liens markdown avec priorités
- `docs/API_REFERENCE.md` : enrichi avec intro/conventions/exemples curl
- Fixes : création `cycle_phase_presets.json` manquant, actions pour 5 refs cassées

### Phase Bonus — Guide IA (✅ complétée)
- Création : `GUIDE_IA.md` (ce document)
- Séparation rôles : `agent.md` (brief canonique) vs `GUIDE_IA.md` (guide complet)
- Stubs : `CLAUDE.md` / `GEMINI.md` pointent vers `agent.md`

---

**Version** : 1.0 (Octobre 2025)
**Maintenu par** : Documentation automatisée + révisions manuelles au besoin
