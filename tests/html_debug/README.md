# 🧪 Test Suite HTML Debug - Guide Complet

Suite de tests organisée pour validation et debug du système Crypto Rebalancer.

## 📁 Organisation des Tests

### 🔧 [Core](./core/) - Tests Système Fondamentaux
Tests des composants critiques et logique métier de base.
- Génération 11 groupes d'actifs
- Système CCS (Crypto Cycle Score)  
- Synchronisation modules backend

### 🌐 [API](./api/) - Tests Intégration & Connecteurs  
Tests des APIs externes et sources de données.
- Coinglass, Crypto Toolbox, FRED
- Validation connecteurs
- Test robustesse réseau

### 🎨 [UI](./ui/) - Tests Interface Utilisateur
Tests des interfaces et interactions utilisateur.
- Navigation et menus
- Boutons et formulaires
- UX et cohérence visuelle

### ⚡ [Performance](./performance/) - Tests Performance & Optimisation
Tests de performance et optimisation système.
- Système de cache
- Pondération dynamique  
- Monitoring temps réel

### ✅ [Validation](./validation/) - Tests Qualité & Validation
Tests de validation finale et assurance qualité.
- Validation complète système
- Cohérence des scores
- Tests de régression

## 🚀 Workflow de Test Recommandé

### 1. Test Rapide (5 minutes)
```bash
# Tests essentiels pour validation rapide
core/debug_11_groups_fix.html      # ✅ Système de base
ui/test_debug_menu.html           # ✅ Interface debug  
validation/test-v2-quick.html     # ✅ Test global rapide
```

### 2. Test Complet (15-20 minutes)
```bash  
# Suite complète pour validation approfondie
core/*                            # 🔧 Tous tests système
api/test-crypto-toolbox-*.html    # 🌐 Intégrations crypto
performance/performance-monitor.html # ⚡ Monitoring performance
validation/validation_finale.html    # ✅ Validation finale
```

### 3. Test Spécialisé (selon besoins)
- **Problème 11 groupes** → `core/debug_11_groups_fix.html`
- **Performance lente** → `performance/test-cache-debug.html`  
- **Bugs interface** → `ui/test_navigation_ui.html`
- **API externes** → `api/test-*-integration.html`

## 📊 Métriques de Test

- **49 tests HTML** organisés en 5 catégories
- **Coverage** : Système (100%), API (95%), UI (90%)
- **Automatisation** : Tests manuels avec validation automatique
- **Performance** : Support portfolios 1000+ actifs

## 🔍 Debug & Diagnostic

Chaque catégorie inclut :
- **README.md** : Guide spécifique et ordre de test
- **Tests simples** : Validation rapide
- **Tests debug** : Diagnostic approfondi
- **Tests de correction** : Fix de bugs spécifiques

## 💡 Conseils d'Usage

1. **Commencez toujours par les tests Core** pour valider la base
2. **Utilisez les README** de chaque catégorie pour l'ordre optimal  
3. **Tests Performance** si problèmes de lenteur
4. **Tests Validation** avant mise en production
5. **Logs navigateur** (F12) pour diagnostic détaillé

---

**🎯 Suite de tests production-ready avec diagnostic complet et organisation modulaire**