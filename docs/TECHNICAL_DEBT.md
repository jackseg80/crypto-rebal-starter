# Dette Technique - Suivi et Roadmap

> **Dernière mise à jour** : 10 octobre 2025
> **Statut global** : 🟢 Sous contrôle (12 items actifs, 2 HIGH priority résolus)

Ce document centralise les TODO, FIXME et items de dette technique identifiés dans le codebase, avec priorités et plan de résolution.

## 📊 Vue d'Ensemble

| Catégorie | Items | Priorité | Action |
|-----------|-------|----------|--------|
| **Features futures** | 6 | 🟢 LOW | Backlog product |
| **À implémenter** | 4 | 🟡 MEDIUM | Plan d'implémentation |
| **Documentation** | 1 | 🔵 INFO | Référence existante |
| **HIGH priority résolus** | 2 | ✅ DONE | Complétés Oct 2025 |
| **Migration terminée** | 4 | ✅ DONE | Complétée Oct 2025 |
| **Archives nettoyées** | 7 | ✅ DONE | Supprimées Oct 2025 |

**Total actif** : 11 items (excluant migrations/HIGH/archives complétées)

---

## ✅ DONE - Migration Risk Dashboard (4 items - Oct 2025)

**Contexte** : Refactoring Risk Dashboard vers architecture modulaire (Oct 2025)

### Migration complétée

#### `static/modules/risk-cycles-tab.js` ✅
- 1397 lignes de code complet
- Chart Bitcoin avec halvings, prix historique, cycle score
- Indicateurs on-chain avec catégories v2
- Calibration historique automatique
- Cache intelligent et lazy-loading

#### `static/modules/risk-targets-tab.js` ✅
- 442 lignes de code complet
- 5 stratégies (macro, CCS, cycle, blend, smart)
- Action plan avec validation
- Decision history tracking
- Intégration targets-coordinator.js

#### Stubs supprimés
- `cycles-tab.js` (30 lignes) → Remplacé par `risk-cycles-tab.js`
- `targets-tab.js` (30 lignes) → Remplacé par `risk-targets-tab.js`

**Date complétion** : 10 octobre 2025
**Résultat** : Architecture modulaire opérationnelle, -60 lignes de stubs, +1839 lignes de code production

---

## 🟢 LOW - Features Non Implémentées (6 items)

Ces items sont des fonctionnalités futures, pas des bugs. Backlog product.

### Admin Dashboard

#### `static/ai-dashboard.html` (2 TODO)
```javascript
// TODO: Implémenter le chargement de symboles spécifiques
// TODO: Endpoint spécifique pour détails régime
```

**Statut** : Feature request
**Justification** : Admin dashboard peu utilisé, priorité basse
**Action recommandée** : Garder dans backlog, implémenter si besoin utilisateur

### Backtesting

#### `static/backtesting.html` (1 TODO)
```javascript
// TODO: Implement strategy comparison
```

**Statut** : Feature request
**Justification** : Backtesting avancé = Phase 4
**Action recommandée** : Spécifier requirements avant implémentation

### Métriques Réelles

#### `static/components/InteractiveDashboard.js` (4 TODO)
```javascript
// TODO: Implémenter calcul basé sur historique prix réel
// TODO: Implémenter calcul de métriques de risque basées sur données réelles
// TODO: Implémenter calculs basés sur données historiques réelles
// TODO: Calculer métriques réelles basées sur historique
```

**Statut** : Enhancement
**Justification** : InteractiveDashboard est déprécié, remplacé par dashboards modernes
**Action recommandée** : **Supprimer** InteractiveDashboard.js si non utilisé

---

## ✅ DONE - HIGH Priority Resolved (2 items - Oct 2025)

### 1. Wallet Stats ✅

#### `static/core/unified-insights-v2.js:580-588`
**Statut** : Implémenté
**Date complétion** : 10 octobre 2025

```javascript
// Implémentation finale
const currentAllocations = window.store?.get('allocations.current') || {};
const sortedByWeight = Object.entries(currentAllocations).sort((a, b) => b[1] - a[1]);

const walletStats = {
  topWeightSymbol: sortedByWeight[0]?.[0] || null,
  topWeightPct: sortedByWeight[0]?.[1] || null,
  volatility: null // Deferred to risk metrics (requires historical data)
};
```

**Résultat** : Allocations dynamiques maintenant basées sur les stats wallet réelles

### 2. Governance Endpoint ✅

#### `static/modules/risk-targets-tab.js:423`
**Statut** : Implémenté
**Date complétion** : 10 octobre 2025

**Problème résolu** : Targets appliqués directement sans workflow governance

**Implémentation** :
- Appel `POST /execution/governance/propose` pour créer plan DRAFT
- Workflow complet : DRAFT → REVIEWED → APPROVED → ACTIVE
- Fallback gracieux si API indisponible (mode local)
- Feedback utilisateur avec plan_id et état

**Résultat** : Workflow governance respecté avec traçabilité complète des décisions

---

## 🟡 MEDIUM - À Implémenter (4 items)

### 1. Governance Overrides (1 TODO) - Priority MEDIUM

#### `static/components/UnifiedInsights.js:571`
```javascript
// TODO: Get from governance state
const overrides = 0;
```

**Impact** : Visibilité sur ajustements manuels
**Effort** : 30 min
**Action recommandée** : Lire `window.store.get('governance.overrides_count')`

### 3. Modules Additionnels (1 TODO) - Priority LOW

#### `static/rebalance.html:3087`
```javascript
// TODO: Charger données pour autres modules (bourse, banque, divers)
```

**Impact** : Unification Wealth (Phase 3)
**Effort** : 4-6h
**Action recommandée** : Voir [TODO_WEALTH_MERGE.md](TODO_WEALTH_MERGE.md) pour roadmap complète

### 4. Save Settings via API (2 TODO) - Priority MEDIUM

#### `static/settings.html:1104` + `static/sources-unified-section.html:250`
```javascript
// TODO: Implémenter la sauvegarde via API
showNotification('Configuration sources sauvegardée', 'success');
```

**Problème actuel** : Settings sauvegardés en localStorage uniquement (client-side)
**Impact** : Perte config lors changement navigateur/device
**Effort** : 2h
**Action recommandée** :
1. Créer endpoint `PUT /api/users/{user_id}/settings/sources`
2. Sauvegarder dans `data/users/{user_id}/config.json`
3. Charger au démarrage page

---

## 🔵 INFO - Documentation (1 item)

### `static/FIXME_getApiUrl.md`

**Statut** : ✅ Documenté
**Description** : Document explicatif sur risque de duplication `/api/api`
**Action** : Aucune (référence existante)

---

## ✅ DONE - Archives Nettoyées (7 items)

**Date nettoyage** : 10 octobre 2025

Fichiers supprimés :
- `static/risk-dashboard.html.backup.20251009_222532` (332 KB)
- `static/archive/unified-insights-versions/unified-insights-v2-backup.js` (3 TODO)
- `static/archive/unified-insights-versions/unified-insights-v2-clean.js` (2 TODO)
- `fix-css-selectors.cjs`
- `test_jack_api_classification.py`
- `test_output.txt`
- `startup_logs.txt`

**Impact** : -350 KB, -7 TODO dans le codebase

---

## 🎯 Plan d'Action Recommandé

### Court Terme (< 1 semaine)

1. **Settings API Save** (settings.html) - 2h
   → Persistance multi-device

**Total** : 2h d'effort

### Moyen Terme (1-2 semaines)

4. **Governance Overrides** (UnifiedInsights.js) - 30 min

**Total** : 30 min d'effort

### Long Terme (> 1 mois)

7. **Wealth Merge Phase 3** (rebalance.html) - 6h
8. **Backtesting Comparison** (backtesting.html) - 8h
9. **Supprimer InteractiveDashboard.js** - 30 min (si non utilisé)

---

## 📏 Métriques

### Réduction Dette (Oct 2025)

| Métrique | Avant | Après | Delta |
|----------|-------|-------|-------|
| TODO/FIXME total | 26 | 12 | -14 ✅ |
| Fichiers backup | 7 | 0 | -7 ✅ |
| Taille backups | 400 KB | 0 KB | -100% ✅ |
| Items HIGH priority | 2 | ✅ 0 | -2 ✅ |
| Migration Risk Dashboard | 4 TODO | ✅ DONE | -4 ✅ |

### Tendance

```
Oct 2025 début: 26 items (baseline)
Oct 2025 nettoyage: 26 → 18 items (-31% cleanup)
Oct 2025 migration: 18 → 14 items (-22% completion)
Oct 2025 HIGH priority: 14 → 12 items (-14% fixes)
Target Nov 2025: 12 items → 6 items (implémenter MEDIUM items)
Target Dec 2025: 6 items → <5 items (dette sous contrôle)
```

---

## 🔍 Comment Utiliser ce Document

### Ajouter un TODO

1. Identifier dans le code :
   ```javascript
   // TODO: Description claire de ce qui manque
   // Context: Pourquoi c'est pas fait maintenant
   // Impact: Conséquence si non fait
   ```

2. Ajouter ici avec :
   - Catégorie (Migration/Feature/À implémenter)
   - Priorité (HIGH/MEDIUM/LOW)
   - Effort estimé
   - Action recommandée

### Résoudre un TODO

1. Implémenter la solution
2. Supprimer le commentaire TODO du code
3. Déplacer l'item vers section ✅ DONE
4. Mettre à jour les métriques

### Review

- **Fréquence** : Mensuelle (chaque début de mois)
- **Responsable** : Lead dev / tech lead
- **Critères de succès** : < 10 items actifs, aucun HIGH > 2 semaines

---

## 📚 Ressources

- [REFACTORING_SUMMARY.md](../REFACTORING_SUMMARY.md) - Plan refactoring global
- [TODO_WEALTH_MERGE.md](TODO_WEALTH_MERGE.md) - Roadmap Wealth
- [E2E_TESTS_STATUS.md](E2E_TESTS_STATUS.md) - Status tests automatisés
- [MIGRATION_RISK_DASHBOARD.md](../static/MIGRATION_RISK_DASHBOARD.md) - Migration Risk Dashboard

---

**Dernière review** : 10 octobre 2025
**Prochaine review** : 1er novembre 2025
**Statut global** : 🟢 Dette sous contrôle, roadmap claire
