# Check-list de vérification post-merge

## Tests automatisés ✅
- [✅] Tests unitaires risk dashboard metadata passent
- [✅] Tests de validation frontend passent
- [✅] Aucune régression détectée

## Validation E2E manuelle

### 1. Settings → Risk Dashboard (Phase 3A)
- [ ] Ouvrir `/static/settings.html`
- [ ] Sélectionner source `csv_0` avec user `demo`
- [ ] Naviguer vers Risk Dashboard
- [ ] Activer le mode debug : `localStorage.setItem('debug_metadata', 'true')`
- [ ] Recharger la page
- [ ] **Vérifier** : Bandeau debug affiche `User: demo | Source: csv_0`
- [ ] **Vérifier** : Phase 3A affiche les données du portefeuille demo/csv_0

### 2. Switch de source dans Settings
- [ ] Dans settings, changer vers `CoinTracking API`
- [ ] Retourner au Risk Dashboard
- [ ] **Vérifier** : Phase 3A se recharge automatiquement
- [ ] **Vérifier** : Bandeau debug montre nouvelle source
- [ ] **Vérifier** : Les pourcentages changent (différents de l'étape 1)

### 3. Switch d'utilisateur
- [ ] Dans settings, changer vers user `jack`
- [ ] **Vérifier** : Risk Dashboard se recharge
- [ ] **Vérifier** : Bandeau debug montre `User: jack`
- [ ] **Vérifier** : Les données sont différentes de demo

### 4. Analytics Unified → Allocation Suggérée
- [ ] Ouvrir `/static/analytics-unified.html`
- [ ] **Vérifier** : Aucun groupe "LARGE" affiché
- [ ] **Vérifier** : Groupes utilisent taxonomie standard (BTC, ETH, L1/L0 majors, etc.)
- [ ] Changer source dans settings
- [ ] **Vérifier** : Allocation se met à jour automatiquement
- [ ] **Vérifier** : Cache est invalidé (nouvelles données)

### 5. Cohérence cross-composant
- [ ] Comparer groupes Risk Dashboard vs Analytics Unified
- [ ] **Vérifier** : Mêmes noms de groupes utilisés
- [ ] **Vérifier** : Pourcentages cohérents entre les pages
- [ ] **Vérifier** : Aucune trace du groupe "LARGE"

## Backend API

### 6. Endpoint /api/risk/dashboard
- [ ] Test direct : `curl -H "X-User: demo" "/api/risk/dashboard"`
- [ ] **Vérifier** : Présence du bloc `meta` dans la réponse
- [ ] **Vérifier** : `meta.user_id` correspond au header
- [ ] **Vérifier** : `meta.taxonomy_hash` présent et 8 caractères
- [ ] Test avec user différent : `curl -H "X-User: jack" "/api/risk/dashboard"`
- [ ] **Vérifier** : Données différentes

### 7. Logs et traçabilité
- [ ] Démarrer le serveur et surveiller les logs
- [ ] Faire quelques requêtes Risk Dashboard
- [ ] **Vérifier** : Logs contiennent metadata (user, source, taxonomy)
- [ ] **Vérifier** : Format `🏷️ Risk dashboard metadata: user=X, source=Y`

## Performance et Caches

### 8. Cache UnifiedInsights
- [ ] Ouvrir DevTools → Console
- [ ] Recharger analytics-unified.html
- [ ] **Vérifier** : Message "Allocation cache invalidated" lors changement source
- [ ] **Vérifier** : Pas de requêtes API multiples simultanées

### 9. Stabilité
- [ ] Recharger pages plusieurs fois
- [ ] Changer source/user rapidement
- [ ] **Vérifier** : Pas d'erreurs console
- [ ] **Vérifier** : Comportement stable

## Rollback si problème
Si un test échoue :
1. `git log --oneline -5` pour voir les commits récents
2. `git revert <commit-hash>` du commit problématique
3. Réexécuter tests automatisés
4. Signaler le problème avec détails de l'échec

## Debug utile
```bash
# Activer debug metadata
localStorage.setItem('debug_metadata', 'true')

# Voir cache allocation
console.log(window.debugGetCurrentAllocation())

# Invalidation manuelle cache
window.debugInvalidateCache()

# Vérifier événements
window.addEventListener('dataSourceChanged', e => console.log('Source changed:', e.detail))
```

---
**Status** : ⏳ En attente de validation manuelle
**Critique** : Les points 1-4 sont critiques - ils valident directement le fix du problème initial.