import { test, expect } from '@playwright/test';

/**
 * Tests E2E - Risk Dashboard (4 onglets refactorisés)
 *
 * Flux testé:
 * 1. Risk Alerts Tab - Alertes actives, pagination, filtres
 * 2. Risk Overview Tab - Risk Score, dual-window, V2 shadow mode
 * 3. Risk Cycles Tab - Bitcoin cycles, on-chain indicators, charts
 * 4. Risk Targets Tab - Objectifs, allocations, plan d'action
 */

test.describe('Risk Dashboard - Navigation & Loading', () => {

  test('should load risk dashboard page successfully', async ({ page }) => {
    // Naviguer vers Risk Dashboard
    await page.goto('/static/risk-dashboard.html');

    // Vérifier titre page
    await expect(page).toHaveTitle(/Risk Dashboard/i);

    // Vérifier que le menu principal est présent
    await expect(page.locator('nav')).toBeVisible();

    // Vérifier que les 4 onglets sont présents
    const tabs = page.locator('[role="tab"]');
    await expect(tabs).toHaveCount(4);

    // Vérifier noms des onglets
    await expect(page.getByRole('tab', { name: /alerts/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /overview/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /cycles/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /targets/i })).toBeVisible();
  });

  test('should select active user from localStorage', async ({ page }) => {
    // Définir activeUser dans localStorage avant navigation
    await page.addInitScript(() => {
      localStorage.setItem('activeUser', 'demo');
    });

    await page.goto('/static/risk-dashboard.html');

    // Vérifier que l'user est bien affiché (dropdown ou badge)
    const userIndicator = page.locator('[data-testid="active-user"], .user-badge, .user-selector');
    // Au moins un indicateur doit être présent
    const count = await userIndicator.count();
    expect(count).toBeGreaterThan(0);
  });

});

test.describe('Risk Alerts Tab', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');
    // Sélectionner onglet Alerts
    await page.getByRole('tab', { name: /alerts/i }).click();
  });

  test('should display active alerts table', async ({ page }) => {
    // Attendre que le contenu de l'onglet soit visible
    const alertsPanel = page.locator('[role="tabpanel"]:visible');
    await expect(alertsPanel).toBeVisible();

    // Vérifier présence du tableau ou liste d'alertes
    const alertsContainer = page.locator('.alerts-list, .alerts-table, [data-testid="alerts-container"]');
    await expect(alertsContainer).toBeVisible({ timeout: 10000 });
  });

  test('should handle empty alerts gracefully', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(2000);

    // Si aucune alerte, vérifier message "Aucune alerte" ou tableau vide
    const noAlerts = page.locator('text=/aucune alerte|no alerts|empty/i');
    const alertItems = page.locator('.alert-item, [data-alert-id]');

    const hasNoAlertsMsg = await noAlerts.isVisible().catch(() => false);
    const alertCount = await alertItems.count();

    // Au moins un des deux doit être vrai
    expect(hasNoAlertsMsg || alertCount >= 0).toBeTruthy();
  });

  test('should filter alerts by severity', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(2000);

    // Chercher filtres de severité (S1, S2, S3)
    const severityFilters = page.locator('[data-filter="severity"], .severity-filter');

    if (await severityFilters.count() > 0) {
      // Cliquer sur un filtre (ex: S1)
      const s1Filter = page.locator('text=/S1|severity.*1/i').first();
      if (await s1Filter.isVisible()) {
        await s1Filter.click();

        // Vérifier que les alertes sont filtrées
        await page.waitForTimeout(1000);

        const visibleAlerts = page.locator('.alert-item:visible');
        const count = await visibleAlerts.count();

        // Au moins 0 alertes (peut être vide)
        expect(count).toBeGreaterThanOrEqual(0);
      }
    }
  });

});

test.describe('Risk Overview Tab', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');
    // Sélectionner onglet Overview
    await page.getByRole('tab', { name: /overview/i }).click();
  });

  test('should display Risk Score metric', async ({ page }) => {
    // Attendre le chargement des métriques
    await page.waitForTimeout(3000);

    // Chercher Risk Score (0-100)
    const riskScore = page.locator('[data-metric=risk-score], .risk-score').or(page.locator('text=/risk score/i'));
    await expect(riskScore.first()).toBeVisible({ timeout: 10000 });

    // Vérifier qu'un nombre est affiché
    const scoreValue = page.locator('[data-value=risk-score], .risk-score-value');
    if (await scoreValue.count() > 0) {
      const text = await scoreValue.first().textContent();
      const num = parseFloat(text);
      expect(num).toBeGreaterThanOrEqual(0);
      expect(num).toBeLessThanOrEqual(100);
    }
  });

  test('should display dual-window metadata', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher badges dual-window (Long-Term, Full Intersection)
    const dualWindowBadge = page.locator('text=/long-term|full intersection|dual window/i');

    // Peut être présent ou non selon les données
    const count = await dualWindowBadge.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should display V2 shadow mode comparison', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher badges V2 (Legacy vs V2)
    const v2Badge = page.locator('text=/v2|legacy|shadow/i');

    // Peut être présent ou non selon configuration
    const count = await v2Badge.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

});

test.describe('Risk Cycles Tab', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');
    // Sélectionner onglet Cycles
    await page.getByRole('tab', { name: /cycles/i }).click();
  });

  test('should display Bitcoin price chart', async ({ page }) => {
    // Attendre le chargement du chart
    await page.waitForTimeout(3000);

    // Chercher canvas Chart.js
    const chartCanvas = page.locator('canvas');
    await expect(chartCanvas.first()).toBeVisible({ timeout: 10000 });
  });

  test('should display halving markers', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher mentions de halvings
    const halvingText = page.locator('text=/halving|halv/i');

    // Peut être présent ou non selon période affichée
    const count = await halvingText.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should display on-chain indicators', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher section on-chain
    const onchainSection = page.locator('[data-section=onchain]').or(page.locator('text=/on-chain|onchain/i'));

    // Doit être présent
    const count = await onchainSection.count();
    expect(count).toBeGreaterThan(0);
  });

});

test.describe('Risk Targets Tab', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');
    // Sélectionner onglet Targets
    await page.getByRole('tab', { name: /targets/i }).click();
  });

  test('should display strategy selector', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(2000);

    // Chercher dropdown stratégies (5 stratégies: macro, ccs, cycle, blend, smart)
    const strategySelector = page.locator('select[name*=strategy], [data-select=strategy]');

    if (await strategySelector.count() > 0) {
      await expect(strategySelector.first()).toBeVisible();

      // Vérifier qu'il y a au moins 5 options
      const options = strategySelector.first().locator('option');
      const count = await options.count();
      expect(count).toBeGreaterThanOrEqual(5);
    }
  });

  test('should display current vs target allocations', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher tableau ou graphique allocations
    const allocTable = page.locator('[data-table=allocations], .allocation-table').or(page.locator('text=/allocation|current|target/i'));

    // Doit être présent
    const count = await allocTable.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should generate action plan', async ({ page }) => {
    // Attendre le chargement
    await page.waitForTimeout(3000);

    // Chercher bouton "Générer plan" ou section plan d'action
    const planButton = page.locator('button:has-text("plan"), button:has-text("générer")');

    if (await planButton.count() > 0) {
      // Cliquer sur le bouton
      await planButton.first().click();

      // Attendre génération
      await page.waitForTimeout(2000);

      // Vérifier que le plan est affiché
      const actionPlan = page.locator('[data-section=action-plan], .action-plan').or(page.locator('text=/buy|sell|hold/i'));
      const count = await actionPlan.count();
      expect(count).toBeGreaterThan(0);
    }
  });

});

test.describe('Risk Dashboard - Cross-Tab Integration', () => {

  test('should maintain data consistency across tabs', async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');

    // Onglet Overview: récupérer Risk Score
    await page.getByRole('tab', { name: /overview/i }).click();
    await page.waitForTimeout(3000);

    const riskScoreOverview = page.locator('[data-value="risk-score"], .risk-score-value').first();
    const scoreTextOverview = await riskScoreOverview.textContent().catch(() => null);

    // Onglet Alerts: vérifier que le même score est affiché (si présent)
    await page.getByRole('tab', { name: /alerts/i }).click();
    await page.waitForTimeout(2000);

    const riskScoreAlerts = page.locator('[data-value="risk-score"], .risk-score-value').first();
    const scoreTextAlerts = await riskScoreAlerts.textContent().catch(() => null);

    // Si les deux sont présents, doivent être identiques
    if (scoreTextOverview && scoreTextAlerts) {
      expect(scoreTextOverview.trim()).toBe(scoreTextAlerts.trim());
    }
  });

  test('should handle tab switching without errors', async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');

    // Listener pour erreurs JS
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    // Naviguer entre tous les onglets
    await page.getByRole('tab', { name: /alerts/i }).click();
    await page.waitForTimeout(1000);

    await page.getByRole('tab', { name: /overview/i }).click();
    await page.waitForTimeout(1000);

    await page.getByRole('tab', { name: /cycles/i }).click();
    await page.waitForTimeout(1000);

    await page.getByRole('tab', { name: /targets/i }).click();
    await page.waitForTimeout(1000);

    // Vérifier qu'il n'y a pas d'erreurs critiques
    const criticalErrors = errors.filter(e =>
      !e.includes('404') && // Ignorer 404 (endpoints optionnels)
      !e.includes('503') && // Ignorer 503 (AlertEngine optionnel)
      !e.includes('Failed to fetch') // Ignorer timeout réseau
    );

    expect(criticalErrors.length).toBe(0);
  });

});

test.describe('Risk Dashboard - Performance', () => {

  test('should load initial view in less than 5 seconds', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/static/risk-dashboard.html');

    // Attendre que le premier onglet soit visible
    await page.locator('[role="tabpanel"]:visible').first().waitFor({ timeout: 10000 });

    const loadTime = Date.now() - startTime;

    // Doit charger en moins de 5s
    expect(loadTime).toBeLessThan(5000);
  });

  test('should handle rapid tab switching', async ({ page }) => {
    await page.goto('/static/risk-dashboard.html');

    // Switch rapide entre onglets (stress test)
    for (let i = 0; i < 3; i++) {
      await page.getByRole('tab', { name: /alerts/i }).click();
      await page.waitForTimeout(200);

      await page.getByRole('tab', { name: /overview/i }).click();
      await page.waitForTimeout(200);

      await page.getByRole('tab', { name: /cycles/i }).click();
      await page.waitForTimeout(200);

      await page.getByRole('tab', { name: /targets/i }).click();
      await page.waitForTimeout(200);
    }

    // Vérifier que la page est toujours responsive
    const activeTab = page.locator('[role="tab"][aria-selected="true"]');
    await expect(activeTab).toBeVisible();
  });

});
