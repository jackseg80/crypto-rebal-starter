# Changelog (Synthétique)

Ce changelog regroupe les informations essentielles issues de `RELEASE_NOTES` et `RECENT_FIXES` en une vue compacte et actionnable.

## 2025-08-28 — Risk Dashboard 2.0 (Real‑Time Analytics)
- Market data live: Fear & Greed, BTC dominance, funding rates, ETH/BTC ratio, volatilité 7j, momentum.
- Portfolio risk analytics: VaR/CVaR (95/99), Sharpe/Sortino, matrice de corrélation 11×11, score diversification.
- UX: codes couleurs, interprétations contextuelles, recommandations dynamiques, executive summary.
- Technique: ordre des fonctions JS corrigé (scope), gestion d’erreurs API + fallbacks, debug logging étendu.

Impact: Dashboard risque passe de mock à données temps réel avec analytics spécifiques au portefeuille.

## 2025-08-27 — CSV Auto‑Download + Corrections critiques
- Nouvel endpoint: `POST /csv/download` (CoinTracking, noms datés, validation contenu, taille minimale).
- UI Settings: section « Téléchargement Automatique CSV », statut en temps réel.
- Parsing: support patterns dynamiques (Balance by Exchange/Coins by Exchange), tri par date.
- Fix critique: balances vides corrigées (loop sur `raw.items` au lieu du dict; front passe par API backend `/balances/current`).

Impact: Workflow CSV simplifié, compatibilité noms datés, stabilité accrue de l’ingestion.

## 2025-08-25 — CCS Sync + Monitoring Unified + Thème global
- CCS → Rebalance: synchronisation complète, targets dynamiques, debug localStorage.
- Monitoring: restauration des onglets, affichage, erreurs/chargement.
- Thème: synchronisation cross‑tabs, clés unifiées `crypto_rebalancer_settings`, persistance dark/light.
- Portfolio dashboard: valeurs correctes, Chart.js thème‑aware, groupement d’assets (WBTC/BTC, stETH/ETH, …).

Impact UX: Cohérence visuelle, rétablissement monitoring, intégration CCS exploitable.

## Améliorations transverses (Août 2025)
- Logging conditionnel: `debug-logger.js`, réduction du bruit en prod, `toggleDebug()`.
- Validation inputs: `input-validator.js` (targets = 100%, montants, clés API, sanitisation).
- Performance: `performance-optimizer.js` (TTL cache, pagination >500, Web Workers >1000, debouncing, lazy/batched rendering).
- Qualité code: try/catch et messages clairs, standardisation localStorage, gestion erreurs renforcée.

## Bugs notables corrigés
- Execution validation: support `quantity` et `est_quantity` (compat) dans `execution.html`.
- JS syntax/try‑catch mal formés dans certaines pages → corrigés.
- CCS non visible dans Rebalance → détection/sync corrigées.
- Monitoring tabs inactifs → restauration `switchTab()`.

## Notes d’upgrade rapides
- UI: utiliser `static/monitoring-unified.html` (au lieu de l’ancien nom).
- Analytics: endpoints sous `/analytics/*` (remplace `/api/analytics/*`).
- Execution history: `GET /api/execution/history/sessions`.
- CSV: privilégier `Balance by Exchange`; sinon fallback Current Balance; utiliser `/csv/download`.

Historique complet et détails techniques: voir `docs/_legacy/RELEASE_NOTES.md` et `docs/_legacy/RECENT_FIXES.md`.
