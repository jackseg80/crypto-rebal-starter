# GEMINI.md — Contexte rapide (Crypto Rebal Starter)

## Environnement
- **OS**: Windows 11  
- **Shell**: PowerShell  
- **Backend**: Python >=3.11 • FastAPI • Postgres  
- **Frontend**: HTML/JS (ESM, Chart.js, stores, localStorage cache)  
- **Lancement**: `.\.venv\Scripts\activate.ps1 ; uvicorn api.main:app --reload`

## Règles générales
- ❌ Pas d'URL en dur → utiliser `static/global-config.js`
- ✅ Respecter caches/TTL (`risk_scores_cache`, 12h) et système cross-tab
- ❌ Pas de nouveaux endpoints temps réel (`/realtime/publish`, `/broadcast`)
- ✅ Toujours produire des **git diff unifiés minimaux** (pas de refactors massifs)
- ⚠️ **Sémantique Risk** : Voir [docs/RISK_SEMANTICS.md](docs/RISK_SEMANTICS.md)  

## Fichiers pivots
- **P&L Today**  
  - Backend : `api/performance_endpoints.py`  
  - Frontend : `static/dashboard.html`, `static/modules/**`  

- **Risk / Phase**  
  - `static/core/risk-dashboard-store.js`  
  - `static/core/phase-engine.js`  
  - `static/risk-dashboard.html`  

- **ML Orchestrator / Analytics**  
  - `services/ml/orchestrator.py`  
  - API : `/api/ml/*`  
  - Frontend : `static/analytics-unified.html`  

## Sortie exigée
Toujours livrer :  
1. 📋 Un plan E2E (flux global, étapes backend → frontend)  
2. 📂 La liste des fichiers impactés  
3. ⏱️ Validation caches/TTL et respect des règles (URLs, stores, cap unique)  
4. 📝 Un **git diff minimal** (unifié, clair, sans reformattage inutile)  
