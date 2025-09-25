# Guide Utilisateur (Niveau intermédiaire)

Ce guide couvre les usages principaux avec exemples.

## 1. Chargement du portefeuille
- Endpoint: `GET /balances/current?source=cointracking&min_usd=1`
- UI: `static/dashboard.html`
- Source sélectionnée dans `static/settings.html` (liste centralisée). Changer la source met à jour tous les écrans.

## 2. Génération d’un plan de rebalancement
- Endpoint: `POST /rebalance/plan`
- UI: `static/rebalance.html`
- Targets dynamiques (CCS): passer `dynamic_targets=true` et fournir `dynamic_targets_pct`.

Exemple curl (targets manuels):
```bash
curl -X POST "http://127.0.0.1:8000/rebalance/plan" \
  -H "Content-Type: application/json" \
  -d '{"group_targets_pct":{"BTC":40,"ETH":30,"Stablecoins":10,"Others":20}}'
```

## 3. Exécution (simulation/temps réel)
- Endpoints: `/execution/*` et `/api/execution/*`
- UI: `static/execution.html`, `static/execution_history.html`
- Historique sessions: `GET /api/execution/history/sessions`

Flux type:
- Valider un plan: `POST /execution/validate-plan`
- Lancer en arrière-plan: `POST /execution/execute-plan?plan_id=...&dry_run=true`
- Suivre le statut: `GET /execution/status/{plan_id}`

## 4. Gestion des risques
- Endpoints: `/api/risk/metrics`, `/api/risk/correlation`, `/api/risk/stress-test`, `/api/risk/dashboard`
- UI: `static/risk-dashboard.html`
- La “Total Value” suit la devise d’affichage (réglée dans Settings). La conversion se fait à l’affichage (USD→EUR/BTC) et affiche `—` si le taux n’est pas disponible.

Métriques incluses: VaR/CVaR, Sharpe, Sortino, Max Drawdown, Ulcer Index, skew/kurtosis.

## 5. Taxonomie & Aliases
- Endpoints: `/taxonomy`, `/taxonomy/suggestions`, `/taxonomy/auto-classify`
- UI: `static/alias-manager.html`

## 6. Monitoring
- Portefeuille (métier): `/api/portfolio/metrics`, `/api/portfolio/alerts`
- Système (avancé): `/api/monitoring/health`, `/api/monitoring/alerts`
- UI: `static/monitoring.html` (métier), `static/monitoring_advanced.html` (technique)

Différence Métier vs Technique:
- Métier (portfolio): alertes pipeline et déviations d’allocation.
- Technique (monitoring): santé système/composants (latences, connexions, historiques).

## 7. CSV CoinTracking
- Export automatique: `POST /csv/download` (current_balance, balance_by_exchange, coins_by_exchange)

Pour la liste complète, consultez `docs/api.md` ou l’OpenAPI (`/docs`).

---

### Paramètres UI globaux
- `static/settings.html` — Réglages rapides: Source de données, Devise d’affichage, Seuil min USD, Thème, URL API.
- Les sélecteurs rapide et détaillé (onglet Pricing) sont synchronisés; un changement re-formate automatiquement les montants sur les pages ouvertes.

### Governance UI – cap et convergence

- Le cap affiché provient de la policy active. En l’absence de policy, l’UI peut afficher le cap SMART comme information secondaire.
- Le badge “🧊 Freeze/Cap serré (±X%)” apparaît pour Freeze ou cap ≤ 2%.
