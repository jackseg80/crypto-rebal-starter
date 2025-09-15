# Validation & Quality Assurance Tests

Tests de validation finale et assurance qualité.

## Tests disponibles

- **validation_finale.html** - Test de validation complète du système
- **score-consistency-validator.html** - Validation cohérence scores
- **test-scores.html** - Test système de scoring
- **test-v2-comprehensive.html** - Test complet système V2
- **test-v2-quick.html** - Test rapide système V2

## Usage

Tests de validation et qualité :
- Validation complète avant mise en production
- Vérification cohérence des scores et calculs
- Tests de régression système  
- Validation des nouvelles fonctionnalités
- Contrôle qualité global

## Scénarios de validation

- **Cohérence des données** : Vérification intégrité
- **Précision des calculs** : Validation algorithmique
- **Performance système** : Test sous charge
- **Robustesse** : Test cas limites et erreurs
- **Compatibilité** : Test versions et browsers

## Ordre de test recommandé

1. `test-v2-quick.html` - Test rapide global
2. `score-consistency-validator.html` - Validation scores  
3. `test-v2-comprehensive.html` - Test complet
4. `validation_finale.html` - Validation finale complète