# Saxo Dashboard Modernization (October 2025)

## Objectif

Moderniser `static/saxo-dashboard.html` pour :
- ✅ Supprimer le sélecteur de portfolio local redondant
- ✅ Aligner sur le pattern global WealthContextBar
- ✅ Assurer la cohérence UX avec le reste du projet (CoinTracking, etc.)
- ✅ Réduire ~100 lignes de code obsolète

## Architecture Avant/Après

### AVANT (Legacy)
```html
<!-- Sélecteur local dans la page -->
<div class="portfolio-selector">
    <label for="portfolioSelect">Portfolio:</label>
    <select id="portfolioSelect" onchange="loadPortfolio()">...</select>
    <button onclick="refreshPortfolios()">🔄</button>
</div>
```

**Problèmes** :
- Duplication de la logique de sélection de source
- Incohérence avec le reste du projet (CoinTracking utilise WealthContextBar)
- Code complexe avec `refreshPortfolios()` et `loadPortfolio()` (~100 lignes)

### APRÈS (Modernisé)
```html
<!-- Bannières info + lien vers settings -->
<div style="display: flex; align-items: center; gap: 1rem;">
    <div class="sources-banner">
        <span>📊 Source active: <strong id="current-source-name">Chargement...</strong></span>
        <a href="settings.html#tab-sources">Gérer Sources →</a>
    </div>
    <div class="sources-banner">
        <span>📊 Fraîcheur — <span id="saxo-staleness-main">...</span></span>
    </div>
</div>
```

**Améliorations** :
- Source sélectionnée globalement via WealthContextBar (menu "Bourse:")
- Page écoute l'event `bourseSourceChanged` pour se mettre à jour automatiquement
- Cohérence totale avec le reste du projet
- Code simplifié et maintenable

## Changements Techniques

### 1. Suppression du Sélecteur Local

**Fichier** : `static/saxo-dashboard.html`

**Supprimé** :
- HTML : `<select id="portfolioSelect">` + bouton refresh
- JS : `refreshPortfolios()` fonction (~48 lignes)
- JS : `loadPortfolio()` fonction (~53 lignes)
- CSS : `.portfolio-selector` styles

### 2. Nouvelle Fonction de Chargement

**Ajouté** : `loadCurrentSaxoData()` (remplacement de `refreshPortfolios()` + `loadPortfolio()`)

**Workflow** :
```javascript
async function loadCurrentSaxoData() {
    // 1. Lire la source active depuis WealthContextBar
    const bourseSource = window.wealthContextBar?.getContext()?.bourse || 'all';
    updateCurrentSourceName(bourseSource);

    // 2. Lister les portfolios disponibles
    const response1 = await fetch('/api/saxo/portfolios', {
        headers: { 'X-User': activeUser }
    });
    const { portfolios } = await response1.json();

    // 3. Charger le premier portfolio avec métadonnées complètes
    const portfolioId = portfolios[0].portfolio_id;
    const response2 = await fetch(`/api/saxo/portfolios/${portfolioId}`, {
        headers: { 'X-User': activeUser }
    });
    const portfolioData = await response2.json();

    // 4. Afficher les données
    currentPortfolioData = portfolioData;
    loadOverviewData(currentPortfolioData);
}
```

**Points clés** :
- ✅ Utilise `/api/saxo/portfolios/{id}` (données complètes avec métadonnées)
- ❌ N'utilise PAS `/api/saxo/positions` (données minimales sans name/symbol/asset_class)

### 3. Écoute Event WealthContextBar

**Ajouté dans DOMContentLoaded** :
```javascript
window.addEventListener('bourseSourceChanged', (event) => {
    debugLogger.debug('🔄 Bourse source changed:', event.detail);
    loadCurrentSaxoData(); // Reload auto des données
});
```

**Workflow utilisateur** :
1. User clique menu "Bourse:" dans WealthContextBar
2. Sélectionne une nouvelle source (ex: `📄 Positions 23 sept.csv`)
3. WealthContextBar émet event `bourseSourceChanged`
4. `saxo-dashboard.html` écoute et recharge automatiquement les données

### 4. Fix Cache Développement

**Problème** : Changes non visibles sans F5 (hard refresh)

**Cause** : FastAPI StaticFiles applique des headers de cache par défaut

**Solution** : Middleware no-cache en mode DEBUG

**Fichier** : `api/main.py`

```python
@app.middleware("http")
async def no_cache_dev_middleware(request: Request, call_next):
    response = await call_next(request)

    # En mode DEBUG, désactiver le cache pour HTML/CSS/JS
    if DEBUG and request.url.path.startswith("/static"):
        if any(request.url.path.endswith(ext) for ext in [".html", ".css", ".js"]):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

    return response
```

**Impact** :
- ✅ Changes visibles immédiatement en développement
- ✅ Pas d'impact en production (middleware actif uniquement si DEBUG=True)

### 5. Fix Affichage Données

**Problème Initial** : Après modernisation, données incorrectes affichées
- $0 Total Value
- "Unknown" noms
- "N/A" symboles
- "NaN%" pourcentages

**Cause** : Utilisation initiale de `/api/saxo/positions` qui retourne `PositionModel` (champs minimaux)

**Solution** : Workflow list-then-detail via `/api/saxo/portfolios/{id}` (données complètes)

**Différence API** :

| Endpoint | Model | Champs disponibles |
|----------|-------|-------------------|
| `/api/saxo/positions` | `PositionModel` | instrument_id, quantity, market_value (NO name/symbol) |
| `/api/saxo/portfolios/{id}` | Full Portfolio | name, symbol, asset_class, market_value_usd, + tous les champs |

**Résultat** :
- ✅ Tous les champs affichés correctement
- ✅ Valeurs, noms, symboles, pourcentages corrects

## Tests

### Test Manuel

1. Démarrer le serveur : `uvicorn api.main:app --reload --port 8000`
2. Ouvrir `http://localhost:8000/static/saxo-dashboard.html`
3. Vérifier :
   - ✅ Bannière "Source active" affiche la source correcte
   - ✅ Données du portfolio affichées (noms, symboles, valeurs, %)
   - ✅ Pas de sélecteur de portfolio local
4. Changer source via WealthContextBar (menu "Bourse:")
5. Vérifier :
   - ✅ Page se recharge automatiquement
   - ✅ Nouvelles données affichées instantanément

### Test Cache (Développement)

1. Modifier `saxo-dashboard.html`
2. Recharger la page (Ctrl+R, pas F5)
3. Vérifier :
   - ✅ Changes visibles immédiatement
   - ✅ Pas besoin de hard refresh (F5)

## Bénéfices

### Cohérence Architecture
- ✅ Alignement total avec pattern CoinTracking
- ✅ WealthContextBar = source unique de vérité pour sélection
- ✅ Event-driven architecture cohérente

### Maintenabilité
- ✅ ~100 lignes de code supprimées
- ✅ Logique simplifiée (1 fonction au lieu de 2)
- ✅ Moins de duplication = moins de bugs

### UX
- ✅ Sélection de source cohérente dans tout le projet
- ✅ Changement de source instantané
- ✅ Pas de confusion avec 2 sélecteurs différents

## Fichiers Modifiés

```
api/main.py                      # Middleware no-cache développement
static/saxo-dashboard.html       # Modernisation complète
docs/SAXO_DASHBOARD_MODERNIZATION.md  # Documentation (ce fichier)
```

## Références

- [WEALTH_CONTEXT_BAR_DYNAMIC_SOURCES.md](WEALTH_CONTEXT_BAR_DYNAMIC_SOURCES.md) - Documentation WealthContextBar
- [SAXO_INTEGRATION_SUMMARY.md](SAXO_INTEGRATION_SUMMARY.md) - Vue d'ensemble intégration Saxo
- [TODO_WEALTH_MERGE.md](TODO_WEALTH_MERGE.md) - Roadmap Wealth namespace

## Statut

✅ **COMPLETE** (October 2025)

- [x] Suppression sélecteur local
- [x] Intégration WealthContextBar
- [x] Event listener `bourseSourceChanged`
- [x] Fix cache développement
- [x] Fix affichage données (API complète)
- [x] Tests manuels réussis
- [x] Documentation
