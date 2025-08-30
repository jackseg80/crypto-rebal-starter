# API

Source of truth: l’OpenAPI embarqué.
- Docs interactives: `http://127.0.0.1:8000/docs`
- Schéma brut: `http://127.0.0.1:8000/openapi.json`

## Espaces principaux
- Core: `/balances`, `/rebalance`, `/portfolio`
- Analytics: `/analytics/*` (summary, detailed, sessions)
- Execution: `/execution/*` et `/api/execution/*` (dashboard, history)
- Risk: `/api/risk/*`
- Taxonomy: `/taxonomy/*`
- Monitoring (base): `/monitoring/*`
- Monitoring (avancé): `/api/monitoring/*`
- CSV utilitaires: `/csv/download`

Voir les exemples détaillés dans l’UI Swagger et les tests existants.

