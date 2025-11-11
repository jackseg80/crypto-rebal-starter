/**
 * Bitcoin Cycle Chart Lazy Loading Component
 * Handles lazy loading of Chart.js and rendering Bitcoin cycle charts
 */

class BitcoinCycleChart {
  constructor(element) {
    debugLogger.debug('🔧 BitcoinCycleChart constructor called with element:', element);
    this.element = element;
    this.chartLoaded = false;
    this.placeholder = element.querySelector('.chart-lazy-placeholder');
    this.canvas = element.querySelector('#bitcoin-cycle-chart');
    debugLogger.debug('🔍 Placeholder found:', !!this.placeholder, 'Canvas found:', !!this.canvas);
  }

  async init() {
    debugLogger.debug('🚀 BitcoinCycleChart init() called');

    // Guard: prevent re-initialization using DOM attribute (more robust than instance property)
    if (this.element.dataset.chartInitialized === 'true') {
      debugLogger.debug('⚡ Chart already initialized (DOM guard), skipping re-initialization');
      return;
    }

    // Also check instance property as secondary guard
    if (this.chartLoaded) {
      debugLogger.debug('⚡ Chart already loaded (instance guard), skipping re-initialization');
      return;
    }

    try {
      // Afficher un indicateur de chargement
      if (this.placeholder) {
        debugLogger.debug('✅ Showing loading indicator');
        this.placeholder.innerHTML = `
          <div style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">📊</div>
            <div>Chargement de Chart.js...</div>
            <div class="lazy-loading" style="margin-top: 1rem;"></div>
          </div>
        `;
      } else {
        debugLogger.warn('⚠️ No placeholder found for loading indicator');
      }

      // Charger Chart.js de manière asynchrone
      debugLogger.debug('📊 Starting to load Chart.js...');
      await this.loadChartJS();
      debugLogger.debug('✅ Chart.js loaded successfully');

      // Masquer le placeholder et afficher le canvas
      debugLogger.debug('🔄 Switching from placeholder to canvas...');
      if (this.placeholder) {
        this.placeholder.style.display = 'none';
        debugLogger.debug('✅ Placeholder hidden');
      }
      if (this.canvas) {
        this.canvas.style.display = 'block';
        debugLogger.debug('✅ Canvas shown');
      } else {
        debugLogger.warn('⚠️ No canvas found to show');
      }

      // Créer le graphique Bitcoin Cycle
      if (typeof createBitcoinCycleChart === 'function') {
        debugLogger.debug('📊 Calling createBitcoinCycleChart...');
        await createBitcoinCycleChart('bitcoin-cycle-chart');
        debugLogger.debug('✅ createBitcoinCycleChart completed');
      } else {
        debugLogger.error('❌ createBitcoinCycleChart function not found');
      }

      this.chartLoaded = true;
      // Mark as initialized in DOM to prevent re-initialization from other instances
      this.element.dataset.chartInitialized = 'true';
      debugLogger.debug('✅ Bitcoin Cycle Chart loaded successfully via lazy loading');

    } catch (error) {
      debugLogger.error('❌ Failed to lazy load Bitcoin Cycle Chart:', error);

      // Afficher l'erreur dans le placeholder
      if (this.placeholder) {
        this.placeholder.innerHTML = `
          <div style="text-align: center; color: var(--theme-error, #dc3545);">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">⚠️</div>
            <div>Erreur lors du chargement du graphique</div>
            <div style="font-size: 0.8rem; margin-top: 0.5rem;">${error.message}</div>
          </div>
        `;
      }
    }
  }

  async loadChartJS() {
    // Vérifier si Chart.js est déjà chargé
    if (window.Chart) {
      debugLogger.debug('📊 Chart.js already loaded');
      return Promise.resolve();
    }

    debugLogger.debug('📊 Loading Chart.js...');

    // Charger Chart.js principal
    const chartPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load Chart.js'));
      document.head.appendChild(script);
    });

    await chartPromise;

    // Charger l'adaptateur de dates
    const adapterPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Failed to load Chart.js date adapter'));
      document.head.appendChild(script);
    });

    await adapterPromise;

    // Petit délai pour s'assurer que Chart.js est disponible
    await new Promise(resolve => setTimeout(resolve, 100));

    if (!window.Chart) {
      throw new Error('Chart.js failed to initialize');
    }

    debugLogger.debug('✅ Chart.js loaded successfully');
  }
}

// Enregistrer le composant globalement pour le lazy loader
window.BitcoinCycleChart = BitcoinCycleChart;

// Export for ES modules
export default BitcoinCycleChart;
