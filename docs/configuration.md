# Configuration Optimale pour Développement

Document déplacé depuis `CONFIGURATION.md` pour centraliser la configuration sous `docs/`.

## Sources de Données — Source de vérité centralisée

La liste des sources est centralisée dans `static/global-config.js` via `window.DATA_SOURCES` (+ ordre via `window.DATA_SOURCE_ORDER`).

### Groupes affichés dans Settings
- "Sources de démo" → entrées avec `kind: 'stub'`
- "Sources CoinTracking" → entrées avec `kind: 'csv'` et `kind: 'api'`

Ajouter/retirer une source = modifier `DATA_SOURCES` uniquement; l’onglet “Résumé”, l’onglet “Source”, les validations (`static/input-validator.js`) et l’ensemble des pages consomment `globalConfig.get('data_source')`.

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

