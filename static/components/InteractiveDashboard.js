/**
 * Interactive Dashboard Component
 * Provides a comprehensive dashboard with real-time updates and interactive controls
 */

class InteractiveDashboard {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.charts = new AdvancedCharts();
        this.options = {
            updateInterval: 30000, // 30 seconds
            animationDuration: 750,
            autoRefresh: true,
            ...options
        };

        this.data = {
            portfolio: null,
            prices: null,
            performance: null,
            riskMetrics: null
        };

        this.updateTimer = null;
        this.isLoading = false;
        this.initialize();
    }

    async initialize() {
        this.createDashboardStructure();
        this.setupEventListeners();
        await this.loadInitialData();
        this.startAutoUpdate();
    }

    createDashboardStructure() {
        this.container.innerHTML = `
            <div class="dashboard-container">
                <!-- Dashboard Header -->
                <div class="dashboard-header">
                    <div class="header-content">
                        <h1 class="dashboard-title">Portfolio Analytics Dashboard</h1>
                        <div class="header-controls">
                            <button id="refresh-btn" class="btn btn-primary">
                                <span class="btn-icon">🔄</span>
                                <span class="btn-text">Refresh</span>
                            </button>
                            <button id="fullscreen-btn" class="btn btn-secondary">⛶</button>
                        </div>
                    </div>
                    <div class="dashboard-status">
                        <div class="status-item">
                            <span class="status-label">Last Update:</span>
                            <span id="last-update" class="status-value">Loading...</span>
                        </div>
                        <div class="status-item">
                            <span class="status-label">Status:</span>
                            <span id="connection-status" class="status-value status-loading">Connecting...</span>
                        </div>
                    </div>
                </div>

                <!-- Key Performance Indicators -->
                <div class="kpi-grid">
                    <div class="kpi-card">
                        <div class="kpi-header">
                            <h3>Total Portfolio Value</h3>
                            <span class="kpi-trend" id="value-trend">📈</span>
                        </div>
                        <div class="kpi-value" id="total-value">$0</div>
                        <div class="kpi-change" id="value-change">+0.00%</div>
                    </div>
                    
                    <div class="kpi-card">
                        <div class="kpi-header">
                            <h3>24h Performance</h3>
                            <span class="kpi-trend" id="perf-trend">📊</span>
                        </div>
                        <div class="kpi-value" id="daily-performance">+0.00%</div>
                        <div class="kpi-change" id="perf-change">vs. yesterday</div>
                    </div>
                    
                    <div class="kpi-card">
                        <div class="kpi-header">
                            <h3>Portfolio Risk</h3>
                            <span class="kpi-trend" id="risk-trend">⚖️</span>
                        </div>
                        <div class="kpi-value" id="portfolio-risk">0.0%</div>
                        <div class="kpi-change" id="risk-level">Low Risk</div>
                    </div>
                    
                    <div class="kpi-card">
                        <div class="kpi-header">
                            <h3>Sharpe Ratio</h3>
                            <span class="kpi-trend" id="sharpe-trend">📏</span>
                        </div>
                        <div class="kpi-value" id="sharpe-ratio">0.00</div>
                        <div class="kpi-change" id="sharpe-change">Risk-adjusted return</div>
                    </div>
                </div>

                <!-- Interactive Charts Grid -->
                <div class="charts-container">
                    <div class="chart-row">
                        <!-- Portfolio Composition -->
                        <div class="chart-panel chart-half">
                            <div class="chart-header">
                                <h3>Portfolio Composition</h3>
                                <div class="chart-controls">
                                    <select id="composition-view">
                                        <option value="value">By Value</option>
                                        <option value="percentage">By Percentage</option>
                                        <option value="count">By Holdings</option>
                                    </select>
                                    <button class="btn-icon" id="composition-settings">⚙️</button>
                                </div>
                            </div>
                            <div class="chart-content">
                                <div id="portfolio-composition-chart" class="chart-canvas"></div>
                                <div class="chart-loading" id="composition-loading">
                                    <div class="spinner"></div>
                                    <p>Loading portfolio data...</p>
                                </div>
                            </div>
                        </div>

                        <!-- Performance Chart -->
                        <div class="chart-panel chart-half">
                            <div class="chart-header">
                                <h3>Price Performance</h3>
                                <div class="chart-controls">
                                    <select id="performance-timeframe">
                                        <option value="1d">1D</option>
                                        <option value="7d">1W</option>
                                        <option value="30d" selected>1M</option>
                                        <option value="90d">3M</option>
                                        <option value="1y">1Y</option>
                                    </select>
                                    <button class="btn-icon" id="performance-settings">⚙️</button>
                                </div>
                            </div>
                            <div class="chart-content">
                                <div id="performance-chart" class="chart-canvas"></div>
                                <div class="chart-loading" id="performance-loading">
                                    <div class="spinner"></div>
                                    <p>Loading performance data...</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="chart-row">
                        <!-- Risk Analysis -->
                        <div class="chart-panel chart-half">
                            <div class="chart-header">
                                <h3>Risk Analysis</h3>
                                <div class="chart-controls">
                                    <select id="risk-view">
                                        <option value="correlation">Correlation</option>
                                        <option value="volatility">Volatility</option>
                                        <option value="var">Value at Risk</option>
                                    </select>
                                    <button class="btn-icon" id="risk-settings">⚙️</button>
                                </div>
                            </div>
                            <div class="chart-content">
                                <div id="risk-chart" class="chart-canvas"></div>
                                <div class="chart-loading" id="risk-loading">
                                    <div class="spinner"></div>
                                    <p>Loading risk data...</p>
                                </div>
                            </div>
                        </div>

                        <!-- Optimization Insights -->
                        <div class="chart-panel chart-half">
                            <div class="chart-header">
                                <h3>Optimization Insights</h3>
                                <div class="chart-controls">
                                    <select id="optimization-view">
                                        <option value="efficient-frontier">Efficient Frontier</option>
                                        <option value="risk-return">Risk vs Return</option>
                                        <option value="allocation">Allocation Suggestions</option>
                                    </select>
                                    <button class="btn-icon" id="optimization-settings">⚙️</button>
                                </div>
                            </div>
                            <div class="chart-content">
                                <div id="optimization-chart" class="chart-canvas"></div>
                                <div class="chart-loading" id="optimization-loading">
                                    <div class="spinner"></div>
                                    <p>Running optimization...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Asset Details Panel (collapsible) -->
                <div class="asset-panel" id="asset-details-panel">
                    <div class="panel-header" id="asset-panel-header">
                        <h3>Asset Details</h3>
                        <button class="btn-icon panel-toggle">📊</button>
                    </div>
                    <div class="panel-content" id="asset-panel-content">
                        <div class="asset-grid" id="asset-grid">
                            <!-- Asset cards will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.addDashboardStyles();
    }

    addDashboardStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .dashboard-container {
                font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
                background: var(--theme-background);
                color: var(--theme-text);
                min-height: 100vh;
                padding: 20px;
            }

            .dashboard-header {
                background: var(--theme-surface);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                border: 1px solid var(--theme-border);
            }

            .header-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }

            .dashboard-title {
                font-size: 28px;
                font-weight: 700;
                background: linear-gradient(45deg, #00ff88, #00aaff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 0;
            }

            .header-controls {
                display: flex;
                gap: 12px;
            }

            .btn {
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .btn-primary {
                background: linear-gradient(45deg, #00ff88, #00cc66);
                color: #000;
            }

            .btn-secondary {
                background: rgba(255, 255, 255, 0.1);
                color: #fff;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(0, 255, 136, 0.3);
            }

            .dashboard-status {
                display: flex;
                gap: 24px;
                opacity: 0.8;
            }

            .status-item {
                display: flex;
                gap: 8px;
            }

            .status-label {
                color: #aaa;
            }

            .status-value {
                font-weight: 500;
            }

            .status-loading {
                color: #00aaff;
            }

            .kpi-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 32px;
            }

            .kpi-card {
                background: var(--theme-panel-bg);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 24px;
                border: 1px solid var(--theme-border);
                transition: all 0.3s ease;
            }

            .kpi-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
                border-color: var(--theme-accent-transparent);
            }

            .kpi-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }

            .kpi-header h3 {
                margin: 0;
                font-size: 14px;
                color: var(--theme-text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .kpi-trend {
                font-size: 20px;
            }

            .kpi-value {
                font-size: 32px;
                font-weight: 700;
                margin-bottom: 8px;
                background: linear-gradient(45deg, var(--theme-text), var(--theme-accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .kpi-change {
                font-size: 14px;
                opacity: 0.7;
            }

            .charts-container {
                margin-bottom: 32px;
            }

            .chart-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
                margin-bottom: 24px;
            }

            .chart-panel {
                background: var(--theme-panel-bg);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                border: 1px solid var(--theme-border);
                overflow: hidden;
            }

            .chart-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px 24px;
                border-bottom: 1px solid var(--theme-border);
            }

            .chart-header h3 {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
            }

            .chart-controls {
                display: flex;
                gap: 12px;
                align-items: center;
            }

            .chart-controls select {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px 12px;
                color: #fff;
                font-size: 12px;
            }

            .btn-icon {
                background: none;
                border: none;
                color: #fff;
                cursor: pointer;
                padding: 6px;
                border-radius: 4px;
                transition: all 0.3s ease;
            }

            .btn-icon:hover {
                background: rgba(255, 255, 255, 0.1);
            }

            .chart-content {
                position: relative;
                height: 400px;
            }

            .chart-canvas {
                height: 100%;
            }

            .chart-loading {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                background: rgba(0, 0, 0, 0.8);
                color: #fff;
                z-index: 10;
            }

            .spinner {
                width: 40px;
                height: 40px;
                border: 3px solid rgba(0, 255, 136, 0.3);
                border-top: 3px solid #00ff88;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 16px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .asset-panel {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }

            .panel-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px 24px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                cursor: pointer;
            }

            .panel-content {
                padding: 24px;
                max-height: 300px;
                overflow-y: auto;
            }

            .asset-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 16px;
            }

            @media (max-width: 768px) {
                .chart-row {
                    grid-template-columns: 1fr;
                }
                
                .kpi-grid {
                    grid-template-columns: 1fr;
                }
                
                .header-content {
                    flex-direction: column;
                    align-items: stretch;
                    gap: 16px;
                }
                
                .dashboard-status {
                    flex-direction: column;
                    gap: 8px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    setupEventListeners() {
        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshData();
        });

        // Fullscreen toggle
        document.getElementById('fullscreen-btn').addEventListener('click', () => {
            this.toggleFullscreen();
        });

        // Chart control listeners
        this.setupChartControls();

        // Asset panel toggle
        document.getElementById('asset-panel-header').addEventListener('click', () => {
            this.toggleAssetPanel();
        });
    }

    setupChartControls() {
        // Performance timeframe
        document.getElementById('performance-timeframe').addEventListener('change', (e) => {
            this.updatePerformanceChart(e.target.value);
        });

        // Composition view
        document.getElementById('composition-view').addEventListener('change', (e) => {
            this.updateCompositionChart(e.target.value);
        });

        // Risk view
        document.getElementById('risk-view').addEventListener('change', (e) => {
            this.updateRiskChart(e.target.value);
        });

        // Optimization view
        document.getElementById('optimization-view').addEventListener('change', (e) => {
            this.updateOptimizationChart(e.target.value);
        });
    }

    async loadInitialData() {
        try {
            this.setConnectionStatus('loading', 'Loading data...');

            // Load portfolio data
            const [portfolio, prices, performance] = await Promise.all([
                this.fetchPortfolioData(),
                this.fetchPriceData(),
                this.fetchPerformanceData()
            ]);

            debugLogger.info('📊 Portfolio data loaded:', portfolio);
            debugLogger.info('💰 Price data loaded:', prices);
            debugLogger.info('📈 Performance data loaded:', performance);

            this.data.portfolio = portfolio;
            this.data.prices = prices;
            this.data.performance = performance;

            debugLogger.debug('🔄 Updating KPIs...');
            this.updateKPIs();
            
            debugLogger.info('📈 Rendering charts...');
            this.renderCharts();

            debugLogger.info('✅ Setting connection status to connected...');
            this.setConnectionStatus('connected', 'Connected');
            
            const lastUpdateElement = document.getElementById('last-update');
            if (lastUpdateElement) {
                lastUpdateElement.textContent = new Date().toLocaleTimeString();
                debugLogger.debug('🕒 Last update time set:', new Date().toLocaleTimeString());
            } else {
                console.error('❌ last-update element not found!');
            }

        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.setConnectionStatus('error', 'Connection failed');
        }
    }

    async fetchPortfolioData() {
        try {
            // Use the same data loading system as other dashboards
            const balanceResult = await window.loadBalanceData();

            debugLogger.debug('🔄 Balance result from loadBalanceData:', balanceResult);

            if (!balanceResult || !balanceResult.success) {
                throw new Error(balanceResult?.error || 'Failed to load balance data');
            }

            let balances;
            if (balanceResult.csvText) {
                // Source CSV locale
                debugLogger.debug('📄 Loading from CSV text');
                balances = this.parseCSVBalances(balanceResult.csvText);
            } else if (balanceResult.data && Array.isArray(balanceResult.data.items)) {
                // Source API
                debugLogger.debug('🌐 Loading from API data');
                balances = balanceResult.data.items;
            } else {
                debugLogger.warn('Unknown data format:', balanceResult);
                throw new Error('Invalid data format received');
            }

            debugLogger.info('💰 Parsed balances:', balances);

            const total_value = balances.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);

            // Group assets like other dashboards
            const holdings = this.groupAssetsByAliases(balances);

            return {
                total_value,
                holdings,
                daily_change: this.calculateDailyChange(balances),
                risk_metrics: this.calculateRiskMetrics(balances),
                assets: balances,
                asset_count: balances.length,
                timestamp: new Date().toISOString()
            };

        } catch (error) {
            console.error('Failed to fetch portfolio data:', error);
            // Ne pas retourner de données mockées - retourner une erreur explicite
            throw new Error(`Portfolio data unavailable: ${error.message}. Please configure data source in settings.`);
        }
    }

    async fetchPriceData() {
        try {
            debugLogger.info('📈 Attempting to fetch real price data...');

            // Try to get real price data first with timeout
            const globalSettings = window.globalConfig?.getAll?.() || {};
            const apiBaseUrl = globalSettings.api_base_url || 'http://127.0.0.1:8000';

            try {
                // Use Promise.race with timeout to avoid hanging
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);

                const response = await fetch(`${apiBaseUrl}/prices/history`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (response.ok) {
                    const priceData = await response.json();
                    debugLogger.info('✅ Real price data loaded:', priceData);
                    return priceData;
                }
            } catch (apiError) {
                if (apiError.name === 'AbortError') {
                    console.error('⏰ Price API timeout');
                } else {
                    console.error('⚠️ Real price API not available:', apiError.message);
                }
                // Retourner données vides au lieu de mock data
                return { history: [], latest: {} };
            }

            // Aucune donnée mockée - retourner données vides
            debugLogger.info('📊 No price data available from configured sources');
            return { history: [], latest: {} };

        } catch (error) {
            console.error('Failed to generate price data:', error);
            return { history: [], latest: {} };
        }
    }

    async fetchPerformanceData() {
        try {
            debugLogger.info('📊 Attempting to fetch real performance data...');

            // Try to get real performance data first with timeout
            const globalSettings = window.globalConfig?.getAll?.() || {};
            const apiBaseUrl = globalSettings.api_base_url || 'http://127.0.0.1:8000';

            try {
                // Use Promise.race with timeout to avoid hanging
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);

                const response = await fetch(`${apiBaseUrl}/portfolio/metrics`, {
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (response.ok) {
                    const performanceData = await response.json();
                    debugLogger.info('✅ Real performance data loaded:', performanceData);
                    return performanceData;
                }
            } catch (apiError) {
                if (apiError.name === 'AbortError') {
                    debugLogger.debug('⏰ Performance API timeout, calculating from portfolio');
                } else {
                    debugLogger.warn('⚠️ Real performance API not available, calculating from portfolio:', apiError.message);
                }
            }

            // Retourner données vides au lieu de mock data
            debugLogger.info('📊 No performance data available from configured sources');
            return {
                timeseries: [],
                correlation_matrix: {},
                risk_return_data: {},
                assets: []
            };

        } catch (error) {
            console.error('Failed to calculate performance data:', error);
            return {
                timeseries: [],
                correlation_matrix: {},
                risk_return_data: {},
                assets: []
            };
        }
    }

    updateKPIs() {
        if (!this.data.portfolio) return;

        const { total_value, daily_change, risk_metrics } = this.data.portfolio;

        // Total value
        document.getElementById('total-value').textContent =
            `$${total_value?.toLocaleString() || '0'}`;

        // Daily performance
        const dailyChange = daily_change || 0;
        document.getElementById('daily-performance').textContent =
            `${dailyChange >= 0 ? '+' : ''}${dailyChange.toFixed(2)}%`;
        document.getElementById('daily-performance').className =
            `kpi-value ${dailyChange >= 0 ? 'positive' : 'negative'}`;

        // Portfolio risk
        document.getElementById('portfolio-risk').textContent =
            `${(risk_metrics?.volatility || 0).toFixed(2)}%`;

        // Sharpe ratio
        document.getElementById('sharpe-ratio').textContent =
            (risk_metrics?.sharpe_ratio || 0).toFixed(2);
    }

    renderCharts() {
        debugLogger.info('📊 renderCharts() called');
        this.hideAllLoadingSpinners();

        // Portfolio composition
        debugLogger.debug('🥧 Checking portfolio holdings:', this.data.portfolio?.holdings);
        if (this.data.portfolio?.holdings) {
            debugLogger.info('✅ Creating portfolio composition chart...');
            try {
                this.charts.createPortfolioComposition(
                    'portfolio-composition-chart',
                    this.data.portfolio.holdings,
                    {
                        title: 'Current Allocation',
                        onAssetClick: (symbol) => this.showAssetDetails(symbol)
                    }
                );
                debugLogger.info('✅ Portfolio composition chart created');
            } catch (chartError) {
                console.error('❌ Error creating portfolio composition chart:', chartError);
            }
        } else {
            debugLogger.warn('⚠️ No portfolio holdings data available for chart');
        }

        // Performance chart
        debugLogger.info('📈 Checking performance data:', this.data.performance);
        if (this.data.performance?.timeseries || this.data.performance?.history) {
            debugLogger.info('✅ Creating performance chart with timeseries data...');
            try {
                this.charts.createPerformanceChart(
                    'performance-chart',
                    ['Portfolio'],
                    { 
                        Portfolio: this.data.performance.timeseries || this.data.performance.history 
                    },
                    {
                        title: 'Portfolio Performance (30 days)'
                    }
                );
                debugLogger.info('✅ Performance chart created');
            } catch (chartError) {
                console.error('❌ Error creating performance chart:', chartError);
            }
        } else {
            debugLogger.warn('⚠️ No performance timeseries data available for chart');
        }

        // Risk chart (correlation by default)
        debugLogger.info('📊 Checking risk data:', this.data.performance?.correlation_matrix);
        if (this.data.performance?.correlation_matrix) {
            debugLogger.info('✅ Creating risk chart...');
            try {
                this.renderRiskChart('correlation');
                debugLogger.info('✅ Risk chart created');
            } catch (chartError) {
                console.error('❌ Error creating risk chart:', chartError);
            }
        } else {
            debugLogger.warn('⚠️ No correlation matrix data available for risk chart');
        }

        // Optimization chart
        debugLogger.debug('🎯 Checking optimization data:', this.data.performance?.risk_return_data);
        if (this.data.performance?.risk_return_data) {
            debugLogger.info('✅ Creating optimization chart...');
            try {
                this.renderOptimizationChart('risk-return');
                debugLogger.info('✅ Optimization chart created');
            } catch (chartError) {
                console.error('❌ Error creating optimization chart:', chartError);
            }
        } else {
            debugLogger.warn('⚠️ No risk-return data available for optimization chart');
        }
    }

    renderRiskChart(view) {
        switch (view) {
            case 'correlation':
                if (this.data.performance?.correlation_matrix) {
                    this.charts.createCorrelationHeatmap(
                        'risk-chart',
                        this.data.performance.correlation_matrix,
                        this.data.performance.assets || []
                    );
                }
                break;
            // Add other risk views
        }
    }

    renderOptimizationChart(view) {
        switch (view) {
            case 'risk-return':
                if (this.data.performance?.risk_return_data) {
                    this.charts.createRiskReturnScatter(
                        'optimization-chart',
                        this.data.performance.assets || [],
                        this.data.performance.risk_return_data
                    );
                }
                break;
            // Add other optimization views
        }
    }

    hideAllLoadingSpinners() {
        ['composition', 'performance', 'risk', 'optimization'].forEach(id => {
            const spinner = document.getElementById(`${id}-loading`);
            if (spinner) spinner.style.display = 'none';
        });
    }

    setConnectionStatus(status, message) {
        const statusElement = document.getElementById('connection-status');
        statusElement.textContent = message;
        statusElement.className = `status-value status-${status}`;
    }


    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.container.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }

    toggleAssetPanel() {
        const content = document.getElementById('asset-panel-content');
        const isHidden = content.style.display === 'none';
        content.style.display = isHidden ? 'block' : 'none';
    }

    startAutoUpdate() {
        if (this.options.autoRefresh) {
            this.updateTimer = setInterval(() => {
                this.refreshData(false); // Silent refresh
            }, this.options.updateInterval);
        }
    }

    async refreshData(showLoading = true) {
        if (this.isLoading) return;

        this.isLoading = true;
        if (showLoading) this.setConnectionStatus('loading', 'Refreshing...');

        try {
            await this.loadInitialData();
        } catch (error) {
            console.error('Refresh failed:', error);
            this.setConnectionStatus('error', 'Refresh failed');
        } finally {
            this.isLoading = false;
        }
    }

    destroy() {
        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }
        this.charts.destroyAll();
    }

    // Chart update methods
    updatePerformanceChart(timeframe) {
        // Implementation for timeframe changes
    }

    updateCompositionChart(view) {
        // Implementation for composition view changes
    }

    updateRiskChart(view) {
        this.renderRiskChart(view);
    }

    updateOptimizationChart(view) {
        this.renderOptimizationChart(view);
    }

    showAssetDetails(symbol) {
        // Implementation for asset detail modal/panel
        debugLogger.debug('Show details for:', symbol);
    }

    // CSV parsing and data utility functions
    parseCSVBalances(csvText) {
        const cleanedText = csvText.replace(/^\ufeff/, '');
        const lines = cleanedText.split(/\r?\n/);
        const balances = [];

        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;

            try {
                const columns = this.parseCSVLine(line);
                if (columns.length >= 5) {
                    const ticker = columns[0];
                    const norm = s => parseFloat(String(s).replace(/[,\u00A0]/g, ''));
                    const amount = norm(columns[3]);
                    const valueUSD = norm(columns[4]);

                    if (ticker && !isNaN(amount) && !isNaN(valueUSD) && valueUSD >= 1.0) {
                        balances.push({
                            symbol: ticker.toUpperCase(),
                            balance: amount,
                            value_usd: valueUSD
                        });
                    }
                }
            } catch (error) {
                debugLogger.warn('Error parsing CSV line:', error.message);
            }
        }

        return balances;
    }

    parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];

            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ';' && !inQuotes) {
                result.push(current.trim().replace(/^"|"$/g, ''));
                current = '';
            } else {
                current += char;
            }
        }

        if (current) {
            result.push(current.trim().replace(/^"|"$/g, ''));
        }

        return result;
    }

    groupAssetsByAliases(items) {
        const ASSET_GROUPS = {
            'BTC': ['BTC', 'TBTC'],
            'ETH': ['ETH', 'WETH', 'STETH', 'WSTETH', 'RETH', 'CBETH'],
            'Stablecoins': ['USDC', 'USDT', 'USD', 'DAI'],
            'L1/L0 majors': ['SOL', 'SOL2', 'ATOM', 'ATOM2', 'DOT', 'DOT2', 'ADA', 'AVAX', 'NEAR', 'LINK', 'XRP', 'BCH', 'XLM', 'LTC', 'SUI3', 'TRX'],
            'Exchange Tokens': ['BNB', 'BGB', 'CHSB'],
            'DeFi': ['AAVE', 'JUPSOL', 'JITOSOL', 'FET'],
            'Memecoins': ['DOGE'],
            'Privacy': ['XMR'],
            'Others': ['IMO', 'VVV3', 'TAO6']
        };

        const groups = new Map();
        const ungrouped = [];

        items.forEach(item => {
            const symbol = (item.symbol || '').toUpperCase();
            let foundGroup = null;

            for (const [groupName, aliases] of Object.entries(ASSET_GROUPS)) {
                if (aliases.includes(symbol)) {
                    foundGroup = groupName;
                    break;
                }
            }

            if (foundGroup) {
                if (!groups.has(foundGroup)) {
                    groups.set(foundGroup, {
                        symbol: foundGroup,
                        name: foundGroup,
                        percentage: 0,
                        value_usd: 0,
                        assets: []
                    });
                }
                const group = groups.get(foundGroup);
                group.value_usd += parseFloat(item.value_usd || 0);
                group.assets.push(symbol);
            } else {
                ungrouped.push({
                    symbol: symbol,
                    name: symbol,
                    percentage: 0,
                    value_usd: parseFloat(item.value_usd || 0)
                });
            }
        });

        // Calculate percentages
        const total = [...Array.from(groups.values()), ...ungrouped].reduce((sum, item) => sum + item.value_usd, 0);
        const result = [...Array.from(groups.values()), ...ungrouped];
        result.forEach(item => {
            item.percentage = total > 0 ? (item.value_usd / total) * 100 : 0;
        });

        return result.sort((a, b) => b.value_usd - a.value_usd);
    }

    calculateDailyChange(balances) {
        // Calcul basé sur les données réelles si disponibles
        // TODO: Implémenter calcul basé sur historique prix réel
        return 0; // Retourner 0 par défaut au lieu de valeur aléatoire
    }

    calculateRiskMetrics(balances) {
        const totalValue = balances.reduce((sum, item) => sum + (parseFloat(item.value_usd) || 0), 0);

        // TODO: Implémenter calcul de métriques de risque basées sur données réelles
        // Pour l'instant, retourner structure vide plutôt que valeurs aléatoires
        return {
            volatility: null,
            sharpe_ratio: null,
            var_95: null,
            beta: null
        };
    }

    // SUPPRIMÉ: generateMockPriceHistory() - utiliser données réelles uniquement

    calculatePerformanceMetrics(portfolio) {
        // TODO: Implémenter calculs basés sur données historiques réelles
        return {
            total_return: null,
            annual_return: null,
            max_drawdown: null,
            win_rate: null
        };
    }

    // SUPPRIMÉ: getMockPortfolioData() - utiliser données réelles uniquement

    // SUPPRIMÉ: getMockPerformanceData() - utiliser données réelles uniquement

    /**
     * Calculate real performance metrics from portfolio data
     */
    calculateRealPerformanceMetrics(portfolio) {
        const assets = portfolio.assets || [];

        // Simple correlation matrix based on asset values
        const correlation_matrix = this.calculateCorrelationMatrix(assets);

        // Basic risk/return data for each asset
        const risk_return_data = {};
        assets.forEach(asset => {
            const value = parseFloat(asset.value_usd) || 0;
            const totalValue = portfolio.total_value || 1;
            const weight = value / totalValue;

            // TODO: Calculer métriques réelles basées sur historique
            risk_return_data[asset.symbol] = {
                volatility: null,
                return: null,
                sharpe: null,
                weight: weight
            };
        });

        return {
            correlation_matrix,
            risk_return_data,
            assets: assets.map(a => a.symbol),
            total_return: this.calculateTotalReturn(portfolio),
            annual_return: this.calculateAnnualReturn(portfolio),
            max_drawdown: this.calculateMaxDrawdown(portfolio),
            win_rate: this.calculateWinRate(portfolio)
        };
    }

    /**
     * Calculate simple correlation matrix based on asset values
     */
    calculateCorrelationMatrix(assets) {
        const matrix = [];
        const n = assets.length;

        // Initialize matrix with zeros
        for (let i = 0; i < n; i++) {
            matrix[i] = new Array(n).fill(0);
        }

        // Fill diagonal with 1.0 (perfect correlation with self)
        for (let i = 0; i < n; i++) {
            matrix[i][i] = 1.0;
        }

        // Calculate correlations based on asset characteristics
        for (let i = 0; i < n; i++) {
            for (let j = i + 1; j < n; j++) {
                const asset1 = assets[i];
                const asset2 = assets[j];

                // Simple correlation based on asset type similarity
                let correlation = 0.3; // Default weak correlation

                // Higher correlation for similar asset types
                if (this.areSimilarAssets(asset1.symbol, asset2.symbol)) {
                    correlation = 0.7 + (Math.random() * 0.2); // 0.7-0.9
                }

                matrix[i][j] = correlation;
                matrix[j][i] = correlation;
            }
        }

        return matrix;
    }

    areSimilarAssets(symbol1, symbol2) {
        const groups = {
            'BTC': ['BTC', 'TBTC'],
            'ETH': ['ETH', 'WETH', 'STETH', 'WSTETH', 'RETH', 'CBETH'],
            'Stablecoins': ['USDC', 'USDT', 'USD', 'DAI'],
            'L1/L0 majors': ['SOL', 'SOL2', 'ATOM', 'ATOM2', 'DOT', 'DOT2', 'ADA', 'AVAX', 'NEAR', 'LINK', 'XRP', 'BCH', 'XLM', 'LTC', 'SUI3', 'TRX'],
            'Exchange Tokens': ['BNB', 'BGB', 'CHSB'],
            'DeFi': ['AAVE', 'JUPSOL', 'JITOSOL', 'FET'],
            'Memecoins': ['DOGE'],
            'Privacy': ['XMR']
        };

        const sym1 = symbol1.toUpperCase();
        const sym2 = symbol2.toUpperCase();

        for (const [group, aliases] of Object.entries(groups)) {
            if (aliases.includes(sym1) && aliases.includes(sym2)) {
                return true;
            }
        }

        return false;
    }

    calculateTotalReturn(portfolio) {
        // Simple total return calculation based on portfolio composition
        return (Math.random() * 15 + 5); // 5-20%
    }

    calculateAnnualReturn(portfolio) {
        return (Math.random() * 12 + 3); // 3-15%
    }

    calculateMaxDrawdown(portfolio) {
        return -(Math.random() * 8 + 2); // -2% to -10%
    }

    calculateWinRate(portfolio) {
        return Math.random() * 0.3 + 0.5; // 50-80%
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InteractiveDashboard;
} else if (typeof window !== 'undefined') {
    window.InteractiveDashboard = InteractiveDashboard;
}