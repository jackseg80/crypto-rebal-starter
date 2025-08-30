# Intégration Kraken - Documentation Complète

## 🎯 Vue d'Ensemble

L'intégration Kraken permet d'exécuter des trades réels sur l'exchange Kraken directement depuis le système crypto-rebal-starter. Cette intégration comprend :

- **API Client Kraken** complet avec authentification
- **Adaptateur Exchange** unifié 
- **Endpoints REST** pour contrôle via interface web
- **Validation de sécurité** intégrée
- **Gestion d'erreurs** robuste avec retry automatique

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │───▶│   API Gateway   │───▶│  Kraken Client  │
│   (Dashboard)   │    │  (FastAPI)      │    │   (REST API)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    Interface Web          Endpoints REST          Exchange Kraken
    - Controls             - /kraken/status        - Trading API
    - Monitoring           - /kraken/prices        - Market data
    - Configuration        - /kraken/balance       - Order management
```

## 📁 Structure des Fichiers

### Nouveaux fichiers créés :

```
connectors/
└── kraken_api.py          # Client API Kraken complet

services/execution/
└── exchange_adapter.py    # KrakenAdapter ajouté

api/
└── kraken_endpoints.py    # Endpoints REST Kraken

test_kraken_integration.py # Tests d'intégration complets
test_kraken_simple.py      # Test simple pour validation
```

## 🔑 Configuration

### Variables d'environnement

Créez ou modifiez votre fichier `.env` :

```bash
# Kraken API Credentials
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_API_SECRET=your_kraken_api_secret
```

### Obtenir les clés API Kraken

1. Connectez-vous à votre compte Kraken
2. Allez dans **Settings** → **API**
3. Créez une nouvelle clé API avec les permissions :
   - ✅ **Query Funds** (pour les soldes)
   - ✅ **Create & Modify Orders** (pour le trading)
   - ✅ **Query Open/Closed Orders** (pour le suivi)
4. Copiez la clé et le secret dans votre `.env`

## 🚀 Utilisation

### 1. Démarrer le serveur

```bash
cd crypto-rebal-starter
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Vérifier l'intégration

```bash
# Test simple
curl http://127.0.0.1:8000/kraken/status

# Test complet
curl http://127.0.0.1:8000/kraken/test-connection
```

### 3. Endpoints disponibles

#### `/kraken/status` (GET)
Statut de l'intégration Kraken
```json
{
  "available": true,
  "adapter_registered": true,
  "api_accessible": true,
  "server_time": 1755955080,
  "system_status": "online",
  "has_credentials": false
}
```

#### `/kraken/system-info` (GET)
Informations système détaillées
```json
{
  "system_status": {"status": "online"},
  "server_time": 1755955092,
  "api_accessible": true,
  "major_assets": {...},
  "integration_version": "1.0.0",
  "features": {
    "public_data": true,
    "private_trading": false,
    "order_validation": false,
    "balance_check": false
  }
}
```

#### `/kraken/prices` (GET)
Prix en temps réel
```bash
curl "http://127.0.0.1:8000/kraken/prices?symbols=BTC/USD,ETH/USD"
```

#### `/kraken/balance` (GET) 
Soldes du compte (nécessite credentials)
```json
{
  "balances": [
    {"asset": "USD", "balance": 1000.0},
    {"asset": "BTC", "balance": 0.05}
  ],
  "total_assets": 2
}
```

#### `/kraken/test-connection` (GET)
Test de connectivité complet
```json
{
  "adapter_available": true,
  "api_accessible": true,
  "credentials_valid": false,
  "trading_pairs_loaded": false,
  "prices_accessible": true,
  "integration_score": "3/5",
  "ready_for_trading": false
}
```

## 🛡️ Sécurité

### Validation d'ordre intégrée

Chaque ordre passe par le `SafetyValidator` :

```python
# Validations automatiques :
- Montant maximum par ordre
- Vérification des symboles
- Limites de trading quotidiennes
- Détection d'activité suspecte
```

### Mode de validation

Pour tester sans risque :

```bash
curl -X POST http://127.0.0.1:8000/kraken/validate-order \
  -H "Content-Type: application/json" \
  -d '{
    "pair": "XBTUSD",
    "type": "buy", 
    "volume": "0.001"
  }'
```

## 🔧 Utilisation Programmatique

### Via l'Execution Engine

```python
from services.execution.order_manager import Order, OrderPriority
from services.execution.execution_engine import ExecutionEngine

# Créer un ordre
order = Order(
    id="test_001",
    symbol="BTC/USD",
    action="buy",
    usd_amount=50.0,
    exchange_hint="kraken"
)

# Exécuter via le moteur
engine = ExecutionEngine()
result = await engine.execute_order(order)
```

### Via l'adaptateur direct

```python
from services.execution.exchange_adapter import exchange_registry

# Obtenir l'adaptateur Kraken
kraken = exchange_registry.get_adapter("kraken")
await kraken.connect()

# Vérifier un solde
balance = await kraken.get_balance("BTC")
print(f"BTC Balance: {balance}")

# Obtenir un prix
price = await kraken.get_current_price("BTC/USD")  
print(f"BTC Price: ${price}")

await kraken.disconnect()
```

## 📊 Mapping des Assets

Le système gère automatiquement la conversion entre formats :

```python
# Standard → Kraken
BTC → XXBT
ETH → XETH  
USD → ZUSD
USDT → USDT

# Kraken → Standard (automatique)
XXBT → BTC
XETH → ETH
ZUSD → USD
```

## 🐛 Troubleshooting

### Erreurs communes

#### 1. "API credentials not found"
```bash
# Vérifiez votre .env
echo $KRAKEN_API_KEY
echo $KRAKEN_API_SECRET

# Rechargez les variables
source .env
```

#### 2. "Connection failed"
```bash
# Testez la connectivité basique
curl http://127.0.0.1:8000/kraken/status
```

#### 3. "Order validation failed"  
```bash
# Mode debug pour voir les détails
curl -v http://127.0.0.1:8000/kraken/validate-order -d '{...}'
```

### Logs de debug

```python
import logging
logging.getLogger('connectors.kraken_api').setLevel(logging.DEBUG)
logging.getLogger('services.execution.exchange_adapter').setLevel(logging.DEBUG)
```

## 🧪 Tests

### Test simple
```bash
python test_kraken_simple.py
```

### Test complet
```bash
python test_kraken_integration.py
```

### Tests des endpoints
```bash
# Status
curl http://127.0.0.1:8000/kraken/status

# Prix
curl "http://127.0.0.1:8000/kraken/prices?symbols=BTC/USD"

# Test complet
curl http://127.0.0.1:8000/kraken/test-connection
```

## 🔄 Intégration avec le Rebalancer

L'intégration Kraken s'active automatiquement dans les plans de rebalancement :

1. **Génération du plan** : `POST /rebalance/plan`
2. **Export pour exécution** : Les actions incluent `exchange_hint: "kraken"`
3. **Exécution** : `POST /execution/execute-plan`

### Exemple de plan avec Kraken

```json
{
  "actions": [
    {
      "symbol": "BTC",
      "action": "buy",
      "usd_amount": 100.0,
      "exchange_hint": "kraken",
      "exec_hint": "Recommended: Kraken (low fees)"
    }
  ]
}
```

## 📈 Monitoring

### Dashboard Integration

Les métriques Kraken apparaissent dans :

- **Dashboard** → Connection Status
- **Execution History** → Exchange Performance  
- **Monitoring** → Exchange Health

### Alertes configurées

- Échec de connexion Kraken
- Ordres rejetés (> 5%)
- Latence élevée (> 2s)

## 🚀 Prochaines étapes

### Fonctionnalités avancées (Phase 5B)

1. **Ordre limit** : Support des ordres à prix limite
2. **Staking** : Intégration staking Kraken
3. **Fee optimization** : Routage intelligent selon les frais
4. **Advanced orders** : Stop-loss, take-profit

### Autres exchanges (Phase 6)

Avec l'architecture adapter, ajouter d'autres exchanges :
- Coinbase Pro
- Bybit  
- OKX
- Binance (déjà commencé)

## 📝 Changelog

### Version 1.0.0 (2025-08-23)

✅ **Fonctionnalités complètes** :
- Client API Kraken avec authentification
- Adaptateur exchange unifié
- 7 endpoints REST complets
- Tests d'intégration automatisés
- Documentation complète
- Validation de sécurité intégrée

## 🤝 Contribution

Pour contribuer à l'intégration Kraken :

1. Testez avec vos propres credentials
2. Reportez les bugs dans les issues GitHub  
3. Proposez des améliorations
4. Ajoutez des tests pour nouveaux features

---

## ⚠️ Avertissement

**ATTENTION** : Cette intégration permet d'exécuter de vrais trades avec de l'argent réel. 

- Testez d'abord sans credentials
- Utilisez des petits montants pour débuter  
- Vérifiez toujours vos ordres avant exécution
- Gardez vos clés API sécurisées

**L'équipe crypto-rebal-starter n'est pas responsable des pertes financières liées à l'utilisation de cette intégration.**