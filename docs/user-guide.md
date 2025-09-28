# Guide Utilisateur — État ACTUEL

Ce guide décrit l’UI **actuelle** :
- `static/dashboard.html` : vue d’ensemble (principalement Crypto aujourd’hui)
- **Crypto** :
  - `static/analytics-unified.html`
  - `static/risk-dashboard.html`
  - `static/rebalance.html`
- **Bourse / Saxo (actuel)** :
  - `static/saxo-dashboard.html` : dashboard bourse
  - `static/saxo-upload.html` : import CSV/XLSX Saxo
  - `static/analytics-equities.html` : analytics détaillées bourse (beta, legacy)
- `static/settings.html` : paramètres (selon versions : liens vers upload Saxo)

> **Note roadmap** : à terme, l'UI bourse adoptera des pages dédiées mirroirs de Crypto. `analytics-equities.html` (beta) existe maintenant mais en lecture legacy `/api/saxo/*`.

## 1. Chargement du portefeuille
- **Crypto** : `GET /balances/current?source=cointracking|cointracking_api&min_usd=1`
- **Bourse (actuel)** :
  - Importer via `saxo-upload.html` (CSV/XLSX)
  - Consulter via `saxo-dashboard.html`
  - Endpoints typiques : `/api/saxo/positions`, `/api/saxo/accounts`, …

> **Wealth (expérimental)** : voir `docs/api.md`. Non recommandé pour un usage quotidien tant que la migration n’est pas terminée.

## 2. Génération d'un plan de rebalancement
- **Crypto** : `POST /rebalance/plan` (targets manuels/dynamiques CCS)
- **Bourse** : non disponible aujourd'hui (voir roadmap)

Exemple curl (targets manuels):
```bash
curl -X POST "http://127.0.0.1:8000/rebalance/plan" \
  -H "Content-Type: application/json" \
  -d '{"group_targets_pct":{"BTC":40,"ETH":30,"Stablecoins":10,"Others":20}}'
```

## 3. Analytics & Risk
- **Crypto**
  - `analytics-unified.html`
  - `risk-dashboard.html` (VaR, caps, contradiction, etc.)
- **Bourse**
  - **Actuel** : `saxo-dashboard.html` (positions, répartition, etc.)
  - **Beta** : `analytics-equities.html` (analyse détaillée, lecture legacy)
  - **À venir** : `risk-equities.html`, `rebalance-equities.html` (voir roadmap)
  - Banques : non intégré aujourd'hui (voir roadmap)

## 4. Monitoring
- Monitoring (métier/portefeuille) et monitoring technique sont séparés (voir `docs/monitoring.md`)
- Utiliser les pages dédiées plutôt que les anciennes vues

## 5. Sources de données (imports)
- **Crypto** : CoinTracking (API/CSV) — voir `settings.html`
- **Bourse** : aujourd'hui via **`saxo-upload.html`**
- **Banques** : non intégré aujourd'hui

> **Roadmap** : l'upload Saxo sera relocalisé dans `settings.html` (section Sources) quand Wealth sera finalisé.
