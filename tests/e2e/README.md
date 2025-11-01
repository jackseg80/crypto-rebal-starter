# Tests E2E - Playwright

Tests end-to-end automatisés pour valider les flux complets utilisateur.

---

## 🚀 Quick Start

### Lancer Tous les Tests

```bash
npm run test:e2e
```

### Lancer un Fichier Spécifique

```bash
# Risk Dashboard (21 tests)
npx playwright test risk-dashboard.spec.js

# Rebalance (14 tests)
npx playwright test rebalance.spec.js

# Analytics (17 tests)
npx playwright test analytics.spec.js

# Simulateur (16 tests)
npx playwright test simulator.spec.js
```

### Mode Interactif

```bash
# UI Playwright (recommandé pour debugging)
npm run test:e2e:ui

# Mode debug (step-by-step)
npm run test:e2e:debug

# Voir navigateur pendant exécution
npm run test:e2e:headed
```

---

## 📊 Tests Disponibles

### `risk-dashboard.spec.js` (21 tests)

**Flux testé** : Navigation 4 onglets, métriques, dual-window, V2 shadow mode

**Sections** :
- Navigation & Loading (2 tests)
- Risk Alerts Tab (4 tests)
- Risk Overview Tab (4 tests)
- Risk Cycles Tab (3 tests)
- Risk Targets Tab (3 tests)
- Cross-Tab Integration (2 tests)
- Performance (2 tests)

**Commande** :
```bash
npx playwright test risk-dashboard.spec.js --headed
```

---

### `rebalance.spec.js` (14 tests)

**Flux testé** : Stratégie → Mode → Calcul → Actions → Soumission

**Sections** :
- Page Loading (2 tests)
- Strategy Selection (2 tests)
- Mode Selection (1 test)
- Plan Calculation (3 tests)
- Plan Submission (1 test)
- Edge Cases (3 tests)
- Performance (1 test)
- Integration (1 test)

**Commande** :
```bash
npx playwright test rebalance.spec.js --headed
```

---

### `analytics.spec.js` (17 tests)

**Flux testé** : ML predictions → Decision Index → Charts → Sources fallback

**Sections** :
- Page Loading (2 tests)
- ML Predictions (4 tests)
- Decision Index Panel (5 tests)
- Charts (2 tests)
- Sources Injection & Fallback (3 tests)
- Performance (2 tests)
- Error Handling (2 tests)

**Commande** :
```bash
npx playwright test analytics.spec.js --headed
```

---

### `simulator.spec.js` (16 tests)

**Flux testé** : Presets → Simulation → Résultats → Inspector → Export

**Sections** :
- Page Loading (2 tests)
- Preset Selection (2 tests)
- Simulation Execution (4 tests)
- Inspector Tree (2 tests)
- Scenario Comparison (1 test)
- Export (2 tests)
- Edge Cases (3 tests)
- Performance (2 tests)

**Commande** :
```bash
npx playwright test simulator.spec.js --headed
```

---

## 🛠️ Configuration

**Fichier** : `playwright.config.js` (racine du projet)

**Paramètres clés** :
- **Base URL** : `http://localhost:8080`
- **Timeout** : 30s par test
- **Retry** : 1 fois (local), 2 fois (CI)
- **Workers** : 3 en parallèle
- **Serveur** : Démarré automatiquement si pas lancé

**Reporters** :
- Console (list)
- HTML (`tests/e2e-report/index.html`)
- JSON (`tests/e2e-results.json`)

---

## 📈 Voir les Résultats

### Rapport HTML

```bash
npm run test:e2e:report
```

**Contenu** :
- Liste des tests (pass/fail)
- Durées d'exécution
- Screenshots des échecs
- Traces interactives

### Traces Interactives

```bash
# Ouvrir trace d'un test échoué
npx playwright show-trace tests/e2e-report/traces/<test-name>.zip
```

**Fonctionnalités** :
- Timeline étape par étape
- DOM snapshots à chaque action
- Network requests
- Console logs

---

## 🐛 Debugging

### Test Spécifique en Debug

```bash
# Lancer un test avec ligne spécifique
npx playwright test risk-dashboard.spec.js:15 --debug
```

### Mode Headed (Voir Navigateur)

```bash
npm run test:e2e:headed
```

### Traces Automatiques

En cas d'échec, Playwright sauvegarde automatiquement :
- **Screenshot** : `tests/e2e-report/screenshots/`
- **Video** : `tests/e2e-report/videos/`
- **Trace** : `tests/e2e-report/traces/`

---

## ✅ Checklist Avant Commit

1. **Lancer tests** :
   ```bash
   npm run test:e2e
   ```

2. **Vérifier rapport** :
   ```bash
   npm run test:e2e:report
   ```

3. **Corriger échecs** (si changements d'UI)

4. **Ajouter nouveaux tests** (si nouvelles features)

---

## 📖 Documentation Complète

Voir [`docs/E2E_TESTING_GUIDE.md`](../../docs/E2E_TESTING_GUIDE.md) pour :
- Bonnes pratiques
- Métriques performance
- CI/CD integration
- Troubleshooting
- Coverage détaillé

---

**Total Tests** : 68 tests E2E
**Framework** : Playwright v1.56
**Navigateur** : Chromium
**Status** : ✅ Prêt à l'emploi

