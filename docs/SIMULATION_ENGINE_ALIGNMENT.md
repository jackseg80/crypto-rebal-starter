# Simulation Engine ↔ Analytics Alignment

## Date
2025-09-30

## Objectif
Éliminer les divergences entre `simulation-engine.js` et `unified-insights-v2.js` pour garantir des résultats identiques (±0.1) entre Analytics Unified et le Simulateur.

---

## 🐛 Divergences Identifiées

### 1. BASE_WEIGHTS Différents ❌
**Problème** :
- `unified-insights-v2.js` : `wCycle=0.5, wOnchain=0.3, wRisk=0.2`
- `simulation-engine.js` : `{ cycle: 0.4, onchain: 0.35, risk: 0.25 }`

**Impact** : Decision Index différent dès le départ

### 2. Boost Cycle ≥ 90 Manquant ❌
**Problème** : Analytics v2 booste `wCycle` à 0.65 si cycle ≥ 90, mais Simulation n'avait pas cette règle.

**Impact** : Exposition alts sous-estimée en phase bullish

### 3. Poids Adaptatifs Non Appliqués ❌ (BUG CRITIQUE)
**Problème** :
- Ligne 1118: `weights` calculé via `calculateAdaptiveWeights`
- Ligne 434-436: `computeDecisionIndex` **ignore `context.weights`** et réinitialise à `0.50/0.30/0.20`

**Impact** : Les poids adaptatifs sont calculés mais jamais utilisés

### 4. Contradiction Source Différente ❌
**Problème** :
- Analytics : Utilise `governance.contradiction_index` comme source primaire
- Simulation : Heuristique `scoreSpread` (écart entre cycle/onchain)

**Impact** : Niveau de contradiction différent → caps différents

### 5. Risk Budget Source ❌
**Problème** :
- Analytics : Utilise `regimeData.risk_budget` depuis `market-regimes.js`
- Simulation : Calcul local linéaire/sigmoïde

**Impact** : Target stables différent si regimeData présent

---

## ✅ Corrections Appliquées

### 1. Alignement BASE_WEIGHTS
**Fichier** : `static/modules/simulation-engine.js` ligne 1028
```javascript
// Avant
const BASE_WEIGHTS = { cycle: 0.4, onchain: 0.35, risk: 0.25 };

// Après
const BASE_WEIGHTS = { cycle: 0.5, onchain: 0.3, risk: 0.2 };
```

### 2. Branchement context.weights
**Fichier** : `static/modules/simulation-engine.js` lignes 435-437
```javascript
// Avant
let wCycle = 0.50;
let wOnchain = 0.30;
let wRisk = 0.20;

// Après
let wCycle = context.weights?.cycle ?? context.weights?.wCycle ?? 0.50;
let wOnchain = context.weights?.onchain ?? context.weights?.wOnchain ?? 0.30;
let wRisk = context.weights?.risk ?? context.weights?.wRisk ?? 0.20;
```

### 3. Implémentation calculateAdaptiveWeights
**Fichier** : `static/modules/simulation-engine.js` lignes 33-71

Nouvelle implémentation qui réplique `unified-insights-v2.js` :
- ✅ Lecture de `governance.contradiction_index`
- ✅ Boost si `cycle ≥ 90` : `wCycle=0.65, wOnchain=0.25, wRisk=0.1`
- ✅ Boost si `cycle ≥ 70` : `wCycle=0.55, wOnchain=0.28, wRisk=0.17`
- ✅ Pénalité on-chain si `contradiction ≥ 50` : `-10%` (max)
- ✅ Normalisation des poids (somme = 1.0)

### 4. Priorité regimeData.risk_budget
**Fichier** : `static/modules/simulation-engine.js` lignes 1165-1177
```javascript
// Nouvelle logique
if (stateForEngine.regimeData?.risk_budget?.target_stables_pct != null) {
  riskBudget = {
    target_stables_pct: stateForEngine.regimeData.risk_budget.target_stables_pct,
    source: 'market-regimes (v2)',
    regime_based: true
  };
} else {
  riskBudget = computeRiskBudget(di.di, uiOverrides.riskBudget, ...);
}
```

---

## 🧪 Tests de Non-Régression

### Cas A : Cycle Élevé + Contradictions
**Input** :
```javascript
{
  cycle: 92,
  onchain: 30,
  risk: 50,
  governance: { contradiction_index: 0.6 }
}
```

**Expected** :
- ✅ `wCycle` boosted à `0.65`
- ✅ `wOnchain` réduit à `0.25` × 0.9 = `0.225` (pénalité contradiction)
- ✅ `wRisk = 0.1`
- ✅ Decision Index Analytics vs Simulations : **±0.1**

**Test** :
1. Ouvrir `analytics-unified.html` avec preset `cycle=92, contradiction=0.6`
2. Ouvrir `simulations.html` avec même preset
3. Comparer Decision Index

### Cas B : regimeData Présent
**Input** :
```javascript
{
  regimeData: {
    risk_budget: {
      target_stables_pct: 25
    }
  }
}
```

**Expected** :
- ✅ Risk budget = `25%` (même source)
- ✅ Console log : `"✅ SIM: Using regimeData.risk_budget as source of truth"`

**Test** :
1. Vérifier que `market-regimes.js` retourne un `risk_budget`
2. Simulateur doit utiliser cette valeur
3. Comparer targets stables Analytics vs Simulations

### Cas C : Import v2 Fail (Fallback)
**Input** : Forcer échec import `unified-insights-v2.js`

**Expected** :
- ✅ Fallback `calculateAdaptiveWeights` actif
- ✅ Console log : `"⚠️ SIM: Using fallback contradiction modules"`
- ✅ Boost cycle ≥ 90 toujours appliqué
- ✅ Résultats cohérents (pas identiques à Analytics mais raisonnables)

**Test** :
1. Temporairement renommer `unified-insights-v2.js`
2. Recharger simulateur
3. Vérifier logs + comportement

---

## 📊 Validation Console

### Logs Attendus (Cas A - Cycle 92 + Contradiction 0.6)

```
🚀 SIM: Adaptive weights - Cycle ≥ 90 → boost cycle influence
🔸 SIM: High contradiction → reduced onchain weight
⚖️ Adaptive weights calculated: {
  wCycle: 0.65,
  wOnchain: 0.225,
  wRisk: 0.125
}
🎭 SIM: diComputed - { di: 78, source: 'ccs_mixed', confidence: 0.85 }
```

### Logs Attendus (Cas B - regimeData présent)

```
✅ SIM: Using regimeData.risk_budget as source of truth: {
  target_stables_pct: 25,
  source: 'market-regimes (v2)',
  regime_based: true
}
```

---

## 🎯 Résultats Attendus

| Métrique | Avant | Après |
|----------|-------|-------|
| BASE_WEIGHTS | `0.4/0.35/0.25` | ✅ `0.5/0.3/0.2` |
| Boost cycle ≥ 90 | ❌ Absent | ✅ `wCycle=0.65` |
| Poids appliqués | ❌ Ignorés | ✅ Branchés |
| Risk budget source | Calcul local | ✅ `regimeData` si dispo |
| DI Analytics vs Sim | ±5-10 | ✅ ±0.1 |

---

## 📝 Commandes de Test Rapide

### 1. Test Console (Cas A)
```javascript
// Dans console du simulateur
const testState = {
  cycle: { score: 92 },
  scores: { onchain: 30, risk: 50 },
  governance: { contradiction_index: 0.6 }
};

const weights = contradictionModules.calculateAdaptiveWeights(
  { cycle: 0.5, onchain: 0.3, risk: 0.2 },
  testState
);

console.log('Weights:', weights);
// Expected: { cycle: 0.65, onchain: ~0.225, risk: 0.1 }
```

### 2. Test Preset
```javascript
// Utiliser preset "Altseason Peak" (cycle 95+)
// Vérifier console logs pour boost cycle
```

### 3. Comparaison Analytics ↔ Sim
```javascript
// Analytics: Onglet "Intelligence ML" → Decision Index
// Simulateur: Preset identique → Decision Index
// Différence doit être < 0.1
```

---

## ⚠️ Points d'Attention

### 1. Scaling par Confidences
`computeDecisionIndex` applique encore un scaling par confidences **après** avoir reçu les poids adaptatifs.
```javascript
wCycle *= (0.8 + 0.4 * confidences.cycle);
```

Ceci est **intentionnel** et cohérent avec Analytics. Les poids adaptatifs sont la base, le scaling par confidence affine ensuite.

### 2. Contradiction Heuristique
La détection de contradiction par `scoreSpread` (lignes 446-454) est **conservée** pour le fallback déterministe. Elle s'ajoute à `governance.contradiction_index` mais ne le remplace pas.

### 3. Risk Budget Fallback
Si `regimeData` est absent, le calcul linéaire/sigmoïde reste actif. C'est voulu pour éviter les blocages.

---

## 🔄 Prochaines Étapes (Optionnel)

### 1. Retry Import avec Backoff
Actuellement, si l'import de `unified-insights-v2.js` échoue au chargement, on reste en fallback.

**Amélioration** : Retry avec exponential backoff (3 tentatives × 500ms).

### 2. Harmoniser applyContradictionCaps
Le fallback actuel ne fait rien. Implémenter la vraie logique depuis `contradiction-policy.js`.

### 3. Tests Automatisés
Ajouter tests Jest/Vitest pour valider les cas A, B, C de façon automatique.

---

## 📚 Références

- **unified-insights-v2.js** : Source de vérité pour poids adaptatifs (lignes 42-94)
- **simulation-engine.js** : Réplique maintenant la logique v2 (lignes 33-71)
- **CLAUDE.md** : Documentation agent sur l'architecture
- **Issue GitHub** : [Divergences Simulation ↔ Analytics](#) (à créer si besoin)

---

**Dernière mise à jour** : 2025-09-30
**Version** : 1.0
**Auteur** : Claude + Jack