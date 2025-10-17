# Optimisation des Logs Répétitifs - Octobre 2025

## 📋 Résumé

**Date**: 17 octobre 2025
**Priorité**: HIGH
**Statut**: ✅ Complété

Optimisation des logs DEBUG répétitifs qui polluaient la console avec des centaines d'appels identiques, rendant le debugging difficile.

---

## 🎯 Problème Identifié

Lors du chargement de `risk-dashboard.html`, la console était polluée par des logs répétitifs:

```
[CAP-SELECTOR] selectPolicyCapPercent: {...}  (x50+)
[CAP-SELECTOR] selectEffectiveCap -> POLICY CAP: 4  (x50+)
🚨 [allocateRiskyBudget] CALLED - riskyPercentage: 37  (x20+)
🔍 DEBUG proposeTargets - before normalization BTC: 35.0  (x30+)
🔍 DEBUG applyTargets - BTC allocation: 36.9  (x10+)
```

**Impact**:
- ❌ Console illisible (200+ logs identiques sur quelques secondes)
- ❌ Performance dégradée (overhead des logs)
- ❌ Debugging difficile (logs importants noyés)

---

## ✅ Solution Implémentée

### Feature Flags Conditionnels

Création de **3 feature flags** globaux pour activer/désactiver les logs verbeux:

```javascript
// Désactivés par défaut (console propre)
window.__DEBUG_TARGETS_VERBOSE__        // targets-coordinator.js
window.__DEBUG_GOVERNANCE_VERBOSE__     // governance.js (CAP-SELECTOR)
window.__DEBUG_MARKET_REGIMES_VERBOSE__ // market-regimes.js (allocateRiskyBudget)
```

### Fichiers Modifiés

#### 1. `static/modules/targets-coordinator.js`

**Logs optimisés**:
- `proposeTargets()` - Avant/après normalisation (lignes 676, 685)
- `applyTargets()` - Save/verification (lignes 772-774, 807-821)

**Avant**:
```javascript
console.debug('🔍 DEBUG proposeTargets - before normalization BTC:', proposedTargets.BTC);
// Appelé 30+ fois → 30+ logs identiques
```

**Après**:
```javascript
if (window.__DEBUG_TARGETS_VERBOSE__) {
  console.debug('🔍 DEBUG proposeTargets - before normalization BTC:', proposedTargets.BTC);
}
// Aucun log par défaut, activable si besoin
```

#### 2. `static/selectors/governance.js`

**Logs optimisés**:
- `selectPolicyCapPercent()` - 11 appels de sélection (lignes 81-198)
- `selectEngineCapPercent()` - Détection cap engine
- `selectCapPercent()` - Sélection cap policy vs engine
- `selectEffectiveCap()` - Cap effectif avec fallbacks

**Avant**:
```javascript
console.debug('[CAP-SELECTOR] selectPolicyCapPercent:', { raw, result, ... });
// Appelé 50+ fois → 50+ logs identiques
```

**Après**:
```javascript
if (window.__DEBUG_GOVERNANCE_VERBOSE__) {
  console.debug('[CAP-SELECTOR] selectPolicyCapPercent:', { raw, result, ... });
}
```

#### 3. `static/modules/market-regimes.js`

**Logs optimisés**:
- `allocateRiskyBudget()` - 5 étapes de calcul (lignes 332-406)
  - CALLED (entrée fonction)
  - BEFORE bias (allocation initiale)
  - AFTER bias (après ajustements)
  - Total before normalization
  - FINAL RESULT (résultat final)

**Avant**:
```javascript
debugLogger.debug('🚨 [allocateRiskyBudget] CALLED - riskyPercentage:', riskyPercentage, ...);
// Appelé 20+ fois → 20+ logs identiques
```

**Après**:
```javascript
if (window.__DEBUG_MARKET_REGIMES_VERBOSE__) {
  debugLogger.debug('🚨 [allocateRiskyBudget] CALLED - riskyPercentage:', riskyPercentage, ...);
}
```

#### 4. `static/components/risk-sidebar-full.js`

**Optimisation supplémentaire**: Debouncing des updates (150ms) avec comparaison de state pour éviter les re-renders inutiles.

---

## 🚀 Usage

### Mode Normal (Production/Dev Standard)

**Par défaut**: Tous les logs verbeux sont **désactivés**.

```
Console propre, lisible
Seuls les logs importants (erreurs, warnings, info de haut niveau) s'affichent
Performance optimale
```

### Mode Debug Verbeux (Investigation)

**Pour activer temporairement** les logs détaillés:

```javascript
// Dans la console du navigateur (F12)

// Activer tous les logs
window.__DEBUG_TARGETS_VERBOSE__ = true;
window.__DEBUG_GOVERNANCE_VERBOSE__ = true;
window.__DEBUG_MARKET_REGIMES_VERBOSE__ = true;

// Recharger la page
location.reload();
```

**Pour activer sélectivement** (investigation ciblée):

```javascript
// Seulement les logs de targets
window.__DEBUG_TARGETS_VERBOSE__ = true;
location.reload();

// Ou seulement les logs de gouvernance (CAP-SELECTOR)
window.__DEBUG_GOVERNANCE_VERBOSE__ = true;
location.reload();

// Ou seulement les logs de market regimes
window.__DEBUG_MARKET_REGIMES_VERBOSE__ = true;
location.reload();
```

**Pour désactiver**:

```javascript
// Désactiver tous
window.__DEBUG_TARGETS_VERBOSE__ = false;
window.__DEBUG_GOVERNANCE_VERBOSE__ = false;
window.__DEBUG_MARKET_REGIMES_VERBOSE__ = false;
location.reload();

// Ou simplement recharger sans définir les flags
// (par défaut = désactivés)
```

---

## 📊 Résultats

### Avant Optimisation

```
Console à l'ouverture de risk-dashboard.html:
- 50+ logs [CAP-SELECTOR]
- 30+ logs proposeTargets
- 20+ logs allocateRiskyBudget
- 10+ logs applyTargets

TOTAL: ~110 logs répétitifs en quelques secondes
→ Console illisible
→ Performance dégradée
```

### Après Optimisation

```
Console à l'ouverture de risk-dashboard.html:
- 0 log [CAP-SELECTOR] (désactivé par défaut)
- 0 log proposeTargets (désactivé par défaut)
- 0 log allocateRiskyBudget (désactivé par défaut)
- 0 log applyTargets (désactivé par défaut)

TOTAL: ~0 log répétitif
→ Console propre ✅
→ Performance optimale ✅
→ Logs activables sur demande ✅
```

**Réduction**: **110+ → 0** logs répétitifs (-100%)

---

## 🎯 Catégories de Logs

### 1. Logs Toujours Actifs (Importants)

Ces logs restent **toujours visibles** car ils sont critiques:

```javascript
// Erreurs
debugLogger.error('❌ API failed:', error);
console.error('Fatal error:', err);

// Warnings importants
debugLogger.warn('⚠️ Cache expired');
console.warn('API rate limit approaching');

// Informations de haut niveau
console.log('✅ Dashboard initialized');
console.log('✅ Store hydrated successfully');
```

### 2. Logs Conditionnels Verbeux (Debug)

Ces logs sont **désactivés par défaut**, activables via feature flags:

```javascript
// Targets (window.__DEBUG_TARGETS_VERBOSE__)
if (window.__DEBUG_TARGETS_VERBOSE__) {
  console.debug('🔍 DEBUG proposeTargets - before normalization...');
}

// Governance (window.__DEBUG_GOVERNANCE_VERBOSE__)
if (window.__DEBUG_GOVERNANCE_VERBOSE__) {
  console.debug('[CAP-SELECTOR] selectPolicyCapPercent:', {...});
}

// Market Regimes (window.__DEBUG_MARKET_REGIMES_VERBOSE__)
if (window.__DEBUG_MARKET_REGIMES_VERBOSE__) {
  debugLogger.debug('🚨 [allocateRiskyBudget] CALLED...');
}
```

---

## 🛠️ Guidelines pour Ajouter des Logs

### Principe

**Logs répétitifs** (appelés 10+ fois) → Rendre **conditionnels** avec feature flag
**Logs uniques** (appelés 1-2 fois) → Laisser **actifs**

### Exemple: Ajouter un Log Conditionnel

Si vous devez ajouter un log de debug dans une fonction appelée fréquemment:

```javascript
// ❌ MAUVAIS: Log toujours actif (pollue la console)
export function calculateSomething(value) {
  console.debug('Calculating:', value);  // Appelé 50x → 50 logs
  return value * 2;
}

// ✅ BON: Log conditionnel (propre par défaut)
export function calculateSomething(value) {
  if (window.__DEBUG_MY_MODULE_VERBOSE__) {
    console.debug('Calculating:', value);  // Activable sur demande
  }
  return value * 2;
}
```

### Nommer le Feature Flag

Convention: `window.__DEBUG_{MODULE}_VERBOSE__`

Exemples:
- `window.__DEBUG_TARGETS_VERBOSE__` (targets-coordinator.js)
- `window.__DEBUG_GOVERNANCE_VERBOSE__` (governance.js)
- `window.__DEBUG_MARKET_REGIMES_VERBOSE__` (market-regimes.js)
- `window.__DEBUG_SIMULATOR_VERBOSE__` (simulation-engine.js)
- etc.

---

## 🔗 Fichiers Modifiés

| Fichier | Lignes Modifiées | Feature Flag |
|---------|------------------|--------------|
| `static/modules/targets-coordinator.js` | 676, 685, 772-774, 807-821 | `__DEBUG_TARGETS_VERBOSE__` |
| `static/selectors/governance.js` | 81-198 (11 logs) | `__DEBUG_GOVERNANCE_VERBOSE__` |
| `static/modules/market-regimes.js` | 332-406 (5 logs) | `__DEBUG_MARKET_REGIMES_VERBOSE__` |
| `static/components/risk-sidebar-full.js` | 76-237 (debouncing) | N/A (optimization) |

**Total**: 4 fichiers, ~20 logs rendus conditionnels

---

## 📝 Commit

```
feat(logs): add conditional verbose logging with feature flags

- Add 3 feature flags for verbose debug logging:
  * __DEBUG_TARGETS_VERBOSE__ (targets-coordinator.js)
  * __DEBUG_GOVERNANCE_VERBOSE__ (governance.js)
  * __DEBUG_MARKET_REGIMES_VERBOSE__ (market-regimes.js)

- Make ~20 repetitive DEBUG logs conditional (default: disabled)
- Add debouncing to risk-sidebar-full (150ms, state comparison)
- Reduce console pollution: ~110+ → 0 repetitive logs

Performance:
- Console readable by default
- ~110 repetitive logs eliminated
- Logs activable on-demand for debugging
- No functional impact

Files:
- static/modules/targets-coordinator.js
- static/selectors/governance.js
- static/modules/market-regimes.js
- static/components/risk-sidebar-full.js
- docs/LOG_OPTIMIZATION_OCT_2025.md (new)

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 📅 Historique

**17 octobre 2025** - v1.0.0
- ✅ Identification des logs répétitifs (110+ occurrences)
- ✅ Création de 3 feature flags conditionnels
- ✅ Optimisation de 4 fichiers
- ✅ Réduction console pollution: -100% logs répétitifs
- ✅ Documentation complète

---

**Auteur**: Claude Code
**Status**: ✅ Complété
**Impact**: High (lisibilité console + performance)
