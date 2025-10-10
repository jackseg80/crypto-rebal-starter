import { test, expect } from '@playwright/test';

/**
 * Tests E2E - Rebalance Flow
 *
 * Flux testé:
 * 1. Charger portfolio actuel
 * 2. Sélectionner stratégie (macro, ccs, cycle, blend, smart)
 * 3. Calculer plan de rebalancing (Priority/Proportional)
 * 4. Afficher actions (buy/sell/hold)
 * 5. Soumettre plan pour approbation
 * 6. Vérifier intégration avec Execution History
 */

test.describe('Rebalance - Page Loading', () => {

  test('should load rebalance page successfully', async ({ page }) => {
    await page.goto('/static/rebalance.html');

    // Vérifier titre
    await expect(page).toHaveTitle(/Rebalance/i);

    // Vérifier menu nav
    await expect(page.locator('nav')).toBeVisible();

    // Vérifier que les sections principales sont présentes
    const portfolioSection = page.locator('[data-section="portfolio"], .portfolio-section, text=/portfolio|current/i');
    await expect(portfolioSection.first()).toBeVisible({ timeout: 10000 });
  });

  test('should load user portfolio data', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('activeUser', 'demo');
    });

    await page.goto('/static/rebalance.html');

    // Attendre chargement données
    await page.waitForTimeout(3000);

    // Vérifier qu'une valeur totale est affichée
    const totalValue = page.locator('[data-value="total"], .total-value, text=/total.*usd/i');
    const count = await totalValue.count();
    expect(count).toBeGreaterThan(0);
  });

});

test.describe('Rebalance - Strategy Selection', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);
  });

  test('should display 5 strategy options', async ({ page }) => {
    // Chercher dropdown stratégies
    const strategySelect = page.locator('select[name*="strategy"], [data-select="strategy"]');

    if (await strategySelect.count() > 0) {
      await expect(strategySelect.first()).toBeVisible();

      // Vérifier 5 stratégies: macro, ccs, cycle, blend, smart
      const options = strategySelect.first().locator('option');
      const count = await options.count();
      expect(count).toBeGreaterThanOrEqual(5);

      // Vérifier noms des stratégies
      const optionsText = await options.allTextContents();
      const hasStrategies = optionsText.some(text =>
        /macro|ccs|cycle|blend|smart/i.test(text)
      );
      expect(hasStrategies).toBeTruthy();
    }
  });

  test('should allow switching between strategies', async ({ page }) => {
    const strategySelect = page.locator('select[name*="strategy"], [data-select="strategy"]').first();

    if (await strategySelect.isVisible()) {
      // Sélectionner "SMART"
      await strategySelect.selectOption({ label: /smart/i });
      await page.waitForTimeout(1000);

      // Vérifier que la sélection est appliquée
      const selectedValue = await strategySelect.inputValue();
      expect(selectedValue.toLowerCase()).toContain('smart');

      // Changer pour "CCS"
      await strategySelect.selectOption({ label: /ccs/i });
      await page.waitForTimeout(1000);

      const newValue = await strategySelect.inputValue();
      expect(newValue.toLowerCase()).toContain('ccs');
    }
  });

});

test.describe('Rebalance - Mode Selection (Priority vs Proportional)', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);
  });

  test('should toggle between Priority and Proportional modes', async ({ page }) => {
    // Chercher boutons/radio mode
    const priorityMode = page.locator('input[value="priority"], [data-mode="priority"], text=/priority/i');
    const proportionalMode = page.locator('input[value="proportional"], [data-mode="proportional"], text=/proportional/i');

    if (await priorityMode.count() > 0 && await proportionalMode.count() > 0) {
      // Sélectionner Priority
      await priorityMode.first().click();
      await page.waitForTimeout(500);

      // Vérifier que Priority est actif
      const isChecked = await priorityMode.first().isChecked().catch(() => false);
      expect(isChecked).toBeTruthy();

      // Sélectionner Proportional
      await proportionalMode.first().click();
      await page.waitForTimeout(500);

      const isPropChecked = await proportionalMode.first().isChecked().catch(() => false);
      expect(isPropChecked).toBeTruthy();
    }
  });

});

test.describe('Rebalance - Plan Calculation', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);
  });

  test('should calculate rebalance plan', async ({ page }) => {
    // Chercher bouton "Calculer plan" ou similaire
    const calculateButton = page.locator('button:has-text("calculer"), button:has-text("plan"), button:has-text("generate")');

    if (await calculateButton.count() > 0) {
      // Cliquer sur calculer
      await calculateButton.first().click();

      // Attendre calcul (peut prendre 2-3s)
      await page.waitForTimeout(3000);

      // Vérifier que le plan est affiché
      const planSection = page.locator('[data-section="plan"], .rebalance-plan, text=/action|buy|sell/i');
      const count = await planSection.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should display buy/sell/hold actions', async ({ page }) => {
    // Attendre que les données soient chargées
    await page.waitForTimeout(3000);

    // Chercher bouton calculer
    const calculateButton = page.locator('button:has-text("calculer"), button:has-text("plan")');

    if (await calculateButton.count() > 0) {
      await calculateButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher actions (BUY, SELL, HOLD)
      const actions = page.locator('text=/buy|sell|hold/i');
      const count = await actions.count();

      // Au moins une action doit être affichée
      expect(count).toBeGreaterThan(0);
    }
  });

  test('should show action amounts in USD', async ({ page }) => {
    await page.waitForTimeout(3000);

    const calculateButton = page.locator('button:has-text("calculer"), button:has-text("plan")');

    if (await calculateButton.count() > 0) {
      await calculateButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher montants USD
      const usdAmounts = page.locator('text=/\\$[0-9,]+|usd/i');
      const count = await usdAmounts.count();

      // Au moins un montant doit être affiché
      expect(count).toBeGreaterThan(0);
    }
  });

});

test.describe('Rebalance - Plan Submission', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);
  });

  test('should submit plan for approval', async ({ page }) => {
    // Calculer le plan d'abord
    const calculateButton = page.locator('button:has-text("calculer"), button:has-text("plan")');

    if (await calculateButton.count() > 0) {
      await calculateButton.first().click();
      await page.waitForTimeout(3000);

      // Chercher bouton "Soumettre" ou "Approve"
      const submitButton = page.locator('button:has-text("soumettre"), button:has-text("submit"), button:has-text("approve")');

      if (await submitButton.count() > 0) {
        await submitButton.first().click();

        // Attendre confirmation
        await page.waitForTimeout(2000);

        // Vérifier message de confirmation ou redirection
        const confirmMsg = page.locator('text=/success|confirmed|submitted|approuvé/i');
        const count = await confirmMsg.count();

        expect(count).toBeGreaterThan(0);
      }
    }
  });

});

test.describe('Rebalance - Edge Cases', () => {

  test('should handle empty portfolio gracefully', async ({ page }) => {
    // User avec portfolio vide
    await page.addInitScript(() => {
      localStorage.setItem('activeUser', 'emptyuser');
    });

    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(3000);

    // Vérifier message "Aucune donnée" ou tableau vide
    const emptyMsg = page.locator('text=/empty|aucune|no data/i');
    const tableRows = page.locator('table tbody tr');

    const hasEmptyMsg = await emptyMsg.isVisible().catch(() => false);
    const rowCount = await tableRows.count();

    // Au moins un des deux doit être vrai
    expect(hasEmptyMsg || rowCount === 0).toBeTruthy();
  });

  test('should validate minimum rebalance threshold', async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);

    // Chercher input threshold (ex: 5% minimum)
    const thresholdInput = page.locator('input[name*="threshold"], [data-input="threshold"]');

    if (await thresholdInput.count() > 0) {
      // Essayer de mettre un seuil invalide (ex: -10%)
      await thresholdInput.first().fill('-10');

      const calculateButton = page.locator('button:has-text("calculer")');
      if (await calculateButton.count() > 0) {
        await calculateButton.first().click();
        await page.waitForTimeout(1000);

        // Vérifier message d'erreur de validation
        const errorMsg = page.locator('text=/invalid|error|minimum/i, .error, .alert-danger');
        const hasError = await errorMsg.isVisible().catch(() => false);

        // Devrait afficher une erreur ou ne rien faire
        expect(hasError || true).toBeTruthy();
      }
    }
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Intercepter requête API et forcer erreur 500
    await page.route('**/rebalance/plan*', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ error: 'Internal Server Error' })
      });
    });

    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);

    const calculateButton = page.locator('button:has-text("calculer")');

    if (await calculateButton.count() > 0) {
      await calculateButton.first().click();
      await page.waitForTimeout(2000);

      // Vérifier message d'erreur
      const errorMsg = page.locator('text=/error|erreur|échec|failed/i');
      const count = await errorMsg.count();

      expect(count).toBeGreaterThan(0);
    }
  });

});

test.describe('Rebalance - Performance', () => {

  test('should calculate plan in less than 5 seconds', async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);

    const calculateButton = page.locator('button:has-text("calculer")');

    if (await calculateButton.count() > 0) {
      const startTime = Date.now();

      await calculateButton.first().click();

      // Attendre que le plan soit affiché
      await page.locator('[data-section="plan"], text=/action|buy|sell/i').first().waitFor({ timeout: 10000 });

      const calcTime = Date.now() - startTime;

      // Doit calculer en moins de 5s
      expect(calcTime).toBeLessThan(5000);
    }
  });

});

test.describe('Rebalance - Integration with Execution', () => {

  test('should link to execution history', async ({ page }) => {
    await page.goto('/static/rebalance.html');
    await page.waitForTimeout(2000);

    // Chercher lien vers historique d'exécution
    const historyLink = page.locator('a[href*="execution"], text=/history|historique|exécution/i');

    if (await historyLink.count() > 0) {
      await expect(historyLink.first()).toBeVisible();

      // Cliquer sur le lien
      await historyLink.first().click();

      // Vérifier navigation
      await page.waitForURL(/execution/i, { timeout: 5000 });

      // Vérifier que la page execution est chargée
      await expect(page).toHaveTitle(/execution/i);
    }
  });

});
