/**
 * GlobalInsightML.js - Composant Global Insight ML unifié
 * Decision Index + résumé SMART + cap effectif + deltas non exécutables
 * Utilisé par ai-dashboard.html et analytics-unified.html
 */

class GlobalInsightML {
    constructor() {
        this.store = null;
    }

    /**
     * Initialise le composant avec le store
     */
    init(store) {
        this.store = store;
    }

    /**
     * Rendu du Global Insight dans un conteneur
     * @param {HTMLElement} container - Élément DOM conteneur
     * @param {Object} options - Options de rendu
     */
    render(container, options = {}) {
        if (!container) return;

        try {
            const data = this.gatherData(options);
            container.innerHTML = this.generateHTML(data, options);
            this.attachEventListeners(container);

            console.debug('🧭 GlobalInsightML rendered:', data);

        } catch (error) {
            console.warn('Failed to render Global Insight ML:', error);
            container.innerHTML = `<div class="error">Global Insight unavailable</div>`;
        }
    }

    /**
     * Collecte les données depuis le store
     */
    gatherData(options) {
        const data = {
            decisionScore: null,
            confidence: null,
            recommendation: null,
            capEffective: null,
            capEngine: null,
            capAlert: null,
            nonExecutableDelta: null,
            policyMode: null,
            freezeStatus: null,
            lastUpdate: null
        };

        if (this.store) {
            // Decision Engine data
            const governance = this.store.get('governance') || {};
            const mlSignals = governance.ml_signals || {};
            const activePolicy = governance.active_policy || {};

            data.decisionScore = mlSignals.decision_score || governance.decision_score;
            data.confidence = mlSignals.confidence || governance.confidence;
            data.capEffective = activePolicy.cap_daily;
            data.capEngine = governance.cap_engine;
            data.capAlert = governance.cap_alert;
            data.policyMode = activePolicy.mode || 'manual';
            data.freezeStatus = governance.freeze_status;
            data.lastUpdate = mlSignals.timestamp;

            // Non executable delta
            const portfolioData = this.store.get('portfolio') || {};
            data.nonExecutableDelta = portfolioData.non_executable_delta_sum || 0;

            // Generate recommendation based on score
            data.recommendation = this.generateRecommendation(data.decisionScore, data.confidence);
        }

        // Override avec les options si fournies
        Object.keys(data).forEach(key => {
            if (options[key] !== undefined) {
                data[key] = options[key];
            }
        });

        return data;
    }

    /**
     * Génère la recommandation basée sur le score et la confidence
     */
    generateRecommendation(score, confidence) {
        if (!score || !confidence) return '⏳ Analyse en cours...';

        const confLevel = confidence * 100;
        const scoreValue = typeof score === 'object' ? score.value || score.score : score;

        if (confLevel < 50) return '🔍 Confidence faible - Monitoring';

        if (scoreValue >= 70) return '⚠️ Alléger 10–20%';
        if (scoreValue <= 35) return '🟢 DCA prudent';
        return '⏸️ Neutre / Attente';
    }

    /**
     * Génère le HTML du composant
     */
    generateHTML(data, options = {}) {
        const isCompact = options.compact || false;
        const showDetails = options.showDetails !== false;

        return `
            <div class="global-insight-ml">
                <!-- Header avec score et confidence -->
                <div class="gi-header">
                    <div class="gi-score-section">
                        <div class="gi-label">Decision Index</div>
                        <div class="gi-score" id="gi-score">${this.formatScore(data.decisionScore)}</div>
                        <div class="gi-confidence" id="gi-confidence">
                            ${data.confidence ? `Conf: ${Math.round(data.confidence * 100)}%` : ''}
                        </div>
                    </div>

                    ${!isCompact ? `
                    <div class="gi-metrics">
                        <div class="gi-metric">
                            <span class="label">Policy:</span>
                            <span class="value" id="gi-policy-mode">${this.formatPolicyMode(data.policyMode)}</span>
                        </div>
                        <div class="gi-metric">
                            <span class="label">Cap Effectif:</span>
                            <span class="value" id="gi-cap-effective">${this.formatCap(data.capEffective)}</span>
                        </div>
                        ${data.freezeStatus ? `
                        <div class="gi-metric gi-freeze">
                            <span class="freeze-status">🧊 ${data.freezeStatus.toUpperCase()}</span>
                        </div>
                        ` : ''}
                    </div>
                    ` : ''}
                </div>

                <!-- Recommandation -->
                <div class="gi-recommendation" id="gi-recommendation">
                    ${data.recommendation}
                </div>

                ${showDetails ? `
                <!-- Détails caps et deltas -->
                <div class="gi-details">
                    <div class="gi-caps">
                        <div class="cap-item">
                            <span class="cap-label">Engine:</span>
                            <span class="cap-value">${this.formatCap(data.capEngine)}</span>
                        </div>
                        ${data.capAlert ? `
                        <div class="cap-item cap-alert">
                            <span class="cap-label">Alert:</span>
                            <span class="cap-value">${this.formatCap(data.capAlert)}</span>
                        </div>
                        ` : ''}
                    </div>

                    ${data.nonExecutableDelta ? `
                    <div class="gi-delta">
                        <span class="delta-label">Non-exec Δ:</span>
                        <span class="delta-value ${data.nonExecutableDelta > 1000 ? 'high' : ''}" id="gi-non-exec-delta">
                            ${this.formatDelta(data.nonExecutableDelta)}
                        </span>
                    </div>
                    ` : ''}
                </div>
                ` : ''}

                <!-- Timestamp -->
                ${data.lastUpdate ? `
                <div class="gi-timestamp">
                    Last update: ${new Date(data.lastUpdate).toLocaleTimeString('fr-FR')}
                </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Formate le score de décision
     */
    formatScore(score) {
        if (!score) return '--';

        const value = typeof score === 'object' ? score.value || score.score : score;
        return Math.round(value);
    }

    /**
     * Formate le mode de policy
     */
    formatPolicyMode(mode) {
        if (!mode) return 'Manual';

        const modes = {
            'manual': 'Manual',
            'ai_assisted': 'AI Assist',
            'full_ai': 'Full AI',
            'freeze': 'Freeze'
        };

        return modes[mode] || mode;
    }

    /**
     * Formate un cap en pourcentage
     */
    formatCap(cap) {
        if (cap == null) return '--';
        return `${Math.round(cap * 100)}%`;
    }

    /**
     * Formate un delta en USD
     */
    formatDelta(delta) {
        if (!delta) return '$0';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0
        }).format(Math.abs(delta));
    }

    /**
     * Attache les event listeners
     */
    attachEventListeners(container) {
        // Click sur le score pour plus de détails
        const scoreEl = container.querySelector('.gi-score');
        if (scoreEl) {
            scoreEl.style.cursor = 'pointer';
            scoreEl.title = 'Click pour détails ML';
            scoreEl.onclick = () => this.showScoreDetails();
        }

        // Click sur la recommandation pour explications XAI
        const recoEl = container.querySelector('.gi-recommendation');
        if (recoEl) {
            recoEl.style.cursor = 'pointer';
            recoEl.title = 'Click pour explications';
            recoEl.onclick = () => this.showXAIExplanation();
        }
    }

    /**
     * Affiche les détails du score
     */
    showScoreDetails() {
        // TODO: Ouvrir modal avec breakdown du score
        console.log('🔍 Score details requested');
    }

    /**
     * Affiche l'explication XAI
     */
    showXAIExplanation() {
        // TODO: Ouvrir modal XAI
        console.log('🤖 XAI explanation requested');
    }

    /**
     * Met à jour automatiquement un conteneur à partir du store
     */
    setupAutoUpdate(container, options = {}) {
        if (!this.store) return;

        // Rendu initial
        this.render(container, options);

        // Subscribe aux changements du store
        this.store.subscribe(() => {
            this.render(container, options);
        });

        // Écoute les événements storage (cross-tab)
        window.addEventListener('storage', () => {
            this.render(container, options);
        });

        // Refresh périodique (toutes les 30s)
        setInterval(() => {
            this.render(container, options);
        }, 30000);
    }
}

// Export global
window.GlobalInsightML = GlobalInsightML;

// Export module ES6
export { GlobalInsightML };