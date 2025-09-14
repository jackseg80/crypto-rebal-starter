# Configuration Optimale pour Développement

Document déplacé depuis `CONFIGURATION.md` pour centraliser la configuration sous `docs/`.

## Sources de Données — Système Multi-Utilisateurs

Le système de sources a été modernisé pour supporter les utilisateurs multiples avec isolation complète des données.

### Architecture Multi-Utilisateurs
- **6 utilisateurs configurés** : demo, jack, donato, elda, roberto, clea
- **Sélecteur utilisateur** : dans la barre de navigation (hors du menu Admin)
- **Isolation complète** : chaque utilisateur a ses propres CSV, clés API et configurations
- **Settings individuels** : stockés dans `data/users/{user}/config.json`

### Sources Dynamiques par Utilisateur
- **CSV** : liste les fichiers CSV réels de chaque utilisateur (`data/users/{user}/csv/`)
- **API CoinTracking** : apparaît seulement si l'utilisateur a configuré des clés API
- **Sections adaptatives** : masquage automatique des options non disponibles

### Endpoints Multi-Utilisateurs
- `GET /api/users/sources` : sources disponibles pour l'utilisateur actuel
- `GET /api/users/settings` : configuration de l'utilisateur
- `PUT /api/users/settings` : sauvegarde des settings utilisateur
- Header `X-User` : identification automatique via le sélecteur

### Sélection de source et nouveaux comportements
- `settings.html` est la source de vérité pour chaque utilisateur; les écritures vont dans `data/users/{user}/config.json`.
- Sélection CSV précise: pour utiliser les CSV d’un utilisateur, choisir un élément explicite (ex: `CoinTracking - Current Balance.csv`) qui se mappe à une clé `data_source = "csv_0"`, `csv_1`, etc.
  - Les endpoints backend utilisent désormais uniquement les variantes `csv_{i}` pour activer la lecture CSV. Une valeur générique `csv` n’active plus de fallback implicite.
- API CoinTracking: choisir la source `cointracking_api` et renseigner les clés dans l’onglet Clés API (sauvegarde par utilisateur). Les endpoints utilisent les clés du `config.json` utilisateur (et non `.env`).
- Debug .env: les boutons “Charger/Sauver .env” sont cachés sauf si `debug_mode: true` dans le `config.json` utilisateur. Ils restent réservés au développement.

### Caches et cohérence inter‑pages
- Tous les fetchs UI sensibles passent par `globalConfig.apiRequest(...)` qui ajoute `X-User` automatiquement.
- Les caches locaux (localStorage) sont scopés par utilisateur et source. Exemples:
  - `analytics_unified_risk_<user>_<source>`
  - `risk-dashboard-balance:<user>:<source>:<min_usd>`
  - Scores persistés: `risk_score_risk:<user>`, `risk_score_onchain:<user>`, etc.
- Cela garantit que Dashboard, Risk Dashboard et Analytics Unifiés affichent des valeurs cohérentes pour l’utilisateur actif.

## Interfaces Frontend Disponibles

Toutes les 19 routes backend ont maintenant des interfaces frontend :

### Principales
- `static/dashboard.html` — Vue d'ensemble portfolio (Global Insight)
- `static/rebalance.html` — Rééquilibrage
- `static/risk-dashboard.html` — Analyse des risques
- `static/execution.html` — Exécution des trades
- `static/execution_history.html` — Historique d'exécution
- `static/settings.html` — Configuration

### Outils Avancés
- `static/cycle-analysis.html` — Analyse cycles marché
- `static/monitoring_advanced.html` — Monitoring avancé
- `static/analytics-unified.html` — Analytics unifié
- `static/alias-manager.html` — Gestion alias cryptos

## Données Mock

Toutes les données mock ont été retirées. L’UI affiche des erreurs explicites si la source n’est pas configurée et oriente vers `settings.html`.

## Configuration Recommandée

1. Créer l’environnement: `python -m venv .venv && ./.venv/bin/pip install -r requirements.txt`
2. Copier l’exemple: `cp env.example .env`
3. Lancer l’API: `uvicorn api.main:app --reload`
4. Ouvrir les pages: `http://localhost:8000/static/dashboard.html`

## Devise & Conversion

Sélecteur devises dans `settings.html`. Conversion affichage via `window.currencyManager` (USD→EUR via exchangerate.host; USD→BTC via prix `BTCUSDT`).

## Architecture API Post-Refactoring (v2)

Namespaces principaux: `/api/ml/*`, `/api/risk/*` (incl. `/api/risk/advanced/*`), `/api/alerts/*`, `/api/governance/*`, `/api/realtime/*`.

Guide de migration: `docs/refactoring.md`.
