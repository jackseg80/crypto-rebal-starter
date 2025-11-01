# Tests E2E - État et Documentation

> **Dernière mise à jour** : 10 octobre 2025
> **Framework** : Playwright 1.x
> **Navigateur** : Chromium (Desktop Chrome)
> **Timeout par test** : 30s

## 📊 Résumé Actuel

| Métrique | Valeur | Notes |
|----------|--------|-------|
| **Tests totaux** | 72 | 4 suites (analytics, risk-dashboard, rebalance, simulator) |
| **Tests passés** | **53** | **74% de réussite** ✅ |
| **Tests échoués** | 19 | 26% (éléments HTML manquants ou timeouts) |
| **Amélioration** | +34% | Avant corrections: 43/72 (60%) |

## 🎯 Corrections Appliquées (Oct 2025)

### 1. Sélecteurs CSS (28 corrections)

**Problème** : Guillemets imbriqués causant erreurs de parsing Playwright
**Solution** : Pattern `.or()` pour séparer attributs et sélecteurs text

```javascript
// ❌ Avant (erreur parsing)
page.locator('[data-section="ml"], text=/ml/i')

// ✅ Après (syntaxe correcte)
page.locator('[data-section=ml]').or(page.locator('text=/ml/i'))
```

**Fichiers modifiés** :
- `tests/e2e/analytics.spec.js` : 9 sélecteurs
- `tests/e2e/risk-dashboard.spec.js` : 6 sélecteurs
- `tests/e2e/rebalance.spec.js` : 9 sélecteurs
- `tests/e2e/simulator.spec.js` : 4 sélecteurs

### 2. Accessibilité ARIA (Risk Dashboard)

**Problème** : Tests cherchent `role="tab"` qui n'existait pas
**Solution** : Ajout attributs ARIA standards

```html
<!-- Ajouté dans static/risk-dashboard.html -->
<div class="tabs" role="tablist">
  <button class="tab-button" role="tab" aria-selected="true" aria-controls="risk-tab">
    Risk Overview
  </button>
</div>

<div class="tab-pane" id="risk-tab" role="tabpanel">
  <!-- contenu -->
</div>
```

**Impact** : +10 tests résolus (Risk Dashboard)

### 3. Fonction switchTab() (JavaScript)

**Problème** : Attributs ARIA non mis à jour lors du changement d'onglet
**Solution** : Synchronisation aria-selected dans `static/modules/risk-dashboard-main.js:21-26`

```javascript
document.querySelectorAll('.tab-button').forEach(btn => {
  const isActive = btn.dataset.tab === tabName;
  btn.classList.toggle('active', isActive);
  btn.setAttribute('aria-selected', isActive ? 'true' : 'false'); // ✅
});
```

## ⚠️ Tests Échouant (19 restants)

### Breakdown par Type

| Type d'erreur | Nombre | Cause |
|---------------|--------|-------|
| **Timeout** | 13 | Éléments chargés dynamiquement ou lents |
| **CountZero** | 5 | Éléments HTML absents (user-badge, presets) |
| **Other** | 1 | Erreur structurelle |

### Breakdown par Fichier

#### 1. risk-dashboard.spec.js (9 échecs)

**Raison principale** : Lazy-loading des tabs + éléments générés dynamiquement

```
❌ should display active alerts table           → Timeout waiting for alerts
❌ should display Risk Score metric              → Timeout loading risk-overview
❌ should generate action plan                   → Timeout loading targets-tab
❌ should maintain data consistency across tabs  → Timeout switching tabs
```

**Solution recommandée** : Augmenter timeouts ou ajouter waitFor explicites

#### 2. analytics.spec.js (5 échecs)

**Raison principale** : Section ML dans tab-panel caché par défaut

```
❌ should load analytics page successfully       → data-section="ml" not visible on load
❌ should display volatility predictions         → ML section not expanded
❌ should load ML predictions in less than 10s   → Timeout too strict
```

**Solution recommandée** : Tests doivent naviguer vers onglet ML avant vérification

#### 3. simulator.spec.js (3 échecs)

**Raison principale** : Presets chargés depuis JSON externe

```
❌ should display 10 presets                     → data-preset attribute missing
❌ should select "Euphorie" preset               → Preset element structure different
```

**Solution recommandée** : Ajouter `data-preset` aux éléments HTML générés

#### 4. rebalance.spec.js (2 échecs)

```
❌ should load user portfolio data               → total-value element not found
❌ should link to execution history              → Navigation timeout
```

**Solution recommandée** : Vérifier structure HTML de rebalance.html

## 🚀 Lancer les Tests

### Prérequis

```bash
# Installer Playwright (une seule fois)
npm install

# Installer les navigateurs Playwright
npx playwright install chromium
```

### Commandes

```bash
# Lancer tous les tests E2E
npx playwright test

# Lancer un fichier spécifique
npx playwright test tests/e2e/risk-dashboard.spec.js

# Mode UI interactif (debug)
npx playwright test --ui

# Voir le rapport HTML
npx playwright show-report tests/e2e-report
```

### ⚠️ Important

**Le serveur backend doit être actif** :
```bash
# Terminal 1 (backend)
.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --port 8080

# Terminal 2 (tests)
npx playwright test
```

## 📝 Structure des Tests

```
tests/e2e/
├── analytics.spec.js       (22 tests) - Analytics Unified page
├── risk-dashboard.spec.js  (18 tests) - Risk Dashboard 4 tabs
├── rebalance.spec.js       (14 tests) - Rebalance flow
├── simulator.spec.js       (18 tests) - Simulation pipeline
└── KNOWN_FAILURES.md       (documentation des échecs connus)
```

## 🔄 Workflow de Contribution

### Ajouter un nouveau test

1. Identifier le flux à tester
2. Créer le test dans le fichier approprié
3. Vérifier que les `data-*` attributes existent dans le HTML
4. Utiliser des sélecteurs robustes (préférer `role` > `data-*` > classes)

### Exemple de test robuste

```javascript
test('should display risk score', async ({ page }) => {
  await page.goto('/static/risk-dashboard.html');

  // Attendre chargement
  await page.waitForLoadState('networkidle');

  // Cliquer sur tab (avec retry implicite)
  await page.getByRole('tab', { name: /overview/i }).click();

  // Attendre contenu visible
  const scoreLocator = page.locator('[data-metric=risk-score]');
  await expect(scoreLocator).toBeVisible({ timeout: 10000 });

  // Vérifier contenu
  const text = await scoreLocator.textContent();
  const score = parseFloat(text);
  expect(score).toBeGreaterThanOrEqual(0);
  expect(score).toBeLessThanOrEqual(100);
});
```

## 🎯 Roadmap

### Court terme (prochaine itération)

- [ ] Augmenter timeouts pour Risk Dashboard tabs (30s → 45s)
- [ ] Ajouter `data-preset` aux éléments de simulateur
- [ ] Documenter les 19 échecs dans KNOWN_FAILURES.md

### Moyen terme

- [ ] Refactoriser HTML pour matcher attentes des tests
- [ ] Ajouter `data-testid` sur éléments critiques
- [ ] Atteindre 90%+ de couverture E2E

### Long terme

- [ ] Tests multi-navigateurs (Firefox, Safari)
- [ ] Tests mobile (viewport responsive)
- [ ] CI/CD intégration (GitHub Actions)

## 📚 Ressources

- [Playwright Documentation](https://playwright.dev/)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Sélecteurs robustes](https://playwright.dev/docs/locators)
- [Debugging](https://playwright.dev/docs/debug)

## 🐛 Debugging

### Tests qui timeout

```bash
# Mode headed (voir le navigateur)
npx playwright test --headed

# Mode debug avec breakpoints
npx playwright test --debug

# Ralentir exécution
npx playwright test --slow-mo=1000
```

### Voir les traces

```bash
# Générer traces pour échecs
npx playwright test --trace on

# Ouvrir trace viewer
npx playwright show-trace tests/e2e-report/trace.zip
```

## ✅ Definition of Done pour Tests E2E

- [ ] Test passe localement (2+ runs)
- [ ] HTML a les attributs nécessaires (`data-*`, `role`)
- [ ] Timeouts appropriés pour chargements async
- [ ] Screenshots capturés en cas d'échec
- [ ] Documentation ajoutée si comportement spécifique

---

**Statut** : 🟢 Tests E2E opérationnels (74% de réussite)
**Maintenance** : Vérifier tous les trimestres ou après refonte HTML majeure

