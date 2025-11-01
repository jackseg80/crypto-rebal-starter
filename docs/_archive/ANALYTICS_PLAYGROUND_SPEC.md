# Analytics Playground - Spécification Complète

**Version:** 1.0
**Date:** 2025-09-30
**Status:** 🚧 En développement

## Objectif

Créer un outil de **What-If Analysis** permettant de simuler différentes phases du cycle crypto **sur le wallet réel de l'utilisateur** pour voir l'impact immédiat sur:
- Decision Index
- Allocations cibles par groupe
- Risk Budget (% stables)
- Plan d'exécution (ordres nécessaires)

## Cas d'Usage

**Question:** "Que se passerait-il sur MON wallet si on entrait en bear market demain?"

**Réponse:** Le Playground applique les overrides du preset "Bear Entry" sur les vraies données du wallet et affiche une comparaison AVANT ↔ APRÈS détaillée.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  📊 Analytics Playground                                     │
├─────────────────────────────────────────────────────────────┤
│  Header                                                      │
│  ├─ Source: [cointracking_api ▼]  [🧪 Test]                │
│  ├─ User: jack                                               │
│  └─ Mode: [💼 Actuel] [🎭 Simulation]                       │
├─────────────────────────────────────────────────────────────┤
│  🎮 Contrôles (Flyout Panel - Left Side)                    │
│  ┌───────────────────────────────────────────────┐          │
│  │ 🎯 Presets de Phases                          │          │
│  │  • 💼 Données Actuelles (baseline)            │          │
│  │  • 🐂 Bull Run - Début                        │          │
│  │  • 🚀 Bull Run - Euphorie                    │          │
│  │  • 🐻 Bear Market - Entrée                   │          │
│  │  • ❄️ Bear Market - Capitulation             │          │
│  │  • 🌱 Phase de Récupération                  │          │
│  │  • 🌊 Altseason Approche                     │          │
│  │  • 🎆 Altseason - Pic                        │          │
│  │  • ⚠️ Crash Imminent                         │          │
│  │  • ↔️ Marché Latéral                         │          │
│  ├───────────────────────────────────────────────┤          │
│  │ 🎚️ Overrides Manuels                         │          │
│  │  Cycle Score:   [████░░░░░░] 70               │          │
│  │  Onchain:       [███████░░░] 55               │          │
│  │  Risk Score:    [█████░░░░░] 45               │          │
│  │  Contradiction: [██░░░░░░░░] 20%              │          │
│  │  Risk Appetite: [Conservative|Balanced|Aggr]  │          │
│  ├───────────────────────────────────────────────┤          │
│  │ 🔄 Actions                                     │          │
│  │  [🔄 Recalculer] [↻ Reset to Current]        │          │
│  └───────────────────────────────────────────────┘          │
├─────────────────────────────────────────────────────────────┤
│  📊 Vue Comparative (Split Screen)                          │
│  ┌──────────────────────────┬──────────────────────────┐   │
│  │ 💼 WALLET ACTUEL         │ 🎭 SIMULATION            │   │
│  │ (Données réelles)         │ (Preset: Bear Entry)     │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │ 🎯 Decision Index        │                          │   │
│  │   65/100 (80%)           │ 35/100 (75%) ⚠️ -30     │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │ 📊 Scores Composites     │                          │   │
│  │   Cycle:   100 🟢        │ Cycle:   35 🟡 -65       │   │
│  │   Onchain:  72 🟢        │ Onchain:  40 🟡 -32      │   │
│  │   Risk:     34 🟢        │ Risk:     55 🟠 +21      │   │
│  │   Contrad:  48% 🟠       │ Contrad:  45% 🟠 -3%     │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │ 💰 Risk Budget           │                          │   │
│  │   34% stables            │ 48% stables ⬆️ +14%     │   │
│  │   66% risky              │ 52% risky ⬇️ -14%       │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │ 📈 Allocations Groupes   │                          │   │
│  │   BTC:         44.3%     │ BTC:     35.0% ⬇️ -9.3%  │   │
│  │   ETH:         22.8%     │ ETH:     17.0% ⬇️ -5.8%  │   │
│  │   Stablecoins: 34.2%     │ Stables: 48.0% ⬆️ +13.8% │   │
│  │   SOL:          2.3%     │ SOL:      0.0% ⬇️ -2.3%  │   │
│  │   L1/L0:       10.5%     │ L1/L0:    8.0% ⬇️ -2.5%  │   │
│  │   L2/Scaling:   4.1%     │ L2:       2.0% ⬇️ -2.1%  │   │
│  │   DeFi:         3.2%     │ DeFi:     1.5% ⬇️ -1.7%  │   │
│  │   Memecoins:    1.8%     │ Memes:    0.5% ⬇️ -1.3%  │   │
│  │   Others:       8.8%     │ Others:   5.0% ⬇️ -3.8%  │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │ 🔄 Plan d'Exécution      │                          │   │
│  │   Total Delta: 37.8%     │ Total Delta: 58.6%       │   │
│  │   Itérations: 5 rebals   │ Itérations: 8 rebals     │   │
│  │   Temps estimé: 5 jours  │ Temps: 8 jours           │   │
│  │                           │                          │   │
│  │   Top Moves:             │ Top Moves:               │   │
│  │   • Stables: +1.0%       │ • Stables: +1.0% ⬆️      │   │
│  │   • BTC: -1.0%           │ • BTC: -1.0% ⬇️          │   │
│  │   • ETH: -1.0%           │ • ETH: -1.0% ⬇️          │   │
│  └──────────────────────────┴──────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  📝 Résumé & Recommandations                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⚠️ IMPACT MAJEUR DÉTECTÉ                            │   │
│  │                                                       │   │
│  │ En cas d'entrée en bear market:                      │   │
│  │ • Decision Index chuterait de 65 → 35 (-46%)        │   │
│  │ • Stables passeraient de 34% → 48% (+41%)           │   │
│  │ • Réduction forte des alts (-24.8% au total)        │   │
│  │                                                       │   │
│  │ 📊 Actions suggérées:                                │   │
│  │ 1. Augmenter stables progressivement (+1%/jour)     │   │
│  │ 2. Réduire exposition SOL/L2/Memecoins en priorité  │   │
│  │ 3. Maintenir core BTC/ETH (quality bias)            │   │
│  │ 4. Éviter ventes paniques (exécution graduée 8j)    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Flux de Données

### Mode Actuel (💼 Baseline)
```
1. Load user wallet (loadBalanceData)
2. Load unified data (loadUnifiedData)
   ├─ Risk scores
   ├─ Cycle scores
   ├─ Onchain indicators
   └─ Balances → store
3. Call getUnifiedState()
   └─ Returns: decision, governance, allocations, risk_budget
4. Display in LEFT column
```

### Mode Simulation (🎭 What-If)
```
1. User selects preset "Bear Entry"
2. Load preset overrides:
   ├─ cycle_score: 35
   ├─ onchain_score: 40
   ├─ risk_score: 55
   ├─ contradiction_pct: 45
   └─ risk_appetite: conservative
3. Call getUnifiedState(overrides)
   └─ Recalculates with overridden values
4. Display in RIGHT column
5. Calculate deltas (RIGHT - LEFT)
6. Highlight significant changes (>5%)
```

## Implémentation

### Phase 1: Initialisation Correcte du Store ✅
```javascript
// Dans loadLiveData() du simulateur
async function loadPlaygroundData() {
  // 1. Charger données complètes AVANT getUnifiedState()
  await loadUnifiedDataComplete(); // Import depuis analytics-unified.html

  // 2. Maintenant getUnifiedState() aura toutes les données
  const currentState = await getUnifiedState();

  return currentState;
}
```

### Phase 2: Charger et Appliquer Presets 🚧
```javascript
// Charger presets
const presets = await fetch('/static/presets/cycle_phase_presets.json').then(r => r.json());

// Appliquer preset
async function applyPreset(presetId) {
  const preset = presets.presets.find(p => p.id === presetId);

  // Créer overrides state
  const overrides = {
    cycle: { score: preset.overrides.cycle_score },
    onchain: { score: preset.overrides.onchain_score },
    risk: { score: preset.overrides.risk_score },
    governance: {
      contradiction_index: preset.overrides.contradiction_pct / 100
    }
  };

  // Recalculer avec overrides
  const simulatedState = await getUnifiedState(overrides);

  return simulatedState;
}
```

### Phase 3: Affichage Comparatif 🚧
```javascript
function displayComparison(currentState, simulatedState) {
  // Left column: current
  displayColumn('before', {
    di: currentState.decision.score,
    contradiction: currentState.governance.contradiction_index,
    allocations: currentState.targets_by_group,
    riskBudget: currentState.risk.budget
  });

  // Right column: simulated
  displayColumn('after', {
    di: simulatedState.decision.score,
    contradiction: simulatedState.governance.contradiction_index,
    allocations: simulatedState.targets_by_group,
    riskBudget: simulatedState.risk.budget
  });

  // Deltas
  displayDeltas({
    di: simulatedState.decision.score - currentState.decision.score,
    stables: simulatedState.risk.budget.target_stables_pct - currentState.risk.budget.target_stables_pct,
    allocations: calculateAllocationDeltas(currentState.targets_by_group, simulatedState.targets_by_group)
  });
}
```

### Phase 4: Overrides Manuels 🚧
```html
<div class="manual-overrides">
  <label>Cycle Score</label>
  <input type="range" id="cycle-override" min="0" max="100" value="70">
  <span id="cycle-value">70</span>

  <label>Onchain Score</label>
  <input type="range" id="onchain-override" min="0" max="100" value="55">
  <span id="onchain-value">55</span>

  <!-- etc. -->
</div>

<script>
document.getElementById('cycle-override').addEventListener('input', (e) => {
  document.getElementById('cycle-value').textContent = e.target.value;
  debounce(() => recalculateWithOverrides(), 300);
});
</script>
```

## Fonctionnalités Avancées

### 1. Comparaison Multi-Presets
Afficher 3 colonnes: Actuel | Bear Entry | Bull Peak

### 2. Export Rapport
Bouton "📄 Export PDF" générant un rapport avec:
- Snapshot du wallet actuel
- Scénario simulé
- Deltas détaillés
- Recommandations d'actions

### 3. Historique de Simulations
Sauvegarder les simulations précédentes dans localStorage pour revue

### 4. Alertes Intelligentes
```javascript
if (Math.abs(deltaDI) > 20) {
  alert(`⚠️ IMPACT MAJEUR: Le DI changerait de ${deltaDI > 0 ? '+' : ''}${deltaDI} points!`);
}
```

### 5. Animation de Transition
Animer les changements entre Actuel → Simulé avec gsap/framer-motion

## Problèmes à Résoudre

### ❌ Problème 1: getUnifiedState() retourne valeurs par défaut
**Symptôme:** DI toujours 50, contradiction 0%

**Cause:** Store pas initialisé avant l'appel

**Solution:** Appeler `loadUnifiedData()` d'analytics-unified.html AVANT `getUnifiedState()`

### ❌ Problème 2: Overrides non pris en compte
**Cause:** getUnifiedState() n'accepte pas de paramètre overrides actuellement

**Solution:** Modifier unified-insights-v2.js pour accepter overrides optionnels

```javascript
// unified-insights-v2.js
export async function getUnifiedState(overrides = {}) {
  // Si overrides fournis, les appliquer sur le state calculé
  const baseState = await calculateUnifiedState();

  if (Object.keys(overrides).length > 0) {
    return applyOverrides(baseState, overrides);
  }

  return baseState;
}
```

## Tests

### Test 1: Preset Bear Entry
```javascript
// Avant
DI: 65, Stables: 34%

// Après preset "Bear Entry"
DI: 35 (-30), Stables: 48% (+14%)

// Assertion
assert(Math.abs(simulatedDI - 35) < 5, 'DI should be ~35 in bear entry');
assert(Math.abs(simulatedStables - 48) < 3, 'Stables should be ~48% in bear entry');
```

### Test 2: Preset Euphoria
```javascript
// Avant
DI: 65, Stables: 34%

// Après preset "Euphoria"
DI: 90 (+25), Stables: 18% (-16%)

// Assertion
assert(simulatedDI > 85, 'DI should be very high in euphoria');
assert(simulatedStables < 20, 'Stables should be minimal in euphoria');
```

## Roadmap

### ✅ Phase 1 (Complétée)
- [x] Créer presets de phases (cycle_phase_presets.json)
- [x] 10 scénarios définis avec overrides

### 🚧 Phase 2 (En cours)
- [ ] Initialiser store correctement dans simulateur
- [ ] Intégrer loadUnifiedData() depuis analytics
- [ ] Appeler getUnifiedState() avec données complètes

### 📋 Phase 3 (Prochaine)
- [ ] Affichage split AVANT ↔ APRÈS
- [ ] Calcul et affichage des deltas
- [ ] Sélecteur de presets fonctionnel

### 📋 Phase 4 (Future)
- [ ] Overrides manuels avec sliders
- [ ] Bouton "Recalculer" temps réel
- [ ] Résumé & recommandations intelligentes

### 📋 Phase 5 (Future)
- [ ] Export PDF
- [ ] Historique simulations
- [ ] Comparaison multi-presets
- [ ] Animations de transition

## Notes Importantes

1. **Ne PAS mélanger modes:** Live mode actuel du simulateur reste pour tester l'engine. Playground est un outil séparé.

2. **Performance:** Cache loadUnifiedData() pour éviter rechargements inutiles

3. **UX:** Indiquer clairement "SIMULATION" en mode What-If pour éviter confusion

4. **Données sensibles:** Les simulations ne touchent jamais au wallet réel (read-only)

5. **Compatibilité:** S'assurer que getUnifiedState(overrides) reste backward-compatible

## Documentation Utilisateur

### Comment utiliser l'Analytics Playground?

1. **Ouvrir** http://localhost:8080/static/analytics-playground.html
2. **Sélectionner** ton user (jack) et source (cointracking_api)
3. **Voir** colonne gauche = état actuel de ton wallet
4. **Choisir** un preset dans le panneau (ex: "🐻 Bear Market - Entrée")
5. **Comparer** colonne droite = ce qui arriverait dans ce scénario
6. **Analyser** les deltas (changements) colorés
7. **Ajuster** manuellement les paramètres si besoin
8. **Exporter** le rapport pour documentation

## Références

- [cycle_phase_presets.json](../static/presets/cycle_phase_presets.json) - Presets de phases
- [unified-insights-v2.js](../static/core/unified-insights-v2.js) - Système de calcul unifié
- [analytics-unified.html](../static/analytics-unified.html) - Référence pour loadUnifiedData()
- [simulations.html](../static/simulations.html) - Base du simulateur actuel
- [SIMULATOR_USER_ISOLATION_FIX.md](SIMULATOR_USER_ISOLATION_FIX.md) - Fix isolation multi-user

---

**Dernière mise à jour:** 2025-09-30
**Auteur:** Claude Code
**Status:** 🚧 Spécification en développement actif
