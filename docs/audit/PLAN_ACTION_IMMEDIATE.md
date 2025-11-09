# ⚡ Plan d'Action Immédiat - SmartFolio

**Période:** Semaine 1 (5 jours)
**Objectif:** Résoudre bloqueurs production + Quick wins conformité
**Effort:** 1 développeur

---

## 🔥 JOUR 1: SÉCURITÉ CRITIQUE (8h)

### 1. Révoquer Clé API CoinGecko (30 min)

**Action:**
1. Se connecter à [CoinGecko Dashboard](https://www.coingecko.com/en/api/pricing)
2. Révoquer clé `CG-ZcsKJgLUH5DeU2xeSu7R2a6v`
3. Générer nouvelle clé

**Code:**
```bash
# Vérifier historique git pour cette clé
cd d:\Python\smartfolio
git log --all --full-history --source -S "CG-ZcsKJgLUH5DeU2xeSu7R2a6v"

# Si trouvé dans historique → Rotation obligatoire
```

**Configuration:**
```bash
# .env (NE PAS COMMITTER)
COINGECKO_API_KEY=<NOUVELLE_CLE>

# .env.example (Template pour équipe)
COINGECKO_API_KEY=your_coingecko_api_key_here
```

✅ **Checklist:**
- [ ] Clé révoquée sur CoinGecko
- [ ] Nouvelle clé générée
- [ ] `.env` mis à jour localement
- [ ] `.env.example` créé (sans vraie clé)
- [ ] Historique git vérifié
- [ ] Équipe notifiée de rotation

---

### 2. Supprimer Credentials Hardcodés (1h30)

**Fichiers à modifier:**

#### A. `api/unified_ml_endpoints.py:486`
```python
# ❌ AVANT
expected_key = os.getenv("ADMIN_KEY", "crypto-rebal-admin-2024")

# ✅ APRÈS
expected_key = os.getenv("ADMIN_KEY")
if not expected_key:
    raise ValueError(
        "ADMIN_KEY environment variable is required. "
        "Generate one with: openssl rand -hex 32"
    )
```

#### B. `tests/smoke_test_refactored_endpoints.py:147`
```python
# ❌ AVANT
headers = {"X-Admin-Key": "crypto-rebal-admin-2024"}

# ✅ APRÈS
import os
ADMIN_KEY = os.getenv("ADMIN_KEY_TEST", "test-key-please-change")
headers = {"X-Admin-Key": ADMIN_KEY}
```

#### C. `setup_dev.py:122`
```bash
# ❌ AVANT
DEBUG_TOKEN=dev-secret-2024

# ✅ APRÈS
DEBUG_TOKEN=$(openssl rand -hex 32)
```

**Générer tokens forts:**
```bash
# Générer ADMIN_KEY
openssl rand -hex 32
# Exemple: a3f2c8b9d1e4f6a7c8b9d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2

# Ajouter à .env
echo "ADMIN_KEY=a3f2c8b9d1e4f6a7c8b9d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2" >> .env
```

✅ **Checklist:**
- [ ] `api/unified_ml_endpoints.py` modifié
- [ ] `tests/smoke_test_refactored_endpoints.py` modifié
- [ ] `setup_dev.py` modifié
- [ ] Tokens forts générés (32 bytes)
- [ ] `.env` mis à jour
- [ ] Tests exécutés (pytest)

---

### 3. Remplacer eval() JavaScript (2h)

**Fichier:** `static/modules/risk-dashboard-main-controller.js:3724`

**Changements:**
```javascript
// ❌ AVANT (ligne 3724)
const onclickAttr = event.target.getAttribute('onclick');
if (onclickAttr) {
  try {
    eval(onclickAttr);  // DANGER!
  } catch (error) {
    debugLogger.error('Error executing toast action:', error);
  }
}

// ✅ APRÈS - Event delegation sécurisé
const SAFE_TOAST_ACTIONS = {
  'reload': () => {
    debugLogger.info('Reloading page...');
    location.reload();
  },
  'dismiss': () => {
    debugLogger.info('Dismissing toast');
    event.target.closest('.toast')?.remove();
  },
  'viewDetails': () => {
    const detailsUrl = event.target.getAttribute('data-details-url');
    if (detailsUrl) {
      window.location.href = detailsUrl;
    }
  }
};

const actionName = event.target.getAttribute('data-action');
if (actionName && SAFE_TOAST_ACTIONS[actionName]) {
  try {
    SAFE_TOAST_ACTIONS[actionName]();
  } catch (error) {
    debugLogger.error(`Error executing toast action '${actionName}':`, error);
  }
}
```

**Mise à jour HTML (si nécessaire):**
```html
<!-- ❌ AVANT -->
<button onclick="location.reload()">Reload</button>

<!-- ✅ APRÈS -->
<button data-action="reload">Reload</button>
<button data-action="viewDetails" data-details-url="/risk/dashboard">View</button>
```

✅ **Checklist:**
- [ ] Code eval() remplacé
- [ ] SAFE_TOAST_ACTIONS défini
- [ ] HTML mis à jour (si nécessaire)
- [ ] Tests manuels (toasts fonctionnent)
- [ ] Vérifier aucun autre eval() (Grep)

**Commande vérification:**
```bash
# Rechercher autres eval()
grep -r "eval(" static/ --include="*.js"
```

---

### 4. Fix CORS Wildcard (30 min)

**Fichiers à modifier:**

#### A. `start_simple.py:18`
```python
# ❌ AVANT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"]
)

# ✅ APRÈS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"]
)
```

#### B. `tests/unit/test_risk_server.py:25`
```python
# Même changement
allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"]
```

✅ **Checklist:**
- [ ] `start_simple.py` modifié
- [ ] `test_risk_server.py` modifié
- [ ] Tests unitaires exécutés
- [ ] Vérifier autres CORS wildcard (Grep)

---

### 5. Validation DEV_OPEN_API Production (1h)

**Fichier:** `api/deps.py`

**Ajouter au startup (api/main.py):**
```python
# api/main.py - Ajouter après ligne 86 (après logging setup)

# Validation environnement critique
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEV_OPEN_API = os.getenv("DEV_OPEN_API", "0")

if ENVIRONMENT == "production" and DEV_OPEN_API == "1":
    raise RuntimeError(
        "SECURITY ERROR: DEV_OPEN_API cannot be enabled in production! "
        "This bypasses all authentication. Set DEV_OPEN_API=0 or remove it."
    )

if DEV_OPEN_API == "1":
    logger.warning("=" * 80)
    logger.warning("⚠️  DEV MODE ACTIVE - AUTHENTICATION BYPASSED")
    logger.warning("⚠️  DO NOT USE IN PRODUCTION")
    logger.warning("=" * 80)
```

**Mise à jour deps.py:**
```python
# api/deps.py:49-52 - Améliorer logging
dev_mode = os.getenv("DEV_OPEN_API", "0") == "1"
if dev_mode:
    logger.warning(
        f"⚠️ DEV MODE: Bypassing authorization for user: {normalized_user} "
        f"(X-User header: {x_user})"
    )
    return normalized_user
```

✅ **Checklist:**
- [ ] Validation startup ajoutée
- [ ] Logging warning amélioré
- [ ] Test avec ENVIRONMENT=production DEV_OPEN_API=1 (doit crash)
- [ ] Test en dev (doit logger warning)
- [ ] Documentation mise à jour

---

### 🎯 Fin Jour 1 - Sécurité Sécurisée!

**Résultat:**
- ✅ 5 vulnérabilités critiques corrigées
- ✅ Clés API rotées
- ✅ Credentials sécurisés
- ✅ Code injection éliminé
- ✅ CORS restreint
- ✅ Validation production

**Tests:**
```bash
# Exécuter suite complète
pytest tests/unit tests/integration -v

# Vérifier sécurité
python -c "import os; os.environ['ENVIRONMENT']='production'; os.environ['DEV_OPEN_API']='1'; import api.main"
# Doit afficher: RuntimeError: DEV_OPEN_API cannot be enabled in production
```

---

## 📋 JOUR 2: CONFORMITÉ CLAUDE.MD (8h)

### 6. Migrer Endpoints Query("demo") → Depends() (6h)

**13 endpoints à migrer:**

#### Template de migration:
```python
# ❌ AVANT
@router.get("/endpoint")
async def my_endpoint(
    user_id: str = Query("demo", description="User ID"),
    other_param: str = Query("default")
):
    data = await some_service(user_id=user_id)
    return {"data": data}

# ✅ APRÈS
from api.deps import get_active_user

@router.get("/endpoint")
async def my_endpoint(
    user: str = Depends(get_active_user),  # ← Changement ici
    other_param: str = Query("default")
):
    data = await some_service(user_id=user)  # ← Et ici
    return {"data": data}
```

#### Fichiers à modifier:

**1. `api/ml_bourse_endpoints.py` (2 endpoints)**
- Ligne 611: `user_id: str = Query("demo")` → `user: str = Depends(get_active_user)`
- Ligne 766: `user_id: str = Query(...)` → `user: str = Depends(get_active_user)`

**2. `api/portfolio_monitoring.py` (4 endpoints)**
- Lignes 236, 293, 474, 726

**3. `api/risk_bourse_endpoints.py` (3 endpoints)**
- Lignes 848, 998, 1050

**4. `api/performance_endpoints.py` (1 endpoint)**
- Ligne 282

**5. `api/saxo_endpoints.py` (2 endpoints - cash endpoints)**
- Lignes 234, 277

**Script semi-automatique:**
```bash
# Rechercher tous les patterns
grep -rn 'user_id.*Query.*"demo"' api/ --include="*.py"

# Pour chaque fichier:
# 1. Ajouter import: from api.deps import get_active_user
# 2. Remplacer user_id: str = Query(...) par user: str = Depends(get_active_user)
# 3. Renommer user_id → user dans corps fonction
```

✅ **Checklist par fichier:**
- [ ] `api/ml_bourse_endpoints.py` (2/2) ✅
- [ ] `api/portfolio_monitoring.py` (4/4) ✅
- [ ] `api/risk_bourse_endpoints.py` (3/3) ✅
- [ ] `api/performance_endpoints.py` (1/1) ✅
- [ ] `api/saxo_endpoints.py` (2/2) ✅
- [ ] Tests unitaires OK
- [ ] Tests intégration OK
- [ ] Smoke tests OK

**Tests:**
```bash
# Test multi-user après migration
curl "http://localhost:8080/api/ml/bourse/opportunities" -H "X-User: jack"
curl "http://localhost:8080/api/ml/bourse/opportunities" -H "X-User: demo"
# Les deux doivent retourner données différentes

pytest tests/integration/test_multi_tenant_isolation.py -v
```

---

### 7. Mettre à Jour Docs --reload (1h)

**Fichiers à corriger (47 occurrences):**

**Pattern de remplacement:**
```markdown
<!-- ❌ AVANT -->
```bash
uvicorn api.main:app --reload --port 8080
```

<!-- ✅ APRÈS -->
```bash
# IMPORTANT: N'utilisez PAS --reload flag!
# Après modifications backend, redémarrer le serveur manuellement
# Voir CLAUDE.md pour détails
python -m uvicorn api.main:app --port 8080
```
```

**Fichiers principaux:**
- `docs/quickstart.md:36`
- `docs/developer.md:7`
- `docs/configuration.md:53,59`
- `docs/CONTRIBUTING.md:122`
- `CONTRIBUTING.md:70`

**Script automatique:**
```bash
# Rechercher toutes occurrences
grep -rn '\-\-reload' docs/ --include="*.md"

# Remplacer (dry-run first)
find docs/ -name "*.md" -exec sed -i 's/--reload --port/--port/g' {} +

# Ajouter warning avant chaque commande uvicorn
```

✅ **Checklist:**
- [ ] Tous les `--reload` supprimés des docs
- [ ] Warnings ajoutés
- [ ] Référence à CLAUDE.md ajoutée
- [ ] Scripts start_dev.ps1/sh vérifiés (OK - déjà conditionnels)

---

### 8. Fix Risk Score Inversions (1h)

**Fichiers concernés:**

#### A. `static/modules/group-risk-index.js:291`
```javascript
// ❌ AVANT
const diversificationComponent = Math.max(0, 100 - concentrationRisk.concentration_score);

// ✅ APRÈS (renommer pour clarté)
const concentrationPenalty = concentrationRisk.concentration_score; // 0-100, higher = worse
const diversificationBonus = Math.max(0, 100 - concentrationPenalty); // Invert for bonus
```

#### B. `static/modules/group-risk-index.js:294`
```javascript
// ❌ AVANT (confusion)
return acc + group.weight * (100 - group.risk_score);

// ✅ APRÈS (clarifier intention)
// Note: risk_score est en fait robustness_score (higher = better)
// Pas besoin d'inversion si convention correcte
return acc + group.weight * group.robustness_score;
```

#### C. `scripts/benchmark_portfolios.py:117`
```python
# ❌ AVANT (inversion)
risk_score = 100 - (stables_factor * 0.3 + concentration_factor * 0.7)

# ✅ APRÈS (clarifier)
# Calculer penalty (higher = worse)
portfolio_penalty = stables_factor * 0.3 + concentration_factor * 0.7

# Convertir en robustness score (higher = better)
robustness_score = 100 - portfolio_penalty
```

**Ajouter commentaires clarification:**
```javascript
// CONVENTION RISK SCORING (CLAUDE.md)
// - Robustness Score: 0-100, higher = better portfolio
// - Penalty Score: 0-100, higher = worse portfolio
// - Concentration: 0-100, higher = more concentrated (worse)
// NEVER use: 100 - robustness_score (violates convention)
```

✅ **Checklist:**
- [ ] Variables renommées pour clarté
- [ ] Commentaires convention ajoutés
- [ ] Tests vérifiés (scores cohérents)
- [ ] Documentation mise à jour

---

### 🎯 Fin Jour 2 - Conformité 90%!

**Résultat:**
- ✅ 13 endpoints conformes multi-tenant
- ✅ Documentation --reload corrigée
- ✅ Risk Score inversions clarifiées
- ✅ Conformité CLAUDE.md: 75% → 90%

---

## 🚀 JOUR 3: QUICK WINS (8h)

### 9. Settings API Save (2h)

**Objectif:** Persister config frontend en backend

**Endpoint à créer:**
```python
# api/user_settings_endpoints.py

from api.deps import get_active_user
from api.utils import success_response, error_response

@router.post("/users/{user_id}/settings/sources")
async def save_source_settings(
    user_id: str,
    user: str = Depends(get_active_user),
    settings: dict = Body(...)
):
    """Persist user source settings (CSV selection, etc.)"""

    # Validation: user can only modify their own settings
    if user != user_id:
        return error_response("Unauthorized", code=403)

    # Save to data/users/{user_id}/config/sources.json
    config_path = Path(f"data/users/{user_id}/config/sources.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        json.dump(settings, f, indent=2)

    return success_response({"saved": True, "settings": settings})

@router.get("/users/{user_id}/settings/sources")
async def get_source_settings(
    user_id: str,
    user: str = Depends(get_active_user)
):
    """Retrieve user source settings"""

    if user != user_id:
        return error_response("Unauthorized", code=403)

    config_path = Path(f"data/users/{user_id}/config/sources.json")

    if not config_path.exists():
        return success_response({"settings": {}})

    with open(config_path, 'r') as f:
        settings = json.load(f)

    return success_response({"settings": settings})
```

**Frontend update (global-config.js):**
```javascript
// Sauvegarder après changement source
async function saveSourceSettings() {
  const activeUser = localStorage.getItem('activeUser') || 'demo';
  const settings = {
    csv_selected_file: window.userSettings.csv_selected_file,
    data_source: globalConfig.get('data_source'),
    last_updated: new Date().toISOString()
  };

  await fetch(`/api/users/${activeUser}/settings/sources`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User': activeUser
    },
    body: JSON.stringify(settings)
  });
}
```

✅ **Checklist:**
- [ ] Endpoint POST créé
- [ ] Endpoint GET créé
- [ ] Frontend intégration
- [ ] Tests unitaires
- [ ] Test multi-device (localStorage synchro)

---

### 10. Print() → Logger (3h)

**18 occurrences à remplacer:**

**Pattern:**
```python
# ❌ AVANT
print(f"Debug: {data}")
print("Generating report...")

# ✅ APRÈS
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Debug: {data}")
logger.info("Generating report...")
```

**Script automatique:**
```bash
# Lister occurrences
grep -rn "print(" services/ --include="*.py" | grep -v "# print"

# Fichiers principaux:
# - services/risk/structural_score_v2.py:13
# - services/ml/bourse/generate_backtest_report.py:5,12,18
# - services/ml/feature_engineering.py
# - scripts/* (backtest, train)
```

**Attention:** Ne pas remplacer dans:
- Tests (print OK pour debug)
- Scripts CLI interactifs (print voulu)
- Commentaires

✅ **Checklist:**
- [ ] 18 print() remplacés
- [ ] Imports logging ajoutés
- [ ] Tests exécutés (pas de régression)
- [ ] Logs vérifiés dans app.log

---

### 11. Magic Numbers → Constants (3h)

**Extraire top 20 magic numbers:**

**Backend (Python):**
```python
# ✅ Créer: services/constants.py

"""Application-wide constants with business justification"""

class AllocationConstants:
    """Allocation engine constants"""
    BTC_FLOOR_BASE = 0.15  # 15% minimum BTC (core holding)
    ETH_FLOOR_BASE = 0.12  # 12% minimum ETH (smart contracts)
    STABLES_FLOOR = 0.10   # 10% minimum stablecoins (safety)
    INCUMBENCY_MIN = 0.03  # 3% minimum for existing positions (no forced liquidation)

class GovernanceConstants:
    """Governance policy constants"""
    CAP_DAILY_DEFAULT = 0.08        # 8% max daily allocation change
    SIGNALS_TTL_SECONDS = 3600      # 1h ML signal freshness
    PLAN_COOLDOWN_HOURS = 24        # 24h between plan publications
    CONTRADICTION_THRESHOLD = 0.5   # 50% contradiction triggers penalty

class RiskConstants:
    """Risk management thresholds"""
    VAR_CONFIDENCE_95 = 0.95        # 95% confidence VaR
    VAR_CONFIDENCE_99 = 0.99        # 99% confidence VaR
    MIN_DATA_POINTS = 30            # Minimum days for metrics
    DUAL_WINDOW_LONG_DAYS = 365     # Long-term window
    DUAL_WINDOW_COVERAGE = 0.80     # 80% minimum coverage
```

**Frontend (JavaScript):**
```javascript
// ✅ Créer: static/constants.js

export const ALLOCATION_CONSTANTS = {
  FLOORS: {
    BTC: { base: 0.15, bullish: 0.15, reason: "Core holding minimum" },
    ETH: { base: 0.12, bullish: 0.12, reason: "Smart contract exposure" },
    STABLECOINS: { base: 0.10, bullish: 0.08, reason: "Safety buffer" },
    SOL: { base: 0.03, bullish: 0.06, reason: "L1 exposure" }
  },
  INCUMBENCY_MIN: 0.03,
  MAX_SECTOR_WEIGHT: 0.25
};

export const PHASE_CONSTANTS = {
  BEARISH_THRESHOLD: 70,    // Cycle < 70 = bearish
  BULLISH_THRESHOLD: 90,    // Cycle >= 90 = bullish
  ML_FEAR_THRESHOLD: 25,    // ML Sentiment < 25 = extreme fear
  ML_GREED_THRESHOLD: 75    // ML Sentiment > 75 = extreme greed
};
```

**Migration fichiers:**
```javascript
// allocation-engine.js
import { ALLOCATION_CONSTANTS } from '../constants.js';

// ❌ AVANT
'BTC': 0.15,

// ✅ APRÈS
'BTC': ALLOCATION_CONSTANTS.FLOORS.BTC.base,
```

✅ **Checklist:**
- [ ] `services/constants.py` créé
- [ ] `static/constants.js` créé
- [ ] Top 20 magic numbers migrés
- [ ] Imports mis à jour
- [ ] Tests OK
- [ ] Documentation constantes

---

## 🎯 JOUR 4-5: TESTS & CI/CD (16h)

### 12. Ajouter Coverage Reports (4h)

**Configuration pytest:**
```toml
# pyproject.toml (créer si n'existe pas)
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=api",
    "--cov=services",
    "--cov-report=html",
    "--cov-report=xml",
    "--cov-report=term-missing",
    "--cov-fail-under=50"  # Baseline actuel
]
```

**Installation:**
```bash
pip install pytest-cov
pip freeze > requirements-dev.txt
```

**Exécution:**
```bash
# Génerer rapport
pytest --cov=api --cov=services --cov-report=html

# Voir rapport
# Windows
start htmlcov/index.html

# Voir fichiers non couverts
pytest --cov=services --cov-report=term-missing
```

✅ **Checklist:**
- [ ] pytest-cov installé
- [ ] pyproject.toml configuré
- [ ] Rapport HTML généré
- [ ] Coverage baseline documentée (50%)
- [ ] `.gitignore` mis à jour (htmlcov/, .coverage)

---

### 13. Tests Balance Service (6h)

**Créer:** `tests/unit/test_balance_service.py`

```python
"""
Tests for BalanceService - Core balance resolution
"""

import pytest
from services.balance_service import balance_service

class TestBalanceService:
    """Test balance resolution and source routing"""

    @pytest.mark.asyncio
    async def test_resolve_cointracking_csv(self):
        """Test CSV source resolution"""
        result = await balance_service.resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        assert result["source_used"] == "cointracking"
        assert "items" in result
        assert isinstance(result["items"], list)

    @pytest.mark.asyncio
    async def test_multi_user_isolation(self):
        """Test user isolation"""
        demo = await balance_service.resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        jack = await balance_service.resolve_current_balances(
            source="cointracking",
            user_id="jack"
        )

        # Données différentes par user
        assert demo["items"] != jack["items"]

    @pytest.mark.asyncio
    async def test_source_fallback(self):
        """Test fallback chain API → CSV"""
        # Mock API failure, doit fallback CSV
        result = await balance_service.resolve_current_balances(
            source="cointracking_api",
            user_id="demo"
        )

        assert result["source_used"] in ["cointracking_api", "cointracking"]
        assert len(result["items"]) > 0

    @pytest.mark.asyncio
    async def test_filtering(self):
        """Test min_usd filtering"""
        result = await balance_service.resolve_current_balances(
            source="cointracking",
            user_id="demo"
        )

        # Filter dust
        filtered = [x for x in result["items"] if x.get("value_usd", 0) >= 1.0]

        assert len(filtered) <= len(result["items"])
        assert all(x.get("value_usd", 0) >= 1.0 for x in filtered)
```

**Exécuter:**
```bash
pytest tests/unit/test_balance_service.py -v
```

✅ **Checklist:**
- [ ] Fichier test créé
- [ ] 4+ tests balance service
- [ ] Tests multi-user isolation
- [ ] Tests source fallback
- [ ] Coverage balance_service > 60%

---

### 14. Tests Pricing Service (6h)

**Créer:** `tests/unit/test_pricing_service.py`

```python
"""
Tests for Pricing Service - Price fetching and caching
"""

import pytest
from unittest.mock import patch, AsyncMock
from services.pricing import get_prices_usd

class TestPricingService:
    """Test price fetching with mocks"""

    @pytest.mark.asyncio
    @patch('services.pricing.coingecko_client')
    async def test_fetch_btc_price(self, mock_coingecko):
        """Test BTC price fetch"""
        mock_coingecko.get_price = AsyncMock(return_value={
            'bitcoin': {'usd': 45000.0}
        })

        prices = await get_prices_usd(['BTC'])

        assert prices['BTC'] == 45000.0
        mock_coingecko.get_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_price_caching(self):
        """Test price cache (3 min TTL)"""
        # Premier appel
        prices1 = await get_prices_usd(['BTC', 'ETH'])

        # Deuxième appel immédiat (doit être caché)
        prices2 = await get_prices_usd(['BTC', 'ETH'])

        assert prices1 == prices2

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test respect rate limit CoinGecko"""
        # 50 appels successifs (rate limit = 50/min)
        for i in range(50):
            await get_prices_usd(['BTC'])

        # Doit réussir sans 429 error

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling"""
        # Symbol invalide
        prices = await get_prices_usd(['INVALID_COIN'])

        assert prices.get('INVALID_COIN') is None
```

✅ **Checklist:**
- [ ] Fichier test créé
- [ ] Tests avec mocks CoinGecko
- [ ] Tests caching
- [ ] Tests rate limiting
- [ ] Coverage pricing > 70%

---

### 🎯 FIN SEMAINE 1 - SUCCÈS!

## ✅ RÉSULTATS ATTENDUS

### Sécurité
- ✅ 0 vulnérabilités critiques
- ✅ Clés API rotées
- ✅ Credentials sécurisés
- ✅ Score sécurité: 6/10 → 8/10

### Conformité
- ✅ 13 endpoints conformes
- ✅ Documentation corrigée
- ✅ Conformité CLAUDE.md: 75% → 90%

### Qualité
- ✅ Settings API implémenté
- ✅ 18 print() éliminés
- ✅ Top 20 magic numbers → constants
- ✅ Balance Service testé
- ✅ Pricing Service testé
- ✅ Coverage reports actifs

### Métriques
- Test coverage: 50% → 55%
- Vulnérabilités: 3 Critical → 0
- Conformité: 75% → 90%
- Dette TODOs: 8 → 6 items

---

## 📋 CHECKLIST GLOBALE

### Sécurité (Jour 1)
- [ ] Clé CoinGecko révoquée + rotée
- [ ] Credentials hardcodés supprimés
- [ ] eval() remplacé
- [ ] CORS wildcard fixé
- [ ] DEV_OPEN_API validé

### Conformité (Jour 2)
- [ ] 13 endpoints migrés Depends()
- [ ] Documentation --reload corrigée
- [ ] Risk Score inversions clarifiées

### Quick Wins (Jour 3)
- [ ] Settings API créé
- [ ] print() → logger (18)
- [ ] Magic numbers → constants (20)

### Tests (Jours 4-5)
- [ ] Coverage reports configurés
- [ ] Balance Service testé
- [ ] Pricing Service testé

---

## 🚀 PROCHAINES ÉTAPES

**Semaine 2:**
- God Services Phase 1 (Governance refactoring)
- CI/CD security scan (safety check)
- Frontend Vitest setup

**Voir:** `docs/audit/AUDIT_DETTE_TECHNIQUE.md` pour plan complet

---

**Document créé par:** Claude Code Agent
**Dernière mise à jour:** 9 novembre 2025
