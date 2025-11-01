# API (état ACTUEL — référence intermédiaire)

Référence synthétique, avec exemples clés.
La source canonique reste l’OpenAPI:
- Docs interactives: `http://127.0.0.1:8080/docs`
- Schéma brut: `http://127.0.0.1:8080/openapi.json`

> **Important**
> Cette page décrit **l’état actuel** du code. Le namespace Wealth unifié est **en cours de conception** et n’est **pas encore** la voie par défaut.

## Crypto (actuel)
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

Exemple `POST /rebalance/plan` (extrait):
```json
{
  "group_targets_pct": {"BTC": 40, "ETH": 30, "Stablecoins": 10, "Others": 20},
  "primary_symbols": {"BTC": ["BTC","TBTC","WBTC"]},
  "min_trade_usd": 25
}
```

## Execution (plan/exécution)
- `POST /execution/validate-plan`
- `POST /execution/execute-plan?plan_id=...&dry_run=true`
- `GET /execution/history/sessions?limit=50`

## Bourse / Saxo (actuel)

Flux actuel centré sur **pages dédiées** et import fichier :
- **UI** : `static/saxo-dashboard.html` (dashboard bourse), `static/saxo-upload.html` (import CSV/XLSX)
- **Endpoints typiques actuels** (selon version du repo) :
  - `POST /api/saxo/upload` (import CSV/XLSX, met à jour un snapshot interne)
  - `GET /api/saxo/positions`
  - `GET /api/saxo/accounts`
  - `GET /api/saxo/instruments`
  - (Selon branches) `GET /api/saxo/prices` (si alimenté) / ou prix issus du snapshot

**Notes** :
- Le calcul **P&L Today** côté Bourse peut dépendre de données `prev_close`. Si indisponible, il peut être 0.
- L’intégration Bourse n’est pas encore alignée sur le même modèle que Crypto (c’est la **roadmap**).

## Wealth (Phase 2 complétée ✅)

> **Statut** : Namespace Wealth **opérationnel**, endpoints disponibles, lecture legacy active. Phase 2 terminée (Sep 2025).

**Endpoints disponibles** :
- `GET /api/wealth/modules` → découverte modules disponibles (retourne `["saxo"]` si snapshot présent)
- `GET /api/wealth/{module}/accounts` → liste comptes normalisés
- `GET /api/wealth/{module}/instruments` → catalogue instruments
- `GET /api/wealth/{module}/positions` → positions actuelles avec P&L
- `GET /api/wealth/{module}/prices` → prix instruments (si disponibles)
- `POST /api/wealth/{module}/rebalance/preview` → simulation rebalancing

**Modèles** :
- Fichier `models/wealth.py` **disponible** avec `AccountModel`, `InstrumentModel`, `PositionModel`, `PricePoint`
- Adapter Saxo : `adapters/saxo_adapter.py` retourne modèles normalisés

**Intégration UI** :
- Pages : `saxo-dashboard.html`, `analytics-equities.html` (beta)
- Tuile Dashboard : intégrée dans `dashboard.html` avec store partagé
- Roadmap Phase 3 : voir `docs/TODO_WEALTH_MERGE.md`

## Taxonomy
- `GET /taxonomy`
- `POST /taxonomy/aliases` (upsert bulk)

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
- Portefeuille (métier): `GET /api/portfolio/metrics`, `GET /api/portfolio/alerts`
- Système (avancé): `GET /api/monitoring/health`, `GET /api/monitoring/alerts`

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

### Remarques frontend

- Cap d’exécution consommé depuis `/execution/governance/state`: utiliser `active_policy.cap_daily` comme source de vérité côté UI.

