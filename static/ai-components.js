/**
 * Composants UI réutilisables pour l'affichage des données IA
 * Architecture basée sur des Web Components et des classes utilitaires
 */

/**
 * Classe de base pour tous les composants IA
 */
class AIComponent extends HTMLElement {
    constructor() {
        super();
        this.isInitialized = false;
        this.updateInterval = null;
        this.data = null;
        this.options = {};
    }

    connectedCallback() {
        if (!this.isInitialized) {
            this.initialize();
            this.isInitialized = true;
        }
    }

    disconnectedCallback() {
        this.cleanup();
    }

    initialize() {
        // À implémenter dans les classes filles
    }

    cleanup() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }

    /**
     * Utilitaire pour créer des éléments avec classes et contenu
     */
    createElement(tag, className, content = '') {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (content) element.innerHTML = content;
        return element;
    }

    /**
     * Formatage des nombres
     */
    formatNumber(value, decimals = 2, suffix = '') {
        if (typeof value !== 'number' || isNaN(value)) return 'N/A';
        return value.toFixed(decimals) + suffix;
    }

    /**
     * Formatage des pourcentages
     */
    formatPercentage(value, decimals = 1) {
        return this.formatNumber(value * 100, decimals, '%');
    }

    /**
     * Utilitaire pour les couleurs basées sur la valeur
     */
    getValueColor(value, thresholds = { positive: 0, negative: 0 }) {
        if (value > thresholds.positive) return 'var(--color-success, #10b981)';
        if (value < thresholds.negative) return 'var(--color-danger, #ef4444)';
        return 'var(--color-neutral, #6b7280)';
    }
}

/**
 * Composant d'affichage de la volatilité prédite
 */
class VolatilityDisplay extends AIComponent {
    static get observedAttributes() {
        return ['symbol', 'horizon', 'auto-update'];
    }

    initialize() {
        this.symbol = this.getAttribute('symbol') || 'BTC';
        this.horizon = parseInt(this.getAttribute('horizon')) || 24;
        this.autoUpdate = this.hasAttribute('auto-update');

        this.innerHTML = this.getTemplate();
        this.loadData();

        if (this.autoUpdate) {
            this.startAutoUpdate();
        }
    }

    getTemplate() {
        return `
            <div class="ai-volatility-display">
                <div class="ai-component-header">
                    <h3 class="ai-component-title">
                        <span class="ai-icon">📈</span>
                        Volatilité Prédite - ${this.symbol}
                    </h3>
                    <div class="ai-component-status">
                        <span class="status-dot" id="vol-status"></span>
                        <span class="status-text">Chargement...</span>
                    </div>
                </div>
                
                <div class="ai-component-content">
                    <div class="volatility-main-value">
                        <div class="value-container">
                            <span class="value" id="vol-current">--</span>
                            <span class="unit">%</span>
                        </div>
                        <div class="value-label">Volatilité ${this.horizon}h</div>
                    </div>
                    
                    <div class="volatility-metrics">
                        <div class="metric">
                            <span class="metric-label">Confiance</span>
                            <span class="metric-value" id="vol-confidence">--%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Tendance</span>
                            <span class="metric-value" id="vol-trend">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Historique 7j</span>
                            <div class="metric-chart" id="vol-chart"></div>
                        </div>
                    </div>
                </div>
                
                <div class="ai-component-footer">
                    <small class="update-time">Dernière mise à jour: <span id="vol-timestamp">--</span></small>
                </div>
            </div>
        `;
    }

    async loadData() {
        const statusDot = this.querySelector('#vol-status');
        const statusText = this.querySelector('.status-text');
        
        try {
            statusDot.className = 'status-dot loading';
            statusText.textContent = 'Chargement...';

            const data = await window.aiServiceManager.volatilityService.predict([this.symbol], this.horizon);
            
            this.updateDisplay(data);
            
            statusDot.className = 'status-dot online';
            statusText.textContent = 'En ligne';
        } catch (error) {
            debugLogger.error('Volatility data loading failed:', error);
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Erreur';
        }
    }

    updateDisplay(data) {
        if (!data || !data.predictions) return;

        const prediction = data.predictions[this.symbol];
        if (!prediction) return;

        // Valeur principale
        const currentValue = this.querySelector('#vol-current');
        currentValue.textContent = this.formatNumber(prediction.volatility * 100, 1);
        currentValue.style.color = this.getValueColor(prediction.volatility, { positive: 0.05, negative: 0.02 });

        // Confiance
        const confidence = this.querySelector('#vol-confidence');
        confidence.textContent = this.formatPercentage(prediction.confidence, 0);

        // Tendance
        const trend = this.querySelector('#vol-trend');
        const trendValue = prediction.trend || 0;
        trend.textContent = trendValue > 0 ? '↗️ Hausse' : trendValue < 0 ? '↘️ Baisse' : '➡️ Stable';
        trend.style.color = this.getValueColor(trendValue);

        // Graphique miniature
        this.renderMiniChart(prediction.historical_data || []);

        // Timestamp
        const timestamp = this.querySelector('#vol-timestamp');
        timestamp.textContent = new Date().toLocaleTimeString();
    }

    renderMiniChart(data) {
        const chartContainer = this.querySelector('#vol-chart');
        if (!data.length) return;

        const maxValue = Math.max(...data);
        const minValue = Math.min(...data);
        const range = maxValue - minValue;

        const points = data.map((value, index) => {
            const x = (index / (data.length - 1)) * 100;
            const y = range > 0 ? ((maxValue - value) / range) * 100 : 50;
            return `${x},${y}`;
        }).join(' ');

        chartContainer.innerHTML = `
            <svg width="60" height="30" viewBox="0 0 100 100" class="mini-chart">
                <polyline points="${points}" fill="none" stroke="var(--theme-portfolio, #10b981)" stroke-width="2"/>
            </svg>
        `;
    }

    startAutoUpdate(interval = 60000) { // 1 minute
        this.updateInterval = setInterval(() => {
            this.loadData();
        }, interval);
    }
}

/**
 * Composant d'affichage du régime de marché
 */
class MarketRegimeDisplay extends AIComponent {
    initialize() {
        this.innerHTML = this.getTemplate();
        this.loadData();
        this.subscribeToRegimeChanges();
    }

    getTemplate() {
        return `
            <div class="ai-regime-display">
                <div class="ai-component-header">
                    <h3 class="ai-component-title">
                        <span class="ai-icon">🎯</span>
                        Régime de Marché
                    </h3>
                    <div class="ai-component-status">
                        <span class="status-dot" id="regime-status"></span>
                        <span class="status-text">Analyse...</span>
                    </div>
                </div>
                
                <div class="ai-component-content">
                    <div class="regime-main">
                        <div class="regime-indicator" id="regime-indicator">
                            <div class="regime-icon" id="regime-icon">🔍</div>
                            <div class="regime-name" id="regime-name">Analyse en cours...</div>
                            <div class="regime-confidence" id="regime-confidence">--%</div>
                        </div>
                    </div>
                    
                    <div class="regime-details">
                        <div class="regime-characteristic" id="regime-volatility">
                            <span class="char-label">Volatilité:</span>
                            <span class="char-value">--</span>
                        </div>
                        <div class="regime-characteristic" id="regime-trend">
                            <span class="char-label">Tendance:</span>
                            <span class="char-value">--</span>
                        </div>
                        <div class="regime-characteristic" id="regime-duration">
                            <span class="char-label">Durée estimée:</span>
                            <span class="char-value">--</span>
                        </div>
                    </div>
                </div>
                
                <div class="ai-component-footer">
                    <small class="update-time">Dernière analyse: <span id="regime-timestamp">--</span></small>
                </div>
            </div>
        `;
    }

    async loadData() {
        const statusDot = this.querySelector('#regime-status');
        const statusText = this.querySelector('.status-text');

        try {
            statusDot.className = 'status-dot loading';
            statusText.textContent = 'Analyse...';

            const data = await window.aiServiceManager.regimeService.getCurrentRegime();
            this.updateDisplay(data);

            statusDot.className = 'status-dot online';
            statusText.textContent = 'Actif';
        } catch (error) {
            debugLogger.error('Market regime data loading failed:', error);
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Erreur';
        }
    }

    updateDisplay(data) {
        if (!data || !data.regime) return;

        const regime = data.regime;
        
        // Configuration des régimes
        const regimeConfig = {
            bullish: { icon: '🚀', name: 'Bull Market', color: '#10b981' },
            bearish: { icon: '🐻', name: 'Bear Market', color: '#ef4444' },
            sideways: { icon: '➡️', name: 'Marché Latéral', color: '#6b7280' },
            volatile: { icon: '⚡', name: 'Haute Volatilité', color: '#f59e0b' }
        };

        const config = regimeConfig[regime.type] || regimeConfig.sideways;

        // Icône et nom du régime
        const icon = this.querySelector('#regime-icon');
        const name = this.querySelector('#regime-name');
        const confidence = this.querySelector('#regime-confidence');
        const indicator = this.querySelector('#regime-indicator');

        icon.textContent = config.icon;
        name.textContent = config.name;
        confidence.textContent = this.formatPercentage(regime.confidence || 0);
        indicator.style.borderLeftColor = config.color;

        // Caractéristiques
        const volatilityChar = this.querySelector('#regime-volatility .char-value');
        const trendChar = this.querySelector('#regime-trend .char-value');
        const durationChar = this.querySelector('#regime-duration .char-value');

        volatilityChar.textContent = regime.volatility ? 
            this.formatNumber(regime.volatility * 100, 1) + '%' : '--';
        
        trendChar.textContent = regime.trend_strength ? 
            (regime.trend_strength > 0 ? 'Haussière' : 'Baissière') : 'Neutre';
            
        durationChar.textContent = regime.expected_duration || '--';

        // Timestamp
        const timestamp = this.querySelector('#regime-timestamp');
        timestamp.textContent = new Date().toLocaleTimeString();
    }

    subscribeToRegimeChanges() {
        this.regimeUnsubscribe = window.aiServiceManager.regimeService.subscribe((data) => {
            this.updateDisplay(data);
        });
    }

    cleanup() {
        super.cleanup();
        if (this.regimeUnsubscribe) {
            this.regimeUnsubscribe();
        }
    }
}

/**
 * Composant de matrice de corrélation
 */
class CorrelationMatrix extends AIComponent {
    static get observedAttributes() {
        return ['symbols', 'size'];
    }

    initialize() {
        this.symbols = (this.getAttribute('symbols') || 'BTC,ETH,ADA,DOT').split(',');
        this.size = this.getAttribute('size') || 'medium';
        
        this.innerHTML = this.getTemplate();
        this.loadData();
    }

    getTemplate() {
        return `
            <div class="ai-correlation-matrix ${this.size}">
                <div class="ai-component-header">
                    <h3 class="ai-component-title">
                        <span class="ai-icon">🔗</span>
                        Matrice de Corrélation
                    </h3>
                    <div class="matrix-controls">
                        <button class="btn-small" onclick="this.closest('correlation-matrix').refresh()">
                            🔄 Actualiser
                        </button>
                    </div>
                </div>
                
                <div class="ai-component-content">
                    <div class="correlation-heatmap" id="correlation-heatmap">
                        <div class="loading">Calcul des corrélations...</div>
                    </div>
                </div>
                
                <div class="ai-component-footer">
                    <div class="correlation-legend">
                        <span class="legend-item">
                            <span class="color-box" style="background: #ef4444"></span>
                            Corrélation négative
                        </span>
                        <span class="legend-item">
                            <span class="color-box" style="background: #6b7280"></span>
                            Neutre
                        </span>
                        <span class="legend-item">
                            <span class="color-box" style="background: #10b981"></span>
                            Corrélation positive
                        </span>
                    </div>
                    <small class="update-time">Mise à jour: <span id="corr-timestamp">--</span></small>
                </div>
            </div>
        `;
    }

    async loadData() {
        const heatmap = this.querySelector('#correlation-heatmap');
        
        try {
            heatmap.innerHTML = '<div class="loading">Calcul des corrélations...</div>';
            
            const data = await window.aiServiceManager.correlationService.getCurrentCorrelations(this.symbols);
            this.renderMatrix(data);

            // Timestamp
            const timestamp = this.querySelector('#corr-timestamp');
            timestamp.textContent = new Date().toLocaleTimeString();
        } catch (error) {
            debugLogger.error('Correlation data loading failed:', error);
            heatmap.innerHTML = '<div class="error">Erreur de chargement</div>';
        }
    }

    renderMatrix(data) {
        const heatmap = this.querySelector('#correlation-heatmap');
        
        if (!data || !data.correlation_matrix) {
            heatmap.innerHTML = '<div class="error">Données non disponibles</div>';
            return;
        }

        const matrix = data.correlation_matrix;
        const symbols = this.symbols;
        
        let html = '<table class="correlation-table">';
        
        // En-tête
        html += '<thead><tr><th></th>';
        symbols.forEach(symbol => {
            html += `<th>${symbol}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        // Lignes de données
        symbols.forEach((rowSymbol, i) => {
            html += `<tr><td class="row-header">${rowSymbol}</td>`;
            symbols.forEach((colSymbol, j) => {
                const correlation = matrix[rowSymbol] && matrix[rowSymbol][colSymbol] !== undefined ? 
                    matrix[rowSymbol][colSymbol] : 0;
                
                const intensity = Math.abs(correlation);
                const color = correlation > 0 ? 
                    `rgba(16, 185, 129, ${intensity})` : 
                    `rgba(239, 68, 68, ${intensity})`;
                
                html += `<td class="correlation-cell" style="background-color: ${color}" 
                            title="${rowSymbol} - ${colSymbol}: ${this.formatNumber(correlation, 2)}">
                            ${this.formatNumber(correlation, 2)}
                         </td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table>';
        heatmap.innerHTML = html;
    }

    refresh() {
        this.loadData();
    }
}

/**
 * Composant d'affichage du sentiment
 */
class SentimentIndicator extends AIComponent {
    static get observedAttributes() {
        return ['symbol', 'compact'];
    }

    initialize() {
        this.symbol = this.getAttribute('symbol') || 'BTC';
        this.compact = this.hasAttribute('compact');
        
        this.innerHTML = this.getTemplate();
        this.loadData();
        this.startAutoUpdate();
    }

    getTemplate() {
        const compactClass = this.compact ? 'compact' : '';
        
        return `
            <div class="ai-sentiment-indicator ${compactClass}">
                ${!this.compact ? `
                <div class="ai-component-header">
                    <h3 class="ai-component-title">
                        <span class="ai-icon">💭</span>
                        Sentiment - ${this.symbol}
                    </h3>
                </div>
                ` : ''}
                
                <div class="ai-component-content">
                    <div class="sentiment-gauge">
                        <div class="gauge-container">
                            <div class="gauge-arc" id="sentiment-arc"></div>
                            <div class="gauge-needle" id="sentiment-needle"></div>
                            <div class="gauge-center">
                                <div class="sentiment-score" id="sentiment-score">--</div>
                                <div class="sentiment-label" id="sentiment-label">Analyse...</div>
                            </div>
                        </div>
                    </div>
                    
                    ${!this.compact ? `
                    <div class="sentiment-details">
                        <div class="sentiment-sources">
                            <div class="source-item">
                                <span class="source-name">Twitter</span>
                                <span class="source-score" id="twitter-score">--</span>
                            </div>
                            <div class="source-item">
                                <span class="source-name">Reddit</span>
                                <span class="source-score" id="reddit-score">--</span>
                            </div>
                            <div class="source-item">
                                <span class="source-name">News</span>
                                <span class="source-score" id="news-score">--</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>
                
                ${!this.compact ? `
                <div class="ai-component-footer">
                    <small class="update-time">Mise à jour: <span id="sentiment-timestamp">--</span></small>
                </div>
                ` : ''}
            </div>
        `;
    }

    async loadData() {
        try {
            const data = await window.aiServiceManager.sentimentService.analyze([this.symbol]);
            this.updateDisplay(data);
        } catch (error) {
            debugLogger.error('Sentiment data loading failed:', error);
        }
    }

    updateDisplay(data) {
        if (!data || !data.sentiment) return;

        const sentimentData = data.sentiment[this.symbol];
        if (!sentimentData) return;

        const overallScore = sentimentData.overall_score || 0;
        
        // Score principal
        const scoreElement = this.querySelector('#sentiment-score');
        const labelElement = this.querySelector('#sentiment-label');
        
        scoreElement.textContent = this.formatNumber(overallScore, 1);
        
        // Label basé sur le score
        let label = 'Neutre';
        let color = '#6b7280';
        
        if (overallScore > 0.6) {
            label = 'Très Positif';
            color = '#10b981';
        } else if (overallScore > 0.2) {
            label = 'Positif';
            color = '#34d399';
        } else if (overallScore < -0.6) {
            label = 'Très Négatif';
            color = '#ef4444';
        } else if (overallScore < -0.2) {
            label = 'Négatif';
            color = '#f87171';
        }
        
        labelElement.textContent = label;
        labelElement.style.color = color;
        
        // Mise à jour de la jauge
        this.updateGauge(overallScore);
        
        // Sources individuelles (si pas compact)
        if (!this.compact && sentimentData.sources) {
            ['twitter', 'reddit', 'news'].forEach(source => {
                const scoreElement = this.querySelector(`#${source}-score`);
                if (scoreElement && sentimentData.sources[source]) {
                    scoreElement.textContent = this.formatNumber(sentimentData.sources[source], 1);
                    scoreElement.style.color = this.getValueColor(sentimentData.sources[source], { positive: 0.1, negative: -0.1 });
                }
            });
        }

        // Timestamp
        const timestamp = this.querySelector('#sentiment-timestamp');
        if (timestamp) {
            timestamp.textContent = new Date().toLocaleTimeString();
        }
    }

    updateGauge(score) {
        const needle = this.querySelector('#sentiment-needle');
        const arc = this.querySelector('#sentiment-arc');
        
        if (!needle || !arc) return;

        // Rotation de l'aiguille (-90° à +90°)
        const rotation = score * 90; // Score de -1 à 1 -> rotation de -90° à 90°
        needle.style.transform = `rotate(${rotation}deg)`;
        
        // Couleur de l'arc
        let color = '#6b7280';
        if (score > 0.2) color = '#10b981';
        else if (score < -0.2) color = '#ef4444';
        
        arc.style.borderColor = color;
    }

    startAutoUpdate(interval = 300000) { // 5 minutes
        this.updateInterval = setInterval(() => {
            this.loadData();
        }, interval);
    }
}

/**
 * Composant de suggestions de rééquilibrage
 */
class RebalancingSuggestions extends AIComponent {
    initialize() {
        this.innerHTML = this.getTemplate();
        this.loadSuggestions();
    }

    getTemplate() {
        return `
            <div class="ai-rebalancing-suggestions">
                <div class="ai-component-header">
                    <h3 class="ai-component-title">
                        <span class="ai-icon">⚖️</span>
                        Suggestions IA de Rééquilibrage
                    </h3>
                    <div class="rebalancing-controls">
                        <button class="btn-primary" onclick="this.closest('rebalancing-suggestions').refresh()">
                            🔄 Actualiser
                        </button>
                        <button class="btn-secondary" onclick="this.closest('rebalancing-suggestions').simulate()">
                            📊 Simuler
                        </button>
                    </div>
                </div>
                
                <div class="ai-component-content">
                    <div class="suggestions-list" id="suggestions-list">
                        <div class="loading">Génération des suggestions...</div>
                    </div>
                </div>
                
                <div class="ai-component-footer">
                    <div class="risk-warning">
                        ⚠️ Ces suggestions sont générées par IA et nécessitent une validation humaine
                    </div>
                    <small class="update-time">Généré: <span id="rebal-timestamp">--</span></small>
                </div>
            </div>
        `;
    }

    async loadSuggestions() {
        const suggestionsList = this.querySelector('#suggestions-list');
        
        try {
            suggestionsList.innerHTML = '<div class="loading">Génération des suggestions...</div>';
            
            // Récupérer le portfolio depuis le localStorage ou une API
            const portfolio = this.getPortfolioData();
            
            const data = await window.aiServiceManager.rebalancingService.getSuggestions(portfolio);
            this.renderSuggestions(data);

            // Timestamp
            const timestamp = this.querySelector('#rebal-timestamp');
            timestamp.textContent = new Date().toLocaleTimeString();
        } catch (error) {
            debugLogger.error('Rebalancing suggestions loading failed:', error);
            suggestionsList.innerHTML = '<div class="error">Erreur de génération des suggestions</div>';
        }
    }

    getPortfolioData() {
        // Placeholder - à remplacer par les vraies données du portfolio
        return {
            assets: {
                BTC: { allocation: 0.5, target_allocation: 0.4 },
                ETH: { allocation: 0.3, target_allocation: 0.35 },
                ADA: { allocation: 0.2, target_allocation: 0.25 }
            },
            total_value: 100000
        };
    }

    renderSuggestions(data) {
        const suggestionsList = this.querySelector('#suggestions-list');
        
        if (!data || !data.suggestions || data.suggestions.length === 0) {
            suggestionsList.innerHTML = '<div class="no-suggestions">Aucune suggestion de rééquilibrage nécessaire</div>';
            return;
        }

        let html = '<div class="suggestions-grid">';
        
        data.suggestions.forEach(suggestion => {
            const actionIcon = suggestion.action === 'buy' ? '📈' : '📉';
            const actionColor = suggestion.action === 'buy' ? 'var(--color-success)' : 'var(--color-danger)';
            
            html += `
                <div class="suggestion-card">
                    <div class="suggestion-header">
                        <div class="asset-info">
                            <span class="asset-symbol">${suggestion.asset}</span>
                            <span class="action-badge" style="color: ${actionColor}">
                                ${actionIcon} ${suggestion.action.toUpperCase()}
                            </span>
                        </div>
                        <div class="confidence-score">
                            ${this.formatPercentage(suggestion.confidence || 0)}
                        </div>
                    </div>
                    
                    <div class="suggestion-details">
                        <div class="detail-item">
                            <span class="label">Montant:</span>
                            <span class="value">${this.formatNumber(suggestion.amount)} ${suggestion.asset}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Impact:</span>
                            <span class="value">${this.formatPercentage(suggestion.impact_score)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Timing:</span>
                            <span class="value">${suggestion.timing || 'Immédiat'}</span>
                        </div>
                    </div>
                    
                    <div class="suggestion-reasoning">
                        <small>${suggestion.reasoning || 'Optimisation de l\'allocation basée sur les prédictions IA'}</small>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        suggestionsList.innerHTML = html;
    }

    refresh() {
        this.loadSuggestions();
    }

    async simulate() {
        try {
            const portfolio = this.getPortfolioData();
            const suggestions = []; // Récupérer les suggestions actuelles
            
            const simulation = await window.aiServiceManager.rebalancingService.simulateRebalancing(portfolio, suggestions);
            
            // Afficher les résultats de simulation dans une modal ou un overlay
            this.showSimulationResults(simulation);
        } catch (error) {
            debugLogger.error('Simulation failed:', error);
            alert('Erreur lors de la simulation');
        }
    }

    showSimulationResults(simulation) {
        // Implémentation d'une modal de résultats
        (window.debugLogger?.debug || console.log)('Simulation results:', simulation);
        alert(`Simulation terminée:\nGain estimé: ${this.formatPercentage(simulation.expected_return || 0)}\nRisque: ${this.formatPercentage(simulation.risk_score || 0)}`);
    }
}

// Enregistrement des Web Components
customElements.define('volatility-display', VolatilityDisplay);
customElements.define('market-regime-display', MarketRegimeDisplay);
customElements.define('correlation-matrix', CorrelationMatrix);
customElements.define('sentiment-indicator', SentimentIndicator);
customElements.define('rebalancing-suggestions', RebalancingSuggestions);

// Exportation pour utilisation en modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        AIComponent,
        VolatilityDisplay,
        MarketRegimeDisplay,
        CorrelationMatrix,
        SentimentIndicator,
        RebalancingSuggestions
    };
}

// Utilitaires globaux pour l'initialisation des composants
window.AIComponents = {
    /**
     * Initialiser tous les composants IA dans un conteneur
     */
    initializeAll(container = document) {
        const components = container.querySelectorAll('volatility-display, market-regime-display, correlation-matrix, sentiment-indicator, rebalancing-suggestions');
        (window.debugLogger?.debug || console.log)(`🔧 Initializing ${components.length} AI components`);
        return components;
    },

    /**
     * Créer un composant programmatiquement
     */
    create(type, attributes = {}) {
        const element = document.createElement(type);
        Object.entries(attributes).forEach(([key, value]) => {
            element.setAttribute(key, value);
        });
        return element;
    }
};