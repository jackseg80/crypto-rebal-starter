# Contributing – Crypto Rebal Starter

Bienvenue ! Ce projet vise à automatiser le rééquilibrage de portefeuilles crypto avec :
- Récupération des soldes via CoinTracking
- Normalisation et agrégation par groupes (BTC, ETH, Stablecoins, etc.)
- Génération d’un plan de rééquilibrage (JSON / CSV)
- Application manuelle ou automatisée via API Exchange
- Dashboard HTML pour la visualisation

Ce document définit les règles et bonnes pratiques pour contribuer efficacement.

======================================================================
1. Workflow Git
======================================================================
- Ne jamais travailler directement sur main.
- Créer une branche dédiée :
  - feature/...   → nouvelle fonctionnalité
  - fix/...       → correction de bug
  - refactor/...  → optimisation du code sans changement de logique
  - docs/...      → documentation
  - chore/...     → maintenance, dépendances, CI/CD
- Toute contribution doit passer par une Pull Request.

======================================================================
2. Conventional Commits
======================================================================
Format obligatoire :
<type>(scope): message court

Types autorisés :
- feat(scope): nouvelle fonctionnalité
- fix(scope): correction de bug
- refactor(scope): simplification ou optimisation
- docs(scope): documentation
- test(scope): ajout ou correction de tests
- chore(scope): maintenance, dépendances, CI/CD

Exemples :
- feat(rebalance): add proportional sub-allocation strategy
- fix(taxonomy): correct alias resolution for WSTETH
- refactor(pricing): simplify stablecoin handling
- docs: update README with CoinTracking API usage

======================================================================
3. Règles de développement
======================================================================
- Toujours commencer par un Plan (3–5 commits maximum).
- Chaque commit doit rester lisible (≤ 200 lignes de diff).
- Les modifications doivent inclure :
  - Mise à jour des tests si nécessaire
  - Respect strict des invariants métier (voir §4)
  - Mise à jour de README.md et TODO.md si applicable

======================================================================
4. Invariants métier
======================================================================
A ne jamais casser :
- Somme des actions en USD = 0 (achats = ventes).
- Pas d’action avec |usd| < min_trade_usd.
- Valeur des stablecoins forcée à 1.0.
- Champs obligatoires à remplir :
  - price_used
  - est_quantity
  - meta.source_used

======================================================================
5. Tests locaux
======================================================================
Lancer l’API :
uvicorn main:app --reload --port 8000

Points de contrôle rapides :
- GET /healthz           → doit retourner {"ok": true}
- GET /balances/current  → soldes agrégés
- POST /rebalance/plan   → génération d’un plan JSON
- POST /rebalance/plan.csv → génération d’un plan CSV

Interface utilisateur :
- Ouvrir rebalance.html
- Vérifier que l’UI interagit bien avec l’API

======================================================================
6. Pull Requests
======================================================================
- Une PR = une seule fonctionnalité ou un fix précis.
- Vérifier avant envoi :
  [ ] Tests locaux passés
  [ ] Invariants métier respectés
  [ ] Documentation mise à jour
- Utiliser le template PR dans .github/

======================================================================
Merci d’appliquer ces règles pour garantir un projet clair, stable et pro 🚀
