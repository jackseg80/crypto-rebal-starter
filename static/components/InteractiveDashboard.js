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
                            <button id="theme-toggle" class="btn btn-secondary">🌙</button>
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
                font-family: 'Inter', system-ui, sans-serif;
                background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%);
                color: #ffffff;
                min-height: 100vh;
                padding: 20px;
            }

            .dashboard-header {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 24px;
                border: 1px solid rgba(255, 255, 255, 0.1);
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
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                padding: 24px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                transition: all 0.3s ease;
            }

            .kpi-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
                border-color: rgba(0, 255, 136, 0.3);
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
                color: #aaa;
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
                background: linear-gradient(45deg, #fff, #00ff88);
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
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                overflow: hidden;
            }

            .chart-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px 24px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
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

        // Theme toggle
        document.getElementById('theme-toggle').addEventListener('click', () => {
            this.toggleTheme();
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

            this.data.portfolio = portfolio;
            this.data.prices = prices;
            this.data.performance = performance;

            this.updateKPIs();
            this.renderCharts();
            
            this.setConnectionStatus('connected', 'Connected');
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.setConnectionStatus('error', 'Connection failed');
        }
    }

    async fetchPortfolioData() {
        const response = await fetch('/api/portfolio/current');
        if (!response.ok) throw new Error('Failed to fetch portfolio data');
        return await response.json();
    }

    async fetchPriceData() {
        const response = await fetch('/api/prices/history?days=30');
        if (!response.ok) throw new Error('Failed to fetch price data');
        return await response.json();
    }

    async fetchPerformanceData() {
        const response = await fetch('/api/analytics/performance');
        if (!response.ok) throw new Error('Failed to fetch performance data');
        return await response.json();
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
        this.hideAllLoadingSpinners();
        
        // Portfolio composition
        if (this.data.portfolio?.holdings) {
            this.charts.createPortfolioComposition(
                'portfolio-composition-chart',
                this.data.portfolio.holdings,
                {
                    title: 'Current Allocation',
                    onAssetClick: (symbol) => this.showAssetDetails(symbol)
                }
            );
        }

        // Performance chart
        if (this.data.prices) {
            const assets = Object.keys(this.data.prices).slice(0, 10); // Top 10
            this.charts.createPerformanceChart(
                'performance-chart',
                assets,
                this.data.prices,
                {
                    title: 'Price Performance (30 days)'
                }
            );
        }

        // Risk chart (correlation by default)
        if (this.data.performance?.correlation_matrix) {
            this.renderRiskChart('correlation');
        }

        // Optimization chart
        this.renderOptimizationChart('risk-return');
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

    toggleTheme() {
        const button = document.getElementById('theme-toggle');
        const isDark = button.textContent === '🌙';
        
        button.textContent = isDark ? '☀️' : '🌙';
        this.charts.switchTheme(isDark ? 'light' : 'dark');
        
        // Update dashboard theme
        document.body.classList.toggle('light-theme', isDark);
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
        console.log('Show details for:', symbol);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InteractiveDashboard;
} else if (typeof window !== 'undefined') {
    window.InteractiveDashboard = InteractiveDashboard;
}