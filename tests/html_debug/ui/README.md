# UI & Interface Tests

Tests des interfaces utilisateur et interactions.

## Tests disponibles

- **test_navigation_ui.html** - Test navigation et menus
- **fix_strategy_buttons.html** - Correction boutons stratégie  
- **test_strategy_buttons.html** - Test boutons stratégie
- **test_debug_menu.html** - Test menu debug intégré
- **debug_apply_button.html** - Debug bouton Apply

## Usage  

Tests spécifiques aux interfaces utilisateur :
- Fonctionnement des boutons et interactions
- Navigation entre pages
- Intégration du système de debug
- Validation des formulaires et inputs
- Cohérence visuelle et UX

## Ordre de test recommandé

1. `test_navigation_ui.html` - Test navigation générale
2. `test_debug_menu.html` - Validation menu debug  
3. `test_strategy_buttons.html` - Test boutons stratégie
4. Tests de correction si problèmes détectés