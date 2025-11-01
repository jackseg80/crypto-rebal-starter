# Fix Multi-Tenant Isolation - Saxo Dashboard (Oct 2025)

## Problème

**Symptôme**: Tous les utilisateurs voyaient le portfolio de jack (28 positions, 100k USD) dans `saxo-dashboard.html`, même ceux qui n'avaient pas uploadé de données Saxo.

**Impact**: Violation critique de l'isolation multi-tenant → Users pouvaient voir les données d'autres users.

## Cause Root

Dans `adapters/saxo_adapter.py`, fonction `_load_snapshot()`:

```python
def _load_snapshot(user_id: Optional[str] = None) -> Dict[str, Any]:
    if user_id:
        sources_data = _load_from_sources_fallback(user_id)
        if sources_data:
            return sources_data

    # ❌ FALLBACK INCORRECT: Si user_id fourni mais pas de données,
    # on fallback vers le fichier legacy PARTAGÉ data/wealth/saxo_snapshot.json
    _ensure_storage()
    with _STORAGE_PATH.open("r") as handle:
        return json.load(handle)  # Retourne données d'autres users!
```

**Scénario du bug**:
1. Jack uploade des fichiers Saxo → données dans `data/wealth/saxo_snapshot.json` (legacy)
2. Clea/Demo/Donato n'ont PAS de fichiers Saxo dans leurs dossiers
3. `_load_from_sources_fallback("clea")` retourne `None` (pas de données)
4. Code fallback vers `data/wealth/saxo_snapshot.json` → **Retourne les données de jack!**
5. Tous les users voient le portfolio de jack

## Solution

Le fallback vers le fichier legacy ne doit se faire **QUE si `user_id` est `None`** (mode compatibilité).

Si un `user_id` est fourni mais qu'il n'a pas de données → retourner snapshot vide.

```python
def _load_snapshot(user_id: Optional[str] = None) -> Dict[str, Any]:
    if user_id:
        sources_data = _load_from_sources_fallback(user_id)
        if sources_data:
            return sources_data
        # ✅ FIX: Si user_id fourni mais pas de données → retourner vide
        logger.debug(f"No Saxo data found for user {user_id}, returning empty snapshot")
        return {"portfolios": []}

    # Fallback vers legacy SEULEMENT si user_id est None
    _ensure_storage()
    with _STORAGE_PATH.open("r") as handle:
        return json.load(handle)
```

## Vérification

**Tests API**:
```bash
# User sans données Saxo → portfolio vide
curl -H "X-User: clea" http://localhost:8080/api/saxo/portfolios
# → {"portfolios": []}  ✅

# User avec données Saxo → son portfolio
curl -H "X-User: jack" http://localhost:8080/api/saxo/portfolios
# → {"portfolios": [{"positions_count": 28, ...}]}  ✅
```

**Tests unitaires**:
```bash
pytest tests/unit/test_saxo_adapter_isolation.py -v
# 4 tests passent ✅
```

## Impact

- ✅ Isolation multi-tenant restaurée
- ✅ Users sans données Saxo voient un dashboard vide (pas de données d'autres users)
- ✅ Mode legacy (user_id=None) continue de fonctionner
- ✅ Tests de non-régression ajoutés

## Fichiers Modifiés

- `adapters/saxo_adapter.py:123-153` - Fix `_load_snapshot()`
- `tests/unit/test_saxo_adapter_isolation.py` - Tests de non-régression (nouveau)
- `docs/SAXO_MULTI_TENANT_FIX.md` - Documentation (ce fichier)

## Références

- Issue: Users seeing jack's portfolio in saxo-dashboard.html
- Fix Date: Oct 12, 2025
- Tested: ✅ API, ✅ Frontend, ✅ Unit tests
- Severity: Critical (data leak)
- Status: FIXED

