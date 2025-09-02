# Configuration Optimale pour Développement

## Sources de Données Configurées

Le système utilise désormais **uniquement des vraies données** via trois sources configurables :

### 1. Source Stub (Recommandée pour développement)
- **Configuration** : Dans `settings.html` → sélectionner "Stub Data"
- **Avantages** : Données cohérentes, rapides, toujours disponibles
- **Usage** : Développement et tests

### 2. Fichiers CSV CoinTracking  
- **Configuration** : Dans `settings.html` → sélectionner "CSV Files"
- **Avantages** : Données réelles de votre portfolio
- **Prérequis** : Fichiers CSV exportés de CoinTracking dans `/data/`

### 3. API CoinTracking
- **Configuration** : Dans `settings.html` → sélectionner "CoinTracking API" + clés API
- **Avantages** : Données temps réel
- **Prérequis** : Clés API CoinTracking valides

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