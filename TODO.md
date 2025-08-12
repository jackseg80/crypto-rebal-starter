# TODO — Crypto Rebal Starter

Suivi des tâches du projet.  
Légende : ✔️ fait · ⬜ à faire · ~ estimation

---

## 1) Données & normalisation
- ✔️ Connexion CoinTracking & récupération des soldes
- ✔️ Normalisation (symbol, alias, value_usd)
- ✔️ Filtre `< min_usd`
- ✔️ Agrégation par groupes (BTC, ETH, Stablecoins, SOL, L1/L0 majors, Others)
- ✔️ `GET /portfolio/groups?source=cointracking&min_usd=...`
- ✔️ Remontée des `unknown_aliases`
- ⬜ Persistance **taxonomie & config** (JSON/YAML) + rechargement à chaud + endpoints admin  
  ~ 0.5 j

## 2) Plan de rebalancement (simulation)
- ✔️ `POST /rebalance/plan?source=...&min_usd=...`
- ✔️ Compat `group_targets_pct` **ou** `targets` (dict/list)
- ✔️ `primary_symbols` par groupe (BTC→ BTC/TBTC/WBTC, etc.)
- ✔️ `sub_allocation="proportional"`
- ✔️ `min_trade_usd`
- ✔️ Ligne d’**équilibrage** pour Σ(usd)=0
- ⬜ **Estimation des quantités** : `est_quantity` + `price_used` (fetch prix + cache)  
  ~ 0.5 j

## 3) “Advisor” / couverture des cibles
- ⬜ Module d’**auto-conseil** si une cible contient peu/pas d’actifs détenus  
  (ex: proposer une short-list pour “Other L1/L0 majors”)  
  ~ 0.5–1 j

## 4) Localisation & exécution
- ⬜ **Localisation** des actifs (exchange, ledger, DeFi) dans la photo courante  
  (via champs, tags ou mapping simple)  
  ~ 0.5 j
- ⬜ Plan **par lieu** (auto via API vs manuel)  
  ~ 0.5 j
- ⬜ **Connecteur d’exécution** — phase 1 **dry-run** pour 1 exchange  
  (tailles min, arrondis, frais, slippage, garde-fous, journalisation)  
  ~ 1–2 j
- ⬜ Connecteurs supplémentaires (par exchange)  
  ~ 0.5–1 j / exchange

## 5) Frontend (page HTML)
- ✔️ Page sliders/phase (existante)
- ⬜ Brancher la page sur `GET /portfolio/groups` et `POST /rebalance/plan`  
  (bouton “Simuler”, affichage actions, export CSV/clipboard, params `primary_symbols`, `min_trade_usd`, mode d’alloc)  
  ~ 0.5–1 j
- ⬜ Mini page **Alias Manager** (lister unknowns, ajouter mapping, sauvegarder)  
  ~ 0.5 j

## 6) Qualité, sécurité, ops
- ✔️ Repo GitHub + PR/Merge OK
- ⬜ Tests unitaires (taxonomie, planner, normalisation)  
  ~ 0.5–1 j
- ⬜ Tests d’intégration (endpoints avec fixtures)  
  ~ 0.5 j
- ⬜ Logging propre + messages d’erreurs utiles  
  ~ 0.25 j
- ⬜ Config & secrets (.env), CORS, (option) auth basique  
  ~ 0.25–0.5 j
- ⬜ Dockerfile & compose (dev)  
  ~ 0.25 j
- ⬜ README / doc d’usage (API + UI + scripts PS)  
  ~ 0.25–0.5 j

---

## Estimations globales

- **MVP Simulation complète** (prix/qty + UI branchée + alias manager + persistance + localisation basique + tests & docs)  
  **~ 2.5–4 jours**
- **Phase Exécution** (plan par lieu + 1er connecteur en dry-run)  
  **~ 1.5–2.5 jours**
- **Total** (MVP + 1 exchange dry-run)  
  **~ 4–6.5 jours**

---

## Priorités recommandées (ordre)
1. **Estimation quantités/prix** (compléter `est_quantity`/`price_used`)
2. **Persistance** taxonomie & config (+ endpoints admin)
3. **Brancher la page HTML** sur l’API (simulateur + export)
4. **Alias Manager** (résoudre les unknowns)
5. **Localisation** des actifs & plan d’action par lieu
6. **Connecteur dry-run** (1er exchange)
7. **Advisor** (suggestions d’actifs pour cibles “floues”)
8. **Tests / Docker / README**

---

## Notes rapides
- Les arrondis/équilibres côté plan sont en place (Σ(usd)=0).  
- Les scripts PowerShell de test fonctionnent ; ajuster après ajout des prix/quantités.  
- Garder une “liste blanche” des actifs éligibles par groupe dans la config persistée.