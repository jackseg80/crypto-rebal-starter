/**
 * Bitcoin Regime Detection Chart Module
 *
 * Displays historical Bitcoin regime timeline with:
 * - Price chart with regime color bands
 * - Event annotations (Mt.Gox, FTX, COVID, ATHs)
 * - Timeframe selector (1Y/2Y/5Y/10Y)
 * - Current regime summary cards
 *
 * Uses /api/ml/crypto/regime and /api/ml/crypto/regime-history
 */

console.log('[BTC Regime] Module loaded');

const BTC_REGIME_CONFIG = {
    regimeColors: {
        'Bear Market': { bg: 'rgba(220, 38, 38, 0.2)', border: '#dc2626', label: 'Bear' },
        'Correction': { bg: 'rgba(234, 88, 12, 0.2)', border: '#ea580c', label: 'Correction' },
        'Bull Market': { bg: 'rgba(34, 197, 94, 0.2)', border: '#22c55e', label: 'Bull' },
        'Expansion': { bg: 'rgba(59, 130, 246, 0.2)', border: '#3b82f6', label: 'Expansion' },
        'Insufficient Data': { bg: 'rgba(156, 163, 175, 0.2)', border: '#9ca3af', label: 'N/A' },
        'Unknown': { bg: 'rgba(107, 114, 128, 0.2)', border: '#6b7280', label: 'Unknown' }
    },
    eventColors: {
        'crisis': '#ef4444',
        'bottom': '#10b981',
        'peak': '#8b5cf6',
        'policy': '#06b6d4'
    },
    defaultTimeframe: 365 // 1 year
};

let btcRegimeChart = null;
let btcRegimeData = null;

/**
 * Initialize Bitcoin Regime Chart
 * @param {string} containerId - Container div ID
 */
export async function initializeBTCRegimeChart(containerId) {
    console.log('[BTC Regime] Initializing chart with containerId:', containerId);

    const container = document.getElementById(containerId);
    if (!container) {
        console.error(`[BTC Regime] Container #${containerId} not found`);
        return;
    }

    console.log('[BTC Regime] Container found:', container);

    // Setup timeframe selector
    setupTimeframeSelector(container);

    // Load initial data (1 year)
    console.log('[BTC Regime] Loading initial data (365 days)');
    await loadBTCRegimeData(BTC_REGIME_CONFIG.defaultTimeframe);
}

/**
 * Setup timeframe selector buttons
 */
function setupTimeframeSelector(container) {
    const selector = container.querySelector('.btc-regime-timeframe-selector');
    if (!selector) return;

    const buttons = selector.querySelectorAll('button');
    buttons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const days = parseInt(e.target.dataset.days);

            // Update active state
            buttons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');

            // Load new data
            await loadBTCRegimeData(days);
        });
    });
}

/**
 * Load Bitcoin regime data from API
 * @param {number} lookbackDays - Number of days to fetch
 */
async function loadBTCRegimeData(lookbackDays) {
    try {
        console.log(`[BTC Regime] Loading data for ${lookbackDays} days`);

        // Show loading state
        showLoadingState();

        // Fetch current regime
        const url = `/api/ml/crypto/regime?symbol=BTC&lookback_days=${lookbackDays}`;
        console.log(`[BTC Regime] Fetching current regime from: ${url}`);
        const currentRegimeResponse = await fetch(url);
        const currentRegimeResult = await currentRegimeResponse.json();

        console.log('[BTC Regime] Current regime response:', currentRegimeResult);

        if (!currentRegimeResult.ok) {
            throw new Error(currentRegimeResult.error || 'Failed to fetch current regime');
        }

        const currentRegime = currentRegimeResult.data;

        // Fetch historical timeline
        const historyResponse = await fetch(`/api/ml/crypto/regime-history?symbol=BTC&lookback_days=${lookbackDays}`);
        const historyResult = await historyResponse.json();

        if (!historyResult.ok) {
            throw new Error(historyResult.error || 'Failed to fetch regime history');
        }

        btcRegimeData = {
            current: currentRegime,
            history: historyResult.data
        };

        // Update UI
        updateCurrentRegimeSummary(currentRegime);
        createTimelineChart(historyResult.data);

        console.log(`[BTC Regime] Loaded ${historyResult.data.dates?.length || 0} days of history`);

    } catch (error) {
        console.error('[BTC Regime] Error loading data:', error);
        showErrorState(error.message);
    }
}

/**
 * Update current regime summary cards
 */
function updateCurrentRegimeSummary(currentRegime) {
    // Update regime name
    const regimeNameEl = document.getElementById('btc-current-regime-name');
    if (regimeNameEl) {
        regimeNameEl.textContent = currentRegime.current_regime || 'Unknown';
        regimeNameEl.className = `regime-chip ${getRegimeClass(currentRegime.current_regime)}`;
    }

    // Update confidence
    const confidenceEl = document.getElementById('btc-current-regime-confidence');
    if (confidenceEl) {
        const confidence = (currentRegime.confidence * 100).toFixed(1);
        confidenceEl.textContent = `${confidence}%`;
    }

    // Update detection method
    const methodEl = document.getElementById('btc-current-regime-method');
    if (methodEl) {
        const method = currentRegime.detection_method === 'rule_based' ? 'Rule-Based' : 'HMM';
        methodEl.textContent = method;
        methodEl.className = `detection-method ${currentRegime.detection_method}`;
    }

    // Update rule reason (if available)
    const reasonCard = document.getElementById('btc-regime-reason-card');
    const reasonEl = document.getElementById('btc-current-regime-reason');
    if (reasonCard && reasonEl && currentRegime.rule_reason) {
        reasonEl.textContent = currentRegime.rule_reason;
        reasonCard.style.display = 'block';
    } else if (reasonCard) {
        reasonCard.style.display = 'none';
    }

    // Update regime probabilities chart
    if (currentRegime.regime_probabilities) {
        createProbabilitiesChart(currentRegime.regime_probabilities);
    }
}

/**
 * Create timeline chart with Chart.js
 */
function createTimelineChart(historyData) {
    const canvas = document.getElementById('btc-regime-timeline-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (btcRegimeChart) {
        btcRegimeChart.destroy();
    }

    // Prepare data
    const dates = historyData.dates || [];
    const prices = historyData.prices || [];
    const regimes = historyData.regimes || [];
    const events = historyData.events || [];

    // Create regime segments for background colors
    const regimeSegments = createRegimeSegments(dates, regimes);

    // Create chart
    btcRegimeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                // Price line
                {
                    label: 'Bitcoin Price (USD)',
                    data: prices,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 5
                },
                // Regime background bands (as separate datasets)
                ...regimeSegments
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                title: {
                    display: true,
                    text: `Bitcoin Regime Detection (${historyData.period_days} days)`,
                    font: { size: 16, weight: 'bold' }
                },
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        filter: (item) => {
                            // Only show price and regime labels, not individual segments
                            return item.text.includes('Price') || item.text.includes('Market') || item.text.includes('Correction') || item.text.includes('Expansion');
                        },
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        title: (context) => {
                            return context[0].label;
                        },
                        label: (context) => {
                            if (context.datasetIndex === 0) {
                                // Price dataset
                                return `Price: $${context.parsed.y.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
                            } else {
                                // Regime dataset
                                const regime = regimes[context.dataIndex];
                                return `Regime: ${regime}`;
                            }
                        }
                    }
                },
                annotation: {
                    annotations: createEventAnnotations(events, prices)
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: dates.length > 730 ? 'year' : dates.length > 180 ? 'month' : 'day',
                        displayFormats: {
                            day: 'MMM dd',
                            month: 'MMM yyyy',
                            year: 'yyyy'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date'
                    }
                },
                y: {
                    type: 'logarithmic',
                    title: {
                        display: true,
                        text: 'Bitcoin Price (USD, log scale)'
                    },
                    ticks: {
                        callback: (value) => '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 })
                    }
                }
            }
        }
    });

    console.log(`[BTC Regime] Chart created with ${dates.length} data points`);
}

/**
 * Create regime color segments for chart background
 */
function createRegimeSegments(dates, regimes) {
    const segments = [];
    const uniqueRegimes = [...new Set(regimes)];

    uniqueRegimes.forEach(regime => {
        const regimeConfig = BTC_REGIME_CONFIG.regimeColors[regime];
        if (!regimeConfig) return;

        const data = regimes.map((r, i) => r === regime ? 1 : null);

        segments.push({
            label: regime,
            data: data,
            backgroundColor: regimeConfig.bg,
            borderColor: regimeConfig.border,
            borderWidth: 0,
            fill: 'origin',
            pointRadius: 0,
            showLine: false,
            hidden: false
        });
    });

    return segments;
}

/**
 * Create event annotations for chart
 */
function createEventAnnotations(events, prices) {
    if (!events || events.length === 0) return {};

    const annotations = {};
    const maxPrice = Math.max(...prices);

    events.forEach((event, idx) => {
        const color = BTC_REGIME_CONFIG.eventColors[event.type] || '#6b7280';

        annotations[`event_${idx}`] = {
            type: 'line',
            xMin: event.date,
            xMax: event.date,
            borderColor: color,
            borderWidth: 2,
            borderDash: [5, 5],
            label: {
                enabled: true,
                content: event.label,
                position: 'top',
                backgroundColor: color,
                color: 'white',
                font: { size: 10 },
                padding: 4,
                rotation: -45
            }
        };
    });

    return annotations;
}

/**
 * Create regime probabilities bar chart
 */
function createProbabilitiesChart(probabilities) {
    const canvas = document.getElementById('btc-regime-probabilities-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (window.btcProbabilitiesChart) {
        window.btcProbabilitiesChart.destroy();
    }

    const labels = Object.keys(probabilities);
    const data = Object.values(probabilities).map(v => v * 100);
    const colors = labels.map(regime => BTC_REGIME_CONFIG.regimeColors[regime]?.border || '#6b7280');

    window.btcProbabilitiesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Probability (%)',
                data: data,
                backgroundColor: colors.map(c => c + '40'), // Add transparency
                borderColor: colors,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Regime Probabilities',
                    font: { size: 14 }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: (value) => value + '%'
                    }
                }
            }
        }
    });
}

/**
 * Get CSS class for regime chip
 */
function getRegimeClass(regime) {
    const classMap = {
        'Bear Market': 'bear',
        'Correction': 'correction',
        'Bull Market': 'bull',
        'Expansion': 'expansion'
    };
    return classMap[regime] || 'unknown';
}

/**
 * Show loading state
 */
function showLoadingState() {
    console.log('[BTC Regime] Showing loading state');

    const chartContainer = document.getElementById('btc-regime-chart-container');
    if (chartContainer) {
        chartContainer.classList.add('loading');
        console.log('[BTC Regime] Chart container set to loading');
    } else {
        console.warn('[BTC Regime] Chart container not found');
    }

    const loadingMsg = document.getElementById('btc-regime-loading-message');
    if (loadingMsg) {
        loadingMsg.style.display = 'block';
        console.log('[BTC Regime] Loading message shown');
    } else {
        console.warn('[BTC Regime] Loading message element not found');
    }

    // Hide error message if visible
    const errorMsg = document.getElementById('btc-regime-error-message');
    if (errorMsg) {
        errorMsg.style.display = 'none';
    }
}

/**
 * Show error state
 */
function showErrorState(errorMessage) {
    const chartContainer = document.getElementById('btc-regime-chart-container');
    if (chartContainer) {
        chartContainer.classList.remove('loading');
    }

    const loadingMsg = document.getElementById('btc-regime-loading-message');
    if (loadingMsg) {
        loadingMsg.style.display = 'none';
    }

    const errorMsg = document.getElementById('btc-regime-error-message');
    if (errorMsg) {
        errorMsg.textContent = `Error: ${errorMessage}`;
        errorMsg.style.display = 'block';
    }

    console.error('[BTC Regime] Error state:', errorMessage);
}

/**
 * Refresh data (called externally)
 */
export function refreshBTCRegimeChart() {
    const activeButton = document.querySelector('.btc-regime-timeframe-selector button.active');
    const days = activeButton ? parseInt(activeButton.dataset.days) : BTC_REGIME_CONFIG.defaultTimeframe;
    loadBTCRegimeData(days);
}

/**
 * Export current data (for debugging)
 */
export function getBTCRegimeData() {
    return btcRegimeData;
}
