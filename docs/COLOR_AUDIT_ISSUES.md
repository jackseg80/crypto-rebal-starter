# Audit des Couleurs - Problèmes Identifiés

**Date:** 8 octobre 2025

## Problèmes Trouvés

### 1. ❌ `risk-dashboard.html` - Fonction `pickScoreColor` inversée (ligne 5276)

**Status:** ✅ CORRIGÉ

**Avant:**
```javascript
const pickScoreColor = (score) => {
  if (score > 70) return 'var(--danger)';     // ❌ Rouge pour score élevé
  if (score < 40) return 'var(--success)';    // ❌ Vert pour score faible
  return 'var(--warning)';
};
```

**Après:**
```javascript
const pickScoreColor = (score) => {
  if (score > 70) return 'var(--success)';    // ✅ Vert pour score élevé
  if (score >= 40) return 'var(--warning)';   // ✅ Orange pour score moyen
  return 'var(--danger)';                     // ✅ Rouge pour score faible
};
```

### 2. ❌ `risk-dashboard.html` - Textes "Niveau de risque" inversés (ligne 4054-4058)

**Status:** ⏳ À CORRIGER

**Problème:** Le texte dit "Élevé - Attention" quand score > 70, mais un score élevé = bon (robuste)

**Avant:**
```javascript
const riskScore = m.risk_score || 0;
if (riskScore > 70) return 'Élevé - Attention aux corrections brutales';  // ❌ Inversé
if (riskScore > 50) return 'Modéré - Typique pour crypto';
return 'Contrôlé - Bon équilibre risque/rendement';  // ❌ Inversé
```

**Après (proposé):**
```javascript
const riskScore = m.risk_score || 0;
if (riskScore > 70) return 'Excellent - Portfolio très robuste';  // ✅ Correct
if (riskScore > 50) return 'Bon - Équilibre robustesse/rendement';
return 'Faible - Attention aux fortes volatilités';  // ✅ Correct
```

### 3. ❌ `risk-dashboard.html` - Risk Score sans couleur (ligne 4236)

**Status:** ⏳ À CORRIGER

**Avant:**
```html
<span class="metric-value" data-score="risk-display">${safeFixed(m.risk_score, 1)}/100</span>
```

**Après (proposé):**
```html
<span class="metric-value" data-score="risk-display" style="color: ${getScoreColor(m.risk_score)};">
  ${safeFixed(m.risk_score, 1)}/100
</span>
```

### 4. ❌ `risk-dashboard.html` - Data Confidence sans couleur (ligne 4138)

**Status:** ⏳ À CORRIGER

**Avant:**
```html
<span class="metric-value">${safeFixed((p.confidence_level || 0) * 100, 1)}%</span>
```

**Après (proposé):**
```html
<span class="metric-value" style="color: ${getScoreColor((p.confidence_level || 0) * 100)};">
  ${safeFixed((p.confidence_level || 0) * 100, 1)}%
</span>
```

### 5. ❌ `risk-dashboard.html` - Calmar Ratio sans couleur (ligne 4211)

**Status:** ⏳ À CORRIGER

**Avant:**
```html
<span class="metric-value">${safeFixed(m.calmar_ratio)}</span>
```

**Après (proposé):**
```html
<span class="metric-value" style="color: ${getCalmarColor(m.calmar_ratio)};">
  ${safeFixed(m.calmar_ratio)}
</span>
```

**Helper function:**
```javascript
const getCalmarColor = (value) => {
  if (value == null) return 'var(--theme-text)';
  if (value > 1.5) return 'var(--success)';   // Excellent
  if (value > 0.5) return 'var(--warning)';   // Acceptable
  return 'var(--danger)';                     // Faible
};
```

### 6. ✅ `risk-dashboard.html` - Diversification Ratio (ligne 4450)

**Status:** ✅ CORRECT (utilise déjà `getMetricHealth`)

```javascript
style="color: ${getMetricHealth('diversification_ratio', c.diversification_ratio).color}"
```

### 7. ❓ `analytics-unified.html` - Decision Index coloré ?

**Question:** Le Decision Index doit-il avoir une couleur selon son score ou rester toujours bleu?

**Réponse proposée:** OUI, il devrait être coloré selon la même sémantique positive (0-100)

### 8. ⏳ Panel de gauche (Sidebar) - Styling minimal

**Problème:** Panel de gauche manque de couleurs et de style

**Éléments à styliser:**
- CCS Mixte (Directeur)
- On-Chain Composite
- Risk Score
- Score Décisionnel
- Contradiction

**Proposition:** Ajouter couleurs + badges de niveau (Excellent/Bon/Faible)

## Fonction Helper Proposée

```javascript
// Fonction universelle pour colorer les scores (0-100)
function getScoreColor(score) {
  if (score == null || isNaN(score)) return 'var(--theme-text)';
  const s = Number(score);
  if (s > 70) return 'var(--success)';    // Vert - Excellent
  if (s >= 40) return 'var(--warning)';   // Orange - Moyen
  return 'var(--danger)';                 // Rouge - Faible
}

// Fonction pour Sharpe Ratio
function getSharpeColor(sharpe) {
  if (sharpe == null || isNaN(sharpe)) return 'var(--theme-text)';
  const s = Number(sharpe);
  if (s > 1.5) return 'var(--success)';   // Excellent
  if (s > 0.5) return 'var(--warning)';   // Acceptable
  return 'var(--danger)';                 // Faible
}

// Fonction pour Calmar Ratio
function getCalmarColor(calmar) {
  if (calmar == null || isNaN(calmar)) return 'var(--theme-text)';
  const c = Number(calmar);
  if (c > 1.5) return 'var(--success)';
  if (c > 0.5) return 'var(--warning)';
  return 'var(--danger)';
}

// Fonction pour Diversification Ratio
function getDiversificationColor(div) {
  if (div == null || isNaN(div)) return 'var(--theme-text)';
  const d = Number(div);
  if (d > 2.0) return 'var(--success)';   // Très diversifié
  if (d > 1.2) return 'var(--warning)';   // Modérément diversifié
  return 'var(--danger)';                 // Concentré
}

// Fonction pour Confidence (0-1 ou 0-100)
function getConfidenceColor(conf) {
  if (conf == null || isNaN(conf)) return 'var(--theme-text)';
  const c = Number(conf);
  const pct = c > 1 ? c : c * 100;  // Normaliser sur 0-100
  if (pct > 70) return 'var(--success)';
  if (pct >= 40) return 'var(--warning)';
  return 'var(--danger)';
}
```

## Labels de Niveau Proposés

```javascript
function getScoreLabel(score) {
  if (score == null || isNaN(score)) return 'N/A';
  const s = Number(score);
  if (s > 80) return 'Excellent';
  if (s > 70) return 'Très bon';
  if (s > 60) return 'Bon';
  if (s > 40) return 'Moyen';
  if (s > 20) return 'Faible';
  return 'Très faible';
}
```

## Plan d'Action

1. ✅ Corriger `pickScoreColor` dans `risk-dashboard.html` (ligne 5276) - FAIT
2. ⏳ Corriger textes "Niveau de risque" (ligne 4054-4058)
3. ⏳ Ajouter couleurs Risk Score (ligne 4236)
4. ⏳ Ajouter couleurs Data Confidence (ligne 4138)
5. ⏳ Ajouter couleurs Calmar Ratio (ligne 4211)
6. ⏳ Vérifier/corriger Decision Index dans `analytics-unified.html`
7. ⏳ Styliser panel de gauche (sidebar)
8. ⏳ Tests visuels complets
9. ⏳ Commit avec toutes les corrections

## Principe Canonique

**Tous les scores (0-100) suivent la sémantique POSITIVE :**
- **Plus haut = meilleur** → Vert
- **Moyen** → Orange
- **Plus bas = pire** → Rouge

**Référence:** [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)
