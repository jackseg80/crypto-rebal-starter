# Decision Index History System

## Vue d'ensemble

Système de persistence historique pour les scores Decision Index (DI), avec gestion timezone Europe/Zurich, validation stricte, et séparation production/simulation.

## Architecture

### Module Core: `static/utils/di-history.js`

Fonctions exportées:

- **`getTodayCH()`**: Retourne date du jour en Europe/Zurich (format `YYYY-MM-DD`)
- **`makeKey({ user, source, suffix })`**: Génère clé localStorage scopée
- **`loadHistory(key, max=30)`**: Charge historique avec sanitization
- **`saveHistory(key, history)`**: Persiste historique
- **`pushIfNeeded({ key, history, today, di, max, minDelta })`**: Ajout conditionnel
- **`migrateLegacy(legacyHistory, max=30)`**: Migration depuis ancien format

### Intégrations

#### 1. Production (`analytics-unified.html`)

```javascript
// Import module
const diHistoryModule = await import(`./utils/di-history.js?v=${cacheBust}`);
window.__DI_HISTORY__ = diHistoryModule;  // Exposer pour debug

// Contexte
const activeUser = localStorage.getItem('activeUser') || 'demo';
const dataSource = window.globalConfig?.get('data_source') || 'cointracking';
const isSimulation = !!window.__SIMULATION__;
const suffix = isSimulation ? '_sim' : '_prod';

// Clé scopée
const historyKey = diHistoryModule.makeKey({ user: activeUser, source: dataSource, suffix });
const today = diHistoryModule.getTodayCH();

// Load + migration
let diHistory = diHistoryModule.loadHistory(historyKey, 30);
if (diHistory.length === 0 && s?.di_history) {
  diHistory = diHistoryModule.migrateLegacy(s.di_history, 30);
  diHistoryModule.saveHistory(historyKey, diHistory);
}

// Push conditionnel
const { history: updated, added } = diHistoryModule.pushIfNeeded({
  key: historyKey,
  history: diHistory,
  today,
  di: blendedScore,
  max: 30,
  minDelta: 0.1
});
diHistory = updated;

// Passer au panneau
const panelData = {
  history: diHistory.map(h => h.di),  // Array de scores
  // ...
};
```

#### 2. Simulation (`simulations.html`)

Utilise un buffer mémoire volatile (`window.diHistoryBuffers`) pour performance. Pas de localStorage dans les simulations rapides.

## Structure des Données

### Format localStorage

```javascript
// Clé: di_history_{user_id}_{source}_{prod|sim}
// Exemple: di_history_demo_cointracking_prod

// Valeur: Array<Entry>
[
  {
    "date": "2025-09-28",           // YYYY-MM-DD (Europe/Zurich)
    "di": 65,                        // Score Decision Index [0..100]
    "timestamp": "2025-09-28T14:23:45.123Z",  // ISO 8601
    "migrated": false                // Optionnel: flag migration legacy
  },
  // ... max 30 entrées (rolling window)
]
```

## Règles de Persistence

### Conditions d'ajout (`pushIfNeeded`)

Une nouvelle entrée est ajoutée SI:
1. **Pas d'historique** (première exécution)
2. **Nouveau jour** (`entry.date !== today`)
3. **Delta significatif** (`|last.di - current.di| > minDelta`)

Seuil par défaut: `minDelta = 0.1`

### Sanitization (`loadHistory`)

Filtrage strict:
- `typeof entry === 'object'` ✅
- `typeof entry.date === 'string'` ✅
- `Number.isFinite(entry.di)` ✅
- Rejet: `NaN`, `Infinity`, `null`, `undefined`

### Rolling Window

Maximum: 30 jours (configurable via paramètre `max`)

Trim automatique:
```javascript
const trimmed = history.slice(-max);  // Garde les N plus récents
```

## Timezone: Europe/Zurich

**Pourquoi?** Cohérence date-civil pour utilisateurs européens (pas UTC).

**Implémentation:**
```javascript
const fmt = new Intl.DateTimeFormat('fr-CH', {
  timeZone: 'Europe/Zurich',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit'
});
const parts = fmt.formatToParts(new Date());
// → "2025-10-01"
```

## Séparation Production / Simulation

### Clés localStorage

- **Production**: `di_history_demo_cointracking_prod`
- **Simulation**: `di_history_demo_cointracking_sim`

### Détection contexte

```javascript
const isSimulation = !!window.__SIMULATION__;
const suffix = isSimulation ? '_sim' : '_prod';
```

## Migration Legacy

### Format ancien (`s?.di_history`)

```javascript
// Array de numbers OU objects {di: number}
[55, 58, 60, 62, 65]
// OU
[{di: 55}, {di: 58}, {di: 60}]
```

### Migration automatique

```javascript
if (diHistory.length === 0 && s?.di_history) {
  diHistory = diHistoryModule.migrateLegacy(s.di_history, 30);
  diHistoryModule.saveHistory(historyKey, diHistory);
  console.debug('✅ Legacy migration done:', { count: diHistory.length });
}
```

**Stratégie dates rétroactives:**
- Dernier élément → aujourd'hui
- Pénultième → hier
- Etc. (approximation raisonnable)

## Tests

### Suite complète: `static/test-di-history.html`

8 test cases:
1. ✅ `getTodayCH()` - Format YYYY-MM-DD
2. ✅ `makeKey()` - Clés scopées user/source/suffix
3. ✅ `loadHistory()` - Chargement + validation
4. ✅ `saveHistory()` - Persistence
5. ✅ `pushIfNeeded()` - Logique conditionnelle (3 cas)
6. ✅ `migrateLegacy()` - Migration ancien format
7. ✅ Sanitization - Filtrage NaN/Infinity/invalides
8. ✅ Max Limit - Rolling window 30 entrées

**Exécution:**
```bash
# Serveur lancé
http://localhost:8080/static/test-di-history.html
```

## Debug

### Console

```javascript
// API exposée dans window (analytics-unified.html)
window.__DI_HISTORY__.getTodayCH()
// → "2025-10-01"

window.__DI_HISTORY__.loadHistory('di_history_demo_cointracking_prod')
// → [{date: "2025-09-28", di: 65, ...}, ...]
```

### Logs

```javascript
// Ajout réussi
📊 DI history updated: {
  count: 12,
  latest: 67,
  context: 'production',
  timezone: 'Europe/Zurich'
}

// Migration legacy
📦 Migration legacy DI history...
✅ Legacy migration done: { count: 15 }
```

### Nettoyage

```javascript
// Via test-di-history.html
// Bouton "🗑️ Clear Storage"

// Via console
Object.keys(localStorage)
  .filter(k => k.includes('di_history'))
  .forEach(k => localStorage.removeItem(k));
```

## Évolution Future

### Possibilités
- Export CSV historique
- Graphiques longue durée (Chart.js)
- Compression LZ pour gros historiques
- Sync cloud (optionnel)

### Limites actuelles
- Stockage client uniquement (localStorage)
- Pas de backup automatique
- 30 jours max (acceptable pour Trend Chip)

## Références

- Spécification initiale: critique expert (Oct 2025)
- Implémentation: `static/utils/di-history.js`
- Tests: `static/test-di-history.html`
- Playbook: `CLAUDE.md` section 11

