# Plan de développement raffiné - Crypto Rebal Starter

## Vue d'ensemble
Plan structuré en phases pour activer et optimiser les composants dormants (ML Alert Predictor, Advanced Risk Engine) tout en corrigeant les bugs critiques identifiés.

---

## Phase 1A - Correction & Nettoyage (1-2 semaines)

### Bugs critiques
- **Endpoint acknowledge 500** : Investiguer l'erreur dans `/api/alerts/acknowledge/{alert_id}` (probablement `self.metrics.increment()`)
- **Unification système alertes** : Centraliser la logique dispersée autour de l'AlertEngine principal
- **CSP warnings** : Nettoyer les violations Content Security Policy dans risk-dashboard.html
- **Gestion d'erreurs API** : Améliorer les messages d'erreur côté frontend (acknowledge/snooze)

### Nettoyage technique
- **Suppression code mort** : Enlever les fonctions/routes/components non utilisés identifiés
- **Consolidation alertes** : S'assurer que tous les types d'alertes passent par l'AlertEngine central
- **Optimisation endpoints** : Réduire les appels API redondants dans risk-dashboard.html

**Livrables** :
- Bug acknowledge réparé
- Système d'alertes unifié et documenté
- Code nettoyé et optimisé

---

## Phase 1B - Monitoring & Documentation (1 semaine)

### Monitoring opérationnel
- **Dashboard système** : Créer une page simple de monitoring des composants actifs/dormants
- **Logs centralisés** : Améliorer le logging pour diagnostic plus facile des pannes
- **Health checks** : Endpoint `/health` détaillé avec statut des sous-systèmes

### Documentation technique
- **Architecture réelle** : Documenter l'état actuel vs les plans initiaux
- **Guide troubleshooting** : Procédures de diagnostic pour les problèmes courants
- **API documentation** : Compléter la doc des endpoints existants

**Livrables** :
- Dashboard de monitoring opérationnel
- Documentation à jour et complète

---

## Phase 2 - Activation ML & Advanced Risk (3-4 semaines)

### ML Alert Predictor (scope réduit)
- **Dataset limité** : Commencer avec BTC/ETH uniquement (données les plus fiables)
- **Modèles simples** : Activer RandomForest en priorité, GradientBoosting en second
- **Validation rigoureuse** : Tests approfondis avant activation en production
- **Métriques de performance** : Precision/Recall pour évaluer la qualité des prédictions

### Advanced Risk Engine (batch processing)
- **VaR parametric/historical** : Activation immédiate (calculs légers)
- **Monte Carlo en batch** : Calculs overnight/hebdomadaires, pas en temps réel
- **Stress testing** : Scénarios limités aux plus critiques (2008, COVID-20, China ban)
- **Alertes VaR** : Intégration dans le système d'alertes existant

### Intégration progressive
- **Tests isolés** : Chaque composant testé séparément avant intégration
- **Rollback plan** : Possibilité de désactiver rapidement si problème
- **Monitoring** : Surveillance étroite des performances et ressources

**Livrables** :
- ML Alert Predictor opérationnel sur BTC/ETH
- Advanced Risk Engine avec calculs VaR
- Système d'alertes prédictives fonctionnel

---

## Phase 3 - Optimisation & Fiabilisation (2-3 semaines)

### Performance
- **Cache intelligent** : Optimiser les calculs répétitifs
- **Batch processing** : Consolider les calculs lourds
- **API rate limiting** : Protéger les endpoints sensibles

### Fiabilité
- **Circuit breakers** : Protection contre les pannes en cascade
- **Graceful degradation** : Fonctionnement dégradé si ML/Risk indisponibles
- **Backup strategies** : Fallback sur méthodes simples si échec des modèles

### Monitoring avancé
- **Métriques business** : Tracking de la qualité des prédictions
- **Alertes système** : Notifications automatiques en cas de dysfonctionnement
- **Performance dashboards** : Visualisation des métriques système

**Livrables** :
- Système robuste et performant
- Monitoring complet et alertes système
- Documentation opérationnelle

---

## Phase 4 - Extensions stratégiques (scope contrôlé)

### Périmètre limité pour éviter scope creep
- **Extension BTC/ETH → Top 5-10 cryptos** : Seulement si Phase 2 est stable
- **WebSocket optimization** : Amélioration du streaming existant uniquement
- **UI/UX polish** : Corrections mineures, pas de refonte majeure

### Validation continue
- **Checkpoints** : Validation à chaque étape avant passage à la suivante
- **User feedback** : Retours utilisateur pour prioriser les améliorations
- **Performance monitoring** : Surveillance continue des impacts

### Critères de succès
- ML Predictor : >70% precision sur BTC/ETH sur 1 mois
- Advanced Risk : VaR calculations opérationnelles sans impact performance
- Système global : Disponibilité >99.5%

**Livrables** :
- Extension contrôlée du périmètre
- Système mature et stable
- Métriques de succès atteintes

---

## Points de vigilance intégrés

### Technique
- **Ressources limitées** : Monte Carlo en batch uniquement
- **Données limitées** : Commencer BTC/ETH, étendre prudemment
- **Rollback ready** : Possibilité de revenir en arrière à tout moment

### Opérationnel
- **Phases courtes** : Livraisons fréquentes pour validation
- **Monitoring continu** : Surveillance étroite à chaque phase
- **Documentation vivante** : Mise à jour continue de la documentation

### Stratégique
- **Scope discipline** : Résister aux ajouts non planifiés
- **Value focus** : Prioriser les fonctionnalités à forte valeur ajoutée
- **User centric** : Validation utilisateur à chaque étape majeure

---

## Timeline estimé
- **Phase 1A** : 2 semaines
- **Phase 1B** : 1 semaine  
- **Phase 2** : 4 semaines
- **Phase 3** : 3 semaines
- **Phase 4** : 4 semaines (si validé)

**Total** : ~14 semaines avec buffer pour imprévus

Ce plan intègre vos retours sur la limitation du scope, la séparation des phases correctives, et les contraintes techniques réalistes.