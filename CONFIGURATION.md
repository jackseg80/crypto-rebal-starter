# Configuration Optimale pour Développement

## Sources de Données — Source de vérité centralisée

La liste des sources est centralisée dans `static/global-config.js` via `window.DATA_SOURCES` (+ ordre via `window.DATA_SOURCE_ORDER`).

### Groupes affichés dans Settings
- "Sources de démo" → entrées avec `kind: 'stub'`
- "Sources CoinTracking" → entrées avec `kind: 'csv'` et `kind: 'api'`

Ajouter/retirer une source = modifier `DATA_SOURCES` uniquement; l’onglet “Résumé”, l’onglet “Source”, les validations (`static/input-validator.js`) et l’ensemble des pages consomment `globalConfig.get('data_source')`.

## Interfaces Frontend Disponibles

Toutes les 19 routes backend ont maintenant des interfaces frontend :

### Principales
- `dashboard.html` - Vue d'ensemble portfolio
- `rebalance.html` - Rééquilibrage strategies  
- `risk-dashboard.html` - Analyse des risques
- `execution.html` - Exécution des trades
- `execution_history.html` - Historique des exécutions
- `settings.html` - Configuration système

### Outils Avancés
- `backtesting.html` - Tests de stratégies historiques
- `performance-monitor.html` - Monitoring performances système
- `portfolio-optimization.html` - Optimisation portfolio
- `cycle-analysis.html` - Analyse cycles marché
- `monitoring-unified.html` - Surveillance unifiée
- `alias-manager.html` - Gestion alias cryptos

## Données Mock Éliminées

✅ **Terminé** : Toutes les données mock ont été supprimées du système :
- Pas de fallback vers données fictives
- Erreurs explicites si source non configurée  
- Messages d'orientation vers settings.html

## Configuration Recommandée

1. **Démarrer le serveur** : `python main.py`
2. **Ouvrir settings.html** : Configure ta source de données préférée
3. **Utiliser Source Stub** : Pour développement rapide et stable
4. **Tester toutes les interfaces** : Vérifier cohérence des données

Toutes les interfaces utilisent maintenant la même configuration centralisée via `global-config.js`.

---

## Devise d’affichage & conversion

### Réglage
- `settings.html` fournit un sélecteur rapide (Résumé) et un sélecteur détaillé (Pricing). Les deux sont synchronisés et persistent dans `globalConfig`.

### Conversion
- Conversion à l’affichage depuis USD vers la devise choisie via `window.currencyManager`:
  - USD→EUR: `exchangerate.host`
  - USD→BTC: prix Binance `BTCUSDT` → USD→BTC = `1 / BTCUSD`
- Si le taux n’est pas disponible, l’UI affiche `—` puis se met à jour automatiquement à réception du taux (`currencyRateUpdated`).
- Formateurs homogènes (locale `fr-FR`), suppression du suffixe "US" ajouté par Intl pour USD (affiche seulement `$`).

### Pages alignées
- Dashboard (`static/dashboard.html`)
- Exécution (`static/execution.html`)
- Historique d'exécution (`static/execution_history.html`)
- Rebalancing (`static/rebalance.html`)
- Risk Dashboard (`static/risk-dashboard.html`)
- Intelligence Dashboard (`static/intelligence-dashboard.html`)
- Fonctions partagées (`static/shared-ml-functions.js`)

## Architecture API Post-Refactoring (v2.0.0)

### Namespaces Principaux
- **`/api/ml/*`** - Machine Learning unifié (remplace /api/ml-predictions)
- **`/api/risk/*`** - Risk Management consolidé (/api/risk/advanced/* pour fonctions avancées)  
- **`/api/alerts/*`** - Alertes centralisées (acknowledge, resolve, monitoring)
- **`/api/governance/*`** - Governance avec endpoints unifiés
- **`/api/realtime/*`** - Streaming temps réel (endpoints sécurisés)

### Endpoints Sécurisés
- **ML Debug**: `/api/ml/debug/*` nécessite header `X-Admin-Key: crypto-rebal-admin-2024`
- **Endpoints supprimés**: Tous `/api/test/*` et endpoints de broadcast supprimés pour sécurité

### Migration depuis v1.x
Consulter `REFACTORING_SUMMARY.md` et utiliser les outils de validation :
```bash
python find_broken_consumers.py          # Scan des références cassées
python tests/smoke_test_refactored_endpoints.py  # Validation endpoints
python verify_openapi_changes.py         # Analyse breaking changes
```
