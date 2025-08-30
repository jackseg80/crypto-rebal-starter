# Architecture (Niveau intermédiaire)

## Vue d’ensemble
- FastAPI (`api/`) expose les endpoints et monte les répertoires `static/` et `data/`.
- Services (`services/`) encapsulent la logique métier: rebalancing, risk, pricing, execution, analytics, notifications.
- Connectors (`connectors/`) intègrent les APIs externes (CoinTracking CSV/API, exchanges).
- UI statique (`static/`) fournit les dashboards locaux (rebalance, risk, execution, monitoring) consommant l’API locale.

## Data flow principal
- Ingestion balances: CoinTracking CSV (Balance by Exchange/Current Balance) ou API.
- Normalisation/aliases → groupes (BTC, ETH, Stablecoins, etc.).
- Pricing: local/fallback, estimation quantités.
- Planning: calcul des deltas vs cibles (targets manuels ou dynamiques CCS) → actions.
- Exécution: création des plans, adaptateurs exchanges, safety checks, statut live.
- Monitoring/Analytics: alertes, historique exécution, performance.

## Points techniques clés
- Mounts: `/static` et `/data` (voir `api/main.py`).
- Environnement: `.env` (CT_API_KEY/SECRET, CORS_ORIGINS, PORT, DEBUG/APP_DEBUG).
- Caching: CoinTracking API avec TTL 60s pour limiter la charge.
- Gestion erreurs: exceptions custom → JSON standardisé (voir `api/exceptions.py`).
- Taxonomy: persistance d’aliases merge mémoire/disque.
- Security: middleware gzip, CORS, trusted hosts; safety validator côté exécution.

Pour plus de détails, l’archive `docs/_legacy/` contient les schémas exhaustifs.
