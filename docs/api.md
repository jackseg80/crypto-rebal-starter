# API (Niveau intermédiaire)

Référence synthétique, avec exemples clés. La source canonique reste l’OpenAPI:
- Docs interactives: `http://127.0.0.1:8000/docs`
- Schéma brut: `http://127.0.0.1:8000/openapi.json`

## Core
- `GET /healthz`
- `GET /balances/current?source=cointracking|cointracking_api&min_usd=1`
- `GET /portfolio/metrics`
- `POST /rebalance/plan` (targets manuels/dynamiques)
- `GET /debug/ctapi` (sonde CoinTracking API)

Exemple `POST /rebalance/plan` (extrait):
```json
{
  "group_targets_pct": {"BTC": 40, "ETH": 30, "Stablecoins": 10, "Others": 20},
  "primary_symbols": {"BTC": ["BTC","TBTC","WBTC"]},
  "min_trade_usd": 25
}
```

## Taxonomy
- `GET /taxonomy`
- `POST /taxonomy/aliases` (upsert bulk)
- `DELETE /taxonomy/aliases/{alias}`
- `POST /taxonomy/suggestions` (auto-suggest à partir d’échantillons ou du cache)
- `POST /taxonomy/auto-classify` (applique les suggestions)

## Analytics
- `GET /analytics/performance/summary?days_back=30`
- `GET /analytics/performance/detailed?days_back=30`
- `GET /analytics/sessions?limit=50&days_back=30&status=completed`

## Execution (plan/exécution)
- `POST /execution/validate-plan`
- `POST /execution/execute-plan?plan_id=...&dry_run=true`
- `GET  /execution/status/{plan_id}`
- `GET  /execution/orders/{plan_id}`
- `GET  /execution/plans?limit=50&offset=0`
- `GET  /execution/pipeline-status`

## Execution (dashboard & history)
- `GET  /api/execution/status` (dashboard état global)
- `GET  /api/execution/connections`
- `POST /api/execution/execute-orders` (simulation d’ordres depuis l’UI dashboard)
- `GET  /api/execution/history/sessions?limit=50&days=7` (historique mock/dev)

## Risk
- `GET /api/risk/metrics?price_history_days=30`
- `GET /api/risk/correlation?price_history_days=90`
- `GET /api/risk/stress-test?scenario=covid_2020`
- `POST /api/risk/stress-test/custom` (shocks personnalisés)
- `GET /api/risk/dashboard` (vue consolidée)

## Monitoring
- Base: `GET /monitoring/alerts` (règles, notifications)
- Avancé: `GET /api/monitoring/health`, `GET /api/monitoring/alerts`

## CSV utilitaires
- `POST /csv/download` body:
```json
{ "file_type": "balance_by_exchange", "download_path": "data/raw/", "auto_name": true }
```

## Kraken (aperçu)
- `GET /kraken/status`, `GET /kraken/prices`, `GET /kraken/balance`
- `POST /kraken/validate-order`, `POST /kraken/orders`

Notes:
- Certains endpoints “dashboard/history” retournent des données simulées en dev.
- Pour payloads complets et schémas, se référer à l’OpenAPI.

## CoinTracking (sources & debug)

- `source=cointracking` → CSV strict via `connectors/cointracking.py`
- `source=cointracking_api` → API CT strict via `connectors/cointracking_api.py`
- Pas de fallback silencieux entre les deux. En cas d’erreur API, la réponse inclut `source_used: "cointracking_api"` avec un champ `error`.
- Debug: `GET /debug/ctapi` (présence clés, aperçu des données, erreurs format/HTTP)
