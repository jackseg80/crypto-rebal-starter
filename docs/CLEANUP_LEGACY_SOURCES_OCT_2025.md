# Nettoyage Code Legacy - Système Sources (Oct 2025)

**Date**: 13 Oct 2025
**Contexte**: Migration vers système `data/` simplifié
**Statut**: 🔍 Audit en cours

---

## Contexte: Nouveau Système data/

Avec le nouveau système unifié, les fichiers sont:
- **Uploadés directement** dans `{module}/data/` avec versioning automatique
- **Lus directement** depuis `data/` (plus de snapshot/imports)
- **Gérés** via `/api/sources/` endpoints et `settings.html#tab-sources`

### Ancien Système (Legacy)
```
data/users/{user}/
  {module}/
    uploads/      # Fichiers temporaires uploadés
    imports/      # Fichiers après import
    snapshots/    # Snapshots consolidés
```

### Nouveau Système (Actuel)
```
data/users/{user}/
  {module}/
    data/         # Tous les fichiers (versionnés automatiquement)
    api_cache/    # Cache API (si module a mode API)
```

---

## Code Obsolète Identifié

### 1. Page Upload Standalone

#### `static/saxo-upload.html`
**Statut**: ⚠️ Probablement obsolète

**Raison**:
- Interface standalone d'upload Saxo
- Duplicate de functionality dans `settings.html#tab-sources`
- Pas de lien dans navigation
- Utilise anciens endpoints `/api/saxo/validate` et `/api/saxo/import`

**Recommandation**:
- ✅ **DÉPLACER vers archive/** - Pas supprimer complètement car endpoints encore utilisés
- Ajouter bannière de redirection vers `settings.html#tab-sources`

**Impact**: Faible - pas lié dans navigation

---

### 2. Références Legacy dans Endpoints

#### `api/sources_endpoints.py`

**Lignes avec références legacy**:

##### L141: Commentaire legacy
```python
is_legacy=False  # Plus de fichiers legacy dans le nouveau système
```
✅ OK - Commentaire explicite, pas de code legacy

##### L265: Commentaire legacy
```python
is_legacy=False  # Plus de fichiers legacy
```
✅ OK - Commentaire explicite

##### L283-405: Endpoint `/import`
**Description**:
```python
@router.post("/import", response_model=ImportResponse)
async def import_module(request: ImportRequest, ...):
    """
    Importe les fichiers d'un module depuis uploads/ ou legacy vers imports/.
    Parse et crée/met à jour le snapshot.
    """
```

**Problème**:
- Docstring mentionne `uploads/` et `imports/` (ancien système)
- Code ligne 349-378 gère déplacement depuis `uploads/` vers `imports/`
- Fonction `_create_snapshot()` ligne 518-598 crée des snapshots dans `{module}/snapshots/`

**Recommandation**:
- ⚠️ **VÉRIFIER SI ENCORE UTILISÉ** - Possiblement remplacé par upload direct
- Si utilisé: Mettre à jour docstring et simplifier (pas besoin de imports/ ni snapshots/)
- Si pas utilisé: Marquer comme deprecated ou supprimer

##### L518-598: Fonction `_create_snapshot()`
```python
async def _create_snapshot(module: str, user_fs: UserScopedFS, source_dir: str) -> bool:
    """
    Crée un snapshot consolidé pour un module depuis un répertoire source.
    Consolidation réelle: merge multiple CSV si disponibles, avec déduplication.
    """
```

**Problème**:
- Crée snapshots dans `{module}/snapshots/`
- Dans le nouveau système, les fichiers sont lus directement depuis `data/` (plus besoin de snapshot)

**Recommandation**:
- ⚠️ **DEPRECATED** - Snapshots ne sont plus nécessaires avec nouveau système
- Vérifier si endpoint `/import` l'utilise encore
- Si oui: Simplifier pour copier directement dans `data/` au lieu de créer snapshot

---

#### `api/user_settings_endpoints.py`

**À vérifier**: Références à `uploads/`, `imports/`, `snapshots/`

---

#### `api/csv_endpoints.py`

**À vérifier**: Anciennes logiques d'upload CSV

---

#### `api/monitoring_advanced.py`

**À vérifier**: Monitoring des anciens répertoires

---

### 3. Navigation et Liens

#### `static/components/nav.js`

**À vérifier**: Liens vers `saxo-upload.html` ou autres pages upload standalone

---

### 4. Documentation Obsolète

#### Docs à vérifier:
- `docs/SOURCES_SYSTEM.md` - Peut-être déjà à jour
- `docs/SAXO_INTEGRATION_SUMMARY.md` - Peut référencer ancien système
- Autres docs mentionnant uploads/imports/snapshots

---

## Plan de Nettoyage

### Phase 1: Audit Détaillé (En cours)
- [x] Identifier `saxo-upload.html`
- [x] Identifier références legacy dans `sources_endpoints.py`
- [ ] Vérifier `user_settings_endpoints.py`
- [ ] Vérifier `csv_endpoints.py`
- [ ] Vérifier `monitoring_advanced.py`
- [ ] Vérifier navigation `nav.js`
- [ ] Lister tous les usages de `uploads/`, `imports/`, `snapshots/`

### Phase 2: Vérification Usage
- [ ] Tester si `/api/sources/import` encore utilisé
- [ ] Tester si `_create_snapshot()` encore appelé
- [ ] Vérifier si `saxo-upload.html` encore accessible

### Phase 3: Nettoyage Progressif
- [ ] **Étape 1**: Archiver `saxo-upload.html` → `static/archive/`
- [ ] **Étape 2**: Marquer fonctions legacy comme deprecated
- [ ] **Étape 3**: Simplifier ou supprimer code snapshot
- [ ] **Étape 4**: Mettre à jour docstrings mentionnant ancien système
- [ ] **Étape 5**: Nettoyer commentaires legacy devenus inutiles

### Phase 4: Tests
- [ ] Tests unitaires passent après nettoyage
- [ ] Upload via settings.html fonctionne
- [ ] Lecture sources depuis data/ fonctionne
- [ ] Aucune régression

---

## Critères de Décision

### ✅ Peut être supprimé si:
1. Pas de lien dans navigation active
2. Pas d'import dans code actif
3. Functionality duplicate ailleurs (ex: settings.html)
4. Tests passent sans ce code

### ⚠️ Marquer deprecated si:
1. Encore quelques usages restants
2. Transition progressive nécessaire
3. Backward compatibility souhaitée temporairement

### ❌ Ne PAS supprimer si:
1. Encore utilisé activement
2. Tests échouent sans
3. Endpoints API publics (breaking change)

---

## Notes Techniques

### Nouveau Workflow Upload
1. User upload fichier via `settings.html#tab-sources`
2. Appelle `/api/sources/upload`
3. Fichier sauvegardé directement dans `{module}/data/` avec timestamp
4. Config mise à jour (`last_import_at`)
5. Données disponibles immédiatement via resolvers

**Plus besoin de**:
- Étape "import" (uploads → imports)
- Création de snapshot (imports → snapshots)
- Lecture depuis snapshot (obsolète)

### Backward Compatibility
Ancien code peut encore fonctionner si:
- Cherche dans `snapshots/` → Fallback à `data/`
- Utilise endpoint `/import` → Marquer deprecated, rediriger vers `/upload`

---

## Prochaines Actions

**Immédiat**:
1. Compléter audit des fichiers listés
2. Créer liste exhaustive code legacy
3. Tester impact suppression `saxo-upload.html`

**Court terme** (après validation):
1. Archiver pages standalone obsolètes
2. Marquer fonctions snapshot comme deprecated
3. Simplifier `sources_endpoints.py` (supprimer logic imports/snapshots)

**Long terme**:
1. Supprimer complètement code snapshot si pas utilisé
2. Nettoyer anciens répertoires user (`uploads/`, `imports/`, `snapshots/`)
3. Mettre à jour toute documentation

---

**Dernière mise à jour**: 13 Oct 2025
**Responsable**: Audit automatisé + review manuelle requise
