# Télémétrie & KPIs

## KPIs Système Core

### Performance API
- **p95_latency_ms** : Latence p95 endpoints API (<100ms target)
- **request_rate** : Requêtes/seconde moyennes
- **error_rate_percent** : % erreurs 5xx (<1% target)
- **cache_hit_rate** : % hits cache localStorage (<80% target)

### Données & Fraîcheur
- **stale_duration_minutes** : Durée données obsolètes (0 target)
- **data_refresh_frequency** : Fréquence actualisation sources
- **cointracking_sync_age** : Âge dernière sync CoinTracking
- **saxo_import_age** : Âge dernier import Saxo CSV

---

## KPIs Gouvernance

### Risk Management
- **portfolio_var_percent** : VaR portfolio actuel (<4% limit)
- **var_exceedances_count** : Nombre dépassements VaR journaliers
- **correlation_spike_events** : Événements corrélation >0.7
- **max_single_asset_percent** : % max single asset

### Decision Engine
- **active_cap_percent** : Cap effectif appliqué (higher = better)
- **contradiction_rate_percent** : % contradictions ML (<55% target)
- **ml_confidence_avg** : Confiance moyenne modèles ML (>0.6 target)
- **override_count_active** : Nombre overrides manuels actifs

### Alertes & Incidents
- **alerts_s1_count_24h** : Alertes info dernières 24h
- **alerts_s2_count_24h** : Alertes warning dernières 24h
- **alerts_s3_count_24h** : Alertes critiques dernières 24h (<3 target)
- **system_freeze_count** : Nombre freeze système mensuel
- **freeze_duration_minutes** : Durée cumulative freeze

---

## KPIs Exécution & Trading

### Performance Trading
- **non_executable_delta_sum_usd** : $ delta non exécutable (caps)
- **execution_cost_bp** : Coûts exécution basis points (<20bp target)
- **slippage_avg_bp** : Slippage moyen basis points
- **fill_rate_percent** : % ordres complètement remplis

### Rebalancing
- **rebalance_frequency_days** : Fréquence rebalance déclenchements
- **drift_from_target_percent** : Dérive moyenne vs targets
- **downgrade_aggressive_total** : Nombre downgrades allocations agressives
- **emergency_stop_count** : Arrêts d'urgence rebalancing

---

## KPIs ML & Intelligence

### Modèles Performance
- **model_accuracy_avg** : Précision moyenne modèles ML
- **prediction_confidence_avg** : Confiance prédictions moyennes
- **model_drift_score** : Score dérive modèles (0-1, <0.3 target)
- **feature_importance_stability** : Stabilité importance features

### Prédictions Qualité
- **volatility_prediction_mae** : MAE prédictions volatilité
- **regime_classification_f1** : F1-Score classification régimes
- **correlation_forecast_rmse** : RMSE prévision corrélations
- **sentiment_signal_accuracy** : Précision signaux sentiment

---

## Métriques Prometheus

### Configuration
```yaml
# /etc/prometheus/crypto-rebal.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'crypto-rebal'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Alerting Rules
```yaml
groups:
  - name: crypto-rebal
    rules:
      - alert: HighVaR
        expr: portfolio_var_percent > 4.0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Portfolio VaR exceeds 4%"

      - alert: MLConfidenceLow
        expr: ml_confidence_avg < 0.4
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "ML confidence below 40%"

      - alert: SystemFreeze
        expr: system_freeze_active == 1
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: "System in freeze mode"
```

---

## Dashboards Grafana

### Dashboard Principal
- **System Health** : Latence, erreurs, uptime
- **Risk Metrics** : VaR, corrélations, caps
- **ML Performance** : Confiance, précision, dérive
- **Trading Stats** : Volumes, coûts, slippage

### Dashboard Gouvernance
- **Decision Flow** : SMART → Engine → Execution
- **Caps Timeline** : Évolution caps dans le temps
- **Alertes Heatmap** : Répartition par type/sévérité
- **Override Tracking** : Suivi interventions manuelles

### Widgets Temps Réel
- **VaR Gauge** : Jauge VaR avec seuils colorés
- **ML Confidence** : Barre confiance temps réel
- **Active Alerts** : Liste alertes actives scrollable
- **System Status** : Statut global vert/orange/rouge

---

## Export & Reporting

### Rapports Automatiques
- **Daily Report** : KPIs journaliers envoyés par email
- **Weekly Summary** : Synthèse hebdomadaire performance
- **Monthly Review** : Analyse mensuelle approfondie
- **Incident Report** : Rapport automatique post-incident

### Format Export
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "period": "24h",
  "kpis": {
    "performance": {
      "p95_latency_ms": 45.2,
      "error_rate_percent": 0.1
    },
    "risk": {
      "portfolio_var_percent": 2.8,
      "var_exceedances_count": 0
    },
    "ml": {
      "confidence_avg": 0.72,
      "contradiction_rate": 0.25
    }
  }
}
```

### Webhooks Reporting
- **Discord** : Résumé quotidien KPIs critiques
- **Slack** : Alertes anomalies détectées
- **Email** : Rapport hebdomadaire stakeholders
- **API** : Push métriques vers systèmes externes