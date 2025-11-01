# Migration du Système Sources vers data/

**Date**: 13 octobre 2025
**Status**: ✅ Complété

## Résumé

Migration du système de gestion des sources de données d'une architecture complexe à 3 dossiers (`uploads/` → `imports/` → `snapshots/`) vers un système unifié et simplifié avec un seul dossier `data/` par module.

## Problème Initial

### Architecture Complexe
```
data/users/{user_id}/
  ├── cointracking/
  │   ├── uploads/      # Zone de dépôt
  │   ├── imports/      # Fichiers validés
  │   └── snapshots/    # Version active
  └── saxobank/
      ├── uploads/
      ├── imports/
      └── snapshots/
```

**Problèmes identifiés:**
- Confusion utilisateur: bouton "Importer" non intuitif
- Étape manuelle requise pour passer de `uploads/` à `imports/`
- Complexité inutile pour un système mono-utilisateur
- Menus déroulants montrant les mauvais dossiers

## Solution Implémentée

### Architecture Simplifiée
```
data/users/{user_id}/
  ├── cointracking/
  │   └── data/        # Un seul dossier unifié
  └── saxobank/
      └── data/        # Un seul dossier unifié
```

### Versioning Automatique

Les fichiers sont automatiquement versionnés avec un timestamp au moment de l'upload:

```
20251013_185242_High_Risk_Contra.csv
20251013_185410_Positions_23-sept.-2025_14_25_22.csv
20251013_185420_Positions_13-oct.-2025_18_09_08.csv
```

**Avantages:**
- Historique complet automatique
- Pas de perte de données
- Sélection du plus récent par défaut
- Possibilité de revenir aux versions précédentes

## Modifications Backend

### 1. sources_endpoints.py
**Endpoint Upload**:
- Sauvegarde directe dans `{module}/data/`
- Génération automatique du timestamp: `YYYYMMDD_HHMMSS_{filename}`
- Suppression de la logique d'import séparée

### 2. sources_resolver.py
**Logique de résolution simplifiée**:
```python
def resolve_effective_path(user_fs, module):
    # 1. Fichier sélectionné par l'utilisateur
    if csv_selected_file:
        return "user_choice", path

    # 2. Fichiers dans data/ (le plus récent)
    data_files = user_fs.glob_files(f"{module}/data/*.csv")
    if data_files:
        data_files.sort(key=os.path.getmtime, reverse=True)
        return "data", data_files[0]

    # 3. Vide
    return "empty", None
```

**Suppression:**
- Fonction `_resolve_legacy_patterns()` complètement retirée
- Patterns `uploads/`, `imports/`, `snapshots/` supprimés

### 3. user_settings_endpoints.py
**Endpoint `/api/users/sources`**:
- Scanner uniquement `{module}/data/*.csv`
- Suppression du scan de `imports/`
- Construction dynamique de la liste des sources

### 4. config_migrator.py
**Configuration des modules**:
```python
{
    "enabled": True,
    "modes": ["data"],  # Plus de "uploads"
    "patterns": [
        "cointracking/data/*.csv"
    ],
    ...
}
```

**Validation:**
- Modes valides: `["data", "api"]` uniquement
- Conversion automatique `uploads` → `data` pour compatibilité

### 5. adapters/saxo_adapter.py
**Chargement des portfolios Saxo**:
```python
def _load_from_sources_fallback(user_id):
    # Essayer data/ (nouveau système unifié)
    data_files = user_fs.glob_files("saxobank/data/*.csv")
    if data_files:
        latest_data = max(data_files, key=os.path.getmtime)
        return _parse_saxo_csv(latest_data, "saxo_data")

    return None
```

## Modifications Frontend

### 1. sources-manager.js
**Actions simplifiées**:
- ✅ Scanner (liste les sources disponibles)
- ✅ Uploader (upload direct vers `data/`)
- ✅ Refresh API (pour CoinTracking API)
- ❌ Importer (supprimé - plus nécessaire)

**Commentaire ajouté**:
```javascript
// Nouveau système: Upload sauvegarde directement dans data/,
// plus besoin d'import séparé!
```

### 2. settings.html
**Dropdown dynamique**:
```javascript
async function buildQuickSourceDropdown() {
    const response = await fetch('/api/sources/list');
    const data = await response.json();

    for (const module of data.modules) {
        // API sources
        if (module.modes.includes('api')) {
            sources.push({
                key: `${module.name}_api`,
                label: `${module.name} API`,
                type: 'api'
            });
        }

        // CSV files from data/
        for (const file of module.detected_files) {
            sources.push({
                key: `csv_${module.name}_${index}`,
                label: `${module.name}: ${file.name}`,
                type: 'csv',
                file_name: file.name
            });
        }
    }
}
```

## Migration des Données

### Processus de Migration

1. **Copie des fichiers utiles** vers `data/`:
   ```python
   # Copier avec timestamp
   timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
   dest = data_dir / f'{timestamp}_{filename}'
   shutil.copy2(source, dest)
   ```

2. **Suppression des anciens dossiers**:
   ```python
   old_dirs = [
       'cointracking/uploads',
       'cointracking/imports',
       'cointracking/snapshots',
       'saxobank/uploads',
       'saxobank/imports',
       'saxobank/snapshots'
   ]
   ```

3. **Vérification**:
   - ✅ 7 sources détectées (4 CoinTracking + 2 Saxo + 1 API)
   - ✅ Balance endpoint: 183 items
   - ✅ Saxo dashboard: 28 positions
   - ✅ Structure finale propre

## Tests de Validation

### 1. Sources Endpoint
```bash
curl "http://localhost:8080/api/users/sources" -H "X-User: jack"
# ✅ 7 sources (CSV + API)
```

### 2. Balance Endpoint
```bash
curl "http://localhost:8080/balances/current?source=cointracking&user_id=jack"
# ✅ 183 items
```

### 3. Saxo Dashboard
```bash
curl "http://localhost:8080/api/saxo/portfolios" -H "X-User: jack"
# ✅ 1 portfolio, 28 positions
```

### 4. Structure Filesystem
```bash
ls -R data/users/jack/
# ✅ Uniquement data/ présent, plus de uploads/imports/snapshots
```

## Impact Utilisateur

### Avant
1. Uploader un fichier → va dans `uploads/`
2. Cliquer sur "Importer" → fichier copié vers `imports/`
3. Dropdown montre les fichiers de `imports/`
4. **Confusion**: Pourquoi deux étapes?

### Après
1. Uploader un fichier → va directement dans `data/`
2. Fichier immédiatement disponible dans les dropdowns
3. **Simple et intuitif**

## Configuration Sources

### Format sources.json
```json
{
  "version": 1,
  "modules": {
    "cointracking": {
      "enabled": true,
      "modes": ["data", "api"],
      "patterns": ["cointracking/data/*.csv"],
      "snapshot_ttl_hours": 24,
      "api": {
        "key_ref": "cointracking_api_key",
        "secret_ref": "cointracking_api_secret"
      },
      "preferred_mode": "api"
    },
    "saxobank": {
      "enabled": true,
      "modes": ["data"],
      "patterns": ["saxobank/data/*.csv"],
      "snapshot_ttl_hours": 24
    }
  }
}
```

## Rétrocompatibilité

**Aucune rétrocompatibilité maintenue** - Clean break:
- Anciens patterns complètement supprimés
- Migration one-time des fichiers existants
- Structure legacy non supportée

**Justification:**
- Simplification maximale
- Pas de technical debt
- Projet en développement (pas de prod)
- Un seul utilisateur actif

## Documentation Mise à Jour

- ✅ `CLAUDE.md` - Guide agent mis à jour
- ✅ `docs/SOURCES_MIGRATION_DATA_FOLDER.md` - Ce document
- ✅ Code comments dans les fichiers modifiés

## Fichiers Modifiés

### Backend
- `api/sources_endpoints.py` - Upload vers data/
- `api/services/sources_resolver.py` - Résolution simplifiée
- `api/services/config_migrator.py` - Patterns et validation
- `api/user_settings_endpoints.py` - List sources depuis data/
- `adapters/saxo_adapter.py` - Chargement portfolios depuis data/

### Frontend
- `static/sources-manager.js` - Suppression bouton Import
- `static/settings.html` - Dropdown dynamique

### Configuration
- `data/users/jack/config/sources.json` - Patterns mis à jour

## Prochaines Étapes

1. ✅ **Immédiat**: Restart serveur FastAPI pour appliquer les changements
2. ⏳ **Court terme**: Monitoring des uploads utilisateur
3. ⏳ **Moyen terme**: Ajouter limite de rétention (ex: garder 10 derniers fichiers)
4. ⏳ **Long terme**: Interface pour supprimer les anciens fichiers

## Leçons Apprises

1. **KISS Principle**: La simplicité est toujours préférable
2. **Versioning**: Timestamps automatiques > nomenclature complexe
3. **User Testing**: Boutons non intuitifs = signaux d'alerte
4. **Migration**: Clean break > compatibilité complexe pour projets en dev

## Résultat Final

- 🎯 **Objectif atteint**: Système sources unifié et intuitif
- 📉 **Complexité réduite**: 3 dossiers → 1 dossier
- ⚡ **Performance**: Pas de changement (même nombre de fichiers lus)
- 🚀 **UX**: Upload → Disponible immédiatement (0 étapes intermédiaires)
- 🧹 **Code**: ~150 lignes supprimées (legacy patterns)

---

**Auteur**: Claude Code
**Review**: Validé par tests fonctionnels
**Status**: Production-ready ✅

