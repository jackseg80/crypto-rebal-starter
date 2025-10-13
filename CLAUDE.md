# CLAUDE.md — Guide Agent Crypto Rebal Starter

> Version condensée pour agents IA. Source canonique: `AGENTS.md`
> Dernière mise à jour: Oct 2025

## 🎯 Règles Critiques

### 1. Multi-Tenant OBLIGATOIRE ⚠️
```python
# Backend: TOUJOURS passer user_id + source
@app.get("/endpoint")
async def endpoint(
    source: str = Query("cointracking"),
    user_id: str = Query("demo")  # OBLIGATOIRE
):
    res = await resolve_current_balances(source=source, user_id=user_id)
```

```javascript
// Frontend: TOUJOURS utiliser window.loadBalanceData()
const balanceResult = await window.loadBalanceData(true);
// ❌ NE JAMAIS: fetch(`/balances/current?...`)
```

**Isolation:** `data/users/{user_id}/{source}/` (chaque user = dossier séparé)

### 2. Risk Score = Positif (0-100)
- **Convention:** Plus haut = plus robuste
- **DI Formula:** `DI = wCycle·scoreCycle + wOnchain·scoreOnchain + wRisk·scoreRisk`
- **❌ INTERDIT:** Ne jamais inverser avec `100 - scoreRisk`

### 3. Autres Règles
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

### Sources (priorité décroissante)
1. `snapshots/` - Dernière version active
2. `imports/` - Fichiers validés
3. `uploads/` - Zone de dépôt
4. API externe (cointracking_api)

### Structure User
```
data/users/{user_id}/
  cointracking/
    uploads/      # CSV uploadés
    imports/      # CSV validés
    snapshots/    # Version active
  saxobank/       # Idem structure
  config.json     # Config user
```

### P&L Today
- Snapshots dans `data/portfolio_history.json`
- Clé: `(user_id, source)`
- Endpoint: `/portfolio/metrics?user_id=X&source=Y`

---

## 🔧 Patterns de Code

### Endpoint API
```python
@router.get("/metrics")
async def get_metrics(
    source: str = Query("cointracking"),
    user_id: str = Query("demo"),
    min_usd_threshold: float = Query(1.0)
):
    # Toujours propager user_id + source
    data = await service.get_data(user_id, source)
    # Filtrer dust assets
    return [x for x in data if x.value_usd >= min_usd_threshold]
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
python -m uvicorn api.main:app --reload --port 8000

# Tests
pytest -q tests/unit
pytest -q tests/integration
```

---

## 🚨 Pièges Fréquents

❌ **Oublier user_id** → Toujours 'demo' par défaut
❌ **Hardcoder user_id='demo'** dans le code
❌ **fetch() direct** au lieu de window.loadBalanceData()
❌ **Mélanger données users** dans caches/fichiers
❌ **Inverser Risk Score** dans Decision Index

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

### Phase Engine
- Détection phases market (ETH expansion, altseason, risk-off)
- `localStorage.setItem('PHASE_ENGINE_ENABLED', 'shadow')`
- Debug: `window.debugPhaseEngine.forcePhase('risk_off')`

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

- Architecture: `docs/ARCHITECTURE.md`
- Risk: `docs/RISK_SEMANTICS.md`, `docs/RISK_SCORE_V2_IMPLEMENTATION.md`
- P&L: `docs/P&L_TODAY_USAGE.md`
- Multi-tenant: `docs/SIMULATOR_USER_ISOLATION_FIX.md`
- Wealth: `docs/TODO_WEALTH_MERGE.md`

---

*Guide condensé de 1122 → 250 lignes. Pour détails complets, voir version originale ou docs spécifiques.*