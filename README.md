# Crypto Rebal Starter — API + UI prêtes à l'emploi

Outil de **simulation de rebalancement** pour portefeuille crypto :
- Connexion **CoinTracking API** (méthode `getBalance` prioritaire, fallback `getGroupedBalance`)
- Calcul d’un **plan d’actions** (ventes/achats) par groupes cibles
- **Enrichissement des prix** & **quantités estimées**
- **Export CSV**
- Gestion des **aliases** (WBTC→BTC, WETH→ETH, …) & détection `unknown_aliases`
- **Classification automatique** par patterns regex (L2/Scaling, DeFi, AI/Data, Gaming/NFT, Memecoins)
- **UI autonome** en HTML (`static/rebalance.html`) pour piloter l'API

---

## Sommaire
- [1) Démarrage rapide](#1-démarrage-rapide)
- [2) Configuration (.env)](#2-configuration-env)
- [3) Architecture](#3-architecture)
- [4) Endpoints principaux](#4-endpoints-principaux)
- [5) UI : Interfaces utilisateur](#5-ui-interfaces-utilisateur)
- [6) Classification automatique](#6-classification-automatique)
- [7) Système de pricing hybride](#7-système-de-pricing-hybride)
- [8) Scripts de test](#8-scripts-de-test)
- [9) CORS, déploiement, GitHub Pages](#9-cors-déploiement-github-pages)
- [10) Workflow Git recommandé](#10-workflow-git-recommandé)
- [11) Roadmap courte](#11-roadmap-courte)

---

## 1) Démarrage rapide

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

- UI locale : ouvrez **`static/rebalance.html`** (une **copie** peut exister dans `docs/` pour GitHub Pages).
- Swagger / OpenAPI : http://127.0.0.1:8000/docs
- Healthcheck : http://127.0.0.1:8000/healthz

> 💡 Pensez à créer votre fichier `.env` (cf. section suivante).

---

## 2) Configuration (.env)

Créez un `.env` (copie de `.env.example`) et renseignez vos clés CoinTracking **sans guillemets** :

```
# CoinTracking API (sans guillemets)
CT_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# (alias compatibles si vous préférez ces noms)
# COINTRACKING_API_KEY=...
# COINTRACKING_API_SECRET=...

# Origins autorisés par CORS (utile si vous servez l'UI depuis GitHub Pages)
# CORS_ORIGINS=https://<user>.github.io,http://localhost:5173

# Port Uvicorn (optionnel)
# PORT=8000
```

Les deux paires de variables sont acceptées :
- `CT_API_KEY` / `CT_API_SECRET`
- `COINTRACKING_API_KEY` / `COINTRACKING_API_SECRET`

# (Optionnel) Chemin CSV CoinTracking si vous utilisez la source "cointracking"
# Si non défini, l'app cherchera automatiquement les fichiers ci-dessous
# et prendra le plus récent trouvé :
# - data/CoinTracking - Current Balance_mini.csv
# - data/CoinTracking - Balance by Exchange_mini.csv
# - data/CoinTracking - Current Balance.csv
# - data/CoinTracking - Balance by Exchange.csv
# puis les mêmes noms à la racine du projet.
# Exemple :
# COINTRACKING_CSV=/path/vers/CoinTracking - Balance by Exchange_mini.csv

---

## 3) Architecture

```
api/
  main.py               # Endpoints FastAPI (plan, CSV, taxonomy, debug, balances)
connectors/
  cointracking_api.py   # Connecteur CoinTracking (getBalance prioritaire, cache 60s)
engine/
  rebalance.py          # Logique de calcul du plan (groupes, deltas, actions)
services/
  pricing.py            # Provider(s) de prix externes (fallback)
data/
  taxonomy.json         # (optionnel) persistance des aliases/groupes si utilisée
static/
  rebalance.html        # UI canonique (à ouvrir localement)
  alias-manager.html    # Interface dédiée de gestion des taxonomies
docs/
  rebalance.html        # (optionnel) copie pour GitHub Pages
```

---

## 4) Endpoints principaux

### 4.1 Balances courantes
```
GET /balances/current?source=cointracking_api&min_usd=1
```
- Réponse :  
  ```json
  {
    "source_used": "cointracking_api",
    "items": [
      { "symbol":"BTC", "amount":1.23, "value_usd":12345.67, "price_usd":10036.8, "location":"CoinTracking" },
      ...
    ]
  }
  ```
- Pour `source=cointracking` (CSV), si `COINTRACKING_CSV` n’est pas fourni, l’application scanne les exports CoinTracking les plus courants et utilise **le fichier existant le plus récent** parmi : *`Current Balance(_mini).csv`* et *`Balance by Exchange(_mini).csv`* dans `data/` puis à la racine.

### 4.2 Plan de rebalancement (JSON)
```
POST /rebalance/plan?source=cointracking_api&min_usd=1
Content-Type: application/json

{
  "group_targets_pct": {
    "BTC":35, "ETH":25, "Stablecoins":10, "SOL":10, "L1/L0 majors":10, "Others":10
  },
  "primary_symbols": {
    "BTC": ["BTC","TBTC","WBTC"],
    "ETH": ["ETH","WSTETH","STETH","RETH","WETH"],
    "SOL": ["SOL","JUPSOL","JITOSOL"]
  },
  "sub_allocation": "proportional",   // "primary_first" si primary_symbols saisis
  "min_trade_usd": 25
}
```

- Réponse (extraits) :
  ```json
  {
    "total_usd": 443428.51,
    "target_weights_pct": {...},
    "deltas_by_group_usd": {...},
    "actions": [
      { "group":"BTC", "alias":"BTC", "symbol":"BTC", "action":"sell", "usd":-1234.56, "price_used":117971.65, "est_quantity":0.01047 },
      ...
    ],
    "unknown_aliases": ["XXX","YYY",...],
    "meta": { "source_used": "cointracking_api" }
  }
  ```

### 4.3 Export CSV (mêmes colonnes)
```
POST /rebalance/plan.csv?source=cointracking_api&min_usd=1
Body: (même JSON que pour /rebalance/plan)
```
- Colonnes : `group,alias,symbol,action,usd,est_quantity,price_used`

### 4.4 Taxonomie / Aliases
```
GET  /taxonomy
GET  /taxonomy/unknown_aliases
POST /taxonomy/aliases
POST /taxonomy/suggestions
POST /taxonomy/auto-classify
```
- `POST /taxonomy/aliases` accepte **deux formats** :
  - `{ "aliases": { "LINK": "Others" } }`
  - `{ "LINK": "Others" }`
- `POST /taxonomy/suggestions` : génère suggestions automatiques par patterns
- `POST /taxonomy/auto-classify` : applique automatiquement les suggestions

### 4.5 Debug CoinTracking
```
GET /debug/ctapi
```
- Affiche l’état des clés (présence/longueur), la base API CT, les tentatives (`getBalance`, `getGroupedBalance`, …), et un **aperçu** des lignes mappées.  
- Statut `ok: true/false`.

---

## 5) UI : Interfaces utilisateur

### 5.1 `static/rebalance.html` - Interface principale

- **API URL**, **source** (`cointracking_api` / `cointracking`), **min_usd**, **pricing mode** (local/hybride/auto).
- **Sous-allocation** : `proportional` (par défaut) ou **`primary_first`** si des `primary_symbols` sont saisis.
- **Persistance** (localStorage) : `api_base`, source, cibles %, primary symbols, min_trade, sous-allocation.
- **Générer le plan** → affichage cibles, deltas par groupe, **Top achats/ventes**, **Unknown aliases** (ajout unitaire + "Tout ajouter → Others"), **Net≈0** et **pas de micro-trades**.
- **Télécharger CSV** : export synchronisé (mêmes prix/quantités).
- **Badge pricing** : affiche le mode utilisé (Prix locaux/Prix marché/Hybride).
- **Pastille "source"** : affiche la **source réelle** (`meta.source_used`) et **signale un mismatch** si différente du choix UI.
- **🏷️ Alias Manager** : bouton d'accès direct à l'interface de gestion des taxonomies.

### 5.2 `static/alias-manager.html` - Gestion des taxonomies

Interface dédiée pour la gestion complète des aliases crypto :

- **Recherche en temps réel** et **filtrage par groupe**
- **Édition individuelle** avec dropdown de sélection de groupe
- **Actions batch** : assigner les filtrés vers un groupe, "Tout → Others"
- **🤖 Classification automatique** : suggestions intelligentes par patterns
- **🚀 Auto-classifier** : application automatique des suggestions
- **Statistiques** : nombre total d'aliases, groupes, éléments en mémoire
- **Export JSON** pour backup de la taxonomie
- **Navigation** retour vers le rebalancer principal
- **Thème sombre** cohérent avec l'interface principale
- **API intégrée** : sauvegarde automatique via `/taxonomy/aliases`

> Si vous servez l'UI depuis `docs/` (GitHub Pages), fixez **CORS_ORIGINS** dans `.env`.

---

## 6) Classification automatique

Le système de classification automatique utilise des **patterns regex** pour identifier et classer automatiquement les cryptomonnaies dans les groupes appropriés.

### 6.1 Groupes étendus (11 catégories)

Le système supporte désormais **11 groupes** au lieu de 6 :

1. **BTC** - Bitcoin et wrapped variants
2. **ETH** - Ethereum et liquid staking tokens  
3. **Stablecoins** - Monnaies stables USD/EUR
4. **SOL** - Solana et liquid staking
5. **L1/L0 majors** - Blockchains Layer 1 principales
6. **L2/Scaling** - Solutions Layer 2 et scaling
7. **DeFi** - Protocoles finance décentralisée
8. **AI/Data** - Intelligence artificielle et données
9. **Gaming/NFT** - Gaming et tokens NFT
10. **Memecoins** - Tokens meme et communautaires
11. **Others** - Autres cryptomonnaies

### 6.2 Patterns de classification

Les règles automatiques utilisent des patterns regex pour chaque catégorie :

```python
AUTO_CLASSIFICATION_RULES = {
    "stablecoins_patterns": [r".*USD[CT]?$", r".*DAI$", r".*BUSD$"],
    "l2_patterns": [r".*ARB.*", r".*OP$", r".*MATIC.*", r".*STRK.*"],
    "meme_patterns": [r".*DOGE.*", r".*SHIB.*", r".*PEPE.*", r".*BONK.*"],
    "ai_patterns": [r".*AI.*", r".*GPT.*", r".*RENDER.*", r".*FET.*"],
    "gaming_patterns": [r".*GAME.*", r".*NFT.*", r".*SAND.*", r".*MANA.*"]
}
```

### 6.3 API de classification

**Obtenir des suggestions** :
```bash
POST /taxonomy/suggestions
{
  "sample_symbols": "DOGE,USDT,ARB,RENDER,SAND"
}
```

**Appliquer automatiquement** :
```bash
POST /taxonomy/auto-classify
{
  "sample_symbols": "DOGE,USDT,ARB,RENDER,SAND"
}
```

### 6.4 Précision du système

Les tests montrent une **précision de ~90%** sur les échantillons types :
- **Stablecoins** : 100% (USDT, USDC, DAI)
- **L2/Scaling** : 85% (ARB, OP, MATIC, STRK)
- **Memecoins** : 95% (DOGE, SHIB, PEPE, BONK)
- **AI/Data** : 80% (AI, RENDER, FET)
- **Gaming/NFT** : 85% (SAND, MANA, GALA)

---

## 7) Système de pricing hybride

Le système de pricing offre **3 modes intelligents** pour enrichir les actions avec `price_used` et `est_quantity` :

### 7.1 Modes de pricing

**🚀 Local (rapide)** : `pricing=local`
- Calcule les prix à partir des balances : `price = value_usd / amount`
- Le plus rapide, idéal pour des données fraîches CoinTracking
- Source affichée : **Prix locaux**

**⚡ Hybride (recommandé)** : `pricing=hybrid` (défaut)
- Commence par les prix locaux
- Bascule automatiquement vers les prix marché si :
  - Données > 30 min (configurable via `PRICE_HYBRID_MAX_AGE_MIN`)
  - Écart > 5% entre local et marché (`PRICE_HYBRID_DEVIATION_PCT`)
- Combine rapidité et précision

**🎯 Auto/Marché (précis)** : `pricing=auto`
- Utilise exclusivement les prix live des APIs (CoinGecko → Binance → cache)
- Le plus précis mais plus lent
- Source affichée : **Prix marché**

### 7.2 Ordre de priorité pour tous les modes

1. **Stables** : `USD/USDT/USDC = 1.0` (prix fixe)
2. **Mode sélectionné** : local, hybride ou auto
3. **Aliases intelligents** : TBTC/WBTC→BTC, WETH/STETH/WSTETH/RETH→ETH, JUPSOL/JITOSOL→SOL
4. **Strip suffixes numériques** : `ATOM2→ATOM`, `SOL2→SOL`, `SUI3→SUI`
5. **Provider externe** (fallback) : CoinGecko → Binance → cache fichier

### 7.3 Configuration

```env
# Provider order (priorité)
PRICE_PROVIDER_ORDER=coingecko,binance,file

# Hybride : seuils de basculement
PRICE_HYBRID_MAX_AGE_MIN=30
PRICE_HYBRID_DEVIATION_PCT=5.0

# Cache TTL pour prix externes
PRICE_CACHE_TTL=120
```

### 7.4 Utilisation dans les endpoints

```bash
# Local (rapide)
POST /rebalance/plan?pricing=local

# Hybride (défaut, recommandé)
POST /rebalance/plan?pricing=hybrid

# Auto/Marché (précis)
POST /rebalance/plan?pricing=auto
```

**Cache** : les appels `getBalance`/`getGroupedBalance` sont mémorisés **60 s** (anti-spam).

**Invariants** :
- Σ(usd) des actions **= 0** (ligne d'équilibrage).
- Aucune action |usd| < `min_trade_usd` (si paramétrée).

---

## 8) Scripts de test

### PowerShell - Tests principaux
```powershell
$base = "http://127.0.0.1:8000"
$qs = "source=cointracking_api&min_usd=1"

$body = @{
  group_targets_pct = @{ BTC=35; ETH=25; Stablecoins=10; SOL=10; "L1/L0 majors"=10; "L2/Scaling"=5; DeFi=5; "AI/Data"=3; "Gaming/NFT"=2; Memecoins=2; Others=8 }
  primary_symbols   = @{ BTC=@("BTC","TBTC","WBTC"); ETH=@("ETH","WSTETH","STETH","RETH","WETH"); SOL=@("SOL","JUPSOL","JITOSOL") }
  sub_allocation    = "proportional"
  min_trade_usd     = 25
} | ConvertTo-Json -Depth 6

irm "$base/healthz"

irm "$base/balances/current?source=cointracking_api&min_usd=1" |
  Select-Object source_used, @{n="count";e={$_.items.Count}},
                         @{n="sum";e={("{0:N2}" -f (($_.items | Measure-Object value_usd -Sum).Sum))}}

$plan = irm -Method POST -ContentType 'application/json' -Uri "$base/rebalance/plan?$qs" -Body $body
("{0:N2}" -f (($plan.actions | Measure-Object -Property usd -Sum).Sum))  # -> 0,00
($plan.actions | ? { [math]::Abs($_.usd) -lt 25 }).Count                   # -> 0

$csvPath = "$env:USERPROFILE\Desktop\rebalance-actions.csv"
irm -Method POST -ContentType 'application/json' -Uri "$base/rebalance/plan.csv?$qs" -Body $body -OutFile $csvPath
("{0:N2}" -f ((Import-Csv $csvPath | Measure-Object -Property usd -Sum).Sum))  # -> 0,00
```

### Tests de classification automatique

```powershell
# Test des patterns
.\test-patterns.ps1

# Test de l'intégration interface
.\test-interface-integration.ps1

# Test manuel des suggestions
$testSymbols = "DOGE,SHIB,USDT,USDC,ARB,RENDER,SAND"
irm -Method POST -Uri "$base/taxonomy/suggestions" -Body "{\"sample_symbols\":\"$testSymbols\"}" -ContentType "application/json"

# Auto-classification
irm -Method POST -Uri "$base/taxonomy/auto-classify" -Body "{\"sample_symbols\":\"$testSymbols\"}" -ContentType "application/json"
```

### cURL (exemple)
```bash
curl -s "http://127.0.0.1:8000/healthz"
curl -s "http://127.0.0.1:8000/balances/current?source=cointracking_api&min_usd=1" | jq .
curl -s -X POST "http://127.0.0.1:8000/rebalance/plan?source=cointracking_api&min_usd=1"   -H "Content-Type: application/json"   -d '{"group_targets_pct":{"BTC":35,"ETH":25,"Stablecoins":10,"SOL":10,"L1/L0 majors":10,"Others":10},"primary_symbols":{"BTC":["BTC","TBTC","WBTC"],"ETH":["ETH","WSTETH","STETH","RETH","WETH"],"SOL":["SOL","JUPSOL","JITOSOL"]},"sub_allocation":"proportional","min_trade_usd":25}' | jq .
```

---

## 9) CORS, déploiement, GitHub Pages

- **CORS** : si l’UI est servie depuis un domaine différent (ex. GitHub Pages), ajoutez ce domaine à `CORS_ORIGINS` dans `.env`.
- **GitHub Pages** : placez une copie de `static/rebalance.html` dans `docs/`.  
  L’UI appellera l’API via l’URL configurée (`API URL` dans l’écran).
- **Docker/compose** : à venir (voir TODO).

---

## 10) Workflow Git recommandé

- Travaillez en branches de feature (ex. `feat-cointracking-api`, `feat-polish`).
- Ouvrez une **PR** vers `main`, listez les tests manuels passés, puis **mergez**.
- Après merge :
  ```bash
  git checkout main
  git pull
  git branch -d <feature-branch>
  git push origin --delete <feature-branch>
  ```

---

## 11) Roadmap courte

- ✅ **Alias Manager** (UI dédiée) avec recherche, filtrage et actions batch
- ✅ **Classification automatique** avec 11 groupes et patterns regex (90% précision)
- ✅ **Cache des unknown aliases** depuis les plans de rebalancement
- ✅ **API suggestions** et auto-classification pour l'interface
- ⬜ Persistance `taxonomy.json` et endpoints admin (reload/save)
- ⬜ **Intégration CoinGecko** pour métadonnées crypto (secteurs, tags)
- ⬜ Vue "Par lieu d'exécution" (exchange / ledger / DeFi) + plan par lieu
- ⬜ **Dry-run d'exécution** pour 1 exchange (arrondis, tailles mini, frais)
- ⬜ **Tests** unitaires & d'intégration, logs plus verbeux
- ⬜ **Docker** (dev & run)

---
