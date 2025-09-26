# Pull Request – Crypto Rebal Starter

## Description
Cette PR introduit des corrections critiques sur le backend et une refonte majeure du système de gestion d'état côté frontend pour améliorer la robustesse, la maintenabilité et la cohérence de l'application.

### Backend (`api/main.py`)

- **Corrections de Bugs Bloquants :**
  - Correction d'une `IndentationError` qui empêchait le démarrage du serveur.
  - Correction de la logique d'import de secours pour `cointracking_api` qui était systématiquement écrasée par `None`.
  - Remplacement d'une référence à `PricingException` (non importée) par une capture d'exception générique pour éviter les `NameError`.

- **Refactoring et Qualité :**
  - Suppression de l'import et du montage en double du `wealth_router` pour clarifier le code.
  - Amélioration de la robustesse de la gestion des erreurs.

### Frontend (`static/core/risk-dashboard-store.js`)

- **Refonte du Store d'État :**
  - Le store global (`risk-dashboard-store.js`) a été entièrement refactorisé pour utiliser un pattern `createStore` (type pub/sub, inspiré de Zustand) beaucoup plus robuste et prévisible.
  - L'état est maintenant géré de manière plus sûre, encourageant l'immutabilité et centralisant la logique de mise à jour.

- **Fiabilisation de l'État :**
  - Standardisation de la structure de l'état initial pour éviter les erreurs sur des valeurs `null` (ex: `governance.active_policy`).
  - Correction des types de données incohérents (ex: `pending_approvals` est maintenant toujours un tableau).
  - Ajout de helpers `deepGet` et `deepSet` pour une manipulation plus sûre de l'état imbriqué.

## Type de changement
- [ ] feat : nouvelle fonctionnalité
- [x] fix : correction de bug
- [x] refactor : simplification / optimisation
- [x] docs : mise à jour documentation
- [ ] test : ajout ou correction de tests
- [ ] chore : maintenance / CI/CD

## Checklist
- [x] Les tests locaux passent
- [x] Les invariants métier sont respectés
- [x] La documentation a été mise à jour
- [x] La PR est claire et limitée à une seule fonctionnalité/fix

## Liens utiles
Issues liées : #
