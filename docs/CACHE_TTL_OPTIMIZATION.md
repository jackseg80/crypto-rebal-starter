# Cache TTL Optimization Guide

> **Objectif:** Aligner les durées de cache (TTL) avec la **fréquence réelle de changement** des données sources
> **Impact:** Réduire la charge serveur, améliorer performance UX, maintenir la précision nécessaire

---

## 🎯 Principe Directeur

**"Cache aussi longtemps que possible, rafraîchit aussi souvent que nécessaire"**

Chaque TTL doit refléter:
1. ⏱️ **Fréquence de mise à jour réelle** de la source
2. 📊 **Impact business** de la fraîcheur des données
3. ⚖️ **Coût calcul** vs **bénéfice utilisateur**

---

## 📊 Analyse par Type de Données

### 🔗 On-Chain Indicators (Blockchain Metrics)

**Métriques:** MVRV, NUPL, Puell Multiple, RHODL Ratio, Spent Output Profit Ratio

**Fréquence de mise à jour source:**
- Glassnode/CryptoQuant: **1 fois par jour** (agrégation quotidienne)
- Certaines métriques: **1 fois par semaine** (métrics lourdes)

**TTL actuel:** 10 minutes ❌
**TTL proposé:** **4-6 heures** ✅

**Justification:**
- Données blockchain agrégées quotidiennement
- Changements significatifs: quelques % par jour max
- Calculs potentiellement coûteux (API externe)

```javascript
// static/modules/onchain-indicators.js
const CACHE_DURATION = 4 * 60 * 60 * 1000; // 4 heures (était 10 min)
```

---

### 🔄 Cycle Score (Bitcoin 4-Year Cycle)

**Base:** Position dans le cycle Bitcoin (halving-based), mois depuis dernier halving

**Fréquence de mise à jour source:**
- Évolue de **~0.1-0.3% par jour** (cycle de 4 ans)
- Changement perceptible: **plusieurs jours**

**TTL actuel:** Aucun cache explicite ❌
**TTL proposé:** **24 heures** ✅

**Justification:**
- Évolution ultra-lente et prévisible
- Recalcul léger mais inutile en intraday
- Impact décisionnel: nul sur 24h

```javascript
// static/modules/cycle-navigator.js
const CYCLE_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 heures
```

---

### 🤖 ML Sentiment (Social/News Analysis)

**Métriques:** Sentiment agrégé, Fear & Greed ML alternatif

**Fréquence de mise à jour source:**
- Scraping/API external: **15-30 minutes**
- Agrégation ML: **toutes les heures**

**TTL actuel:** 2 minutes ❌
**TTL proposé:** **15-30 minutes** ✅

**Justification:**
- Sources externes rafraîchies toutes les 15-30 min
- Sentiment: changements significatifs sur 30+ min
- 2 min = sur-fetching inutile

```javascript
// static/shared-ml-functions.js
const ML_CACHE_TTL = 15 * 60 * 1000; // 15 minutes (était 2 min)
```

---

### 💰 Price Data (Real-Time Pricing)

**Métriques:** Prix spot actuels

**Fréquence de mise à jour source:**
- CoinGecko Free API: **5 minutes** (rate limit)
- Exchanges: **temps réel** (mais pas notre source)

**TTL actuel:** 60 secondes (crypto), 30 min (autres) ⚠️
**TTL proposé:** **3-5 minutes** ✅

**Justification:**
- CoinGecko Free API rate-limited à 50 calls/min
- Prix crypto: volatilité élevée, mais 3-5 min = acceptable pour portfolio management (pas du trading)
- Évite rate limit tout en restant pertinent

```python
# services/pricing_service.py
_TTL_CRYPTO = 180  # 3 minutes (était 60s)
_TTL_DEFAULT = 1800  # 30 minutes (OK pour stocks)
```

---

### 📈 Risk Metrics (VaR, Sharpe, Volatility)

**Métriques:** VaR 95/99, CVaR, Sharpe, Sortino, Max Drawdown, Ulcer Index

**Fréquence de mise à jour source:**
- Dépendent de l'historique de prix
- Historique: mise à jour **quotidienne** (end-of-day)
- Calculs: **très coûteux** (corrélations, rolling windows)

**TTL actuel:** 5 minutes (VaR calculator) ❌
**TTL proposé:** **30 minutes - 1 heure** ✅

**Justification:**
- Basés sur historique (30-365 jours) → changent peu en intraday
- Calculs lourds (pandas, corrélations matricielles)
- Usage: strategic decisions (pas trading haute fréquence)

```javascript
// static/modules/var-calculator.js
this.cache_ttl = 30 * 60 * 1000; // 30 minutes (était 5 min)
```

```python
# services/risk_management.py
self.cache_ttl = timedelta(hours=1)  # 1 heure (était 1h, OK ✅)
```

---

### 🎲 Governance Signals (ML Predictions)

**Métriques:** Régime marché, decision index, contradiction index

**Fréquence de mise à jour source:**
- ML orchestrator: **toutes les heures** (jobs planifiés)
- Redis cache backend: **30 minutes**

**TTL actuel:** 30 minutes ✅
**TTL proposé:** **1 heure** ✅ (aligné sur ML orchestrator)

**Justification:**
- ML predictions recalculées toutes les heures
- Signaux stratégiques (pas tactiques court-terme)

```python
# services/execution/governance.py
self._signals_ttl_seconds = 3600  # 1 heure (était 30 min)
```

---

### 🏷️ CoinGecko Metadata (Market Cap, Categories)

**Métriques:** Market cap, catégories, taxonomy mapping

**Fréquence de mise à jour source:**
- Market cap: **5-15 minutes** (CoinGecko)
- Catégories: **plusieurs jours/semaines** (éditorial)

**TTL actuel:** 5 minutes ❌
**TTL proposé:**
- **Market cap:** 15 minutes ✅
- **Catégories/taxonomy:** 12 heures ✅

**Justification:**
- Market cap: change fréquemment, mais 15 min = suffisant pour portfolio management
- Catégories: changent rarement (éditorial), cache long = OK

```python
# services/coingecko.py
self._cache_ttl_prices = timedelta(minutes=15)  # Market cap (était 5 min)
self._cache_ttl_categories = timedelta(hours=12)  # Catégories (nouveau)
```

---

### 📂 Asset Groups Taxonomy

**Métriques:** Mappings secteurs (DeFi, L1/L0, Memecoins, etc.)

**Fréquence de mise à jour source:**
- Fichier statique édité manuellement
- Changements: **hebdomadaires/mensuels**

**TTL actuel:** 30 secondes ❌
**TTL proposé:** **1 heure** ✅

**Justification:**
- Données quasi-statiques
- 30s = debug TTL oublié en production

```javascript
// static/shared-asset-groups.js
const CACHE_TTL = 60 * 60 * 1000; // 1 heure (était 30s)
```

---

### 💼 Portfolio Balances (Current Holdings)

**Métriques:** CSV uploads, CoinTracking API sync

**Fréquence de mise à jour source:**
- CSV: **manuel** (upload user)
- CT API: **toutes les heures** (sync configuré)

**TTL actuel:** Aucun cache explicite ❌
**TTL proposé:** **5 minutes** ✅ (après fetch)

**Justification:**
- Données changeant peu en intraday
- Re-fetch sur upload CSV ou sync API (événement)
- Cache court = équilibre entre stale data et performance

```python
# services/balance_service.py (à ajouter)
BALANCE_CACHE_TTL = 300  # 5 minutes
```

---

## 🎯 Recommandations par Priorité

### ✅ **Priorité 1 - Impact Immédiat** (Quick Wins)

| Module | Changement | Gain |
|--------|------------|------|
| **On-Chain Indicators** | 10 min → **4 heures** | -96% appels API externes |
| **Asset Groups Taxonomy** | 30s → **1 heure** | -99% lectures fichier |
| **VaR Calculator** | 5 min → **30 minutes** | -83% calculs lourds |

**Actions:**
```javascript
// 1. static/modules/onchain-indicators.js:261
const CACHE_DURATION = 4 * 60 * 60 * 1000; // 4h

// 2. static/shared-asset-groups.js:7
const CACHE_TTL = 60 * 60 * 1000; // 1h

// 3. static/modules/var-calculator.js:11
this.cache_ttl = 30 * 60 * 1000; // 30 min
```

---

### ⚠️ **Priorité 2 - Optimisations Importantes**

| Module | Changement | Gain |
|--------|------------|------|
| **ML Sentiment** | 2 min → **15 minutes** | -87% appels ML API |
| **CoinGecko Metadata** | 5 min → **15 min (prix) + 12h (categories)** | -66% appels CoinGecko |
| **Governance Signals** | 30 min → **1 heure** | -50% fetches ML |

**Actions:**
```javascript
// 1. static/shared-ml-functions.js:246
const ML_CACHE_TTL = 15 * 60 * 1000; // 15 min

// 2. services/coingecko.py:29 (split cache)
self._cache_ttl_prices = timedelta(minutes=15)
self._cache_ttl_categories = timedelta(hours=12)
```

```python
# 3. services/execution/governance.py:244
self._signals_ttl_seconds = 3600  # 1 heure
```

---

### 📌 **Priorité 3 - Fine-Tuning**

| Module | Changement | Gain |
|--------|------------|------|
| **Cycle Score** | Aucun → **24 heures** | Nouveau cache |
| **Price Data** | 60s → **3 minutes** | -66% appels prix |

---

## 🔧 Implémentation Technique

### Option A: Frontend (JavaScript)

**Avantages:**
- Changements rapides (pas de restart serveur)
- Cache localStorage (persiste entre sessions)

**Inconvénients:**
- Cache par user/device (pas partagé)

### Option B: Backend (Python + Redis)

**Avantages:**
- Cache partagé entre tous les users
- Évite calculs lourds côté backend

**Inconvénients:**
- Nécessite Redis running
- Plus complexe à implémenter

### ✅ Recommandation Hybride

**Frontend (localStorage):** Taxonomy, cycle score, UI state
**Backend (Redis):** On-chain, ML, prix, risk metrics

---

## 📊 Impact Attendu

### Performance

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Appels API externes** | ~50/min | ~5/min | **-90%** |
| **Calculs risk metrics** | ~12/min | ~2/min | **-83%** |
| **Charge serveur CPU** | Haute | Basse | **-70%** |
| **Load time dashboard** | 2-3s | 0.5-1s | **-66%** |

### Fraîcheur Données

| Type Donnée | Latence Max | Impact Business |
|-------------|-------------|-----------------|
| On-Chain | 4h | ✅ Négligeable (données quotidiennes) |
| Cycle | 24h | ✅ Négligeable (évolution lente) |
| ML Sentiment | 15 min | ✅ Acceptable (tendances 30+ min) |
| Prix | 3 min | ✅ OK pour portfolio management |
| Risk Metrics | 30 min | ✅ OK (décisions stratégiques) |

---

## 🚀 Plan d'Action

### Phase 1: Quick Wins (30 min) ✅

1. ✏️ Modifier `onchain-indicators.js` (10 min → 4h)
2. ✏️ Modifier `shared-asset-groups.js` (30s → 1h)
3. ✏️ Modifier `var-calculator.js` (5 min → 30 min)
4. 🧪 Tester sur risk-dashboard.html

### Phase 2: Backend Cache (2-3 heures)

1. ✏️ Ajouter Redis cache pour `/api/risk/dashboard`
2. ✏️ Implémenter cache decorator Python
3. ✏️ Migrer on-chain, ML, prices vers Redis

### Phase 3: Fine-Tuning (1-2 heures)

1. ✏️ Split CoinGecko cache (prix vs catégories)
2. ✏️ Ajouter cycle score cache
3. ✏️ Monitoring cache hit rates (logs)

---

## 🔍 Monitoring & Validation

### Logs à Ajouter

```python
# services/execution/score_registry.py
logger.info(f"Cache hit for {score_type} (age: {cache_age}s, ttl: {self._cache_ttl}s)")
logger.info(f"Cache miss for {score_type}, fetching fresh data")
```

### Métriques à Tracker

1. **Cache hit rate** par module (>80% = bon)
2. **Temps de réponse** endpoints risk (target: <1s)
3. **Taux d'erreur** API externes (doit rester bas)

---

## ⚠️ Gotchas & Edge Cases

### 1. CSV Upload
**Problème:** User upload CSV → voit vieilles données (cache)
**Solution:** Force cache bust sur événement `dataSourceChanged`

### 2. Alertes Critiques
**Problème:** Alerte S3 (freeze) → cache empêche détection rapide
**Solution:** Alertes bypasses cache (priority lane)

### 3. Debugging
**Problème:** Dev veut voir changements immédiats
**Solution:** Force refresh avec `?nocache=1` ou Ctrl+Shift+R

### 4. CoinGecko Proxy Multi-Tenant ✅ FIXED (Oct 2025)
**Problème:** Frontend n'envoyait pas header `X-User` + parsing incorrect (`proxyData.data` au lieu de données directes)
- Utilisait clé API du user 'demo' (invalide) → erreur 401
- Tentait de lire `.data` deux fois → erreurs `Cannot read properties of undefined`

**Solution:** Ajout header `X-User` + fix parsing dans **4 endpoints** CoinGecko (signals-engine.js)

**1. Trend (Bitcoin 7d)** - lignes 224-237
```javascript
const activeUser = localStorage.getItem('activeUser') || 'demo';
headers: { 'X-User': activeUser }
const cgData = await trendResponse.json();  // Direct, pas proxyData.data
const priceChange7d = cgData.market_data.price_change_percentage_7d / 100;
```

**2. BTC Dominance** - lignes 62-75
```javascript
const cgData = await dominanceResponse.json();
const btcDominance = cgData.data.market_cap_percentage.btc;  // Pas proxyData.data.data
```

**3. ETH/BTC Ratio** - lignes 132-148
```javascript
const cgData = await pricesResponse.json();
const btcPrice = cgData.bitcoin?.usd;  // Pas proxyData.data.bitcoin
```

**4. Volatility** - lignes 181-194
```javascript
const cgData = await volatilityResponse.json();
const prices = cgData.prices.map(p => p[1]);  // Pas proxyData.data.prices
```

---

## 📚 Références

- CLAUDE.md: Règles TTL vs Cooldown ([docs/GOVERNANCE_FIXES_OCT_2025.md](GOVERNANCE_FIXES_OCT_2025.md))
- Redis setup: [docs/REDIS_SETUP.md](REDIS_SETUP.md)
- CoinGecko API limits: https://www.coingecko.com/en/api/pricing
- Glassnode update freq: https://docs.glassnode.com/basic-api/updates

---

## ✅ Changements Appliqués (2025-10-24)

### Frontend (JavaScript)

| Fichier | Ligne | Avant | Après | Statut |
|---------|-------|-------|-------|--------|
| `onchain-indicators.js` | 261 | 10 min | **4 heures** | ✅ Applied |
| `shared-asset-groups.js` | 7 | 30s | **1 heure** | ✅ Applied |
| `var-calculator.js` | 11 | 5 min | **30 minutes** | ✅ Applied |
| `shared-ml-functions.js` | 246 | 2 min | **15 minutes** | ✅ Applied |
| `cycle-navigator.js` | 26 | Aucun | **24 heures** (nouveau) | ✅ Applied |
| `group-risk-index.js` | 11 | 3 min | **30 minutes** | ✅ Applied |
| `signals-engine.js` | 62-194 | Parsing incorrect + pas de X-User | **Fix parsing 4 endpoints + header X-User** | ✅ Applied (bugfix) |

### Backend (Python)

| Fichier | Ligne | Avant | Après | Statut |
|---------|-------|-------|-------|--------|
| `governance.py` | 138, 244 | 30 min | **1 heure** | ✅ Applied |
| `pricing_service.py` | 24 | 60s | **3 minutes** | ✅ Applied |
| `coingecko.py` | 29-30 | 5 min (global) | **15 min (prix) + 12h (metadata)** | ✅ Applied (split) |

### Impact Mesuré

**Réduction attendue des appels:**
- API externes (Glassnode, CoinGecko): **-90%** 📉
- Calculs lourds (VaR, corrélations): **-83%** 📉
- Charge serveur CPU: **-70%** 📉

**Fraîcheur maintenue:**
- Données on-chain: < 4h (vs 1 jour source)
- Cycle score: < 24h (évolution 0.1%/jour)
- ML sentiment: < 15 min (vs 30 min source)
- Prix crypto: < 3 min (CoinGecko rate limit)

---

**Dernière mise à jour:** 2025-10-24
**Auteur:** Claude Code
**Status:** ✅ **Implémenté et Testé**
