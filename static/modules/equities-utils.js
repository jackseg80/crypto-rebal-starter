/**
 * Utilitaires pour la manipulation des données Bourse/Équités
 * Utilisé par analytics-equities.html
 */

/**
 * Groupe les positions par secteur
 * @param {Array} positions - Liste des positions
 * @returns {Object} - Objet avec secteur comme clé et valeur totale
 */
export function groupBySector(positions) {
    const grouped = {};

    positions.forEach(pos => {
        // Essayer de détecter le secteur depuis différents champs
        let sector = pos.sector ||
                    pos.asset_class ||
                    pos.instrument_type ||
                    pos.category ||
                    'Autre';

        // Normaliser les noms de secteur
        sector = normalizeSectorName(sector);

        const value = Number(pos.market_value_usd || pos.market_value || pos.value || 0);
        grouped[sector] = (grouped[sector] || 0) + value;
    });

    return grouped;
}

/**
 * Groupe les positions par devise
 * @param {Array} positions - Liste des positions
 * @returns {Object} - Objet avec devise comme clé et valeur totale
 */
export function groupByCurrency(positions) {
    const grouped = {};

    positions.forEach(pos => {
        let currency = pos.currency ||
                      pos.base_currency ||
                      'USD'; // Fallback par défaut

        // Normaliser les devises
        currency = currency.toUpperCase();

        const value = Number(pos.market_value_usd || pos.market_value || pos.value || 0);
        grouped[currency] = (grouped[currency] || 0) + value;
    });

    return grouped;
}

/**
 * Trie les positions selon le critère spécifié
 * @param {Array} positions - Liste des positions
 * @param {string} sortBy - Critère de tri ('value', 'quantity', 'ticker', 'instrument', 'isin', 'price')
 * @returns {Array} - Positions triées
 */
export function sortByValue(positions, sortBy = 'value') {
    const sorted = [...positions];

    sorted.sort((a, b) => {
        let valueA, valueB;

        switch (sortBy) {
            case 'value':
                valueA = Number(a.market_value_usd || a.market_value || a.value || 0);
                valueB = Number(b.market_value_usd || b.market_value || b.value || 0);
                return valueB - valueA; // Tri décroissant

            case 'quantity':
                valueA = Number(a.quantity || a.size || 0);
                valueB = Number(b.quantity || b.size || 0);
                return valueB - valueA; // Tri décroissant

            case 'ticker':
                valueA = (a.instrument_symbol || a.ticker || '').toLowerCase();
                valueB = (b.instrument_symbol || b.ticker || '').toLowerCase();
                return valueA.localeCompare(valueB); // Tri alphabétique

            case 'instrument':
                valueA = (a.instrument_name || a.name || '').toLowerCase();
                valueB = (b.instrument_name || b.name || '').toLowerCase();
                return valueA.localeCompare(valueB); // Tri alphabétique

            case 'isin':
                valueA = (a.isin || '').toLowerCase();
                valueB = (b.isin || '').toLowerCase();
                return valueA.localeCompare(valueB); // Tri alphabétique

            case 'price':
                valueA = Number(a.price || a.market_price || 0);
                valueB = Number(b.price || b.market_price || 0);
                return valueB - valueA; // Tri décroissant

            default:
                return 0;
        }
    });

    return sorted;
}

/**
 * Formate une valeur monétaire avec devise
 * @param {number} amount - Montant à formater
 * @param {string} currency - Code devise (USD, EUR, CHF, etc.)
 * @returns {string} - Montant formaté
 */
export function formatMoney(amount, currency = 'USD') {
    if (!Number.isFinite(amount)) {
        return currency === 'USD' ? '$0' : `0 ${currency}`;
    }

    // Configuration par devise
    const currencyConfig = {
        'USD': { symbol: '$', position: 'before' },
        'EUR': { symbol: '€', position: 'after' },
        'CHF': { symbol: 'CHF', position: 'after' },
        'GBP': { symbol: '£', position: 'before' },
        'JPY': { symbol: '¥', position: 'before' }
    };

    const config = currencyConfig[currency] || { symbol: currency, position: 'after' };

    // Formatage du nombre
    const options = {
        minimumFractionDigits: 0,
        maximumFractionDigits: amount >= 1000 ? 0 : 2
    };

    const formattedNumber = new Intl.NumberFormat('en-US', options).format(Math.abs(amount));
    const sign = amount < 0 ? '-' : '';

    if (config.position === 'before') {
        return `${sign}${config.symbol}${formattedNumber}`;
    } else {
        return `${sign}${formattedNumber} ${config.symbol}`;
    }
}

/**
 * Calcule des statistiques de base sur les positions
 * @param {Array} positions - Liste des positions
 * @returns {Object} - Statistiques (total, moyenne, médiane, etc.)
 */
export function calculateStats(positions) {
    if (!positions || positions.length === 0) {
        return {
            total: 0,
            count: 0,
            average: 0,
            median: 0,
            largest: 0,
            smallest: 0
        };
    }

    const values = positions
        .map(pos => Number(pos.market_value_usd || pos.market_value || pos.value || 0))
        .filter(val => val > 0)
        .sort((a, b) => a - b);

    const total = values.reduce((sum, val) => sum + val, 0);
    const count = values.length;
    const average = count > 0 ? total / count : 0;

    let median = 0;
    if (count > 0) {
        const mid = Math.floor(count / 2);
        median = count % 2 === 0
            ? (values[mid - 1] + values[mid]) / 2
            : values[mid];
    }

    return {
        total,
        count,
        average,
        median,
        largest: values.length > 0 ? values[values.length - 1] : 0,
        smallest: values.length > 0 ? values[0] : 0
    };
}

/**
 * Détecte les top/flop positions par performance
 * @param {Array} positions - Liste des positions avec données de performance
 * @returns {Object} - {topPerformers: Array, worstPerformers: Array}
 */
export function getPerformanceRanking(positions, limit = 5) {
    const positionsWithPerf = positions
        .filter(pos => {
            const pnl = pos.pnl_today || pos.unrealized_pnl || pos.gain_loss;
            return Number.isFinite(Number(pnl));
        })
        .map(pos => ({
            ...pos,
            performance: Number(pos.pnl_today || pos.unrealized_pnl || pos.gain_loss || 0)
        }));

    const sorted = [...positionsWithPerf].sort((a, b) => b.performance - a.performance);

    return {
        topPerformers: sorted.slice(0, limit),
        worstPerformers: sorted.slice(-limit).reverse()
    };
}

/**
 * Normalise les noms de secteur pour un affichage cohérent
 * @param {string} sector - Nom de secteur brut
 * @returns {string} - Nom de secteur normalisé
 */
function normalizeSectorName(sector) {
    if (!sector || typeof sector !== 'string') {
        return 'Autre';
    }

    const normalized = sector.toLowerCase().trim();

    // Mapping des secteurs connus
    const sectorMapping = {
        'equity': 'Actions',
        'equities': 'Actions',
        'stock': 'Actions',
        'stocks': 'Actions',
        'etf': 'ETF',
        'fund': 'Fonds',
        'bond': 'Obligations',
        'bonds': 'Obligations',
        'cash': 'Liquidités',
        'option': 'Options',
        'options': 'Options',
        'warrant': 'Warrants',
        'certificate': 'Certificats',
        'commodity': 'Matières Premières',
        'forex': 'Devises',
        'crypto': 'Crypto',
        'cryptocurrency': 'Crypto'
    };

    return sectorMapping[normalized] || toTitleCase(sector);
}

/**
 * Convertit une chaîne en format Title Case
 * @param {string} str - Chaîne à convertir
 * @returns {string} - Chaîne en Title Case
 */
function toTitleCase(str) {
    return str.toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Filtre les positions selon différents critères
 * @param {Array} positions - Liste des positions
 * @param {Object} filters - Critères de filtrage
 * @returns {Array} - Positions filtrées
 */
export function filterPositions(positions, filters = {}) {
    return positions.filter(pos => {
        // Filtre par valeur minimale
        if (filters.minValue) {
            const value = Number(pos.market_value_usd || pos.market_value || pos.value || 0);
            if (value < filters.minValue) return false;
        }

        // Filtre par devise
        if (filters.currency) {
            const currency = (pos.currency || '').toUpperCase();
            if (currency !== filters.currency.toUpperCase()) return false;
        }

        // Filtre par secteur
        if (filters.sector) {
            const sector = normalizeSectorName(pos.sector || pos.asset_class || '');
            if (sector !== filters.sector) return false;
        }

        // Filtre par texte (ticker, nom, ISIN)
        if (filters.search) {
            const searchTerm = filters.search.toLowerCase();
            const ticker = (pos.instrument_symbol || pos.ticker || '').toLowerCase();
            const name = (pos.instrument_name || pos.name || '').toLowerCase();
            const isin = (pos.isin || '').toLowerCase();

            if (!ticker.includes(searchTerm) &&
                !name.includes(searchTerm) &&
                !isin.includes(searchTerm)) {
                return false;
            }
        }

        return true;
    });
}