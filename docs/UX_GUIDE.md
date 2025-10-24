# UX Guide - Visualisations & Conventions UI

## Date
2025-09-30

## Vue d'ensemble

Ce guide définit les conventions UI/UX pour les visualisations du Cockpit Patrimoine Cross-Asset, en particulier pour le **Decision Index** et les **contributions relatives** des piliers.

---

## Visualisation du Decision Index

### 1. Barre Empilée (Contributions Relatives)

**Objectif** : Afficher la contribution relative de chaque pilier (Cycle, Onchain, Risk) au Decision Index total.

**Formule correcte** :
```javascript
const total = wCycle * scoreCycle + wOnchain * scoreOnchain + wRisk * scoreRisk;

const contribCycle = (wCycle * scoreCycle) / total;
const contribOnchain = (wOnchain * scoreOnchain) / total;
const contribRisk = (wRisk * scoreRisk) / total;
```

**⚠️ IMPORTANT — Sémantique Risk** :

> **⚠️ Règle Canonique — Sémantique Risk**
>
> Le **Risk Score** est un indicateur **positif** de robustesse, borné **[0..100]**.
>
> **Convention** : Plus haut = plus robuste (risque perçu plus faible).
>
> **Conséquence** : Dans le Decision Index (DI), Risk contribue **positivement** :
> ```
> DI = wCycle·scoreCycle + wOnchain·scoreOnchain + wRisk·scoreRisk
> ```
>
> **❌ Interdit** : Ne jamais inverser avec `100 - scoreRisk`.
>
> **Visualisation** : Contribution = `(poids × score) / Σ(poids × score)`
>
> 📖 Source : [RISK_SEMANTICS.md](RISK_SEMANTICS.md)

**Exemple visuel** :
```
┌────────────────────────────────────────────┐
│ Cycle (55%)  │ Onchain (30%) │ Risk (15%) │  ← Contributions relatives
└────────────────────────────────────────────┘
  Vert          Bleu            Orange
```

### 2. Badges & Métadonnées

**Badges affichés** :
- **Confiance** : Niveau de confiance composite (0..100)
- **Contradiction** : Indice de contradiction entre piliers (0..100)
- **Cap** : Pourcentage de cap d'exécution (0..100)
- **Mode** : Mode de fonctionnement (Live, Shadow, Simulation)

**⚠️ Important** :
- Les badges **influencent les poids** via la politique d'adaptation
- Les badges **n'influencent PAS les scores bruts** (cycle, onchain, risk)

**Exemple badge** :
```
Source • Updated 14:32:15 • Contrad 40% • Cap 12% • Overrides 2
```

### 3. Code de Couleurs

**Piliers Decision Index** :
- **Cycle** : Vert (`#4ade80`, `--color-cycle`)
- **Onchain** : Bleu (`#3b82f6`, `--color-onchain`)
- **Risk** : Orange (`#fb923c`, `--color-risk`)

**Niveaux d'alerte** :
- **Vert** : Score ≥ 70 (favorable)
- **Jaune** : Score 50-69 (neutre)
- **Orange** : Score 30-49 (attention)
- **Rouge** : Score < 30 (alerte)

---

## Visualisation des Poids Adaptatifs

### Affichage des Poids

**Objectif** : Montrer les poids post-adaptatifs utilisés dans le calcul du DI.

**Format recommandé** :
```
Poids Adaptatifs (Σ = 100%)
┌─────────────────────────────────┐
│ Cycle:   65% (boost cycle ≥ 90) │
│ Onchain: 25% (pénalité contrad) │
│ Risk:    10%                     │
└─────────────────────────────────┘
```

**⚠️ Ne pas transformer** :
- Afficher les poids **tels quels** (pas de `100 - wRisk`)
- Toujours vérifier que Σ(poids) = 100%
- Ajouter des infobulles pour expliquer les ajustements (boost, pénalité)

### Indicateurs de Boost/Pénalité

**Boost Cycle** :
- Cycle ≥ 90 → Badge "Boost Cycle (65%)" en vert
- Cycle ≥ 70 → Badge "Boost Cycle (55%)" en vert clair

**Pénalité Contradiction** :
- Contradiction ≥ 50% → Badge "Pénalité Contrad (-10%)" en orange
- Afficher les poids affectés : Onchain et Risk

**Exemple** :
```html
<div class="weight-badge boost">
  🚀 Boost Cycle (65%)
</div>
<div class="weight-badge penalty">
  ⚠️ Pénalité Contrad (Onchain -10%, Risk -10%)
</div>
```

---

## Composants UI

### 1. Decision Index Panel (`decision-index-panel.js`)

**Responsabilités** :
- Afficher le Decision Index total (0..100)
- Visualiser les contributions relatives en barre empilée
- Afficher les poids adaptatifs
- Afficher les badges (Confiance, Contradiction, Cap, Mode)

**⚠️ Erreurs à éviter** :
- ❌ Inverser Risk : `100 - scoreRisk`
- ❌ Transformer les poids : `1 - wRisk`
- ❌ Oublier de normaliser les poids (Σ ≠ 1.0)

### 2. Governance Panel (`GovernancePanel.js`)

**Responsabilités** :
- Afficher l'état de la gouvernance (decisions, caps, overrides)
- Synchroniser avec `static/core/risk-dashboard-store.js`
- Afficher le cap d'exécution dynamique

**Source unique cap** : `selectCapPercent(state)` (voir `static/selectors/governance.js`)

### 3. ML Status Badge (`shared-ml-functions.js`)

**Source unifiée ML** : `getUnifiedMLStatus()`

**Priorité** :
1. Governance Engine (`/execution/governance/signals`)
2. ML Status API (`/api/ml/status`)
3. Stable Data (fallback basé sur temps)

**Affichage** :
```
[ML Status] Source • Updated HH:MM:SS • Contrad XX% • Cap YY% • Overrides N
```

---

## Interactions Utilisateur

### 1. Changement de Source (Simulateur)

**Workflow** :
1. Utilisateur sélectionne un preset (ex: "Altseason Peak")
2. Simulateur applique les scores (cycle=95, onchain=85, risk=70)
3. Poids adaptatifs recalculés (boost cycle ≥ 90 → wCycle=65%)
4. DI recalculé avec nouveaux poids
5. UI mise à jour (barre empilée, poids, badges)

**Feedback temps réel** :
- Afficher "Calcul en cours..." pendant le recalcul
- Animer la transition de la barre empilée
- Highlighter les changements de poids (boost/pénalité)

### 2. Changement d'Utilisateur

**Workflow** :
1. Utilisateur sélectionne un user dans le dropdown (ex: "jack")
2. `localStorage.setItem('activeUser', 'jack')`
3. Purge des caches
4. Reload de la page
5. Toutes les données sont isolées par `user_id`

**Indicateur visuel** :
```html
<div class="user-badge">
  👤 Active User: jack
</div>
```

---

## Responsive Design

### Breakpoints Standards (Oct 2025)

| Breakpoint | Width | Layout | Use case |
|------------|-------|--------|----------|
| **XL** | ≥ 2000px | 4+ columns, padding augmenté | Ultra-wide monitors |
| **Large** | 1400px - 1999px | 3-4 columns | Modern desktops |
| **Desktop** | 1024px - 1399px | 2-3 columns | Standard desktops |
| **Tablet** | 768px - 1023px | 1-2 columns | Tablets |
| **Mobile** | < 768px | 1 column | Phones |

### Règles Critiques

#### ❌ À ÉVITER

```css
/* NE JAMAIS fixer une largeur max arbitraire */
.container {
  max-width: 1200px;  /* ❌ Limite l'espace sur grands écrans */
}
```

#### ✅ À FAIRE

```css
/* Full responsive avec padding adaptatif */
.container {
  width: 100%;
  max-width: none;  /* Utilise tout l'espace disponible */
  padding: 1rem 2rem;
}

@media (min-width: 2000px) {
  .container {
    padding: 1rem 4rem;  /* Plus d'espace sur XL screens */
  }
}

@media (max-width: 768px) {
  .container {
    padding: 1rem;  /* Moins d'espace sur mobile */
  }
}
```

#### Grid Auto-Fit

```css
/* S'adapte automatiquement au nombre de colonnes */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1.5rem;
}
```

### Layout par Device

#### Desktop (≥ 1024px)

- Barre empilée horizontale
- Poids affichés en colonnes
- Badges en ligne
- **Full width** (pas de max-width)

#### Tablet (768px - 1023px)

- Barre empilée horizontale (plus petite)
- Poids en 2 colonnes
- Badges empilés

#### Mobile (< 768px)

- Barre empilée verticale
- Poids en liste verticale
- Badges en liste verticale
- Texte condensé
- Padding réduit

---

## Accessibilité

### Contraste

- Ratio contraste minimum : 4.5:1 (WCAG AA)
- Utiliser `--color-text` et `--color-bg` depuis `shared-theme.css`

### Labels ARIA

```html
<div role="progressbar"
     aria-label="Decision Index: 78"
     aria-valuenow="78"
     aria-valuemin="0"
     aria-valuemax="100">
</div>
```

### Tooltips

- Expliquer la sémantique Risk : "Plus haut = mieux (portfolio plus robuste)"
- Expliquer les poids adaptatifs : "Cycle boosté à 65% (≥90)"
- Expliquer les pénalités : "Onchain réduit de 10% (contradiction élevée)"

---

## Références

- [docs/index.md — Sémantique de Risk](index.md#sémantique-de-risk-pilier-du-decision-index)
- [docs/architecture.md — Pilier Risk](architecture.md#pilier-risk-sémantique-et-propagation)
- [docs/UNIFIED_INSIGHTS_V2.md](UNIFIED_INSIGHTS_V2.md)
- [docs/SIMULATION_ENGINE_ALIGNMENT.md](SIMULATION_ENGINE_ALIGNMENT.md)
- [static/components/decision-index-panel.js](../static/components/decision-index-panel.js)
