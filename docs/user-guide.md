# Guide Utilisateur

Ce guide couvre les usages principaux de l’application.

## 1. Chargement du portefeuille
- Endpoint: `GET /balances/current?source=cointracking&min_usd=1`
- UI: `static/dashboard.html`

## 2. Génération d’un plan de rebalancement
- Endpoint: `POST /rebalance/plan`
- UI: `static/rebalance.html`
- Targets dynamiques (CCS): passer `dynamic_targets=true` et fournir `dynamic_targets_pct`.

## 3. Exécution (simulation/temps réel)
- Endpoints: `/execution/*` et `/api/execution/*`
- UI: `static/execution.html`, `static/execution_history.html`
- Historique sessions: `GET /api/execution/history/sessions`

## 4. Gestion des risques
- Endpoints: `/api/risk/metrics`, `/api/risk/correlation`, `/api/risk/stress-test`, `/api/risk/dashboard`
- UI: `static/risk-dashboard.html`

## 5. Taxonomie & Aliases
- Endpoints: `/taxonomy`, `/taxonomy/suggestions`, `/taxonomy/auto-classify`
- UI: `static/alias-manager.html`

## 6. Monitoring
- Base: `/monitoring/alerts`
- Avancé: `/api/monitoring/health`, `/api/monitoring/alerts`
- UI: `static/monitoring-unified.html`

## 7. CSV CoinTracking
- Export automatique: `POST /csv/download` (current_balance, balance_by_exchange, coins_by_exchange)

Pour la liste complète, consultez `docs/api.md` ou l’OpenAPI (`/docs`).

