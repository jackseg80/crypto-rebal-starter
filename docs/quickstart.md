# Quickstart

## Prérequis
- Python 3.10+
- `pip install -r requirements.txt`

## Configuration
1. Copiez `env.example` vers `.env` et renseignez vos clés CoinTracking (CT_API_KEY/CT_API_SECRET).
2. Optionnel: `CORS_ORIGINS` pour servir l’UI depuis une autre origine.

## Lancer l’API
```bash
uvicorn api.main:app --reload --port 8000
```

## Ouvrir l’UI
- Rebalance: `static/rebalance.html`
- Dashboard: `static/dashboard.html`
- Risk Dashboard: `static/risk-dashboard.html`
- Execution: `static/execution.html`
- Alias Manager: `static/alias-manager.html`
- Monitoring: `static/monitoring-unified.html`

## Endpoints essentiels
- GET `/healthz`
- GET `/balances/current`
- POST `/rebalance/plan`
- GET `/portfolio/metrics`

Pour l’ensemble des endpoints: voir `docs/api.md`.

