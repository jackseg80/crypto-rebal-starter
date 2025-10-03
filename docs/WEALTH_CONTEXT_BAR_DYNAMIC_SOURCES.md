# WealthContextBar - Sources Dynamiques (Oct 2025)

## 🎯 Objectif

Remplacer les comptes hardcodés ("Trading", "Hold", "Staking") du menu secondaire par les **vraies sources de données** disponibles pour chaque utilisateur (CSV + API), avec isolation multi-tenant stricte.

## 🔧 Modifications Implémentées

### 1. **Persistance localStorage namespacée par utilisateur**

**Avant** :
```javascript
localStorage.setItem('wealthCtx', JSON.stringify(context));
```

**Après** :
```javascript
const userKey = `wealth_ctx:${activeUser}`;
localStorage.setItem(userKey, JSON.stringify(context));
```

**Bénéfice** : Chaque utilisateur a son propre contexte isolé, évite les collisions multi-tenant.

### 2. **Chargement dynamique des sources via API**

Nouvelle méthode `loadAccountSources()` :
- Fetch `/api/users/sources` avec header `X-User`
- Tri automatique : API (alphabétique) puis CSV (alphabétique)
- Séparateurs visuels `──── API ────` et `──── CSV ────`
- Timeout + AbortController pour gestion robuste
- Fallback gracieux en cas d'erreur réseau

### 3. **Format de valeur normalisé**

**Structure** : `type:key`
- Exemple API : `api:cointracking_api` → 🌐 CoinTracking API
- Exemple CSV : `csv:csv_latest` → 📄 latest.csv
- Option spéciale : `all` → Tous (vue consolidée)

**Parsing** :
```javascript
parseAccountValue('csv:csv_latest')
// → { type: 'csv', key: 'csv_latest' }

parseAccountValue('all')
// → { type: 'all', key: null }
```

### 4. **Gestion du switch utilisateur**

Nouvelle méthode `setupUserSwitchListener()` :
- Écoute l'événement `activeUserChanged` (émis par `nav.js`)
- Annule fetch en cours via AbortController
- Recharge les sources du nouvel utilisateur
- Restaure la sélection depuis `wealth_ctx:{newUser}`
- Affiche état de chargement (`aria-busy`)

### 5. **État de chargement accessible**

```html
<select id="wealth-account" aria-busy="true">
  <option>Chargement…</option>
</select>
```

Après chargement :
```javascript
accountSelect.removeAttribute('aria-busy');
accountSelect.innerHTML = accountHTML; // Options dynamiques
```

### 6. **Événement canonique wealth:change**

**Structure enrichie** :
```javascript
{
  household: 'all',
  module: 'crypto',
  currency: 'USD',
  account: { type: 'csv', key: 'csv_latest' },  // ← Parsé
  sourceValue: 'csv:csv_latest'                 // ← Valeur brute
}
```

**Consommateurs** peuvent parser facilement :
```javascript
window.addEventListener('wealth:change', (e) => {
  const { account } = e.detail;
  if (account.type === 'csv') {
    // Charger données CSV spécifiques
  } else if (account.type === 'api') {
    // Charger données API
  } else {
    // Vue consolidée (all)
  }
});
```

### 7. **Intégration complète avec le système de sources** 🆕

Nouvelle méthode `handleAccountChange()` qui réplique la logique de `settings.html` :

**Workflow complet** :
1. Parse la valeur sélectionnée (`type:key`)
2. Charge `window.availableSources` si nécessaire
3. **Préserve les clés API** (fetch `/api/users/settings`)
4. Détecte changement réel (source ou fichier CSV)
5. **Vide tous les caches** (`clearBalanceCache()`, localStorage `cache:*`, `risk_score*`, `balance_*`)
6. **Met à jour `window.globalConfig.data_source`**
7. **Met à jour `window.userSettings.data_source` et `csv_selected_file`**
8. **Émet événement `dataSourceChanged`** pour les pages avec listeners
9. **Sauvegarde dans le backend** (`PUT /api/users/settings`)
10. **Notification visuelle** + **Reload automatique après 1s** ⚡

**Exemple** :
```javascript
// User sélectionne "📄 latest.csv" dans le dropdown
// → handleAccountChange('csv:csv_latest')
//   → window.globalConfig.set('data_source', 'cointracking')
//   → window.userSettings.csv_selected_file = 'latest.csv'
//   → clearBalanceCache()
//   → dispatchEvent('dataSourceChanged') // Pages avec listeners rechargent
//   → PUT /api/users/settings (persist)
//   → Notification: "✅ Source changée: 📄 latest.csv"
//   → setTimeout(() => location.reload(), 1000) // Reload auto
```

### 8. **Rechargement automatique immédiat** ⚡ 🆕

**Problème résolu** : Avant, il fallait refresh manuellement (F5) pour voir les données de la nouvelle source.

**Solution** : Double approche pour compatibilité maximale :

1. **Event `dataSourceChanged`** : Pages qui écoutent rechargent leurs données sans reload complet
   - `analytics-unified.html` → `loadUnifiedData()`
   - `dashboard.html` → Recharge tiles automatiquement

2. **Auto-reload après 1s** : Garantit 100% compatibilité avec toutes les pages
   - Même les pages sans listener voient immédiatement la nouvelle source
   - UX fluide : notification → reload transparent

**Workflow UX** :
```
User clique dropdown → Sélectionne source
↓
Notification verte: "✅ Source changée: ..."
↓
1 seconde d'attente (permet de lire la notification)
↓
Page recharge automatiquement
↓
Données affichées = nouvelle source ✅
```

## 📋 Checklist de tests

- [x] Endpoint `/api/users/sources` retourne bien les sources pour chaque user
- [x] Chargement initial → dropdown rempli avec sources réelles
- [x] Séparateurs `──── API ────` et `──── CSV ────` affichés si > 0 items
- [x] "Tous" toujours en premier
- [x] Persistance localStorage namespacée par user
- [x] Switch user (demo → jack) → sources rechargées automatiquement
- [x] AbortController annule fetch en cours lors du switch
- [x] Fallback "Tous" uniquement si erreur réseau
- [x] Event `wealth:change` émis avec structure canonique
- [x] `aria-busy` présent pendant chargement
- [x] **Changement de source met à jour `window.userSettings`** 🆕
- [x] **Changement de source met à jour `window.globalConfig`** 🆕
- [x] **Changement de source vide les caches (balance, risk, localStorage)** 🆕
- [x] **Changement de source sauvegardé dans le backend via `/api/users/settings`** 🆕
- [x] **Synchronisation avec tout le projet (analytics, rebalance, execution, etc.)** 🆕
- [x] **Émission événement `dataSourceChanged` pour pages avec listeners** ⚡ 🆕
- [x] **Reload automatique après 1s pour changement immédiat** ⚡ 🆕
- [x] **Restauration au chargement appelle handleAccountChange() avec skipSave** 🆕

## 🧪 Pages de test

### Test 1: Événements et localStorage
**URL** : `http://localhost:8000/static/test-wealth-context-bar-dynamic.html`

**Fonctionnalités** :
- Affichage état actuel (user, compte, type, clé)
- Logs temps réel des événements `wealth:change`
- Debug localStorage namespacé
- Bouton "Tester Switch User" (démo ↔ jack)
- Refresh manuel de l'état

### Test 2: Intégration complète 🆕
**URL** : `http://localhost:8000/static/test-wealth-source-integration.html`

**Fonctionnalités** :
- Vérification synchronisation `window.userSettings` ↔ `window.globalConfig` ↔ Backend
- Test automatique de changement de source
- Validation checklist complète
- Logs détaillés des changements
- Détection de désynchronisation

## 📁 Fichiers modifiés

### `static/components/WealthContextBar.js`

**Nouvelles méthodes** :
- `loadAccountSources()` : Fetch API avec AbortController
- `buildAccountOptions(sources)` : Construction HTML triée avec séparateurs
- `buildFallbackAccountOptions()` : Fallback minimal
- `parseAccountValue(rawValue)` : Parse `type:key` → objet
- `setupUserSwitchListener()` : Écoute `activeUserChanged`
- `loadAndPopulateAccountSources()` : Wrapper async pour render()
- **`handleAccountChange(selectedValue)`** 🆕 : Gestion complète changement de source

**Méthodes modifiées** :
- `loadContext()` : Lecture localStorage namespacé par user
- `saveContext()` : Sauvegarde namespacée + événement canonique
- `render()` : Appel async `loadAndPopulateAccountSources()`
- **`bindEvents()`** 🆕 : Listener spécial pour 'account' → `handleAccountChange()`

**Lignes ajoutées/modifiées** : ~290 lignes

**Fonctionnalités clés ajoutées** :
- Paramètre `options = { skipSave, skipNotification }` pour éviter boucles infinies
- Émission `dataSourceChanged` event pour pages avec listeners
- Reload automatique après 1s pour compatibilité universelle
- Appel `handleAccountChange()` lors restauration (avec `skipSave: true`)

### `static/test-wealth-context-bar-dynamic.html`

Page de test complète avec :
- État temps réel
- Event logs
- localStorage debug
- Boutons de test interactifs

## 🔮 Évolutions futures (hors scope)

- [ ] Rendre Module dynamique (crypto/bourse détectés automatiquement)
- [ ] Ajouter compteurs dans séparateurs (`──── API (3) ────`)
- [ ] Quick-filter si > 30 sources
- [ ] Pin sources favorites (persistance par user)
- [ ] Household dynamique (si config multi-foyer ajoutée)

## 📖 Documentation liée

- [CLAUDE.md](../CLAUDE.md) - Section 3 : Système Multi-Utilisateurs
- [config/users.json](../config/users.json) - Liste des utilisateurs
- [api/user_settings_endpoints.py](../api/user_settings_endpoints.py) - Endpoint `/api/users/sources`

## ✅ Statut

**Implémentation** : ✅ Complétée (Oct 2025)
**Tests manuels** : ✅ Validés
**Production ready** : ✅ Oui
