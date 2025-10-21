/**
 * Stock Market Regime History Chart Modal
 *
 * Displays historical stock market regime detection with:
 * - Timeline chart showing regime transitions
 * - Confidence levels over time
 * - Key market events annotations
 */

// Debug logger
const debugLogger = {
    debug: (...args) => console.log('[StockRegimeHistory]', ...args),
    warn: (...args) => console.warn('[StockRegimeHistory]', ...args),
    error: (...args) => console.error('[StockRegimeHistory]', ...args)
};

// Regime colors matching main dashboard
const REGIME_COLORS = {
    'Bull Market': 'rgb(34, 197, 94)',      // green
    'Bull': 'rgb(34, 197, 94)',
    'Bear Market': 'rgb(220, 38, 38)',      // red
    'Bear': 'rgb(220, 38, 38)',
    'Correction': 'rgb(234, 88, 12)',       // orange
    'Sideways': 'rgb(107, 114, 128)',       // gray
    'Distribution': 'rgb(139, 92, 246)',    // purple
    'Expansion': 'rgb(59, 130, 246)'        // blue
};

let stockHistoryChart = null;
let stockHistoryModal = null;

/**
 * Initialize the Stock Regime History modal
 */
export function initializeStockRegimeHistory() {
    debugLogger.debug('Initializing Stock Regime History...');

    // Check if modal already exists
    if (document.getElementById('stock-regime-history-modal')) {
        debugLogger.debug('Modal already exists');
        return;
    }

    // Create modal HTML
    const modalHTML = `
        <div id="stock-regime-history-modal" class="regime-modal" style="display: none;">
            <div class="regime-modal-overlay" onclick="window.closeStockRegimeHistory()"></div>
            <div class="regime-modal-content" style="max-width: 1200px; width: 90%; max-height: 90vh; overflow-y: auto;">
                <div class="regime-modal-header" style="display: flex; justify-content: space-between; align-items: center; padding: 1.5rem; border-bottom: 1px solid var(--theme-border);">
                    <h2 style="margin: 0; font-size: 1.5rem; color: var(--theme-text);">📈 Stock Market Regime Probabilities</h2>
                    <button onclick="window.closeStockRegimeHistory()" style="background: none; border: none; font-size: 1.5rem; cursor: pointer; color: var(--theme-text-muted); padding: 0; line-height: 1;">&times;</button>
                </div>
                <div class="regime-modal-body" style="padding: 1.5rem;">
                    <div id="stock-regime-history-loading" style="text-align: center; padding: 3rem; color: var(--theme-text-muted);">
                        <p>Loading stock regime probabilities...</p>
                    </div>
                    <div id="stock-regime-history-error" style="display: none; text-align: center; padding: 3rem; color: var(--danger);">
                        <!-- Error message will be inserted here -->
                    </div>
                    <div id="stock-regime-history-chart-container" style="display: none;">
                        <canvas id="stock-regime-history-chart" style="height: 500px; width: 100%;"></canvas>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Add CSS for modal
    if (!document.getElementById('regime-modal-styles')) {
        const styles = `
            <style id="regime-modal-styles">
                .regime-modal {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .regime-modal-overlay {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.6);
                    backdrop-filter: blur(4px);
                }
                .regime-modal-content {
                    position: relative;
                    background: var(--theme-surface);
                    border-radius: var(--radius-lg);
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    z-index: 1;
                }
            </style>
        `;
        document.head.insertAdjacentHTML('beforeend', styles);
    }

    stockHistoryModal = document.getElementById('stock-regime-history-modal');
    debugLogger.debug('Stock Regime History modal initialized');
}

/**
 * Open the Stock Regime History modal and load data
 */
export async function openStockRegimeHistory() {
    debugLogger.debug('Opening Stock Regime History modal...');

    // Initialize modal if not already done
    if (!stockHistoryModal) {
        initializeStockRegimeHistory();
        stockHistoryModal = document.getElementById('stock-regime-history-modal');
    }

    // Show modal
    stockHistoryModal.style.display = 'flex';

    // Load data
    await loadStockRegimeHistory();
}

/**
 * Close the Stock Regime History modal
 */
export function closeStockRegimeHistory() {
    debugLogger.debug('Closing Stock Regime History modal...');
    if (stockHistoryModal) {
        stockHistoryModal.style.display = 'none';
    }
}

/**
 * Load and display stock regime history data
 */
async function loadStockRegimeHistory() {
    debugLogger.debug('Loading stock regime history...');

    const loadingEl = document.getElementById('stock-regime-history-loading');
    const errorEl = document.getElementById('stock-regime-history-error');
    const chartContainer = document.getElementById('stock-regime-history-chart-container');

    // Show loading state
    loadingEl.style.display = 'block';
    errorEl.style.display = 'none';
    chartContainer.style.display = 'none';

    try {
        // Use window.fetchUserConfig if available, otherwise construct endpoint
        let endpoint;
        if (window.fetchUserConfig) {
            const config = await window.fetchUserConfig();
            endpoint = `${config.api_base_url}/api/ml/bourse/regime?benchmark=SPY&lookback_days=365`;
        } else {
            // Fallback: assume localhost:8000
            endpoint = `http://localhost:8000/api/ml/bourse/regime?benchmark=SPY&lookback_days=365`;
        }
        debugLogger.debug('Fetching from:', endpoint);

        const response = await fetch(endpoint);

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        debugLogger.debug('Stock regime data received:', data);

        // Hide loading, show chart
        loadingEl.style.display = 'none';
        chartContainer.style.display = 'block';

        // Render chart
        renderStockRegimeHistoryChart(data);

    } catch (error) {
        debugLogger.error('Failed to load stock regime history:', error);
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.innerHTML = `
            <p><strong>Error loading stock regime history</strong></p>
            <p style="font-size: 0.9rem; color: var(--theme-text-muted);">${error.message}</p>
            <button onclick="window.loadStockRegimeHistory()" class="btn primary" style="margin-top: 1rem;">🔄 Retry</button>
        `;
    }
}

/**
 * Render stock regime history chart
 */
function renderStockRegimeHistoryChart(data) {
    debugLogger.debug('Rendering stock regime probabilities chart...', data);

    const canvas = document.getElementById('stock-regime-history-chart');
    if (!canvas) {
        debugLogger.error('Chart canvas not found');
        return;
    }

    // Destroy existing chart
    if (stockHistoryChart) {
        stockHistoryChart.destroy();
        stockHistoryChart = null;
    }

    const ctx = canvas.getContext('2d');

    // Extract regime probabilities
    const currentRegime = data.current_regime || 'Unknown';
    const confidence = data.confidence ? (data.confidence * 100).toFixed(1) : 'N/A';
    const regimeProbabilities = data.regime_probabilities || {};

    // Prepare chart data
    const labels = Object.keys(regimeProbabilities);
    const values = Object.values(regimeProbabilities).map(v => v * 100);
    const colors = labels.map(regime => REGIME_COLORS[regime] || 'rgb(107, 114, 128)');

    // If no probabilities, show current regime only
    if (labels.length === 0) {
        labels.push(currentRegime);
        values.push(data.confidence * 100);
        colors.push(REGIME_COLORS[currentRegime] || 'rgb(107, 114, 128)');
    }

    stockHistoryChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Regime Probability',
                data: values,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace('rgb', 'rgba').replace(')', ', 1)')),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: `Stock Market Regime Probabilities\nCurrent: ${currentRegime} (${confidence}% confidence)`,
                    font: { size: 16 }
                },
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.parsed.y.toFixed(1) + '% probability';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Probability %'
                    },
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Regime States (HMM Model)'
                    }
                }
            }
        }
    });

    debugLogger.debug('Stock regime probabilities chart rendered');
}

// Export functions to window for onclick handlers
if (typeof window !== 'undefined') {
    window.openStockRegimeHistory = openStockRegimeHistory;
    window.closeStockRegimeHistory = closeStockRegimeHistory;
    window.loadStockRegimeHistory = loadStockRegimeHistory;
}

debugLogger.debug('Stock Regime History module loaded');
