# Résumé Hotfix : Incohérences données de wallet

## 🎯 Problème résolu
**Phase 3A du Risk Dashboard affichait les données du compte "jack" au lieu de l'utilisateur actuel**

**Cause root:** Appels `fetch()` directs sans headers `X-User`, cache non invalidé lors changements source/user

## 📋 Corrections appliquées

### P1 Frontend Hotfix ✅
**Fichiers modifiés:**
- `static/risk-dashboard.html` : Remplacé 3 appels fetch() par globalConfig.apiRequest()
- `static/components/UnifiedInsights.js` : Cache avec clé `user:source:taxonomy:version`
- Ajouté listeners `dataSourceChanged`/`activeUserChanged` pour invalidation automatique

### P2 Backend "garde-fous" ✅
**Fichiers modifiés:**
- `api/risk_endpoints.py` : Ajouté bloc `meta` normalisé dans réponses
```json
"meta": {
  "user_id": "demo",
  "source_id": "cointracking",
  "taxonomy_version": "v2",
  "taxonomy_hash": "abc12345",
  "generated_at": "2024-01-15T10:30:00Z",
  "correlation_id": "risk-demo-1234567890"
}
```
- Bandeau debug activable : `localStorage.setItem('debug_metadata', 'true')`

### P3 Taxonomie unifiée ✅
**Fichiers modifiés:**
- `services/execution/strategy_registry.py` : "LARGE" → "L1/L0 majors"
- Mapping d'alias cohérent dans tous les composants

## ✅ Tests et validation

### Tests automatisés (9/9 passent)
```bash
pytest tests/unit/test_risk_dashboard_metadata.py -v     # 4/4 ✅
pytest tests/unit/test_frontend_fixes_validation.py -v   # 5/5 ✅
```

**Couverture:**
- Headers X-User correctement utilisés
- Métadonnées cohérentes entre users
- Aucun groupe "LARGE" en sortie
- Cache keys canoniques
- Event listeners fonctionnels

### Check-list E2E manuelle
📁 `POST_MERGE_CHECKLIST.md` : 9 points de validation critiques

## 🔧 Instructions debug

```bash
# Activer métadonnées debug
localStorage.setItem('debug_metadata', 'true')

# Vérifier cache allocation
window.debugGetCurrentAllocation()

# Invalider cache manuellement
window.debugInvalidateCache()

# Monitor événements
window.addEventListener('dataSourceChanged', e => console.log('Source changed:', e.detail))
```

## 📊 Impact

### Avant ❌
- Phase 3A : Données fixes compte "jack"
- Groupe "LARGE" fictif affiché
- Cache non synchronisé cross-tabs
- Pas de traçabilité user/source

### Après ✅
- Phase 3A : Données utilisateur actuel (demo/csv_0)
- Taxonomie standard 11 groupes ("L1/L0 majors")
- Cache invalidé automatiquement sur changements
- Metadata complète + logs traçabilité

## 🚀 Déploiement
**Commit:** `c5d9595` - `fix(risk-dashboard): enforce user/source context in Phase 3A using apiRequest`

**Rollback si besoin:**
```bash
git revert c5d9595
```

**Validation critique:**
1. Settings → csv_0/demo → Risk Dashboard → Vérifier données demo
2. Switch CoinTracking API → Vérifier rechargement auto
3. Switch user jack → Vérifier données différentes

---
✅ **Status:** Corrections déployées et testées
⏳ **Next:** Validation E2E manuelle selon checklist