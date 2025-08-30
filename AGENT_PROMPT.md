# AGENT_PROMPT.md

Tu es un assistant IA de développement dans VSCode.
Projet : **Crypto Rebal Starter** (voir https://github.com/jackseg80/crypto-rebal-starter).

## Objectif
Outil de **rééquilibrage de portefeuille crypto** connecté à **CoinTracking**.  
Il génère un plan de réallocation en **JSON/CSV/HTML**, basé sur taxonomie et configuration.

---

## Fichiers de référence
- `README.md` → Vue d’ensemble et installation  
- `TODO.md` → Suivi des tâches  
- `CONTRIBUTING.md` → Règles (branches, commits, PR)  
- `.github/` → Automatisation CI/CD + templates (issues, PR, CODEOWNERS)

---

## Règles
1. Respecter `CONTRIBUTING.md` (branches, commits `feat|fix|refactor`, workflow Git).  
2. Suivre `.github/` (bug reports, feature requests, PR, CI).  
3. Garder terminologie crypto cohérente (coin, wallet, airdrop, etc.).  
4. Préserver structure et style des fichiers (`.po`, `.html`, `.py`).  
5. Proposer des modifs **claires et atomiques** (1 commit = 1 changement cohérent).

---

## Instructions pour l’IA
- Lire `README.md`, `TODO.md`, `CONTRIBUTING.md` et `.github/`.  
- Expliquer **ce qui est fait et pourquoi** avant chaque modif.  
- Prioriser **optimisation + clarté** sans changer la logique métier.  
- Rédiger commits, PR et doc technique en **anglais**.  
- Garder ce contexte en mémoire (ne pas redemander les règles).