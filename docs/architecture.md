# Architecture - Cockpit Patrimoine Cross-Asset

## Vue d'ensemble

**Architecture modulaire cross-asset** intégrant Crypto, Bourse (Saxo), Banque et Divers avec hiérarchie décisionnelle unifiée.

### Composants principaux
- **FastAPI (`api/`)** : Endpoints API + montage répertoires `static/` et `data/`
- **Services (`services/`)** : Logique métier rebalancing, risk, pricing, execution, analytics
- **Connectors (`connectors/`)** : Intégrations CoinTracking, Saxo, exchanges
- **UI Consolidée (`static/`)** : 6 pages canoniques avec navigation unifiée

## Hiérarchie Décisionnelle

**SMART System** (quoi) → **Decision Engine** (combien/tempo) → **Execution** (comment)

### 1. SMART System - Intelligence Artificielle
- **Allocation Strategy** : Détermine "quoi" acheter/vendre par asset class
- **ML Signals** : Prédictions volatilité, régimes, corrélations
- **Market Analysis** : Classification bull/bear/neutral cross-asset

### 2. Decision Engine - Gouvernance
- **Quantification** : "Combien" allouer par module (crypto/bourse/banque/divers)
- **Timing** : "Quand" exécuter selon caps et contraintes
- **Risk Management** : VaR globale, corrélations, limites exposition

### 3. Execution Layer - Implémentation
- **Order Management** : Fragmentation, timing, venues
- **Cost Optimization** : Slippage, fees, market impact
- **Reconciliation** : Suivi exécution vs plan

## Architecture Multi-Utilisateurs (Multi-Tenant)

**Le système est multi-tenant** avec isolation complète des données par utilisateur.

### Structure Filesystem
Chaque utilisateur dispose d'un dossier isolé : `data/users/{user_id}/`
```
data/users/{user_id}/
  ├── cointracking/
  │   ├── uploads/       # CSV uploadés
  │   ├── imports/       # CSV validés
  │   └── snapshots/     # Snapshots actifs
  ├── saxobank/
  │   ├── uploads/
  │   ├── imports/
  │   └── snapshots/
  └── config.json        # Config utilisateur
```

### Clé Primaire Globale
**Toutes les données utilisent `(user_id, source)` comme clé primaire** :
- `user_id` : Identifiant utilisateur (demo, jack, donato, elda, roberto, clea)
- `source` : Type de données (cointracking, cointracking_api, saxobank, etc.)

### Isolation Sécurisée
- **Backend** : Classe `UserScopedFS` (`api/services/user_fs.py`) empêche path traversal
- **Frontend** : `localStorage.getItem('activeUser')` + user selector dans navigation
- **API** : Tous les endpoints acceptent paramètre `user_id`
- **Fichiers partagés** : Filtrage dynamique par (user_id, source)

Voir [CLAUDE.md Section 3](../CLAUDE.md) pour détails complets.

---

## Flux de Données Cross-Asset

**Schéma** : Sources → Normalisation → Signaux → Gouvernance → UI

### 1. Sources de Données
- **Crypto** : CoinTracking API/CSV + exchanges (Kraken, etc.)
- **Bourse** : Saxo CSV/XLSX + feeds de prix
- **Banque** : Import CSV manuel + conversion FX
- **Divers** : Valorisation périodique manuelle

### 2. Normalisation & Enrichissement
- **Unification devises** : Conversion EUR/USD/CHF temps réel
- **Taxonomie assets** : Classification cross-asset standardisée
- **Pricing consolidé** : Sources multiples avec fallbacks

### 3. Signaux & Intelligence - **Source ML Unifiée** ⭐
- **Source Centralisée** : `shared-ml-functions.js::getUnifiedMLStatus()` - Single source of truth
- **Logique Prioritaire** :
  1. **Governance Engine** (`/execution/governance/signals`) - Priority 1
  2. **ML Status API** (`/api/ml/status`) - Fallback
  3. **Stable Data** - Final fallback basé sur temps
- **ML Cross-Asset** : Corrélations, régimes, volatilité prédictive
- **Risk Attribution** : Contribution VaR par module/asset
- **Decision Signals** : Score composite SMART multi-module

### 4. Gouvernance Unifiée
- **Budget Risque Global** : Allocation VaR 4% across modules
- **Caps Dynamiques** : Limitation automatique selon volatilité
- **Hystérésis** : Anti-flapping VaR in/out (4%/3.5%)

### 5. UI Consolidée
- **WealthContextBar** : Filtrage household/module/ccy + **Badge Global ML** ⭐
- **6 Pages Canoniques** : Navigation simplifiée
- **Source ML Unifiée** : Toutes les pages utilisent `getUnifiedMLStatus()` ⭐
- **Badges Standards** : Format "Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N"
- **Timezone Uniforme** : Europe/Zurich pour tous les timestamps

## Data flow détaillé (Legacy)
- Ingestion balances: CoinTracking CSV (Balance by Exchange/Current Balance) ou API.
- Normalisation/aliases → groupes (BTC, ETH, Stablecoins, etc.).
- Pricing: local/fallback, estimation quantités.
- Planning: calcul des deltas vs cibles (targets manuels ou dynamiques CCS) → actions.
- Exécution: création des plans, adaptateurs exchanges, safety checks, statut live.
- Monitoring/Analytics: alertes, historique exécution, performance.

## Points techniques clés
- Mounts: `/static` et `/data` (voir `api/main.py`).
- Environnement: `.env` (CT_API_KEY/SECRET, CORS_ORIGINS, PORT, DEBUG/APP_DEBUG).
- Caching: CoinTracking API avec TTL 60s pour limiter la charge.
- Gestion erreurs: exceptions custom → JSON standardisé (voir `api/exceptions.py`).
- Taxonomy: persistance d’aliases merge mémoire/disque.
- Security: middleware gzip, CORS, trusted hosts; safety validator côté exécution.

Pour plus de détails, l’archive `docs/_legacy/` contient les schémas exhaustifs.

### Selectors centralisés (governance UI)

Le front consolide l’accès au cap via `static/selectors/governance.js`:
- `selectCapPercent(state)` – source unique pour cap en % (policy prioritaire).
- `selectPolicyCapPercent(state)` et `selectEngineCapPercent(state)` – détails pour affichage/diagnostic.
Ces helpers normalisent 0–1 et 0–100, et évitent les divergences multi-sources.
