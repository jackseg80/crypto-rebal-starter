/**
 * BadgesML.js - Composant badges ML unifié
 * Format: Source • Updated HH:MM:SS • Contrad X% • Cap Y% • Overrides Z
 * Utilisé par ai-dashboard.html et analytics-unified.html
 */

class BadgesML {
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
     * Rendu des badges ML dans un conteneur
     * @param {HTMLElement} container - Élément DOM conteneur
     * @param {Object} options - Options de rendu
     */
    render(container, options = {}) {
        if (!container) return;

        try {
            const badges = this.generateBadges(options);
            container.textContent = badges.join(' • ');
            container.className = 'ml-badges';

            // Debug
            console.debug('🏷️ BadgesML updated:', {
                badges: badges,
                text: container.textContent
            });

        } catch (error) {
            console.warn('Failed to render ML badges:', error);
            container.textContent = 'Badges unavailable';
        }
    }

    /**
     * Génère les badges selon les données disponibles
     */
    generateBadges(options = {}) {
        const badges = [];

        // Source
        const source = this.getDataSource(options);
        if (source) badges.push(source);

        // Updated timestamp
        const timestamp = this.getTimestamp(options);
        if (timestamp) badges.push(`Updated ${timestamp}`);

        // Contradiction index
        const contradiction = this.getContradiction(options);
        if (contradiction !== null) badges.push(`Contrad ${contradiction}%`);

        // Cap
        const cap = this.getCap(options);
        if (cap !== null) badges.push(`Cap ${cap}%`);

        // Overrides
        const overrides = this.getOverrides(options);
        if (overrides > 0) badges.push(`Overrides ${overrides}`);

        // Status alerts (STALE, ERROR)
        const statusBadges = this.getStatusBadges(options);
        badges.push(...statusBadges);

        return badges;
    }

    /**
     * Récupère la source de données
     */
    getDataSource(options) {
        if (options.source) return options.source;

        if (this.store) {
            const govData = this.store.get('governance') || {};
            return govData.data_source || 'API';
        }

        return 'API';
    }

    /**
     * Récupère le timestamp formaté
     */
    getTimestamp(options) {
        if (options.timestamp) {
            const ts = new Date(options.timestamp);
            return ts.toLocaleTimeString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }

        if (this.store) {
            const ml = this.store.get('governance.ml_signals');
            if (ml?.timestamp) {
                const ts = new Date(ml.timestamp);
                return ts.toLocaleTimeString('fr-FR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            }
        }

        return null;
    }

    /**
     * Récupère l'index de contradiction en %
     */
    getContradiction(options) {
        if (options.contradiction !== undefined) {
            return Math.round(options.contradiction * 100);
        }

        if (this.store) {
            const ml = this.store.get('governance.ml_signals');
            if (ml?.contradiction_index != null) {
                return Math.round(ml.contradiction_index * 100);
            }
        }

        return null;
    }

    /**
     * Récupère le cap en %
     */
    getCap(options) {
        if (options.cap !== undefined) {
            return Math.round(options.cap * 100);
        }

        if (this.store) {
            const policy = this.store.get('governance.active_policy');
            if (policy?.cap_daily != null) {
                return Math.round(policy.cap_daily * 100);
            }
        }

        return null;
    }

    /**
     * Récupère le nombre d'overrides
     */
    getOverrides(options) {
        if (options.overrides !== undefined) return options.overrides;

        if (this.store) {
            const govData = this.store.get('governance') || {};
            return govData.overrides_count || 0;
        }

        return 0;
    }

    /**
     * Récupère les badges de status (STALE, ERROR)
     */
    getStatusBadges(options) {
        const statusBadges = [];

        if (options.backendStatus) {
            if (options.backendStatus === 'stale') statusBadges.push('STALE');
            if (options.backendStatus === 'error') statusBadges.push('ERROR');
        }

        if (this.store) {
            const govData = this.store.get('governance') || {};
            if (govData.backend_status === 'stale') statusBadges.push('STALE');
            if (govData.backend_status === 'error') statusBadges.push('ERROR');
        }

        return statusBadges;
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
    }
}

// Export global
window.BadgesML = BadgesML;

// Export module ES6
export { BadgesML };