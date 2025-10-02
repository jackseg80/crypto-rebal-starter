# Quickstart

## Prérequis
- Python 3.10+
- `pip install -r requirements.txt`

## Configuration
1. Copiez `env.example` vers `.env` et renseignez vos clés CoinTracking (CT_API_KEY/CT_API_SECRET).
   - Linux/macOS: `cp env.example .env`
   - Windows (PowerShell): `copy env.example .env`
2. Optionnel: `CORS_ORIGINS` pour servir l’UI depuis une autre origine.
3. Ouvrez `static/settings.html` pour configurer:
   - La source de données (démo/CSV/API) — liste centralisée.
   - La devise d’affichage (USD/EUR/BTC). La conversion est réelle à l’affichage; si le taux est temporairement indisponible, l’UI affiche `—`.

## Lancer l'API

**Méthode recommandée** (avec scripts) :

Linux/macOS:
```bash
./start_dev.sh          # FastAPI native avec Playwright (défaut)
./start_dev.sh 0        # Mode Flask proxy (legacy)
```

Windows (PowerShell):
```powershell
.\start_dev.ps1                    # FastAPI native (défaut)
.\start_dev.ps1 -CryptoToolboxMode 0   # Flask proxy (legacy)
```

**Méthode manuelle** :

Linux/macOS:
```bash
uvicorn api.main:app --reload --port 8000
```

Windows (PowerShell):
```powershell
python -m uvicorn api.main:app --port 8000
# Note: --reload désactivé sur Windows pour compatibilité Playwright
```

## Ouvrir l’UI
- Rebalance: `static/rebalance.html`
- Dashboard: `static/dashboard.html`
- Risk Dashboard: `static/risk-dashboard.html`
- Execution: `static/execution.html`
- Alias Manager: `static/alias-manager.html`
- Monitoring: `static/monitoring.html`
- Monitoring avancé: `static/monitoring_advanced.html`

Astuce: la barre de navigation unifiée est chargée automatiquement sur la plupart des pages (désactivable avec `?nav=off`).

## Endpoints essentiels
- GET `/healthz`
- GET `/balances/current`
- POST `/rebalance/plan`
- GET `/portfolio/metrics`

Pour l’ensemble des endpoints: voir `docs/api.md`.
