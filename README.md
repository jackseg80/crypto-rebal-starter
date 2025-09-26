# Crypto Rebal Starter — Cockpit Patrimoine Modulaire

Plateforme de gestion de patrimoine cross‑asset (Crypto, Bourse, Banque, Divers) avec IA et gestion unifiée des risques. Navigation simplifiée autour de 6 pages canoniques: Portfolio, Analytics, Risk, Rebalance, Execution, Settings.

## Fonctionnalités Principales
- **Rebalancing intelligent** avec allocations dynamiques basées sur le contexte réel (cycle, régime, concentration wallet)
- **Simulateur Pipeline Complet** (static/simulations.html) : test en temps réel du pipeline complet Decision Inputs → Risk Budget → Targets → Phase Tilts → Governance → Execution avec 10 presets de scénarios
- **Decision Engine** avec gouvernance (approbations AI/manuelles)
- **Phase Engine** : détection proactive de phases market avec tilts automatiques (ETH expansion, altseason, risk-off)
- **ML avancé** (LSTM, Transformers), signaux temps réel
- **Analytics**: Sharpe/Calmar, drawdown, VaR/CVaR
- **Risk management v2**: corrélations, stress testing, alertes, circuit breakers, GRI (Group Risk Index)
- **Strategy API v3**: calculs dynamiques remplaçant les presets hardcodés
- **Classification unifiée** des assets via taxonomy_aliases.json (source unique de vérité)
- **Synchronisation parfaite** Analytics ↔ Rebalance via u.targets_by_group
- **35+ dashboards**, navigation unifiée, deep links
- **Multi‑sources**: CoinTracking CSV/API, données temps réel
- **Système multi-utilisateurs** avec isolation complète des données
- **🔄 Système de Contradiction Unifié**: Source unique, poids adaptatifs, caps risque, classification auto (Low/Medium/High)

## 🔄 Système de Contradiction Unifié

Le système centralise la gestion des signaux contradictoires avec:

- **Source unique**: `governance.contradiction_index` (0-1 normalisé)
- **Poids adaptatifs**: Renormalisation automatique (-35%/-15%/+50% baseline)
- **Caps de risque**: Réduction memecoins (15%→5%) et small_caps (25%→12%)
- **Classification**: Low/Medium/High avec recommandations contextuelles
- **Page test**: `/static/test-contradiction-unified.html`
- **Documentation**: `docs/contradiction-system.md`

**Architecture**: Sélecteurs centralisés, politique unifiée, validation automatique, intégration badges/simulateur.

## Démarrage rapide
Prérequis: Python 3.10+, pip, virtualenv

1) Installer dépendances

Linux/macOS:
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

Windows (PowerShell):
```
py -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
copy env.example .env
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

Dashboards principaux:
```
http://localhost:8000/static/dashboard.html        # Portfolio overview
http://localhost:8000/static/analytics-unified.html # Analytics unifiés + lien vers simulateur
http://localhost:8000/static/risk-dashboard.html   # Risk management
http://localhost:8000/static/rebalance.html        # Rebalancing
http://localhost:8000/static/simulations.html      # Simulateur Pipeline (NOUVEAU)
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

### 🔧 Production Stabilization (NOUVEAU)
- **Hystérésis & EMA Anti-Flickering** : Deadband ±2%, persistence 3 ticks pour prévenir les oscillations
- **Staleness Gating** : Freeze des poids adaptatifs mais préservation des caps défensifs (>30min)
- **Token Bucket Rate Limiting** : 6 req/s avec burst 12, TTL adaptatif (10s-300s)
- **Suite Tests Complète** : 16 scénarios de validation avec tests temps réel

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

### Mode Priority Rebalancing
- **Allocation intelligente** : Choix automatique des meilleurs assets dans chaque groupe
- **Support univers limité** : Fallback gracieux vers mode proportionnel si données limitées
- **Gestion des locations** : Attribution automatique des vraies exchanges (Kraken, Binance, etc.) depuis les données CSV
- **Interface unifiée** : Toggle simple dans l'interface de rebalancing pour basculer entre modes proportionnel et priority

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

## Simulateur Pipeline Complet

**URL**: `http://localhost:8000/static/simulations.html`

Le simulateur permet de tester en temps réel le pipeline complet sans impact sur les données :
```
Decision Inputs → Risk Budget → Targets → Phase Tilts → Governance → Execution
```

**Fonctionnalités** :
- **10 presets** : Fin Bull Run, Capitulation, ETH Expansion, Altseason, etc.
- **Contrôles temps réel** : scores, confidences, hystérésis, circuit breakers, caps
- **Position réelle** : utilise le portefeuille source réel pour calculer les deltas
- **Phase Engine unifié** : tilts identiques à la production
- **Market overlays** : volatilité Z-score, drawdown 90j, breadth pour circuit breakers
- **Reproductibilité** : état déterministe, plus de hasard
- **URL hash** : état partageable via URL
- **Mode Live/Simulation** : comparaison avec données réelles

**Architecture technique** :

**Alignement Cap d'exécution** :
- La policy active ctive_policy.cap_daily (fraction 0–1) est injectée dans le simulateur.
- planOrdersSimulated() clampe chaque delta à ±cap (en points de %), puis applique les seuils bucket/global et le min trade.
- L'UI expose esult.ui.capPercent et esult.ui.capPct01 pour l'affichage cohérent.


- Engine principal : `static/modules/simulation-engine.js`
- Contrôles UI : `static/components/SimControls.js`
- Inspecteur : `static/components/SimInspector.js`
- Presets : `static/presets/sim_presets.json`

## Notes
- Les documents détaillés et historiques sont archivés sous `docs/_legacy/`.
- Les endpoints ML/Risk/Alerts ont été consolidés; voir `docs/refactoring.md` pour la migration.
- Classification des assets: `data/taxonomy_aliases.json` est la source unique de vérité pour tous les groupes d'assets. Les dashboards utilisent automatiquement cette classification via l'API `/taxonomy` et le module `static/shared-asset-groups.js`.

### Governance UI (Cap d’exécution)

- Source de vérité frontend: `GET /execution/governance/state.active_policy.cap_daily`.
- Utiliser `selectCapPercent(state)` du module `static/selectors/governance.js` pour tout affichage/calcul en %.
- Si la policy est absente, fallback sur engine cap (affiché en second comme “SMART {x}%”).
- Convergence: `ceil(maxDelta / (capPct/100))`. Exemple: maxΔ=23 pts, cap=1% → 23 itérations; cap=10% → 3.
- Badge serré: afficher “🧊 Freeze/Cap serré (±X%)” pour Freeze ou cap ≤ 2%.


