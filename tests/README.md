# Tests Organization

## Structure

- `unit/` - Tests unitaires pour des fonctions/classes spécifiques
- `integration/` - Tests d'intégration avec APIs externes et services
- `e2e/` - Tests end-to-end et de communication entre modules
- `fixtures/` - Données de test et fixtures (JSON, HTML de diagnostic)
- `utils/` - Utilitaires de test réutilisables
- `html_debug/` - Pages HTML de debug et test d'interface
- `powershell_scripts/` - Scripts PowerShell pour automatisation

## Types de Tests

### Unit Tests (`unit/`)
- `test_smart_classification.py` - Classification intelligente
- `test_safety_validator.py` - Validateur de sécurité
- `test_error_handling.py` - Gestion d'erreurs

### Integration Tests (`integration/`)
- `test_binance_integration.py` - Intégration Binance
- `test_kraken_integration.py` - Intégration Kraken
- `test_enhanced_simulation.py` - Simulation avancée

### E2E Tests (`e2e/`)
- `test_pipeline_e2e.py` - Pipeline complet
- `test_execution_e2e.py` - Exécution complète
- Communication entre modules frontend/backend

## Usage

```bash
# Tests unitaires
python -m pytest tests/unit/

# Tests d'intégration
python -m pytest tests/integration/

# Tests complets
python -m pytest tests/e2e/

# Tous les tests
python -m pytest tests/
```