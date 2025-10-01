# agent.md — Brief Canonique (Crypto Rebal Starter)

## But
Donner à l'IA un contexte minimal et fiable pour comprendre l'architecture, la sémantique des scores et les conventions du projet.

## Règles d'or
- **Multi-tenant** : toujours propager `user_id` (API, stores, caches).
- **Risk ∈ [0..100], plus haut = plus robuste** (jamais d'inversion `100 - scoreRisk`).
- **Pas d'URL en dur** : utiliser `global-config.js` ou variables d'environnement.
- **Timezone** : Europe/Zurich pour les calculs sensibles (DI History, P&L Today).
- **Prod vs Simulation** : séparer les clés et stores (`_prod` vs `_sim`).
- **Validation stricte** : filtrer NaN/Infinity, erreurs explicites, ETag correct.

## Workflow IA
- **Problème → Travail → Commit final** (pas de WIP sauf demande explicite)
- **DoR** : objectif clair, critères mesurables, fichiers identifiés, contraintes précisées
- **DoD** : critères atteints, tests OK, doc mise à jour (à la fin), liens non cassés, Risk/multi-tenant respectés
- **Commits** : 1 tâche = 1 commit (`feat|fix|docs(scope): description`)
- **Doute** : stopper + poser question avec 1-2 options + recommandation
- **Guide complet** : voir [GUIDE_IA.md](GUIDE_IA.md)

## Architecture
- **Backend** : `api/` (FastAPI, routers par domaine), `services/`, `connectors/`.
- **Frontend** : `static/` (HTML, JS/ESM), `components/`, `modules/`, `core/`, `utils/`.
- **Simulation** : `static/modules/simulation-engine.js` + `static/core/risk-dashboard-store.js`.

## Pages actives
- **Crypto** : `dashboard.html`, `analytics-unified.html`, `risk-dashboard.html`
- **Bourse** : `saxo-dashboard.html`, `analytics-equities.html`
- **Simulation** : `simulations.html` (10 presets)

## Endpoints clés
- `/api/risk/*`, `/api/ml/*`, `/api/wealth/*`, `/api/saxo/*`
- `/balances/current`, `/portfolio/metrics`
- Gouvernance : `/execution/governance/approve/{resource_id}`

## Fichiers pivots
- Risk store : `static/core/risk-dashboard-store.js`
- Simulation : `static/modules/simulation-engine.js`
- DI History : `static/utils/di-history.js` (+ tests `static/test-di-history.html`)

## Terminologie
- Conserver les anglicismes établis : **coin**, **wallet**, **exchange**, **airdrop**, **long/short**.
- Traductions standardisées : *Capital Gains Reports* → *Rapports sur les plus-values*.

## Sources de vérité
- Risk : [docs/RISK_SEMANTICS.md](docs/RISK_SEMANTICS.md)
- DI History : [docs/DI_HISTORY_SYSTEM.md](docs/DI_HISTORY_SYSTEM.md)
- P&L Today : [docs/PNL_TODAY.md](docs/PNL_TODAY.md)
- API : [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
