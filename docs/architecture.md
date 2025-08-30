# Architecture

## Vue d’ensemble
- FastAPI (`api/`) expose endpoints et sert les assets statiques.
- Services (`services/`) encapsulent la logique (rebalance, risk, pricing, execution).
- Connectors (`connectors/`) intègrent des APIs externes (CoinTracking, exchanges).
- Static UI (`static/`) fournit des dashboards locaux (rebalance, risk, execution, monitoring).

## Pipeline (résumé)
- Ingestion balances (CoinTracking CSV/API)
- Pricing (local/fallback)
- Plan de rebalancement (targets manuels/dynamiques)
- Exécution (adapters exchanges, safety)
- Monitoring & analytics

Pour les détails historiques, voir les anciens fichiers TECHNICAL_ARCHITECTURE.md et PIPELINE_ARCHITECTURE.md (dépréciés).

