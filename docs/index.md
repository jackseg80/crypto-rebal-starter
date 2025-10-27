# Documentation Index

Index complet de la documentation du projet Crypto Rebal Starter.

## 📚 Essentiels

### Pour Humains
- **[README.md](../README.md)** - Guide principal (Quick start, features, architecture)
- **[quickstart.md](quickstart.md)** - Guide démarrage pas à pas
- **[user-guide.md](user-guide.md)** - Guide utilisateur complet
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Guidelines de contribution

### Pour Agents IA
- **[CLAUDE.md](../CLAUDE.md)** ⭐ - **Source canonique pour IA** (règles critiques, patterns, quick checks)
- **[AGENTS.md](../AGENTS.md)** - Pointeur vers CLAUDE.md
- **[agent.md](../agent.md)** - Pointeur vers CLAUDE.md
- **[GUIDE_IA.md](../GUIDE_IA.md)** - Pointeur vers CLAUDE.md
- **[GEMINI.md](../GEMINI.md)** - Pointeur vers CLAUDE.md

## 🏗️ Architecture & Design

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Architecture système détaillée
- **[API_REFERENCE.md](API_REFERENCE.md)** - API complète (325 endpoints, 19 namespaces)
- **[FRONTEND_PAGES.md](FRONTEND_PAGES.md)** - Inventaire pages HTML (101 pages)
- **[MODULE_MAP.md](MODULE_MAP.md)** - Inventaire modules JS (70 modules)
- **[navigation.md](navigation.md)** - Structure navigation UI
- **[configuration.md](configuration.md)** - Configuration système

## 🎯 Features & Systèmes

### Allocation & Rebalancing
- **[ALLOCATION_ENGINE_V2.md](ALLOCATION_ENGINE_V2.md)** - Allocation topdown hierarchical
- **[dynamic-allocation-system.md](dynamic-allocation-system.md)** - Système allocation dynamique
- **[PHASE_ENGINE.md](PHASE_ENGINE.md)** - Phase Engine (ETH expansion, altseason, risk-off)
- **[UNIFIED_INSIGHTS_V2.md](UNIFIED_INSIGHTS_V2.md)** - Decision Index unifié
- **[DECISION_INDEX_V2.md](DECISION_INDEX_V2.md)** - Decision Index V2 (dual scoring)

### Risk Management
- **[RISK_SEMANTICS.md](RISK_SEMANTICS.md)** ⭐ - **Règle canonique Risk Score**
- **[RISK_SCORE_V2_IMPLEMENTATION.md](RISK_SCORE_V2_IMPLEMENTATION.md)** - Risk Score V2
- **[RISK_SCORING_MODULE.md](RISK_SCORING_MODULE.md)** - Module central risk scoring
- **[risk-dashboard.md](risk-dashboard.md)** - Risk Dashboard guide
- **[STRUCTURE_MODULATION_V2.md](STRUCTURE_MODULATION_V2.md)** - Structure modulation

### Governance & Execution
- **[governance.md](governance.md)** - Système de gouvernance
- **[GOVERNANCE_FIXES_OCT_2025.md](GOVERNANCE_FIXES_OCT_2025.md)** - Freeze semantics, TTL vs Cooldown
- **[CAP_STABILITY_FIX.md](CAP_STABILITY_FIX.md)** - Hystérésis anti flip-flop
- **[CAP_OSCILLATION_ANALYSIS.md](CAP_OSCILLATION_ANALYSIS.md)** - Analyse oscillations cap
- **[CAP_MONITORING_GUIDE.md](CAP_MONITORING_GUIDE.md)** - Guide monitoring cap

### Simulation & Testing
- **[SIMULATION_ENGINE.md](SIMULATION_ENGINE.md)** - Simulateur pipeline complet
- **[SIMULATION_ENGINE_ALIGNMENT.md](SIMULATION_ENGINE_ALIGNMENT.md)** - Alignement production
- **[SIMULATOR_USER_ISOLATION_FIX.md](SIMULATOR_USER_ISOLATION_FIX.md)** - Isolation multi-tenant
- **[SIMULATOR_LIVE_MODE_FIX.md](SIMULATOR_LIVE_MODE_FIX.md)** - Fix mode live

### Bourse (Saxo Integration)
- **[SAXO_INTEGRATION_SUMMARY.md](SAXO_INTEGRATION_SUMMARY.md)** - Intégration Saxo complète
- **[SAXO_DASHBOARD_MODERNIZATION.md](SAXO_DASHBOARD_MODERNIZATION.md)** - Modernisation dashboard
- **[SAXO_IMPORT_FIX_GUIDE.md](SAXO_IMPORT_FIX_GUIDE.md)** - Guide import positions
- **[SAXO_MULTI_TENANT_FIX.md](SAXO_MULTI_TENANT_FIX.md)** - Fix multi-tenant
- **[SAXO_ASSET_CLASS_FIX.md](SAXO_ASSET_CLASS_FIX.md)** - Fix classification assets
- **[STOP_LOSS_SYSTEM.md](STOP_LOSS_SYSTEM.md)** - Stop loss intelligent (5 méthodes)
- **[STOP_LOSS_BACKTEST_RESULTS.md](STOP_LOSS_BACKTEST_RESULTS.md)** - Résultats backtest

## 💾 Données & Sources

- **[SOURCES_SYSTEM.md](SOURCES_SYSTEM.md)** - Sources System v2
- **[SOURCES_MIGRATION_DATA_FOLDER.md](SOURCES_MIGRATION_DATA_FOLDER.md)** - Migration data/
- **[P&L_TODAY_USAGE.md](P&L_TODAY_USAGE.md)** - P&L Today tracking
- **[PNL_TODAY.md](PNL_TODAY.md)** - P&L Today documentation
- **[DI_HISTORY_SYSTEM.md](DI_HISTORY_SYSTEM.md)** - Decision Index History
- **[universe.md](universe.md)** - Universe management

## 🔧 Infrastructure & Performance

- **[REDIS_SETUP.md](REDIS_SETUP.md)** - Redis setup (cache & streaming)
- **[LOGGING.md](LOGGING.md)** - Système logs rotatifs (5MB x3, optimisé IA)
- **[PERFORMANCE_MONITORING.md](PERFORMANCE_MONITORING.md)** - Monitoring performance
- **[CACHE_TTL_OPTIMIZATION.md](CACHE_TTL_OPTIMIZATION.md)** - Optimisation TTL cache
- **[CRYPTO_TOOLBOX.md](CRYPTO_TOOLBOX.md)** - Crypto Toolbox scraping
- **[CRYPTO_TOOLBOX_PARITY.md](CRYPTO_TOOLBOX_PARITY.md)** - Parity checks
- **[START_MODES.md](START_MODES.md)** - Modes démarrage serveur
- **[SCHEDULER.md](SCHEDULER.md)** - Scheduler jobs

## 🎨 UI & Components

- **[RISK_SIDEBAR_FULL_IMPLEMENTATION.md](RISK_SIDEBAR_FULL_IMPLEMENTATION.md)** - Risk Sidebar réutilisable
- **[WEALTH_CONTEXT_BAR_DYNAMIC_SOURCES.md](WEALTH_CONTEXT_BAR_DYNAMIC_SOURCES.md)** - Context bar dynamique
- **[WEALTH_CONTEXT_BAR_FIXES_OCT_2025.md](WEALTH_CONTEXT_BAR_FIXES_OCT_2025.md)** - Fixes context bar
- **[SCORE_COLOR_SEMANTICS_FIX.md](SCORE_COLOR_SEMANTICS_FIX.md)** - Sémantique couleurs scores

## 🤖 ML & Intelligence

- **[ml-centralization.md](ml-centralization.md)** - Centralisation ML
- **[HYBRID_REGIME_DETECTOR.md](HYBRID_REGIME_DETECTOR.md)** - Détecteur régime hybride
- **[BTC_HYBRID_REGIME_DETECTOR.md](BTC_HYBRID_REGIME_DETECTOR.md)** - Détecteur BTC spécifique
- **[ML_ALERT_PREDICTOR_REAL_DATA_OCT_2025.md](ML_ALERT_PREDICTOR_REAL_DATA_OCT_2025.md)** - ML Alert Predictor

## 🧪 Tests & Quality

- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Guide tests (unitaires/intégration/E2E)
- **[E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md)** - Tests End-to-End
- **[TEST_FIXES_REPORT.md](TEST_FIXES_REPORT.md)** - Rapport fixes tests
- **[TESTS_SECURITY_SUMMARY.md](TESTS_SECURITY_SUMMARY.md)** - Tests sécurité
- **[DEV_TO_PROD_CHECKLIST.md](DEV_TO_PROD_CHECKLIST.md)** - Checklist production

## 🔒 Sécurité

- **[SECURITY.md](../SECURITY.md)** - Politique sécurité
- **[AUDIT_RESPONSE.md](AUDIT_RESPONSE.md)** - Réponse audit sécurité
- **[HARDENING_SUMMARY.md](HARDENING_SUMMARY.md)** - Résumé hardening

## 🛠️ Développement & Refactoring

- **[developer.md](developer.md)** - Guide développeur
- **[refactoring.md](refactoring.md)** - Migration et refactoring
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Résumé refactoring
- **[TECHNICAL_DEBT.md](TECHNICAL_DEBT.md)** - Dette technique
- **[BUGS_TO_FIX_NEXT.md](BUGS_TO_FIX_NEXT.md)** - Bugs à corriger

### Code Quality & Fixes (Oct 2025)
- **[BARE_EXCEPTIONS_FIX_OCT_2025.md](BARE_EXCEPTIONS_FIX_OCT_2025.md)** - Fix bare exceptions
- **[CONSOLE_LOG_CLEANUP_OCT_2025.md](CONSOLE_LOG_CLEANUP_OCT_2025.md)** - Cleanup console.log
- **[HARDCODED_URLS_FIX_OCT_2025.md](HARDCODED_URLS_FIX_OCT_2025.md)** - Fix URLs hardcodées
- **[LOG_OPTIMIZATION_OCT_2025.md](LOG_OPTIMIZATION_OCT_2025.md)** - Optimisation logs
- **[CLEANUP_LEGACY_SOURCES_OCT_2025.md](CLEANUP_LEGACY_SOURCES_OCT_2025.md)** - Cleanup legacy
- **[UNUSED_CODE_AUDIT_2025-10-22.md](UNUSED_CODE_AUDIT_2025-10-22.md)** - Audit code inutilisé

### Specific Fixes
- **[FIX_GROUP_CLASSIFICATION_CONSISTENCY.md](FIX_GROUP_CLASSIFICATION_CONSISTENCY.md)** - Fix classification
- **[PORTFOLIO_MONITORING_FIX_OCT_2025.md](PORTFOLIO_MONITORING_FIX_OCT_2025.md)** - Fix monitoring
- **[ALERT_REDUCTION_AUTO_CLEAR.md](ALERT_REDUCTION_AUTO_CLEAR.md)** - Auto-clear alertes
- **[RECOMMENDATIONS_STABILITY_FIX.md](RECOMMENDATIONS_STABILITY_FIX.md)** - Stabilité recommandations
- **[SCORE_CACHE_HARD_REFRESH_FIX.md](SCORE_CACHE_HARD_REFRESH_FIX.md)** - Hard refresh cache
- **[SCORE_STABILITY_COMPLETE_FIX.md](SCORE_STABILITY_COMPLETE_FIX.md)** - Stabilité scores
- **[CAP_FIX_COMPLETE_SUMMARY.md](CAP_FIX_COMPLETE_SUMMARY.md)** - Fix cap complet

## 📊 Phase Reports & Completion

- **[REFACTOR_PHASE0_COMPLETE.md](REFACTOR_PHASE0_COMPLETE.md)** - Phase 0 complétée
- **[REFACTOR_PHASE1_COMPLETE.md](REFACTOR_PHASE1_COMPLETE.md)** - Phase 1 complétée
- **[REFACTOR_PHASE2_COMPLETE.md](REFACTOR_PHASE2_COMPLETE.md)** - Phase 2 complétée
- **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** - Implémentation complète
- **[PHASE_2B2_CROSS_ASSET_CORRELATION.md](PHASE_2B2_CROSS_ASSET_CORRELATION.md)** - Phase 2B2
- **[PHASE_2C_ML_ALERT_PREDICTIONS.md](PHASE_2C_ML_ALERT_PREDICTIONS.md)** - Phase 2C
- **[PHASE2A_PERFORMANCE_RESULTS.md](PHASE2A_PERFORMANCE_RESULTS.md)** - Phase 2A
- **[PHASE3_DUAL_WINDOW_BLEND_SUMMARY.md](PHASE3_DUAL_WINDOW_BLEND_SUMMARY.md)** - Phase 3

## 📝 Autres Ressources

- **[api.md](api.md)** - Documentation API générale
- **[architecture-risk-routers.md](architecture-risk-routers.md)** - Architecture risk routers
- **[consolidation-finale.md](consolidation-finale.md)** - Consolidation finale
- **[contradiction-system.md](contradiction-system.md)** - Système contradiction
- **[integrations.md](integrations.md)** - Intégrations (CoinTracking, Kraken, FRED)
- **[monitoring.md](monitoring.md)** - Système monitoring
- **[runbooks.md](runbooks.md)** - Runbooks opérationnels
- **[telemetry.md](telemetry.md)** - Télémétrie
- **[troubleshooting.md](troubleshooting.md)** - Résolution problèmes
- **[wealth-modules.md](wealth-modules.md)** - Modules wealth
- **[TODO_WEALTH_MERGE.md](TODO_WEALTH_MERGE.md)** - TODO wealth merge
- **[WATCHER_ISSUE.md](WATCHER_ISSUE.md)** - Issue watcher

## 📦 Projets Connexes

- **[AUDIT_REPORT_2025-10-19.md](../AUDIT_REPORT_2025-10-19.md)** - Audit code complet
- **[GOD_SERVICES_REFACTORING_PLAN.md](../GOD_SERVICES_REFACTORING_PLAN.md)** - Plan refactoring services
- **[DUPLICATE_CODE_CONSOLIDATION.md](../DUPLICATE_CODE_CONSOLIDATION.md)** - Consolidation duplications
- **[CHANGELOG.md](../CHANGELOG.md)** - Historique versions

## 🗄️ Archives

- **[_archive/](./archive/)** - Documentation obsolète conservée pour historique
  - **[_archive/session_notes/](_archive/session_notes/)** - Notes de sessions archivées

---

## 🎯 Comment Utiliser Cet Index

### Nouvelle Session IA
1. Lire **[CLAUDE.md](../CLAUDE.md)** en premier
2. Consulter sections pertinentes selon la tâche
3. Pointer vers docs spécialisées pour détails

### Nouveau Développeur
1. **[README.md](../README.md)** - Quick start
2. **[quickstart.md](quickstart.md)** - Setup détaillé
3. **[developer.md](developer.md)** - Workflow dev
4. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Comprendre le système

### Debugging / Troubleshooting
1. **[troubleshooting.md](troubleshooting.md)** - Problèmes courants
2. **[LOGGING.md](LOGGING.md)** - Analyser logs
3. **[runbooks.md](runbooks.md)** - Procédures opérationnelles

### Feature Spécifique
- Utiliser la recherche (Ctrl+F) dans cet index
- Consulter la doc spécialisée correspondante
- Revenir à CLAUDE.md pour patterns de code

---

**Dernière mise à jour** : Oct 2025
**Statut** : ✅ Production Stable
