# Guide de Test - Intégration CCS → Rebalance

## 🧪 Fichiers de Test Disponibles

### 1. `test_dynamic_targets_e2e.html` ✅ 
**Test API complet** - Teste l'intégration backend CCS → Rebalance
- Ouvrir dans le navigateur
- Cliquer sur "Lancer tous les tests" 
- Vérifie: API, dynamic_targets, exec_hint, différents scenarios CCS

### 2. `test_rebalance_simple.html` ✅
**Test Interface** - Simule l'usage de `window.rebalanceAPI`
- Ouvrir dans le navigateur  
- Cliquer sur "Simuler Interface rebalanceAPI"
- Simule les appels sans problèmes de cross-origin

## 🎯 Test Manuel de l'Interface Réelle

Pour tester la vraie interface `window.rebalanceAPI` dans `rebalance.html`:

1. **Ouvrir** `http://localhost:8001/static/rebalance.html`
2. **Console développeur** (F12)  
3. **Exécuter les commandes**:

```javascript
// Test 1: Définir dynamic targets avec CCS=75 (conservateur)
window.rebalanceAPI.setDynamicTargets(
    { BTC: 45, ETH: 20, Stablecoins: 20, SOL: 8, "L1/L0 majors": 7 }, 
    { ccs: 75, autoRun: true }
);
```

**Résultats attendus:**
- 🟡 Indicateur "🎯 CCS 75" apparaît en haut à droite
- 🚀 Plan se génère automatiquement (autoRun: true)
- 📊 Allocation conservatrice (plus de BTC/Stablecoins)

```javascript
// Test 2: Vérifier l'état actuel
console.log(window.rebalanceAPI.getCurrentTargets());
// Doit retourner: {dynamic: true, targets: {...}}
```

```javascript  
// Test 3: CCS=15 (euphorie - risqué)
window.rebalanceAPI.setDynamicTargets(
    { BTC: 25, ETH: 30, Stablecoins: 5, SOL: 20, "L1/L0 majors": 20 }, 
    { ccs: 15, autoRun: true }
);
```

**Résultats attendus:**
- 🟡 Indicateur devient "🎯 CCS 15" 
- 📊 Allocation risquée (moins de BTC, plus d'alts)

```javascript
// Test 4: Retour au mode manuel
window.rebalanceAPI.clearDynamicTargets();
```

**Résultats attendus:**
- 🔄 Indicateur disparaît
- 📊 Retour aux targets manuels par défaut

## ✅ Points de Vérification

### Backend (API)
- ✅ Parameter `dynamic_targets=true` respecté
- ✅ `exec_hint` présent dans toutes les actions (JSON + CSV)  
- ✅ Targets dynamiques appliqués vs targets manuels
- ✅ Backward compatibility (pas de dynamic_targets = mode manuel)

### Frontend (Interface)
- ✅ `window.rebalanceAPI` disponible
- ✅ Indicateur visuel dynamic targets
- ✅ Switching manuel ↔ dynamique sans conflit
- ✅ Metadata CCS affiché correctement

### Integration E2E  
- ✅ CCS → API → Actions avec exec_hint
- ✅ Différents scenarios (euphorie vs accumulation)
- ✅ Auto-génération du plan (autoRun)
- ✅ Persistance des targets pendant la session

## 🔗 Intégration avec Module CCS Existant

Le module CCS du fichier `rapport_crypto_dashboard_v70_2.html` peut maintenant intégrer via:

```javascript
// Dans le module CCS, bouton "Apply as targets"
document.getElementById('btnApplyTargets').onclick = function() {
    const currentCCS = calculateCCS(); // votre logique CCS
    const dynamicTargets = applyFreeToTargetsFromCCS(baseTargets, currentCCS, 0.3);
    
    // Intégration avec rebalance.html
    if (window.rebalanceAPI) {
        window.rebalanceAPI.setDynamicTargets(dynamicTargets, {
            ccs: currentCCS,
            source: 'cycles_module',
            autoRun: true
        });
    }
};
```

## 🚀 Prêt pour Production

L'intégration CCS → Rebalance est complètement fonctionnelle:
- Backend API étendu avec dynamic_targets et exec_hint
- Frontend avec interface claire et indicateurs visuels  
- Tests E2E validés
- Backward compatibility assurée
- Documentation complète