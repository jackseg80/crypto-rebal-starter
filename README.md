# Crypto Rebal Starter — Cockpit Patrimoine Modulaire

Plateforme de gestion de patrimoine cross‑asset (Crypto, Bourse, Banque, Divers) avec IA et gestion unifiée des risques. Navigation simplifiée autour de 6 pages canoniques: Portfolio, Analytics, Risk, Rebalance, Execution, Settings.

## Fonctionnalités Principales
- **Rebalancing intelligent** avec allocations dynamiques basées sur le contexte réel (cycle, régime, concentration wallet)
- **Decision Engine** avec gouvernance (approbations AI/manuelles)
- **ML avancé** (LSTM, Transformers), signaux temps réel
- **Analytics**: Sharpe/Calmar, drawdown, VaR/CVaR
- **Risk management v2**: corrélations, stress testing, alertes, GRI (Group Risk Index)
- **Strategy API v3**: calculs dynamiques remplaçant les presets hardcodés
- **Classification unifiée** des assets via taxonomy_aliases.json (source unique de vérité)
- **Synchronisation parfaite** Analytics ↔ Rebalance via u.targets_by_group
- **35+ dashboards**, navigation unifiée, deep links
- **Multi‑sources**: CoinTracking CSV/API, données temps réel
- **Système multi-utilisateurs** avec isolation complète des données

## Démarrage rapide
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
3) Ouvrir l’UI (servie par FastAPI)
```
http://localhost:8000/static/settings.html
```
Dans Settings:
- **Sélectionner un utilisateur** (demo, jack, donato, elda, roberto, clea) dans la barre de navigation
- Choisir la source de données (fichiers CSV de l'utilisateur, CoinTracking API si configuré)
- (Optionnel) Configurer les clés API par utilisateur (CoinGecko, CoinTracking, FRED)
- Tester: « 🧪 Tester les APIs » et « 🧪 Tester la Source »

Dashboards:
```
http://localhost:8000/static/dashboard.html
http://localhost:8000/static/risk-dashboard.html
http://localhost:8000/static/rebalance.html
```

Docs API: `http://localhost:8000/docs` • OpenAPI: `/openapi.json`

## Système Multi-Utilisateurs

La plateforme supporte 6 utilisateurs avec isolation complète des données:

### Utilisateurs Configurés
- **demo** : Utilisateur de démonstration avec données d'exemple
- **jack, donato, elda, roberto, clea** : Utilisateurs individuels avec configurations isolées

### Fonctionnalités
- **Sélecteur utilisateur** : dans la barre de navigation (indépendant du menu Admin)
- **Isolation des données** : chaque utilisateur a ses propres :
  - Fichiers CSV dans `data/users/{user}/csv/`
  - Configuration dans `data/users/{user}/config.json`
  - Clés API CoinTracking individuelles
- **Sources dynamiques** : l'interface affiche automatiquement :
  - Les fichiers CSV réels de l'utilisateur
  - L'option API CoinTracking seulement si des clés sont configurées
- **Settings par utilisateur** : sauvegardés côté serveur avec rechargement automatique

### Endpoints Multi-Utilisateurs
```
GET  /api/users/sources     # Sources disponibles pour l'utilisateur
GET  /api/users/settings    # Configuration utilisateur
PUT  /api/users/settings    # Sauvegarde configuration utilisateur
```

## 🚀 Nouvelles Fonctionnalités (v3.0)

### Système d'Allocation Dynamique
- **Élimination des presets hardcodés** : Plus de templates figés (BTC 40%, ETH 30%, etc.)
- **Calculs contextuels** : Allocations basées sur cycle de marché, régime, concentration wallet
- **Source canonique unique** : `u.targets_by_group` remplace les presets dispersés
- **Synchronisation parfaite** : Analytics ↔ Rebalance automatiquement cohérents

### Implémentation Technique
```javascript
// Ancien système (éliminé)
if (blended >= 70) {
  stablesTarget = 20; btcTarget = 35; // Preset figé
}

// Nouveau système (dynamique)
function computeMacroTargetsDynamic(ctx, rb, walletStats) {
  const stables = rb.target_stables_pct;  // Source de vérité risk budget
  const riskyPool = 100 - stables;
  // Modulateurs intelligents selon contexte...
}
```

### Bénéfices Utilisateur
- **Cohérence garantie** : Plus jamais de "Others 31%" incohérent
- **Adaptabilité** : Objectifs s'ajustent automatiquement au profil réel
- **Transparence** : Une seule source de données entre toutes les pages
- **Performance** : Allocations optimisées selon concentration du wallet

## Documentation
- Guide agent: `CLAUDE.md`
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

Endpoints utiles:
```
GET  /healthz
GET  /balances/current?source=cointracking       # CSV
GET  /balances/current?source=cointracking_api   # API CT
GET  /debug/ctapi                                # Sonde CoinTracking API
```

Changelog: `CHANGELOG.md`

## Notes
- Les documents détaillés et historiques sont archivés sous `docs/_legacy/`.
- Les endpoints ML/Risk/Alerts ont été consolidés; voir `docs/refactoring.md` pour la migration.
- Classification des assets: `data/taxonomy_aliases.json` est la source unique de vérité pour tous les groupes d'assets. Les dashboards utilisent automatiquement cette classification via l'API `/taxonomy` et le module `static/shared-asset-groups.js`.
