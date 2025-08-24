# Developer Guide - Crypto Rebalancer

## 🎯 Bienvenue développeur !

Ce guide vous permettra de contribuer efficacement au projet Crypto Rebalancer. Vous y trouverez tout ce qu'il faut savoir pour développer, tester et déployer de nouvelles fonctionnalités.

## 📋 Table des matières

- [Quick Start Developer](#-quick-start-developer)
- [Architecture & Conventions](#-architecture--conventions)
- [Développement Local](#-développement-local)
- [Standards de Code](#-standards-de-code)
- [Testing Strategy](#-testing-strategy)
- [Contribution Workflow](#-contribution-workflow)
- [Debugging & Profiling](#-debugging--profiling)
- [Déploiement](#-déploiement)

---

## 🚀 Quick Start Developer

### Prerequisites

```bash
# Python 3.9+
python --version  # >= 3.9

# Git configuré
git config --global user.name "Votre Nom"
git config --global user.email "votre@email.com"

# IDE recommandé : VS Code avec extensions
# - Python
# - Python Docstring Generator
# - Black Formatter
# - Pylint
```

### Installation & Setup

```bash
# 1. Clone du projet
git clone https://github.com/votre-org/crypto-rebal-starter.git
cd crypto-rebal-starter

# 2. Environment virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\\Scripts\\activate    # Windows

# 3. Installation des dépendances
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Outils de dev (à créer)

# 4. Configuration
cp .env.example .env
# Éditez .env avec vos clés API

# 5. Vérification de l'installation
python -m pytest tests/  # Si tests disponibles
uvicorn api.main:app --reload
```

### Premier Lancement

```bash
# Terminal 1 : API Server
uvicorn api.main:app --reload --port 8000

# Terminal 2 : Tests de base
curl http://127.0.0.1:8000/healthz

# Terminal 3 : Interface web
# Ouvrir static/dashboard.html dans le navigateur
```

---

## 🏗️ Architecture & Conventions

### Structure du Projet

```
crypto-rebal-starter/
├── api/                    # 🔌 FastAPI endpoints
│   ├── main.py            # Point d'entrée principal
│   ├── exceptions.py      # Gestion des erreurs
│   ├── models.py          # Modèles Pydantic
│   └── *_endpoints.py     # Endpoints par domaine
├── services/              # 🧠 Business Logic
│   ├── analytics/         # Analytics et performance
│   ├── execution/         # Moteur d'exécution
│   ├── notifications/     # Alertes et monitoring
│   ├── monitoring/        # Surveillance système
│   └── *.py              # Services core
├── connectors/            # 🔗 External APIs
│   ├── cointracking_api.py
│   └── kraken_api.py
├── engine/                # ⚙️ Core Algorithms
│   └── rebalance.py       # Algorithme de rebalancement
├── static/                # 🖥️ Frontend
│   ├── *.html            # Interfaces utilisateur
│   ├── shared-*.js       # Modules JavaScript partagés
│   └── *.css             # Styles
├── tests/                 # 🧪 Tests (à développer)
├── data/                  # 📊 Données temporaires
├── docs/                  # 📚 Documentation
└── scripts/              # 🔧 Outils utilitaires
```

### Patterns Architecturaux

#### 1. **Service Layer Pattern**
```python
# services/portfolio.py
class PortfolioService:
    def __init__(self, connector: DataConnector):
        self.connector = connector
    
    async def get_portfolio(self, source: str) -> Portfolio:
        raw_data = await self.connector.fetch(source)
        return self.normalize(raw_data)
```

#### 2. **Repository Pattern**
```python
# connectors/base.py
class DataConnector(ABC):
    @abstractmethod
    async def fetch_balances(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def fetch_prices(self) -> Dict[str, float]:
        pass
```

#### 3. **Factory Pattern**
```python
# services/pricing.py
def get_pricing_strategy(mode: str) -> PricingStrategy:
    strategies = {
        'local': LocalPricingStrategy(),
        'hybrid': HybridPricingStrategy(),
        'auto': AutoPricingStrategy()
    }
    return strategies.get(mode, HybridPricingStrategy())
```

---

## 💻 Développement Local

### Environment Setup

#### Variables d'Environnement
```bash
# .env.dev - Configuration développement
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# CoinTracking (obligatoire pour certains tests)
CT_API_KEY=your_key_here
CT_API_SECRET=your_secret_here

# CoinGecko (optionnel)
COINGECKO_API_KEY=your_coingecko_key

# Développement spécifique
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
RELOAD=true
WORKERS=1
```

#### IDE Configuration (VS Code)

`.vscode/settings.json`
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

`.vscode/launch.json`
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI Dev Server",
            "type": "python",
            "request": "launch",
            "program": "-m",
            "args": ["uvicorn", "api.main:app", "--reload", "--port", "8000"],
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env"
        }
    ]
}
```

### Hot Reload Development

```bash
# Serveur avec hot reload
uvicorn api.main:app --reload --port 8000

# Monitoring des changements frontend
# (Optionnel) Serveur HTTP simple pour static/
python -m http.server 3000 --directory static/

# Watch files pour auto-refresh
# npm install -g browser-sync
browser-sync start --server static --files "static/**/*"
```

### Base de Données de Dev

```python
# scripts/dev_data.py - Générateur de données de test
def generate_test_portfolio():
    return {
        "items": [
            {"symbol": "BTC", "amount": 1.5, "value_usd": 45000, "location": "Kraken"},
            {"symbol": "ETH", "amount": 10, "value_usd": 25000, "location": "Binance"},
            # ... plus de données de test
        ]
    }
```

---

## 📏 Standards de Code

### Python Code Style

#### Formatting avec Black
```bash
# Configuration dans pyproject.toml
[tool.black]
line-length = 88
target-version = ['py39']
include = '\\.pyi?$'
extend-exclude = '''
/(
  | migrations
  | venv
)/
'''

# Usage
black services/ api/ connectors/ engine/
```

#### Linting avec Pylint
```bash
# .pylintrc
[MASTER]
disable = C0114,C0115,C0116  # Missing docstrings
max-line-length = 88

[DESIGN]
max-args = 8
max-locals = 20

# Usage
pylint services/ api/
```

#### Type Hints
```python
# ✅ Bon exemple
from typing import List, Dict, Optional, Union
from datetime import datetime

def calculate_portfolio_value(
    items: List[Dict[str, Union[str, float]]], 
    price_source: str = "auto"
) -> Optional[float]:
    """Calculate total portfolio value in USD.
    
    Args:
        items: List of portfolio items with symbol/amount/value
        price_source: Pricing strategy to use
    
    Returns:
        Total value in USD, None if calculation fails
    """
    total = 0.0
    for item in items:
        if isinstance(item.get('value_usd'), (int, float)):
            total += item['value_usd']
    return total if total > 0 else None
```

### JavaScript Code Style

#### ES6+ Standards
```javascript
// ✅ Bon exemple - Module pattern
const PortfolioAPI = {
    async loadPortfolio(source = 'cointracking') {
        try {
            const response = await fetch(`/api/balances/current?source=${source}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Portfolio loading failed:', error);
            throw error;
        }
    },

    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }
};

// Usage
PortfolioAPI.loadPortfolio()
    .then(data => console.log('Portfolio loaded:', data))
    .catch(error => console.error('Error:', error));
```

### Documentation Standards

#### Python Docstrings (Google Style)
```python
def rebalance_portfolio(
    portfolio: List[Dict], 
    targets: Dict[str, float],
    min_trade_usd: float = 25.0
) -> Dict[str, Any]:
    """Generate rebalancing plan for given portfolio and targets.

    This function calculates the optimal buy/sell actions needed to
    rebalance a portfolio according to target allocations.

    Args:
        portfolio: List of portfolio items with symbol, amount, value_usd
        targets: Target allocation percentages by group
        min_trade_usd: Minimum trade size to avoid micro-transactions

    Returns:
        Dict containing:
            - actions: List of buy/sell actions
            - total_usd: Total portfolio value
            - deltas_by_group_usd: Required changes by group

    Raises:
        ValueError: If portfolio is empty or targets don't sum to 100%
        
    Example:
        >>> portfolio = [{"symbol": "BTC", "amount": 1, "value_usd": 40000}]
        >>> targets = {"BTC": 50, "ETH": 50}
        >>> plan = rebalance_portfolio(portfolio, targets)
        >>> print(f"Actions needed: {len(plan['actions'])}")
    """
```

---

## 🧪 Testing Strategy

### Test Structure

```
tests/
├── unit/                  # Tests unitaires
│   ├── test_services.py
│   ├── test_connectors.py
│   └── test_engine.py
├── integration/           # Tests d'intégration
│   ├── test_api_endpoints.py
│   └── test_external_apis.py
├── e2e/                   # Tests end-to-end
│   └── test_pipeline.py
├── fixtures/              # Données de test
│   ├── portfolio_data.json
│   └── price_data.json
└── conftest.py           # Configuration pytest
```

### Unit Tests avec pytest

```python
# tests/unit/test_rebalance.py
import pytest
from engine.rebalance import RebalanceEngine

@pytest.fixture
def sample_portfolio():
    return [
        {"symbol": "BTC", "amount": 1.0, "value_usd": 40000, "location": "Kraken"},
        {"symbol": "ETH", "amount": 10.0, "value_usd": 20000, "location": "Binance"}
    ]

@pytest.fixture  
def target_allocation():
    return {"BTC": 50, "ETH": 50}

class TestRebalanceEngine:
    def test_calculate_actions_basic(self, sample_portfolio, target_allocation):
        engine = RebalanceEngine()
        plan = engine.generate_plan(sample_portfolio, target_allocation)
        
        assert len(plan['actions']) >= 0
        assert 'total_usd' in plan
        assert abs(sum(action['usd'] for action in plan['actions'])) < 0.01

    def test_empty_portfolio_raises_error(self):
        engine = RebalanceEngine()
        with pytest.raises(ValueError, match="Portfolio cannot be empty"):
            engine.generate_plan([], {"BTC": 100})

    @pytest.mark.parametrize("targets,expected_error", [
        ({"BTC": 101}, "Target percentages must sum to 100"),
        ({"BTC": 50, "ETH": 45}, "Target percentages must sum to 100"),
        ({}, "No targets provided")
    ])
    def test_invalid_targets(self, sample_portfolio, targets, expected_error):
        engine = RebalanceEngine()
        with pytest.raises(ValueError, match=expected_error):
            engine.generate_plan(sample_portfolio, targets)
```

### Integration Tests

```python
# tests/integration/test_api_endpoints.py
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

class TestPortfolioEndpoints:
    def test_get_balances_success(self):
        response = client.get("/balances/current?source=stub&min_usd=1")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "source_used" in data

    def test_generate_plan_success(self):
        payload = {
            "group_targets_pct": {"BTC": 50, "ETH": 50},
            "min_trade_usd": 25
        }
        response = client.post("/rebalance/plan", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "total_usd" in data
```

### E2E Tests

```python
# tests/e2e/test_pipeline.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_full_rebalancing_pipeline():
    """Test complet du pipeline de rebalancement."""
    
    # 1. Load portfolio
    portfolio_service = PortfolioService()
    portfolio = await portfolio_service.load_portfolio("cointracking")
    assert len(portfolio.items) > 0
    
    # 2. Generate plan
    rebalance_service = RebalanceService()
    targets = {"BTC": 40, "ETH": 30, "Others": 30}
    plan = await rebalance_service.generate_plan(portfolio, targets)
    assert len(plan.actions) > 0
    
    # 3. Validate plan
    validator = SafetyValidator()
    is_valid = validator.validate_plan(plan)
    assert is_valid == True
    
    # 4. Execute (simulation)
    simulator = EnhancedSimulator()
    results = await simulator.execute_plan(plan)
    assert results.success == True
```

### Test Configuration

```python
# conftest.py
import pytest
import asyncio
from unittest.mock import Mock

@pytest.fixture
def mock_cointracking_api():
    mock = Mock()
    mock.get_balances.return_value = {
        "items": [
            {"symbol": "BTC", "amount": 1, "value_usd": 40000}
        ]
    }
    return mock

@pytest.fixture
def event_loop():
    """Fixture for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Configuration pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --cov=services
    --cov=api
    --cov-report=html
    --cov-report=term
markers =
    unit: Unit tests
    integration: Integration tests  
    e2e: End-to-end tests
    slow: Tests that take > 1s
```

---

## 🔄 Contribution Workflow

### Git Workflow

#### Branch Strategy
```bash
# Structure des branches
main                    # Production stable
├── develop            # Intégration des features
├── feature/new-risk-metrics    # Nouvelles fonctionnalités
├── fix/portfolio-loading-bug   # Corrections de bugs
└── docs/api-reference         # Améliorations documentation
```

#### Contribution Process
```bash
# 1. Synchronisation
git checkout develop
git pull origin develop

# 2. Nouvelle feature branch
git checkout -b feature/awesome-new-feature

# 3. Développement
# ... code, test, commit ...
git add .
git commit -m "feat: Add awesome new feature with comprehensive tests

- Implement core functionality in services/awesome.py
- Add unit tests with 95% coverage  
- Update API endpoints with new routes
- Add frontend integration in dashboard.html

Closes #123"

# 4. Tests avant push
python -m pytest tests/
black services/ api/
pylint services/

# 5. Push et Pull Request
git push origin feature/awesome-new-feature
# Créer PR vers develop via GitHub/GitLab
```

### Commit Message Standards

#### Format Conventional Commits
```bash
# Format: type(scope): description
feat(api): Add new risk metrics endpoint
fix(portfolio): Resolve balance calculation error
docs(readme): Update installation instructions
test(engine): Add comprehensive rebalancing tests
refactor(services): Extract pricing logic to separate service
perf(cache): Optimize portfolio data caching
style(frontend): Fix CSS styling issues
```

#### Types de Commits
- **feat**: Nouvelle fonctionnalité
- **fix**: Correction de bug
- **docs**: Documentation uniquement
- **style**: Changements de formatage
- **refactor**: Refactoring sans changement fonctionnel
- **perf**: Amélioration de performance
- **test**: Ajout/modification de tests
- **chore**: Maintenance (deps, config, etc.)

### Pull Request Template

```markdown
## 🎯 Description
Brief description of what this PR does.

## 🔧 Changes Made
- [ ] Added new service for X functionality
- [ ] Updated API endpoints  
- [ ] Added comprehensive tests
- [ ] Updated documentation

## 🧪 Testing
- [ ] Unit tests pass (pytest tests/unit/)
- [ ] Integration tests pass (pytest tests/integration/)
- [ ] Manual testing completed
- [ ] Performance impact assessed

## 📚 Documentation
- [ ] Code comments updated
- [ ] API documentation updated
- [ ] User guide updated (if applicable)

## 🚀 Deployment Notes
Any special deployment considerations.

## 📸 Screenshots (if applicable)
Before/after screenshots for UI changes.
```

---

## 🐛 Debugging & Profiling

### Logging pour Debugging

#### Configuration des Logs
```python
# services/logging_config.py
import logging
import sys
from datetime import datetime

def setup_logging(level=logging.INFO):
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger

# Usage dans les services
logger = logging.getLogger(__name__)

def process_portfolio(data):
    logger.debug(f"Processing portfolio with {len(data)} items")
    
    try:
        result = complex_calculation(data)
        logger.info(f"Portfolio processed successfully: {result.summary}")
        return result
    except Exception as e:
        logger.error(f"Portfolio processing failed: {e}", exc_info=True)
        raise
```

#### Structured Logging
```python
# Pour debugging avancé
import structlog

logger = structlog.get_logger()

def rebalance_portfolio(portfolio, targets):
    logger.info(
        "rebalancing_started",
        portfolio_value=sum(item['value_usd'] for item in portfolio),
        target_groups=list(targets.keys()),
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Processing...
    
    logger.info(
        "rebalancing_completed", 
        actions_count=len(actions),
        total_trades_usd=sum(abs(a['usd']) for a in actions),
        duration_ms=duration
    )
```

### Performance Profiling

#### Profiling avec cProfile
```python
# scripts/profile_rebalance.py
import cProfile
import pstats
from engine.rebalance import RebalanceEngine

def profile_rebalancing():
    engine = RebalanceEngine()
    # Large portfolio for testing
    portfolio = generate_large_portfolio(1000)  
    targets = {"BTC": 30, "ETH": 25, "Others": 45}
    
    # Profile the heavy computation
    engine.generate_plan(portfolio, targets)

if __name__ == "__main__":
    cProfile.run('profile_rebalancing()', 'rebalance_profile.prof')
    
    # Analyze results
    stats = pstats.Stats('rebalance_profile.prof')
    stats.sort_stats('tottime')
    stats.print_stats(20)  # Top 20 functions
```

#### Memory Profiling
```python
# pip install memory-profiler
from memory_profiler import profile

@profile
def memory_intensive_function():
    portfolio_data = load_large_portfolio()
    processed_data = process_all_data(portfolio_data)
    return generate_report(processed_data)

# Usage: python -m memory_profiler script.py
```

#### API Performance Testing
```python
# scripts/load_test.py
import asyncio
import aiohttp
import time

async def load_test_endpoint():
    async with aiohttp.ClientSession() as session:
        start_time = time.time()
        
        # 100 concurrent requests
        tasks = []
        for i in range(100):
            task = session.get('http://localhost:8000/balances/current?source=stub')
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"100 requests completed in {duration:.2f}s")
        print(f"Average: {duration/100*1000:.2f}ms per request")

# Run: python scripts/load_test.py
```

---

## 🚀 Déploiement

### Local Deployment

#### Docker Development
```dockerfile
# Dockerfile.dev
FROM python:3.9-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Development dependencies
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

# Code
COPY . .

# Development server with hot reload
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  api:
    build: 
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/__pycache__
    environment:
      - ENV=development
      - DEBUG=true
    env_file:
      - .env
```

### Production Deployment

#### Optimized Dockerfile
```dockerfile
# Dockerfile
FROM python:3.9-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Production stage
FROM python:3.9-slim

WORKDIR /app

# Copy from builder
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Non-root user for security
RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8000

# Production server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### Production docker-compose
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    build: .
    restart: unless-stopped
    environment:
      - ENV=production
      - WORKERS=4
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data  # Persistent data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./static:/usr/share/nginx/html:ro
    depends_on:
      - api
```

### CI/CD Pipeline

#### GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Lint with black and pylint
      run: |
        black --check services/ api/
        pylint services/ api/
    
    - name: Test with pytest
      run: |
        pytest tests/ --cov=services --cov=api --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: docker build -t crypto-rebalancer:latest .
    
    - name: Push to registry (if configured)
      # Add your registry push logic here
      run: echo "Would push to registry"

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - name: Deploy to production
      # Add your deployment logic here
      run: echo "Would deploy to production"
```

---

## 🎯 Prochaines Étapes

### Pour Commencer
1. **Setup complet** : Suivre le Quick Start Developer
2. **Premier ticket** : Chercher les issues `good-first-issue`  
3. **Tests** : Ajouter des tests pour votre première contribution
4. **Documentation** : Maintenir la doc à jour

### Amélioration Continue
- **Code Reviews** : Participer aux reviews des autres
- **Performance** : Profiler et optimiser les parties critiques
- **Sécurité** : Toujours penser sécurité dans vos développements
- **Testing** : Viser 80%+ de couverture de tests

### Ressources Utiles
- **TECHNICAL_ARCHITECTURE.md** : Architecture détaillée
- **API_REFERENCE.md** : Documentation des endpoints
- **Issues GitHub** : Backlog et bugs à corriger
- **Discussions** : Forum pour questions et propositions

---

**🎉 Bienvenue dans l'équipe ! Ce guide évolue avec le projet, n'hésitez pas à proposer des améliorations.**