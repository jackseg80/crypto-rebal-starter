# Module Map — JavaScript

**Total** : 70 modules JS détectés

---

## Core Modules

| Module                                   | Exports clés              | Utilisé par                  | Notes |
|------------------------------------------|---------------------------|------------------------------|-------|
| static/core/risk-dashboard-store.js      | riskStore, getDecision()  | risk-dashboard.html, simulations.html | Store central Risk |
| static/core/unified-insights-v2.js       | computeUnifiedInsights()  | analytics-unified.html       | Prod, DI calcul |
| static/core/phase-engine.js              | detectPhase(), applyTilts() | unified-insights-v2.js     | Phase detection |

---

## Components

| Component                                | Exports                   | Pages                        | Notes |
|------------------------------------------|----------------------------|------------------------------|-------|
| static/components/decision-index-panel.js| renderDecisionIndexPanel() | analytics-unified.html, simulations.html | Trend chip + regime |
| static/components/GovernancePanel.js     | GovernancePanel (class)    | risk-dashboard.html          | Gouvernance |
| static/components/UnifiedInsights.js     | UnifiedInsights (class)    | analytics-unified.html       | Wrapper |

---

## Modules (Domaine)

| Module                                   | Exports                   | Domaine     | Notes |
|------------------------------------------|----------------------------|-------------|-------|
| static/modules/simulation-engine.js      | Fonctions simulation       | Simulation  | Aligne DI prod (pas de classe exportée) |
| static/modules/wealth-saxo-summary.js    | fetchSaxoSummary()         | Bourse      | Utilisé dashboard & saxo-dashboard |
| static/utils/di-history.js               | getTodayCH(), makeKey(), loadHistory() | DI History | Persistence localStorage |

---

## Utilities

| Utility                                  | Exports                   | Usage       | Notes |
|------------------------------------------|----------------------------|-------------|-------|
| static/global-config.js                  | API_BASE_URL               | Global      | Config centralisée |
| static/lazy-loader.js                    | lazyLoad()                 | Navigation  | Iframes lazy |

---

## Notes

- **debug-logger.js** : Non trouvé dans static/utils/ (peut-être inline ou autre emplacement)
- **70 modules** : Inventaire complet disponible via `find static/ -name "*.js" -type f`
- **Exports vérifiés** : decision-index-panel (ligne 999), GovernancePanel (ligne 13), wealth-saxo-summary (fetchSaxoSummary)
