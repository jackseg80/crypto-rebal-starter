# Allocation Engine V2 - Topdown Hierarchical

> **Version**: 2.0
> **Date**: Octobre 2025
> **Statut**: ✅ Production

## 📊 Vue d'Ensemble

L'Allocation Engine V2 calcule l'allocation optimale du portfolio via une **descente hiérarchique à 3 niveaux** avec floors contextuels, incumbency protection et renormalisation proportionnelle.

**Fichier source**: [`static/core/allocation-engine.js`](../static/core/allocation-engine.js)

---

## 🏗️ Architecture Hiérarchique

### Niveau 1 - MACRO
**Distribution entre grandes classes d'actifs** :
- **BTC** (Bitcoin)
- **ETH** (Ethereum)
- **Stablecoins** (USDT, USDC, DAI, etc.)
- **Alts** (Total pour tous les altcoins)

### Niveau 2 - SECTEURS
**Redistribution des Alts vers secteurs** :
- SOL (Solana)
- L1/L0 majors (Avalanche, Polygon, Cosmos, etc.)
- L2/Scaling (Arbitrum, Optimism, zkSync, etc.)
- DeFi (Uniswap, Aave, Curve, etc.)
- Memecoins (PEPE, BONK, DOGE, SHIB, etc.)
- Gaming/NFT (AXS, SAND, IMX, etc.)
- AI/Data (FET, OCEAN, GRT, etc.)
- Others (reste)

### Niveau 3 - COINS
**Allocation individuelle avec protections** :
- Incumbency protection (3% minimum pour assets détenus)
- Meme cap (limite globale memecoins selon régime)
- Caps par catégorie (risque)

---

## 🎯 Mécanismes Clés

### 1. Floors Contextuels

Les **floors** (allocations minimales) varient selon la **phase du cycle** :

#### Floors de BASE (toujours actifs)
```javascript
{
  'BTC': 0.15,           // 15% minimum
  'ETH': 0.12,           // 12% minimum
  'Stablecoins': 0.10,   // 10% minimum sécurité
  'SOL': 0.03,           // 3% minimum
  'L1/L0 majors': 0.08,  // 8% minimum diversification
  'L2/Scaling': 0.03,
  'DeFi': 0.04,
  'Memecoins': 0.02,
  'Gaming/NFT': 0.01,
  'AI/Data': 0.01,
  'Others': 0.01
}
```

#### Floors BULLISH (Cycle Score ≥ 90)
```javascript
{
  'SOL': 0.06,           // 3% → 6% (DOUBLE)
  'L1/L0 majors': 0.12,  // 8% → 12% (+50%)
  'L2/Scaling': 0.06,    // 3% → 6% (DOUBLE)
  'DeFi': 0.08,          // 4% → 8% (DOUBLE)
  'Memecoins': 0.05,     // 2% → 5% (×2.5)
  'Gaming/NFT': 0.02,    // 1% → 2% (DOUBLE)
  'AI/Data': 0.02        // 1% → 2% (DOUBLE)
}
```

**Détection phase** (ligne 104):
```javascript
const isBullishPhase = cycleScore >= 90;
const isModeratePhase = cycleScore >= 70 && cycleScore < 90;
const isBearishPhase = cycleScore < 70;
```

---

### 2. Incumbency Protection

**Règle** : Aucun asset **actuellement détenu** ne peut descendre sous **3%** dans l'allocation cible.

**Implémentation** (ligne 55):
```javascript
const FLOORS_CONFIG = {
  incumbency: 0.03  // 3% minimum pour assets détenus
};
```

**Rationale** :
- Évite liquidations forcées d'assets existants
- Maintient diversification minimale
- Réduit coûts de transaction (pas de vente complète)

**Exemple** :
```
Portfolio actuel:
- BTC: 10%, ETH: 8%, SOL: 2%, DOGE: 1%

Target théorique (bearish):
- BTC: 35%, ETH: 25%, SOL: 5%, DOGE: 0%  ← DOGE à 0%!

Target APRÈS incumbency:
- BTC: 34%, ETH: 24%, SOL: 5%, DOGE: 3%  ← DOGE protégé à 3%
```

---

### 3. Renormalisation Proportionnelle

**Principe** : Les **stablecoins** sont la SOURCE DE VÉRITÉ, les **risky assets** se partagent l'espace restant **proportionnellement**.

#### Formule (lignes 214-274)

```javascript
// 1. Source unique: risk_budget.target_stables_pct
const stablesTarget = risk_budget.target_stables_pct / 100;  // Ex: 0.25 (25%)

// 2. Espace disponible pour risky assets
const nonStablesSpace = 1 - stablesTarget;  // Ex: 0.75 (75%)

// 3. Ratios de base selon cycle (AVANT renormalisation)
let baseBtcRatio, baseEthRatio, baseAltsRatio;

if (cycleScore >= 90) {
  // Bull market: plus d'alts
  baseBtcRatio = 0.25;   // 25%
  baseEthRatio = 0.20;   // 20%
  baseAltsRatio = 0.55;  // 55%
} else if (cycleScore >= 70) {
  // Modéré: équilibré
  baseBtcRatio = 0.30;
  baseEthRatio = 0.22;
  baseAltsRatio = 0.48;
} else {
  // Bearish: défensif
  baseBtcRatio = 0.35;
  baseEthRatio = 0.25;
  baseAltsRatio = 0.40;
}

// 4. RENORMALISATION proportionnelle
const baseTotal = baseBtcRatio + baseEthRatio + baseAltsRatio;  // = 1.0

btcTarget = (baseBtcRatio / baseTotal) × nonStablesSpace;
ethTarget = (baseEthRatio / baseTotal) × nonStablesSpace;
altsTarget = (baseAltsRatio / baseTotal) × nonStablesSpace;
```

#### Exemple Concret

**Inputs** :
- `stablesTarget = 25%`
- `cycleScore = 85` (moderate phase)

**Calcul** :
```
nonStablesSpace = 100% - 25% = 75%

Ratios de base (moderate):
- baseBtcRatio = 0.30
- baseEthRatio = 0.22
- baseAltsRatio = 0.48
- baseTotal = 1.0

Renormalisation:
- btcTarget = (0.30 / 1.0) × 0.75 = 0.225 → 22.5%
- ethTarget = (0.22 / 1.0) × 0.75 = 0.165 → 16.5%
- altsTarget = (0.48 / 1.0) × 0.75 = 0.36  → 36%
```

**Résultat** :
```
Stablecoins: 25.0%  ← PRÉSERVÉ exactement
BTC:         22.5%  ← Proportionnel (30% du risky pool)
ETH:         16.5%  ← Proportionnel (22% du risky pool)
Alts:        36.0%  ← Proportionnel (48% du risky pool)
────────────────
TOTAL:       100%
```

**Garanties** :
- ✅ Stables **JAMAIS** affectés par tilts risky
- ✅ Proportions relatives risky **préservées**
- ✅ Somme = 100% **toujours**

---

### 4. Floors Enforcement

Si les floors causent un dépassement de 100%, l'engine **réduit les Alts en priorité**, puis BTC/ETH proportionnellement (lignes 252-267).

**Exemple** :
```
Avant floors:
- BTC: 22%, ETH: 18%, Stables: 30%, Alts: 30%

Après floors BTC≥15%, ETH≥12%, Stables≥10%:
- Floors OK (tous respectés)

Scénario extrême (Stables=60%):
- BTC floor: 15%
- ETH floor: 12%
- Stables floor: 60%
- → Total floors = 87%, reste 13% pour Alts
- Alts: max(5%, 13%) = 13%  ← Réduit au minimum viable
```

---

### 5. Validation & Checksum

**Contrôles hiérarchiques** (lignes 125-154) :

#### 1. Target Sum Check
```javascript
const targetSum = Object.values(coinAllocation).reduce((sum, val) => sum + val, 0);

if (Math.abs(targetSum - 1.0) > 0.01) {
  console.warn(`⚠️ target_sum_mismatch: ${(targetSum * 100).toFixed(1)}%`);
}
```

#### 2. Hierarchy Validation
```javascript
const hierarchyCheck = validateHierarchy(coinAllocation, currentPositions);
// Vérifie:
// - Pas de double-comptage (BTC individuel vs groupe "Majors")
// - Cohérence secteurs vs coins
// - Respect incumbency
```

#### 3. Normalization (si nécessaire)
```javascript
if (!totalCheck.isValid) {
  const scale = 1 / totalCheck.total;
  Object.keys(coinAllocation).forEach(key => {
    coinAllocation[key] *= scale;
  });
  console.warn('⚠️ Allocation normalized to sum to 1.0');
}
```

---

## 🔗 Intégration avec Autres Systèmes

### Structure Modulation V2

**deltaCap appliqué APRÈS gouvernance** (lignes 9-21):

```javascript
function getEffectiveCapWithStructure(state, deltaCap = 0) {
  const capEff = selectEffectiveCap(state);  // Gouvernance (staleness, alerts, policy)
  const adjusted = Math.max(0, capEff + (deltaCap || 0));
  const maxDelta = 0.5;  // Garde-fou: ±0.5% max
  return Math.min(adjusted, capEff + maxDelta);
}
```

**Extraction deltaCap** (lignes 100-101):
```javascript
const deltaCap = structure_modulation?.delta_cap ?? 0;
```

### Meme Cap (Regime-Based)

**Extraction depuis régime** (ligne 98):
```javascript
const meme_cap = regime?.allocation_bias?.meme_cap ?? null;
```

**Application au niveau 3** (ligne 119):
```javascript
const coinAllocation = calculateCoinAllocation(
  sectorAllocation,
  currentPositions,
  selectedFloors,
  meme_cap  // Appliqué ici
);
```

### Phase Engine Integration

Le Phase Engine est **transparent** : il modifie les targets AVANT qu'Allocation Engine V2 ne reçoive les inputs via `unified-insights-v2.js`.

**Flow** :
```
1. unified-insights-v2.js → getUnifiedState()
2. ├─> computeMacroTargetsDynamic() [avec Phase Engine tilts]
3. │   └─> applyPhaseTilts() si mode 'apply'
4. └─> Allocation Engine V2 reçoit targets PRÉ-TILTÉS
5.     └─> Applique floors, incumbency, caps
```

---

## 📊 Métadonnées Résultat

L'engine retourne un objet avec métadonnées complètes (lignes 175-198):

```javascript
{
  version: 'v2',
  allocation: {
    'BTC': 0.225,
    'ETH': 0.165,
    'Stablecoins': 0.25,
    'SOL': 0.06,
    // ...
  },
  execution: {
    cap_pct_per_iter: 5.5,  // Avec deltaCap appliqué
    estimated_iters_to_target: 3,
    current_iteration: 1,
    convergence_strategy: 'standard'
  },
  metadata: {
    phase: 'bullish',  // 'bearish', 'moderate', 'bullish'
    floors_applied: { ... },
    adaptive_weights: { cycle: 0.65, onchain: 0.25, risk: 0.10 },
    total_check: { isValid: true, total: 1.0 },
    meme_cap: {
      defined: true,
      value: 2,  // 2% max
      applied: true
    },
    structure_modulation: {
      structure_score: 85,
      delta_stables: -5,
      delta_cap: +0.5,
      stables_before: 30,
      stables_after: 25,
      cap_after: 5.5,
      enabled: true
    }
  }
}
```

---

## 🧪 Exemples Complets

### Exemple 1 : Bull Market (Cycle = 92)

**Inputs** :
```javascript
{
  cycleScore: 92,
  onchainScore: 75,
  riskScore: 80,
  risk_budget: { target_stables_pct: 20, min_stables: 10, max_stables: 60 },
  structure_modulation: { delta_stables: -5, delta_cap: +0.5 },
  currentPositions: [
    { symbol: 'BTC', value_usd: 10000 },
    { symbol: 'ETH', value_usd: 8000 },
    { symbol: 'SOL', value_usd: 3000 },
    { symbol: 'DOGE', value_usd: 500 }
  ]
}
```

**Calcul** :
```
1. Phase: bullish (cycle ≥ 90)
2. Stables: 20% - 5% (structure) = 15%
3. Risky pool: 85%
4. Ratios bullish: BTC=25%, ETH=20%, Alts=55%
5. Renormalisation:
   - BTC: 0.25 × 0.85 = 21.25%
   - ETH: 0.20 × 0.85 = 17%
   - Alts: 0.55 × 0.85 = 46.75%
6. Floors bullish:
   - BTC: max(21.25%, 15%) = 21.25%
   - ETH: max(17%, 12%) = 17%
   - SOL: max(6%, 6%) = 6%
   - DOGE: max(calculé, 3%) = 3%  ← Incumbency!
```

**Résultat** :
```json
{
  "Stablecoins": 15.0,
  "BTC": 21.3,
  "ETH": 17.0,
  "SOL": 6.0,
  "L1/L0 majors": 12.0,
  "L2/Scaling": 6.0,
  "DeFi": 8.0,
  "Memecoins": 5.0,
  "Gaming/NFT": 2.0,
  "AI/Data": 2.0,
  "Others": 5.7
}
```

### Exemple 2 : Bear Market (Cycle = 35)

**Inputs** :
```javascript
{
  cycleScore: 35,
  risk_budget: { target_stables_pct: 50 },
  structure_modulation: { delta_stables: +10 },  // Structure faible
  currentPositions: [...]
}
```

**Calcul** :
```
1. Phase: bearish (cycle < 70)
2. Stables: 50% + 10% (structure) = 60% (capped à max_stables)
3. Risky pool: 40%
4. Ratios bearish: BTC=35%, ETH=25%, Alts=40%
5. Renormalisation:
   - BTC: 0.35 × 0.40 = 14% → floor 15% = 15%
   - ETH: 0.25 × 0.40 = 10% → floor 12% = 12%
   - Alts: restant = 13%
```

**Résultat** :
```json
{
  "Stablecoins": 60.0,
  "BTC": 15.0,
  "ETH": 12.0,
  "L1/L0 majors": 8.0,
  "SOL": 3.0,
  "DeFi": 2.0
}
```

---

## 🔍 Debug & Logs

### Logs Console

```javascript
console.debug('🏗️ Allocation Engine called:', {
  enableV2: true,
  contextualScores: true
});

console.debug('📊 Market phase detection:', {
  cycleScore: 92,
  isBullishPhase: true,
  isModeratePhase: false
});

console.debug('🌍 Macro allocation:', {
  BTC: 0.2125,
  ETH: 0.17,
  Stablecoins: 0.15,
  Alts: 0.4675
});

console.debug('🏭 Sector allocation:', { ... });

console.debug('🪙 Coin allocation:', { ... });

console.debug('💯 CHECKSUM:', {
  total_allocation: 1.0,
  entries_count: 11,
  valid_entries: 11,
  is_normalized: true,
  hierarchy_ok: true,
  target_sum_ok: true
});
```

### Browser DevTools

```javascript
// Charger unified state
const { getUnifiedState } = await import('./core/unified-insights-v2.js');
const u = await getUnifiedState();

// Inspecter allocation
console.table(u.targets_by_group);

// Vérifier métadonnées
console.log(u.intelligence?.allocation);
```

---

## 📚 Références

### Documentation
- [DECISION_INDEX_V2.md](DECISION_INDEX_V2.md) - Decision Index vs Score de Régime
- [STRUCTURE_MODULATION_V2.md](STRUCTURE_MODULATION_V2.md) - Structure Modulation details
- [CLAUDE.md](../CLAUDE.md) - Guide général agent

### Code Source
- `static/core/allocation-engine.js` - Implémentation principale
- `static/core/unified-insights-v2.js` - Integration + Phase Engine
- `static/modules/market-regimes.js` - Risk Budget calculation
- `services/execution/governance.py` - Backend governance + caps

### Tests
```bash
# Pas de tests unitaires dédiés encore
# Validation via:
# - simulations.html (mode live)
# - analytics-unified.html (comparaison avec V1)
```

---

## ✅ Checklist IA

Avant de modifier l'Allocation Engine V2 :

- [ ] Je comprends la descente hiérarchique (Macro → Secteurs → Coins)
- [ ] Je sais que les stables sont la SOURCE DE VÉRITÉ (renormalisation proportionnelle)
- [ ] Je connais les floors contextuels (base vs bullish)
- [ ] Je sais que incumbency = 3% minimum pour assets détenus
- [ ] Je comprends que deltaCap est limité à ±0.5%
- [ ] J'ai vérifié que la somme = 100% ± 0.1%
- [ ] J'ai testé avec simulations.html en mode live

---

**Dernière mise à jour** : 2025-10-22
**Auteur** : Claude Code Analysis
**Statut** : ✅ Documentation complète et validée
