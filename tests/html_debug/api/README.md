# API & Integration Tests  

Tests des connecteurs externes et intégrations de données.

## Tests disponibles

### Données Crypto
- **debug_bitcoin_fetch.html** - Test récupération données Bitcoin
- **test-coinglass-integration.html** - Intégration Coinglass API
- **test-coinglass-scraping.html** - Test scraping Coinglass
- **test-crypto-toolbox-integration.html** - Intégration Crypto Toolbox
- **test-crypto-toolbox-simple.html** - Test simple Crypto Toolbox

### Données Macro (FRED)
- **test_fred_integration.html** - Test intégration Federal Reserve
- **test_proxy_fred.html** - Test proxy FRED API  
- **test_fred_complete.html** - Test complet FRED
- **auto_load_fred.html** - Chargement automatique FRED

## Usage

Tests d'intégration avec APIs externes :
- Validation connecteurs de données
- Test robustesse et fallback
- Vérification cache et performance
- Debug problèmes de réseau/API

## Ordre de test recommandé

1. Tests simples d'abord (simple, integration)
2. Tests complets ensuite (complete, auto_load)  
3. Debug spécifique si problèmes détectés