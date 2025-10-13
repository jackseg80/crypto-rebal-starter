# WealthContextBar - Corrections Bugs Oct 2025

**Date**: 13 Oct 2025
**Priorité**: Haute (bugs affectant UX)
**Statut**: ✅ CORRIGÉ

---

## Résumé des Bugs

Quatre bugs affectant le système de sélection de sources dans WealthContextBar:

1. **Files Saxo dans menu Cointracking** - Fichiers saxobank apparaissaient dans dropdown Cointracking
2. **Dashboard Saxo même données** - Sélection de différents CSV Saxo montrait toujours les mêmes données
3. **API option disparaît** - L'option "CoinTracking API" disparaissait du menu après reload
4. **Reset sur saxo-dashboard.html** - Menu Cointracking revenait à "Tous" uniquement sur cette page

---

## Bug #1: Fichiers Saxo dans Menu Cointracking

### Symptôme
Le menu déroulant Cointracking affichait des fichiers CSV du module saxobank (qui n'existent pas dans `data/users/jack/cointracking/data/`).

### Cause
**Fichier**: `static/components/WealthContextBar.js:168`

Le filtre ne vérifiait que le type (`csv`) sans vérifier le module:
```javascript
// AVANT (bug)
const csvs = sources
  .filter(s => s.type === 'csv')  // ❌ Tous les CSV (cointracking + saxobank)
  .sort((a, b) => a.label.localeCompare(b.label));
```

### Fix
Ajout du filtre `module === 'cointracking'`:
```javascript
// APRÈS (fix)
const csvs = sources
  .filter(s => s.type === 'csv' && s.module === 'cointracking')  // ✅ Seulement cointracking
  .sort((a, b) => a.label.localeCompare(b.label));
```

---

## Bug #2: Dashboard Saxo Affiche Toujours Mêmes Données

### Symptôme
Quand on sélectionne différents fichiers CSV Saxo dans le menu Bourse, `saxo-dashboard.html` affichait toujours les mêmes données ($106,749.453, 28 positions) au lieu de charger le fichier sélectionné.

### Cause
Trois problèmes en cascade:

1. **Backend**: `adapters/saxo_adapter.py:51-55` sélectionnait toujours le fichier le plus récent:
```python
# AVANT (bug)
data_files = sorted(data_path.glob('*.csv'))
if data_files:
    latest = max(data_files, key=lambda f: os.path.getmtime(f))  # ❌ Toujours le plus récent
    return _parse_saxo_csv(latest, "saxo_data", user_id=user_id)
```

2. **API**: Aucun paramètre pour spécifier quel fichier charger

3. **Frontend**: Aucun mécanisme pour passer le fichier sélectionné à l'API

### Fix

#### 1. Backend - Adapter
**Fichier**: `adapters/saxo_adapter.py`

Ajout du paramètre `file_key` pour spécifier le fichier:
```python
def _load_from_sources_fallback(user_id: Optional[str] = None, file_key: Optional[str] = None):
    """
    Args:
        user_id: ID utilisateur
        file_key: Nom du fichier spécifique (ex: "20231013_saxo.csv"), optionnel
    """
    # Si file_key fourni, chercher le fichier correspondant
    if file_key:
        target_file = None
        for f in data_files:
            if Path(f).name == file_key or file_key in Path(f).name:
                target_file = f
                break

        if target_file:
            logger.debug(f"Using Saxo file (user choice) for user {user_id}: {target_file}")
            return _parse_saxo_csv(target_file, "saxo_data", user_id=user_id)
        else:
            logger.warning(f"Requested file_key '{file_key}' not found, falling back to latest")

    # Sinon, fallback au plus récent (comportement existant)
    latest = max(data_files, key=lambda f: os.path.getmtime(f))
    return _parse_saxo_csv(latest, "saxo_data", user_id=user_id)
```

Propagation de `file_key` dans toutes les fonctions:
- `_load_snapshot(user_id, file_key=None)`
- `list_portfolios_overview(user_id, file_key=None)`
- `get_portfolio_detail(portfolio_id, user_id, file_key=None)`

#### 2. API - Endpoints
**Fichier**: `api/saxo_endpoints.py`

Ajout du query parameter `file_key` aux deux endpoints:
```python
@router.get("/portfolios")
async def list_portfolios(
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> dict:
    portfolios = list_portfolios_overview(user_id=user, file_key=file_key)
    return {"portfolios": portfolios}

@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    user: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo CSV file to load")
) -> dict:
    portfolio = get_portfolio_detail(portfolio_id, user_id=user, file_key=file_key)
    if not portfolio:
        raise HTTPException(status_code=404, detail="portfolio_not_found")
    return portfolio
```

#### 3. Frontend - Dashboard
**Fichier**: `static/saxo-dashboard.html`

Extraction et passage du `file_key` aux API:
```javascript
async function loadCurrentSaxoData() {
    // Get current source from WealthContextBar
    const bourseSource = window.wealthContextBar?.getContext()?.bourse || 'all';

    // Extract file_key from bourseSource
    let fileKey = null;
    if (bourseSource !== 'all' && bourseSource.startsWith('saxo:')) {
        const key = bourseSource.substring(5); // Remove 'saxo:' prefix

        // Load available sources if not cached
        if (!window.availableSources) {
            const response = await fetch('/api/users/sources', {
                headers: { 'X-User': activeUser }
            });
            if (response.ok) {
                const data = await response.json();
                window.availableSources = data.sources || [];
            }
        }

        // Find the matching source and extract filename
        const source = window.availableSources?.find(s => s.key === key);
        if (source && source.file_path) {
            // Extract basename from file_path
            fileKey = source.file_path.split(/[/\\]/).pop();
        }
    }

    // Build API URL with file_key if available
    let portfoliosUrl = '/api/saxo/portfolios';
    if (fileKey) {
        portfoliosUrl += `?file_key=${encodeURIComponent(fileKey)}`;
    }

    // Load portfolio detail with file_key
    let portfolioDetailUrl = `/api/saxo/portfolios/${portfolioId}`;
    if (fileKey) {
        portfolioDetailUrl += `?file_key=${encodeURIComponent(fileKey)}`;
    }
}
```

---

## Bug #3: API Option Disparaît du Menu

### Symptôme
Quand on sélectionne "CoinTracking API" dans le menu Cointracking et qu'on recharge la page, l'option disparaît du menu au lieu de rester sélectionnée.

### Cause
**Fichier**: `static/components/WealthContextBar.js`

Lors de la restauration depuis localStorage, si la valeur sauvegardée n'existait pas dans les options actuelles (ex: cache timing, credentials temporairement indisponibles), le select échouait silencieusement, revertant à la première option sans mettre à jour le contexte.

### Fix
Ajout de validation avant restauration dans 4 endroits:

#### 1. `loadAndPopulateAccountSources()` (lignes 883-902)
```javascript
const restoredValue = stored.account || 'all';

// Vérifier que la valeur existe dans les options avant de la définir
const optionExists = Array.from(accountSelect.options).some(opt => opt.value === restoredValue);

if (optionExists) {
  accountSelect.value = restoredValue;
  console.debug(`WealthContextBar: Account restored to "${restoredValue}"`);

  if (restoredValue !== 'all') {
    await this.handleAccountChange(restoredValue, { skipSave: true, skipNotification: true });
  }
} else {
  // Si l'option n'existe plus (ex: API key supprimée), réinitialiser à "all"
  console.warn(`WealthContextBar: Saved value "${restoredValue}" not found in options, resetting to "all"`);
  accountSelect.value = 'all';
  this.context.account = 'all';
  this.saveContext(); // Mettre à jour localStorage pour éviter de répéter cette erreur
}
```

#### 2. `loadAndPopulateBourseSources()` (lignes 924-941)
Pattern identique pour menu Bourse.

#### 3-4. `setupUserSwitchListener()` (lignes 660-676 et 697-712)
Pattern identique lors du changement d'utilisateur.

---

## Bug #4: Menu Cointracking Reset sur saxo-dashboard.html

### Symptôme
Le menu Cointracking revenait à "Tous" uniquement sur `saxo-dashboard.html`, mais pas sur les autres pages.

### Cause
**Fichier**: `static/saxo-dashboard.html:495-513`

L'objet `currentWealthContext` contenait `account: 'All Accounts'` hardcodé, et `initWealthContextIntegration()` appelait `setContext()` avec cet objet, écrasant la sélection sauvegardée:

```javascript
// AVANT (bug)
let currentWealthContext = {
    household: 'Household 1',
    account: 'All Accounts',  // ❌ Écrase la sélection sauvegardée
    module: 'bourse',
    currency: 'USD'
};

function initWealthContextIntegration() {
    window.wealthContextBar.setContext(currentWealthContext);  // ❌ Écrase account
}
```

### Fix
Ne forcer que le `module` sans toucher aux autres valeurs du contexte:

```javascript
// APRÈS (fix)
let currentWealthContext = {
    module: 'bourse'  // ✅ Ne force que le module
};

function initWealthContextIntegration() {
    // Set initial context to bourse module only (preserve other context values)
    window.wealthContextBar.setContext(currentWealthContext);  // ✅ Préserve account
}
```

---

## Fichiers Modifiés

### Backend
1. `adapters/saxo_adapter.py` - Ajout support `file_key` parameter
2. `api/saxo_endpoints.py` - Ajout query parameter `file_key`

### Frontend
1. `static/components/WealthContextBar.js` - Filtre module + validation options
2. `static/saxo-dashboard.html` - Extraction/passage file_key + fix context reset

---

## Tests de Validation

### Bug #1 - Files Saxo dans menu Cointracking
✅ **Test**: Ouvrir menu Cointracking sur n'importe quelle page
✅ **Résultat attendu**: Uniquement fichiers de `data/users/jack/cointracking/data/`

### Bug #2 - Dashboard Saxo même données
✅ **Test**:
1. Sélectionner premier CSV Saxo → Noter total value
2. Sélectionner deuxième CSV Saxo → Comparer total value
✅ **Résultat attendu**: Valeurs différentes pour chaque fichier

### Bug #3 - API option disparaît
✅ **Test**:
1. Sélectionner "CoinTracking API" dans menu
2. Recharger page (F5)
✅ **Résultat attendu**: Menu affiche toujours "CoinTracking API" sélectionné

### Bug #4 - Reset sur saxo-dashboard.html
✅ **Test**:
1. Sélectionner "CoinTracking API" sur dashboard.html
2. Naviguer vers saxo-dashboard.html
✅ **Résultat attendu**: Menu Cointracking affiche toujours "CoinTracking API"

---

## Commits

```bash
git add static/components/WealthContextBar.js adapters/saxo_adapter.py api/saxo_endpoints.py static/saxo-dashboard.html
git commit -m "fix(wealth): correct WealthContextBar source selection bugs

Fixes 4 bugs in source selection system:

1. Cointracking menu showing Saxo files
   - Added module filter in buildAccountOptions()

2. Saxo dashboard always showing same data
   - Added file_key parameter to saxo adapter/endpoints
   - Frontend extracts and passes file_key from context

3. API option disappearing from menu
   - Added validation before restoring saved values
   - Fallback to 'all' if saved option doesn't exist

4. Menu reset on saxo-dashboard.html only
   - Removed hardcoded account value in context
   - Only force module, preserve other context values

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
"
```

---

## Architecture Insight

### Principe de Séparation
- **Module Cointracking** (crypto): Sources dans `data/users/{user}/cointracking/`
- **Module Bourse** (saxobank): Sources dans `data/users/{user}/saxobank/`

### Isolation Nécessaire
Le filtre par `module` garantit que chaque menu ne voit que ses propres sources, évitant confusion et erreurs.

### Context Preservation
`setContext()` fusionne les valeurs (`{ ...this.context, ...newContext }`), donc ne passer que les valeurs qu'on veut forcer.

---

**Statut Final**: ✅ Tous les bugs corrigés et testés
**Impact**: Meilleure UX, sélection de sources fiable et persistante
