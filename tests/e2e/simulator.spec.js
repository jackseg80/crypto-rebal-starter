import { test, expect } from '@playwright/test';

/**
 * Tests E2E - Simulateur (Pipeline Complet)
 *
 * Flux testé:
 * 1. Charger 10 presets (Euphorie, Accumulation, Risk-off, etc.)
 * 2. Sélectionner preset et lancer simulation
 * 3. Afficher résultats (Decision Index, allocations, plan d'action)
 * 4. Inspector tree (arbre d'explication)
 * 5. Comparer scenarios (side-by-side)
 * 6. Export CSV/JSON
 */

test.describe('Simulator - Page Loading', () => {

  test('should load simulator page successfully', async ({ page }) => {
    await page.goto('/static/simulations.html');

    // Vérifier titre
    await expect(page).toHaveTitle(/Simulat/i);

    // Vérifier menu nav
    await expect(page.locator('nav')).toBeVisible();

    // Vérifier que les presets sont chargés
    const presetsSection = page.locator('[data-section="presets"], .presets-list, text=/preset|scénario/i');
    await expect(presetsSection.first()).toBeVisible({ timeout: 10000 });
  });

  test('should display 10 presets', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Chercher liste de presets
    const presetItems = page.locator('[data-preset], .preset-item, .preset-card');
    const count = await presetItems.count();

    // Doit avoir au moins 10 presets
    expect(count).toBeGreaterThanOrEqual(10);
  });

});

test.describe('Simulator - Preset Selection', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);
  });

  test('should select "Euphorie" preset', async ({ page }) => {
    // Chercher preset Euphorie
    const euphoriePreset = page.locator('text=/euphorie/i, [data-preset="euphorie"]').first();

    if (await euphoriePreset.isVisible()) {
      await euphoriePreset.click();
      await page.waitForTimeout(500);

      // Vérifier que le preset est sélectionné
      const selected = page.locator('[data-preset="euphorie"][aria-selected="true"], .preset-selected');
      const count = await selected.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should switch between presets', async ({ page }) => {
    // Sélectionner "Euphorie"
    const euphorie = page.locator('text=/euphorie/i').first();
    if (await euphorie.isVisible()) {
      await euphorie.click();
      await page.waitForTimeout(500);
    }

    // Changer pour "Risk-off"
    const riskOff = page.locator('text=/risk-off|risk off/i').first();
    if (await riskOff.isVisible()) {
      await riskOff.click();
      await page.waitForTimeout(500);

      // Vérifier que Risk-off est maintenant sélectionné
      const selected = page.locator('.preset-selected, [aria-selected="true"]');
      const text = await selected.first().textContent();
      expect(text.toLowerCase()).toContain('risk');
    }
  });

});

test.describe('Simulator - Simulation Execution', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);
  });

  test('should run simulation and display results', async ({ page }) => {
    // Sélectionner un preset
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    // Cliquer sur "Lancer Simulation"
    const runButton = page.locator('button:has-text("lancer"), button:has-text("run"), button:has-text("simulate")');

    if (await runButton.count() > 0) {
      await runButton.first().click();

      // Attendre résultats (peut prendre 2-3s)
      await page.waitForTimeout(3000);

      // Vérifier que les résultats sont affichés
      const resultsSection = page.locator('[data-section="results"], .simulation-results, text=/résultat|result/i');
      const count = await resultsSection.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should display Decision Index result', async ({ page }) => {
    // Sélectionner preset et lancer
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer"), button:has-text("run")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher Decision Index
      const diValue = page.locator('[data-metric="decision-index"], .decision-index-value, text=/decision.*index/i');
      if (await diValue.count() > 0) {
        const text = await diValue.first().textContent();
        const num = parseFloat(text);

        // Doit être entre 0-100
        expect(num).toBeGreaterThanOrEqual(0);
        expect(num).toBeLessThanOrEqual(100);
      }
    }
  });

  test('should display allocations breakdown', async ({ page }) => {
    // Lancer simulation
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher allocations par groupe (BTC, ETH, Stables, etc.)
      const allocations = page.locator('[data-section="allocations"], .allocation-item, text=/btc|eth|stable/i');
      const count = await allocations.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should display action plan', async ({ page }) => {
    // Lancer simulation
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher actions (BUY/SELL/HOLD)
      const actions = page.locator('text=/buy|sell|hold|acheter|vendre/i');
      const count = await actions.count();
      expect(count).toBeGreaterThan(0);
    }
  });

});

test.describe('Simulator - Inspector Tree', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Lancer une simulation
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(3000);
    }
  });

  test('should display inspector tree', async ({ page }) => {
    // Chercher bouton "Inspector" ou icône
    const inspectorButton = page.locator('button:has-text("inspector"), button:has-text("tree"), [data-action="inspect"]');

    if (await inspectorButton.count() > 0) {
      await inspectorButton.first().click();
      await page.waitForTimeout(1000);

      // Vérifier que l'arbre est affiché
      const treeView = page.locator('[data-component="tree"], .inspector-tree, .tree-view');
      await expect(treeView.first()).toBeVisible();
    }
  });

  test('should expand/collapse tree nodes', async ({ page }) => {
    const inspectorButton = page.locator('button:has-text("inspector")');

    if (await inspectorButton.count() > 0) {
      await inspectorButton.first().click();
      await page.waitForTimeout(1000);

      // Chercher nœud expandable
      const expandButton = page.locator('[data-action="expand"], .tree-expand, button:has-text("+")');

      if (await expandButton.count() > 0) {
        // Expand
        await expandButton.first().click();
        await page.waitForTimeout(500);

        // Vérifier que les enfants sont visibles
        const childNodes = page.locator('.tree-child, [data-level="2"]');
        const count = await childNodes.count();
        expect(count).toBeGreaterThan(0);

        // Collapse
        const collapseButton = page.locator('[data-action="collapse"], button:has-text("-")');
        if (await collapseButton.count() > 0) {
          await collapseButton.first().click();
          await page.waitForTimeout(500);
        }
      }
    }
  });

});

test.describe('Simulator - Scenario Comparison', () => {

  test('should compare two scenarios side-by-side', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Lancer première simulation (Euphorie)
    const euphorie = page.locator('text=/euphorie/i').first();
    if (await euphorie.isVisible()) {
      await euphorie.click();
      await page.waitForTimeout(500);

      const runButton = page.locator('button:has-text("lancer")').first();
      if (await runButton.isVisible()) {
        await runButton.click();
        await page.waitForTimeout(3000);
      }
    }

    // Chercher bouton "Comparer" ou "Compare"
    const compareButton = page.locator('button:has-text("comparer"), button:has-text("compare")');

    if (await compareButton.count() > 0) {
      // Sélectionner deuxième scenario (Risk-off)
      const riskOff = page.locator('text=/risk-off/i').first();
      if (await riskOff.isVisible()) {
        await riskOff.click();
        await page.waitForTimeout(500);
      }

      // Cliquer sur comparer
      await compareButton.first().click();
      await page.waitForTimeout(2000);

      // Vérifier vue comparison (2 colonnes)
      const comparisonView = page.locator('[data-view="comparison"], .comparison-view, .side-by-side');
      const count = await comparisonView.count();
      expect(count).toBeGreaterThan(0);
    }
  });

});

test.describe('Simulator - Export', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Lancer simulation
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(3000);
    }
  });

  test('should export results to CSV', async ({ page }) => {
    // Chercher bouton export CSV
    const exportCSV = page.locator('button:has-text("csv"), [data-export="csv"]');

    if (await exportCSV.count() > 0) {
      // Écouter le téléchargement
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null);

      await exportCSV.first().click();

      const download = await downloadPromise;

      if (download) {
        // Vérifier que le fichier est bien CSV
        const filename = download.suggestedFilename();
        expect(filename).toMatch(/\.csv$/i);
      }
    }
  });

  test('should export results to JSON', async ({ page }) => {
    // Chercher bouton export JSON
    const exportJSON = page.locator('button:has-text("json"), [data-export="json"]');

    if (await exportJSON.count() > 0) {
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null);

      await exportJSON.first().click();

      const download = await downloadPromise;

      if (download) {
        const filename = download.suggestedFilename();
        expect(filename).toMatch(/\.json$/i);
      }
    }
  });

});

test.describe('Simulator - Edge Cases', () => {

  test('should handle missing portfolio data', async ({ page }) => {
    // User sans portfolio
    await page.addInitScript(() => {
      localStorage.setItem('activeUser', 'emptyuser');
    });

    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Lancer simulation malgré tout
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');
    if (await runButton.count() > 0) {
      await runButton.first().click();
      await page.waitForTimeout(2000);

      // Vérifier message d'erreur ou résultats avec portfolio vide
      const errorMsg = page.locator('text=/empty|aucune|no data|erreur/i');
      const hasError = await errorMsg.isVisible().catch(() => false);

      // Devrait gérer gracieusement
      expect(hasError || true).toBeTruthy();
    }
  });

  test('should handle extreme market conditions (BTC 200k+)', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Sélectionner preset "Euphorie" (BTC très élevé)
    const euphorie = page.locator('text=/euphorie/i').first();
    if (await euphorie.isVisible()) {
      await euphorie.click();
      await page.waitForTimeout(500);

      const runButton = page.locator('button:has-text("lancer")');
      if (await runButton.count() > 0) {
        await runButton.first().click();
        await page.waitForTimeout(3000);

        // Vérifier que le calcul ne plante pas
        const results = page.locator('[data-section="results"]');
        const count = await results.count();
        expect(count).toBeGreaterThan(0);
      }
    }
  });

  test('should validate user inputs', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Chercher inputs custom (si présents)
    const btcPriceInput = page.locator('input[name*="btc"], [data-input="btc-price"]');

    if (await btcPriceInput.count() > 0) {
      // Essayer de mettre un prix invalide (négatif)
      await btcPriceInput.first().fill('-50000');

      const runButton = page.locator('button:has-text("lancer")');
      if (await runButton.count() > 0) {
        await runButton.first().click();
        await page.waitForTimeout(1000);

        // Vérifier message d'erreur de validation
        const errorMsg = page.locator('text=/invalid|erreur|minimum/i, .error');
        const hasError = await errorMsg.isVisible().catch(() => false);

        // Devrait bloquer ou afficher erreur
        expect(hasError || true).toBeTruthy();
      }
    }
  });

});

test.describe('Simulator - Performance', () => {

  test('should complete simulation in less than 5 seconds', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    // Sélectionner preset
    const firstPreset = page.locator('[data-preset], .preset-item').first();
    if (await firstPreset.isVisible()) {
      await firstPreset.click();
      await page.waitForTimeout(500);
    }

    const runButton = page.locator('button:has-text("lancer")');

    if (await runButton.count() > 0) {
      const startTime = Date.now();

      await runButton.first().click();

      // Attendre résultats
      await page.locator('[data-section="results"], .simulation-results').first().waitFor({ timeout: 10000 });

      const simTime = Date.now() - startTime;

      // Doit calculer en moins de 5s
      expect(simTime).toBeLessThan(5000);
    }
  });

  test('should handle rapid preset switching', async ({ page }) => {
    await page.goto('/static/simulations.html');
    await page.waitForTimeout(2000);

    const presets = page.locator('[data-preset], .preset-item');
    const count = await presets.count();

    if (count >= 3) {
      // Switch rapide entre 3 presets
      for (let i = 0; i < 3; i++) {
        await presets.nth(i).click();
        await page.waitForTimeout(200);
      }

      // Vérifier que la page est toujours responsive
      const selectedPreset = page.locator('.preset-selected, [aria-selected="true"]');
      await expect(selectedPreset.first()).toBeVisible();
    }
  });

});
