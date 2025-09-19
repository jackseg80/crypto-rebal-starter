# Système Unifié de Gestion des Contradictions

## Vue d'ensemble

Le système de contradiction unifié centralise la détection et le traitement des signaux contradictoires dans une architecture cohérente. Il remplace les implémentations éparses par une logique centralisée avec poids adaptatifs et caps de risque.

### Source de Vérité Unique

**Clé primaire**: `governance.contradiction_index` (0-1 normalisé)

**Sélecteurs centralisés**:
- `selectContradiction01(state)` → 0-1 (calculs internes)
- `selectContradictionPct(state)` → 0-100% (affichage UI)
- `getContradictionPctCompat(state)` → Compatibilité legacy avec warning

---

## Classification des Contradictions

### Seuils Standardisés

| Niveau | Seuil | Couleur | Priorité | Message Type |
|--------|-------|---------|----------|--------------|
| **Low** | < 40% | 🟢 Success | Low | "Signaux alignés" |
| **Medium** | 40-70% | 🟡 Warning | Medium | "Vigilance recommandée" |
| **High** | ≥ 70% | 🔴 Critical | High | "Approche prudente" |

### Recommandations Contextuelles

**High (≥70%)**:
- Réduire exposition actifs risqués
- Privilégier stablecoins et majors (BTC/ETH)
- Reporter décisions non-urgentes
- Surveillance rapprochée

**Medium (40-70%)**:
- Maintenir allocation équilibrée
- Éviter positions spéculatives importantes
- Surveiller développements marché
- Préparer scenarios contingence

**Low (<40%)**:
- Conditions favorables stratégies actives
- Opportunité optimiser allocation
- Considérer positions tactiques
- Exploiter signaux momentum

---

## Poids Adaptatifs avec Renormalisation

### Formule de Base

```javascript
// Coefficients baseline (backtesting 24 mois)
const cycleReduction = 0.35;    // jusqu'à -35%
const onchainReduction = 0.15;  // jusqu'à -15%
const riskIncrease = 0.50;      // jusqu'à +50%

// Application
cycle = base.cycle * (1 - cycleReduction * contradiction)
onchain = base.onchain * (1 - onchainReduction * contradiction)
risk = base.risk * (1 + riskIncrease * contradiction)
```

### Bornes Défensives

- **Floor**: 12% minimum par composant
- **Ceil**: 65% maximum par composant
- **Renormalisation**: Somme stricte = 1.000

### Exemples de Poids

| Contradiction | Cycle | OnChain | Risk | Mode |
|---------------|-------|---------|------|------|
| 10% (Low) | 39% | 34% | 27% | Normal |
| 50% (Medium) | 32% | 29% | 39% | Prudent |
| 85% (High) | 27% | 25% | 48% | Défensif |

---

## Caps de Risque Adaptatifs

### Segments Ciblés

**Memecoins**: 15% → 5% (réduction jusqu'à 67%)
**Small Caps**: 25% → 12% (réduction jusqu'à 52%)
**AI/Data**: 20% → 10% (réduction jusqu'à 50%)
**Gaming/NFT**: 18% → 8% (réduction jusqu'à 56%)

### Logique d'Application

```javascript
// Interpolation linéaire selon contradiction
cap_adjusted = lerp(cap_normal, cap_minimum, contradiction_01)

// Exemple Memecoins
cap_memecoins = 0.15 + (0.05 - 0.15) * contradiction  // 15% → 5%
```

### Validation d'Allocation

Le système valide automatiquement que les allocations respectent les caps adaptatifs et génère des warnings/violations selon le niveau de contradiction.

---

## Intégration UI

### Badges Unifiés

Format standardisé: `"Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N"`

**Arrondi cohérent**: `Math.round(selectContradictionPct(state))`

### Indicateurs Visuels

- **Badge couleur**: Selon classification (success/warning/danger)
- **Status flags**: STALE/ERROR intégrés
- **Métadonnées**: Timestamps et sources visibles

---

## Architecture Technique

### Modules Centralisés

```
static/selectors/governance.js           # Sélecteurs centralisés
static/governance/contradiction-policy.js # Classification + poids + caps
static/risk/adaptive-weights.js          # Interface unifiée poids
static/simulations/contradiction-caps.js # Intégration simulateur
static/components/Badges.js              # UI unifiée (refactorisé)
```

### Points d'Intégration

1. **Badges**: Tous les dashboards via `renderBadges()`
2. **Analytics**: Via sélecteurs centralisés
3. **Simulateur**: Via `applyContradictionCaps()`
4. **Recommendations**: Via `classifyContradiction()`

---

## Tests et Validation

### Page de Test Interactive

**URL**: `/static/test-contradiction-unified.html`

**Fonctionnalités**:
- Slider contradiction 0-100%
- Validation temps réel des 4 critères
- Badge demo live
- Tests automatiques (10%, 50%, 85%)
- Métadonnées détaillées

### Checks Automatiques

✅ **Somme poids = 1.000** (tolerance 0.001)
✅ **Poids dans bornes [12%-65%]**
✅ **Risk augmente avec contradiction**
✅ **Caps diminuent avec contradiction**

### API de Debug

```javascript
// Console debugging
window.testContradictionLogic.setContradiction(85)
window.testContradictionLogic.runAutoTest()
```

---

## Migration et Compatibilité

### Suppression Sources Legacy

- ❌ `scores.contradictory_signals` (array count)
- ❌ `contradictions.length` (direct count)
- ✅ `governance.contradiction_index` (source unique)

### Wrapper Compatibilité

```javascript
// Temporaire - génère warning console
export function getContradictionPctCompat(state) {
  const primary = selectContradictionPct(state);
  if (primary > 0) return primary;

  console.warn("⚠️ Fallback to legacy contradiction source");
  // fallback logic...
}
```

### Re-exports Backward

```javascript
// Dans Badges.js - compatibilité API
export {
  selectContradictionPct as getContradiction,
  selectEffectiveCap as getEffectiveCap,
  // ...
} from '../selectors/governance.js';
```

---

## Monitoring et Observabilité

### Métriques Clés

- **Contradiction %**: Niveau temps réel
- **Adjustments ratio**: Impact sur poids/caps
- **Validation status**: Cohérence système
- **Classification changes**: Transitions de niveau

### Logging Standard

```javascript
console.debug('🚀 Adaptive weights: contradiction 47% → defensive mode');
console.warn('⚠️ Fallback to legacy contradiction source');
console.info('✅ Contradiction system unified: all checks passed');
```

### Rapports Automatiques

```javascript
const report = generateCapsReport(state);
// Inclut: contradiction, caps, reductions, recommendations
```

---

## Roadmap

### Phase 1 ✅ (Actuel)
- Sélecteurs centralisés
- Poids adaptatifs avec renormalisation
- Caps de risque memecoins/small_caps
- Badges unifiés

### Phase 2 (Futur)
- Extension caps: AI/Data, Gaming/NFT
- Backtesting automatisé 24 mois
- Calibrage coefficients basé sur Sharpe/Sortino
- Intégration Phase Engine

### Phase 3 ✅ (Production Stabilization)
- Hystérésis & EMA anti-flickering (deadband ±2%, persistence 3 ticks)
- Staleness gating pour robustesse (freeze weights, preserve caps)
- Rate limiting token bucket (6 req/s, burst 12, TTL adaptatif)
- Suite tests complète avec 16 scénarios de validation

### Phase 4 (Évolution Future)
- Machine learning des seuils
- Contradiction multi-timeframe
- Caps dynamiques selon volatilité
- API temps réel contradiction

---

## Production Stabilization (Phase 3)

### Hystérésis & EMA Anti-Flickering

**Objectif**: Prévenir les oscillations rapides des poids adaptatifs

**Architecture**:
- `static/governance/stability-engine.js` - Engine principal avec deadband ±2%
- Persistence 3 ticks avant validation de changement
- EMA coefficient α=0.3 pour lissage
- Global state tracking pour continuité

**Fonctionnalités**:
```javascript
// Application automatique dans contradiction-policy.js
const c = getStableContradiction(state); // Au lieu de selectContradiction01
```

**Debug interface**:
```javascript
window.stabilityEngine.getDebugInfo()  // État détaillé
window.stabilityEngine.reset()         // Reset pour tests
window.stabilityEngine.forceStale(true) // Force staleness
```

### Staleness Gating

**Principe**: Gestion dégradée lors de données obsolètes (>30min)

**Comportement**:
- **Freeze adaptatif**: Poids figés sur dernière valeur stable
- **Caps préservés**: Limites défensives maintenues
- **Auto-resume**: Reprise automatique sur données fraîches

**Logs de monitoring**:
```
🔒 Staleness gating: freezing adaptive weights at last stable value
🔓 Staleness gating: resuming adaptive weights
```

### Rate Limiting Token Bucket

**Configuration**: `config/settings.py`
```python
rate_limit_refill_rate: 6.0    # 6 req/s (21600/h)
rate_limit_burst_size: 12      # Burst capacity
```

**Fonctionnalités avancées**:
- **TTL adaptatif**: 30s base, ajusté selon hit ratio (10s-300s)
- **Cleanup automatique**: Buckets stale supprimés après 1h
- **Métriques**: Cache hit ratio, tokens disponibles, temps d'attente

**Service**: `services/rate_limiter.py`
```python
limiter = get_rate_limiter()
allowed, metadata = await limiter.check_rate_limit(client_id, endpoint)
ttl = limiter.get_adaptive_cache_ttl(client_id, endpoint)
```

### Tests Complets

**Suite complète**: `/static/test-stability-comprehensive.html`

**Couverture**:
- ✅ 4 tests hystérésis (deadband, persistence, EMA, anti-oscillation)
- ✅ 4 tests staleness (freeze, resume, caps, degradation)
- ✅ 4 tests rate limiting (bucket, burst, TTL, graceful)
- ✅ 4 tests intégration (pipeline, cohérence, edge cases, performance)

**Tests unitaires**: `tests/unit/test_stability_engine.py`
- Token bucket mechanics avec pytest
- Performance sous charge (1000 req < 1s)
- Gestion erreurs et cas limites
- Thread safety validation

**Monitoring en continu**:
```javascript
// Auto-update status chaque seconde
setInterval(updateRateLimitStatus, 1000);

// Métriques temps réel
window.stabilityTests.runFullSuite() // Suite complète
```

---

*Dernière mise à jour: Production Stabilization complète avec tests exhaustifs*