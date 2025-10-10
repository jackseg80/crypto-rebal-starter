import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Test Configuration
 *
 * Tests complets des flux utilisateurs critiques:
 * - Risk Dashboard (4 onglets)
 * - Rebalance (calcul → exécution → historique)
 * - Analytics (ML predictions → insights)
 * - Simulateur (scénarios → résultats)
 */

export default defineConfig({
  testDir: './tests/e2e',

  // Timeout par test (30s pour flux complets)
  timeout: 30000,

  // Tests en parallèle (performance)
  fullyParallel: true,

  // Retry en cas d'échec (flakiness)
  retries: process.env.CI ? 2 : 1,

  // Workers (max parallélisme)
  workers: process.env.CI ? 1 : 3,

  // Reporter (console + HTML)
  reporter: [
    ['list'],
    ['html', { outputFolder: 'tests/e2e-report', open: 'never' }],
    ['json', { outputFile: 'tests/e2e-results.json' }]
  ],

  use: {
    // URL de base (localhost:8000)
    baseURL: 'http://localhost:8000',

    // Traces en cas d'échec (debugging)
    trace: 'on-first-retry',

    // Screenshots en cas d'échec
    screenshot: 'only-on-failure',

    // Videos en cas d'échec
    video: 'retain-on-failure',

    // Viewport par défaut (1280x720)
    viewport: { width: 1280, height: 720 },

    // User-Agent custom (identifiable dans logs)
    userAgent: 'Playwright E2E Test Suite',

    // Timeout pour actions (10s)
    actionTimeout: 10000,

    // Timeout pour navigation (15s)
    navigationTimeout: 15000,
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // User context (multi-tenant testing)
        storageState: undefined, // Fresh context par test
      },
    },

    // Firefox (optionnel, décommenter pour tester)
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },

    // Safari (optionnel, Mac uniquement)
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },

    // Mobile (optionnel, responsive testing)
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
  ],

  // Serveur de dev (géré manuellement)
  // IMPORTANT: Démarrez le serveur backend dans un terminal séparé avant de lancer les tests:
  // python -m uvicorn api.main:app --reload --port 8000
  //
  // webServer: {
  //   command: 'python -m uvicorn api.main:app --port 8000',
  //   url: 'http://localhost:8000',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120000,
  //   stdout: 'ignore',
  //   stderr: 'pipe',
  // },
});
