# Tests E2E - Échecs Connus (36/72)

> **État actuel** : 36 tests passés (50%), 36 tests échoués (50%)
> **Date** : Octobre 2025
> **Priorité correction** : Moyenne (tests fonctionnels, mais sélecteurs à ajuster)

---

## 📊 Résumé des Échecs

```
✅ Tests passés    : 36/72 (50%)
❌ Tests échoués   : 36/72 (50%)

Répartition par catégorie:
- Erreurs syntaxe CSS  : 19 tests (53%)
- Timeouts navigation  : 16 tests (44%)
- Erreurs RegExp       :  1 test  (3%)
```

---

## 🔴 Catégorie 1 : Erreurs Syntaxe CSS (19 tests)

### Problème

**Sélecteurs avec guillemets doubles mal échappés** dans les attributs `data-*`.

### Exemples

```javascript
// ❌ MAUVAIS (cause parse error)
page.locator('[data-section="ml"], text=/prediction/i')
page.locator('[data-metric="decision-index"], .decision-index-value')
page.locator('input[value="priority"], [data-mode="priority"]')

// ✅ BON (guillemets simples ou méthode séparée)
page.locator("[data-section='ml']").or(page.getByText(/prediction/i))
page.locator("[data-metric='decision-index']").or(page.locator('.decision-index-value'))
page.locator("[data-mode='priority']").or(page.getByRole('radio', { name: /priority/i }))
```

### Fichiers Affectés

**`analytics.spec.js`** (10 tests) :
- `should display ML status` (line 52)
- `should display volatility predictions` (line 62)
- `should display sentiment scores` (line 86)
- `should display Decision Index value (0-100)` (line 105)
- `should display Trend Chip with Δ7d/Δ30d` (line 144)
- `should fallback to API if store empty` (line 258)
- `should display effective weights (post-adaptive)` (line 303)
- `should load ML predictions in less than 10 seconds` (line 335)
- `should load analytics page successfully` (line 16)
- `should load user context from localStorage` (line 30)

**`rebalance.spec.js`** (3 tests) :
- `should load user portfolio data` (line 31)
- `should toggle between Priority and Proportional modes` (line 107)
- `should link to execution history` (line 335)

**`risk-dashboard.spec.js`** (2 tests) :
- `should load risk dashboard page successfully` (line 15)
- `should select active user from localStorage` (line 36)

**`simulator.spec.js`** (2 tests) :
- `should load simulator page successfully` (line 17)
- `should display 10 presets` (line 31)

**Autres** (2 tests) :
- `rebalance.spec.js`: `should load rebalance page successfully` (line 17)

### Correction

**Rechercher/Remplacer** dans tous les fichiers `tests/e2e/*.spec.js` :

```bash
# Pattern à chercher:
\[data-([^=]+)="([^"]+)"\]

# Remplacer par:
[data-$1='$2']
```

Ou utiliser `.or()` pour séparer les sélecteurs :

```javascript
const element = page.locator("[data-metric='risk-score']")
  .or(page.locator('.risk-score'))
  .or(page.getByText(/risk score/i));
```

---

## ⏱️ Catégorie 2 : Timeouts Navigation (16 tests)

### Problème

**Les onglets du Risk Dashboard ne répondent pas** → Timeout 10s lors des clics.

### Exemples

```javascript
// ❌ ÉCHOUE (onglet non trouvé)
await page.getByRole('tab', { name: /alerts/i }).click();
// TimeoutError: locator.click: Timeout 10000ms exceeded.
```

### Fichiers Affectés

**`risk-dashboard.spec.js`** (16 tests - tous après le `beforeEach()`) :
- `should display active alerts table`
- `should handle empty alerts gracefully`
- `should filter alerts by severity`
- `should display Risk Score metric`
- `should display dual-window metadata`
- `should display V2 shadow mode comparison`
- `should display Bitcoin price chart`
- `should display halving markers`
- `should display on-chain indicators`
- `should display strategy selector`
- `should display current vs target allocations`
- `should generate action plan`
- `should maintain data consistency across tabs`
- `should handle tab switching without errors`
- `should load initial view in less than 5 seconds`
- `should handle rapid tab switching`

### Cause Racine

Le fichier `static/risk-dashboard.html` n'utilise probablement **pas** les attributs ARIA standards :
- `role="tab"` manquant
- `aria-selected` manquant
- Noms d'onglets différents (ex: "Alertes" vs "Alerts")

### Inspection Nécessaire

**Ouvrir** `http://localhost:8080/static/risk-dashboard.html` et inspecter le HTML :

```bash
# Dans la console navigateur (F12)
document.querySelectorAll('[role="tab"]')
# Si retourne 0 → Les onglets n'ont pas role="tab"

# Trouver les vrais sélecteurs
document.querySelectorAll('.tab, [data-tab], .nav-link')
```

### Correction

**Option 1** : Ajouter attributs ARIA dans `risk-dashboard.html` (recommandé)

```html
<!-- Avant -->
<div class="tab" onclick="switchTab('alerts')">Alertes</div>

<!-- Après -->
<div role="tab"
     aria-selected="true"
     class="tab"
     data-tab="alerts"
     onclick="switchTab('alerts')">
  Alertes
</div>
```

**Option 2** : Adapter les tests aux sélecteurs existants

```javascript
// Au lieu de:
await page.getByRole('tab', { name: /alerts/i }).click();

// Utiliser:
await page.locator('.tab[data-tab="alerts"]').click();
// Ou:
await page.locator('.nav-link:has-text("Alertes")').click();
```

---

## ⚠️ Catégorie 3 : Erreur RegExp (1 test)

### Problème

**Flags RegExp invalides** dans le sélecteur.

### Exemple

```javascript
// ❌ MAUVAIS
page.locator('text=/euphorie/i, [data-preset="euphorie"]')
// Error: Invalid flags supplied to RegExp constructor 'i, [data-preset="euphorie"]'

// ✅ BON
page.locator('text=/euphorie/i').first()
// Ou:
page.locator('[data-preset="euphorie"]')
```

### Fichier Affecté

**`simulator.spec.js`** :
- `should select "Euphorie" preset` (line 52)

### Correction

```javascript
// Ligne 55 de simulator.spec.js
// Avant:
const euphoriePreset = page.locator('text=/euphorie/i, [data-preset="euphorie"]').first();

// Après:
const euphoriePreset = page.locator('text=/euphorie/i').first();
```

---

## 🚀 Plan de Correction (Pour Plus Tard)

### Court Terme (1-2h)

1. **Fixer syntaxe CSS** (19 tests) :
   ```bash
   # Rechercher/remplacer dans tests/e2e/*.spec.js
   [data-xxx="yyy"] → [data-xxx='yyy']
   ```

2. **Fixer RegExp** (1 test) :
   - `simulator.spec.js:55` → Supprimer `, [data-preset="euphorie"]`

3. **Relancer tests** :
   ```bash
   npm run test:e2e
   # Objectif: 56/72 tests passés (78%)
   ```

### Moyen Terme (2-4h)

4. **Inspecter Risk Dashboard HTML** :
   - Ouvrir `http://localhost:8080/static/risk-dashboard.html`
   - Copier structure HTML des onglets
   - Noter les vrais sélecteurs (classes, data attributes)

5. **Adapter tests Risk Dashboard** (16 tests) :
   - Remplacer `getByRole('tab')` par sélecteurs réels
   - Augmenter timeout si nécessaire (`timeout: 15000`)

6. **Relancer tests** :
   ```bash
   npm run test:e2e
   # Objectif: 72/72 tests passés (100%)
   ```

### Long Terme (Optionnel)

7. **Améliorer accessibilité** :
   - Ajouter `role="tab"` dans `risk-dashboard.html`
   - Ajouter `aria-selected`, `aria-controls`
   - Rendre tests futurs plus robustes

8. **Ajouter tests multi-browsers** :
   - Décommenter Firefox, Safari dans `playwright.config.js`
   - Tester compatibilité cross-browser

---

## 📝 Commandes Utiles

### Relancer Tests Spécifiques

```bash
# Seulement les tests qui échouent
npx playwright test --grep "should display ML status"

# Seulement Risk Dashboard
npx playwright test risk-dashboard.spec.js

# Mode debug (un test)
npx playwright test risk-dashboard.spec.js:15 --debug
```

### Voir les Échecs

```bash
# Rapport HTML
npm run test:e2e:report

# Traces d'un test échoué
npx playwright show-trace tests/e2e-report/traces/<test-name>.zip
```

### Analyse Rapide

```bash
# Compter succès/échecs
node analyze_failed_tests.cjs
```

---

## ✅ Checklist Validation (Post-Correction)

- [ ] 20 tests syntaxe CSS corrigés
- [ ] 16 tests Risk Dashboard adaptés
- [ ] 1 test RegExp corrigé
- [ ] `npm run test:e2e` → 72/72 passés (100%)
- [ ] Rapport HTML sans erreurs
- [ ] Documentation mise à jour

---

**Auteur** : Claude Code Agent
**Date** : Octobre 2025
**Version** : 1.0.0

**Status** : ⚠️ **36/72 Tests Échoués (Corrections Documentées)**

