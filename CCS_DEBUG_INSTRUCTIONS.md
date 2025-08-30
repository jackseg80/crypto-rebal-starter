# 🔍 Instructions de Debug CCS

## Problème
- **Risk Dashboard "Proposed Targets"**: BTC: 32.1%, ETH: 24.2%, etc.
- **Rebalance après sync CCS**: BTC: 29.4%, ETH: 19.6%, etc.

## Debug ajouté

J'ai ajouté des logs de debug dans plusieurs fichiers pour tracer le flux de données:

### Dans `targets-coordinator.js`:
- `proposeTargets()` - avant et après normalisation
- `applyTargets()` - avant et après sauvegarde localStorage

### Dans `risk-dashboard.html`:
- `renderTargetsContent()` - valeurs utilisées pour l'affichage
- `applyStrategy()` - valeurs passées entre fonctions

## Instructions pour diagnostiquer

1. **Ouvrir Risk Dashboard** → onglet "Targets"
2. **Ouvrir Console du navigateur** (F12)
3. **Observer les logs** de `renderTargetsContent` (valeurs affichées)
4. **Cliquer sur "Blended Strategy"**
5. **Observer les logs** de `applyStrategy` et `applyTargets` (valeurs sauvegardées)

## Que chercher

### Cas 1: Affichage = Sauvegarde
```
DEBUG renderTargetsContent - BTC allocation for DISPLAY: 32.1
DEBUG applyTargets - BTC allocation: 32.1
```
→ **Le problème est dans rebalance.html**

### Cas 2: Affichage ≠ Sauvegarde  
```
DEBUG renderTargetsContent - BTC allocation for DISPLAY: 32.1
DEBUG applyTargets - BTC allocation: 29.4
```
→ **Le problème est dans Risk Dashboard (entre display et save)**

## Hypothèses les plus probables

1. **Cycle multipliers**: Risk Dashboard applique des multipliers de cycle qui ne sont pas visibles
2. **CCS score différent**: L'affichage utilise un score, la sauvegarde en utilise un autre
3. **Double normalisation**: Les données sont normalisées deux fois

## Fichiers de test créés

- `debug_data_flow.html` - Test des fonctions de base
- `test_cycle_multipliers.html` - Analyse des multipliers
- `final_diagnosis.html` - Test complet du pipeline
- `diagnostic_test.html` - Reproduction de l'issue exacte

## Prochaine étape

Une fois que vous aurez identifié où se produit la différence (affichage vs sauvegarde), nous pourrons corriger le problème spécifique.