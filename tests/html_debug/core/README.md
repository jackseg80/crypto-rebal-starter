# Core System Tests

Tests fondamentaux pour les composants système critiques.

## Tests disponibles

- **debug_11_groups.html** - Test original du problème 11 groupes
- **debug_11_groups_fix.html** - Version corrigée avec diagnostics complets  
- **debug_ccs_check.html** - Vérification système CCS
- **debug_ccs_flow.html** - Test du flux de données CCS
- **debug_ccs_sync.html** - Test synchronisation CCS
- **test_ccs_modules.html** - Test modules CCS individuels

## Usage

Ces tests vérifient le bon fonctionnement des composants système de base :
- Génération des 11 groupes d'actifs
- Système de scoring CCS (Crypto Cycle Score)  
- Synchronisation entre modules
- Intégrité des calculs backend

## Ordre de test recommandé

1. `debug_11_groups_fix.html` - Diagnostic complet système
2. `test_ccs_modules.html` - Validation modules CCS
3. `debug_ccs_sync.html` - Test synchronisation