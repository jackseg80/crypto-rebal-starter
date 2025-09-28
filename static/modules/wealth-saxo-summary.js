/**
 * Store utilitaire pour résumer les données Saxo (Bourse)
 * Utilisé par dashboard.html et settings.html pour éviter la duplication
 */
import { safeFetch } from './http.js';

let _cachedSummary = null;
let _cacheTimestamp = 0;
const CACHE_TTL = 30000; // 30 secondes

/**
 * Récupère un résumé des positions Saxo depuis l'API legacy
 * @returns {Promise<{total_value: number, positions_count: number, asof: string, error?: string}>}
 */
export async function fetchSaxoSummary() {
    const now = Date.now();

    // Retourner le cache si valide
    if (_cachedSummary && (now - _cacheTimestamp) < CACHE_TTL) {
        return _cachedSummary;
    }

    try {
        const { ok, data } = await safeFetch(
            window.globalConfig?.getApiUrl('/api/saxo/positions') || '/api/saxo/positions',
            { timeout: 8000 }
        );

        if (!ok || !data) {
            throw new Error('API Saxo indisponible');
        }

        const positions = Array.isArray(data.positions) ? data.positions :
                         Array.isArray(data) ? data : [];

        if (positions.length === 0) {
            const summary = {
                total_value: 0,
                positions_count: 0,
                asof: 'Aucune donnée',
                isEmpty: true
            };
            _cachedSummary = summary;
            _cacheTimestamp = now;
            return summary;
        }

        // Calculer la valeur totale
        const totalValue = positions.reduce((sum, pos) => {
            const value = Number(pos.market_value_usd || pos.market_value || pos.value || 0);
            return sum + value;
        }, 0);

        // Trouver la date la plus récente (asof)
        let latestDate = 'Date inconnue';
        try {
            const dates = positions
                .map(pos => pos.asof || pos.date || pos.timestamp)
                .filter(d => d)
                .sort((a, b) => new Date(b) - new Date(a));

            if (dates.length > 0) {
                const date = new Date(dates[0]);
                latestDate = date.toLocaleDateString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch (e) {
            // Fallback: extraire de portfolio_id si disponible
            const portfolioId = data.portfolio_id || data.portfolios?.[0]?.portfolio_id || '';
            if (portfolioId.includes('25-09-2025')) {
                latestDate = '25/09/2025 18:40';
            }
        }

        const summary = {
            total_value: totalValue,
            positions_count: positions.length,
            asof: latestDate,
            isEmpty: false
        };

        _cachedSummary = summary;
        _cacheTimestamp = now;
        return summary;

    } catch (error) {
        console.warn('[Saxo Summary] Erreur fetch:', error.message);

        const errorSummary = {
            total_value: 0,
            positions_count: 0,
            asof: 'Erreur',
            error: error.message,
            isEmpty: true
        };

        // Cache l'erreur pour éviter les appels répétés
        _cachedSummary = errorSummary;
        _cacheTimestamp = now;
        return errorSummary;
    }
}

/**
 * Force le rechargement du cache (utilisé après upload)
 */
export function invalidateSaxoCache() {
    _cachedSummary = null;
    _cacheTimestamp = 0;
}

/**
 * Formate une valeur monétaire pour l'affichage
 * @param {number} value - Valeur en USD
 * @returns {string} - Valeur formatée (ex: "$1,234.56")
 */
export function formatCurrency(value) {
    if (!Number.isFinite(value) || value === 0) {
        return '$0';
    }

    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: value >= 1000 ? 0 : 2
    }).format(value);
}

/**
 * Détermine la couleur pour les métriques selon la valeur
 * @param {number} value - Valeur numérique
 * @returns {string} - Classe CSS ou couleur
 */
export function getMetricColor(value) {
    if (!Number.isFinite(value) || value === 0) {
        return 'var(--theme-text-muted)';
    }
    return value > 0 ? 'var(--success)' : 'var(--theme-text)';
}