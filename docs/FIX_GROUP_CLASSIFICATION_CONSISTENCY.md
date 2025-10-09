# Fix: Incohérence Classification des 11 Groupes (Oct 2025)

## Problème Identifié

Pour jack avec API (192 assets), les différentes pages affichaient des classifications incohérentes :

- ✅ **analytics-unified.html** : Affichage correct avec les bonnes valeurs pour tous les 11 groupes
- ❌ **dashboard.html** : N'affichait pas tous les 11 groupes dans Portfolio Overview
- ❌ **risk-dashboard.html** : Affichait les 11 groupes mais Gaming/NFT et L2/Scaling à 0% (faux)
- ❌ **rebalance.html** : Ne montrait pas tous les groupes

## Cause Racine

**Seul `analytics-unified.html` forçait le rechargement de la taxonomy** avant de classifier les assets :

```javascript
// analytics-unified.html (CORRECT)
const { forceReloadTaxonomy, UNIFIED_ASSET_GROUPS } = await import('./shared-asset-groups.js');
await forceReloadTaxonomy();
```

Les autres pages :
- `dashboard.html` : Importait mais n'appelait pas `forceReloadTaxonomy()` au chargement initial
- `risk-dashboard.html` : N'appelait pas `forceReloadTaxonomy()` du tout
- `rebalance.html` : Import asynchrone avec `.then()` causant des problèmes de timing

## Corrections Appliquées

### 1. dashboard.html (static/dashboard.html:1668-1682, 1752-1764, 1899, 1999, 2014, 1403)

**Avant** : Fonction vide qui ne chargeait rien
```javascript
async function loadAssetGroups() {
    console.debug('🔍 Asset groups ready via unified functions');
    // Plus besoin de charger, les fonctions sont directement disponibles
}
```

**Après** : Force reload taxonomy + vérification
```javascript
async function loadAssetGroups() {
    try {
        console.debug('🔄 [Dashboard] Force reloading taxonomy for proper asset classification...');
        const { forceReloadTaxonomy, UNIFIED_ASSET_GROUPS } = await import('./shared-asset-groups.js');
        await forceReloadTaxonomy();

        if (!Object.keys(UNIFIED_ASSET_GROUPS || {}).length) {
            console.warn('⚠️ [Dashboard] Taxonomy non chargée – risque de "Others" gonflé');
        } else {
            console.log('✅ [Dashboard] Taxonomy loaded:', Object.keys(UNIFIED_ASSET_GROUPS).length, 'groupes');
        }
    } catch (error) {
        console.error('❌ [Dashboard] Failed to load taxonomy:', error);
    }
}
```

**Et** : Amélioration de `groupAssetsByAliases()` pour utiliser `async/await` (ligne 1752-1764)
```javascript
async function groupAssetsByAliases(items) {
    try {
        console.log('🔄 [Dashboard] Classifying', items.length, 'assets with unified taxonomy');
        const { groupAssetsByClassification } = await import('./shared-asset-groups.js');

        if (!groupAssetsByClassification) {
            throw new ReferenceError('groupAssetsByClassification not available');
        }

        const result = groupAssetsByClassification(items);
        console.log('✅ [Dashboard] Unified grouping succeeded, found', result.length, 'groups');
        return result;
    } catch (error) {
        console.warn('⚠️ [Dashboard] Unified grouping failed, using fallback:', error);
        // ... fallback code
    }
}
```

**Et** : Correction de tous les appels à `groupAssetsByAliases()` avec `await` (lignes 1899, 2014, 1403)
```javascript
// Ligne 1899 - updatePortfolioChart()
const groupedData = await groupAssetsByAliases(filteredItems);

// Ligne 1999 - updatePortfolioBreakdown() rendue async
async function updatePortfolioBreakdown(balancesData) { ... }

// Ligne 2014 - dans updatePortfolioBreakdown()
const groupedData = await groupAssetsByAliases(filteredItems);

// Ligne 1403 - appel depuis updatePortfolioDisplay()
await updatePortfolioBreakdown(data.balances);
```

**Pourquoi** : Éviter `TypeError: groupedData.sort is not a function` car appel async sans await retournait une Promise au lieu d'un Array

**Et** : Suppression de la limite artificielle d'affichage à 8 groupes (lignes 1659-1663, 1903-1905, 1947)
```javascript
// Avant - limitait à 8 groupes
const sortedData = groupedData.sort((a, b) => b.value - a.value).slice(0, 8);

// Après - affiche TOUS les groupes (11 canoniques)
const sortedData = groupedData.sort((a, b) => b.value - a.value);

// Ajout 11ème couleur
const PORTFOLIO_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1',
    '#14b8a6'  // Teal pour le 11ème groupe
];

// Attribution couleurs robuste (recycle si > 11 groupes)
backgroundColor: values.map((_, i) => PORTFOLIO_COLORS[i % PORTFOLIO_COLORS.length])
```

**Pourquoi** : Le graphique affichait seulement 8 groupes au lieu des 11 canoniques, cachant Gaming/NFT, L2/Scaling, etc.

### 2. risk-dashboard.html (static/risk-dashboard.html:2752-2772)

**Avant** : Import asynchrone sans force reload
```javascript
import('./shared-asset-groups.js').then(module => {
    groupAssetsByClassification = module.groupAssetsByClassification;
    getAssetGroup = module.getAssetGroup;
    console.debug('✅ Risk Dashboard: Unified asset groups loaded');
});
```

**Après** : Fonction d'initialisation avec force reload + appel immédiat
```javascript
async function initAssetGroups() {
    try {
        console.debug('🔄 [Risk Dashboard] Force reloading taxonomy for proper asset classification...');
        const module = await import('./shared-asset-groups.js');
        await module.forceReloadTaxonomy();

        groupAssetsByClassification = module.groupAssetsByClassification;
        getAssetGroup = module.getAssetGroup;

        if (!Object.keys(module.UNIFIED_ASSET_GROUPS || {}).length) {
            console.warn('⚠️ [Risk Dashboard] Taxonomy non chargée – risque de "Others" gonflé');
        } else {
            console.log('✅ [Risk Dashboard] Taxonomy loaded:', Object.keys(module.UNIFIED_ASSET_GROUPS).length, 'groupes');
        }
    } catch (error) {
        console.error('❌ [Risk Dashboard] Failed to load taxonomy:', error);
    }
}

// Initialize asset groups on page load
initAssetGroups();
```

**Et** : Amélioration de `groupAssetsByAliases()` avec fallback intelligent (ligne 2774-2793)

### 3. rebalance.html (static/rebalance.html:1854-1880)

**Avant** : Import avec `.then()` causant des problèmes de timing
```javascript
import('./shared-asset-groups.js').then(async module => {
    try {
        await module.forceReloadTaxonomy();
        ASSET_GROUPS = module.UNIFIED_ASSET_GROUPS;
        // ...
    } catch (taxonomyError) {
        console.warn('❌ [rebalance] Force reload taxonomy failed:', taxonomyError.message);
        // ...
    }
});
```

**Après** : Fonction d'initialisation avec flag `taxonomyReady` + appel immédiat
```javascript
let taxonomyReady = false;

async function initAssetGroupsSystem() {
    try {
        console.debug('🔄 [Rebalance] Force reloading taxonomy for proper asset classification...');
        const module = await import('./shared-asset-groups.js');

        await module.forceReloadTaxonomy();

        ASSET_GROUPS = module.UNIFIED_ASSET_GROUPS;
        getAssetGroup = module.getAssetGroup;
        groupAssetsByClassification = module.groupAssetsByClassification;

        if (!Object.keys(ASSET_GROUPS || {}).length) {
            console.warn('⚠️ [Rebalance] Taxonomy non chargée – risque de "Others" gonflé');
        } else {
            console.log('✅ [Rebalance] Taxonomy loaded:', Object.keys(ASSET_GROUPS).length, 'groupes');
        }

        taxonomyReady = true;
    } catch (taxonomyError) {
        console.error('❌ [Rebalance] Failed to load taxonomy:', taxonomyError);
        taxonomyReady = false;
    }
}

// Initialize taxonomy on page load
initAssetGroupsSystem();
```

**Et** : `groupAssetsByAliases()` attend que taxonomy soit prête (ligne 1882-1896)

## Résultat Attendu

Après ces corrections, **toutes les pages devraient afficher les 11 groupes de manière cohérente** :

1. BTC
2. ETH
3. Stablecoins
4. SOL
5. L1/L0 majors
6. L2/Scaling
7. DeFi
8. AI/Data
9. Gaming/NFT
10. Memecoins
11. Others

**Note** : Gaming/NFT et L2/Scaling peuvent légitimement être à 0% si le wallet de jack API ne contient pas d'assets de ces catégories. Ce qui compte, c'est que les pages affichent tous les groupes avec les **mêmes valeurs**.

**Fix Backend** : Après la correction dans `portfolio_metrics.py`, l'API `/api/risk/dashboard` retourne maintenant **tous les 11 groupes** dans `exposure_by_group`, même ceux à 0%. La section GRI de `risk-dashboard.html` affiche donc bien les 11 groupes canoniques.

## Test de Validation

Pour vérifier la cohérence, ouvrir avec jack + source API :

1. `dashboard.html` → Portfolio Overview (graphique donut)
   - **Devrait afficher** : Tous les 11 groupes (ou moins si certains à 0%)
   - **Vérifier** : Pas de limite artificielle à 8 groupes
2. `analytics-unified.html` → Objectifs Théoriques
   - **Référence** : Affichage correct depuis le début
3. `risk-dashboard.html` → Advanced Risk → GRI Section (Group Risk Index)
   - **Devrait afficher** : Tous les 11 groupes canoniques dans "Exposition & Risque par Groupe"
   - **Vérifier** : Groupes à 0% sont visibles (ex: Gaming/NFT, L2/Scaling si jack n'a pas d'actifs)
   - **Backend API** : `/api/risk/dashboard` doit retourner tous les groupes dans `risk_metrics.exposure_by_group`
4. `rebalance.html` → Résumé par groupe
   - **Devrait afficher** : Tous les groupes présents

**Vérifier** : Les valeurs % pour chaque groupe doivent être identiques sur toutes les pages.

**Test Backend API** :
```bash
# Tester que l'API retourne tous les 11 groupes
curl "http://localhost:8000/api/risk/dashboard?source=cointracking_api&user_id=jack" | jq '.risk_metrics.exposure_by_group | keys | length'
# Devrait retourner : 11
```

## Logs de Debug Ajoutés

Chaque page log maintenant :
```
🔄 [PageName] Force reloading taxonomy for proper asset classification...
✅ [PageName] Taxonomy loaded: 221 groupes
🔄 [PageName] Classifying N assets with unified taxonomy
✅ [PageName] Unified grouping succeeded, found 11 groups
```

**En cas de problème** :
```
⚠️ [PageName] Taxonomy non chargée – risque de "Others" gonflé
❌ [PageName] Failed to load taxonomy: [error]
⚠️ [PageName] Unified grouping failed, using fallback: [error]
```

## Fichiers Modifiés

- `static/dashboard.html` (lignes 1668-1682, 1752-1764, 1899, 1999, 2014, 1403, 1659-1663, 1903-1905, 1947)
  - Ajout force reload taxonomy
  - Conversion `groupAssetsByAliases()` en async
  - Ajout `await` sur tous les appels (fix TypeError)
  - Conversion `updatePortfolioBreakdown()` en async
  - **Suppression limite 8 groupes** → affiche tous les 11 groupes canoniques
  - Ajout 11ème couleur (teal #14b8a6)
  - Attribution couleurs robuste avec modulo (recycle si > 11)
- `static/risk-dashboard.html` (lignes 2752-2793, 7941)
  - Section GRI affiche bien tous les groupes (ligne 7938: "Show all groups")
  - **Fix affichage décimales** (ligne 7941): `(weight * 100).toFixed(1)` au lieu de `Math.round(weight * 100)`
  - **Avant**: 0.2% → Math.round(0.2) = 0% | 0.8% → Math.round(0.8) = 1%
  - **Après**: 0.2% → "0.2%" | 0.8% → "0.8%" | 44.3% → "44.3%"
  - **Problème résolu**: Affichage précis avec 1 décimale, plus de perte d'info pour petites allocations
- `static/rebalance.html` (lignes 1854-1896)
- **`services/portfolio_metrics.py` (lignes 170-179)** ✅ **FIX BACKEND #1**
  - Initialisation `exposure_by_group` avec **tous les 11 groupes canoniques** à 0.0
  - Utilisé par le service centralisé de métriques
- **`api/risk_endpoints.py` (lignes 865-895)** ✅ **FIX BACKEND #2 (CRITIQUE!)**
  - **C'était le vrai problème!** L'endpoint `/api/risk/dashboard` calculait `exposure_by_group` localement
  - Initialisation `exposure_by_group` avec **tous les 11 groupes canoniques** à 0.0
  - **Avant** : Dict vide `{}`, puis ajout seulement des groupes présents → Gaming/NFT et L2/Scaling manquaient si 0%
  - **Après** : Tous les 11 groupes toujours présents, valeurs exactes même si 0.2% ou 0.8%
  - Garantit que la section GRI de `risk-dashboard.html` affiche **tous** les 11 groupes

## Script de Test (Bonus)

Créé `test_jack_api_classification.py` pour analyser la classification backend Python (nécessite credentials API jack).

---

**Date** : Oct 2025
**Auteur** : Claude Code
**Status** : ✅ Completed
