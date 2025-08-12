# crypto-rebal-starter

API FastAPI pour **agréger ton portefeuille CoinTracking**, afficher des **groupes simplifiés** (BTC, ETH, Stablecoins, SOL, L1/L0 majors, Others) et calculer un **plan de rebalancement** exécutable (liste d’achats/ventes par symbole).

---

## ⚙️ Prérequis

- Python 3.11+ (testé avec 3.13)
- `pip` (ou `uv` si tu l’utilises)
- (Optionnel) un fichier `.env` — un exemple est fourni dans `.env.example`

---

## 🚀 Installation rapide

```bash
git clone https://github.com/jackseg80/crypto-rebal-starter.git
cd crypto-rebal-starter

# Crée ton venv (exemples)
python -m venv .venv
# Windows PowerShell
. .venv/Scripts/Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Copie ensuite le fichier d’exemple d’environnement :

```bash
cp .env.example .env
# puis adapte les variables si besoin
```

---

## ▶️ Lancer l’API

```bash
uvicorn api.main:app --reload --port 8000
```

- Swagger/Playground : <http://127.0.0.1:8000/docs>

> **Astuce** : la plupart des routes ont un paramètre `source=cointracking` et un filtre `min_usd` (pour ignorer les poussières).

---

## 📚 Endpoints principaux

### 1) Snapshot brut (balances courantes)

```
GET /balances/current?source=cointracking&min_usd=1
```

- **But** : récupérer la liste des positions (symbol, value_usd, …).
- **Retour** : `{ items: [...], total_usd: number }`

### 2) Groupes (vue simplifiée pour décisions rapides)

```
GET /portfolio/groups?source=cointracking&min_usd=1
```

- **But** : agréger ton portefeuille par groupes : `BTC`, `ETH`, `Stablecoins`, `SOL`, `L1/L0 majors`, `Others`.
- **Retour** : total, détail par groupe, poids % et `unknown_aliases` (à mapper).

### 3) Debug / Snapshot formaté

```
GET /debug/snapshot?source=cointracking&alias=all&min_usd=1
```

- **But** : aide au débogage (aperçu de la taxonomie, alias inconnus, etc.).

### 4) Plan de rebalancement (POST)

```
POST /rebalance/plan?source=cointracking&min_usd=1
Content-Type: application/json
```

**Body (exemple minimal)** :

```json
{
  "group_targets_pct": {
    "BTC": 35,
    "ETH": 25,
    "Stablecoins": 10,
    "SOL": 10,
    "L1/L0 majors": 10,
    "Others": 10
  },
  "sub_allocation": "proportional",
  "min_trade_usd": 25,
  "primary_symbols": {
    "BTC": ["BTC","TBTC","WBTC"],
    "ETH": ["ETH","WSTETH","STETH","RETH","WETH"],
    "SOL": ["SOL","JUPSOL","JITOSOL"]
  }
}
```

**Notes** :
- Tu peux aussi envoyer `targets` **(liste)** au lieu de `group_targets_pct` **(objet)** :

```json
{
  "targets": [
    { "group": "BTC", "weight_pct": 35 },
    { "group": "ETH", "weight_pct": 25 },
    { "group": "Stablecoins", "weight_pct": 10 },
    { "group": "SOL", "weight_pct": 10 },
    { "group": "L1/L0 majors", "weight_pct": 10 },
    { "group": "Others", "weight_pct": 10 }
  ],
  "sub_allocation": "proportional",
  "min_trade_usd": 25
}
```

**Réponse** (extraits) :
- `total_usd`
- `current_by_group`, `current_weights_pct`
- `target_weights_pct`, `targets_usd`
- `deltas_by_group_usd`
- `actions`: liste d’ordres **buy/sell** par symbole (`group`, `alias`, `symbol`, `usd`, …)
- `unknown_aliases`: symboles non mappés dans la taxonomie

---

## 🧭 Exemples d’utilisation

### cURL — groupes

```bash
curl "http://127.0.0.1:8000/portfolio/groups?source=cointracking&min_usd=1"
```

### cURL — plan de rebalancement

```bash
curl -X POST "http://127.0.0.1:8000/rebalance/plan?source=cointracking&min_usd=1"   -H "Content-Type: application/json"   -d '{
    "group_targets_pct": { "BTC":35,"ETH":25,"Stablecoins":10,"SOL":10,"L1/L0 majors":10,"Others":10 },
    "sub_allocation": "proportional",
    "min_trade_usd": 25,
    "primary_symbols": {
      "BTC": ["BTC","TBTC","WBTC"],
      "ETH": ["ETH","WSTETH","STETH","RETH","WETH"],
      "SOL": ["SOL","JUPSOL","JITOSOL"]
    }
  }'
```

### PowerShell — plan (extrait)
```powershell
$body = @{
  group_targets_pct = @{
    BTC = 35; ETH = 25; "Stablecoins" = 10; SOL = 10; "L1/L0 majors" = 10; Others = 10
  }
  sub_allocation = "proportional"
  min_trade_usd = 25
  primary_symbols = @{
    BTC = @("BTC","TBTC","WBTC")
    ETH = @("ETH","WSTETH","STETH","RETH","WETH")
    SOL = @("SOL","JUPSOL","JITOSOL")
  }
} | ConvertTo-Json -Depth 10

$plan = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/rebalance/plan?source=cointracking&min_usd=1" `
  -Method POST -Body $body -ContentType "application/json"

$plan.actions | Select-Object group,alias,symbol,usd | Sort-Object usd
```

---

## 🧩 Taxonomie & alias

- Les groupes attendus par l’API : **BTC**, **ETH**, **Stablecoins**, **SOL**, **L1/L0 majors**, **Others**.
- Si des symboles apparaissent dans `unknown_aliases`, il faut les mapper (ajouter un alias) dans la taxonomie.
- Emplacement : `api/taxonomy.py` (ou directement dans le code selon le commit où tu es).
- Exemple d’alias : `{"TBTC": "BTC", "WSTETH": "ETH", "STETH": "ETH", ...}`

---

## 🔒 Variables d’environnement

Voir `.env.example` pour une liste commentée. Dans beaucoup de cas, **rien n’est requis** si tu consommes CoinTracking via le flux déjà en place. Si tu branches une API/CSV personnelle, utilise les variables prévues.

---

## ✅ État / Todo (résumé)

- [x] Agrégation par groupes & filtres `min_usd`
- [x] Endpoint `/rebalance/plan` avec `group_targets_pct` **ou** `targets`
- [x] Répartition intra-groupe via `sub_allocation="proportional"` et `primary_symbols`
- [x] Sortie détaillée des `actions`
- [x] `unknown_aliases` pour compléter la taxonomie
- [ ] Conseils auto pour remplir des groupes cibles vides (module *advice*)
- [ ] Détection d’emplacement (CEX, Ledger, DeFi) + plan d’exécution
- [ ] Export avancé (CSV/Excel) + UI qui consomme l’API

---

## 🆘 Dépannage

- **Tout est à 0** : vérifie `min_usd`, la source `?source=cointracking`, et le mapping d’alias.
- **Alias inconnus** : utilise `/debug/snapshot` pour la liste puis complète la taxonomie.
- **Erreur de parsing `min_usd`** : passe un nombre valide (`min_usd=1` et pas une chaîne vide).
- **Plan non équilibré** : regarde `min_trade_usd` (les petites lignes sont ignorées).

---

flowchart LR
  %% ============ Styles ============
  classDef ui fill:#FFF3E0,stroke:#FB8C00,color:#111,stroke-width:1px
  classDef api fill:#E8F0FE,stroke:#4285F4,color:#111,stroke-width:1px
  classDef core fill:#EAF7EE,stroke:#2E7D32,color:#111,stroke-width:1px
  classDef conn fill:#FCE4EC,stroke:#AD1457,color:#111,stroke-width:1px
  classDef ext fill:#E0F7FA,stroke:#006064,color:#111,stroke-width:1px
  classDef file fill:#F3E5F5,stroke:#6A1B9A,color:#111,stroke-width:1px

  %% ============ UI ============
  subgraph UI[Front Web (HTML/JS)]
    sliders[Sliders poids par groupes\n+ phase cycle\n+ min_usd & min_trade_usd]:::ui
    viewGroups[Vue « Portfolio Groups »\n(GET /portfolio/groups)]:::ui
    viewPlan[Vue « Rebalance Plan »\n(POST /rebalance/plan)]:::ui
  end

  %% ============ API ============
  subgraph API[API FastAPI]
    routeGroups[/GET /portfolio/groups/]:::api
    routePlan[/POST /rebalance/plan/]:::api
    routeExec[/POST /rebalance/execute/ (à implémenter)/]:::api
    routeSnap[/GET /debug/snapshot/]:::api
  end

  %% ============ Core ============
  subgraph Core[Domain / Core]
    taxonomy[Taxonomy & Aliases\n(symbol → alias → groupe)]:::core
    grouper[Aggregator\n(grouping + poids actuels)]:::core
    planner[Planner\n(cibles %, deltas $, actions)]:::core
    allocator[Allocator\n(sub_allocation: proportional|equal)]:::core
    advisor[Advisor (à faire)\n(suggère coins manquants par groupe)]:::core
    router[Routing (à faire)\n(où sont les coins: CEX/Ledger/DeFi)]:::core
  end

  %% ============ Connecteurs ============
  subgraph Connecteurs[Connecteurs]
    cointracking[(CoinTracking\nbalances current)]:::conn
    exAPIs[APIs d’exchanges (à faire)\nBinance, Kraken, …]:::conn
  end

  %% ============ Ext ============
  subgraph Ext[Exchanges & Wallets]
    cex[CEX]:::ext
    cold[Ledger / Cold]:::ext
    defi[DeFi]:::ext
  end

  %% ============ Fichiers ============
  subgraph Files[Fichiers / Exports]
    csv[CSV des actions\nrebalance-actions.csv]:::file
    xlsx[(XLSX export – optionnel)]:::file
  end

  %% ============ Flows ============
  sliders -->|params (poids, min_usd, min_trade_usd)| routePlan
  viewGroups --> routeGroups
  UI -->|debug| routeSnap

  routeGroups --> cointracking
  cointracking --> routeGroups
  routeGroups --> taxonomy --> grouper --> routeGroups

  routePlan --> cointracking --> routePlan
  routePlan --> taxonomy --> grouper --> planner --> allocator
  advisor -. suggestions .-> planner
  router -. contraintes d’exécution .-> planner
  planner -->|actions buy/sell par alias| routePlan
  routePlan --> csv

  routeExec --> planner
  routeExec --> exAPIs --> cex
  routeExec --> cold
  routeExec --> defi
  routeExec --> csv


## Licence

MIT (ou celle de ton repo s’il y en a une). Bon build !
