# Frontend Pages — Inventaire

**Total** : 101 pages HTML détectées

---

## Pages Production (Principales)

| Page                  | Title                | Endpoints                          | Modules JS                                   | Statut |
|-----------------------|----------------------|------------------------------------|----------------------------------------------|--------|
| dashboard.html        | Portfolio Overview   | /balances/current, /portfolio/*    | wealth-saxo-summary.js                       | Prod   |
| analytics-unified.html| Analytics            | /api/ml/*, /balances/current       | unified-insights-v2.js, decision-index-panel | Prod   |
| risk-dashboard.html   | Risk Management      | /api/risk/*                        | risk-dashboard-store.js, GovernancePanel     | Prod   |
| simulations.html      | Simulation Engine    | local (riskStore, presets)         | simulation-engine.js, SimControls.js         | Prod   |
| rebalance.html        | Rebalancing          | /rebalance/plan                    | allocation-engine.js                         | Prod   |
| execution.html        | Execution            | /execution/*                       | execution-manager.js                         | Prod   |

---

## Pages Bourse/Saxo

| Page                  | Title                | Endpoints                          | Modules JS                  | Statut |
|-----------------------|----------------------|------------------------------------|-----------------------------|--------|
| saxo-dashboard.html   | Bourse Overview      | /api/saxo/positions                | wealth-saxo-summary.js      | Prod   |
| saxo-upload.html      | Import Saxo          | /api/sources/*                     | sources-manager.js          | Migrating |
| analytics-equities.html| Analytics Equities  | /api/wealth/*                      | wealth-analytics.js         | Beta   |

---

## Pages Test/Debug (54)

| Préfixe | But                      | Exemple            | Statut |
|---------|---------------------------|--------------------|--------|
| test-   | Tests unitaires frontend  | test-di-history.html| Actif  |
| debug-  | Outils de diagnostic      | debug-risk.html     | Actif  |
| clear-  | Nettoyage caches/localStorage | clear-cache.html | Actif  |

**Liste partielle** :
- test-di-history.html
- test-phase-engine.html
- test-contradiction-unified.html
- debug-risk.html
- clear-cache.html
- (49 autres pages test/debug)

---

## Pages Utilities

| Page                  | But                      | Statut |
|-----------------------|---------------------------|--------|
| settings.html         | Configuration utilisateur | Prod   |
| alias-manager.html    | Gestion aliases assets    | Prod   |
| sources-manager.html  | Sources System v2         | Prod   |

---

## Pages Legacy/Deprecated

À documenter au fur et à mesure de l'audit. Critère : pages non référencées dans navigation principale et non maintenues depuis > 6 mois.

---

## Notes

- **Statut** : Prod (production), Beta (fonctionnel mais incomplet), Migrating (en transition), Legacy (déprécié)
- **101 pages** : Inventaire complet disponible via `find static/ -name "*.html"`
- **Test/Debug** : 54 pages identifiées avec préfixes test-, debug-, clear-
