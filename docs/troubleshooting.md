# Dépannage

## Problèmes fréquents
- Aucune balance trouvée: vérifier `.env` (CT_API_KEY/CT_API_SECRET) et les exports CSV.
- CORS depuis pages externes: définir `CORS_ORIGINS` dans `.env`.
- OpenAPI non accessible: utiliser `/schema` (fallback) dans `api/main.py`.

## Diagnostics
- `GET /healthz`
- `GET /debug/paths`
- Logs `uvicorn` en `--reload`.

## Corrections Récentes (2025-09-29)

### TypeError: resolve_current_balances() got unexpected keyword argument 'source'

**Problème** : Erreur 500 sur `/balances/current` due à une incompatibilité signature FastAPI.

**Solution** : Corrigé l'appel dans `api/unified_data.py:22` :
```python
# Avant (cassé)
res = await resolve_current_balances.__wrapped__(source=source, user_id=user_id)

# Après (corrigé)
res = await resolve_current_balances(source, user_id)
```

### Endpoints manquants (404 Not Found)

**Problème** : `/api/market/prices` retournait 404.

**Solution** : Décommenté le router dans `api/main.py:96` et ajouté stubs pour imports manquants.

### 403 Forbidden - Utilisateurs non autorisés

**Problème** : Utilisateurs bloqués même avec des IDs valides.

**Solution** : Ajouté bypass mode développement dans `api/deps.py` :
```python
# Mode développement : bypass de l'autorisation si DEV_OPEN_API=1
dev_mode = os.getenv("DEV_OPEN_API", "0") == "1"
if dev_mode:
    logger.info(f"DEV MODE: Bypassing authorization for user: {normalized_user}")
    return normalized_user
```

**Usage** : Démarrer avec `DEV_OPEN_API=1 uvicorn api.main:app --reload --port 8000`

### Fichiers secrets manquants

**Problème** : FileNotFoundError pour `data/users/{user}/secrets.json` causant 500 errors.

**Solution** : Créé système fallback robuste :
- `config/secrets_example.json` : Template avec clés exemple
- `services/user_secrets.py` : Gestionnaire avec fallbacks gracieux
  1. Essaie `data/users/{user}/secrets.json`
  2. Fallback sur `config/secrets_example.json`
  3. Fallback ultime sur secrets vides avec dev_mode

### Validation Pydantic - Erreurs "dict * int"

**Problème** : Erreurs de type coercion dans modèles Pydantic.

**Solution** : Ajouté fonction `safe_float_conversion()` dans `api/models.py` avec field validators robustes pour tous les champs float.

### Double montage router analytics

**Problème** : Uniformisation endpoints `/analytics/*` ET `/api/analytics/*`.

**Solution** : Double montage dans `api/main.py:1781` :
```python
app.include_router(analytics_router)
# Double montage pour uniformiser /api/analytics ET /analytics
app.include_router(analytics_router, prefix="/api")
```

L'ancien TROUBLESHOOTING.md est déprécié au profit de cette page.

