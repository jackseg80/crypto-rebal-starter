# Issue: File Watcher Preventing Edits

## Problème Observé

Lors du cleanup architecture (2025-09-30), impossible d'éditer certains fichiers :

- `static/global-config.js`
- `CLAUDE.md`
- Autres fichiers de configuration

**Symptôme** : Erreur `File has been unexpectedly modified` lors de tentatives d'édition avec l'outil Edit.

## Cause Probable

Un **file watcher** actif modifie continuellement ces fichiers, probablement :

1. **Hot reload / Dev server** (si `uvicorn --reload` actif)
   - Surveille les changements de fichiers Python
   - Peut déclencher des rebuilds JS/CSS

2. **Linter/Formatter automatique** (ESLint, Prettier, Black)
   - Reformate automatiquement à la sauvegarde
   - Modifie les fichiers pendant l'édition

3. **VSCode extensions**
   - Extensions de formatting auto-save
   - Extensions de synchronisation

## Impact

- **Bloque modifications programmatiques** via agents/scripts
- **Empêche fixes automatisés** (ex: FIXME getApiUrl)
- **Force workarounds manuels**

## Workarounds Appliqués

### 1. Documents FIXME séparés

Au lieu de modifier directement `global-config.js`, créé :
- `static/FIXME_getApiUrl.md` : Documentation du problème et solution proposée

### 2. Documents architecture externes

Au lieu de modifier `CLAUDE.md`, créé :
- `docs/architecture-risk-routers.md` : Diagramme et explication séparation risk routers

### 3. Éditions via sed/bash

Pour modifications simples (ex: suppression de ligne), utiliser :
```bash
sed -i '157,162d' static/global-config.js  # Supprimer lignes 157-162
```

## Solutions Permanentes

### Option A: Désactiver watchers temporairement

```bash
# 1. Identifier processus watcher
ps aux | grep -E "watch|nodemon|uvicorn.*--reload"

# 2. Arrêter temporairement
pkill -f "uvicorn.*--reload"

# 3. Faire les modifications

# 4. Redémarrer
uvicorn api.main:app --reload
```

### Option B: Exclure fichiers des watchers

**VSCode** (`settings.json`) :
```json
{
  "files.watcherExclude": {
    "**/static/global-config.js": true,
    "**/CLAUDE.md": true
  }
}
```

**Prettier** (`.prettierignore`) :
```
static/global-config.js
CLAUDE.md
```

**ESLint** (`.eslintignore`) :
```
static/global-config.js
```

### Option C: Éditions par patch files

```bash
# 1. Créer patch
cat > fix.patch << 'EOF'
--- a/static/global-config.js
+++ b/static/global-config.js
@@ -242,6 +242,15 @@
   getApiUrl(endpoint, additionalParams = {}) {
     const base = this.settings.api_base_url;
+    // Normalize endpoint to avoid /api/api duplication
+    let normalized = endpoint;
+    if (base.endsWith('/api') && /^\/+api(\/|$)/i.test(endpoint)) {
+      normalized = endpoint.replace(/^\/+api/, '');
+      if (!normalized.startsWith('/')) normalized = '/' + normalized;
+    }
     const url = new URL(normalized, base.endsWith('/') ? base : base + '/');
EOF

# 2. Appliquer
git apply fix.patch
```

## Recommandation

**Court terme** : Continuer avec documents FIXME séparés (déjà fait)

**Moyen terme** :
1. Identifier quel watcher est actif (`ps aux | grep watch`)
2. Configurer `.prettierignore` / `.eslintignore`
3. Appliquer les FIXME manuellement quand watcher est off

**Long terme** :
- Désactiver auto-format sur ces fichiers critiques
- Utiliser pre-commit hooks au lieu de watchers continus

## Fichiers Affectés

- ✅ `static/global-config.js` : FIXME documenté dans `static/FIXME_getApiUrl.md`
- ✅ `CLAUDE.md` : Architecture documentée dans `docs/architecture-risk-routers.md`
- ⚠️ Autres fichiers à risque : `package.json`, `.eslintrc`, `tsconfig.json`

## Validation

**Test si watcher actif** :
```bash
# Créer fichier test
echo "test" > test_watcher.tmp

# Surveiller modifications
watch -n 1 'stat -c %Y test_watcher.tmp'

# Si timestamp change sans action manuelle → watcher actif
```

---

**Statut** : DOCUMENTÉ (workarounds appliqués, solution permanente à planifier)
**Date** : 2025-09-30
**Auteur** : Audit architecture cleanup