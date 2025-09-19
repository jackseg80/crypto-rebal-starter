# Monitoring (Niveau intermédiaire)

## UI
- Monitoring (métier): `static/monitoring.html`
- Monitoring avancé (technique): `static/monitoring_advanced.html`
- Vues: connexions exchanges, alertes, santé système.

## Endpoints API
- Système (avancé):
  - `GET /api/monitoring/health` (santé système et latences)
  - `GET /api/monitoring/alerts`
- Portefeuille (métier):
  - `GET /api/portfolio/metrics`
  - `GET /api/portfolio/alerts`

## Différences et usages
- Métier (portfolio): pilotage du pipeline (déviations, erreurs d’exécution).
- Technique (monitoring): diagnostic système (connectivité, métriques, tests de connexion).

## Conseils
- Utiliser `GET /healthz` et `GET /debug/paths` pour diagnostics rapides.
- Activer `DEBUG/APP_DEBUG=true` en local pour traces plus verbeuses.
