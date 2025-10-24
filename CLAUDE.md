# CLAUDE.md — Guide Agent Crypto Rebal Starter

> Version condensée pour agents IA. Source canonique: `AGENTS.md`
> Dernière mise à jour: Oct 2025

## 🎯 Règles Critiques

### 1. Multi-Tenant OBLIGATOIRE ⚠️
```python
# Backend: TOUJOURS utiliser les dependencies ou BalanceService
from api.deps import get_active_user
from services.balance_service import balance_service

@app.get("/endpoint")
async def endpoint(
    user: str = Depends(get_active_user),
    source: str = Query("cointracking")
):
    res = await balance_service.resolve_current_balances(source=source, user_id=user)
```

```javascript
// Frontend: TOUJOURS utiliser window.loadBalanceData()
const balanceResult = await window.loadBalanceData(true);
// ❌ NE JAMAIS: fetch(`/balances/current?...`)
```

**Isolation:** `data/users/{user_id}/{source}/` (chaque user = dossier séparé)

### 2. Risk Score = Positif (0-100)
- **Convention:** Plus haut = plus robuste
- **❌ INTERDIT:** Ne jamais inverser avec `100 - scoreRisk`
- **⚠️ ATTENTION:** Le Decision Index N'EST PAS une somme pondérée (voir règle #3)

### 3. Système Dual de Scoring ⚠️
**Deux systèmes parallèles avec objectifs différents:**

| Métrique | Formule | Valeur | Usage |
|----------|---------|--------|-------|
| **Score de Régime** | `0.5×CCS + 0.3×OnChain + 0.2×Risk` | Variable (0-100) | Régime marché |
| **Decision Index** | `total_check.isValid ? 65 : 45` | Fixe (65/45) | Qualité allocation |

**Règles:**
- Score de Régime (ex: 55) → Détermine régime (Accumulation/Expansion/Euphorie)
- Decision Index (65 ou 45) → Qualité technique de l'allocation V2
- **Phase != Régime**: Phase basée UNIQUEMENT sur cycle (<70=bearish, 70-90=moderate, ≥90=bullish)
- Régime "Expansion" (55) + Phase "bearish" (cycle 59<70) est NORMAL!
- Ne PAS forcer la convergence entre les deux!
- Voir [`docs/DECISION_INDEX_V2.md`](docs/DECISION_INDEX_V2.md) pour détails

**Phase Detection (allocation-engine.js ligne 180):**
- Cycle < 70 → Phase "bearish" (allocation conservatrice)
- Cycle 70-90 → Phase "moderate"
- Cycle ≥ 90 → Phase "bullish" (floors agressifs)

**Overrides (sur allocation, pas sur DI/Régime):**
- **ML Sentiment <25** → Force allocation défensive (+10 pts stables)
  - ⚠️ "ML Sentiment" = Sentiment ML agrégé (`/api/ml/sentiment/symbol/BTC`)
  - PAS le Fear & Greed Index officiel (alternative.me)
  - Calcul: `50 + (sentiment_ml × 50)` où sentiment ∈ [-1, 1]
  - Ex: sentiment 0.6 → 80 (Extreme Greed), sentiment -0.4 → 30 (Fear)
  - Affiché dans Decision Index Panel et analytics-unified.html
- Contradiction >50% → Pénalise On-Chain/Risk (×0.9)
- Structure Score <50 → +10 pts stables

### 4. Design & Responsive

- **Full responsive** : Toutes les pages principales utilisent `max-width: none`
- **Adaptive padding** : Plus d'espace sur grands écrans (2000px+)
- **Grid auto-fit** : `repeat(auto-fit, minmax(300px, 1fr))` pour adaptation automatique
- **Breakpoints cohérents** : 768px (mobile), 1024px (tablet), 1400px (desktop), 2000px (XL)
- **Pas de largeur fixe** : Éviter `max-width: 1200px` ou similaires

### 5. Autres Règles
- Ne jamais committer `.env` ou clés
- Pas d'URL API en dur → `static/global-config.js`
- Modifications minimales, pas de refonte sans demande
- Windows: `.venv\Scripts\Activate.ps1` avant tout

---

## 📁 Architecture Essentielle

### Pages Production
```
dashboard.html          # Vue globale + P&L Today
analytics-unified.html  # ML temps réel + Decision Index
risk-dashboard.html     # Risk management + Governance
rebalance.html         # Plans de rééquilibrage
execution.html         # Exécution temps réel
simulations.html       # Simulateur complet
```

### API Namespaces
```
/balances/current      # Données portfolio (CSV/API)
/portfolio/metrics     # Métriques + P&L
/api/ml/*             # ML unifié
/api/risk/*           # Risk management
/api/wealth/*         # Cross-asset wealth
/api/sources/*        # Sources System v2
/execution/governance/* # Decision Engine
```

### Fichiers Clés
```
api/main.py                      # FastAPI app + routers
api/services/sources_resolver.py # Résolution données
services/portfolio.py            # P&L tracking
services/execution/governance.py # Decision Engine
services/ml/orchestrator.py     # ML orchestration
static/global-config.js          # Config frontend
static/components/nav.js         # Navigation
static/core/unified-insights-v2.js # Phase Engine
```

---

## 💾 Système de Données

### Sources Unifiées (Système data/)
1. **`data/`** - Dossier unique avec versioning automatique
2. **API externe** (cointracking_api)

**Principe**: Upload direct → disponible immédiatement
- Versioning automatique: `YYYYMMDD_HHMMSS_{filename}.csv`
- Sélection du plus récent par défaut
- Historique complet préservé

### Structure User
```
data/users/{user_id}/
  cointracking/
    data/         # Tous les CSV (versionnés automatiquement)
    api_cache/    # Cache API
  saxobank/
    data/         # Tous les CSV (versionnés automatiquement)
  config/
    config.json   # Config utilisateur
    sources.json  # Configuration modules
```

### P&L Today
- Snapshots dans `data/portfolio_history.json`
- Clé: `(user_id, source)`
- Endpoint: `/portfolio/metrics?user_id=X&source=Y`

---

## 🔧 Patterns de Code

### Endpoint API (Nouveau Pattern - Oct 2025)
```python
from api.deps import get_active_user
from api.utils import success_response, error_response
from services.balance_service import balance_service

@router.get("/metrics")
async def get_metrics(
    user: str = Depends(get_active_user),
    source: str = Query("cointracking"),
    min_usd: float = Query(1.0)
):
    # Utiliser BalanceService (pas api.main)
    res = await balance_service.resolve_current_balances(source=source, user_id=user)
    items = res.get("items", [])

    # Filtrer dust assets
    filtered = [x for x in items if x.get("value_usd", 0) >= min_usd]

    # Utiliser response formatters
    return success_response(filtered, meta={"count": len(filtered)})
```

### Response Formatting (Nouveau - Oct 2025)
```python
from api.utils import success_response, error_response, paginated_response

# Success response
return success_response(data, meta={"currency": "USD"})
# → {"ok": true, "data": {...}, "meta": {...}, "timestamp": "..."}

# Error response
return error_response("Not found", code=404, details={"id": "123"})
# → {"ok": false, "error": "...", "details": {...}, "timestamp": "..."}

# Paginated response
return paginated_response(items, total=100, page=1, page_size=50)
# → {"ok": true, "data": [...], "meta": {"pagination": {...}}, ...}
```

### Frontend Data Loading
```javascript
// TOUJOURS utiliser loadBalanceData
const activeUser = localStorage.getItem('activeUser') || 'demo';
const balanceResult = await window.loadBalanceData(true);

if (balanceResult.csvText) {
    // Source CSV
    balances = parseCSVBalancesAuto(balanceResult.csvText);
} else if (balanceResult.data?.items) {
    // Source API
    balances = balanceResult.data.items;
}
```

### Decision Index Panel
```javascript
import { renderDecisionIndexPanel } from './components/decision-index-panel.js';

const data = {
    di: 65,
    weights: { cycle: 0.65, onchain: 0.25, risk: 0.10 }, // Post-adaptatifs
    scores: { cycle: 100, onchain: 41, risk: 57 },
    history: [60, 62, 65, 67, 65, 68, 70], // ≥6 pour Trend Chip
    meta: { confidence: 0.82, mode: 'Priority' }
};
renderDecisionIndexPanel(container, data);
```

---

## ✅ Quick Checks

### Test Multi-User
```bash
# Users différents
curl "localhost:8000/balances/current?user_id=demo"
curl "localhost:8000/balances/current?user_id=jack"

# Sources différentes (même user)
curl "localhost:8000/portfolio/metrics?user_id=jack&source=cointracking"
curl "localhost:8000/portfolio/metrics?user_id=jack&source=cointracking_api"
```

### Dev Server
```bash
# Windows
.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --port 8000

# ⚠️ IMPORTANT: PAS de --reload flag!
# Après modifications backend → TOUJOURS demander à l'utilisateur de redémarrer manuellement
# "Veuillez redémarrer le serveur pour appliquer les changements"

# Tests
pytest -q tests/unit
pytest -q tests/integration
```

### Redis (Cache & Streaming)
```bash
# Vérifier si Redis tourne
redis-cli ping  # Doit répondre PONG

# Démarrer Redis (WSL2)
wsl -d Ubuntu bash -c "sudo service redis-server start"

# Config dans .env
REDIS_URL=redis://localhost:6379/0
```

**Utilisation:** Cache haute performance, alertes persistantes, streaming temps réel (4 streams: risk_events, alerts, market_data, portfolio_updates). Voir `docs/REDIS_SETUP.md` pour installation complète.

### Logs Serveur (Debug)
```bash
# Lire les logs en temps réel
Get-Content logs\app.log -Wait -Tail 20

# Chercher des erreurs
Select-String -Path "logs\app.log" -Pattern "ERROR|WARNING" | Select-Object -Last 20

# Analyser avec Claude Code
@logs/app.log  # Lire fichier complet (max 5 MB)
```

**Configuration:**
- **5 MB par fichier** (rotation automatique, optimisé pour IA)
- **3 backups** (15 MB total: app.log, app.log.1, app.log.2, app.log.3)
- Format: `YYYY-MM-DD HH:MM:SS,mmm LEVEL module: message`
- Sorties: Console + Fichier (UTF-8)

**Usage IA:** Les agents peuvent lire `logs/app.log` pour débugger erreurs, analyser performance, identifier patterns. Fichiers < 5 MB = facilement traitable.

---

## 🚨 Pièges Fréquents

❌ **Oublier user_id** → Utiliser `Depends(get_active_user)`
❌ **Hardcoder user_id='demo'** → Utiliser dependency injection
❌ **Importer de api.main** → Utiliser `services.balance_service` à la place
❌ **fetch() direct** au lieu de window.loadBalanceData()
❌ **Mélanger données users** dans caches/fichiers
❌ **Inverser Risk Score** dans Decision Index
❌ **Oublier de demander restart serveur** → Pas de --reload, toujours demander à l'utilisateur après modifs backend
❌ **Response format incohérent** → Utiliser success_response() / error_response()

---

## 📊 Features Avancées

### Dual-Window Metrics
- Évite Sharpe négatifs sur assets récents
- `/api/risk/dashboard?use_dual_window=true`
- Long-term (365j, 80% coverage) + Full intersection

### Risk Score V2 (Shadow Mode)
- Détecte portfolios "degen" (memecoins jeunes)
- `/api/risk/dashboard?risk_version=v2_shadow`
- Pénalités: -75 pts exclusion, -25 pts memes

### Phase Engine + Logique Contextuelle ML Sentiment (Oct 2025)
**Architecture hiérarchique à 3 niveaux:**

1. **NIVEAU 1 (Priorité Absolue):** Sentiments Extrêmes
   - `mlSentiment < 25` (Extreme Fear) + Bull → Opportuniste (boost ETH/SOL/DeFi)
   - `mlSentiment < 25` (Extreme Fear) + Bear → Défensif (réduit risky assets)
   - `mlSentiment > 75` (Extreme Greed) → Prise profits (toujours)

2. **NIVEAU 2 (Optimisations Tactiques):** Phase Engine
   - Détecte: ETH expansion, large-cap altseason, full altseason, risk-off
   - **Active par défaut** (`'apply'` mode)
   - Persistence: buffers localStorage (TTL 7 jours, 14 samples max)
   - Fallback intelligent: utilise DI + breadth si données partielles

3. **NIVEAU 3 (Fallback):** Modulateurs bull/bear standard
   - Désactivés si Phase Engine actif
   - Utilisés uniquement en dernier recours

**Commandes:**
- Phase Engine toujours actif (pas besoin de commande)
- Debug force phase: `window.debugPhaseEngine.forcePhase('risk_off')`
- Status buffers: `window.debugPhaseBuffers.getStatus()`
- Désactiver (non recommandé): `localStorage.setItem('PHASE_ENGINE_ENABLED', 'off')`

**Note:** Panneau "Phase Engine Beta" supprimé - système autonome

### Allocation Engine V2 - Topdown Hierarchical (Oct 2025)
**Architecture à 3 niveaux** ([allocation-engine.js](static/core/allocation-engine.js)):

**Niveau 1 - MACRO**: BTC, ETH, Stablecoins, Alts (total)
**Niveau 2 - SECTEURS**: SOL, L1/L0, L2/Scaling, DeFi, Memecoins, Gaming/NFT, AI/Data, Others
**Niveau 3 - COINS**: Assets individuels avec incumbency protection

**Mécanismes clés:**

#### Floors Contextuels
```javascript
// Floors de BASE (toujours)
BTC: 15%, ETH: 12%, Stablecoins: 10%, SOL: 3%

// Floors BULLISH (Cycle ≥ 90)
SOL: 3% → 6%, L2/Scaling: 3% → 6%, DeFi: 4% → 8%, Memecoins: 2% → 5%
```

#### Incumbency Protection
**Aucun asset détenu ne peut descendre sous 3%** → Évite liquidations forcées d'assets existants

#### Renormalisation Proportionnelle
```javascript
// Préserve stables EXACTEMENT, redistribue risky pool proportionnellement
nonStablesSpace = 1 - stablesTarget  // Ex: 75%
btcTarget = (baseBtcRatio / baseTotal) × nonStablesSpace
ethTarget = (baseEthRatio / baseTotal) × nonStablesSpace
```

### Stop Loss Intelligent - Multi-Method (Oct 2025)

**4 méthodes de calcul adaptatives** ([stop_loss_calculator.py](services/ml/bourse/stop_loss_calculator.py)):

**Méthodes :**

1. **ATR 2x** (Recommandé) - S'adapte à la volatilité, multiplier selon régime marché (1.5x-2.5x)
2. **Technical Support** - Basé sur MA20/MA50
3. **Volatility 2σ** - 2 écarts-types statistiques
4. **Fixed %** - Pourcentage fixe (legacy fallback)

**Frontend** ([saxo-dashboard.html](static/saxo-dashboard.html)):

- Tableau comparatif des 4 méthodes dans modal de recommendation
- Badge R/R avec icônes (✅ ≥2.0, ⚠️ ≥1.5, ❌ <1.5)
- Alerte automatique si R/R < 1.5 (trade non recommandé)
- Colonne R/R triable dans tableau principal (tri par défaut)
- Calcul du risque en € pour chaque méthode

**Détails complets :** [`docs/STOP_LOSS_SYSTEM.md`](docs/STOP_LOSS_SYSTEM.md)

### Governance - Freeze Semantics (Oct 2025)
**3 types de freeze avec opérations granulaires** ([governance.py](services/execution/governance.py)):

| Type | Achats | Ventes→Stables | Rotations Assets | Hedge | Réductions Risque |
|------|--------|----------------|------------------|-------|-------------------|
| **full_freeze** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **s3_alert_freeze** | ❌ | ✅ | ❌ | ✅ | ✅ |
| **error_freeze** | ❌ | ✅ | ❌ | ✅ | ✅ |

**Usage:**
- `full_freeze`: Urgence absolue (tout bloqué sauf sorties d'urgence)
- `s3_alert_freeze`: Alerte sévère (protection capital, hedge autorisé)
- `error_freeze`: Erreur technique (prudence, réductions risque prioritaires)

### TTL vs Cooldown (Critique!)
**Distinction essentielle** pour éviter spam UI ([governance.py:137-245](services/execution/governance.py)):

```python
signals_ttl_seconds = 1800      # 30 min: Signaux ML peuvent être rafraîchis
plan_cooldown_hours = 24        # 24h: Publications plans limitées
```

**Permet** : Rafraîchir signaux backend toutes les 30min SANS publier nouveau plan toutes les 30min !

### Cap Stability (Hystérésis Anti Flip-Flop)
**3 variables d'état** pour smoothing ([governance.py:247-250](services/execution/governance.py)):

```python
_last_cap = 0.08                # Dernière cap calculée (smoothing EMA)
_prudent_mode = False           # État hystérésis (Schmitt trigger)
_alert_cap_reduction = 0.0      # Override AlertEngine
```

**+ Hystérésis Memecoins** ([risk_scoring.py:186-200](services/risk_scoring.py)):
```python
# Zone transition 48-52%: interpolation linéaire (évite flip-flop -10 ↔ -15)
if memecoins_pct >= 0.48 and memecoins_pct <= 0.52:
    t = (memecoins_pct - 0.48) / 0.04
    delta = -10 + t * (-15 - (-10))  # Transition douce
```

### WealthContextBar
- Change source depuis n'importe quelle page
- Menu "Compte" → Sélection CSV/API → Reload auto
- Synchronise localStorage + backend

---

## 📝 Commandes Utiles

```bash
# Créer snapshot P&L
curl -X POST "localhost:8000/portfolio/snapshot?user_id=jack&source=cointracking"

# Créer compte bancaire
curl -X POST "localhost:8000/api/wealth/banks/accounts" \
  -H "X-User: jack" \
  -d '{"bank_name":"UBS","balance":5000,"currency":"CHF"}'

# Git avec message formaté
git commit -m "$(cat <<'EOF'
feat: description courte

Description détaillée...

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

## 🔗 Docs Détaillées

### Architecture & Design
- Architecture: `docs/ARCHITECTURE.md`
- Code Quality: `AUDIT_REPORT_2025-10-19.md` (audit complet)
- Refactoring Plans: `GOD_SERVICES_REFACTORING_PLAN.md`
- Code Consolidation: `DUPLICATE_CODE_CONSOLIDATION.md`

### Features & Systems
- **Allocation**: `docs/ALLOCATION_ENGINE_V2.md` (topdown hierarchical, floors, incumbency)
- **Decision Index**: `docs/DECISION_INDEX_V2.md` (système dual scoring, DI vs Régime)
- **Risk**: `docs/RISK_SEMANTICS.md`, `docs/RISK_SCORE_V2_IMPLEMENTATION.md`
- **Structure**: `docs/STRUCTURE_MODULATION_V2.md` (garde-fou allocation, deltaCap)
- **Governance**: `docs/GOVERNANCE_FIXES_OCT_2025.md` (freeze semantics, TTL vs Cooldown)
- **Cap Stability**: `docs/CAP_STABILITY_FIX.md` (hystérésis, anti flip-flop)
- **P&L**: `docs/P&L_TODAY_USAGE.md`
- **Multi-tenant**: `docs/SIMULATOR_USER_ISOLATION_FIX.md`
- **Wealth**: `docs/TODO_WEALTH_MERGE.md`
- **Sources**: `docs/SOURCES_MIGRATION_DATA_FOLDER.md`
- **Logging**: `docs/LOGGING.md` (système de logs rotatifs pour debug/IA)
- **Redis**: `docs/REDIS_SETUP.md` (installation, config, cache & streaming)

### Session Notes
- Latest: `SESSION_RESUME_2025-10-20.md` (dependency injection + consolidation)

---

*Guide condensé de 1122 → 250 lignes. Pour détails complets, voir version originale ou docs spécifiques.*