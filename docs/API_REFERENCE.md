# API Reference (auto-généré)

> **Note**
> Ce document est **auto-généré** par `tools/gen_api_reference.py`.
> Merci de **ne pas éditer les tableaux de routes à la main**. Les sections "Guides", "Conventions" et "Exemples" ci-dessous sont **éditables**.

# Référence API — Vue d'ensemble

Cette référence liste **toutes les routes** (GET/POST/PUT/DELETE/PATCH), groupées par **namespace** (premier segment du chemin).
Elle complète les documents fonctionnels : `docs/FRONTEND_PAGES.md` (qui consomme quoi) et `docs/MODULE_MAP.md` (modules & exports).

## TL;DR — Quickstart

- **Base URL** : définie via `static/global-config.js` (`API_BASE_URL`) — **pas d'URL en dur**.
- **Auth** : `Authorization: Bearer <token>` (si activé)
- **Content-Type** : `application/json; charset=utf-8`
- **Réponses JSON** : UTF-8, champs snake_case
- **Cache** : `ETag` + `If-None-Match` (voir section ETag)

### Exemple `curl`
```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json" \
     "$API_BASE_URL/portfolio/metrics?user_id=alice&since=2025-01-01"
```

## Conventions

### Identifiants & multi-tenant
- Tous les endpoints acceptent/propagent `user_id` (query ou header).
- Les identifiants de ressources sont en UUID (sauf mention contraire).

### Paramètres
- **Path params** : `/resource/{id}` → obligatoires
- **Query params** : optionnels, typés (bool=true|false, dates ISO-8601, décimaux en .)

### Pagination
- **Entrée** : `limit` (par défaut 50, max 500), `cursor` (opaque)
- **Sortie** :
```json
{ "data": [...], "next_cursor": "..." }
```
- Boucler côté client jusqu'à `next_cursor = null`.

### Filtrage & tri
- Filtrage par champ : `?status=active&asset=BTC`
- Tri : `?order_by=timestamp&order=desc`

### Champs communs (réponses liste)
- `data`: tableau d'objets
- `meta`: informations complémentaires (facultatif)
- `next_cursor`: pagination (facultatif)

## ETag, cache & idempotence
- **ETag** renvoyé sur les endpoints de lecture; réutiliser via `If-None-Match` pour éviter les transferts inutiles (réponse 304 Not Modified).
- Les POST idempotents peuvent, si exposé, accepter `Idempotency-Key` (UUID v4) → répéter une requête ne duplique pas l'effet.

## Gestion des erreurs
- Codes HTTP standard : 400 (validation), 401 (auth), 403 (droits), 404 (absent), 409 (conflit), 422 (schéma), 429 (rate limit), 5xx (serveur).
- Format d'erreur :
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Field 'amount' must be > 0",
    "details": { "field": "amount", "min": 0 }
  },
  "request_id": "req_abc123"
}
```

### Exemple erreur curl
```bash
curl -i -H "Accept: application/json" "$API_BASE_URL/api/risk/score?user_id="
# HTTP/1.1 400 Bad Request
# { "error": { "code": "VALIDATION_ERROR", "message": "..."} , "request_id": "..." }
```

## Authentification & sécurité
- **Auth** (si activée) : `Authorization: Bearer <token>`.
- **Scope minimal** : principe du moindre privilège (lecture seule si possible).
- **Journaux** : chaque requête est horodatée (Europe/Zurich) et peut renvoyer `request_id`.

## Versionning & stabilité
- Les URLs sont stables; les évolutions rétro-compatibles ajoutent des champs optionnels.
- Les dépréciations sont annoncées dans `CHANGELOG.md` et marquées "(deprecated)" dans le tableau des routes.
- Les changements cassants sont regroupés et annoncés au moins 30 jours avant.

## Limitation de débit (rate limit)
- Réponses peuvent inclure :
  `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- En cas de 429, réessayer après `X-RateLimit-Reset`.

## Liens utiles
- Pages front consommant l'API : [docs/FRONTEND_PAGES.md](docs/FRONTEND_PAGES.md)
- Modules JS appelant l'API : [docs/MODULE_MAP.md](docs/MODULE_MAP.md)
- Sémantique Risk (canonique) : [docs/RISK_SEMANTICS.md](docs/RISK_SEMANTICS.md)
- P&L Today : [docs/PNL_TODAY.md](docs/PNL_TODAY.md)
- Simulation Engine : [docs/SIMULATION_ENGINE.md](docs/SIMULATION_ENGINE.md)

<!-- Les sections par namespace générées par l'outil commencent ci-dessous -->

## Namespace `/advanced-rebalancing`

| Method | Path | Summary | File |
|---|---|---|---|
| POST | `/advanced-rebalancing/constraints/validate` | Valide des contraintes de rebalancement personnalisées | `api/advanced_rebalancing_endpoints.py` |
| POST | `/advanced-rebalancing/plan` |  | `api/advanced_rebalancing_endpoints.py` |
| POST | `/advanced-rebalancing/simulate` | Simule plusieurs stratégies de rebalancement pour comparaison | `api/advanced_rebalancing_endpoints.py` |
| GET | `/advanced-rebalancing/strategies` | Liste les stratégies de rebalancement disponibles avec descriptions | `api/advanced_rebalancing_endpoints.py` |

## Namespace `/analytics`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/analytics/advanced/drawdown-analysis` | Analyser les périodes de drawdown en détail | `api/advanced_analytics_endpoints.py` |
| GET | `/analytics/advanced/metrics` | Calculer les métriques de performance avancées | `api/advanced_analytics_endpoints.py` |
| GET | `/analytics/advanced/risk-metrics` | Calculer les métriques de risque avancées | `api/advanced_analytics_endpoints.py` |
| GET | `/analytics/advanced/strategy-comparison` | Comparer les performances de différentes stratégies | `api/advanced_analytics_endpoints.py` |
| GET | `/analytics/advanced/timeseries` | Récupérer les données de série temporelle pour les graphiques | `api/advanced_analytics_endpoints.py` |
| GET | `/analytics/market-breadth` | Analyse de largeur de marché (market breadth) | `api/analytics_endpoints.py` |
| GET | `/analytics/optimization/recommendations` | Obtenir des recommandations d'optimisation | `api/analytics_endpoints.py` |
| POST | `/analytics/performance/calculate` | Calculer les métriques de performance d'un portfolio | `api/analytics_endpoints.py` |
| GET | `/analytics/performance/detailed` | Obtenir une analyse de performance détaillée | `api/analytics_endpoints.py` |
| GET | `/analytics/performance/summary` | Obtenir un résumé des performances | `api/analytics_endpoints.py` |
| GET | `/analytics/reports/comprehensive` | Générer un rapport de performance complet | `api/analytics_endpoints.py` |
| GET | `/analytics/sessions` | Obtenir la liste des sessions de rebalancement | `api/analytics_endpoints.py` |
| POST | `/analytics/sessions` | Créer une nouvelle session de rebalancement | `api/analytics_endpoints.py` |
| GET | `/analytics/sessions/{session_id}` | Obtenir les détails d'une session de rebalancement | `api/analytics_endpoints.py` |
| POST | `/analytics/sessions/{session_id}/actions` | Ajouter les actions de rebalancement à une session | `api/analytics_endpoints.py` |
| POST | `/analytics/sessions/{session_id}/complete` | Marquer une session comme terminée | `api/analytics_endpoints.py` |
| POST | `/analytics/sessions/{session_id}/execution-results` | Mettre à jour les résultats d'exécution d'une session | `api/analytics_endpoints.py` |
| POST | `/analytics/sessions/{session_id}/portfolio-snapshot` | Ajouter un snapshot de portfolio à une session | `api/analytics_endpoints.py` |

## Namespace `/api`

| Method | Path | Summary | File |
|---|---|---|---|
| POST | `/api/alerts/acknowledge/{alert_id}` | Acquitte une alerte | `api/alerts_endpoints.py` |
| GET | `/api/alerts/active` | Récupère les alertes actives | `api/alerts_endpoints.py` |
| GET | `/api/alerts/config/current` | Retourne la configuration actuelle des alertes | `api/alerts_endpoints.py` |
| POST | `/api/alerts/config/reload` | Recharge la configuration des alertes depuis le fichier | `api/alerts_endpoints.py` |
| GET | `/api/alerts/cross-asset/status` | Phase 2B2: Cross-Asset Correlation Status | `api/alerts_endpoints.py` |
| GET | `/api/alerts/cross-asset/systemic-risk` | Phase 2B2: Systemic Risk Assessment | `api/alerts_endpoints.py` |
| GET | `/api/alerts/cross-asset/top-correlated` | Phase 2B2: Top Correlated Asset Pairs | `api/alerts_endpoints.py` |
| GET | `/api/alerts/formatted` | Récupère les alertes actives avec format unifié pour UI | `api/alerts_endpoints.py` |
| GET | `/api/alerts/health` | Vérification de santé du système d'alertes | `api/alerts_endpoints.py` |
| GET | `/api/alerts/history` | Historique des alertes | `api/alerts_endpoints.py` |
| GET | `/api/alerts/metrics` | Récupère les métriques d'observabilité | `api/alerts_endpoints.py` |
| GET | `/api/alerts/metrics/prometheus` | Phase 2A Comprehensive Prometheus Metrics | `api/alerts_endpoints.py` |
| GET | `/api/alerts/multi-timeframe/coherence/{alert_type}` | Phase 2B1: Alert Type Coherence Analysis | `api/alerts_endpoints.py` |
| GET | `/api/alerts/multi-timeframe/status` | Phase 2B1: Multi-Timeframe Analysis Status | `api/alerts_endpoints.py` |
| POST | `/api/alerts/resolve/{alert_id}` | Résout définitivement une alerte | `api/alerts_endpoints.py` |
| POST | `/api/alerts/snooze/{alert_id}` | Snooze une alerte pour X minutes | `api/alerts_endpoints.py` |
| POST | `/api/alerts/test/acknowledge/{alert_id}` | Test endpoint pour acknowledge sans auth (DEBUG ONLY) | `api/alerts_endpoints.py` |
| GET | `/api/alerts/test/generate` | Alias sans paramètre de chemin: génère 3 alertes par défaut. | `api/alerts_endpoints.py` |
| POST | `/api/alerts/test/generate` | Alias sans paramètre de chemin: génère 3 alertes par défaut. | `api/alerts_endpoints.py` |
| POST | `/api/alerts/test/generate/{count}` | Endpoint de test pour générer des alertes de démonstration (DEBUG ONLY) | `api/alerts_endpoints.py` |
| POST | `/api/alerts/test/snooze/{alert_id}` | Test endpoint pour snooze sans auth (DEBUG ONLY) | `api/alerts_endpoints.py` |
| GET | `/api/alerts/types` | Liste les types d'alertes disponibles | `api/alerts_endpoints.py` |
| POST | `/api/backtesting/compare` | Compare multiple strategies side-by-side | `api/backtesting_endpoints.py` |
| GET | `/api/backtesting/metrics/definitions` | Get definitions of all backtesting metrics | `api/backtesting_endpoints.py` |
| GET | `/api/backtesting/performance/charts/{strategy}` | Get chart data for a specific strategy backtest | `api/backtesting_endpoints.py` |
| POST | `/api/backtesting/run` | Run comprehensive backtest for a single strategy | `api/backtesting_endpoints.py` |
| GET | `/api/backtesting/strategies` | Get list of available backtesting strategies | `api/backtesting_endpoints.py` |
| GET | `/api/config/data-source` | Get the currently configured data source | `api/main.py` |
| POST | `/api/config/data-source` | Set the data source configuration from frontend | `api/main.py` |
| GET | `/api/crypto-toolbox` | Proxy vers le backend Flask de scraping Crypto-Toolbox (port 8001 par défaut). | `api/main.py` |
| GET | `/api/execution/connections` | État détaillé des connexions aux exchanges | `api/execution_dashboard.py` |
| POST | `/api/execution/history/cleanup` | Nettoyer les anciennes données (maintenance) | `api/execution_history.py` |
| GET | `/api/execution/history/dashboard-data` | Obtenir toutes les données nécessaires pour le dashboard d'historique | `api/execution_history.py` |
| GET | `/api/execution/history/export/sessions` | Exporter l'historique des sessions en CSV | `api/execution_history.py` |
| GET | `/api/execution/history/performance` | Obtenir les métriques de performance sur une période | `api/execution_history.py` |
| POST | `/api/execution/history/record` | Enregistrer une nouvelle session d'exécution (usage interne) | `api/execution_history.py` |
| GET | `/api/execution/history/sessions` | Obtenir l'historique des sessions d'exécution | `api/execution_history.py` |
| GET | `/api/execution/history/sessions/{session_id}` | Obtenir les détails complets d'une session | `api/execution_history.py` |
| GET | `/api/execution/history/statistics` | Obtenir les statistiques générales d'exécution | `api/execution_history.py` |
| GET | `/api/execution/history/trends` | Analyser les tendances d'exécution | `api/execution_history.py` |
| GET | `/api/execution/market-data` | Données de marché pour les symboles surveillés | `api/execution_dashboard.py` |
| POST | `/api/execution/orders/execute` | Exécuter des ordres avec monitoring en temps réel | `api/execution_dashboard.py` |
| GET | `/api/execution/orders/recent` | Obtenir les ordres récents avec détails | `api/execution_dashboard.py` |
| GET | `/api/execution/statistics/summary` | Résumé des statistiques d'exécution | `api/execution_dashboard.py` |
| GET | `/api/execution/status` | Statut général du dashboard d'exécution | `api/execution_dashboard.py` |
| POST | `/api/execution/test-connection/{exchange_name}` | Tester la connexion à un exchange spécifique | `api/execution_dashboard.py` |
| POST | `/api/intelligence/demo/simulate-decision-flow` | Simuler un flux complet de décision avec explication et intervention humaine | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/explain/alert` | Générer une explication pour une alerte de risque | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/explain/counterfactual` | Générer une explication contrefactuelle | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/explain/decision` | Générer une explication pour une décision ML | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/explain/decision-mock` | Endpoint mock pour tester le frontend sans dépendances XAI | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/explain/decision-simple` | Test endpoint - Générer une explication avec structure simplifiée | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/explain/history` | Récupérer l'historique des explications | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/explain/test` | Test rapide du moteur d'IA explicable | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/feedback/submit` | Soumettre un feedback sur une décision | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/human/dashboard-stats` | Statistiques pour le dashboard human-in-the-loop | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/human/decision-history` | Récupérer l'historique des décisions | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/human/pending-decisions` | Récupérer les décisions en attente | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/human/provide-decision/{request_id}` | Fournir une décision humaine | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/human/request-decision` | Demander une intervention humaine pour une décision | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/human/wait-for-decision/{request_id}` | Attendre une décision humaine (avec polling) | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/learning/feature-status` | Status d'apprentissage par feature | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/learning/generate-improvements` | Générer des suggestions d'amélioration de modèle | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/learning/insights` | Récupérer les insights d'apprentissage | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/learning/metrics` | Métriques d'apprentissage | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/learning/performance-trends` | Tendances de performance | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/learning/suggestions` | Récupérer les suggestions d'amélioration de modèle | `api/intelligence_endpoints.py` |
| GET | `/api/intelligence/status` | Status global du système d'intelligence hybride | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/system/start` | Démarrer le système d'intelligence hybride | `api/intelligence_endpoints.py` |
| POST | `/api/intelligence/system/stop` | Arrêter le système d'intelligence hybride | `api/intelligence_endpoints.py` |
| GET | `/api/market/prices` | Récupérer les prix de marché et calculer la force relative | `api/market_endpoints.py` |
| POST | `/api/ml/cache/clear` | Vider le cache des endpoints ML | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/cache/stats` | Obtenir les statistiques détaillées du cache optimisé | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/correlation/matrix/current` | Alias routed to risk correlation endpoint logic. | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/debug/pipeline-info` | Endpoint de debug pour analyser les instances du pipeline manager | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/memory/optimize` | Optimiser l'utilisation mémoire des modèles ML | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/metrics/{model_name}` | Obtenir les métriques pour un modèle spécifique | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/metrics/{model_name}/update` | Mettre à jour les métriques d'un modèle (version spécifique) | `api/unified_ml_endpoints.py` |
| DELETE | `/api/ml/models/clear-all` | Décharger tous les modèles de la mémoire | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/models/load-regime` | Charger le modèle de détection de régime | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/models/load-volatility` | Charger les modèles de volatilité | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/models/loaded` | Obtenir la liste des modèles actuellement chargés | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/models/loading-status` | Obtenir le statut de chargement en temps réel des modèles | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/models/preload` | Précharger des modèles prioritaires (BTC, ETH par défaut) | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/models/status` | Alias of /api/ml/status for legacy front-ends. | `api/unified_ml_endpoints.py` |
| DELETE | `/api/ml/models/{model_key}` | Décharger un modèle spécifique de la mémoire | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/models/{model_key}/info` | Obtenir les informations détaillées d'un modèle chargé | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/monitoring/health` | Obtenir l'état de santé global du système ML | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/performance/summary` | Obtenir un résumé des performances des modèles | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/pipeline/test` |  | `api/main.py` |
| GET | `/api/ml/portfolio-metrics` | Obtenir les métriques de portefeuille ML (stub endpoint) | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/predict` | Prédictions ML unifiées - volatilité, régime, corrélations | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/predictions/live` | Obtenir les prédictions en temps réel basées sur les modèles entraînés | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/regime/current` | Alias that returns current/live regime signal. | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/regime/train` | Alias that loads the regime model. | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/registry/models` | Lister les modèles enregistrés dans le registry | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/registry/models/{model_name}` | Obtenir les informations détaillées d'un modèle | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/registry/models/{model_name}/versions` | Obtenir toutes les versions d'un modèle depuis le registry | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/registry/models/{model_name}/versions/{version}/metrics` | Mettre à jour les métriques de performance d'un modèle | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/registry/models/{model_name}/versions/{version}/status` | Mettre à jour le statut d'un modèle | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/sentiment/analyze` | Alias that aggregates sentiment for multiple symbols. | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/sentiment/fear-greed` | Obtenir Fear & Greed index (stub endpoint) | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/sentiment/symbol/{symbol}` | Get sentiment analysis for a cryptocurrency symbol | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/sentiment/{symbol}` | Obtenir le sentiment pour un asset (stub endpoint) | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/status` | Obtenir le statut complet du pipeline ML unifié | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/train` | Entraîner les modèles ML de manière unifiée | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/unified/predict` | Endpoint unifié de prédiction ML avec gating et incertitude | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/unified/volatility/{symbol}` | Prédiction de volatilité avec contrat unifié | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/versions/{model_name}` | Lister les versions disponibles d'un modèle | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/volatility/batch-predict` | Alias that forwards to unified /predict. | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/volatility/models/status` | Expose a volatility-focused status for legacy widgets. | `api/unified_ml_endpoints.py` |
| GET | `/api/ml/volatility/predict/{symbol}` | Prédiction de volatilité pour un asset spécifique | `api/unified_ml_endpoints.py` |
| POST | `/api/ml/volatility/train-portfolio` | Alias that preloads requested volatility models instead of training. | `api/unified_ml_endpoints.py` |
| GET | `/api/monitoring/alerts` | Obtenir les alertes avec filtres | `api/monitoring_advanced.py` |
| POST | `/api/monitoring/alerts/test` | Déclencher une alerte de test | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/analytics/performance` | Analytics de performance agrégées | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/analytics/trends` | Analysis des tendances de performance | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/health` | Vue d'ensemble de la santé du système | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/metrics/{exchange}` | Métriques détaillées pour un exchange spécifique | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/monitoring/config` | Configuration actuelle du monitoring | `api/monitoring_advanced.py` |
| PUT | `/api/monitoring/monitoring/config` | Mettre à jour la configuration du monitoring | `api/monitoring_advanced.py` |
| POST | `/api/monitoring/monitoring/restart` | Redémarrer le monitoring | `api/monitoring_advanced.py` |
| POST | `/api/monitoring/notifications/config` | Ajouter ou mettre à jour une configuration de notification | `api/monitoring_advanced.py` |
| DELETE | `/api/monitoring/notifications/config/{channel_type}` | Supprimer une configuration de notification | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/notifications/status` | Obtenir le statut des notifications | `api/monitoring_advanced.py` |
| POST | `/api/monitoring/start` | Démarrer le service de monitoring | `api/monitoring_advanced.py` |
| GET | `/api/monitoring/status/detailed` | Statut détaillé avec métriques complètes | `api/monitoring_advanced.py` |
| POST | `/api/monitoring/stop` | Arrêter le service de monitoring | `api/monitoring_advanced.py` |
| POST | `/api/multi-asset/allocation/suggest` | Get suggested asset allocation based on risk profile and investment horizon | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/asset-classes` | Get all supported asset classes | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/assets` | Get available assets, optionally filtered by class, region, or sector | `api/multi_asset_endpoints.py` |
| POST | `/api/multi-asset/assets` | Add a new asset to the universe | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/correlation` | Calculate correlation matrix across multiple asset classes | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/diversification-score` | Calculate portfolio diversification score across asset classes | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/performance-analysis` | Analyze performance metrics by asset class | `api/multi_asset_endpoints.py` |
| GET | `/api/multi-asset/prices` | Get price data for multiple assets across different classes | `api/multi_asset_endpoints.py` |
| POST | `/api/performance/cache/clear` | Clear optimization cache | `api/performance_endpoints.py` |
| GET | `/api/performance/cache/stats` | Get cache statistics and memory usage | `api/performance_endpoints.py` |
| GET | `/api/performance/optimization/benchmark` | Benchmark different optimization methods for performance comparison | `api/performance_endpoints.py` |
| POST | `/api/performance/optimization/precompute` | Precompute optimization matrices for faster subsequent optimizations | `api/performance_endpoints.py` |
| GET | `/api/performance/system/memory` | Get current system memory usage | `api/performance_endpoints.py` |
| POST | `/api/phase3/decision/process` | Process a decision using all Phase 3 components in orchestrated fashion | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/health/alerts` | Get active health alerts for all Phase 3 components | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/health/component/{component_name}` | Get detailed health status of a specific Phase 3 component | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/health/comprehensive` | Get comprehensive health status of all Phase 3 components | `api/unified_phase3_endpoints.py` |
| POST | `/api/phase3/health/initialize-monitoring` | Initialize comprehensive Phase 3 health monitoring | `api/unified_phase3_endpoints.py` |
| POST | `/api/phase3/intelligence/explain-decision` | Mock endpoint pour tester les explications d'IA | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/intelligence/human-decisions` | Get pending human-in-the-loop decisions | `api/unified_phase3_endpoints.py` |
| POST | `/api/phase3/intelligence/submit-human-feedback` | Submit human feedback for a pending decision | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/learning/insights` | Get insights from feedback learning system | `api/unified_phase3_endpoints.py` |
| POST | `/api/phase3/orchestrate/full-workflow` | Execute complete Phase 3A/3B/3C workflow with all components | `api/unified_phase3_endpoints.py` |
| POST | `/api/phase3/risk/comprehensive-analysis` | Perform comprehensive risk analysis using Phase 3A Advanced Risk Engine | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/status` | Get comprehensive status of all Phase 3 components | `api/unified_phase3_endpoints.py` |
| GET | `/api/phase3/streaming/active-connections` | Get information about active real-time streaming connections | `api/unified_phase3_endpoints.py` |
| GET | `/api/portfolio/alerts` | Obtenir les alertes de portefeuille | `api/portfolio_monitoring.py` |
| GET | `/api/portfolio/dashboard-summary` | Résumé complet pour le dashboard de monitoring | `api/portfolio_monitoring.py` |
| GET | `/api/portfolio/metrics` | Obtenir les métriques actuelles du portefeuille | `api/portfolio_monitoring.py` |
| GET | `/api/portfolio/optimization/analyze` | Analyze current portfolio and suggest optimization parameters. | `api/portfolio_optimization_endpoints.py` |
| POST | `/api/portfolio/optimization/backtest` | Backtest optimization strategy over historical periods | `api/portfolio_optimization_endpoints.py` |
| GET | `/api/portfolio/optimization/constraints/defaults` | Get default optimization constraints | `api/portfolio_optimization_endpoints.py` |
| GET | `/api/portfolio/optimization/objectives` | Get available optimization objectives | `api/portfolio_optimization_endpoints.py` |
| POST | `/api/portfolio/optimization/optimize` | Optimize portfolio allocation using advanced Markowitz optimization | `api/portfolio_optimization_endpoints.py` |
| POST | `/api/portfolio/optimization/optimize-advanced` | Advanced portfolio optimization with sophisticated algorithms: | `api/portfolio_optimization_endpoints.py` |
| GET | `/api/portfolio/performance` | Obtenir les analytics de performance | `api/portfolio_monitoring.py` |
| GET | `/api/portfolio/rebalance-history` | Obtenir l'historique des rééquilibrages | `api/portfolio_monitoring.py` |
| GET | `/api/portfolio/strategy-performance` | Analyser les performances par stratégie de rééquilibrage | `api/portfolio_monitoring.py` |
| GET | `/api/pricing/diagnostic` |  | `api/main.py` |
| GET | `/api/realtime/connections` | Statistiques détaillées des connexions WebSocket | `api/realtime_endpoints.py` |
| GET | `/api/realtime/demo` | Endpoint DEV-ONLY pour simuler un évènement. Protégé par DEBUG_SIM. | `api/realtime_endpoints.py` |
| POST | `/api/realtime/dev/simulate` | Endpoint DEV-ONLY pour simuler un évènement. Protégé par DEBUG_SIM. | `api/realtime_endpoints.py` |
| POST | `/api/realtime/start` | Démarrer le moteur de streaming (pour tests/management) | `api/realtime_endpoints.py` |
| GET | `/api/realtime/status` | Status du système de streaming temps réel | `api/realtime_endpoints.py` |
| POST | `/api/realtime/stop` | Arrêter le moteur de streaming (pour tests/management) | `api/realtime_endpoints.py` |
| GET | `/api/realtime/streams/{stream_name}/info` | Informations sur un Redis Stream spécifique | `api/realtime_endpoints.py` |
| POST | `/api/risk/advanced/attribution/analyze` | Analyse d'attribution du risque par composant | `api/advanced_risk_endpoints.py` |
| GET | `/api/risk/advanced/methods/info` | Information sur les méthodes disponibles | `api/advanced_risk_endpoints.py` |
| POST | `/api/risk/advanced/monte-carlo/simulate` | Execute simulation Monte Carlo pour scénarios extrêmes | `api/advanced_risk_endpoints.py` |
| GET | `/api/risk/advanced/scenarios/list` | Liste des scénarios de stress disponibles | `api/advanced_risk_endpoints.py` |
| POST | `/api/risk/advanced/stress-test/run` | Execute un test de stress sur le portefeuille | `api/advanced_risk_endpoints.py` |
| POST | `/api/risk/advanced/summary` | Résumé complet des métriques de risque avancées | `api/advanced_risk_endpoints.py` |
| POST | `/api/risk/advanced/var/calculate` | Calcule Value-at-Risk pour un portefeuille donné | `api/advanced_risk_endpoints.py` |
| GET | `/api/risk/alerts` | Récupère les alertes de risque actives | `api/risk_endpoints.py` |
| GET | `/api/risk/alerts/history` | Récupère l'historique des alertes | `api/risk_endpoints.py` |
| GET | `/api/risk/attribution` | Calcule l'attribution de performance détaillée du portfolio | `api/risk_endpoints.py` |
| POST | `/api/risk/backtest` | Exécute un backtest d'une stratégie d'allocation personnalisée | `api/risk_endpoints.py` |
| GET | `/api/risk/correlation` | Calcule la matrice de corrélation temps réel entre assets | `api/risk_endpoints.py` |
| GET | `/api/risk/dashboard` | Endpoint principal utilisant le vrai portfolio depuis les CSV avec le système de... | `api/risk_dashboard_endpoints.py` |
| GET | `/api/risk/metrics` | Calcule les métriques de risque complètes du portfolio | `api/risk_endpoints.py` |
| GET | `/api/risk/status` | Statut du système de gestion des risques | `api/risk_endpoints.py` |
| POST | `/api/risk/stress-test/custom` | Exécute un stress test personnalisé avec shocks définis par l'utilisateur | `api/risk_endpoints.py` |
| GET | `/api/risk/stress-test/{scenario}` | Exécute un stress test basé sur des scénarios crypto historiques | `api/risk_endpoints.py` |
| GET | `/api/saxo/accounts` |  | `api/saxo_endpoints.py` |
| POST | `/api/saxo/import` | Import Saxo CSV/XLSX and persist through the wealth adapter. | `api/saxo_endpoints.py` |
| GET | `/api/saxo/instruments` |  | `api/saxo_endpoints.py` |
| GET | `/api/saxo/portfolios` | Return lightweight overview of stored Saxo portfolios. | `api/saxo_endpoints.py` |
| GET | `/api/saxo/portfolios/{portfolio_id}` | Return full detail for a given Saxo portfolio. | `api/saxo_endpoints.py` |
| GET | `/api/saxo/positions` |  | `api/saxo_endpoints.py` |
| GET | `/api/saxo/prices` |  | `api/saxo_endpoints.py` |
| POST | `/api/saxo/rebalance/preview` |  | `api/saxo_endpoints.py` |
| GET | `/api/saxo/transactions` |  | `api/saxo_endpoints.py` |
| POST | `/api/saxo/validate` | Validate Saxo payload before ingestion | `api/saxo_endpoints.py` |
| POST | `/api/sources/import` | Importe les fichiers d'un module depuis uploads/ ou legacy vers imports/. | `api/sources_endpoints.py` |
| GET | `/api/sources/list` | Liste tous les modules de sources configurés avec leur état. | `api/sources_endpoints.py` |
| POST | `/api/sources/refresh-api` | Rafraîchit les données depuis l'API pour un module. | `api/sources_endpoints.py` |
| GET | `/api/sources/scan` | Scan détaillé des fichiers qui seraient importés pour chaque module. | `api/sources_endpoints.py` |
| POST | `/api/sources/upload` | Upload de fichiers pour un module spécifique. | `api/sources_endpoints.py` |
| GET | `/api/strategies/list` | Alias pour compatibilité front attendu (/api/strategies/list). | `api/main.py` |
| GET | `/api/strategies/{strategy_id}` | Alias pour compatibilité front attendu (/api/strategies/{id}). | `api/main.py` |
| GET | `/api/strategy/admin/templates/{template_id}/weights` | Retourne les poids détaillés d'un template (admin) | `api/strategy_endpoints.py` |
| POST | `/api/strategy/compare` | Compare plusieurs templates côte à côte | `api/strategy_endpoints.py` |
| GET | `/api/strategy/current` | Retourne l'état stratégie courante (cache autorisé) | `api/strategy_endpoints.py` |
| GET | `/api/strategy/health` | Health check du Strategy Registry | `api/strategy_endpoints.py` |
| POST | `/api/strategy/preview` | Génère une preview d'allocation selon le template | `api/strategy_endpoints.py` |
| GET | `/api/strategy/templates` | Liste tous les templates de stratégie disponibles | `api/strategy_endpoints.py` |
| DELETE | `/api/users/settings` | Remet les settings utilisateur aux valeurs par défaut. | `api/user_settings_endpoints.py` |
| GET | `/api/users/settings` | Récupère les settings de l'utilisateur actuel. | `api/user_settings_endpoints.py` |
| PUT | `/api/users/settings` | Sauvegarde les settings de l'utilisateur actuel. | `api/user_settings_endpoints.py` |
| GET | `/api/users/settings/info` | Récupère des informations de debug sur les settings utilisateur. | `api/user_settings_endpoints.py` |
| GET | `/api/users/sources` | Récupère les sources de données disponibles pour l'utilisateur. | `api/user_settings_endpoints.py` |
| GET | `/api/wealth/modules` | Liste les modules wealth disponibles pour l'utilisateur. | `api/wealth_endpoints.py` |
| GET | `/api/wealth/{module}/accounts` | Liste les comptes pour un module (lecture seule depuis sources). | `api/wealth_endpoints.py` |
| GET | `/api/wealth/{module}/instruments` |  | `api/wealth_endpoints.py` |
| GET | `/api/wealth/{module}/positions` |  | `api/wealth_endpoints.py` |
| GET | `/api/wealth/{module}/prices` |  | `api/wealth_endpoints.py` |
| POST | `/api/wealth/{module}/rebalance/preview` |  | `api/wealth_endpoints.py` |
| GET | `/api/wealth/{module}/transactions` |  | `api/wealth_endpoints.py` |

## Namespace `/balances`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/balances/current` |  | `api/main.py` |

## Namespace `/csv`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/csv/cleanup` | Nettoie les anciens fichiers CSV (garde seulement les X derniers jours) | `api/csv_endpoints.py` |
| POST | `/csv/download` | [LEGACY] Télécharge un fichier CSV depuis CoinTracking - délègue vers /api/sourc... | `api/csv_endpoints.py` |
| GET | `/csv/status` | [LEGACY] Retourne le status des fichiers CSV - délègue vers /api/sources | `api/csv_endpoints.py` |

## Namespace `/debug`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/debug/api-keys` | Expose les clés API depuis .env pour auto-configuration (sécurisé) | `api/main.py` |
| POST | `/debug/api-keys` | Met à jour les clés API dans le fichier .env (sécurisé) | `api/main.py` |
| GET | `/debug/ctapi` | Endpoint de debug pour CoinTracking API | `api/main.py` |
| GET | `/debug/exchanges-snapshot` | Simple health check endpoint for containers | `api/main.py` |
| GET | `/debug/paths` | Endpoint de diagnostic pour vérifier les chemins | `api/main.py` |

## Namespace `/execution`

| Method | Path | Summary | File |
|---|---|---|---|
| POST | `/execution/cancel/{plan_id}` | Annuler l'exécution d'un plan | `api/execution_endpoints.py` |
| GET | `/execution/exchanges` | Lister les exchanges disponibles | `api/execution_endpoints.py` |
| POST | `/execution/exchanges/connect` | Connecter tous les exchanges configurés | `api/execution_endpoints.py` |
| POST | `/execution/execute-plan` | Exécuter un plan de rebalancement | `api/execution_endpoints.py` |
| POST | `/execution/governance/activate/{plan_id}` | Activer un plan APPROVED → ACTIVE | `api/execution_endpoints.py` |
| POST | `/execution/governance/apply_policy` | Applique une policy sans creer de plan (respecte cooldown) - NOUVEAU | `api/execution_endpoints.py` |
| POST | `/execution/governance/approve/{resource_id}` | Endpoint unifié pour approuver/rejeter des décisions ou des plans | `api/execution_endpoints.py` |
| POST | `/execution/governance/cancel/{plan_id}` | Annuler un plan ANY_STATE → CANCELLED | `api/execution_endpoints.py` |
| GET | `/execution/governance/cooldown-status` | Vérifier le statut du cooldown de publication des plans | `api/execution_endpoints.py` |
| GET | `/execution/governance/decisions` | Lister les décisions de gouvernance | `api/execution_endpoints.py` |
| POST | `/execution/governance/execute/{plan_id}` | Marquer un plan comme exécuté ACTIVE → EXECUTED | `api/execution_endpoints.py` |
| POST | `/execution/governance/freeze` | Freeze le système avec TTL et auto-restore - ÉTENDU | `api/execution_endpoints.py` |
| POST | `/execution/governance/init-ml` | Force l'initialisation des modèles ML pour la gouvernance | `api/execution_endpoints.py` |
| POST | `/execution/governance/mode` | Changer le mode de gouvernance | `api/execution_endpoints.py` |
| POST | `/execution/governance/propose` | Proposer une nouvelle décision avec respect du cooldown | `api/execution_endpoints.py` |
| POST | `/execution/governance/review/{plan_id}` | Review un plan DRAFT → REVIEWED with ETag-based concurrency control | `api/execution_endpoints.py` |
| GET | `/execution/governance/signals` | Obtenir les signaux ML actuels | `api/execution_endpoints.py` |
| POST | `/execution/governance/signals/recompute` | Recompute blended score server-side from components and attach to governance sig... | `api/execution_endpoints.py` |
| POST | `/execution/governance/signals/update` | Mettre à jour des champs de signaux ML maintenus côté gouvernance. | `api/execution_endpoints.py` |
| GET | `/execution/governance/state` | Obtenir l'état actuel du système de gouvernance - VERSION UNIFIÉE | `api/execution_endpoints.py` |
| POST | `/execution/governance/unfreeze` | Dégeler le système de gouvernance | `api/execution_endpoints.py` |
| POST | `/execution/governance/validate-allocation` | Valide un changement d'allocation avant exécution | `api/execution_endpoints.py` |
| GET | `/execution/orders/{plan_id}` | Obtenir la liste détaillée des ordres d'un plan | `api/execution_endpoints.py` |
| GET | `/execution/pipeline-status` | Obtenir le statut global du pipeline d'exécution | `api/execution_endpoints.py` |
| GET | `/execution/plans` | Lister les plans d'exécution | `api/execution_endpoints.py` |
| GET | `/execution/status/{plan_id}` | Obtenir le statut d'exécution d'un plan | `api/execution_endpoints.py` |
| POST | `/execution/validate-plan` | Valider un plan d'exécution avant lancement | `api/execution_endpoints.py` |

## Namespace `/favicon.ico`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/favicon.ico` | Serve a tiny placeholder favicon to avoid 404s in the browser console. | `api/main.py` |

## Namespace `/health`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/health` | Simple health check endpoint for containers | `api/main.py` |
| GET | `/health/detailed` | Endpoint de santé détaillé avec métriques complètes | `api/main.py` |

## Namespace `/healthz`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/healthz` | Serve a tiny placeholder favicon to avoid 404s in the browser console. | `api/main.py` |

## Namespace `/kraken`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/kraken/balance` | Obtenir les soldes du compte Kraken (nécessite credentials) | `api/kraken_endpoints.py` |
| GET | `/kraken/pairs` | Obtenir les paires de trading Kraken disponibles | `api/kraken_endpoints.py` |
| GET | `/kraken/prices` | Obtenir les prix Kraken pour des symboles spécifiques | `api/kraken_endpoints.py` |
| GET | `/kraken/status` | Obtenir le statut de l'intégration Kraken | `api/kraken_endpoints.py` |
| GET | `/kraken/system-info` | Obtenir les informations système Kraken | `api/kraken_endpoints.py` |
| GET | `/kraken/test-connection` | Test de connexion Kraken complet | `api/kraken_endpoints.py` |
| POST | `/kraken/validate-order` | Valider un ordre Kraken sans l'exécuter | `api/kraken_endpoints.py` |

## Namespace `/portfolio`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/portfolio/alerts` | Calcule les alertes de dérive du portfolio par rapport aux targets. | `api/portfolio_endpoints.py` |
| GET | `/portfolio/breakdown-locations` | Renvoie la répartition par exchange à partir de la CT-API. | `api/main.py` |
| GET | `/portfolio/metrics` | Métriques calculées du portfolio avec P&L configurable. | `api/portfolio_endpoints.py` |
| POST | `/portfolio/snapshot` | Sauvegarde un snapshot du portfolio pour suivi historique | `api/portfolio_endpoints.py` |
| GET | `/portfolio/trend` | Données de tendance du portfolio pour graphiques | `api/portfolio_endpoints.py` |

## Namespace `/pricing`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/pricing/diagnostic` | Diagnostique la source de prix retenue par symbole selon la logique actuelle. | `api/main.py` |

## Namespace `/proxy`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/proxy/fred/bitcoin` | Proxy pour récupérer les données Bitcoin historiques via FRED API (user-scoped) | `api/main.py` |

## Namespace `/rebalance`

| Method | Path | Summary | File |
|---|---|---|---|
| POST | `/rebalance/plan` |  | `api/main.py` |
| POST | `/rebalance/plan.csv` |  | `api/main.py` |

## Namespace `/schema`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/schema` | Fallback endpoint to expose OpenAPI schema if /openapi.json isn't reachable in y... | `api/main.py` |

## Namespace `/strategies`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/strategies/list` | Liste des stratégies de rebalancing prédéfinies avec cache ETag | `api/main.py` |
| GET | `/strategies/{strategy_id}` | Détails d'une stratégie spécifique | `api/main.py` |

## Namespace `/taxonomy`

| Method | Path | Summary | File |
|---|---|---|---|
| POST | `/taxonomy/aliases` | Upsert d'aliases (bulk ou unitaire). | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/aliases/bulk` | Retourne des suggestions de classification automatique pour les symboles inconnu... | `api/taxonomy_endpoints.py` |
| DELETE | `/taxonomy/aliases/{alias}` | Retourne des suggestions de classification automatique pour les symboles inconnu... | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/auto-classify` | Applique automatiquement la classification suggérée aux symboles inconnus. | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/auto-classify-enhanced` | Version améliorée de l'auto-classification avec support CoinGecko | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/cache/clear` | Vide le cache de classification (maintenance) | `api/smart_taxonomy_endpoints.py` |
| POST | `/taxonomy/classify` | Classification intelligente de symboles avec scoring de confiance | `api/smart_taxonomy_endpoints.py` |
| GET | `/taxonomy/coingecko-stats` | Statistiques sur le service CoinGecko | `api/taxonomy_endpoints.py` |
| GET | `/taxonomy/duplicates` | Détection de doublons et dérivés dans un portfolio | `api/smart_taxonomy_endpoints.py` |
| POST | `/taxonomy/enrich-from-coingecko` | Enrichit directement des symboles via CoinGecko sans les patterns regex | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/learn` | API d'apprentissage - Feedback humain pour améliorer la classification | `api/smart_taxonomy_endpoints.py` |
| GET | `/taxonomy/stats` | Statistiques du système de classification intelligente | `api/smart_taxonomy_endpoints.py` |
| GET | `/taxonomy/suggest-improvements` | Suggestions d'améliorations pour la taxonomie basées sur l'analyse des classific... | `api/smart_taxonomy_endpoints.py` |
| GET | `/taxonomy/suggestions` | Retourne des suggestions de classification automatique pour les symboles inconnu... | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/suggestions` | Retourne des suggestions de classification automatique pour les symboles inconnu... | `api/taxonomy_endpoints.py` |
| POST | `/taxonomy/suggestions-enhanced` | Version améliorée des suggestions avec support CoinGecko | `api/taxonomy_endpoints.py` |
| GET | `/taxonomy/test-coingecko-api` | Test direct de l'API CoinGecko avec une clé fournie. | `api/taxonomy_endpoints.py` |

## Namespace `/test-simple`

| Method | Path | Summary | File |
|---|---|---|---|
| GET | `/test-simple` | Endpoint de santé détaillé avec métriques complètes | `api/main.py` |
