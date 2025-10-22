# Documentation — Portail

> **Navigation principale** : Ce fichier sert d'index pour toute la documentation du projet.

---

## 🎯 Vue d'ensemble

### Architecture & Design
- **Architecture** : [ARCHITECTURE.md](ARCHITECTURE.md) - Design système
- **Risk (source canonique)** : [RISK_SEMANTICS.md](RISK_SEMANTICS.md) - Conventions risk scoring
- **Decision Index (Unified Insights)** : [UNIFIED_INSIGHTS_V2.md](UNIFIED_INSIGHTS_V2.md) - Système de scoring unifié
- **UX & Règles UI** : [UX_GUIDE.md](UX_GUIDE.md) - Standards UI/UX

---

## 🖥️ Frontend

### Pages & Components
- **Pages** : [FRONTEND_PAGES.md](FRONTEND_PAGES.md) - Inventaire prod/test/legacy
- **Modules** : [MODULE_MAP.md](MODULE_MAP.md) - Cartographie modules JS
- **Flyout Panel** : [FLYOUT_IMPLEMENTATION_DONE.md](FLYOUT_IMPLEMENTATION_DONE.md) - Web Components (Risk Sidebar)

---

## ⚙️ Backend & API

### API Reference
- **Référence API** : [API_REFERENCE.md](API_REFERENCE.md) - Auto-généré, tous les endpoints
- **Services** : `services/` - Business logic
- **Connecteurs** : `connectors/` - External integrations

### Features
- **P&L Today** : [PNL_TODAY.md](PNL_TODAY.md) - Portfolio tracking
- **Simulation Engine** : [SIMULATION_ENGINE.md](SIMULATION_ENGINE.md) - Backtesting system
- **Sources System** : [SOURCES_SYSTEM.md](SOURCES_SYSTEM.md) - Multi-source data resolution
- **Wealth Modules** : [wealth-modules.md](wealth-modules.md) - Cross-asset tracking

---

## 🔧 Systems & Operations

### Infrastructure
- **Logging** : [LOGGING.md](LOGGING.md) - Système de logs rotatifs (5MB, optimisé IA)
- **Redis** : [REDIS_SETUP.md](REDIS_SETUP.md) - Cache & streaming temps réel
- **Scheduler** : [SCHEDULER.md](SCHEDULER.md) - Background jobs

### Monitoring
- **Performance** : [PERFORMANCE_MONITORING.md](PERFORMANCE_MONITORING.md) - Metrics & alerting
- **Technical Debt** : [TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) - Known issues

---

## 🧪 Testing & Quality

### Testing
- **Guide** : [TESTING_GUIDE.md](TESTING_GUIDE.md) - Strategy & best practices
- **E2E Testing** : [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md) - End-to-end tests

### Code Quality
- **Latest Audit** : [../AUDIT_REPORT_2025-10-19.md](../AUDIT_REPORT_2025-10-19.md) - Code quality audit
- **Refactoring (Phases)** : [REFACTORING_PHASES_SUMMARY.md](REFACTORING_PHASES_SUMMARY.md) - Phases 0-2 summary
- **Refactoring (Dashboard)** : [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) - Risk Dashboard tabs modularization
- **Security** : [TESTS_SECURITY_SUMMARY.md](TESTS_SECURITY_SUMMARY.md) - Security testing

---

## 🚀 Implementation Guides

### Recent Features (Oct 2025)
- **BTC Hybrid Regime Detector** : [BTC_HYBRID_REGIME_DETECTOR.md](BTC_HYBRID_REGIME_DETECTOR.md) - Market regime detection
- **Sentiment Contextual Logic** : [README_SENTIMENT_CONTEXTUAL_LOGIC.md](README_SENTIMENT_CONTEXTUAL_LOGIC.md) - ML sentiment integration
- **Risk Score V2** : [RISK_SCORE_V2_IMPLEMENTATION.md](RISK_SCORE_V2_IMPLEMENTATION.md) - Enhanced risk scoring
- **Decision Index V2** : [DECISION_INDEX_V2.md](DECISION_INDEX_V2.md) - Quality allocation scoring

### Integration & Setup
- **Saxo Integration** : [SAXO_INTEGRATION_SUMMARY.md](SAXO_INTEGRATION_SUMMARY.md) - Bourse/Saxo Bank
- **Quickstart** : [quickstart.md](quickstart.md) - Getting started
- **Dev Checklist** : [DEV_TO_PROD_CHECKLIST.md](DEV_TO_PROD_CHECKLIST.md) - Deployment

---

## 📚 Contribution

### Guidelines
- **Conventions & PR** : [CONTRIBUTING.md](CONTRIBUTING.md) - Code standards
- **Troubleshooting** : [troubleshooting.md](troubleshooting.md) - Common issues
- **Developer Guide** : [developer.md](developer.md) - Development setup

---

## 🗂️ Archives

- **Historique** : [_archive/](_archive/) - Session notes, deprecated docs (17 fichiers archivés Oct 2025)

---

**Dernière mise à jour** : 2025-10-22
**Fichiers actifs** : ~100 docs
**Statut** : ✅ Production-ready
