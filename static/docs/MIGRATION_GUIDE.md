# Guide de Migration Strategy API - PR-C

Guide pour migrer de la logique frontend `calculateIntelligentDecisionIndex` vers l'API Strategy backend.

## Vue d'ensemble

**Objectif** : Remplacer la logique de calcul de décision dispersée dans le frontend par l'API Strategy unifiée.

**Approche** : Migration progressive avec adaptateur de compatibilité, permettant un rollback facile.

## Architecture de Migration

```
Frontend Legacy          Adaptateur             Backend API
┌─────────────────┐     ┌─────────────────┐    ┌─────────────────┐
│calculateIntel...│────▶│strategy-api-    │───▶│/api/strategy/   │
│unified-insights │     │adapter.js       │    │preview          │
│                 │     │                 │    │                 │
│Logique dispersée│     │Feature flags    │    │Strategy Registry│
│Calculs frontend │     │Cache TTL        │    │Templates        │
│Pas de templates │     │Fallback auto    │    │Phase-aware      │
└─────────────────┘     └─────────────────┘    └─────────────────┘
```

## Étapes de Migration

### 1. Activation de l'Adaptateur

```javascript
// Dans votre dashboard existant
import { calculateIntelligentDecisionIndexAPI, StrategyConfig } from './core/strategy-api-adapter.js';

// Activer la migration
StrategyConfig.setEnabled(true);
StrategyConfig.setDefaultTemplate('balanced');

// Utiliser l'adaptateur (interface identique)
const decision = await calculateIntelligentDecisionIndexAPI(context);
```

### 2. Remplacement Progressif

**Option A : Import alias (recommandé)**
```javascript
// Remplacer l'import existant
// import { calculateIntelligentDecisionIndex } from './core/unified-insights.js';
import { calculateIntelligentDecisionIndex } from './core/strategy-api-adapter.js';
```

**Option B : Unified State V2**
```javascript
// Utiliser la nouvelle version complète
import { getUnifiedState } from './core/unified-insights-v2.js';

const state = await getUnifiedState();
// Nouvelles propriétés disponibles :
// - state.strategy.template_used
// - state.strategy.policy_hint  
// - state.strategy.targets
```

### 3. Contrôles Utilisateur

```javascript
import { createMigrationControls, createMigrationIndicator } from './components/MigrationControls.js';

// Panel complet (développement)
createMigrationControls(document.body);

// Indicateur simple (production)  
createMigrationIndicator(headerContainer, (enabled) => {
  console.log('Strategy API', enabled ? 'activé' : 'désactivé');
});
```

## Configuration Avancée

### Templates Stratégiques

```javascript
import { getAvailableStrategyTemplates, compareStrategyTemplates } from './core/strategy-api-adapter.js';

// Lister les templates
const templates = await getAvailableStrategyTemplates();
// { conservative: {name: "Conservative", risk_level: "low"}, ... }

// Comparer plusieurs templates
const comparison = await compareStrategyTemplates(['conservative', 'balanced', 'aggressive']);
// { comparisons: { conservative: {decision_score: 52.8}, ... } }
```

### Logique Adaptative

```javascript
// L'adaptateur choisit automatiquement le template basé sur le contexte
const context = {
  riskScore: 25,          // Faible → template conservative
  contradiction: 0.7,     // Élevé → template contradiction_averse
  blendedScore: 80        // Score élevé → template aggressive
};

const result = await calculateIntelligentDecisionIndexAPI(context);
console.log(result.template_used); // "conservative" (basé sur riskScore)
```

### Gestion d'Erreur et Fallback

```javascript
StrategyConfig.setEnabled(true);          // Activer API
StrategyConfig.setFallbackOnError(true);  // Fallback auto vers legacy

try {
  const result = await calculateIntelligentDecisionIndexAPI(context);
  if (result.source === 'strategy_api') {
    // Succès API
  } else {
    // Fallback legacy utilisé
  }
} catch (error) {
  // Erreur complète (si fallback désactivé)
}
```

## Nouveautés Disponibles

### Allocation Targets

```javascript
const result = await calculateIntelligentDecisionIndexAPI(context);

result.targets.forEach(target => {
  console.log(`${target.symbol}: ${(target.weight * 100).toFixed(1)}%`);
  console.log(`Rationale: ${target.rationale}`);
});

// Exemple sortie:
// BTC: 35.0% - Base solide
// ETH: 25.0% - Growth potential  
// LARGE: 20.0% - Diversification
// USDC: 20.0% - Buffer
```

### Policy Hints

```javascript
const result = await calculateIntelligentDecisionIndexAPI(context);

switch (result.policy_hint) {
  case 'Slow':
    // Contradictions élevées ou confiance faible
    // → Approche prudente, seuils élevés
    break;
  case 'Aggressive':  
    // Score élevé et signaux cohérents
    // → Opportunités d'allocation
    break;
  case 'Normal':
    // Conditions standard
    break;
}
```

### Métadonnées Enrichies

```javascript
const result = await calculateIntelligentDecisionIndexAPI(context);

console.log({
  template_used: result.template_used,      // "Balanced"
  api_version: result.api_version,          // "v1"
  generated_at: result.generated_at,        // ISO timestamp
  source: result.source,                    // "strategy_api" | "legacy"
  policy_hint: result.policy_hint           // "Normal" | "Slow" | "Aggressive"
});
```

## Test et Validation

### Page de Test

Ouvrir `http://localhost:8080/static/test-strategy-migration.html` pour :
- Comparer legacy vs API côte à côte
- Tester différents templates
- Visualiser les allocations targets
- Analyser les performances

### Tests Unitaires

```bash
# Test du Strategy Registry
pytest tests/unit/test_strategy_registry.py -v

# Test des endpoints API
pytest tests/integration/test_strategy_endpoints.py -v
```

### Validation Console

```javascript
// Debug mode pour logs détaillés
StrategyConfig.setDebugMode(true);

const result = await calculateIntelligentDecisionIndexAPI(context);
// Console affichera :
// [StrategyAdapter] Calling strategy API: /api/strategy/preview {...}
// [StrategyAdapter] Strategy API result: {...}
```

## Checklist de Migration

### Pré-migration
- [ ] Serveur avec Strategy API démarrée (`/api/strategy/templates` accessible)
- [ ] Tests existants du dashboard fonctionnels
- [ ] Backup de la logique frontend actuelle

### Migration
- [ ] Import de `strategy-api-adapter.js`
- [ ] Activation progressive avec feature flag
- [ ] Test comparatif legacy vs API
- [ ] Validation des nouvelles données (targets, policy_hint)
- [ ] Test de fallback en cas d'erreur API

### Post-migration
- [ ] Monitoring des performances API vs frontend
- [ ] Validation comportement utilisateur final
- [ ] Documentation mise à jour
- [ ] Suppression progressive code legacy (optionnel)

## Troubleshooting

### API Non Accessible
```javascript
// Vérifier connectivity
const templates = await getAvailableStrategyTemplates();
console.log(templates); // Si erreur → problème réseau/serveur
```

### Résultats Incohérents
```javascript
// Activer comparison logging
StrategyConfig.setDebugMode(true);

// Les logs montreront les différences entre legacy et API
const result = await calculateIntelligentDecisionIndexAPI(context);
```

### Performance Dégradée
```javascript
// Vérifier timeout et cache
StrategyConfig.getConfig();
// { cache_ttl_ms: 60000, api_timeout_ms: 3000, ... }

// Clear cache si nécessaire
StrategyConfig.clearCache();
```

## Rollback

En cas de problème, désactivation immédiate possible :

```javascript
// Rollback complet vers legacy
StrategyConfig.setEnabled(false);

// Ou utiliser directement l'ancienne version
import { getUnifiedState } from './core/unified-insights.js'; // Version originale
```

## Contact et Support

- **Tests** : `/static/test-strategy-migration.html`
- **Endpoints** : `/api/strategy/templates`, `/api/strategy/preview`
- **Logs** : Console développeur avec `StrategyConfig.setDebugMode(true)`
