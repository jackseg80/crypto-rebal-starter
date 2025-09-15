# Phase 2C: ML Alert Predictions System

## Vue d'ensemble

La Phase 2C introduit les **alertes prédictives basées sur Machine Learning** pour anticiper les événements de marché 24-48h à l'avance. Ce système s'appuie sur l'infrastructure d'alertes existante (Phase 2A/2B1/2B2) pour fournir des capacités d'anticipation avancées.

## Objectifs Business

- **Anticipation** : Prédire les spikes de volatilité/corrélation 24-48h avant qu'ils se produisent
- **Risk Reduction** : Permettre des ajustements proactifs de position sizing
- **Performance** : Réduire les drawdowns liés aux événements de marché soudains
- **Automation** : Intégrer les prédictions dans les règles de gouvernance automatiques

## Architecture Technique

### Components Principaux

1. **MLAlertPredictor** (`services/alerts/ml_alert_predictor.py`)
   - Feature engineering automatisé
   - Ensemble de modèles (RandomForest + GradientBoosting)
   - Support multi-horizon (4h, 12h, 24h, 48h)
   - Cache de prédictions avec TTL

2. **MLModelManager** (`services/alerts/ml_model_manager.py`)
   - Versioning automatique des modèles avec MLflow
   - A/B Testing entre versions
   - Performance monitoring et drift detection
   - Pipeline de retraining automatique

3. **AlertEngine Integration** (dans `alert_engine.py`)
   - Intégration transparente dans le workflow d'évaluation
   - Support des 4 nouveaux types d'alertes prédictives
   - Phase-aware gating pour les prédictions ML

4. **API Endpoints** (`api/ml_predictions_endpoints.py`)
   - Prédictions temps réel via REST API
   - Management des modèles et A/B tests
   - Métriques de performance et santé

## Types d'Alertes Prédictives

### 1. SPIKE_LIKELY
**Description** : Spike de corrélation probable dans les prochaines 24-48h
- **Seuils** : S2 ≥ 70%, S3 ≥ 85% de probabilité
- **Actions suggérées** : Réduction préventive des positions
- **Use case** : Anticiper les événements de contagion de marché

### 2. REGIME_CHANGE_PENDING
**Description** : Changement de régime de marché imminent
- **Seuils** : S2 ≥ 65%, S3 ≥ 80% de probabilité
- **Actions suggérées** : Préparation recalibration des paramètres
- **Use case** : Adaptation préventive aux nouvelles conditions de marché

### 3. CORRELATION_BREAKDOWN
**Description** : Décorrélation majeure des assets attendue
- **Seuils** : S2 ≥ 75%, S3 ≥ 90% de probabilité
- **Actions suggérées** : Repositionnement pour optimiser la diversification
- **Use case** : Capitaliser sur les opportunités de diversification

### 4. VOLATILITY_SPIKE_IMMINENT
**Description** : Spike de volatilité critique prédit
- **Seuils** : S2 ≥ 80%, S3 ≥ 95% de probabilité
- **Actions suggérées** : Protection maximale du capital
- **Use case** : Protection proactive contre les chocs de volatilité

## Feature Engineering

### Categories de Features

**Corrélation Features (Phase 2B2)** :
- Moyennes corrélation multi-timeframe (1h, 4h, 1d)
- Volatilité des corrélations historiques
- Trend corrélation (pente régression linéaire)
- Score de concentration systémique

**Cross-Asset Features** :
- Corrélation BTC/ETH spécifique
- Spread large-cap vs alt-coins
- Stabilité des clusters de corrélation
- Métriques de concentration

**Volatilité Features** :
- Volatilité réalisée multi-timeframe
- Vol-of-vol (volatilité de la volatilité)
- Skew de volatilité
- Momentum de volatilité

**Market Features** :
- Fear & Greed Index
- Funding rates moyens
- Sentiment composite
- Confidence du Decision Engine

**Total : 18 features** optimisées pour performance et interpretabilité

## Modèles ML

### Ensemble Architecture

**RandomForest (60% du poids)** :
- 100 arbres, profondeur max 10
- Robuste au bruit, bonne interpretabilité
- Feature importance intégrée

**GradientBoosting (40% du poids)** :
- 100 itérations, learning rate 0.1
- Capture des patterns non-linéaires complexes
- Optimisation séquentielle des erreurs

### Horizons de Prédiction

- **4h** : Ultra-court terme, high precision
- **12h** : Court terme, équilibré precision/recall
- **24h** : Moyen terme, horizon principal
- **48h** : Long terme, early warning

### Seuils de Déclenchement

Configurables par type d'alerte :
```json
{
  "SPIKE_LIKELY": 0.7,
  "REGIME_CHANGE_PENDING": 0.65,
  "CORRELATION_BREAKDOWN": 0.75,
  "VOLATILITY_SPIKE_IMMINENT": 0.8
}
```

## MLflow Integration

### Model Registry

- **Versioning automatique** avec timestamp et métadonnées
- **Tags** : stage (testing/production), alert_type, horizon
- **Métriques** : Precision, Recall, F1-Score, AUC par validation croisée
- **Artifacts** : Modèles sérialisés + scalers + config

### A/B Testing

Pipeline automatisé pour tester nouvelles versions :
1. **Challenger vs Baseline** avec split de trafic configurable
2. **Durée** : 7 jours par défaut avec arrêt anticipé si significatif
3. **Métriques** : F1-Score comme métrique principale
4. **Promotion** : Automatique du gagnant vers production

### Performance Monitoring

- **Real-time tracking** des métriques de prédiction
- **Drift detection** : Alerte si F1 drop > 10%
- **Trend analysis** : "improving", "stable", "degrading"
- **Auto-retraining** si performance sous seuil

## Configuration

### Activation (alerts_rules.json)

```json
{
  "alerting_config": {
    "ml_alert_predictor": {
      "enabled": false,  // À activer en production
      "default_horizon": "24h",
      "prediction_thresholds": {
        "SPIKE_LIKELY": 0.7,
        "REGIME_CHANGE_PENDING": 0.65,
        "CORRELATION_BREAKDOWN": 0.75,
        "VOLATILITY_SPIKE_IMMINENT": 0.8
      },
      "features": {
        "lookback_hours": 168,  // 7 jours d'historique
        "min_data_points": 50,  // Minimum pour entraînement
        "update_frequency_minutes": 15
      },
      "cache_ttl_minutes": 10,
      "model_path": "data/ml_models/alert_predictor"
    }
  }
}
```

### Alert Types Configuration

```json
{
  "alert_types": {
    "SPIKE_LIKELY": {
      "enabled": false,
      "thresholds": {"S2": 0.70, "S3": 0.85},
      "min_interval_minutes": 360,
      "rate_limit_per_day": 4
    }
    // ... autres types
  }
}
```

## API Reference

### GET /api/ml/predict

**Description** : Génère prédictions ML temps réel

**Paramètres** :
- `alert_types` : Types à prédire (optionnel)
- `horizons` : Horizons temporels (défaut: ["24h"])
- `min_probability` : Seuil minimum (défaut: 0.5)

**Response** :
```json
{
  "timestamp": "2025-09-11T14:00:00Z",
  "predictions": [
    {
      "alert_type": "SPIKE_LIKELY",
      "probability": 0.75,
      "confidence": 0.82,
      "horizon": "24h",
      "target_time": "2025-09-12T14:00:00Z",
      "severity_estimate": "S2",
      "model_version": "ensemble_v1.0_SPIKE_LIKELY_24h",
      "assets_affected": ["BTC", "ETH"]
    }
  ],
  "model_status": {"SPIKE_LIKELY_24h": "healthy"},
  "performance_summary": {
    "total_predictions": 1,
    "high_confidence": 1,
    "critical_alerts": 0,
    "avg_probability": 0.75
  }
}
```

### GET /api/ml/models/status

**Description** : Statut global des modèles ML

**Response** :
```json
{
  "timestamp": "2025-09-11T14:00:00Z",
  "total_models": 4,
  "active_models": 3,
  "model_health": {
    "SPIKE_LIKELY_24h": "healthy",
    "REGIME_CHANGE_PENDING_24h": "healthy",
    "CORRELATION_BREAKDOWN_24h": "degrading",
    "VOLATILITY_SPIKE_IMMINENT_24h": "failed"
  },
  "performance_metrics": {
    "SPIKE_LIKELY_24h": {
      "f1_score": 0.78,
      "precision": 0.82,
      "recall": 0.75,
      "auc_score": 0.85
    }
  }
}
```

### GET /api/ml/features/current

**Description** : Features actuelles utilisées pour prédictions

**Paramètres** :
- `include_raw` : Inclure données brutes (défaut: false)

**Response** :
```json
{
  "timestamp": "2025-09-11T14:00:00Z",
  "features": {
    "avg_correlation_1h": 0.65,
    "btc_eth_correlation": 0.82,
    "realized_vol_1h": 0.025,
    "market_stress": 0.4,
    // ... 18 features total
  },
  "feature_count": 18,
  "data_quality": {
    "missing_features": 0,
    "non_zero_features": 16,
    "feature_range": {"min": 0.0, "max": 1.0}
  }
}
```

### POST /api/ml/models/retrain

**Description** : Déclenche réentraînement des modèles

**Body** :
```json
{
  "alert_types": ["SPIKE_LIKELY", "REGIME_CHANGE_PENDING"],
  "force": false
}
```

## Métriques & Monitoring

### Prometheus Metrics

Nouvelles métriques Phase 2C :

```python
# Prédictions générées
crypto_rebal_ml_predictions_total{alert_type, horizon, severity}

# Performance temps réel 
crypto_rebal_ml_model_performance{model_version, metric}

# A/B Tests
crypto_rebal_ml_ab_tests_active{}
crypto_rebal_ml_ab_test_duration_hours{test_id}

# Feature quality
crypto_rebal_ml_feature_quality{feature_name}
```

### Alertes de Santé

- **Model Drift** : F1 drop > 10% vs baseline
- **Prediction Anomaly** : >90% des prédictions à même probabilité
- **Feature Missing** : >20% de features à zéro
- **A/B Test Stuck** : Test actif depuis >14 jours

## Performance Benchmarks

### Target Performance

- **Latence prédiction** : <200ms pour batch de 4 types × 4 horizons
- **F1-Score minimum** : >0.6 pour production, >0.7 pour excellent
- **Feature extraction** : <50ms
- **Memory usage** : <100MB pour cache complet

### Benchmarks Actuels

Tests sur données simulées :
- **SPIKE_LIKELY** : F1=0.72, Précision=0.78, Recall=0.67
- **REGIME_CHANGE_PENDING** : F1=0.65, Précision=0.71, Recall=0.60
- **CORRELATION_BREAKDOWN** : F1=0.58, Précision=0.62, Recall=0.55
- **VOLATILITY_SPIKE_IMMINENT** : F1=0.70, Précision=0.75, Recall=0.66

## Déploiement

### Pré-requis

```bash
pip install mlflow scikit-learn==1.3.0
```

### Activation Progressive

1. **Phase 1** : Activer `ml_alert_predictor.enabled = true`
2. **Phase 2** : Activer types d'alertes un par un dans `alert_types`
3. **Phase 3** : Monitorer performance et ajuster seuils
4. **Phase 4** : Intégrer dans gouvernance automatique

### Production Checklist

- [ ] MLflow tracking configuré avec persistance
- [ ] Model registry opérationnel  
- [ ] Métriques Prometheus actives
- [ ] Alertes de santé configurées
- [ ] A/B testing pipeline testé
- [ ] Performance benchmarks validés
- [ ] Rollback procedure documentée

## Évolutions Futures

### Phase 2C.5 - Advanced Features

- **LSTM Models** : Séries temporelles pour détection de patterns complexes
- **Ensemble Voting** : Meta-modèles combinant plusieurs approches
- **Feature Selection** : Automatique avec importance et correlation analysis
- **Multi-Asset Specific** : Modèles spécialisés par classe d'actifs

### Phase 2C.6 - Real-time Streaming

- **Kafka Integration** : Stream processing pour prédictions temps réel
- **WebSocket API** : Push notifications des prédictions
- **Event-driven** : Déclenchement automatique sur seuils de confiance
- **Edge Computing** : Modèles locaux pour latence ultra-faible

### Phase 2D - Hybrid Intelligence

- **Human-in-the-loop** : Feedback humain pour améliorer modèles
- **Explainable AI** : SHAP values pour interpretabilité complète
- **Causal Inference** : Passage de corrélation à causalité
- **Multi-modal** : Intégration sentiment analysis (news, social media)

---

## Troubleshooting

### Problèmes Courants

**Q: Prédictions toujours à 0.5 (aléatoire)**  
A: Vérifier que les modèles sont entraînés et que les features ne sont pas toutes nulles

**Q: Performance dégradée après mise à jour**  
A: Check MLflow pour compare les métriques, possiblement rollback via A/B test

**Q: Memory leak dans le predictor**  
A: Vérifier TTL des caches et limites des collections deque

**Q: A/B tests ne se terminent jamais**  
A: Check sample size minimum et durée maximale dans configuration

### Logs de Debug

Activer debug logging :
```python
logging.getLogger('services.alerts.ml_alert_predictor').setLevel(logging.DEBUG)
logging.getLogger('mlflow').setLevel(logging.INFO)
```

### Health Checks

Endpoints de santé :
- `/api/ml/models/status` : Santé globale
- `/api/ml/features/current` : Qualité des features  
- `/api/ml/ab-tests` : Status des tests

---

## Support & Contact

- **Documentation** : `/docs` (OpenAPI automatique)
- **Monitoring** : Grafana dashboards avec métriques Prometheus
- **Logs** : Centralisés avec tags `ml_predictions`, `model_version`, `alert_type`
- **Issues** : Tracker GitHub avec labels `ml`, `predictions`, `performance`