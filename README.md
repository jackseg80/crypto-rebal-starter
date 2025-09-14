# Crypto Rebal Starter — Cockpit Patrimoine Modulaire

Plateforme de gestion de patrimoine cross‑asset (Crypto, Bourse, Banque, Divers) avec IA et gestion unifiée des risques. Navigation simplifiée autour de 6 pages canoniques: Portfolio, Analytics, Risk, Rebalance, Execution, Settings.

## 🚀 Fonctionnalités Principales
- Rebalancing intelligent avec allocations dynamiques
- Decision Engine avec gouvernance (approbations AI/manuelles)
- ML avancé (LSTM, Transformers), signaux temps réel
- Analytics: Sharpe/Calmar, drawdown, VaR/CVaR
- Risk management: corrélations, stress testing, alertes
- 35+ dashboards, navigation unifiée, deep links
- Multi‑sources: CoinTracking CSV/API, données temps réel

## ⚡ Démarrage rapide
Prérequis: Python 3.10+, pip, virtualenv

1) Installer dépendances
```
python -m venv .venv
. .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env
```
2) Lancer l’API
```
uvicorn api.main:app --reload --port 8000
```
3) Ouvrir l’UI (pages statiques servies par FastAPI)
```
http://localhost:8000/static/dashboard.html
http://localhost:8000/static/risk-dashboard.html
http://localhost:8000/static/rebalance.html
http://localhost:8000/static/settings.html
```

Docs API: `http://localhost:8000/docs` • OpenAPI: `/openapi.json`

## 📖 Documentation
- Index docs: `docs/index.md`
- Quickstart: `docs/quickstart.md`
- Configuration: `docs/configuration.md`
- Navigation: `docs/navigation.md`
- Architecture: `docs/architecture.md`
- Governance: `docs/governance.md`
- Risk Dashboard: `docs/risk-dashboard.md`
- Télémétrie: `docs/telemetry.md`
- Runbooks: `docs/runbooks.md`
- Intégrations: `docs/integrations.md`
- Refactoring & migration: `docs/refactoring.md`

Changelog: `CHANGELOG.md`

## 🧭 Notes
- Les documents détaillés et historiques sont archivés sous `docs/_legacy/`.
- Les endpoints ML/Risk/Alerts ont été consolidés; voir `docs/refactoring.md` pour la migration.

