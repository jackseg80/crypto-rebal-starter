# Monitoring (Niveau intermédiaire)

## UI
- Page: `static/monitoring-unified.html`
- Vue consolidée: connexions exchanges, alertes, santé système.

## Endpoints Base (`/monitoring`)
- `GET /monitoring/alerts` (filtrable par `level`, `alert_type`, `unresolved_only`, `limit`)
- Actions d’alertes (ack/resolution) si exposées

## Endpoints Avancés (`/api/monitoring`)
- `GET /api/monitoring/health` (santé système et latences)
- `GET /api/monitoring/alerts`

## Différences et usages
- Base: pilotage “métier” du pipeline de rebalancing (alertes sur déviations, erreurs d’exécution).
- Avancé: diagnostic “technique” (connectivité, métriques système, tests de connexion).

## Conseils
- Utiliser `GET /healthz` et `GET /debug/paths` pour diagnostics rapides.
- Activer `DEBUG/APP_DEBUG=true` en local pour traces plus verbeuses.
