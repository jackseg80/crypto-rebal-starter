# TODO — Crypto Rebal Starter

Suivi des tâches du projet.  
Légende : ✔️ fait · ⬜ à faire · ~ estimation

---

## 1) Données & normalisation
- ✔️ CoinTracking **API** (getBalance prioritaire, fallback grouped, placeholders filtrés)
- ✔️ Normalisation (symbol, alias, value_usd, amount, price_usd)
- ✔️ Filtre `< min_usd`
- ✔️ Endpoint `GET /balances/current?source=cointracking_api&min_usd=...`
- ✔️ Debug `GET /debug/ctapi`
- ✔️ Cache CT API 60 s
- ⬜ Persistance **taxonomie & config** (JSON) + reload à chaud + endpoints admin  
  ~ 0.5 j

## 2) Plan de rebalancement (simulation)
- ✔️ `POST /rebalance/plan?source=...&min_usd=...`
- ✔️ Compat `group_targets_pct` **ou** `targets`
- ✔️ `primary_symbols` par groupe
- ✔️ `sub_allocation` (proportional / primary_first auto si primary_symbols saisis)
- ✔️ `min_trade_usd`
- ✔️ CSV `/rebalance/plan.csv` aligné (usd, est_quantity, price_used)
- ✔️ **Système de pricing hybride** (3 modes intelligents) :
  - **Local** (rapide) : prix calculés depuis balances (value_usd/amount)
  - **Hybride** (recommandé) : local + basculement auto vers marché si données anciennes
  - **Auto/Marché** (précis) : prix live CoinGecko/Binance exclusivement
  - Stables 1.0 (USD/USDT/USDC)
  - Aliases TBTC/WBTC→BTC, WETH/STETH/WSTETH/RETH→ETH, JUPSOL/JITOSOL→SOL
  - Strip suffixes numériques: `ATOM2→ATOM`, `SOL2→SOL`, …
  - Provider ordre configurable : coingecko,binance,file
- ✔️ Ligne d’équilibrage Σ(usd)=0

## 3) Alias & taxonomy
- ✔️ `GET /taxonomy/unknown_aliases`
- ✔️ `POST /taxonomy/aliases` (formats A/B)
- ⬜ Mini page **Alias Manager** (vue dédiée, recherche, batch)  
  ~ 0.5 j
- ⬜ Persistance/chargement taxonomy.json (admin endpoints)  
  ~ 0.5 j

## 4) Localisation & exécution
- ⬜ Localisation des actifs (exchange / ledger / DeFi)  
  ~ 0.5 j
- ⬜ Plan **par lieu** (regroupement auto)  
  ~ 0.5 j
- ⬜ Connecteur d’exécution — phase 1 **dry-run** (1 exchange)  
  ~ 1–2 j
- ⬜ Connecteurs supplémentaires (par exchange)  
  ~ 0.5–1 j / exchange

## 5) Frontend
- ✔️ Page `rebalance.html` (API URL, source select, localStorage, CSV)
- ✔️ **Badge pricing intelligent** (Prix locaux/Prix marché selon mode actif)
- ✔️ Pastille **source utilisée** (+ avertissement si mismatch)
- ✔️ Unknown aliases: ajout unitaire + "Tout ajouter → Others"
- ✔️ Contrôles (Top, Deltas, Net≈0, micro-trades)
- ⬜ Mini page **Alias Manager** séparée  
  ~ 0.5 j
- ⬜ Vue “Par lieu” (breakdown exécution)  
  ~ 0.5 j

## 6) Qualité, sécurité, ops
- ✔️ Repo GitHub + PR/Merge OK
- ⬜ Tests unitaires (taxonomy, planner, normalisation, pricing)  
  ~ 0.5–1 j
- ⬜ Tests d’intégration (endpoints avec fixtures)  
  ~ 0.5–1 j
- ⬜ Logging propre + messages d’erreurs utiles  
  ~ 0.25 j
- ⬜ Config & secrets (.env), CORS, (option) auth basique  
  ~ 0.25–0.5 j
- ⬜ Dockerfile & compose (dev)  
  ~ 0.25 j
- ⬜ README / doc d’usage (API + UI + scripts PS) — **MAJ faite**  
  ~ 0.25–0.5 j

---

## Estimations globales (restant)
- **MVP complet** (persistance taxonomy, Alias Manager, vue par lieu, tests & Docker)  
  **~ 2–3 jours**
- **Phase Exécution** (1er exchange en dry-run)  
  **~ 1.5–2.5 jours**
