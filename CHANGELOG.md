# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2025-01-14

### 🎯 Centralisation ML - Source Unique de Vérité

### Added
- **Source ML Centralisée** : `shared-ml-functions.js::getUnifiedMLStatus()` - single source of truth
- **Logique Prioritaire Unifiée** : Governance Engine → ML Status API → Stable fallback (identique AI Dashboard)
- **Cache Intelligent** : TTL 2 minutes pour performance avec invalidation automatique
- **Validation Robuste** : Caps automatiques (4 modèles max, 100% confidence max) pour éviter valeurs aberrantes
- **Documentation Complète** : `docs/ml-centralization.md` avec architecture détaillée

### Fixed
- **❌ Calculs ML Erronés** : Fini les "8/4 modèles = 200% confidence" - désormais capé à 4/4 = 100%
- **❌ Badge Global Manquant** : Erreur syntaxe WealthContextBar.js (else if après else) corrigée
- **❌ Intelligence ML Vide** : Analytics-unified affichait "--" au lieu des données réelles
- **❌ Logique Dupliquée** : 3 implémentations différentes (badge, analytics, ai-dashboard) unifiées
- **❌ Timezone Incorrect** : Badge utilise désormais Europe/Zurich via `formatZurich()`

### Changed
- **WealthContextBar** : Utilise source ML centralisée au lieu de logique dupliquée
- **Analytics-unified** : Intelligence ML tab utilise `getUnifiedMLStatus()` avec fallback
- **AI Dashboard** : Migration vers source centralisée tout en conservant même logique
- **Configuration API Safe** : `globalConfig` access sécurisé pour éviter erreurs d'import

### Technical
- **Architecture** : Un seul module gère toute la logique ML pour 3 pages
- **Performance** : Cache 2min TTL évite appels API répétés
- **Maintenance** : Plus qu'un seul endroit à modifier pour la logique ML
- **Cohérence** : Calculs identiques partout, fini les divergences

## [2.1.0] - 2024-01-15

### 🧭 Consolidation Navigation & WealthContextBar Cross-Asset

### Added
- **Navigation Canonique** : 6 pages principales - Portfolio, Analytics, Risk, Rebalance, Execution, Settings
- **WealthContextBar Global** : Filtres household/account/module/currency persistants avec sync localStorage+querystring
- **Deep Links System** : Ancres fonctionnelles avec scroll automatique et highlight temporaire (2s)
- **RBAC Admin Dropdown** : Menu visible uniquement pour governance_admin/ml_admin avec ML Command Center, Tools & Debug, Archive
- **Legacy Redirections** : Système de redirections douces vers ancres canoniques pour éviter 404s
- **Badges Standards** : Format uniforme "Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N" (timezone Europe/Zurich)

### Changed
- **Menu Navigation** : Simplifié de 10+ entrées vers 6 pages canoniques avec sous-menus via ancres
- **Archive System** : Pages legacy conservées mais accessibles via Admin > Archive uniquement
- **Cross-Asset Filtering** : WealthContextBar applique filtrage sur pages Rebalance/Execution
- **Documentation** : Restructuration complète avec 7 nouveaux docs (navigation, wealth-modules, governance, runbooks, etc.)

### Technical
- **Components** : `WealthContextBar.js`, `deep-links.js`, `Badges.js`, `legacy-redirects.js`
- **Archive Index** : `static/archive/index.html` avec liens legacy → canonical
- **RBAC Integration** : Vérification rôles localStorage/window.userRoles dans nav.js
- **Event System** : Événement `wealth:change` pour synchronisation cross-composants

### Documentation
- **Navigation & Architecture** : `docs/navigation.md` - Structure menus et liens profonds
- **Modules Patrimoniaux** : `docs/wealth-modules.md` - Crypto/Bourse/Banque/Divers
- **Governance & Caps** : `docs/governance.md` - Hiérarchie SMART→Decision Engine
- **Runbooks** : `docs/runbooks.md` - Procédures incidents (stale/error, VaR>4%, contradiction>55%)
- **Télémétrie** : `docs/telemetry.md` - KPIs système et métriques Prometheus

---

## [2.0.1] - 2024-01-15

### 🎯 Dashboard Global Insight Enhancement

### Added
- **Global Insight Badge**: Dashboard principal affiche maintenant "Updated: HH:MM:SS • Contrad: X% • Cap: Y%" en bas de la tuile
- **Real-time Governance Data**: Badge se met à jour automatiquement avec les données du Decision Engine
- **Cross-dashboard Consistency**: Format cohérent avec les autres dashboards (Analytics, Risk)
- **Store Integration**: Synchronisation via `risk-dashboard-store.js` pour données temps réel

### Changed
- **Badge Position**: Déplacé de haut vers bas de la tuile Global Insight pour cohérence visuelle
- **Data Flow**: Badge récupère timestamp des signaux ML et données policy du store governance
- **Update Triggers**: Badge se rafraîchit lors des changements store et événements `configChanged`

### Technical
- **Function**: `updateGlobalInsightMeta()` pour gestion badge dans `dashboard.html`
- **Store Sync**: Utilise `store.get('governance.ml_signals')` et `store.get('governance.active_policy')`
- **Event Handling**: Écoute changements store via subscription et événements storage cross-tab

### Fixed
- Badge Global Insight maintenant visible et fonctionnel
- Données gouvernance affichées en temps réel sur dashboard principal
- Cohérence visuelle avec format badges des autres dashboards

---

## [2.0.0] - 2024-12-12

### 🔄 Major API Refactoring & Security Improvements

This release contains **BREAKING CHANGES** requiring consumer updates.

### Added
- **Unified Endpoints**: Single approval endpoint `/api/governance/approve/{resource_id}` for both decisions and plans
- **Centralized Alerts**: All alert operations now under `/api/alerts/*` namespace
- **Admin Protection**: ML debug endpoints now require `X-Admin-Key` header
- **Validation Tools**: 
  - `tests/smoke_test_refactored_endpoints.py` - Endpoint validation
  - `find_broken_consumers.py` - Consumer reference scanner  
  - `verify_openapi_changes.py` - Breaking changes analyzer
- **Documentation**: `docs/refactoring.md` with complete migration guide

### Changed
- **ML Namespace**: `/api/ml-predictions/*` → `/api/ml/*` (unified)
- **Risk Namespace**: `/api/advanced-risk/*` → `/api/risk/advanced/*` (consolidated)
- **Governance API**: Unified approval endpoint with `resource_type` parameter
- **Alert Resolution**: Centralized under `/api/alerts/resolve/{alert_id}`
- **Alert Acknowledgment**: Centralized under `/api/alerts/acknowledge/{alert_id}`

### Removed (Security & Production Readiness)
- **Dangerous Endpoints**: 
  - `/api/realtime/publish` - Could allow arbitrary event publishing
  - `/api/realtime/broadcast` - Could spam all connected clients
- **Test Endpoints**: 
  - All `/api/test/*` endpoints - Removed from production
  - All `/api/alerts/test/*` endpoints - Removed from production
- **Duplicate Endpoints**:
  - `/api/risk/alerts/{id}/resolve` - Now `/api/alerts/resolve/{id}`
  - `/api/monitoring/alerts/{id}/resolve` - Now `/api/alerts/resolve/{id}`
  - `/api/portfolio/alerts/{id}/resolve` - Now `/api/alerts/resolve/{id}`

### Fixed
- **Pydantic v2 Compatibility**: Fixed `regex=` → `pattern=` in Field definitions
- **Consumer References**: Updated 13 files with broken endpoint references
- **Test Suites**: Updated E2E tests to work with new architecture
- **Documentation**: Synchronized all docs with new endpoint structure

### Security
- **Endpoint Protection**: ML debug endpoints require admin authentication
- **Attack Surface Reduction**: Removed 5 potentially dangerous endpoints
- **Test Isolation**: No test endpoints exposed in production

### Migration
**Required Actions for Consumers:**
1. Replace `/api/ml-predictions/*` with `/api/ml/*`
2. Remove all `/api/test/*` and `/api/alerts/test/*` calls
3. Update `/api/advanced-risk/*` to `/api/risk/advanced/*`
4. Update `/governance/approve` calls to include `resource_type` in body
5. Centralize alert operations to `/api/alerts/*`

**Tools Available:**
- Run `python find_broken_consumers.py` to scan for broken references
- Run `python tests/smoke_test_refactored_endpoints.py` to validate endpoints
- See `docs/refactoring.md` for complete migration guide

### Performance
- **Namespace Consolidation**: Reduced API surface from 6 to 3 main namespaces
- **Endpoint Efficiency**: Unified endpoints reduce client-side complexity

---

## [1.8.0] - 2024-12-10

### Added
- Phase 3C: Hybrid Intelligence integration
- Advanced ML pipeline management
- Cross-asset correlation monitoring
- Enhanced governance workflows

### Changed
- Improved risk calculation performance
- Enhanced dashboard responsiveness
- Better error handling in ML components

### Fixed
- Memory leaks in ML pipeline
- Cache invalidation issues
- Dashboard synchronization bugs

---

## [1.7.0] - 2024-12-01

### Added
- Phase 2C: ML Alert Predictions
- Predictive alerting system
- Enhanced ML models integration
- Real-time streaming improvements

### Changed
- Optimized risk calculations
- Enhanced UI/UX across dashboards
- Improved API response times

---

## [1.6.0] - 2024-11-15

### Added
- Phase 2B: Cross-asset correlation analysis
- Advanced risk engine
- Multi-exchange support
- Enhanced monitoring

---

*Earlier versions documented in git history*
