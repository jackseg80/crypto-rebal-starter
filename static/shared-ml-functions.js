/**
 * Fonctions ML partagées - Crypto Portfolio
 * Centralise les appels API, utilitaires UI et fonctions communes
 */

// Configuration API
const ML_API_BASE = globalConfig?.get('api_base_url') || 'http://localhost:8000';

// Utilitaires UI communes
export function showLoading(elementId, message = 'Chargement...') {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `<span class="loading-spinner"></span> ${message}`;
    }
}

export function showError(message, container = null) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.style.cssText = `
        background: var(--error-bg, #fee);
        color: var(--error-text, #c53030);
        border: 1px solid var(--error-border, #fed7d7);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    `;
    errorDiv.textContent = message;
    
    if (container) {
        container.appendChild(errorDiv);
    } else {
        document.body.appendChild(errorDiv);
    }
    
    setTimeout(() => errorDiv.remove(), 5000);
}

export function showSuccess(message, container = null) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.style.cssText = `
        background: var(--success-bg, #f0fff4);
        color: var(--success-text, #2d7d32);
        border: 1px solid var(--success-border, #c6f6d5);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    `;
    successDiv.textContent = message;
    
    if (container) {
        container.appendChild(successDiv);
    } else {
        document.body.appendChild(successDiv);
    }
    
    setTimeout(() => successDiv.remove(), 5000);
}

// API Calls communes
export async function fetchMLStatus(endpoint) {
    try {
        const response = await fetch(`${ML_API_BASE}/api/ml/${endpoint}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.warn(`ML API ${endpoint} unavailable:`, error.message);
        return null;
    }
}

export async function postMLAction(endpoint, data = {}) {
    try {
        const response = await fetch(`${ML_API_BASE}/api/ml/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`ML API ${endpoint} failed:`, error);
        throw error;
    }
}

// Fonctions ML spécifiques
export async function getVolatilityStatus() {
    return await fetchMLStatus('volatility/models/status');
}

export async function getRegimeStatus() {
    return await fetchMLStatus('regime/status');
}

export async function getCorrelationStatus() {
    return await fetchMLStatus('correlation/status');
}

export async function getSentimentStatus() {
    return await fetchMLStatus('sentiment/status');
}

export async function getRebalanceStatus() {
    return await fetchMLStatus('rebalance/status');
}

// Actions ML
export async function trainVolatilityModel(symbols = ['BTC', 'ETH']) {
    return await postMLAction('volatility/train-portfolio', { symbols });
}

export async function getCurrentRegime() {
    return await fetchMLStatus('regime/current');
}

export async function trainRegimeModel() {
    return await postMLAction('regime/train', {});
}

export async function analyzeCorrelations(symbols = ['BTC', 'ETH'], windowDays = 30) {
    return await fetchMLStatus(`correlation/matrix/current?window_days=${windowDays}`);
}

export async function analyzeSentiment(symbols = ['BTC', 'ETH'], days = 7) {
    return await fetchMLStatus(`sentiment/analyze?symbols=${symbols.join(',')}&days=${days}`);
}

export async function getFearGreedIndex(days = 7) {
    return await fetchMLStatus(`sentiment/fear-greed?days=${days}`);
}

// Utilitaires de formatage
export function formatPercentage(value, decimals = 2) {
    return `${(value * 100).toFixed(decimals)}%`;
}

export function formatCurrency(value, currency = 'USD', decimals = 2) {
    return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

export function formatDate(date, options = { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
}) {
    return new Intl.DateTimeFormat('fr-FR', options).format(new Date(date));
}

// Gestion des boutons d'action
export function setupActionButton(buttonId, actionFn, loadingText = 'Traitement...') {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    
    btn.addEventListener('click', async (e) => {
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = loadingText;
        
        try {
            await actionFn(e);
            showSuccess('Opération terminée avec succès');
        } catch (error) {
            showError(`Erreur: ${error.message}`);
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    });
}

// Mise à jour des status cards
export function updateStatusCard(cardId, data) {
    const card = document.getElementById(cardId);
    if (!card || !data) return;
    
    const statusElement = card.querySelector('.status-indicator');
    const valueElements = card.querySelectorAll('[data-value]');
    
    // Mise à jour du statut
    if (statusElement) {
        const isActive = data.active || data.loaded || data.status === 'active';
        statusElement.className = `status-indicator ${isActive ? 'active' : 'inactive'}`;
    }
    
    // Mise à jour des valeurs
    valueElements.forEach(el => {
        const key = el.getAttribute('data-value');
        if (data[key] !== undefined) {
            el.textContent = data[key];
        }
    });
}

// Chargement de tous les status ML
export async function loadAllMLStatus() {
    const [volatility, regime, correlation, sentiment, rebalance] = await Promise.allSettled([
        getVolatilityStatus(),
        getRegimeStatus(),
        getCorrelationStatus(),
        getSentimentStatus(),
        getRebalanceStatus()
    ]);
    
    return {
        volatility: volatility.status === 'fulfilled' ? volatility.value : null,
        regime: regime.status === 'fulfilled' ? regime.value : null,
        correlation: correlation.status === 'fulfilled' ? correlation.value : null,
        sentiment: sentiment.status === 'fulfilled' ? sentiment.value : null,
        rebalance: rebalance.status === 'fulfilled' ? rebalance.value : null
    };
}

// Initialisation globale
export function initializeMLDashboard() {
    console.log('🧠 ML Dashboard initialized');
    
    // Charger le status initial
    loadAllMLStatus().then(status => {
        console.log('📊 ML Status loaded:', status);
        
        // Mettre à jour les cards si elles existent
        if (status.volatility) updateStatusCard('volatility-card', status.volatility);
        if (status.regime) updateStatusCard('regime-card', status.regime);
        if (status.correlation) updateStatusCard('correlation-card', status.correlation);
        if (status.sentiment) updateStatusCard('sentiment-card', status.sentiment);
        if (status.rebalance) updateStatusCard('rebalance-card', status.rebalance);
    });
}