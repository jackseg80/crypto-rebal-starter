/**
 * ML Card Component - Composant unifié pour les cartes ML
 */

export class MLCard {
    constructor(config) {
        this.id = config.id;
        this.title = config.title;
        this.icon = config.icon;
        this.description = config.description;
        this.actions = config.actions || [];
        this.statusFields = config.statusFields || [];
        this.draggable = config.draggable || false;
        this.container = null;
    }

    render() {
        const card = document.createElement('div');
        card.className = 'ml-card';
        card.id = this.id;
        
        if (this.draggable) {
            card.draggable = true;
            card.setAttribute('data-drag-handle', 'true');
        }

        card.innerHTML = `
            <div class="card-header">
                <div class="card-title">
                    <span class="card-icon">${this.icon}</span>
                    <span>${this.title}</span>
                </div>
                ${this.draggable ? '<div class="drag-handle" data-drag-handle="true">⋮⋮</div>' : ''}
                <div class="status-indicator inactive" id="${this.id}-status"></div>
            </div>
            
            <div class="card-content">
                <p class="card-description">${this.description}</p>
                ${this.renderStatusFields()}
            </div>
            
            <div class="card-actions">
                ${this.renderActions()}
            </div>
        `;

        this.attachEventListeners(card);
        return card;
    }

    renderStatusFields() {
        if (!this.statusFields.length) return '';
        
        return `
            <div class="status-grid">
                ${this.statusFields.map(field => `
                    <div class="status-item">
                        <span class="status-label">${field.label}</span>
                        <span class="status-value" data-value="${field.key}" id="${this.id}-${field.key}">${field.defaultValue || '—'}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderActions() {
        return this.actions.map(action => `
            <button class="btn ${action.type || 'primary'}" 
                    id="${this.id}-${action.id}"
                    ${action.disabled ? 'disabled' : ''}>
                ${action.icon || ''} ${action.label}
            </button>
        `).join('');
    }

    attachEventListeners(card) {
        // Gestionnaires des boutons d'action
        this.actions.forEach(action => {
            const btn = card.querySelector(`#${this.id}-${action.id}`);
            if (btn && action.handler) {
                btn.addEventListener('click', action.handler);
            }
        });

        // Gestionnaires drag & drop si activé
        if (this.draggable) {
            this.setupDragAndDrop(card);
        }
    }

    setupDragAndDrop(card) {
        card.addEventListener('dragstart', (e) => {
            card.classList.add('dragging');
            e.dataTransfer.setData('text/plain', this.id);
        });

        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
        });

        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            card.classList.add('drop-target');
        });

        card.addEventListener('dragleave', () => {
            card.classList.remove('drop-target');
        });

        card.addEventListener('drop', (e) => {
            e.preventDefault();
            card.classList.remove('drop-target');
            const draggedId = e.dataTransfer.getData('text/plain');
            this.handleDrop(draggedId, this.id);
        });
    }

    handleDrop(draggedId, targetId) {
        if (draggedId === targetId) return;
        
        const grid = this.container;
        const draggedEl = document.getElementById(draggedId);
        const targetEl = document.getElementById(targetId);
        
        if (grid && draggedEl && targetEl) {
            grid.insertBefore(draggedEl, targetEl.nextSibling);
            this.saveOrder(grid);
        }
    }

    saveOrder(grid) {
        const order = Array.from(grid.querySelectorAll('.ml-card[draggable="true"]')).map(c => c.id);
        try {
            localStorage.setItem('ml_cards_order', JSON.stringify(order));
        } catch (e) {
            console.warn('Could not save card order:', e);
        }
    }

    updateStatus(data) {
        if (!data) return;

        const statusIndicator = document.getElementById(`${this.id}-status`);
        if (statusIndicator) {
            const isActive = data.active || data.loaded || data.status === 'active';
            statusIndicator.className = `status-indicator ${isActive ? 'active' : 'inactive'}`;
        }

        // Mettre à jour les champs de statut
        this.statusFields.forEach(field => {
            const element = document.getElementById(`${this.id}-${field.key}`);
            if (element && data[field.key] !== undefined) {
                element.textContent = field.formatter ? 
                    field.formatter(data[field.key]) : 
                    data[field.key];
            }
        });
    }

    setLoading(loading = true, message = 'Chargement...') {
        const statusIndicator = document.getElementById(`${this.id}-status`);
        if (statusIndicator) {
            if (loading) {
                statusIndicator.innerHTML = `<span class="loading-spinner"></span>`;
                statusIndicator.title = message;
            } else {
                statusIndicator.innerHTML = '';
                statusIndicator.title = '';
            }
        }
    }

    setError(error) {
        const statusIndicator = document.getElementById(`${this.id}-status`);
        if (statusIndicator) {
            statusIndicator.className = 'status-indicator error';
            statusIndicator.title = error;
        }
    }
}

// Factory pour créer des cartes prédéfinies
export class MLCardFactory {
    static createVolatilityCard() {
        return new MLCard({
            id: 'volatility-card',
            title: 'Modèle de Volatilité',
            icon: '📊',
            description: 'Prédiction de la volatilité des crypto-monnaies avec des modèles LSTM avancés.',
            draggable: true,
            statusFields: [
                { label: 'Modèles', key: 'models', defaultValue: '0' },
                { label: 'Précision', key: 'accuracy', defaultValue: '—', formatter: v => `${(v*100).toFixed(1)}%` },
                { label: 'Dernière MAJ', key: 'lastUpdate', formatter: v => new Date(v).toLocaleDateString() }
            ],
            actions: [
                { id: 'train', label: 'Entraîner', type: 'primary', handler: () => trainVolatilityModel() },
                { id: 'predict', label: 'Prédire', type: 'secondary', handler: () => predictVolatility() }
            ]
        });
    }

    static createRegimeCard() {
        return new MLCard({
            id: 'regime-card',
            title: 'Détection de Régime',
            icon: '🎯',
            description: 'Détection automatique des régimes de marché (bull/bear/sideways).',
            draggable: true,
            statusFields: [
                { label: 'Régime actuel', key: 'currentRegime', defaultValue: '—' },
                { label: 'Confiance', key: 'confidence', defaultValue: '—', formatter: v => `${(v*100).toFixed(1)}%` },
                { label: 'Transition', key: 'transitionProb', defaultValue: '—', formatter: v => `${(v*100).toFixed(1)}%` }
            ],
            actions: [
                { id: 'current', label: 'Régime Actuel', type: 'primary', handler: () => getCurrentRegime() },
                { id: 'train', label: 'Réentraîner', type: 'secondary', handler: () => trainRegimeModel() }
            ]
        });
    }

    static createCorrelationCard() {
        return new MLCard({
            id: 'correlation-card',
            title: 'Analyse de Corrélation',
            icon: '🔗',
            description: 'Matrice de corrélation dynamique entre crypto-monnaies.',
            draggable: true,
            statusFields: [
                { label: 'Assets', key: 'assetsCount', defaultValue: '0' },
                { label: 'Fenêtre', key: 'windowDays', defaultValue: '30', formatter: v => `${v} jours` },
                { label: 'Corrélation moy.', key: 'avgCorrelation', defaultValue: '—', formatter: v => v.toFixed(3) }
            ],
            actions: [
                { id: 'analyze', label: 'Analyser', type: 'primary', handler: () => analyzeCorrelations() },
                { id: 'matrix', label: 'Voir Matrice', type: 'secondary', handler: () => showCorrelationMatrix() }
            ]
        });
    }

    static createSentimentCard() {
        return new MLCard({
            id: 'sentiment-card',
            title: 'Analyse de Sentiment',
            icon: '😊',
            description: 'Analyse du sentiment du marché via Fear & Greed Index et social media.',
            draggable: true,
            statusFields: [
                { label: 'Fear & Greed', key: 'fearGreedIndex', defaultValue: '—' },
                { label: 'Sentiment', key: 'overallSentiment', defaultValue: 'Neutre' },
                { label: 'Sources', key: 'sourcesCount', defaultValue: '0' }
            ],
            actions: [
                { id: 'analyze', label: 'Analyser', type: 'primary', handler: () => analyzeSentiment() },
                { id: 'report', label: 'Rapport', type: 'secondary', handler: () => getSentimentReport() }
            ]
        });
    }
}

// Gestionnaire global des cartes
export class MLCardManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.cards = new Map();
    }

    addCard(card) {
        if (!this.container) return;
        
        const cardElement = card.render();
        card.container = this.container;
        this.container.appendChild(cardElement);
        this.cards.set(card.id, card);
        
        return cardElement;
    }

    removeCard(cardId) {
        const card = this.cards.get(cardId);
        if (card) {
            const element = document.getElementById(cardId);
            if (element) element.remove();
            this.cards.delete(cardId);
        }
    }

    updateCard(cardId, data) {
        const card = this.cards.get(cardId);
        if (card) {
            card.updateStatus(data);
        }
    }

    updateAllCards(statusData) {
        for (const [cardId, card] of this.cards) {
            const data = statusData[cardId.replace('-card', '')];
            if (data) {
                card.updateStatus(data);
            }
        }
    }

    restoreOrder() {
        try {
            const savedOrder = localStorage.getItem('ml_cards_order');
            if (savedOrder) {
                const order = JSON.parse(savedOrder);
                order.forEach(cardId => {
                    const element = document.getElementById(cardId);
                    if (element) {
                        this.container.appendChild(element);
                    }
                });
            }
        } catch (e) {
            console.warn('Could not restore card order:', e);
        }
    }
}