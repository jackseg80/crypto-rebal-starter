# Système P&L Today - Documentation

## Vue d'ensemble

Le système P&L Today fournit un calcul fiable du profit/perte journalier basé sur des **snapshots historiques**. Chaque combinaison (user_id, source) maintient son propre historique de snapshots pour un tracking P&L indépendant.

**Date de mise à jour:** Septembre 2025

## Architecture

### Backend

**Endpoints disponibles:**
- `GET /portfolio/metrics?source={source}&user_id={user_id}` - Métriques + P&L Today
- `POST /portfolio/snapshot?source={source}&user_id={user_id}` - Créer un snapshot

**Service principal:** `services/portfolio.py`
- `calculate_performance_metrics()` - Calcul P&L par comparaison snapshots
- `save_portfolio_snapshot()` - Sauvegarde snapshot avec user_id/source
- `_load_historical_data()` - Charge snapshots filtrés par (user_id, source)

**Fonctionnalités:**
- Snapshots multi-tenant isolés par (user_id, source)
- Stockage centralisé dans `data/portfolio_history.json`
- Calcul P&L: `current_value - latest_snapshot_value`
- Limite: 365 snapshots par combinaison (user_id, source)
- Groupage et tri automatique par (user_id, source)

**Structure de réponse `/portfolio/metrics`:**
```json
{
  "ok": true,
  "metrics": {
    "total_value_usd": 133100.00,
    "asset_count": 5,
    "group_count": 3,
    "diversity_score": 2,
    "top_holding": {
      "symbol": "ETH",
      "value_usd": 75000.00,
      "percentage": 0.56
    },
    "group_distribution": {...},
    "last_updated": "2025-09-30T13:34:00.223805"
  },
  "performance": {
    "performance_available": true,
    "current_value_usd": 133100.00,
    "historical_value_usd": 130000.00,
    "absolute_change_usd": 3100.00,
    "percentage_change": 2.38,
    "days_tracked": 1,
    "annualized_return_estimate": 868.7,
    "performance_status": "gain",
    "comparison_date": "2025-09-29T08:00:00",
    "historical_entries_count": 2
  }
}
```

**Structure snapshot dans `portfolio_history.json`:**
```json
{
  "date": "2025-09-30T13:34:39.940690",
  "user_id": "jack",
  "source": "cointracking",
  "total_value_usd": 133100.00,
  "asset_count": 5,
  "group_count": 3,
  "diversity_score": 2,
  "top_holding_symbol": "ETH",
  "top_holding_percentage": 0.56,
  "group_distribution": {...}
}
```

### Frontend (`static/dashboard.html`)

**Intégration:**
- Fonction `loadRealCSVPortfolioData()` charge données + P&L
- Appel API: `/portfolio/metrics?source=${currentSource}&user_id=${activeUser}`
- Affichage dans tuile "Portfolio Overview"
- P&L affiché avec couleur selon gain/perte

**Code clé (lignes 1186-1203):**
```javascript
const activeUser = localStorage.getItem('activeUser') || 'demo';
const pnlUrl = `${window.location.origin}/portfolio/metrics?source=${currentSource}&user_id=${activeUser}`;
const pnlResponse = await fetch(pnlUrl);

if (pnlResponse.ok) {
    const pnlData = await pnlResponse.json();
    if (pnlData.ok && pnlData.performance && pnlData.performance.performance_available) {
        performance = pnlData.performance;
    }
}
```

**Affichage UX:**
- Format: `$3,100.00` avec couleur verte (gain) ou rouge (perte)
- Indique "No historical data" si moins de 2 snapshots
- Synchronisation automatique avec localStorage (`activeUser`, `currentSource`)

## Tests

### Scripts PowerShell

**test_pnl_separation.ps1** - Validation isolation P&L par (user_id, source):
```powershell
.\test_pnl_separation.ps1
```

**tests_save_snapshot.ps1** - Création snapshots manuels:
```bash
.\tests_save_snapshot.ps1 -Source cointracking -UserId jack
.\tests_save_snapshot.ps1 -Source cointracking_api -UserId jack
```

### Tests manuels API

**Créer un snapshot:**
```bash
curl -X POST "http://localhost:8000/portfolio/snapshot?source=cointracking&user_id=jack"
```

**Consulter P&L:**
```bash
curl "http://localhost:8000/portfolio/metrics?source=cointracking&user_id=jack" | python -m json.tool
```

**Vérifier isolation des sources:**
```bash
# CSV (5 assets, 133k USD)
curl -s "http://localhost:8000/portfolio/metrics?source=cointracking&user_id=jack"

# API (190+ assets, 423k USD)
curl -s "http://localhost:8000/portfolio/metrics?source=cointracking_api&user_id=jack"
```

### Tests frontend

1. Ouvrir `http://localhost:8000/static/dashboard.html`
2. Sélectionner user "jack" et source "cointracking"
3. Vérifier P&L Today dans tuile Portfolio Overview
4. Changer de source → P&L doit être différent (ou 0 si pas de snapshots)

## Configuration

### Stockage
- Fichier: `data/portfolio_history.json`
- Format: JSON array avec tous les snapshots multi-tenant
- Rotation: 365 derniers jours par (user_id, source)
- Backup: Recommandé avant migrations

### Isolation par source
Chaque combinaison (user_id, source) est indépendante:
- `jack + cointracking` (CSV local) → historique séparé
- `jack + cointracking_api` (API externe) → historique séparé
- `demo + cointracking` → historique séparé

### Snapshots automatiques
Pour activer snapshots quotidiens automatiques (optionnel):
1. Créer un cron/task scheduler
2. Appeler `/portfolio/snapshot` pour chaque (user_id, source)
3. Exemple cron: `0 0 * * * curl -X POST "http://localhost:8000/portfolio/snapshot?source=cointracking&user_id=jack"`

## Monitoring

### Logs importants
```python
# services/portfolio.py
logger.info(f"Loaded {len(filtered)} historical entries for user={user_id}, source={source}")
logger.info(f"Portfolio snapshot sauvé ({total_value_usd:.2f} USD) for user={user_id}, source={source}")
```

### Métriques à surveiller
- Nombre d'entrées par (user_id, source)
- Taille du fichier `portfolio_history.json`
- Fréquence des snapshots (idéalement 1/jour)
- P&L aberrants (> ±50% en 1 jour → alerte)

### Dashboard console
```javascript
// Depuis la console browser sur dashboard.html
console.log('Active user:', localStorage.getItem('activeUser'));
console.log('Current source:', localStorage.getItem('currentSource'));
```

## Troubleshooting

### P&L toujours à 0$
**Cause:** Un seul snapshot disponible pour cette source
**Solution:** Attendre le prochain snapshot ou en créer un manuellement

### P&L aberrant (-289k$ sur portfolio 133k$)
**Cause:** Snapshot historique créé avec mauvaises données (autre source)
**Solution:**
```bash
# Supprimer snapshots incorrects
python -c "import json; h=json.load(open('data/portfolio_history.json')); cleaned=[e for e in h if not (e.get('user_id')=='jack' and e.get('source')=='cointracking')]; json.dump(cleaned, open('data/portfolio_history.json','w'), indent=2)"

# Créer nouveau snapshot valide
curl -X POST "http://localhost:8000/portfolio/snapshot?source=cointracking&user_id=jack"
```

### CSV charge mauvaises données
**Cause:** Serveur uvicorn non redémarré après changement fichiers
**Solution:** Redémarrer serveur: `uvicorn api.main:app --reload --port 8000`

### "No historical data available"
**Cause:** Aucun snapshot pour cette combinaison (user_id, source)
**Solution:** Créer premier snapshot via API POST

## Maintenance

### Nettoyage snapshots anciens
```python
# Garder seulement 90 derniers jours au lieu de 365
python -c "
import json
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(days=90)
h = json.load(open('data/portfolio_history.json'))
recent = [e for e in h if datetime.fromisoformat(e['date'].replace('Z', '+00:00')) > cutoff]
json.dump(recent, open('data/portfolio_history.json', 'w'), indent=2)
print(f'Kept {len(recent)}/{len(h)} snapshots')
"
```

### Migration données
Lors d'ajout de nouveaux champs dans les snapshots, migrer l'historique:
```python
import json
h = json.load(open('data/portfolio_history.json'))
for entry in h:
    entry.setdefault('user_id', 'demo')  # Valeur par défaut
    entry.setdefault('source', 'cointracking')
json.dump(h, open('data/portfolio_history.json', 'w'), indent=2)
```