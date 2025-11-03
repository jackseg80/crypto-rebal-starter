# SmartFolio

Plateforme intelligente de gestion de patrimoine cross-asset (Crypto, Bourse, Banque) avec IA, ML avancé et gestion unifiée des risques. Architecture modulaire autour de 6 pages canoniques optimisées pour la prise de décision en temps réel.

## 🎯 Features Principales

- **Decision Engine** avec gouvernance intelligente (approvals AI/manuels, freeze semantics)
- **Rebalancing dynamique** basé sur cycle marché, régime, concentration wallet
- **Phase Engine** : détection proactive de phases (ETH expansion, altseason, risk-off) avec tilts automatiques
- **ML avancé** : LSTM, Transformers, sentiment analysis, signaux temps réel
- **Risk management v2** : VaR/CVaR, stress testing, circuit breakers, dual-window metrics
- **P&L Today** : calcul Profit & Loss en temps réel avec anchor points (midnight/session)
- **Simulateur Pipeline** : test complet Decision → Risk Budget → Targets → Governance → Execution
- **Multi-tenant** : isolation complète des données par utilisateur et source

## 🚀 Quick Start

### Prérequis
- Python 3.10+
- pip, virtualenv
- (Optionnel) Redis pour cache avancé et streaming temps réel

### Installation

**Windows (PowerShell):**
```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate
pip install -r requirements.txt
copy .env.example .env
# Éditer .env avec vos clés API (CoinGecko, CoinTracking, FRED)
```

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec vos clés API
```

**Playwright (optionnel, pour crypto-toolbox scraping):**
```bash
pip install playwright
playwright install chromium
```

### Lancement

**Windows:**
```powershell
.\\.venv\\Scripts\\Activate
.\\start_dev.ps1
# Avec scheduler (P&L snapshots, OHLCV updates): .\\start_dev.ps1 -EnableScheduler
```

**Linux/macOS:**
```bash
source .venv/bin/activate
./start_dev.sh
# Avec scheduler: ./start_dev.sh --enable-scheduler
```

**Accès Web:**
- **Settings** : http://localhost:8080/static/settings.html (configuration initiale)
- **Dashboard** : http://localhost:8080/static/dashboard.html
- **API Docs** : http://localhost:8080/docs

## 📊 Pages Principales

| Page | Description | URL |
|------|-------------|-----|
| **Dashboard** | Vue globale portfolio + P&L Today | `/static/dashboard.html` |
| **Analytics** | ML temps réel + Decision Index | `/static/analytics-unified.html` |
| **Risk** | Risk management + Governance + Alertes | `/static/risk-dashboard.html` |
| **Rebalance** | Plans de rééquilibrage dynamiques | `/static/rebalance.html` |
| **Execution** | Exécution temps réel avec validation | `/static/execution.html` |
| **Simulations** | Simulateur pipeline complet | `/static/simulations.html` |
| **Saxo Dashboard** | Bourse (stocks, ETFs, fonds) avec stop-loss intelligent | `/static/saxo-dashboard.html` |

## 🏗️ Architecture

### Backend (FastAPI)
```
api/
├── main.py                          # App principale + routers
├── deps.py                          # Dependency injection (multi-tenant)
├── execution/                       # Decision Engine + Governance
├── *_endpoints.py                   # 30+ routers modulaires
services/
├── balance_service.py               # Résolution données multi-source
├── execution/governance.py          # Decision Engine + Freeze semantics
├── ml/orchestrator.py              # ML orchestration
├── risk_scoring.py                  # Risk Score central (dual system)
├── portfolio.py                     # P&L tracking
```

### Frontend (Vanilla JS + ES6 Modules)
```
static/
├── *.html                           # Pages principales
├── core/
│   ├── allocation-engine.js         # Allocation topdown hierarchical
│   └── unified-insights-v2.js       # Phase Engine
├── components/
│   ├── nav.js                       # Navigation unifiée
│   ├── decision-index-panel.js      # Decision Index UI
│   └── flyout-panel.js              # Risk Sidebar réutilisable
├── global-config.js                 # Config frontend centralisée
```

### Données
```
data/
└── users/{user_id}/
    ├── cointracking/data/           # CSV crypto (versioning auto)
    ├── saxobank/data/               # CSV bourse
    ├── config/config.json           # Config utilisateur
    └── config/sources.json          # Modules actifs
```

## 🔒 Sécurité

- ✅ **Secrets management** : `.env` template, pre-commit hooks (detect-secrets + gitleaks)
- ✅ **Frontend sécurisé** : 464 console.log → debugLogger, ESLint (no-console, no-eval)
- ✅ **HTTP headers** : CSP, X-Content-Type-Options, X-Frame-Options, rate limiting
- ✅ **Tests automatisés** : validation headers + sécurité

📖 Détails complets : [SECURITY.md](SECURITY.md)

## 📚 Documentation

### Essentiels
- **[CLAUDE.md](CLAUDE.md)** - Guide pour agents IA (règles critiques, patterns, quick checks)
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Architecture détaillée
- **[Quick Start](docs/quickstart.md)** - Guide démarrage pas à pas
- **[API Reference](docs/API_REFERENCE.md)** - Endpoints et schemas
- **[User Guide](docs/user-guide.md)** - Guide utilisateur complet

### Features & Systèmes
- **Allocation** : [ALLOCATION_ENGINE_V2.md](docs/ALLOCATION_ENGINE_V2.md) - Topdown hierarchical, floors, incumbency
- **Decision Index** : [DECISION_INDEX_V2.md](docs/DECISION_INDEX_V2.md) - Dual scoring (DI vs Régime)
- **Risk Management** : [RISK_SEMANTICS.md](docs/RISK_SEMANTICS.md), [RISK_SCORE_V2_IMPLEMENTATION.md](docs/RISK_SCORE_V2_IMPLEMENTATION.md)
- **Governance** : [GOVERNANCE_FIXES_OCT_2025.md](docs/GOVERNANCE_FIXES_OCT_2025.md) - Freeze semantics, TTL vs Cooldown
- **Phase Engine** : [PHASE_ENGINE.md](docs/PHASE_ENGINE.md) - Détection phases marché
- **Simulateur** : [SIMULATION_ENGINE.md](docs/SIMULATION_ENGINE.md) - Pipeline complet
- **Sources System** : [SOURCES_SYSTEM.md](docs/SOURCES_SYSTEM.md) - Multi-source unifiée
- **Stop Loss Intelligent** : [STOP_LOSS_SYSTEM.md](docs/STOP_LOSS_SYSTEM.md) - 5 méthodes adaptatives
- **P&L Today** : [P&L_TODAY_USAGE.md](docs/P&L_TODAY_USAGE.md) - Tracking temps réel
- **Redis** : [REDIS_SETUP.md](docs/REDIS_SETUP.md) - Cache & streaming
- **Logging** : [LOGGING.md](docs/LOGGING.md) - Logs rotatifs (5MB x3, optimisé IA)

### Développement
- **[Developer Guide](docs/developer.md)** - Setup, tests, workflow
- **[Testing Guide](docs/TESTING_GUIDE.md)** - Tests unitaires/intégration/E2E
- **[Runbooks](docs/runbooks.md)** - Procédures opérationnelles
- **[Troubleshooting](docs/troubleshooting.md)** - Résolution problèmes courants
- **[Contributing](CONTRIBUTING.md)** - Guidelines contribution

### Index Complet
📖 **[Index Documentation](docs/index.md)** - Liste complète des docs disponibles

## 🔧 Configuration

### Multi-Utilisateurs
6 utilisateurs configurés : `demo`, `jack`, `donato`, `elda`, `roberto`, `clea`
- **Isolation complète** : données, config, clés API séparées
- **Sélecteur dynamique** : barre navigation (indépendant du menu Admin)
- **Sources dynamiques** : affichage auto des CSV + API selon config

### Sources de Données
1. **CSV locaux** : upload via Settings → Sources (versioning automatique)
2. **API CoinTracking** : si clés configurées (temps réel)
3. **API Saxo** : import positions bourse
4. **Banks** : comptes bancaires manuels

### Clés API Recommandées
```env
# .env
COINGECKO_API_KEY=your_key_here        # Prix crypto (3 min cache)
COINTRACKING_API_KEY=your_key_here     # Balances temps réel
FRED_API_KEY=your_key_here             # Macro data
REDIS_URL=redis://localhost:6379/0     # Cache avancé (optionnel)
```

## 📊 Endpoints Principaux

```bash
# Health & Config
GET  /healthz                                    # Status application
GET  /api/config                                 # Configuration frontend

# Portfolio
GET  /balances/current?source=cointracking       # Balances actuelles
GET  /portfolio/metrics?user_id=demo             # Métriques + P&L Today
POST /portfolio/snapshot                         # Créer snapshot P&L

# ML & Analytics
GET  /api/ml/sentiment/symbol/BTC                # Sentiment ML
GET  /api/ml/cycle_score                         # Cycle Score
GET  /api/ml/onchain_score                       # On-Chain Score

# Risk
GET  /api/risk/dashboard                         # Dashboard risk complet
GET  /api/risk/bourse/dashboard                  # Risk bourse (Saxo)

# Governance & Execution
GET  /execution/governance/state                 # État gouvernance
POST /execution/governance/approve               # Approuver plan
GET  /execution/monitoring/live                  # Monitoring temps réel

# Sources
GET  /api/sources/list                           # Sources disponibles
POST /api/sources/upload                         # Upload fichier
GET  /api/sources/test                           # Tester source
```

📖 API complète : http://localhost:8080/docs (Swagger UI)

## 🧪 Tests

```bash
# Activer environnement
.venv\\Scripts\\Activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Tests unitaires
pytest tests/unit -v

# Tests intégration
pytest tests/integration -v

# Tests E2E (nécessite serveur lancé)
pytest tests/e2e -v

# Coverage
pytest --cov=services --cov=api --cov-report=html
```

## 🎯 Règles Critiques (Développeurs)

### 1. Multi-Tenant OBLIGATOIRE
```python
# Backend: TOUJOURS utiliser dependency injection
from api.deps import get_active_user

@router.get("/endpoint")
async def endpoint(user: str = Depends(get_active_user)):
    pass
```

```javascript
// Frontend: TOUJOURS utiliser window.loadBalanceData()
const balanceResult = await window.loadBalanceData(true);
```

### 2. Risk Score = Positif (0-100)
- **Convention** : Plus haut = plus robuste
- **❌ INTERDIT** : Ne jamais inverser avec `100 - scoreRisk`

### 3. Decision Index vs Régime
- **Decision Index** : Qualité technique allocation (65/45 fixe)
- **Score de Régime** : État marché (0-100 variable)
- **Phase** : Basée UNIQUEMENT sur Cycle Score (<70=bearish, 70-90=moderate, ≥90=bullish)

📖 Détails : [CLAUDE.md](CLAUDE.md)

## 🤝 Contributing

Contributions bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour guidelines.

**Workflow recommandé :**
1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Ouvrir Pull Request

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique complet des versions.

## 📄 Licence

Ce projet est un starter/template pour usage personnel ou éducatif.

## 🆘 Support

- **Documentation** : [docs/index.md](docs/index.md)
- **Issues** : Pour bugs et feature requests
- **Troubleshooting** : [docs/troubleshooting.md](docs/troubleshooting.md)

---

**Status** : ✅ Production Stable (Oct 2025)
**Version** : 3.0
**Stack** : Python 3.10+ • FastAPI • Vanilla JS (ES6) • Redis (optionnel)
