# Saxo Dashboard P0 Enhancements (October 2025)

> **Priority 0 improvements for Saxo portfolio management**
> Last updated: Oct 28, 2025

## 🎯 Overview

Améliorations critiques (P0) du Saxo Dashboard pour gérer :
1. **CFD/Leveraged Detection** - Détection automatique des produits à levier (CFD, leveraged ETFs)
2. **Position Consolidation** - Consolidation des positions fragmentées (multi-lots)
3. **Export Enrichment** - Export complet avec tous les price targets et stop loss
4. **Trailing Stop Tiers** - Affichage détaillé des tiers de trailing stop

---

## ✅ Features Implémentées

### 1. CFD & Leveraged Products Detection

**Problème** : Les positions CFD et ETFs à levier nécessitent des stops plus serrés (risque amplifié par le levier) mais n'étaient pas détectées automatiquement.

**Solution** : Détection multi-sources dans `recommendations_orchestrator.py`

#### Backend Implementation

**Fichier** : `services/ml/bourse/recommendations_orchestrator.py`

**Méthode ajoutée** : `_detect_asset_type()` (lignes 343-407)

```python
def _detect_asset_type(self, symbol: str, asset_class: str, position: Optional[Dict]) -> tuple:
    """
    Detect asset type and CFD/leverage status

    Returns:
        tuple: (asset_type, is_cfd, leverage_multiplier)
    """
    is_cfd = False
    leverage = 1.0

    # 1. Check metadata tags
    if position and 'tags' in position:
        for tag in position['tags']:
            if 'cfd' in tag.lower():
                is_cfd = True
                leverage = 5.0  # Default CFD leverage
                break

    # 2. Check instrument_type field
    if position:
        instrument_type = position.get('instrument_type', '').lower()
        if 'cfd' in instrument_type:
            is_cfd = True
            leverage = 5.0

    # 3. Check asset_class
    if asset_class and 'cfd' in asset_class.lower():
        is_cfd = True
        leverage = 5.0

    # 4. Check symbol pattern
    if 'CFD' in symbol.upper() or symbol.upper().endswith(':CFD'):
        is_cfd = True
        leverage = 5.0

    # 5. Detect leveraged ETFs
    if symbol.upper() in ['TQQQ', 'SQQQ', 'UPRO', 'SPXL']:
        is_cfd = True
        leverage = 3.0  # 3x leveraged ETFs

    return (asset_type, is_cfd, leverage)
```

**Integration** : Appelée dans `analyze_position()` (ligne 183)

**Stop Loss Adjustment** : Passé à `calculate_targets()` (ligne 254)

```python
price_targets = targets.calculate_targets(
    current_price=current_price,
    leverage=leverage if is_cfd else None  # Adjust stop for CFD
)
```

#### Frontend Display

**Fichier** : `static/saxo-dashboard.html`

**Badge CFD** (lignes 4409-4413) :
```javascript
const isCFD = rec.is_cfd || false;
const leverage = rec.leverage || 1;
const cfdBadge = isCFD ?
    `<span style="...">⚠️ ${leverage.toFixed(0)}x</span>` : '';
```

**Warning Modal** : Modal rouge avec warning si CFD détecté
- Affichage du levier (ex: "5x")
- Message : "Leverage: 5x | Risk amplified"
- Tactical advice ajusté : "Reduce position 50%" pour BUY/STRONG BUY

**Résultat visuel** :
```
Tesla Inc. (CFD) ⚠️ 5x | HOLD | R/R 1.8 | $13,650
```

---

### 2. Position Consolidation (Multi-Lots)

**Problème** : Le CSV Saxo exporté avec sections dépliées contient des positions fragmentées :
- Baxter : 5 lignes (1 résumé + 4 achats) → Affiché comme "5 lots" au lieu de "4 lots"
- AMD : 7 lignes → Chaque achat séparé
- Tesla : 2 lignes (CFD + Actions) → Ne doivent PAS être groupés ensemble

**Solution** : Consolidation intelligente avec détection des lignes résumé Saxo

#### Backend Implementation

**Fichier** : `services/ml/bourse/portfolio_adjuster.py`

**Méthode ajoutée** : `_consolidate_duplicate_positions()` (lignes 80-166)

```python
def _consolidate_duplicate_positions(self, recommendations: List[Dict]) -> List[Dict]:
    """
    Consolidate duplicate positions (e.g., 7x AMD → 1x AMD aggregate)

    Handles Saxo double-counting: CSV contains both aggregate + detail lines
    """
    # Group by symbol
    by_symbol = {}
    for rec in recommendations:
        symbol = rec.get('symbol', 'UNKNOWN')
        if symbol not in by_symbol:
            by_symbol[symbol] = []
        by_symbol[symbol].append(rec)

    consolidated = []
    for symbol, recs in by_symbol.items():
        if len(recs) == 1:
            consolidated.append(recs[0])
        else:
            # Detect Saxo summary line (heuristic)
            values = sorted([r.get('current_value', 0) for r in recs], reverse=True)
            largest = values[0]
            sum_others = sum(values[1:])

            # If largest ≈ sum of others (±5%), it's a summary line → remove it
            if abs(largest - sum_others) / max(largest, 1) < 0.05:
                recs_sorted = sorted(recs, key=lambda x: x.get('current_value', 0), reverse=True)
                detail_recs = recs_sorted[1:]  # Remove largest (summary)
                recs = detail_recs

            # Consolidate remaining positions
            total = {
                ...recs[0],
                'current_value': sum(r.get('current_value', 0) for r in recs),
                'positions_count': len(recs),
                'fragmentation_warning': True
            }
            consolidated.append(total)

    return consolidated
```

**Integration** : Appelée dans `adjust_recommendations()` (ligne 61)

#### Frontend Implementation (Onglet Positions)

**Fichier** : `static/saxo-dashboard.html`

**Fonction modifiée** : `loadAllPositions()` (lignes 3695-3742)

**Changements clés** :

1. **Groupement par `(symbol + asset_class)`** au lieu de `symbol` seul :
```javascript
// Key = symbol + asset_class to separate CFD/Actions/etc
const key = `${symbol}|${assetClass}`;
```
→ Tesla CFD et Tesla Actions restent séparés

2. **Détection lignes résumé Saxo** (heuristique identique au backend) :
```javascript
// If largest value ≈ sum of others (±5%), it's a summary line
const values = positions.map(p => p.market_value_usd || 0).sort((a, b) => b - a);
const largest = values[0];
const sumOthers = values.slice(1).reduce((sum, v) => sum + v, 0);

if (Math.abs(largest - sumOthers) / Math.max(largest, 1) < 0.05) {
    // Remove summary line, keep only detail lines
    filteredPositions = sortedPositions.slice(1);
}
```

3. **Badge Fragmentation** :
```javascript
const fragmentationBadge = lotsCount > 1 ?
    `<span style="...">⚠️ ${lotsCount} lots</span>` : '';
```

**Résultat attendu** :

| Avant (brut) | Après (consolidé) |
|--------------|-------------------|
| Baxter 65 actions (résumé)<br>Baxter 20 actions<br>Baxter 15 actions<br>Baxter 15 actions<br>Baxter 15 actions | Baxter ⚠️ 4 lots \| 65 actions \| $1,290 |
| Tesla CFD 50<br>Tesla Actions 31 | Tesla CFD \| 50 actions \| $19,422<br>Tesla Actions \| 31 actions \| $12,011 |

**Tooltip** : "4 lots détectés - Considérer consolidation pour réduire frais"

---

### 3. Export Enrichment

**État** : ✅ **DÉJÀ COMPLET** (aucune modification nécessaire)

L'export texte (All Timeframes) inclut déjà :
- Entry price, Stop Loss, TP1, TP2
- Risk/Reward Ratio
- Toutes les 5 méthodes de stop loss (Fixed Variable, ATR, Technical, Volatility, Fixed %)
- Metadata complète (confidence, rationale, etc.)

**Documentation** : Voir [SAXO_RECOMMENDATIONS_EXPORT.md](SAXO_RECOMMENDATIONS_EXPORT.md)

---

### 4. Trailing Stop Tiers Display

**Problème** : Les positions legacy (forts gains latents) utilisent un trailing stop adaptatif par tiers, mais l'utilisateur ne voyait pas quel tier s'appliquait.

**Solution** : Affichage enrichi dans le modal de recommandation

**Fichier** : `static/saxo-dashboard.html`

**Modal enrichi** (affiché lors du clic sur une recommandation) :
```
🏆 Legacy position: +186%
📊 Tier: 100-500% (Legacy) → Trailing -25%
🛡️ Protected minimum gain: +161%
```

**Tiers de trailing stop** :
- Tier 1 (20-100%) : -15% from ATH
- Tier 2 (100-500%) : -25% from ATH
- Tier 3 (500%+) : -30% from ATH

**Logique** : Voir [TRAILING_STOP_IMPLEMENTATION.md](TRAILING_STOP_IMPLEMENTATION.md)

---

## 📊 Validation des Résultats

### Test Case: Baxter International (BAX)

**CSV Source** :
```
Ligne 36: Baxter 65 actions | $1,289.96  ← RÉSUMÉ
Ligne 38: Baxter 20 actions | $396.91    ← Détail (Position ID: 7053105528)
Ligne 40: Baxter 15 actions | $297.68    ← Détail (Position ID: 7056421140)
Ligne 42: Baxter 15 actions | $297.68    ← Détail (Position ID: 7055057582)
Ligne 44: Baxter 15 actions | $297.68    ← Détail (Position ID: 7053773325)
```

**Validation** :
- Sum détails : 20+15+15+15 = **65 actions** ✅
- Sum valeurs : $396.91 + $297.68×3 = **$1,289.95** ≈ $1,289.96 (différence de $0.01 = arrondi) ✅
- Détection résumé : `|1289.96 - 1289.95| / 1289.96 = 0.000008 < 0.05` → **Détecté comme résumé** ✅

**Résultat Frontend** :
```
Onglet Recommendations: Baxter ⚠️ 4 lots | 65 actions | $1,290
Onglet Positions:       Baxter ⚠️ 4 lots | 65 actions | $1,290
```

### Test Case: Tesla (TSLA)

**CSV Source** :
```
Ligne 3: Tesla Inc. (CFD)     | 50 actions | $19,422 | Type: CFD
Ligne 6: Tesla Inc. (Actions) | 31 actions | $12,011 | Type: Actions
```

**Validation** :
- Groupement par clé : `"TSLA:xnas|CFD"` ≠ `"TSLA:xnas|Actions"` → **Séparés** ✅
- Badge CFD : `⚠️ 5x` affiché sur ligne CFD ✅

**Résultat Frontend** :
```
Tesla Inc. (CFD)     ⚠️ 5x | 50 actions | $19,422
Tesla Inc. (Actions)       | 31 actions | $12,011
```

---

## 🗂️ Fichiers Modifiés

### Backend (3 fichiers)

1. **`services/ml/bourse/recommendations_orchestrator.py`** (+70 lignes)
   - Méthode `_detect_asset_type()` : Détection CFD/leverage multi-sources
   - CFD tactical advice adjustment
   - Metadata `is_cfd`, `leverage`, `cfd_warning`

2. **`services/ml/bourse/price_targets.py`** (+10 lignes)
   - Paramètre `leverage` ajouté à `calculate_targets()`
   - Stop loss ajusté pour CFD : `adjusted_distance = stop_distance / leverage`

3. **`services/ml/bourse/portfolio_adjuster.py`** (+70 lignes)
   - Méthode `_consolidate_duplicate_positions()` : Détection heuristique + consolidation
   - Agrégation des valeurs et quantités
   - Badge `positions_count` et `fragmentation_warning`

### Frontend (1 fichier)

**`static/saxo-dashboard.html`** (+85 lignes)
- Badge CFD `⚠️ 5x` (orange)
- Badge fragmentation `⚠️ N lots` (rouge)
- Warning modal CFD (rouge, "Risk amplified")
- Trailing stop tiers display enrichi (modal)
- Consolidation positions dans `loadAllPositions()` (lignes 3695-3742)
  - Groupement par `(symbol + asset_class)`
  - Détection lignes résumé Saxo
  - Agrégation quantités/valeurs

---

## 🔧 Logique Technique Détaillée

### Heuristique de Détection Ligne Résumé

**Principe** : Dans les exports Saxo avec sections dépliées, la première ligne d'une position multi-lot est un résumé agrégé des achats détaillés qui suivent.

**Caractéristiques ligne résumé** :
- ✅ Valeur = somme exacte des lignes détails (±5% tolérance)
- ✅ Quantité = somme exacte des lignes détails
- ❌ **Pas de Position ID** (colonne vide)

**Algorithme** :
```python
values = [rec.get('current_value', 0) for rec in positions_for_symbol]
values.sort(reverse=True)  # Largest first

largest = values[0]
sum_others = sum(values[1:])

if abs(largest - sum_others) / max(largest, 1) < 0.05:
    # Ligne résumé détectée → supprimer
    positions_without_summary = positions_sorted[1:]
```

**Tolérance 5%** : Permet de gérer les arrondis et variations mineures (frais, spreads, etc.)

### Groupement CFD vs Actions

**Problème** : Le même symbole (ex: TSLA) peut avoir plusieurs instruments :
- Tesla CFD (contrat à terme avec levier)
- Tesla Actions (propriété réelle)

**Solution** : Clé de groupement = `symbol + asset_class`

**Exemple** :
```javascript
const key = `${symbol}|${assetClass}`;
// "TSLA:xnas|CFD"     → Groupe 1
// "TSLA:xnas|Actions" → Groupe 2
```

**Avantage** : Séparation automatique sans parsing complexe du symbol

---

## 📚 Références

### Code Backend
- [services/ml/bourse/recommendations_orchestrator.py:183-313](../services/ml/bourse/recommendations_orchestrator.py#L183-L313) - CFD detection
- [services/ml/bourse/price_targets.py](../services/ml/bourse/price_targets.py) - Stop loss adjustment
- [services/ml/bourse/portfolio_adjuster.py:80-166](../services/ml/bourse/portfolio_adjuster.py#L80-L166) - Consolidation backend

### Code Frontend
- [static/saxo-dashboard.html:3695-3742](../static/saxo-dashboard.html#L3695-L3742) - Position consolidation
- [static/saxo-dashboard.html:4409-4418](../static/saxo-dashboard.html#L4409-L4418) - CFD/Fragmentation badges

### Docs Connexes
- [SAXO_RECOMMENDATIONS_EXPORT.md](SAXO_RECOMMENDATIONS_EXPORT.md) - Export système
- [TRAILING_STOP_IMPLEMENTATION.md](TRAILING_STOP_IMPLEMENTATION.md) - Trailing stop logic
- [STOP_LOSS_SYSTEM.md](STOP_LOSS_SYSTEM.md) - Stop loss methods

---

## 🐛 Troubleshooting

### Badge "⚠️ N lots" incorrect

**Symptôme** : Affiche "5 lots" au lieu de "4 lots" pour Baxter

**Cause** : Ligne résumé Saxo non détectée

**Vérification** :
1. Ouvrir console JavaScript (F12)
2. Vérifier logs : `"Saxo summary detected for BAX:xnys|Actions: removed summary line, keeping 4 detail lots"`
3. Si absent → Heuristique échoue (tolérance 5% trop stricte ?)

**Solution** :
- Augmenter tolérance à 10% : `< 0.10` au lieu de `< 0.05`
- Vérifier valeurs exactes dans CSV

### Tesla CFD et Actions groupés ensemble

**Symptôme** : Une seule ligne "Tesla 81 actions" au lieu de 2 lignes séparées

**Cause** : Groupement par `symbol` au lieu de `symbol + asset_class`

**Vérification** :
```javascript
// Code actuel (CORRECT)
const key = `${symbol}|${assetClass}`;

// Code incorrect (ancien)
const key = symbol; // ❌ Groupe tout ensemble
```

**Solution** : Vérifier que le code utilise bien `${symbol}|${assetClass}`

### Badge CFD n'apparaît pas

**Symptôme** : Pas de badge "⚠️ 5x" sur positions CFD

**Cause** : Backend ne retourne pas `is_cfd` ou `leverage` dans la réponse API

**Vérification** :
1. Ouvrir Network tab (F12) → `/api/ml/bourse/portfolio-recommendations`
2. Vérifier réponse JSON : `rec.is_cfd` et `rec.leverage` présents ?
3. Si absents → Vérifier backend `_detect_asset_type()` logs

**Solution** : Redémarrer serveur backend pour activer détection CFD

---

## 🔮 Améliorations Futures

### P1 - Court terme
- [ ] Détecter plus de leveraged ETFs (SOXL, TECL, etc.)
- [ ] Ajouter metadata Position ID dans export CSV pour faciliter détection résumé
- [ ] Badge "consolidate" actionnable (bouton pour fusionner lots)

### P2 - Moyen terme
- [ ] Détection automatique levier custom (parsing symbol pattern)
- [ ] Warning modal avec calcul exact du risque amplifié (ex: "Perte de -10% = -50% avec 5x leverage")
- [ ] Comparaison frais multi-lots vs position consolidée

### P3 - Long terme
- [ ] API Saxo pour consolider positions automatiquement
- [ ] Machine learning pour détecter patterns de résumé Saxo (au-delà de l'heuristique)
- [ ] Dashboard dédié aux positions fragmentées avec recommandations de consolidation

---

*Améliorations P0 du Saxo Dashboard - Focus sur CFD detection et consolidation positions*
