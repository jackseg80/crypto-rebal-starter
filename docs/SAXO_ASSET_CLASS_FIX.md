# Fix: Saxo Asset Class Detection & Dashboard Cleanup

**Date**: 18 octobre 2025
**Commit**: `46c54e917e7c1cf7a37acd8973820125f02fa9ed`

## Problem

Asset classes dans le dashboard Saxo s'affichaient tous comme "Other" au lieu de "Stock", "ETF", "Bond", etc.

**Cause**: Le CSV Saxo contient des libellés longs comme "Exchange Traded Fund (ETF)" au lieu de simplement "ETF", et le mapping exact ne fonctionnait pas.

## Solution

### 1. Asset Class Detection Améliorée

**Fichier**: `connectors/saxo_import.py:318-340`

**Avant** (mapping exact):
```python
mapping = {
    'etf': 'ETF',
    'stock': 'Stock',
    # ...
}
return mapping.get(asset_class, 'Other')
```

**Après** (substring matching):
```python
# Check for partial matches
if 'etf' in asset_class or 'exchange traded fund' in asset_class:
    return 'ETF'
if 'action' in asset_class or 'equity' in asset_class or 'stock' in asset_class:
    return 'Stock'
if 'bond' in asset_class or 'obligation' in asset_class:
    return 'Bond'
if 'cfd' in asset_class:
    return 'CFD'
```

**Améliorations**:
- ✅ Support des formats longs: "Exchange Traded Fund (ETF)" → "ETF"
- ✅ Support français: "Actions" → "Stock", "Obligations" → "Bond"
- ✅ Nouveau type: CFD (Contracts for Difference)
- ✅ Robuste aux variations CSV

### 2. Dashboard Simplifié

**Fichier**: `static/saxo-dashboard.html`

**Suppressions** (-172 lignes):
- ❌ Bandeau "Nouveau système Sources"
- ❌ Indicateurs "Source active" et "Fraîcheur"
- ❌ Fonction `updateCurrentSourceName()`
- ❌ Fonction `refreshSaxoStaleness()`
- ❌ Styles CSS obsolètes (`.sources-banner`, `.sources-link`, etc.)
- ❌ Logique de résolution `file_key` et `bourseSource`

**Ajouts**:
- ✅ Style CSS pour `.asset-class-cfd` (rouge #FF6B6B)
- ✅ Header simplifié: titre + sous-titre seulement

## Tests

Portfolio utilisateur `jack` (28 positions, $106,749.45):

**Avant**:
```
Asset Classes:
  - Other: 28  ❌
```

**Après**:
```
Asset Classes:
  - Stock: 21  ✅
  - ETF: 7     ✅
```

### Exemples de détection

| CSV Raw Value                    | Détecté comme |
|----------------------------------|---------------|
| "Exchange Traded Fund (ETF)"     | ETF           |
| "Actions"                        | Stock         |
| "Equity"                         | Stock         |
| "Obligations"                    | Bond          |
| "CFD"                            | CFD           |

## Asset Classes Supportés

1. **Stock** (Actions)
   - Détection: `action`, `equity`, `stock`
   - Badge: Bleu (brand-primary)

2. **ETF** (Exchange-Traded Funds)
   - Détection: `etf`, `exchange traded fund`
   - Badge: Vert (success)

3. **Bond** (Obligations)
   - Détection: `bond`, `obligation`, `fixed income`
   - Badge: Orange (warning)

4. **CFD** (Contracts for Difference)
   - Détection: `cfd`, `contract for difference`
   - Badge: Rouge (#FF6B6B)

5. **Other** (Fallback)
   - Tout ce qui ne matche pas les catégories ci-dessus
   - Badge: Bleu info

## Impact

- Dashboard Saxo maintenant simple et épuré
- Asset classes correctement détectées dans tous les onglets
- Visualisations (allocation pie charts) précises
- Pas besoin de réimporter les CSV (parsing à la volée)

## Fichiers Modifiés

```
connectors/saxo_import.py       +14 -6   (logique substring matching)
static/saxo-dashboard.html      +6 -166  (cleanup + CSS CFD)
```

## Migration

**Aucune action requise** - Les changements s'appliquent immédiatement:
1. Le parsing CSV se fait à chaque requête API
2. Recharger le dashboard suffit pour voir les nouvelles asset classes
3. Pas de cache à vider

## Notes Techniques

### Debug Field

Ajout du champ `_raw_asset_class` dans les positions pour faciliter le débogage:

```python
return {
    "asset_class": enriched_asset_class,
    "_raw_asset_class": asset_class_raw,  # Pour debugging
    # ...
}
```

Ce champ n'est pas affiché dans l'UI mais permet de tracer les mappings.

### Log Amélioré

```python
logger.debug(f"Processed: {instrument_raw} → symbol={enriched_symbol}, "
             f"isin={enriched_isin}, asset_class={asset_class_raw} → {enriched_asset_class}")
```

Exemple:
```
DEBUG: Processed: Tesla Inc. → symbol=TSLA, isin=US88160R1014, asset_class=Actions → Stock
DEBUG: Processed: iShares Core MSCI World UCITS ETF → symbol=IWDA, asset_class=Exchange Traded Fund (ETF) → ETF
```

## Voir Aussi

- `docs/SAXO_IMPORT_FIX_GUIDE.md` - Fix général import CSV
- `docs/SAXO_INTEGRATION_SUMMARY.md` - Vue d'ensemble intégration Saxo
- `connectors/saxo_import.py` - Code source parsing CSV
