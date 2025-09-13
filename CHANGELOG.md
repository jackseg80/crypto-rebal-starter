# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Documentation**: `REFACTORING_SUMMARY.md` with complete migration guide

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
- See `REFACTORING_SUMMARY.md` for complete migration guide

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