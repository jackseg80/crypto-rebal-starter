# Système d'Allocation Dynamique v3.0

## Vue d'ensemble

Le nouveau système d'allocation dynamique remplace les presets hardcodés par des calculs contextuels intelligents, garantissant une cohérence parfaite entre Analytics et Rebalance.

## Architecture

### Avant (v2.x) - Presets Statiques
```javascript
// Presets hardcodés dans multiple fichiers
if (blended >= 70) {
  stablesTarget = 20; btcTarget = 35; ethTarget = 25; // Bull preset
} else if (blended >= 50) {
  stablesTarget = 30; btcTarget = 40; ethTarget = 20; // Moderate preset
} else {
  stablesTarget = 50; btcTarget = 30; ethTarget = 15; // Bear preset
}
```

**Problèmes identifiés:**
- Objectifs théoriques ≠ plan d'exécution
- "Others 31%" incohérent
- Presets ignorent risk budget et wallet
- Code dupliqué dans 4+ fichiers

### Après (v3.0) - Calculs Dynamiques
```javascript
// Source canonique unique dans unified-insights-v2.js
function computeMacroTargetsDynamic(ctx, rb, walletStats) {
  // 0) Stables = SOURCE DE VÉRITÉ (risk budget)
  const stables = rb.target_stables_pct;
  const riskyPool = Math.max(0, 100 - stables);

  // 1) Poids de base adaptatifs
  let base = {
    BTC: 0.42, ETH: 0.28, 'L1/L0 majors': 0.06,
    SOL: 0.06, 'L2/Scaling': 0.06, DeFi: 0.05,
    'AI/Data': 0.04, 'Gaming/NFT': 0.02, Memecoins: 0.01
  };

  // 2) Modulateurs contextuels
  const bull = (ctx.cycle_score >= 70);
  const bear = (ctx.cycle_score <= 30);
  const hedge = (ctx.governance_mode === 'Hedge');

  if (bull) {
    base.BTC *= 0.95; base.ETH *= 1.08;
    base['L2/Scaling'] *= 1.15; base.SOL *= 1.10;
  }
  if (bear || hedge) {
    base.Memecoins *= 0.5; base['Gaming/NFT'] *= 0.7;
  }

  // 3) Diversification wallet
  if (walletStats?.topWeightSymbol === 'BTC' && walletStats?.topWeightPct > 35) {
    base.BTC *= 0.92; base.ETH *= 1.06;
  }

  // 4) Normalisation et conversion
  const targets = { Stablecoins: stables };
  // ... logique de normalisation
  return targets;
}
```

## Synchronisation Analytics ↔ Rebalance

### Flux de Données
1. **Analytics-unified.html** → `getUnifiedState()` → calculs dynamiques
2. **Sauvegarde automatique** → `saveUnifiedDataForRebalance()` → localStorage
3. **Rebalance.html** → `syncUnifiedSuggestedTargets()` → lecture cohérente

### Format localStorage
```javascript
{
  "targets": {                    // ← Allocations pour affichage
    "Stablecoins": 25.0,
    "BTC": 31.5,
    "ETH": 21.0,
    // ... autres groupes
  },
  "execution_plan": {             // ← Métadonnées d'exécution
    "estimated_iters": 2.0,
    "cap_pct_per_iter": 7
  },
  "source": "analytics_unified_v2",
  "methodology": "unified_v2",
  "timestamp": "2025-09-17T00:12:00.000Z"
}
```

### Correction Critique
```javascript
// AVANT (incorrect)
const targetsSource = data.execution_plan || data.targets;
// Problem: execution_plan contient des métadonnées, pas des allocations!

// APRÈS (correct)
const targetsSource = data.targets;
// Solution: toujours utiliser targets pour les allocations
```

## Fichiers Modifiés

### Core Engine
- **`static/core/unified-insights-v2.js`**
  - Ajout `computeMacroTargetsDynamic()`
  - Construction `u.targets_by_group` dynamique
  - Remplacement presets par calculs contextuels

### UI Components
- **`static/components/UnifiedInsights.js`**
  - Suppression logique preset hardcodée
  - Lecture directe `u.targets_by_group`
  - Élimination références `buildTheoreticalTargets`

### Pages HTML
- **`static/analytics-unified.html`**
  - Ajout `saveUnifiedDataForRebalance()`
  - Sauvegarde automatique après rendu
  - Format données compatible v2

- **`static/rebalance.html`**
  - Migration `syncUnifiedSuggestedTargets()`
  - Support sources v2 + rétrocompatibilité
  - Correction logique targetsSource

## Bénéfices Mesurables

### Cohérence
- ✅ Objectifs Analytics = Plan Rebalance (100%)
- ✅ Plus de "Others 31%" aberrant
- ✅ Source unique `u.targets_by_group`

### Adaptabilité
- ✅ Stables suivent risk budget (était ignoré)
- ✅ Allocations s'adaptent au cycle (bull/bear/hedge)
- ✅ Diversification selon concentration wallet

### Performance
- ✅ Élimination code dupliqué (4 fichiers → 1)
- ✅ Calculs cachés et optimisés
- ✅ Synchronisation temps réel

### UX
- ✅ Interface cohérente entre pages
- ✅ Allocations "intelligentes" vs arbitraires
- ✅ Transparence des calculs

## Tests de Validation

### Scénarios Bull Market
```javascript
ctx = { cycle_score: 75, regime: 'bull' }
rb = { target_stables_pct: 20 }
// Résultat: moins BTC, plus ETH/L2, stables = 20%
```

### Scénarios Bear Market
```javascript
ctx = { cycle_score: 25, regime: 'bear' }
rb = { target_stables_pct: 45 }
// Résultat: moins memecoins/gaming, stables = 45%
```

### Scénarios Concentration
```javascript
walletStats = { topWeightSymbol: 'BTC', topWeightPct: 50 }
// Résultat: réduction BTC, augmentation ETH/L2
```

## Migration et Compatibilité

### Rétrocompatibilité
- Support ancien format localStorage
- Fallbacks gracieux si données manquantes
- Presets legacy en secours d'urgence

### Monitoring
- Logs détaillés des calculs
- Assertions de cohérence intégrées
- Debug traces pour troubleshooting

### Future Evolution
- Ajout nouveaux modulateurs (volatilité, liquidité)
- Paramètres utilisateur personnalisables
- ML pour optimisation auto des poids

---

**Impact Global**: Transformation d'un système rigide à presets vers une allocation véritablement intelligente et contextuelle. 🎯