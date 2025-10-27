# 🎭 Guide de Test des Phases - Phase Engine Risky-Only

## Vue d'ensemble

Le nouveau Phase Engine utilise une architecture **risky-only, zero-sum** où :
- Les **Stablecoins ne sont JAMAIS modifiées** par les tilts de phase
- Tous les tilts opèrent uniquement sur les actifs risqués
- Compensation zero-sum entre actifs risqués uniquement

## 🎮 Comment Tester les Phases

### 1. Page de Test Dédiée
```
http://localhost:8000/static/test-theoretical-targets.html
```

Cette page permet de :
- ✅ Forcer des phases spécifiques
- ✅ Voir les objectifs théoriques en temps réel
- ✅ Comparer toutes les phases côte à côte
- ✅ Lancer des tests de validation automatiques

### 2. Forçage Manuel des Phases

#### Via controls debug (Console F12) :
```javascript
// Activer le mode Apply (appliquer les tilts)
localStorage.setItem('PHASE_ENGINE_ENABLED', 'apply');

// Forcer une phase
window.debugPhaseEngine.forcePhase('eth_expansion');

// Retour à l'auto-détection
window.debugPhaseEngine.clearForcePhase();

// Recharger pour voir les effets
location.reload();
```

#### Ou via localStorage :
```javascript
// Forcer une phase
localStorage.setItem('PHASE_ENGINE_DEBUG_FORCE', 'eth_expansion');

// Retour à l'auto-détection
localStorage.removeItem('PHASE_ENGINE_DEBUG_FORCE');
```

#### Phases disponibles :
- `'neutral'` - Aucun tilt appliqué
- `'risk_off'` - Aucun tilt appliqué (risky-only policy)
- `'eth_expansion'` - ETH +5%, L2/Scaling +3%
- `'largecap_altseason'` - L1/L0 majors +6%, SOL +4%
- `'full_altseason'` - L2 +8%, DeFi +6%, AI +4%, Gaming +6%, Memes +1% absolu

## 📊 Objectifs Théoriques Attendus

### Phase: **neutral** / **risk_off**
```
Aucun tilt appliqué - allocation de base selon stratégie
```

### Phase: **eth_expansion**
```
✅ ETH: +5% (multiplicateur 1.05)
✅ L2/Scaling: +3% (multiplicateur 1.03)
❌ Compensation prise sur: BTC uniquement
✅ Stablecoins: INCHANGÉES
```

### Phase: **largecap_altseason**
```
✅ L1/L0 majors: +6% (multiplicateur 1.06)
✅ SOL: +4% (multiplicateur 1.04)
❌ Compensation prise sur: BTC + ETH (pro-rata)
✅ Stablecoins: INCHANGÉES
```

### Phase: **full_altseason**
```
✅ L2/Scaling: +8% (multiplicateur 1.08)
✅ DeFi: +6% (multiplicateur 1.06)
✅ AI/Data: +4% (multiplicateur 1.04)
✅ Gaming/NFT: +6% (multiplicateur 1.06)
✅ Memecoins: +1% absolu (si DI≥80 && breadth≥80%)
❌ Compensation prise sur: BTC + L1/L0 majors
✅ Stablecoins: INCHANGÉES
```

## 🧪 Tests de Validation Critiques

### 1. **Préservation des Stablecoins**
```javascript
// Test: Stablecoins identiques sur toutes les phases
const phases = ['neutral', 'risk_off', 'eth_expansion', 'largecap_altseason', 'full_altseason'];
// ✅ Stablecoins% doit être identique pour toutes les phases
```

### 2. **Somme = 100%**
```javascript
// Test: Intégrité des allocations
const total = Object.values(targets).reduce((sum, val) => sum + val, 0);
// ✅ Math.abs(total - 100) < 0.1
```

### 3. **Zero-sum dans le pool risky**
```javascript
// Test: Compensation correcte
const riskySum = Object.entries(targets)
  .filter(([asset]) => asset !== 'Stablecoins')
  .reduce((sum, [, val]) => sum + val, 0);
// ✅ riskySum = 100 - stablecoins_percentage
```

### 4. **Caps respectés**
```javascript
// Caps configurés:
const caps = {
  'L2/Scaling': 8,     // ≤ 8%
  'DeFi': 8,           // ≤ 8%
  'Gaming/NFT': 5,     // ≤ 5%
  'Memecoins': 2,      // ≤ 2%
  'Others': 2          // ≤ 2%
};
```

### 5. **Tilts appliqués uniquement si pertinent**
```javascript
// Test: Tilts conditionnels
// ✅ neutral/risk_off → NO tilts
// ✅ autres phases → tilts appliqués selon config
```

## 🔍 Débugging

### Logs à surveiller (Console F12) :
```
🎯 PhaseEngine: Applying risky-only phase tilts
😐 PhaseEngine: neutral phase, no tilts applied
✅ PhaseEngine: Risky-only tilts applied successfully
🔒 Stables préservées: X.X% → X.X%
✅ PhaseEngine Apply Mode - TARGETS MODIFIED
🚀 PhaseEngine: Using cached phase-tilted targets (sync)
```

### Erreurs communes :
- **Somme ≠ 100%** → Problème de normalisation
- **Stables modifiées** → Violation risky-only
- **Caps dépassés** → applyCapsAndNormalize échoué
- **Tilts non appliqués** → Vérifier phase détectée
- **⚠️ PhaseEngine: No targets returned** → Min-effect filter trop restrictif

### Fix récent (2025-09-18) :
**Problème** : Min-effect filter avec seuil 0.03% annulait les tilts `full_altseason`
**Solution** : Seuil réduit à 0.01% pour préserver les petits tilts multiplicatifs
**Localisation** : `static/core/phase-engine.js:720`

## 🚀 Pages de Test Recommandées

1. **Test complet** : `test-theoretical-targets.html`
2. **Test unitaire** : `test-phase-engine.html`
3. **Analytics intégrés** : `analytics-unified.html`
4. **Rebalance** : `rebalance.html`

## 📈 Workflow de Test Complet

1. **Ouvrir la page de test** : `test-theoretical-targets.html`
2. **Tester chaque phase** via les boutons de phase
3. **Vérifier stables préservées** sur toutes les phases
4. **Comparer les allocations** avec le bouton "Comparer"
5. **Lancer validation** avec bouton "Tests de Validation"
6. **Vérifier logs console** pour détails techniques

## ⚡ Tests Rapides

### Test express en console :
```javascript
// Activer le mode Apply
localStorage.setItem('PHASE_ENGINE_ENABLED', 'apply');

// Test neutral
window.debugPhaseEngine.clearForcePhase();
location.reload();
// Observer les targets dans l'interface

// Test full_altseason
window.debugPhaseEngine.forcePhase('full_altseason');
location.reload();
// Observer les targets modifiés

// Test ETH expansion
window.debugPhaseEngine.forcePhase('eth_expansion');
location.reload();
// Observer ETH et L2/Scaling augmentés

// Nettoyer
window.debugPhaseEngine.clearForcePhase();
localStorage.setItem('PHASE_ENGINE_ENABLED', 'shadow');
```

## 🎯 Critères de Succès

- ✅ **Stables préservées** sur toutes les phases
- ✅ **Somme = 100%** toujours respectée
- ✅ **Tilts phase-spécifiques** appliqués correctement
- ✅ **Caps respectés** sans exception
- ✅ **Zero-sum** dans le pool risky uniquement
- ✅ **Pas de régression** vs objectifs de base
- ✅ **Logs clairs** et informatifs