# Migration OnChain Score V1 → V2

**Date:** 2 octobre 2025
**Statut:** ✅ Complété

## Contexte

Le système utilisait deux versions de calcul du score OnChain:
- **V1** (`calculateCompositeScore` dans `onchain-indicators.js`) - Score simple, obsolète
- **V2** (`calculateCompositeScoreV2` dans `composite-score-v2.js`) - Score avancé avec:
  - Gestion spéciale des indicateurs problématiques (Coin Days Destroyed, Jours depuis halving)
  - Réduction de corrélation entre indicateurs similaires
  - Dynamic weighting adaptatif selon la phase de marché

## Problèmes Identifiés

### 1. Scores Incohérents Entre Pages

**Symptôme:**
- `risk-dashboard.html` (Market Cycles tab): OnChain = 36
- `analytics-unified.html`: OnChain = 42 (puis 36 après visite Market Cycles)
- `risk-data-orchestrator.js`: OnChain = 42

**Cause:**
- L'orchestrator utilisait V1 (score=42)
- Market Cycles tab utilisait V2 (score=36)
- Résultat différent selon le chemin de navigation

### 2. Risk Score Cache Race Condition

**Symptôme:**
- Hard refresh (Ctrl+Shift+R) sur `analytics-unified.html`: Risk = 37
- Refresh normal (F5): Risk = 50

**Cause:**
- Orchestrator hydratait le store avec Risk = 50 ✅
- `loadUnifiedData()` dans analytics-unified.html chargeait ensuite le Risk depuis cache/API
- Cache contenait l'ancienne valeur (37) qui écrasait la bonne (50) ❌

### 3. Checkbox "Adaptation contextuelle" Obsolète

**Symptôme:**
- Checkbox permettait de toggle dynamic weighting ON/OFF
- Complexité inutile: V2 avec dynamic weighting devrait toujours être activé

## Solution Implémentée

### A. Unification sur V2 (Dynamic Weighting Always ON)

**Fichiers modifiés:**

1. **`static/core/risk-data-orchestrator.js`**
   - Ligne 8: Import `calculateCompositeScoreV2` de `composite-score-v2.js`
   - Ligne 178: Appel `calculateCompositeScoreV2(indicators, true)` (force dynamic weighting)
   - ✅ Orchestrator utilise maintenant V2

2. **`static/risk-dashboard.html`**
   - Lignes 5443-5446: Checkbox "Adaptation contextuelle" supprimée
   - Lignes 3619-3663: Fonctions `toggleDynamicWeighting()` et `initializeDynamicWeightingToggle()` supprimées
   - Lignes 3366, 5051: Force `calculateCompositeScoreV2(indicators, true)`
   - ✅ V2 toujours actif, UI simplifiée

3. **`static/analytics-unified.html`**
   - Lignes 751-753: Détection hard refresh ajoutée
   - Lignes 773, 788: Force `calculateCompositeScoreV2(indicators, true)`
   - ✅ V2 toujours actif, hard refresh détecté

4. **`static/simulations.html`**
   - Ligne 1245: Force `calculateCompositeScoreV2(indicators, true)`
   - ✅ V2 toujours actif

5. **`static/modules/onchain-indicators.js`**
   - Ligne 36: Import `calculateCompositeScoreV2` de `composite-score-v2.js`
   - Ligne 1512: Fonction `calculateCompositeScore()` V1 supprimée (132 lignes)
   - Lignes 1653, 1684: `enhanceCycleScore()` et `analyzeDivergence()` utilisent V2
   - ✅ V1 complètement supprimé

6. **`static/modules/historical-validator.js`**
   - Ligne 12: Import V1 supprimé
   - Lignes 223-236: Code de comparaison V1 vs V2 supprimé
   - ✅ Plus de référence à V1

### B. Fix Race Condition Risk Score

**Fichier:** `static/analytics-unified.html`

**Avant (lignes 698-724):**
```javascript
// 1) Risk (backend) - With cache
if (!force && isCacheValid(CACHE_CONFIG.risk.key, CACHE_CONFIG.risk.ttl)) {
  const riskData = getCache(CACHE_CONFIG.risk.key);
  store.set('risk', riskData);
  const rs = riskData?.risk_metrics?.risk_score;
  if (typeof rs === 'number') store.set('scores.risk', rs); // ❌ Écrase orchestrator
}
```

**Après (lignes 698-717):**
```javascript
// 1) Risk (backend) - Use orchestrator's hydrated value (DON'T OVERWRITE)
const existingRiskScore = store.get('scores.risk');
if (typeof existingRiskScore === 'number') {
  console.log(`✅ Risk score already hydrated by orchestrator: ${existingRiskScore}`);
  loadedFromCache++;
} else {
  // Wait for orchestrator hydration if not ready
  await new Promise(resolve => {
    window.addEventListener('riskStoreReady', handler, { once: true });
    setTimeout(resolve, 2000); // Fallback timeout
  });
}
```

**Principe:**
- Analytics-unified.html **ne charge plus** le Risk Score lui-même
- Il lit simplement `store.get('scores.risk')` déjà hydraté par l'orchestrator
- Évite la race condition: orchestrator = source de vérité unique

## Résultats

### Scores Unifiés (Production)

| Score | Valeur | Source | Cohérence |
|-------|--------|--------|-----------|
| **OnChain** | 36 | V2 (dynamic weighting) | ✅ Partout |
| **Risk** | 50 | Orchestrator | ✅ Partout (même hard refresh) |
| **CCS Mixte** | Variable | Signals Engine | ✅ Cohérent |
| **Cycle** | 100 | Cycle Navigator | ✅ Cohérent |

### Vérification

**Test 1: Hard Refresh**
```bash
# Avant: OnChain=42, Risk=37
# Après: OnChain=36, Risk=50
```

**Test 2: Navigation Market Cycles → Analytics**
```bash
# Avant: OnChain change de 42 → 36 → 42
# Après: OnChain stable à 36 partout
```

**Test 3: Recherche Code V1**
```bash
grep -r "calculateCompositeScore(" static/ --include="*.js" --include="*.html" | grep -v "V2"
# Résultat: Aucune référence V1 ✅
```

## Architecture Finale

```
┌─────────────────────────────────────────────────────────────┐
│                     risk-data-orchestrator.js                │
│                    (Single Source of Truth)                  │
│                                                              │
│  import { calculateCompositeScoreV2 } from 'composite-score-v2.js'  │
│                                                              │
│  onchainScore = calculateCompositeScoreV2(indicators, true)  │
│  store.set('scores.onchain', onchainScore)  // 36           │
│  store.set('scores.risk', riskScore)        // 50           │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       │ riskStoreReady event
                       ▼
        ┌──────────────────────────────────────┐
        │  All Pages (read-only)               │
        ├──────────────────────────────────────┤
        │  • analytics-unified.html            │
        │  • risk-dashboard.html               │
        │  • simulations.html                  │
        │  • rebalance.html                    │
        │                                      │
        │  const score = store.get('scores.*') │
        └──────────────────────────────────────┘
```

## Migration Checklist

- [x] Orchestrator utilise V2
- [x] Tous les fichiers utilisent V2 avec dynamic weighting ON
- [x] Fonction V1 supprimée de onchain-indicators.js
- [x] Imports V1 supprimés partout
- [x] Checkbox "Adaptation contextuelle" supprimée
- [x] Fonctions toggle supprimées
- [x] Analytics-unified.html lit Risk depuis orchestrator (pas de fetch)
- [x] Hard refresh force cache refresh OnChain
- [x] Tests manuels validés (hard refresh, navigation)
- [x] Aucune référence V1 dans le code

## Notes Techniques

### Dynamic Weighting (V2)

Le dynamic weighting ajuste automatiquement les poids des catégories d'indicateurs selon la phase de marché détectée:

```javascript
// Exemple: Phase "Early Expansion"
{
  onchain_pure: 0.35,      // Boost valuation metrics
  cycle_technical: 0.30,   // Standard cycle indicators
  sentiment_social: 0.20,  // Reduced sentiment weight
  market_context: 0.15     // Context indicators
}
```

**Phases supportées:**
- Accumulation
- Early Expansion
- Late Expansion
- Euphoria
- Distribution
- Bear Market

### Indicateurs Problématiques Gérés

**V2 applique des normalisations spéciales:**

1. **Coin Days Destroyed (CDD)**
   ```javascript
   // CDD on 90d → score 0..100 by percentile
   rawValue = Math.min(100, Math.max(0, (rawValue / 20000000) * 100));
   ```

2. **Jours depuis halving**
   ```javascript
   // Days since halving → 0..100 on [0..1460] (≈ 4 years)
   rawValue = Math.min(100, Math.max(0, (rawValue / 1460) * 100));
   ```

## Références

- **Source code:** `static/modules/composite-score-v2.js`
- **Documentation:** `docs/RISK_SEMANTICS.md`
- **Orchestrator:** `static/core/risk-data-orchestrator.js`
