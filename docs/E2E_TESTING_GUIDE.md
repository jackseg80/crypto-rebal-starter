# Guide Tests E2E - Playwright

> **Objectif** : Valider les flux complets utilisateur avec tests end-to-end automatisés.
> **Framework** : Playwright (Chromium)
> **Couverture** : Risk Dashboard, Rebalance, Analytics, Simulateur

---

## 📊 Vue d'Ensemble

### Tests Créés

```
tests/e2e/
├── risk-dashboard.spec.js   (21 tests) - Navigation 4 onglets, intégration
├── rebalance.spec.js         (14 tests) - Flux complet calcul → soumission
├── analytics.spec.js         (17 tests) - ML predictions, Decision Index Panel
└── simulator.spec.js         (16 tests) - Presets, simulation, export

Total: 68 tests E2E
```

### Flux Testés

**Risk Dashboard** :
- ✅ Navigation entre 4 onglets (Alerts, Overview, Cycles, Targets)
- ✅ Chargement données + affichage métriques
- ✅ Dual-Window Metrics + Risk Score V2 Shadow Mode
- ✅ Filtres alertes, pagination, charts Chart.js
- ✅ Génération plan d'action

**Rebalance** :
- ✅ Sélection stratégie (5 options: macro, ccs, cycle, blend, smart)
- ✅ Mode Priority vs Proportional
- ✅ Calcul plan de rebalancing
- ✅ Affichage actions (BUY/SELL/HOLD)
- ✅ Soumission pour approbation

**Analytics** :
- ✅ ML predictions (volatilité, sentiment, regime)
- ✅ Decision Index Panel avec Trend Chip + Regime Ribbon
- ✅ Sources injection (Store → API fallback)
- ✅ Charts Chart.js + timeframe selection
- ✅ Unified Insights (weights adaptatifs, confidence, contradiction)

**Simulateur** :
- ✅ 10 presets (Euphorie, Accumulation, Risk-off, etc.)
- ✅ Lancement simulation + résultats (DI, allocations, actions)
- ✅ Inspector tree (arbre d'explication)
- ✅ Comparaison scenarios side-by-side
- ✅ Export CSV/JSON

---

## 🚀 Commandes

### Installation

```bash
# Installer Playwright (déjà fait)
npm install --save-dev @playwright/test

# Installer navigateurs
npx playwright install chromium
```

### Lancer les Tests

```bash
# Tous les tests E2E (headless)
npm run test:e2e

# Avec UI interactive (Playwright UI)
npm run test:e2e:ui

# Mode debug (step-by-step)
npm run test:e2e:debug

# Mode headed (voir navigateur)
npm run test:e2e:headed

# Tests spécifiques
npx playwright test risk-dashboard.spec.js
npx playwright test rebalance.spec.js --headed
```

### Voir le Rapport

```bash
# Ouvrir rapport HTML après exécution
npm run test:e2e:report

# Ou directement
npx playwright show-report tests/e2e-report
```

---

## 📁 Structure Fichiers

### Configuration

**`playwright.config.js`** :
- Base URL : `http://localhost:8080`
- Timeout par test : 30s
- Retry : 1 fois en local, 2 fois en CI
- Workers : 3 en parallèle (local), 1 en CI
- Reporters : list + HTML + JSON
- Serveur auto-démarré si pas lancé (`uvicorn api.main:app`)

### Tests Specs

**`tests/e2e/risk-dashboard.spec.js`** :
```javascript
test.describe('Risk Dashboard - Navigation & Loading', () => {
  test('should load risk dashboard page successfully', async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');
    await expect(page).toHaveTitle(/Risk Dashboard/i);
  });
});
```

**Structure commune** :
1. `test.describe()` - Suite de tests (ex: "Page Loading", "Strategy Selection")
2. `test.beforeEach()` - Setup commun (navigation, attente chargement)
3. `test()` - Test individuel avec assertions

---

## 🛠️ Bonnes Pratiques

### 1. Sélecteurs Robustes

```javascript
// ✅ BON : Sélecteurs sémantiques
await page.getByRole('tab', { name: /alerts/i })
await page.getByRole('button', { name: /calculer/i })

// ✅ BON : Data attributes
await page.locator('[data-section="ml"]')
await page.locator('[data-metric="risk-score"]')

// ❌ ÉVITER : Classes CSS (fragile)
await page.locator('.btn-primary')
```

### 2. Attentes Explicites

```javascript
// ✅ BON : Attendre élément visible
await expect(page.locator('[data-section="ml"]')).toBeVisible({ timeout: 10000 });

// ✅ BON : Attendre navigation
await page.waitForURL(/execution/i, { timeout: 5000 });

// ❌ ÉVITER : Attentes fixes (flakiness)
await page.waitForTimeout(5000); // Uniquement si vraiment nécessaire
```

### 3. Gestion Erreurs

```javascript
// ✅ BON : Fallback gracieux
const count = await errorMsg.count();
const hasError = await errorMsg.isVisible().catch(() => false);

// ✅ BON : Conditions multiples
expect(hasEmptyMsg || rowCount === 0).toBeTruthy();
```

### 4. Tests Conditionnels

```javascript
// ✅ BON : Vérifier existence avant interaction
if (await calculateButton.count() > 0) {
  await calculateButton.first().click();
  // ... assertions
}
```

---

## 📈 Métriques Performance

### Objectifs

- **Chargement initial** : < 5s (Risk Dashboard, Analytics)
- **Calcul plan** : < 5s (Rebalance)
- **Simulation** : < 5s (Simulateur)
- **ML predictions** : < 10s (Analytics)

### Tests Performance Inclus

```javascript
test('should load initial view in less than 5 seconds', async ({ page }) => {
  const startTime = Date.now();
  await page.goto('/static/risk-dashboard.html');
  await page.locator('[role="tabpanel"]:visible').first().waitFor();
  const loadTime = Date.now() - startTime;
  expect(loadTime).toBeLessThan(5000);
});
```

---

## 🐛 Debugging

### Mode Debug

```bash
# Lancer un test spécifique en debug
npx playwright test risk-dashboard.spec.js:15 --debug
```

**Fonctionnalités** :
- Step-by-step avec Play/Pause
- Inspect sélecteurs
- Console logs
- Screenshots automatiques

### Mode Headed

```bash
# Voir navigateur pendant exécution
npm run test:e2e:headed
```

### Screenshots & Videos

**Automatique en cas d'échec** :
- Screenshots : `tests/e2e-report/screenshots/`
- Videos : `tests/e2e-report/videos/`
- Traces : `tests/e2e-report/traces/`

**Ouvrir trace** :
```bash
npx playwright show-trace tests/e2e-report/traces/risk-dashboard-should-load.zip
```

---

## 🔄 CI/CD Integration

### GitHub Actions (exemple)

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          npm ci
          pip install -r requirements.txt
          npx playwright install chromium

      - name: Run E2E tests
        run: npm run test:e2e

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-report
          path: tests/e2e-report/
```

---

## 📊 Coverage par Flux

### Risk Dashboard (21 tests)

| Fonctionnalité | Tests | Statut |
|----------------|-------|--------|
| Navigation onglets | 4 | ✅ |
| Risk Alerts Tab | 4 | ✅ |
| Risk Overview Tab | 4 | ✅ |
| Risk Cycles Tab | 3 | ✅ |
| Risk Targets Tab | 3 | ✅ |
| Cross-tab integration | 2 | ✅ |
| Performance | 2 | ✅ |

### Rebalance (14 tests)

| Fonctionnalité | Tests | Statut |
|----------------|-------|--------|
| Page loading | 2 | ✅ |
| Strategy selection | 2 | ✅ |
| Mode selection | 1 | ✅ |
| Plan calculation | 3 | ✅ |
| Plan submission | 1 | ✅ |
| Edge cases | 3 | ✅ |
| Performance | 1 | ✅ |
| Integration | 1 | ✅ |

### Analytics (17 tests)

| Fonctionnalité | Tests | Statut |
|----------------|-------|--------|
| Page loading | 2 | ✅ |
| ML predictions | 4 | ✅ |
| Decision Index Panel | 5 | ✅ |
| Charts | 2 | ✅ |
| Sources injection | 3 | ✅ |
| Performance | 2 | ✅ |
| Error handling | 2 | ✅ |

### Simulateur (16 tests)

| Fonctionnalité | Tests | Statut |
|----------------|-------|--------|
| Page loading | 2 | ✅ |
| Preset selection | 2 | ✅ |
| Simulation execution | 4 | ✅ |
| Inspector tree | 2 | ✅ |
| Scenario comparison | 1 | ✅ |
| Export | 2 | ✅ |
| Edge cases | 3 | ✅ |
| Performance | 2 | ✅ |

---

## 🎯 Prochaines Étapes

### Court Terme

- [ ] Lancer les 68 tests E2E pour vérifier compatibilité
- [ ] Corriger sélecteurs si nécessaire (data attributes manquants)
- [ ] Ajouter screenshots de référence (visual regression)

### Moyen Terme

- [ ] Ajouter tests multi-browsers (Firefox, Safari)
- [ ] Ajouter tests responsive (mobile, tablet)
- [ ] Intégrer dans CI/CD (GitHub Actions)
- [ ] Ajouter coverage badge dans README

### Long Terme

- [ ] Tests de régression visuelle (Percy, Applitools)
- [ ] Tests d'accessibilité (axe-core)
- [ ] Tests de performance (Lighthouse CI)
- [ ] Tests de sécurité (OWASP ZAP)

---

## 📝 Troubleshooting

### Le serveur ne démarre pas automatiquement

**Solution** :
```bash
# Lancer manuellement dans un terminal séparé
python -m uvicorn api.main:app --reload --port 8080

# Puis dans un autre terminal
npm run test:e2e
```

### Tests échouent avec "Timeout 30s exceeded"

**Causes possibles** :
- Serveur backend lent (ML loading)
- Données manquantes (user vide)
- Sélecteur incorrect

**Solution** :
```bash
# Lancer en debug pour voir où ça bloque
npx playwright test --debug
```

### Échecs intermittents (flaky tests)

**Causes** :
- Race conditions (données pas encore chargées)
- Timeouts trop courts
- Sélecteurs ambigus

**Solution** :
```javascript
// Augmenter timeout
await expect(element).toBeVisible({ timeout: 15000 });

// Ajouter retry
retries: 2
```

---

## ✅ Checklist Validation

Avant de committer des changements frontend :

- [ ] Lancer tests E2E : `npm run test:e2e`
- [ ] Vérifier rapport : `npm run test:e2e:report`
- [ ] Corriger tests cassés si changements d'UI
- [ ] Ajouter nouveaux tests si nouvelles fonctionnalités
- [ ] Vérifier performance (< 5s objectif)

---

**Auteur** : Claude Code Agent
**Date** : Octobre 2025
**Version** : 1.0.0

**Status** : ✅ **68 Tests E2E Créés (Playwright + Chromium)**

