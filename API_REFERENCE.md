# API Reference - Crypto Rebalancer

## 🚀 API Overview

Le Crypto Rebalancer expose une API REST complète avec plus de 50 endpoints couvrant le portfolio management, le rebalancing, le risk management, l'exécution de trades et l'analytics avancée.

**Base URL:** `http://127.0.0.1:8000`  
**Documentation Interactive:** `http://127.0.0.1:8000/docs`

## 📋 Table des matières

- [Authentication](#-authentication)
- [Core Portfolio APIs](#-core-portfolio-apis)
- [Rebalancing APIs](#-rebalancing-apis)
- [Risk Management APIs](#-risk-management-apis)
- [Trading & Execution APIs](#-trading--execution-apis)
- [Analytics APIs](#-analytics-apis)
- [Monitoring APIs](#-monitoring-apis)
- [Configuration APIs](#-configuration-apis)
- [Utility APIs](#-utility-apis)
- [Error Handling](#-error-handling)

---

## 🔐 Authentication

**Statut actuel:** Aucune authentication requise (développement local)  
**Production:** À implémenter (API Keys, JWT, ou OAuth2)

```bash
# Headers recommandés
Content-Type: application/json
Accept: application/json
User-Agent: crypto-rebalancer/1.0
```

---

## 💼 Core Portfolio APIs

### GET /balances/current

Récupère les balances actuelles du portfolio.

#### Paramètres Query

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `source` | string | `cointracking` | Source des données: `cointracking`, `cointracking_api`, `stub` |
| `min_usd` | float | `1.0` | Valeur minimum en USD pour filtrer les positions |

#### Exemple de Requête

```bash
curl "http://127.0.0.1:8000/balances/current?source=cointracking_api&min_usd=10"
```

#### Réponse

```json
{
  "source_used": "cointracking_api",
  "total_value_usd": 453041.15,
  "items": [
    {
      "symbol": "BTC",
      "amount": 1.5,
      "value_usd": 67500.00,
      "location": "Kraken",
      "price_usd": 45000.00,
      "alias": "BTC",
      "group": "BTC"
    },
    {
      "symbol": "ETH", 
      "amount": 25.5,
      "value_usd": 63750.00,
      "location": "Binance",
      "price_usd": 2500.00,
      "alias": "ETH",
      "group": "ETH"
    }
  ]
}
```

### GET /portfolio/breakdown-locations

Obtient la répartition du portfolio par exchange/location.

#### Exemple de Requête

```bash
curl "http://127.0.0.1:8000/portfolio/breakdown-locations?source=cointracking&min_usd=1"
```

#### Réponse

```json
{
  "breakdown": {
    "total_value_usd": 453041.15,
    "location_count": 8,
    "locations": [
      {
        "location": "Ledger Wallets",
        "total_value_usd": 302839.23,
        "asset_count": 35,
        "percentage": 66.8
      },
      {
        "location": "Kraken", 
        "total_value_usd": 67500.00,
        "asset_count": 12,
        "percentage": 14.9
      }
    ]
  }
}
```

### GET /portfolio/metrics

Calcule les métriques avancées du portfolio.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `source` | string | Source des données portfolio |
| `benchmark` | string | Benchmark de comparaison (défaut: "BTC") |

#### Réponse

```json
{
  "total_value_usd": 453041.15,
  "asset_count": 47,
  "diversification_score": 0.73,
  "top_5_concentration": 0.68,
  "risk_score": 42,
  "recommendations": [
    "Consider reducing BTC concentration (currently 32%)",
    "Increase stablecoin allocation for volatility buffer"
  ]
}
```

---

## ⚖️ Rebalancing APIs

### POST /rebalance/plan

Génère un plan de rebalancement complet.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `source` | string | Source des données |
| `min_usd` | float | Filtrage minimum |
| `dynamic_targets` | boolean | Utilise les cibles dynamiques si disponibles |
| `pricing` | string | Mode de pricing: `local`, `hybrid`, `auto` |

#### Body Request

```json
{
  "group_targets_pct": {
    "BTC": 35,
    "ETH": 25,
    "Stablecoins": 15,
    "SOL": 10,
    "L1/L0 majors": 10,
    "Others": 5
  },
  "dynamic_targets_pct": {
    "BTC": 45,
    "ETH": 20,
    "Stablecoins": 15,
    "SOL": 12,
    "Others": 8
  },
  "primary_symbols": {
    "BTC": ["BTC", "TBTC", "WBTC"],
    "ETH": ["ETH", "WSTETH", "STETH", "RETH", "WETH"],
    "SOL": ["SOL", "JUPSOL", "JITOSOL"]
  },
  "sub_allocation": "proportional",
  "min_trade_usd": 25
}
```

#### Exemple de Requête

```bash
curl -X POST "http://127.0.0.1:8000/rebalance/plan?source=cointracking_api&dynamic_targets=true&pricing=hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "group_targets_pct": {"BTC": 40, "ETH": 30, "Others": 30},
    "min_trade_usd": 50
  }'
```

#### Réponse

```json
{
  "total_usd": 453041.15,
  "target_weights_pct": {
    "BTC": 40,
    "ETH": 30,
    "Others": 30
  },
  "current_weights_pct": {
    "BTC": 32.5,
    "ETH": 28.1,
    "Others": 39.4
  },
  "deltas_by_group_usd": {
    "BTC": 33928.09,
    "ETH": 8591.17,
    "Others": -42519.26
  },
  "actions": [
    {
      "group": "Others",
      "alias": "LINK",
      "symbol": "LINK",
      "action": "sell",
      "usd": -5000.00,
      "est_quantity": 312.5,
      "price_used": 16.00,
      "location": "Binance",
      "exec_hint": "Sell on Binance"
    },
    {
      "group": "BTC",
      "alias": "BTC", 
      "symbol": "BTC",
      "action": "buy",
      "usd": 33928.09,
      "est_quantity": 0.754,
      "price_used": 45000.00,
      "location": "Kraken",
      "exec_hint": "Buy on Kraken"
    }
  ],
  "unknown_aliases": ["NEWCOIN", "TESTTOKEN"],
  "meta": {
    "source_used": "cointracking_api",
    "pricing_mode": "hybrid",
    "plan_generated_at": "2024-08-24T10:30:00Z",
    "dynamic_targets_active": true,
    "ccs_score": 0.78
  }
}
```

### GET /api/portfolio/metrics

Métriques consolidées du portefeuille (monitoring synthétique).

### GET /api/portfolio/alerts

Alertes de portefeuille dérivées des déviations d'allocation et métriques.

### POST /rebalance/plan.csv

Génère et télécharge le plan au format CSV.

#### Paramètres

Identiques à `/rebalance/plan` mais retourne un fichier CSV.

#### Exemple de Requête

```bash
curl -X POST "http://127.0.0.1:8000/rebalance/plan.csv?source=cointracking_api" \
  -H "Content-Type: application/json" \
  -d '{"group_targets_pct": {"BTC": 50, "ETH": 50}}' \
  -o rebalance_plan.csv
```

#### Format CSV

```csv
group,alias,symbol,action,usd,est_quantity,price_used,location,exec_hint
BTC,BTC,BTC,buy,15000.00,0.333,45000.00,Kraken,Buy on Kraken
ETH,ETH,ETH,sell,-8500.00,3.4,2500.00,Binance,Sell on Binance
```

---

## 🛡️ Risk Management APIs

### GET /api/risk/metrics

Calcule les métriques de risque avancées.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `period_days` | int | Période d'analyse (défaut: 30) |
| `confidence_level` | float | Niveau de confiance pour VaR (défaut: 0.95) |

#### Réponse

```json
{
  "portfolio_metrics": {
    "total_value_usd": 453041.15,
    "volatility_30d": 0.045,
    "var_95": -0.089,
    "cvar_95": -0.134,
    "sharpe_ratio": 1.23,
    "sortino_ratio": 1.67,
    "max_drawdown": -0.23,
    "calmar_ratio": 0.87
  },
  "risk_score": 42,
  "risk_level": "Moderate",
  "last_updated": "2024-08-24T10:30:00Z"
}
```

### GET /api/risk/correlation

Analyse de corrélation entre les actifs du portfolio.

#### Réponse

```json
{
  "correlation_matrix": {
    "BTC": {"BTC": 1.0, "ETH": 0.73, "SOL": 0.68},
    "ETH": {"BTC": 0.73, "ETH": 1.0, "SOL": 0.71},
    "SOL": {"BTC": 0.68, "ETH": 0.71, "SOL": 1.0}
  },
  "pca_analysis": {
    "explained_variance": [0.68, 0.23, 0.09],
    "components": 3,
    "diversification_score": 0.73
  },
  "high_correlations": [
    {"asset1": "ETH", "asset2": "SOL", "correlation": 0.71}
  ]
}
```

### GET /api/risk/stress-test

Effectue des tests de stress sur le portfolio.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `scenario` | string | Scénario: `covid2020`, `bear2018`, `luna2022`, `all` |

#### Réponse

```json
{
  "scenarios": {
    "covid2020": {
      "name": "COVID-19 Crash (March 2020)",
      "portfolio_impact": -0.52,
      "duration_days": 30,
      "recovery_days": 120,
      "worst_assets": [
        {"symbol": "ETH", "impact": -0.67},
        {"symbol": "SOL", "impact": -0.71}
      ]
    },
    "bear2018": {
      "name": "Bear Market 2018",
      "portfolio_impact": -0.78,
      "duration_days": 365,
      "recovery_days": 730
    }
  },
  "summary": {
    "worst_case_scenario": "bear2018",
    "average_impact": -0.61,
    "resilience_score": 0.34
  }
}
```

---

## 🚀 Trading & Execution APIs

### POST /execution/validate-plan

Valide un plan de rebalancement avant exécution.

#### Body Request

```json
{
  "plan": {
    "actions": [
      {
        "symbol": "BTC",
        "action": "buy", 
        "usd": 1000,
        "location": "kraken"
      }
    ]
  },
  "safety_checks": true,
  "dry_run": true
}
```

#### Réponse

```json
{
  "validation_result": {
    "is_valid": true,
    "warnings": [
      "Large trade size detected for BTC (>$10,000)"
    ],
    "errors": [],
    "estimated_fees": 25.50,
    "estimated_slippage": 0.002
  }
}
```

### POST /execution/execute-plan

Exécute un plan de rebalancement validé.

#### Body Request

```json
{
  "plan_id": "abc123",
  "execution_mode": "simulation",
  "max_slippage": 0.005,
  "timeout_minutes": 30
}
```

#### Réponse

```json
{
  "execution_id": "exec_456",
  "status": "completed",
  "results": {
    "successful_trades": 8,
    "failed_trades": 0,
    "total_fees_usd": 127.45,
    "total_slippage": 0.0023,
    "execution_time_seconds": 45
  },
  "trade_results": [
    {
      "symbol": "BTC",
      "action": "buy",
      "requested_usd": 1000,
      "executed_usd": 998.50,
      "quantity": 0.0222,
      "fee_usd": 2.50,
      "status": "filled"
    }
  ]
}
```

### GET /execution/status/{execution_id}

Suit le statut d'une exécution en cours.

#### Réponse

```json
{
  "execution_id": "exec_456",
  "status": "in_progress",
  "progress": {
    "completed_trades": 3,
    "total_trades": 8,
    "percentage": 37.5
  },
  "current_trade": {
    "symbol": "ETH",
    "action": "sell",
    "status": "pending"
  },
  "estimated_completion": "2024-08-24T10:45:00Z"
}
```

---

## 📊 Analytics APIs

### GET /analytics/performance/summary

Résumé de performance du portfolio sur une période donnée.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `days_back` | int | Période d'analyse en jours |

#### Réponse

```json
{
  "total_return": 0.234,
  "annualized_return": 0.187,
  "volatility": 0.045,
  "sharpe_ratio": 1.23,
  "max_drawdown": -0.23,
  "generated_at": "2024-08-24T10:30:00Z"
}
```

### GET /analytics/performance/detailed

Analyse détaillée des performances (impact des rebalancements, attribution, recommandations).

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `days_back` | int | Période d'analyse en jours |

### GET /analytics/sessions

Liste des sessions de rebalancement récentes (historique).

#### Réponse

```json
{
  "rebalancing_history": [
    {
      "date": "2024-08-20T14:30:00Z",
      "total_value_before": 420000,
      "total_value_after": 425000,
      "trades_count": 12,
      "fees_total": 156.78,
      "performance_impact": 0.0119
    }
  ],
  "summary": {
    "total_rebalances": 15,
    "average_improvement": 0.023,
    "total_fees_paid": 2450.67,
    "best_rebalance_date": "2024-07-15T10:00:00Z"
  }
}
```

---

## 🔍 Monitoring APIs

### GET /api/monitoring/health

Status général du système et connexions.

#### Réponse

```json
{
  "status": "healthy",
  "timestamp": "2024-08-24T10:30:00Z",
  "services": {
    "cointracking_api": {
      "status": "healthy",
      "response_time_ms": 245,
      "last_check": "2024-08-24T10:29:30Z"
    },
    "coingecko_api": {
      "status": "healthy", 
      "response_time_ms": 156,
      "last_check": "2024-08-24T10:29:45Z"
    },
    "kraken_api": {
      "status": "degraded",
      "response_time_ms": 1200,
      "last_error": "High latency detected"
    }
  },
  "system_metrics": {
    "cpu_usage": 0.23,
    "memory_usage": 0.45,
    "disk_usage": 0.12
  }
}
```

### GET /api/monitoring/alerts

### GET /monitoring/alerts

Endpoints de monitoring de base (non préfixés) pour gérer les alertes du pipeline.

```
GET /monitoring/alerts
```

Paramètres facultatifs: `level`, `alert_type`, `unresolved_only`, `limit`.

Alertes actives du système.

#### Réponse

```json
{
  "active_alerts": [
    {
      "id": "alert_001",
      "severity": "warning",
      "type": "api_latency",
      "message": "Kraken API response time above threshold",
      "timestamp": "2024-08-24T10:25:00Z",
      "details": {
        "service": "kraken_api",
        "threshold_ms": 1000,
        "actual_ms": 1200
      }
    }
  ],
  "alert_summary": {
    "critical": 0,
    "warning": 1,
    "info": 2,
    "total": 3
  }
}
```

---

## ⚙️ Configuration APIs

### GET /debug/api-keys

Récupère les clés API configurées (masquées).

#### Réponse

```json
{
  "keys": {
    "cointracking": {
      "api_key_configured": true,
      "api_key_length": 32,
      "api_secret_configured": true,
      "api_secret_length": 64
    },
    "coingecko": {
      "api_key_configured": false
    }
  },
  "config_source": ".env file"
}
```

### POST /debug/api-keys

Met à jour les clés API dans le fichier .env.

#### Body Request

```json
{
  "cointracking_api_key": "new_key_here",
  "cointracking_api_secret": "new_secret_here",
  "coingecko_api_key": "optional_coingecko_key"
}
```

#### Réponse

```json
{
  "updated_keys": ["cointracking_api_key", "cointracking_api_secret"],
  "status": "success",
  "requires_restart": false
}
```

---

## 🏷️ Taxonomy APIs

### GET /taxonomy

Récupère la taxonomie complète (aliases et groupes).

#### Réponse

```json
{
  "aliases": {
    "WBTC": "BTC",
    "TBTC": "BTC", 
    "WETH": "ETH",
    "USDC": "Stablecoins",
    "USDT": "Stablecoins"
  },
  "groups": {
    "BTC": ["BTC", "WBTC", "TBTC"],
    "ETH": ["ETH", "WETH", "STETH"],
    "Stablecoins": ["USDC", "USDT", "DAI"]
  },
  "stats": {
    "total_aliases": 127,
    "total_groups": 11,
    "coverage_percentage": 89.5
  }
}
```

### GET /taxonomy/unknown_aliases

Identifie les symboles non classifiés dans un portfolio.

#### Paramètres Query

| Paramètre | Type | Description |
|-----------|------|-------------|
| `source` | string | Source du portfolio à analyser |

#### Réponse

```json
{
  "unknown_aliases": ["NEWCOIN", "TESTTOKEN", "OBSCURE"],
  "count": 3,
  "suggestions": {
    "NEWCOIN": {
      "suggested_group": "Others",
      "confidence": 0.4,
      "reason": "No matching pattern found"
    }
  }
}
```

### POST /taxonomy/aliases

Met à jour les associations alias → groupe.

#### Body Request

```json
{
  "aliases": {
    "NEWCOIN": "Others",
    "TESTTOKEN": "DeFi"
  }
}
```

#### Réponse

```json
{
  "updated_aliases": ["NEWCOIN", "TESTTOKEN"],
  "total_aliases": 129,
  "status": "success"
}
```

### POST /taxonomy/suggestions

Génère des suggestions de classification automatique.

#### Body Request

```json
{
  "sample_symbols": "DOGE,SHIB,USDT,USDC,ARB,OP,RENDER"
}
```

#### Réponse

```json
{
  "suggestions": {
    "DOGE": {
      "suggested_group": "Memecoins",
      "confidence": 0.95,
      "pattern_matched": "meme_patterns"
    },
    "USDT": {
      "suggested_group": "Stablecoins", 
      "confidence": 1.0,
      "pattern_matched": "stablecoins_patterns"
    },
    "ARB": {
      "suggested_group": "L2/Scaling",
      "confidence": 0.88,
      "pattern_matched": "l2_patterns"
    }
  },
  "accuracy_estimate": 0.89
}
```

---

## 🛠️ Utility APIs

### GET /healthz

Health check simple pour monitoring/load balancers.

#### Réponse

```json
{
  "status": "ok",
  "timestamp": "2024-08-24T10:30:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

### GET /debug/ctapi

Debug spécifique pour la connexion CoinTracking.

#### Réponse

```json
{
  "cointracking_api": {
    "configured": true,
    "api_key_length": 32,
    "api_secret_length": 64,
    "base_url": "https://cointracking.info/api/v1/",
    "last_request": "2024-08-24T10:29:30Z",
    "status": "ok"
  },
  "test_results": {
    "connection": "success",
    "authentication": "success",
    "data_fetch": "success",
    "sample_data": {
      "balance_count": 47,
      "total_value_estimate": 453041.15
    }
  }
}
```

### POST /csv/download

Télécharger un export CoinTracking dans `data/raw/` avec nom de fichier auto daté.

Body JSON:
```
{
  "file_type": "balance_by_exchange",   // ou: current_balance, coins_by_exchange
  "download_path": "data/raw/",
  "auto_name": true
}
```

---

## ❌ Error Handling

### Standard HTTP Status Codes

| Code | Signification | Usage |
|------|---------------|-------|
| 200 | OK | Requête réussie |
| 201 | Created | Ressource créée |
| 400 | Bad Request | Paramètres invalides |
| 401 | Unauthorized | Authentication requise |
| 403 | Forbidden | Accès refusé |
| 404 | Not Found | Ressource introuvable |
| 422 | Unprocessable Entity | Erreur de validation |
| 429 | Too Many Requests | Rate limit dépassé |
| 500 | Internal Server Error | Erreur serveur |
| 503 | Service Unavailable | Service temporairement indisponible |

### Format d'Erreur Standard

```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid target percentages: sum must equal 100%",
    "details": {
      "field": "group_targets_pct",
      "provided_sum": 95,
      "expected_sum": 100
    },
    "timestamp": "2024-08-24T10:30:00Z",
    "request_id": "req_abc123"
  }
}
```

### Types d'Erreurs Communes

#### Erreurs de Validation
```json
{
  "error": {
    "type": "ValidationError",
    "message": "Portfolio is empty or contains no valid items",
    "details": {
      "items_received": 0,
      "min_required": 1
    }
  }
}
```

#### Erreurs de Service Externe
```json
{
  "error": {
    "type": "ExternalServiceError",
    "message": "CoinTracking API is temporarily unavailable",
    "details": {
      "service": "cointracking",
      "status_code": 503,
      "retry_after_seconds": 300
    }
  }
}
```

#### Erreurs de Configuration
```json
{
  "error": {
    "type": "ConfigurationError", 
    "message": "CoinTracking API credentials not configured",
    "details": {
      "required_env_vars": ["CT_API_KEY", "CT_API_SECRET"],
      "missing_vars": ["CT_API_SECRET"]
    }
  }
}
```

---

## 📖 Guides d'Usage

### Workflow Typique

1. **Vérification système**
   ```bash
   curl http://127.0.0.1:8000/healthz
   ```

2. **Chargement portfolio**
   ```bash
   curl "http://127.0.0.1:8000/balances/current?source=cointracking_api"
   ```

3. **Génération plan de rebalancement**
   ```bash
   curl -X POST "http://127.0.0.1:8000/rebalance/plan" \
     -H "Content-Type: application/json" \
     -d '{"group_targets_pct": {"BTC": 40, "ETH": 30, "Others": 30}}'
   ```

4. **Validation et exécution**
   ```bash
   curl -X POST "http://127.0.0.1:8000/execution/validate-plan" \
     -H "Content-Type: application/json" \
     -d '{"plan": {...}, "dry_run": true}'
   ```

### Rate Limiting

- **Endpoints publics** : 100 requêtes/minute
- **Endpoints de trading** : 60 requêtes/minute  
- **Endpoints d'analytics** : 30 requêtes/minute

### Versioning

**Actuel:** v1 (implicite dans les URLs)  
**Futur:** `/api/v2/...` pour changements breaking

---

**📚 Cette référence API couvre l'ensemble des 50+ endpoints disponibles. Pour des exemples d'usage complets, consultez la documentation interactive à `/docs` et le USER_GUIDE.md.**
