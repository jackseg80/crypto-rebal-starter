/**
 * OpsKpis.js - Composant KPIs Opérationnels unifié
 * cap_effectif vs cap_engine, non_executable_delta_sum, stale_duration, hystérésis status
 * Utilisé par ai-dashboard.html et analytics-unified.html
 */

class OpsKpis {
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
     * Rendu des KPIs Ops dans un conteneur
     * @param {HTMLElement} container - Élément DOM conteneur
     * @param {Object} options - Options de rendu
     */
    render(container, options = {}) {
        if (!container) return;

        try {
            this.fetchOpsData().then(data => {
                container.innerHTML = this.generateHTML(data, options);
                this.attachEventListeners(container, data);
            });

            console.debug('📊 OpsKpis render initiated');

        } catch (error) {
            console.warn('Failed to render Ops KPIs:', error);
            container.innerHTML = `<div class="error">Ops KPIs unavailable</div>`;
        }
    }

    /**
     * Récupère les données opérationnelles
     */
    async fetchOpsData() {
        try {
            const data = {
                caps: await this.fetchCapsData(),
                deltas: await this.fetchDeltasData(),
                hystérésis: await this.fetchHysteresisData(),
                staleDuration: await this.fetchStaleDuration(),
                systemHealth: await this.fetchSystemHealth()
            };

            return data;

        } catch (error) {
            console.warn('Error fetching ops data:', error);
            return this.getDefaultOpsData();
        }
    }

    /**
     * Récupère les données des caps
     */
    async fetchCapsData() {
        try {
            // Depuis governance endpoint ou store
            if (this.store) {
                const governance = this.store.get('governance') || {};
                const activePolicy = governance.active_policy || {};

                return {
                    capEffective: activePolicy.cap_daily,
                    capEngine: governance.cap_engine,
                    capAlert: governance.cap_alert,
                    capError: governance.cap_error,
                    capStale: governance.cap_stale,
                    priorityOrder: ['error', 'stale', 'alert', 'engine'],
                    appliedRule: this.determineAppliedRule(governance)
                };
            }

            // Fallback API call
            const response = await fetch(`${this.apiBaseUrl}/api/governance/state`);
            if (response.ok) {
                const data = await response.json();
                return this.processCapsFromAPI(data);
            }

        } catch (error) {
            console.warn('Error fetching caps data:', error);
        }

        return { capEffective: null, capEngine: null };
    }

    /**
     * Détermine quelle règle de cap est appliquée
     */
    determineAppliedRule(governance) {
        const caps = [
            { name: 'ERROR', value: governance.cap_error, priority: 1 },
            { name: 'STALE', value: governance.cap_stale, priority: 2 },
            { name: 'ALERT', value: governance.cap_alert, priority: 3 },
            { name: 'ENGINE', value: governance.cap_engine, priority: 4 }
        ];

        // Trouve le cap le plus restrictif (plus petit et défini)
        const activeCaps = caps.filter(cap => cap.value != null && cap.value > 0);
        if (activeCaps.length === 0) return null;

        const appliedCap = activeCaps.reduce((min, cap) =>
            cap.value < min.value ? cap : min
        );

        return appliedCap.name;
    }

    /**
     * Récupère les données des deltas non exécutables
     */
    async fetchDeltasData() {
        try {
            if (this.store) {
                const portfolio = this.store.get('portfolio') || {};
                return {
                    nonExecutableSum: portfolio.non_executable_delta_sum || 0,
                    byAsset: portfolio.non_executable_by_asset || {},
                    trend: portfolio.non_executable_trend || 'stable'
                };
            }

        } catch (error) {
            console.warn('Error fetching deltas data:', error);
        }

        return { nonExecutableSum: 0 };
    }

    /**
     * Récupère les données d'hystérésis
     */
    async fetchHysteresisData() {
        try {
            if (this.store) {
                const governance = this.store.get('governance') || {};
                return {
                    varHysteresis: {
                        current: governance.var_current,
                        threshold: governance.var_threshold,
                        status: governance.var_hysteresis_status, // 'normal', 'prudent'
                        entryThreshold: 0.04, // 4%
                        exitThreshold: 0.035  // 3.5%
                    },
                    staleHysteresis: {
                        current: governance.stale_duration_minutes,
                        status: governance.stale_hysteresis_status,
                        entryThreshold: 60, // 60 min
                        exitThreshold: 30   // 30 min
                    },
                    contradictionHysteresis: {
                        current: governance.contradiction_index,
                        status: governance.contradiction_hysteresis_status,
                        entryThreshold: 0.45, // 45%
                        exitThreshold: 0.40   // 40%
                    }
                };
            }

        } catch (error) {
            console.warn('Error fetching hysteresis data:', error);
        }

        return {};
    }

    /**
     * Récupère la durée de stale moyenne
     */
    async fetchStaleDuration() {
        try {
            // Calculé sur les dernières 24h
            if (this.store) {
                const governance = this.store.get('governance') || {};
                return {
                    avgDuration: governance.stale_duration_avg_minutes || 0,
                    maxDuration: governance.stale_duration_max_minutes || 0,
                    incidents24h: governance.stale_incidents_24h || 0,
                    target: 10 // Target: <10 min/j
                };
            }

        } catch (error) {
            console.warn('Error fetching stale duration:', error);
        }

        return { avgDuration: 0 };
    }

    /**
     * Récupère les données de santé système
     */
    async fetchSystemHealth() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/health`);
            if (response.ok) {
                const data = await response.json();
                return {
                    apiLatencyP95: data.api_latency_p95 || null,
                    errorRate: data.error_rate || 0,
                    lastHealthCheck: data.timestamp || null
                };
            }

        } catch (error) {
            console.warn('Error fetching system health:', error);
        }

        return {};
    }

    /**
     * Données par défaut
     */
    getDefaultOpsData() {
        return {
            caps: { capEffective: null, capEngine: null },
            deltas: { nonExecutableSum: 0 },
            hystérésis: {},
            staleDuration: { avgDuration: 0 },
            systemHealth: {}
        };
    }

    /**
     * Génère le HTML du composant
     */
    generateHTML(data, options = {}) {
        const isCompact = options.compact || false;

        return `
            <div class="ops-kpis">
                <!-- Caps comparison -->
                <div class="kpi-section caps-section">
                    <h4 class="kpi-title">📊 Caps & Limits</h4>
                    <div class="caps-comparison">
                        <div class="cap-item primary">
                            <div class="cap-label">Cap Effectif</div>
                            <div class="cap-value effective">${this.formatCap(data.caps.capEffective)}</div>
                            ${data.caps.appliedRule ? `<div class="cap-rule">(${data.caps.appliedRule})</div>` : ''}
                        </div>
                        <div class="cap-separator">vs</div>
                        <div class="cap-item">
                            <div class="cap-label">Cap Engine</div>
                            <div class="cap-value engine">${this.formatCap(data.caps.capEngine)}</div>
                        </div>
                    </div>

                    ${!isCompact && data.caps.appliedRule ? `
                    <div class="caps-breakdown">
                        <div class="caps-grid">
                            <div class="cap-detail ${data.caps.appliedRule === 'ERROR' ? 'active' : ''}">
                                <span class="cap-type">ERROR (5%)</span>
                                <span class="cap-val">${this.formatCap(data.caps.capError)}</span>
                            </div>
                            <div class="cap-detail ${data.caps.appliedRule === 'STALE' ? 'active' : ''}">
                                <span class="cap-type">STALE (8%)</span>
                                <span class="cap-val">${this.formatCap(data.caps.capStale)}</span>
                            </div>
                            <div class="cap-detail ${data.caps.appliedRule === 'ALERT' ? 'active' : ''}">
                                <span class="cap-type">ALERT</span>
                                <span class="cap-val">${this.formatCap(data.caps.capAlert)}</span>
                            </div>
                            <div class="cap-detail ${data.caps.appliedRule === 'ENGINE' ? 'active' : ''}">
                                <span class="cap-type">ENGINE</span>
                                <span class="cap-val">${this.formatCap(data.caps.capEngine)}</span>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>

                <!-- Deltas non exécutables -->
                <div class="kpi-section deltas-section">
                    <h4 class="kpi-title">⚖️ Non-executable Δ</h4>
                    <div class="delta-display">
                        <div class="delta-value ${this.getDeltaStatusClass(data.deltas.nonExecutableSum)}">
                            ${this.formatDelta(data.deltas.nonExecutableSum)}
                        </div>
                        <div class="delta-trend">${this.formatTrend(data.deltas.trend)}</div>
                    </div>
                    ${data.deltas.nonExecutableSum > 1000 ? `
                    <div class="delta-warning">⚠️ High non-executable delta</div>
                    ` : ''}
                </div>

                ${!isCompact ? `
                <!-- Hystérésis Status -->
                ${Object.keys(data.hystérésis).length > 0 ? `
                <div class="kpi-section hysteresis-section">
                    <h4 class="kpi-title">🎯 Hystérésis Status</h4>
                    <div class="hysteresis-grid">
                        ${data.hystérésis.varHysteresis ? `
                        <div class="hysteresis-item">
                            <div class="hyst-label">VaR</div>
                            <div class="hyst-status ${data.hystérésis.varHysteresis.status}">
                                ${data.hystérésis.varHysteresis.status.toUpperCase()}
                            </div>
                            <div class="hyst-value">${this.formatPercentage(data.hystérésis.varHysteresis.current)}</div>
                        </div>
                        ` : ''}

                        ${data.hystérésis.staleHysteresis ? `
                        <div class="hysteresis-item">
                            <div class="hyst-label">Stale</div>
                            <div class="hyst-status ${data.hystérésis.staleHysteresis.status || 'normal'}">
                                ${(data.hystérésis.staleHysteresis.status || 'normal').toUpperCase()}
                            </div>
                            <div class="hyst-value">${data.hystérésis.staleHysteresis.current || 0}min</div>
                        </div>
                        ` : ''}

                        ${data.hystérésis.contradictionHysteresis ? `
                        <div class="hysteresis-item">
                            <div class="hyst-label">Contrad</div>
                            <div class="hyst-status ${data.hystérésis.contradictionHysteresis.status || 'normal'}">
                                ${(data.hystérésis.contradictionHysteresis.status || 'normal').toUpperCase()}
                            </div>
                            <div class="hyst-value">${this.formatPercentage(data.hystérésis.contradictionHysteresis.current)}</div>
                        </div>
                        ` : ''}
                    </div>
                </div>
                ` : ''}

                <!-- Stale Duration -->
                <div class="kpi-section stale-section">
                    <h4 class="kpi-title">⏱️ Stale Duration</h4>
                    <div class="stale-metrics">
                        <div class="stale-metric">
                            <div class="stale-value ${data.staleDuration.avgDuration > 10 ? 'warning' : 'good'}">
                                ${data.staleDuration.avgDuration}min
                            </div>
                            <div class="stale-label">Avg/Day</div>
                        </div>
                        ${data.staleDuration.incidents24h ? `
                        <div class="stale-metric">
                            <div class="stale-value">${data.staleDuration.incidents24h}</div>
                            <div class="stale-label">Incidents 24h</div>
                        </div>
                        ` : ''}
                    </div>
                    <div class="stale-target">Target: &lt;${data.staleDuration.target}min/day</div>
                </div>

                <!-- System Health -->
                ${data.systemHealth.apiLatencyP95 ? `
                <div class="kpi-section health-section">
                    <h4 class="kpi-title">🏥 System Health</h4>
                    <div class="health-metrics">
                        <div class="health-metric">
                            <div class="health-value ${data.systemHealth.apiLatencyP95 > 300 ? 'warning' : 'good'}">
                                ${data.systemHealth.apiLatencyP95}ms
                            </div>
                            <div class="health-label">Latency p95</div>
                        </div>
                        <div class="health-metric">
                            <div class="health-value ${data.systemHealth.errorRate > 0.5 ? 'warning' : 'good'}">
                                ${this.formatPercentage(data.systemHealth.errorRate / 100)}
                            </div>
                            <div class="health-label">Error Rate</div>
                        </div>
                    </div>
                </div>
                ` : ''}
                ` : ''}
            </div>
        `;
    }

    /**
     * Utilitaires de formatage
     */
    formatCap(cap) {
        if (cap == null) return '--';
        return `${Math.round(cap * 100)}%`;
    }

    formatDelta(delta) {
        if (!delta) return '$0';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0
        }).format(Math.abs(delta));
    }

    formatPercentage(value) {
        if (value == null) return '--';
        return `${Math.round(value * 100)}%`;
    }

    formatTrend(trend) {
        const trends = {
            'up': '📈 Rising',
            'down': '📉 Falling',
            'stable': '➡️ Stable'
        };
        return trends[trend] || '';
    }

    getDeltaStatusClass(delta) {
        if (!delta) return 'good';
        if (Math.abs(delta) > 5000) return 'critical';
        if (Math.abs(delta) > 1000) return 'warning';
        return 'good';
    }

    /**
     * Attache les event listeners
     */
    attachEventListeners(container, data) {
        // Click sur caps pour drill-down
        const capItems = container.querySelectorAll('.cap-item');
        capItems.forEach(item => {
            item.style.cursor = 'pointer';
            item.onclick = () => this.showCapDetails(data.caps);
        });

        // Click sur delta pour détail par asset
        const deltaValue = container.querySelector('.delta-value');
        if (deltaValue && data.deltas.byAsset) {
            deltaValue.style.cursor = 'pointer';
            deltaValue.onclick = () => this.showDeltaBreakdown(data.deltas);
        }
    }

    /**
     * Affiche les détails des caps
     */
    showCapDetails(capsData) {
        console.log('🔍 Caps details requested:', capsData);
        // TODO: Ouvrir modal avec historique des caps
    }

    /**
     * Affiche le détail des deltas par asset
     */
    showDeltaBreakdown(deltasData) {
        console.log('📊 Delta breakdown requested:', deltasData);
        // TODO: Ouvrir modal avec breakdown par asset
    }

    /**
     * Met à jour automatiquement un conteneur
     */
    setupAutoUpdate(container, options = {}) {
        // Rendu initial
        this.render(container, options);

        // Subscribe aux changements du store
        if (this.store) {
            this.store.subscribe(() => {
                this.render(container, options);
            });
        }

        // Refresh périodique (toutes les minute)
        setInterval(() => {
            this.render(container, options);
        }, 60000);
    }
}

// Export global
window.OpsKpis = OpsKpis;

// Export module ES6
export { OpsKpis };