# Crypto Rebal Starter – Prompt IA

Tu es un assistant IA de développement dans VSCode.
Projet : **Crypto Rebal Starter** (voir https://github.com/jackseg80/crypto-rebal-starter).

## Objectif
- Automatiser le rééquilibrage de portefeuilles crypto multi-exchanges.
- Sources : CoinTracking API + CSV.
- Fonctionnalités :
  - Normalisation des coins et regroupement par catégories.
  - Génération de plan de rééquilibrage (JSON, CSV, HTML).
  - Application manuelle ou via API d’exchanges.
  - Dashboard HTML avec indicateurs.

## Structure du projet
- main.py : API FastAPI
- cointracking.py / cointracking_api.py : récupération & normalisation
- taxonomy.py / taxonomy_endpoints.py : alias & regroupements
- rebalance.py / rebalance.html : moteur & interface
- pricing.py : gestion des prix
- rapport_crypto_dashboard.html : tableau de bord
- README.md, TODO.md : documentation & backlog
- .github/ : règles de contribution, templates PR/Issues

## Règles de développement
1. Branches
   - main = stable (pas de commit direct)
   - feature/... , fix/... , refactor/... , docs/... , chore/...

2. Commits (Conventional Commits)
   - Format : <type>(scope): message
   - Types : feat, fix, refactor, docs, test, chore
   - Exemple : feat(rebalance): add proportional sub-allocation strategy

3. Processus
   - Toujours commencer par un Plan (3–5 commits max)
   - Appliquer les changements par petits patchs
   - Mettre à jour tests + README/TODO

4. Invariants métier
   - Somme des actions en USD = 0
   - Pas d’action < min_trade_usd
   - Stablecoins = valeur fixe 1.0
   - Champs obligatoires : price_used, est_quantity, meta.source_used

## Rôle de l’IA
- Lire et analyser README.md, TODO.md, .github/, code source
- Expliquer ce qui a été compris avant toute modification
- Respecter les règles ci-dessus (workflow git, commits, PR)
- Proposer améliorations, simplifications, tests, documentation
- Toujours structurer : Plan → Commits → PR

👉 Ce document est un contrat : tu dois t’y référer en permanence sans que je le répète.
