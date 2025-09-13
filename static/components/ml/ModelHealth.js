/**
 * ModelHealth.js - Composant Model Health unifié
 * Model version, calibration, Brier/ECE, PSI/drift, stale/error, prochains jobs
 * Utilisé par ai-dashboard.html et analytics-unified.html
 */

class ModelHealth {
    constructor() {
        this.store = null;
        this.apiBaseUrl = window.globalConfig?.get('api_base_url') || '';
    }

    /**
     * Initialise le composant avec le store
     */
    init(store) {
        this.store = store;
    }

    /**
     * Rendu du Model Health dans un conteneur
     * @param {HTMLElement} container - Élément DOM conteneur
     * @param {Object} options - Options de rendu
     */
    render(container, options = {}) {
        if (!container) return;

        try {
            this.fetchModelHealthData().then(data => {
                container.innerHTML = this.generateHTML(data, options);
                this.attachEventListeners(container, data, options);
            });

            console.debug('🩺 ModelHealth render initiated');

        } catch (error) {
            console.warn('Failed to render Model Health:', error);
            container.innerHTML = `<div class="error">Model Health unavailable</div>`;
        }
    }

    /**
     * Récupère les données de santé des modèles
     */
    async fetchModelHealthData() {
        try {
            // Données depuis les endpoints ML
            const [statusResponse, registryResponse] = await Promise.all([
                fetch(`${this.apiBaseUrl}/api/ml/status`),
                fetch(`${this.apiBaseUrl}/api/ml/models/registry`).catch(() => null)
            ]);

            const statusData = statusResponse.ok ? await statusResponse.json() : {};
            const registryData = registryResponse?.ok ? await registryResponse.json() : {};

            return this.processModelHealthData(statusData, registryData);

        } catch (error) {
            console.warn('Error fetching model health data:', error);
            return this.getDefaultHealthData();
        }
    }

    /**
     * Traite et structure les données de santé des modèles
     */
    processModelHealthData(statusData, registryData) {
        return {
            models: this.extractModelsData(statusData, registryData),
            globalStats: {
                totalModels: statusData.models_loaded || 0,
                activeModels: statusData.active_models || 0,
                avgConfidence: statusData.avg_confidence || 0,
                lastUpdate: statusData.last_update || null
            },
            calibration: this.extractCalibrationData(statusData),
            performance: this.extractPerformanceData(statusData),
            jobs: this.extractJobsData(statusData)
        };
    }

    /**
     * Extrait les données des modèles individuels
     */
    extractModelsData(statusData, registryData) {
        const models = [];

        // Modèles principaux
        const modelTypes = ['volatility', 'regime', 'correlation', 'sentiment'];

        modelTypes.forEach(type => {
            const modelData = statusData[`${type}_model`] || {};
            models.push({
                name: this.formatModelName(type),
                type: type,
                version: modelData.version || registryData?.models?.[type]?.version || '1.0.0',
                status: modelData.status || 'unknown',
                lastTrained: modelData.last_trained || null,
                accuracy: modelData.accuracy || null,
                confidence: modelData.confidence || null,
                drift: modelData.drift_score || null,
                stale: this.isModelStale(modelData)
            });
        });

        return models;
    }

    /**
     * Extrait les données de calibration
     */
    extractCalibrationData(statusData) {
        return {
            brierScore: statusData.calibration?.brier_score || null,
            ece: statusData.calibration?.ece || null, // Expected Calibration Error
            calibrationVersion: statusData.calibration?.version || null,
            lastCalibration: statusData.calibration?.last_update || null
        };
    }

    /**
     * Extrait les données de performance
     */
    extractPerformanceData(statusData) {
        return {
            psi: statusData.performance?.psi || null, // Population Stability Index
            overallDrift: statusData.performance?.overall_drift || null,
            errorRate: statusData.performance?.error_rate || null,
            avgLatency: statusData.performance?.avg_latency || null
        };
    }

    /**
     * Extrait les informations sur les jobs
     */
    extractJobsData(statusData) {
        return {
            nextRetraining: statusData.jobs?.next_retraining || null,
            nextCalibration: statusData.jobs?.next_calibration || null,
            queueLength: statusData.jobs?.queue_length || 0,
            runningJobs: statusData.jobs?.running || []
        };
    }

    /**
     * Formate le nom du modèle
     */
    formatModelName(type) {
        const names = {
            'volatility': 'Volatility LSTM',
            'regime': 'Regime HMM',
            'correlation': 'Correlation Transformer',
            'sentiment': 'Sentiment Composite'
        };
        return names[type] || type;
    }

    /**
     * Vérifie si un modèle est stale
     */
    isModelStale(modelData) {
        if (!modelData.last_trained) return true;

        const lastTrained = new Date(modelData.last_trained);
        const now = new Date();
        const hoursAgo = (now - lastTrained) / (1000 * 60 * 60);

        return hoursAgo > 24; // Stale si pas d'entraînement depuis 24h
    }

    /**
     * Données par défaut en cas d'erreur
     */
    getDefaultHealthData() {
        return {
            models: [
                { name: 'Volatility LSTM', type: 'volatility', status: 'unknown', stale: true },
                { name: 'Regime HMM', type: 'regime', status: 'unknown', stale: true },
                { name: 'Correlation Transformer', type: 'correlation', status: 'unknown', stale: true },
                { name: 'Sentiment Composite', type: 'sentiment', status: 'unknown', stale: true }
            ],
            globalStats: { totalModels: 0, activeModels: 0, avgConfidence: 0 },
            calibration: {},
            performance: {},
            jobs: {}
        };
    }

    /**
     * Génère le HTML du composant
     */
    generateHTML(data, options = {}) {
        const isCompact = options.compact || false;

        return `
            <div class="model-health">
                <!-- Stats globales -->
                <div class="health-header">
                    <div class="health-stat">
                        <div class="stat-value">${data.globalStats.activeModels}/${data.globalStats.totalModels}</div>
                        <div class="stat-label">Modèles Actifs</div>
                    </div>
                    <div class="health-stat">
                        <div class="stat-value">${this.formatPercentage(data.globalStats.avgConfidence)}</div>
                        <div class="stat-label">Conf. Moyenne</div>
                    </div>
                    ${data.calibration.brierScore ? `
                    <div class="health-stat">
                        <div class="stat-value">${this.formatScore(data.calibration.brierScore, 3)}</div>
                        <div class="stat-label">Brier Score</div>
                    </div>
                    ` : ''}
                    ${data.performance.psi ? `
                    <div class="health-stat ${data.performance.psi > 0.2 ? 'warning' : ''}">
                        <div class="stat-value">${this.formatScore(data.performance.psi, 3)}</div>
                        <div class="stat-label">PSI Drift</div>
                    </div>
                    ` : ''}
                </div>

                ${!isCompact ? `
                <!-- Modèles individuels -->
                <div class="models-grid">
                    ${data.models.map(model => `
                        <div class="model-card ${this.getModelStatusClass(model)}">
                            <div class="model-header">
                                <div class="model-name">${model.name}</div>
                                <div class="model-status">${this.getStatusIcon(model.status)}</div>
                            </div>
                            <div class="model-details">
                                <div class="model-metric">
                                    <span>v${model.version || '1.0.0'}</span>
                                    ${model.confidence ? `<span>Conf: ${this.formatPercentage(model.confidence)}</span>` : ''}
                                </div>
                                ${model.drift ? `
                                <div class="model-metric ${model.drift > 0.3 ? 'warning' : ''}">
                                    Drift: ${this.formatScore(model.drift, 3)}
                                </div>
                                ` : ''}
                                ${model.stale ? '<div class="model-warning">⚠️ Stale</div>' : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>

                <!-- Jobs et calibration -->
                <div class="health-footer">
                    ${data.jobs.nextRetraining ? `
                    <div class="job-info">
                        <span class="job-label">Next Training:</span>
                        <span class="job-time">${this.formatRelativeTime(data.jobs.nextRetraining)}</span>
                    </div>
                    ` : ''}

                    ${data.jobs.queueLength > 0 ? `
                    <div class="job-info">
                        <span class="job-label">Queue:</span>
                        <span class="job-queue">${data.jobs.queueLength} jobs</span>
                    </div>
                    ` : ''}

                    ${data.calibration.lastCalibration ? `
                    <div class="calibration-info">
                        <span class="cal-label">Last Calibration:</span>
                        <span class="cal-time">${this.formatRelativeTime(data.calibration.lastCalibration)}</span>
                    </div>
                    ` : ''}
                </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Utilitaires de formatage
     */
    formatPercentage(value) {
        if (!value) return '--';
        return `${Math.round(value * 100)}%`;
    }

    formatScore(value, decimals = 2) {
        if (value == null) return '--';
        return value.toFixed(decimals);
    }

    formatRelativeTime(timestamp) {
        if (!timestamp) return '--';

        const now = new Date();
        const target = new Date(timestamp);
        const diffMs = target - now;
        const diffHours = Math.abs(diffMs) / (1000 * 60 * 60);

        if (diffHours < 1) return 'Soon';
        if (diffHours < 24) return `${Math.round(diffHours)}h`;
        return `${Math.round(diffHours / 24)}d`;
    }

    getModelStatusClass(model) {
        if (model.stale) return 'stale';
        if (model.status === 'error') return 'error';
        if (model.status === 'active' || model.status === 'ready') return 'active';
        return 'inactive';
    }

    getStatusIcon(status) {
        const icons = {
            'active': '🟢',
            'ready': '🟢',
            'training': '🔄',
            'error': '🔴',
            'inactive': '⚪',
            'unknown': '❓'
        };
        return icons[status] || '❓';
    }

    /**
     * Attache les event listeners
     */
    attachEventListeners(container, data, options = {}) {
        // Click sur les modèles pour plus de détails
        container.querySelectorAll('.model-card').forEach((card, index) => {
            card.style.cursor = 'pointer';
            card.onclick = () => this.showModelDetails(data.models[index]);
        });

        // Actions rapides
        if (options.showActions) {
            // TODO: Ajouter boutons retrain, recalibrate, etc.
        }
    }

    /**
     * Affiche les détails d'un modèle
     */
    showModelDetails(model) {
        console.log('🔍 Model details requested:', model);
        // TODO: Ouvrir modal avec détails complets
    }

    /**
     * Met à jour automatiquement un conteneur
     */
    setupAutoUpdate(container, options = {}) {
        // Rendu initial
        this.render(container, options);

        // Refresh périodique (toutes les 2 minutes)
        setInterval(() => {
            this.render(container, options);
        }, 120000);
    }
}

// Export global
window.ModelHealth = ModelHealth;

// Export module ES6
export { ModelHealth };