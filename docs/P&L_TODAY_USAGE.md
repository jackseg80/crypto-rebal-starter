# P&L Today - Guide d'Utilisation

## Vue d'ensemble

L'endpoint `/api/performance/summary` calcule le **Profit & Loss (P&L)** du portfolio depuis un point d'ancrage temporel configurable.

## Architecture

### Composants Principaux

1. **Endpoint API** : `/api/performance/summary` (`api/performance_endpoints.py`)
2. **Service Portfolio** : `services/portfolio.py` (calculs P&L, snapshots)
3. **Stockage** : `data/portfolio_history.json` (snapshots historiques)

### Workflow

```
┌─────────────────┐
│  Portfolio      │
│  actuel         │ ──┐
└─────────────────┘   │
                      ├──> Calcul P&L
┌─────────────────┐   │    (absolute_change_usd)
│  Snapshot       │   │    (percent_change)
│  historique     │ ──┘
└─────────────────┘
```

## Utilisation de l'API

### Endpoint Principal

```http
GET /api/performance/summary?user_id={user}&source={source}&anchor={anchor}
```

#### Paramètres

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `user_id` | string | "demo" | ID de l'utilisateur |
| `source` | string | "cointracking" | Source de données (cointracking, saxobank, etc.) |
| `anchor` | string | "prev_close" | Point d'ancrage temporel |

#### Anchor Points Supportés

- **`prev_close`** : Début du jour actuel (00:00 pour crypto 24/7)
- **`midnight`** : Identique à prev_close (00:00 en Europe/Zurich)
- **`session`** : Dernier snapshot disponible (plus flexible)

### Réponse

```json
{
  "ok": true,
  "performance": {
    "as_of": "2025-10-12T18:30:00+02:00",
    "anchor": "midnight",
    "base_snapshot_at": "2025-10-12T00:15:00+02:00",
    "total": {
      "current_value_usd": 133100.50,
      "absolute_change_usd": 2345.75,
      "percent_change": 1.7895
    },
    "by_account": {
      "main": {
        "current_value_usd": 133100.50,
        "absolute_change_usd": 2345.75,
        "percent_change": 1.7895
      }
    },
    "by_source": {
      "cointracking": {
        "current_value_usd": 133100.50,
        "absolute_change_usd": 2345.75,
        "percent_change": 1.7895
      }
    }
  }
}
```

### Headers de Cache

L'endpoint supporte **ETag** pour optimisation HTTP :

```http
# Premier appel
GET /api/performance/summary
→ 200 OK
ETag: "a1b2c3d4..."
Cache-Control: private, max-age=60

# Appel suivant avec validation
GET /api/performance/summary
If-None-Match: "a1b2c3d4..."
→ 304 Not Modified (si données inchangées)
```

## Création de Snapshots

Pour activer le calcul P&L, créer des snapshots réguliers :

```http
POST /portfolio/snapshot?user_id={user}&source={source}
```

### Stratégies de Snapshot

1. **Cron quotidien** : Créer un snapshot à 00:00 chaque jour
2. **Pré-rebalancing** : Snapshot avant chaque rebalancement
3. **À la demande** : Snapshot manuel via l'API

### Exemple avec cURL

```bash
# Créer un snapshot pour user "jack"
curl -X POST "http://localhost:8000/portfolio/snapshot?source=cointracking&user_id=jack"

# Récupérer le P&L depuis midnight
curl "http://localhost:8000/api/performance/summary?source=cointracking&user_id=jack&anchor=midnight"
```

## Isolation Multi-Tenant

Les snapshots sont **isolés par (user_id, source)** :

```
data/portfolio_history.json
├── user: "demo", source: "cointracking"  → 365 snapshots max
├── user: "jack", source: "cointracking"  → 365 snapshots max
└── user: "jack", source: "cointracking_api" → 365 snapshots max
```

## Gestion Automatique

### Upsert Journalier

Le système évite les doublons :
- **1 snapshot par jour civil** (Europe/Zurich timezone)
- Snapshots multiples le même jour → **remplacés** automatiquement

### Rotation Automatique

- **365 snapshots maximum** par (user_id, source)
- Snapshots anciens supprimés automatiquement
- Écriture atomique (évite corruption fichier)

## Cas d'Usage

### Tracking Intraday

```javascript
// Refresh toutes les 5 minutes
setInterval(async () => {
  const response = await fetch(
    '/api/performance/summary?anchor=midnight'
  );
  const data = await response.json();
  displayPnL(data.performance.total);
}, 5 * 60 * 1000);
```

### Dashboard avec Cache

```javascript
// Utiliser ETag pour optimiser
const etag = localStorage.getItem('pnl_etag');
const response = await fetch('/api/performance/summary', {
  headers: etag ? { 'If-None-Match': etag } : {}
});

if (response.status === 304) {
  // Utiliser cache local
  return JSON.parse(localStorage.getItem('pnl_data'));
}

const data = await response.json();
localStorage.setItem('pnl_etag', response.headers.get('etag'));
localStorage.setItem('pnl_data', JSON.stringify(data));
```

### Comparaison Multi-Anchor

```javascript
// Comparer P&L depuis différents points
const [sinceSession, sinceMidnight] = await Promise.all([
  fetch('/api/performance/summary?anchor=session'),
  fetch('/api/performance/summary?anchor=midnight')
]);

const sessionPnL = await sinceSession.json();
const midnightPnL = await sinceMidnight.json();

console.log('P&L depuis dernière session:',
  sessionPnL.performance.total.percent_change);
console.log('P&L aujourd\'hui:',
  midnightPnL.performance.total.percent_change);
```

## Limitations & Considérations

### Pas de Données Historiques

Si aucun snapshot n'existe, l'endpoint retourne :
```json
{
  "ok": true,
  "performance": {
    "total": {
      "current_value_usd": 133100.50,
      "absolute_change_usd": 0.0,
      "percent_change": 0.0
    }
  }
}
```

**Solution** : Créer au moins 1 snapshot via `POST /portfolio/snapshot`

### Flux de Capitaux

Le P&L ne distingue **pas** :
- Performance réelle (gains/pertes de marché)
- Dépôts/retraits de fonds

Pour les portfolios avec flux fréquents, utiliser l'algorithme **Modified Dietz** (TODO).

### Précision Temporelle

- Snapshots : Précision à la **seconde**
- Anchor "midnight" : 00:00 en **Europe/Zurich** (pas UTC)
- Crypto 24/7 : Pas de "prev_close" réel → fallback midnight

## Troubleshooting

### P&L toujours à 0

1. Vérifier qu'un snapshot existe :
   ```bash
   curl "http://localhost:8000/portfolio/metrics?user_id=jack&source=cointracking"
   ```

2. Créer un snapshot si nécessaire :
   ```bash
   curl -X POST "http://localhost:8000/portfolio/snapshot?user_id=jack&source=cointracking"
   ```

### Cache ETag ne fonctionne pas

- Vérifier que le header `If-None-Match` est bien envoyé
- L'ETag exclut le timestamp mais inclut les données P&L
- Si les données changent même légèrement, ETag sera différent

### Base snapshot non trouvé

- Vérifier l'isolation (user_id, source) correcte
- Pour anchor="midnight", un snapshot doit exister avant 00:00 du jour
- Pour anchor="session", au moins 1 snapshot doit exister

## Références Techniques

- **Service Principal** : `services/portfolio.py:213-330`
- **Endpoint** : `api/performance_endpoints.py:278-400`
- **Fonction Anchor** : `services/portfolio.py:87-128` (`_compute_anchor_ts`)
- **Upsert Snapshot** : `services/portfolio.py:52-84` (`_upsert_daily_snapshot`)
- **Tests** : `tests/test_performance_endpoints.py`

## Roadmap

- [ ] Support `prev_close` réel pour équities (17:00 NYSE)
- [ ] Algorithme Modified Dietz pour flux de capitaux
- [ ] Breakdown P&L par asset/groupe
- [ ] Calcul attribution de performance
- [ ] Export P&L historique (CSV, JSON)
