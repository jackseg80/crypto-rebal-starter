# Documentation : Mode d'Allocation Priority

## Vue d'ensemble

Le mode d'allocation **priority** est une fonctionnalité avancée qui permet de sélectionner intelligemment quoi acheter et vendre dans chaque groupe selon un scoring multi-facteurs basé sur la qualité, liquidité, et momentum des actifs.

### Concepts clés

- **Mode proportionnel** (défaut) : Répartition selon les poids existants dans le portfolio
- **Mode priority** : Sélection des Top-N actifs par score avec répartition decay/softmax
- **Fallback automatique** : Retour vers proportionnel si l'univers est indisponible
- **Cache intelligent** : Données marché mises en cache avec TTL configurable

## Architecture

### Composants principaux

```
connectors/coingecko.py     # Récupération données marché
services/universe.py        # Scoring et cache univers
config/universe.json        # Configuration scoring
data/mkt/aliases.json       # Mapping symbol → coingecko_id
data/cache/universe.json    # Cache persistant (auto-généré)
```

### Flux de données

1. **Extraction portfolio** → Groupes selon Taxonomy
2. **Récupération marché** → API CoinGecko (avec cache)
3. **Scoring multi-facteurs** → Score composite par coin
4. **Allocation priority** → Top-N + decay ou softmax
5. **Fallback automatique** → Proportionnel si problème

## Configuration

### config/universe.json

```json
{
  "features": {
    "priority_allocation": true    // Activer/désactiver la feature
  },
  "scoring": {
    "weights": {
      "w_cap_rank_inv": 0.30,     // Poids rank inverse (1=meilleur)
      "w_liquidity": 0.25,        // Poids liquidité (volume/mcap)
      "w_momentum": 0.20,         // Poids momentum (30d+90d)
      "w_internal": 0.10,         // Poids signaux internes
      "w_risk": 0.15              // Poids pénalités risque
    }
  },
  "allocation": {
    "top_n": 3,                   // Nombre max d'actifs par groupe
    "distribution_mode": "decay", // "decay" ou "softmax"
    "decay": [0.5, 0.3, 0.2]     // Poids decay pour Top-3
  },
  "guardrails": {
    "min_liquidity_usd": 50000,   // Volume 24h minimum
    "max_weight_per_coin": 0.40,  // Poids max par coin
    "min_trade_usd_default": 25.0 // Trade minimum par défaut
  },
  "lists": {
    "global_blacklist": ["LUNA", "UST", "FTT"],
    "pinned_by_group": {
      "BTC": ["BTC"],
      "ETH": ["ETH"]
    }
  },
  "cache": {
    "ttl_seconds": 3600,          // TTL cache (1h)
    "mode": "prefer_cache"        // "prefer_cache"|"cache_only"|"live_only"
  }
}
```

### data/mkt/aliases.json

Mapping des symbols/aliases vers les IDs CoinGecko :

```json
{
  "mappings": {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "WBTC": "wrapped-bitcoin"
  },
  "categories": {
    "layer-1": ["bitcoin", "ethereum", "solana"],
    "defi": ["uniswap", "aave", "maker"]
  }
}
```

## Utilisation

### Interface utilisateur

Dans `static/rebalance.html`, section **⚙️ Paramètres d'Allocation** :

- **Toggle Mode** : Proportionnel ↔ Priorité
- **Trade minimum** : Montant USD minimum par transaction
- **Statut univers** : Source (cache/live), timestamp, groupes traités

### API Endpoint

L'endpoint `/rebalance/plan` accepte le paramètre `sub_allocation` :

```json
POST /rebalance/plan
{
  "group_targets_pct": {"BTC": 40, "ETH": 30, "Others": 30},
  "sub_allocation": "priority",  // "proportional" (défaut) | "priority"
  "min_trade_usd": 50
}
```

### Réponse avec métadonnées

```json
{
  "actions": [...],
  "priority_meta": {
    "mode": "priority",
    "universe_available": true,
    "groups_with_fallback": ["Others"],
    "groups_details": {
      "BTC": {
        "total_coins": 3,
        "top_suggestions": [
          {"alias": "BTC", "score": 0.89, "rank": 1, "volume_24h": 25000000000},
          {"alias": "WBTC", "score": 0.72, "rank": 15, "volume_24h": 180000000}
        ],
        "fallback_used": false
      }
    }
  }
}
```

## Algorithme de scoring

### Score composite

```
score = w_cap_rank_inv × cap_rank_inv
      + w_liquidity × liquidity_proxy
      + w_momentum × norm_momentum_30_90d
      + w_internal × internal_signals
      - w_risk × risk_penalty
```

### Composantes détaillées

1. **Cap rank inverse** : `max(0, 1 - log10(rank) / 3)`
   - Rank 1 → score 1.0
   - Rank 100 → score ~0.33
   - Rank 1000 → score 0.0

2. **Liquidité** : `min(1, volume_24h / market_cap × 2)`
   - Ratio 10% → score 1.0
   - Plus le ratio est élevé, meilleure est la liquidité

3. **Momentum** : `(momentum_30d × 0.6 + momentum_90d × 0.4)`
   - Normalisé sur échelle -50% → +100%
   - Pondération favoring momentum récent

4. **Pénalités risque** :
   - `small_cap` (< 10M mcap) : -0.3
   - `low_volume` (< 100k vol/24h) : -0.4
   - `incomplete_data` : -0.2

## Gestion d'erreur et fallbacks

### Modes de fallback

1. **Univers indisponible** → Tous les groupes en proportionnel
2. **Mapping partiel** → Groupes sans données en proportionnel
3. **API timeout** → Cache existant ou proportionnel
4. **Configuration invalide** → Désactivation feature

### Logging pour debugging

```
INFO: Attempting priority allocation for 5 groups
INFO: Priority universe loaded for 4 groups
WARNING: UNIVERSE_FALLBACK_TO_PROPORTIONAL[g=Others] for remaining sell: 125.50 USD
ERROR: Priority buy failed for group L2/Scaling: API timeout, falling back to proportional
```

### Détection et diagnostic

- **Cache hits/misses** : Logs de performance
- **API failures** : Timeouts, rate limits, erreurs HTTP
- **Mapping failures** : Symbols non résolus vers coingecko_id
- **Score outliers** : Coins avec scores négatifs ou > 1.0

## Performance et limitations

### Performance

- **Cache TTL** : 1h par défaut, configurable
- **API rate limit** : 1.1s entre requêtes (free tier CoinGecko)
- **Batch size** : 100 coins max par requête
- **Response time** : p95 < 2s (avec cache), < 10s (live)

### Limitations actuelles

1. **Couverture mapping** : ~80 tokens principaux dans aliases.json
2. **Categories expansion** : Pas d'élargissement d'univers automatique
3. **ML scoring** : Pas de signaux ML intégrés (feature experimentale)
4. **Real-time updates** : Pas de refresh automatique pendant la session

### Améliorations futures

- [ ] Intégration signals on-chain (Glassnode)
- [ ] Expansion univers via catégories CoinGecko
- [ ] ML ranking avec sentiment/fundamentals
- [ ] Cache distribution multi-nœuds
- [ ] Refresh automatique background

## Dépannage

### Problèmes fréquents

1. **"Priority universe unavailable"**
   - Vérifier connectivité API CoinGecko
   - Vérifier config `features.priority_allocation: true`
   - Vérifier structure data/mkt/aliases.json

2. **"No coins selected after filtering"**
   - Blacklist trop restrictive
   - Min_liquidity_usd trop élevé
   - Mapping aliases incomplet

3. **"Fallback to proportional for group X"**
   - Normal si peu de coins dans le groupe
   - Vérifier pinned coins pas en conflit
   - Ajuster top_n si nécessaire

### Debug manuel

```python
# Test du connecteur
from connectors.coingecko import get_connector
connector = get_connector()
data = connector.get_market_snapshot(["BTC", "ETH"])
print(data)

# Test de l'univers
from services.universe import get_universe_cached
universe = get_universe_cached(["BTC", "ETH"], mode="live_only")
print(universe)

# Test du scoring
from services.rebalance import plan_rebalance
plan = plan_rebalance(rows, targets, sub_allocation="priority")
print(plan.get("priority_meta"))
```

### Monitoring

- **Logs application** : `UNIVERSE_*` pour events priority
- **Cache performance** : Hit rate dans universe.json metadata
- **API quotas** : Headers CoinGecko pour usage quotas
- **Error rates** : Fallback frequency par groupe

---

**Documentation générée pour smartfolio v1.0**
**Mode priority implémenté en septembre 2025** 🚀