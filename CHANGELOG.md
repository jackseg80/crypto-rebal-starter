# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2025-10-08

### 🔧 Cap Stability Fix (Oct 2025)

#### Fixed
- **Cap oscillations fixed** ([docs/CAP_STABILITY_FIX.md](docs/CAP_STABILITY_FIX.md))
  - **Problem**: Cap varied 1% → 7% and allocations 45% ↔ 68% with constant scores
  - **Root causes identified**:
    1. Backend/frontend cap desynchronization (backend 7.7% ignored by frontend)
    2. Risk semantics mode changing (legacy/v2 → 31%-63% stables variation)
    3. Cache disabled (recalculation on every call)
    4. Market overrides without hysteresis (flip-flop +10-20%)
  - **Fixes applied**:
    1. Cache reactivated with 30s TTL ([market-regimes.js:233](static/modules/market-regimes.js#L233))
    2. Risk semantics fixed to v2_conservative by default ([market-regimes.js:226](static/modules/market-regimes.js#L226))
    3. Hysteresis widened (gap 10pts vs 4pts before) ([market-regimes.js:171](static/modules/market-regimes.js#L171))
    4. Frontend now reads backend cap as MAX limit ([targets-coordinator.js:485](static/modules/targets-coordinator.js#L485))
  - **Result**: Max variation 0.21% (< 2% target) ✅

#### Added
- **Audit tools**:
  - `tools/audit_governance_state.py` - Backend state inspector (mode, cap, signals, hysteresis)
  - `tools/audit_frontend_state.html` - Frontend state inspector (localStorage, store, risk mode)
- **Tests**: `tests/unit/test_cap_stability.py` - 4 scenarios, all PASSING
  - Cap stability (5 ticks): max variation 0.21% ✅
  - Cap floor check: within bounds 1%-95% ✅
  - NaN protection: variation 0.12% < 15% ✅
  - Manual override: cap = 15.0% exact ✅

#### Documentation
- **Complete analysis**: [docs/CAP_STABILITY_FIX.md](docs/CAP_STABILITY_FIX.md)
  - Before/after comparison
  - Root cause analysis (5 bugs identified)
  - Fix details with code references
  - Test results and validation criteria
  - Deployment instructions
  - Future work (complete v2 migration)

### 🎯 Exposure Cap Overhaul & Risk Semantics V2

### Added
- **Pure function `computeExposureCap()`** ([targets-coordinator.js:337-412](static/modules/targets-coordinator.js#L337-L412))
  - Testable, side-effect-free cap calculation with comprehensive unit tests
  - Regime-based floors (FR/EN support): Euphorie ≥75%, Expansion ≥60%, Neutral ≥40%, etc.
  - Dynamic boost: Expansion + Risk Score ≥80 → floor raised from 60% to 65%
  - Smooth penalty curves instead of binary cliffs (signal quality, volatility)
  - 20+ unit tests covering all regimes, backend states, edge cases ([computeExposureCap.test.js](static/tests/computeExposureCap.test.js))

- **Test Infrastructure**
  - Vitest setup with Happy-DOM environment ([vitest.config.js](vitest.config.js))
  - Comprehensive test suite: 6 describe blocks, 20+ test cases
  - Coverage reports: text + HTML + JSON formats
  - Test scripts: `npm test`, `npm run test:watch`, `npm run test:ui`

### Changed
- **Volatility penalty** - Max reduced from 15pts to 10pts for smoother behavior in high-vol markets
- **Volatility normalization** - Automatic unit handling: `32` (percent) ≡ `0.32` (decimal)
- **Signal quality adjustment** - Continuous gradient penalty (0-10pts) replacing binary cliffs (raw < 0.45 → -10, raw < 0.65 → -5)
- **Backend fallback logic** - Graceful degradation for `stale`/`error` status:
  - **Stale**: -15pts penalty but respects regime floors (no hard-cap)
  - **Error**: -25pts penalty but respects regime floors (no hard-cap)
  - **Before**: Hard-cap 5-8% overriding all market context ❌
  - **After**: Regime-aware fallback preserving market logic ✅

### Fixed
- **`renderTargetsTable()` crash** ([risk-dashboard.html:6053-6095](static/risk-dashboard.html#L6053-L6095))
  - Robust validation against `null`/`NaN`/`undefined` allocations
  - Comprehensive filtering with `isValid = value != null && typeof value === 'number' && !isNaN(value)`
  - Graceful error messages instead of crashes
  - Console warnings for filtered invalid entries

- **Risk Score semantics inversion** ([market-regimes.js:219-270](static/modules/market-regimes.js#L219-L270))
  - **V2 mode activated**: Risk Score now correctly interpreted as robustness (high = low perceived risk)
  - **Legacy mode deprecated**: Inverted logic where high Risk = danger (will be removed in v4.0)
  - **Feature flag**: `localStorage.setItem('RISK_SEMANTICS_MODE', 'v2_conservative')`
  - **Doc reference**: [docs/RISK_SEMANTICS.md](docs/RISK_SEMANTICS.md) - Canonical risk semantics documentation

- **Exposure cap calculation** - Complete architectural overhaul:
  - **Before (Legacy + 40% cap)**:
    - Euphorie (73) + Risk (90) → 40% cap → 60% stables, 18% BTC ❌
    - Expansion (61) + Risk (90) → 40% cap → 60% stables, 18% BTC ❌
  - **After (V2 + Pure Function)**:
    - Euphorie (73) + Risk (90) → 80%+ cap → 20-25% stables, 35%+ BTC ✅
    - Expansion (61) + Risk (90) → 65% cap (boost) → 47% stables, 30% BTC ✅
  - **Impact**: +20-25 percentage points exposure to risky assets in bull markets

### Performance
- **Allocation calculations** - Deterministic, cacheable pure functions reduce recomputation overhead
- **Test execution** - Vitest parallel test runner for fast feedback loops

### Documentation
- **CHANGELOG.md** - Comprehensive documentation of changes with links to code
- **Test coverage** - Inline JSDoc comments for all test cases
- **Migration guide** - Backward compatible, no user action required

### Migration Guide

#### For Users
1. **No action required** - Changes are backward compatible
2. Risk semantics V2 activates automatically on first page load after update
3. To revert to legacy mode (not recommended): `localStorage.setItem('RISK_SEMANTICS_MODE', 'legacy')`
4. To enable debug logs: `localStorage.setItem('DEBUG_RISK', '1'); location.reload();`

#### For Developers
1. **Install test dependencies**: `npm install`
2. **Run tests**: `npm test` or `npm run test:watch` (development)
3. **Update custom allocation logic** to use `computeExposureCap()` instead of inline calculations
4. **Review regime floors** if customizing market regime behavior
5. **Check debug logs** with `window.__DEBUG_RISK__ = true` or `localStorage.DEBUG_RISK = '1'`

### Testing

```bash
# Install dependencies
npm install

# Run all tests
npm test

# Watch mode (development)
npm run test:watch

# UI test explorer
npm run test:ui

# Coverage report
npm run test:coverage
```

#### Test Coverage
- ✅ 20+ unit tests for `computeExposureCap()`
- ✅ All market regimes: Euphorie, Expansion, Neutral, Accumulation, Bear, Capitulation
- ✅ Backend status handling: ok, stale, error, unknown
- ✅ Volatility normalization: decimal (0.32) vs percent (32)
- ✅ Edge cases: null values, unknown regimes, extreme volatility, mixed case regime names
- ✅ Regime floors: All regimes respect their minimum thresholds
- ✅ Dynamic boost: Expansion + Risk ≥80 verified
- ✅ Signal quality penalties: Continuous gradient validation

### Roadmap

#### Next Steps (Planned)
- [ ] UI debug badges for cap breakdown visualization
- [ ] Allocation snapshots tests (detect regressions in target allocations)
- [ ] Progressive boost by Risk Score tranches (≥85, 80-84, <80)
- [ ] Regime transition smoothing (prevent allocation whipsaw)
- [ ] On-chain score null fix (ensure intelligence always available)

#### Under Consideration
- [ ] Machine learning cap predictor (replace heuristic rules)
- [ ] User-configurable regime floors via UI
- [ ] Multi-timeframe regime detection (hourly, daily, weekly consensus)
- [ ] Backtesting framework with historical price data

---

## [3.0.0] - 2025-09-17

### 🚀 Major Features - Système d'Allocation Dynamique

#### Élimination des Presets Hardcodés
- **BREAKING**: Suppression complète des presets figés (BTC 40%, ETH 30%, Stables 20/30/50%)
- **NEW**: Calculs d'allocation contextuels basés sur cycle de marché, régime, et concentration wallet
- **NEW**: Source canonique unique `u.targets_by_group` pour cohérence parfaite Analytics ↔ Rebalance
- **NEW**: Fonction `computeMacroTargetsDynamic()` avec modulateurs intelligents

#### Synchronisation Analytics ↔ Rebalance
- **FIXED**: "Allocation Suggérée (Unified)" maintenant peuplée automatiquement dans rebalance.html
- **NEW**: Sauvegarde automatique des données unified avec nouveau format v2
- **CRITICAL**: Correction `targetsSource = data.targets` vs `data.execution_plan`
- **NEW**: Support rétrocompatible ancien + nouveau format localStorage

### 🔧 Technical Changes

#### Core Engine (`static/core/unified-insights-v2.js`)
- **ADD**: `computeMacroTargetsDynamic(ctx, rb, walletStats)` - remplace presets
- **CHANGE**: Construction `targets_by_group` via calculs vs templates statiques
- **ADD**: Modulateurs bull/bear/hedge + diversification selon concentration wallet
- **ADD**: Garde-fous cohérence stables = risk_budget.target_stables_pct (source de vérité)

#### UI Components (`static/components/UnifiedInsights.js`)
- **REMOVE**: Logique preset hardcodée (elimination complète lignes 680-725)
- **CHANGE**: Lecture directe `u.targets_by_group` vs `buildTheoreticalTargets()`
- **REMOVE**: Import `buildTheoreticalTargets` (function deprecated)
- **ADD**: Logs debug pour validation données dynamiques

#### Pages HTML
- **Analytics** (`static/analytics-unified.html`):
  - **ADD**: `saveUnifiedDataForRebalance()` - sauvegarde automatique
  - **ADD**: Format données v2 avec source `analytics_unified_v2`
- **Rebalance** (`static/rebalance.html`):
  - **FIXED**: `syncUnifiedSuggestedTargets()` support sources v2
  - **ADD**: Protection taxonomie `forceReloadTaxonomy()`
  - **ADD**: Logs debug détaillés structure données

### 🐛 Critical Bug Fixes

#### Allocation Display Issues
- **FIXED**: "Others 31%" incohérent → allocations cohérentes via source unique
- **FIXED**: Inconsistance Objectifs Théoriques vs Plan d'Exécution → même source
- **FIXED**: rebalance.html "Allocation Suggérée (Unified)" vide → peuplée automatiquement
- **FIXED**: Affichage `estimated_iters: 2.0%` au lieu allocations réelles

#### Data Synchronization
- **FIXED**: Analytics et Rebalance utilisaient sources différentes → u.targets_by_group unique
- **FIXED**: Presets ignoraient risk_budget.target_stables_pct → intégration native
- **FIXED**: Taxonomie non chargée causant "Others" gonflé → forceReloadTaxonomy()

### 📚 Documentation
- **NEW**: `docs/dynamic-allocation-system.md` - guide complet nouveau système
- **UPDATE**: `README.md` - section "Nouvelles Fonctionnalités v3.0"
- **NEW**: Commentaires détaillés code + logs explicites

### 💔 Breaking Changes
- **REMOVE**: Presets hardcodés dans tous les fichiers
- **REMOVE**: `buildTheoreticalTargets()` calls (replaced by dynamic computation)
- **CHANGE**: Allocations maintenant contextuelles vs statiques (amélioration UX)

**Migration**: Rétrocompatibilité assurée, aucune action utilisateur requise.

---

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

## 2025-09-26 - Tri stable stratégies & équilibrage visuel

### 🎯 Tri stable des stratégies Rebalance
- **Nouveau**: Système de priorité garantissant l'ordre Unified Analytics → CCS Dynamic → statiques
- **Fonction `rank()`**: Attribution de scores (0=Unified live, 1=Unified placeholder, 2=CCS live, 3=CCS placeholder/error, 10=statiques)
- **Tri stable**: Maintien de l'ordre même après rafraîchissement dynamique via `refreshDynamicStrategy()`
- **Localisation**: Support français pour le tri alphabétique secondaire via `localeCompare('fr')`

### 🎨 Équilibrage visuel (Solution C)
- **Filler invisible**: Ajout automatique d'éléments invisibles quand 1 carte reste sur la dernière ligne
- **Détection responsive**: Activation uniquement si grille ≥3 colonnes et `(cartes % colonnes) === 1`
- **Accessibilité**: Filler marqué `aria-hidden="true"` pour lecteurs d'écran
- **Performance**: Gestion d'erreur avec `try/catch` pour éviter les crashes

### 📱 Adaptation responsive améliorée
- **Breakpoint ajusté**: Passage à 4 colonnes dès 1280px (au lieu de 1440px)
- **Évite lignes orphelines**: Réduction du risque de ligne avec 1 seule carte sur écrans larges
- **Rétrocompatibilité**: Maintien du comportement 3 colonnes ≥1200px inchangé

### 🔧 Technical Changes
- **Fichier modifié**: `static/rebalance.html`
- **Fonction `renderStrategiesUI()`**: Ajout tri stable avant `.map()` et équilibrage après `innerHTML`
- **CSS responsive**: Modification breakpoint `@media (min-width: 1280px)`

### ✅ Résultat
- Interface cohérente avec Unified Analytics toujours en premier
- CCS Dynamic systématiquement en deuxième position
- Équilibrage visuel optimal sur toutes les tailles d'écran
- Pas de ligne orpheline avec une seule carte


