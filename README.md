# Crypto Rebal Starter — API + UI prêtes à l'emploi

Outil de **simulation de rebalancement** pour portefeuille crypto :
- Connexion **CoinTracking API** (méthode `getBalance` prioritaire, fallback `getGroupedBalance`)
- Calcul d’un **plan d’actions** (ventes/achats) par groupes cibles
- **Enrichissement des prix** & **quantités estimées**
- **Export CSV**
- Gestion des **aliases** (WBTC→BTC, WETH→ETH, …) & détection `unknown_aliases`
- **UI autonome** en HTML (`static/rebalance.html`) pour piloter l’API

---

## Sommaire
- [1) Démarrage rapide](#1-démarrage-rapide)
- [2) Configuration (.env)](#2-configuration-env)
- [3) Architecture](#3-architecture)
- [4) Endpoints principaux](#4-endpoints-principaux)
- [5) UI : static/rebalance.html](#5-ui-staticrebalancehtml)
- [6) Notes techniques de pricing](#6-notes-techniques-de-pricing)
- [7) Scripts de test](#7-scripts-de-test)
- [8) CORS, déploiement, GitHub Pages](#8-cors-déploiement-github-pages)
- [9) Workflow Git recommandé](#9-workflow-git-recommandé)
- [10) Roadmap courte](#10-roadmap-courte)

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
- `source_used` confirme la **source réellement utilisée** (utile si un fallback se produit).

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
```
- `POST /taxonomy/aliases` accepte **deux formats** :
  - `{ "aliases": { "LINK": "Others" } }`
  - `{ "LINK": "Others" }`

### 4.5 Debug CoinTracking
```
GET /debug/ctapi
```
- Affiche l’état des clés (présence/longueur), la base API CT, les tentatives (`getBalance`, `getGroupedBalance`, …), et un **aperçu** des lignes mappées.  
- Statut `ok: true/false`.

---

## 5) UI : `static/rebalance.html`

- **API URL**, **source** (`cointracking_api` / `cointracking`), **min_usd**, **min_trade_usd**.
- **Sous-allocation** : `proportional` (par défaut) ou **`primary_first`** si des `primary_symbols` sont saisis.
- **Persistance** (localStorage) : `api_base`, source, cibles %, primary symbols, min_trade, sous-allocation.
- **Générer le plan** → affichage cibles, deltas par groupe, **Top achats/ventes**, **Unknown aliases** (ajout unitaire + “Tout ajouter → Others”), **Net≈0** et **pas de micro-trades**.
- **Télécharger CSV** : export synchronisé (mêmes prix/quantités).
- **Pastille “source”** : affiche la **source réelle** (`meta.source_used`) et **signale un mismatch** si différente du choix UI.

> Si vous servez l’UI depuis `docs/` (GitHub Pages), fixez **CORS_ORIGINS** dans `.env`.

---

## 6) Notes techniques de pricing

Ordre de priorité pour `price_used` & `est_quantity` :
1. **Stables** : `USD/USDT/USDC = 1.0`.
2. **Prix CoinTracking** : `price_fiat` s’il est fourni, sinon **`value_fiat / amount`**.
3. **Aliases** : TBTC/WBTC→BTC, WETH/STETH/WSTETH/RETH→ETH, JUPSOL/JITOSOL→SOL.
4. **Strip suffixes numériques** : `ATOM2→ATOM`, `SOL2→SOL`, `SUI3→SUI`, etc.
5. **Provider externe** (dans `services/pricing.py`) en **fallback** uniquement.

**Cache** : les appels `getBalance`/`getGroupedBalance` sont mémorisés **60 s** (anti-spam).

**Invariants** :
- Σ(usd) des actions **= 0** (ligne d’équilibrage).
- Aucune action |usd| < `min_trade_usd` (si paramétrée).

---

## 7) Scripts de test

### PowerShell
```powershell
$base = "http://127.0.0.1:8000"
$qs = "source=cointracking_api&min_usd=1"

$body = @{
  group_targets_pct = @{ BTC=35; ETH=25; Stablecoins=10; SOL=10; "L1/L0 majors"=10; Others=10 }
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

### cURL (exemple)
```bash
curl -s "http://127.0.0.1:8000/healthz"
curl -s "http://127.0.0.1:8000/balances/current?source=cointracking_api&min_usd=1" | jq .
curl -s -X POST "http://127.0.0.1:8000/rebalance/plan?source=cointracking_api&min_usd=1"   -H "Content-Type: application/json"   -d '{"group_targets_pct":{"BTC":35,"ETH":25,"Stablecoins":10,"SOL":10,"L1/L0 majors":10,"Others":10},"primary_symbols":{"BTC":["BTC","TBTC","WBTC"],"ETH":["ETH","WSTETH","STETH","RETH","WETH"],"SOL":["SOL","JUPSOL","JITOSOL"]},"sub_allocation":"proportional","min_trade_usd":25}' | jq .
```

---

## 8) CORS, déploiement, GitHub Pages

- **CORS** : si l’UI est servie depuis un domaine différent (ex. GitHub Pages), ajoutez ce domaine à `CORS_ORIGINS` dans `.env`.
- **GitHub Pages** : placez une copie de `static/rebalance.html` dans `docs/`.  
  L’UI appellera l’API via l’URL configurée (`API URL` dans l’écran).
- **Docker/compose** : à venir (voir TODO).

---

## 9) Workflow Git recommandé

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

## 10) Roadmap courte

- **Alias Manager** (UI dédiée) + persistance `taxonomy.json` et endpoints admin (reload/save)
- Vue “Par lieu d’exécution” (exchange / ledger / DeFi) + plan par lieu
- **Dry-run d’exécution** pour 1 exchange (arrondis, tailles mini, frais)
- **Tests** unitaires & d’intégration, logs plus verbeux
- **Docker** (dev & run)

---
