/**
 * ML Components Index
 * Point d'entrée unifié pour tous les composants ML factorisés
 */

// Import des composants
import { BadgesML } from './BadgesML.js';
import { GlobalInsightML } from './GlobalInsightML.js';
import { ModelHealth } from './ModelHealth.js';
import { OpsKpis } from './OpsKpis.js';

/**
 * Classe principale pour gérer tous les composants ML
 */
class MLComponents {
    constructor(store = null) {
        this.store = store;

        // Initialisation des composants
        this.badges = new BadgesML();
        this.globalInsight = new GlobalInsightML();
        this.modelHealth = new ModelHealth();
        this.opsKpis = new OpsKpis();

        // Init avec store si fourni
        if (store) {
            this.initWithStore(store);
        }
    }

    /**
     * Initialise tous les composants avec le store
     */
    initWithStore(store) {
        this.store = store;
        this.badges.init(store);
        this.globalInsight.init(store);
        this.modelHealth.init(store);
        this.opsKpis.init(store);
    }

    /**
     * Rendu rapide d'un Command Center ML complet
     */
    renderCommandCenter(container, options = {}) {
        if (!container) return;

        container.innerHTML = `
            <div class="ml-command-center">
                <!-- Header avec badges -->
                <div class="ml-header" id="ml-badges-container"></div>

                <!-- Global Insight principal -->
                <div class="ml-insight" id="ml-insight-container"></div>

                <!-- Model Health compact -->
                <div class="ml-health" id="ml-health-container"></div>

                <!-- KPIs opérationnels -->
                <div class="ml-ops" id="ml-ops-container"></div>
            </div>
        `;

        // Rendu des composants individuels
        this.badges.setupAutoUpdate(
            container.querySelector('#ml-badges-container'),
            options.badges || {}
        );

        this.globalInsight.setupAutoUpdate(
            container.querySelector('#ml-insight-container'),
            { compact: false, showDetails: true, ...options.insight }
        );

        this.modelHealth.setupAutoUpdate(
            container.querySelector('#ml-health-container'),
            { compact: true, ...options.health }
        );

        this.opsKpis.setupAutoUpdate(
            container.querySelector('#ml-ops-container'),
            { compact: true, ...options.ops }
        );
    }

    /**
     * Rendu pour onglet Intelligence ML dans analytics-unified
     */
    renderIntelligenceTab(container, options = {}) {
        if (!container) return;

        container.innerHTML = `
            <div class="ml-intelligence-tab">
                <!-- Stats globales ML -->
                <div class="ml-stats-section" id="ml-stats-container"></div>

                <!-- Vue détaillée modèles -->
                <div class="ml-models-section" id="ml-models-container"></div>

                <!-- Administration ML (repliable) -->
                <details class="ml-admin-section">
                    <summary>🔧 Administration ML</summary>
                    <div id="ml-admin-container"></div>
                </details>
            </div>
        `;

        // Rendu des composants pour l'analyse détaillée
        this.badges.setupAutoUpdate(
            container.querySelector('#ml-stats-container'),
            { compact: false, ...options.badges }
        );

        this.modelHealth.setupAutoUpdate(
            container.querySelector('#ml-models-container'),
            { compact: false, showActions: true, ...options.health }
        );

        // Admin section (si autorisé)
        if (options.showAdmin) {
            this.opsKpis.setupAutoUpdate(
                container.querySelector('#ml-admin-container'),
                { compact: false, showAdvanced: true, ...options.ops }
            );
        }
    }

    /**
     * Méthode utilitaire pour ajouter les styles CSS
     */
    addStyles() {
        if (document.querySelector('#ml-components-styles')) return;

        const styles = document.createElement('style');
        styles.id = 'ml-components-styles';
        styles.textContent = `
            /* Styles pour les composants ML */
            .ml-badges {
                font-size: 11px;
                color: var(--theme-text-muted);
                text-align: center;
                padding: 4px 0;
                border-top: 1px solid var(--theme-border);
            }

            .ml-command-center {
                display: grid;
                gap: 1rem;
                max-width: 100%;
            }

            .ml-intelligence-tab {
                display: grid;
                gap: 1.5rem;
                max-width: 100%;
            }

            /* Global Insight styles */
            .global-insight-ml {
                background: var(--theme-surface);
                border-radius: var(--radius-md);
                padding: 1rem;
                border: 1px solid var(--theme-border);
            }

            .gi-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }

            .gi-score {
                font-size: 2.5rem;
                font-weight: 800;
                color: var(--theme-text);
            }

            .gi-confidence {
                font-size: 0.9rem;
                color: var(--theme-text-muted);
            }

            .gi-recommendation {
                font-weight: 600;
                padding: 0.5rem;
                border-radius: var(--radius-sm);
                margin: 0.5rem 0;
                text-align: center;
            }

            /* Model Health styles */
            .model-health {
                background: var(--theme-surface);
                border-radius: var(--radius-md);
                padding: 1rem;
                border: 1px solid var(--theme-border);
            }

            .health-header {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .health-stat {
                text-align: center;
            }

            .stat-value {
                font-size: 1.5rem;
                font-weight: 600;
            }

            .stat-label {
                font-size: 0.8rem;
                color: var(--theme-text-muted);
            }

            .models-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .model-card {
                background: var(--theme-surface-elevated);
                border-radius: var(--radius-sm);
                padding: 0.75rem;
                border: 1px solid var(--theme-border);
                transition: all 0.2s ease;
            }

            .model-card:hover {
                border-color: var(--theme-primary);
            }

            .model-card.active {
                border-color: var(--success);
            }

            .model-card.error {
                border-color: var(--danger);
            }

            .model-card.stale {
                border-color: var(--warning);
            }

            /* Ops KPIs styles */
            .ops-kpis {
                display: grid;
                gap: 1rem;
            }

            .kpi-section {
                background: var(--theme-surface);
                border-radius: var(--radius-md);
                padding: 1rem;
                border: 1px solid var(--theme-border);
            }

            .kpi-title {
                margin: 0 0 0.75rem 0;
                font-size: 0.95rem;
                font-weight: 600;
                color: var(--theme-text);
            }

            .caps-comparison {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1rem;
            }

            .cap-item {
                text-align: center;
                flex: 1;
            }

            .cap-value.effective {
                font-size: 1.8rem;
                font-weight: 700;
                color: var(--theme-primary);
            }

            .cap-value.engine {
                font-size: 1.5rem;
                font-weight: 600;
                color: var(--theme-text-muted);
            }

            .cap-separator {
                font-size: 0.9rem;
                color: var(--theme-text-muted);
            }

            .caps-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
                gap: 0.5rem;
                margin-top: 0.75rem;
            }

            .cap-detail {
                display: flex;
                justify-content: space-between;
                font-size: 0.85rem;
                padding: 0.25rem 0.5rem;
                border-radius: var(--radius-xs);
            }

            .cap-detail.active {
                background: var(--theme-primary-bg);
                color: var(--theme-primary);
                font-weight: 600;
            }

            .delta-display {
                text-align: center;
            }

            .delta-value {
                font-size: 1.6rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
            }

            .delta-value.good { color: var(--success); }
            .delta-value.warning { color: var(--warning); }
            .delta-value.critical { color: var(--danger); }

            .hysteresis-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 1rem;
            }

            .hysteresis-item {
                text-align: center;
            }

            .hyst-status.normal { color: var(--success); }
            .hyst-status.prudent { color: var(--warning); }

            .error {
                color: var(--danger);
                text-align: center;
                padding: 1rem;
                font-style: italic;
            }

            /* Responsive */
            @media (max-width: 768px) {
                .caps-comparison {
                    flex-direction: column;
                    gap: 0.5rem;
                }

                .caps-grid {
                    grid-template-columns: 1fr 1fr;
                }

                .models-grid {
                    grid-template-columns: 1fr;
                }
            }
        `;

        document.head.appendChild(styles);
    }
}

// Export global
window.MLComponents = MLComponents;

// Export des composants individuels
window.BadgesML = BadgesML;
window.GlobalInsightML = GlobalInsightML;
window.ModelHealth = ModelHealth;
window.OpsKpis = OpsKpis;

// Export module ES6
export {
    MLComponents,
    BadgesML,
    GlobalInsightML,
    ModelHealth,
    OpsKpis
};