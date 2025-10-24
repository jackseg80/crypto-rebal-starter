// shared-asset-groups.js - Système unifié de classification des assets
// Source unique de vérité : API /taxonomy (comme alias-manager.html)

// Cache global synchrone pour les données de taxonomy (chargées une fois au démarrage)
let taxonomyCache = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60 * 60 * 1000; // 1 hour (optimized: static file, weekly updates)

// Variables globales synchrones pour compatibilité immédiate
export let UNIFIED_ASSET_GROUPS = {};
export let KNOWN_ASSET_MAPPING = {};
export let GROUP_ORDER = [];

// Initialisation immédiate au chargement du module
initializeTaxonomySync();

// Expose functions globally for debugging
if (typeof window !== 'undefined') {
  window.forceReloadTaxonomy = forceReloadTaxonomy;
  window.debugClassification = debugClassification;
  window.groupAssetsByClassification = (...args) => groupAssetsByClassification(...args);
  window.getAssetGroup = (symbol) => getAssetGroup(symbol);
  const descriptor = Object.getOwnPropertyDescriptor(window, 'UNIFIED_ASSET_GROUPS');
  if (!descriptor || descriptor.configurable) {
    Object.defineProperty(window, 'UNIFIED_ASSET_GROUPS', {
      get: () => UNIFIED_ASSET_GROUPS,
      configurable: true
    });
  }
}

// Fallback pour classification automatique si API indisponible
function autoClassifySymbolFallback(symbol) {
  const upperSymbol = symbol.toUpperCase();

  if (upperSymbol.includes('BTC') || upperSymbol.includes('WBTC')) {
    return 'BTC';
  } else if (upperSymbol.includes('ETH') || upperSymbol.includes('STETH') || upperSymbol.includes('RETH')) {
    return 'ETH';
  } else if (['USDT', 'USDC', 'DAI', 'USD', 'BUSD', 'TUSD', 'FDUSD', 'EUR'].includes(upperSymbol)) {
    return 'Stablecoins';
  } else if (upperSymbol.includes('SOL')) {
    return 'SOL';
  } else {
    return 'Others';
  }
}

// Fallback groups si API indisponible
const FALLBACK_GROUPS = ['BTC', 'ETH', 'Stablecoins', 'SOL', 'L1/L0 majors', 'L2/Scaling', 'DeFi', 'AI/Data', 'Gaming/NFT', 'Memecoins', 'Others'];

// Initialisation synchrone au chargement du module
function initializeTaxonomySync() {
  // Essayer d'abord un chargement synchrone immédiat
  try {
    loadTaxonomyDataSync();
    (window.debugLogger?.info || console.log)('✅ Taxonomy data loaded synchronously on init:', Object.keys(KNOWN_ASSET_MAPPING).length, 'aliases,', GROUP_ORDER.length, 'groups');
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Sync load on init failed, trying async...', error.message);

    // Fallback async si sync fail
    loadTaxonomyData()
      .then(data => {
        updateGlobalVariables(data);
        (window.debugLogger?.info || console.log)('✅ Taxonomy data loaded asynchronously:', Object.keys(KNOWN_ASSET_MAPPING).length, 'aliases,', GROUP_ORDER.length, 'groups');
      })
      .catch(error => {
        (window.debugLogger?.warn || console.warn)('⚠️ Taxonomy async load failed, using fallback:', error.message);
        // Utiliser les fallback en cas d'erreur
        const fallbackData = {
          aliases: {},
          groups: FALLBACK_GROUPS
        };
        updateGlobalVariables(fallbackData);
      });
  }
}

// Charger les données taxonomy depuis l'API
async function loadTaxonomyData() {
  const now = Date.now();

  // Utiliser le cache si valide
  if (taxonomyCache && (now - cacheTimestamp) < CACHE_TTL) {
    return taxonomyCache;
  }

  try {
    const apiBase = (window.globalConfig?.get && window.globalConfig.get('api_base_url')) || 'http://localhost:8000';
    const response = await fetch(`${apiBase}/taxonomy`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Mettre en cache
    taxonomyCache = {
      aliases: data.aliases || {},
      groups: data.groups || FALLBACK_GROUPS
    };
    cacheTimestamp = now;

    (window.debugLogger?.info || console.log)('✅ Taxonomy data loaded from API:', Object.keys(taxonomyCache.aliases).length, 'aliases,', taxonomyCache.groups.length, 'groups');

    return taxonomyCache;
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Taxonomy API unavailable, using fallback:', error.message);

    // Fallback si API indisponible
    taxonomyCache = {
      aliases: {},
      groups: FALLBACK_GROUPS
    };
    cacheTimestamp = now;

    return taxonomyCache;
  }
}

// Version synchrone pour les cas d'urgence
export function loadTaxonomyDataSync() {
  const now = Date.now();

  // Utiliser le cache si valide
  if (taxonomyCache && (now - cacheTimestamp) < CACHE_TTL) {
    updateGlobalVariables(taxonomyCache);
    return;
  }

  try {
    const apiBase = (window.globalConfig?.get && window.globalConfig.get('api_base_url')) || 'http://localhost:8000';

    // XMLHttpRequest synchrone (deprecated mais nécessaire ici)
    const xhr = new XMLHttpRequest();
    xhr.open('GET', `${apiBase}/taxonomy`, false); // false = synchrone
    xhr.send();

    if (xhr.status !== 200) {
      throw new Error(`HTTP ${xhr.status}`);
    }

    const data = JSON.parse(xhr.responseText);

    // Mettre en cache
    taxonomyCache = {
      aliases: data.aliases || {},
      groups: data.groups || FALLBACK_GROUPS
    };
    cacheTimestamp = now;

    updateGlobalVariables(taxonomyCache);

    (window.debugLogger?.info || console.log)('✅ Taxonomy data loaded sync from API:', Object.keys(taxonomyCache.aliases).length, 'aliases,', taxonomyCache.groups.length, 'groups');
  } catch (error) {
    (window.debugLogger?.warn || console.warn)('⚠️ Taxonomy sync API failed, using fallback:', error.message);

    // Fallback si API indisponible
    taxonomyCache = {
      aliases: {},
      groups: FALLBACK_GROUPS
    };
    cacheTimestamp = now;
    updateGlobalVariables(taxonomyCache);
  }
}

// Fonction helper pour mettre à jour les variables globales
function updateGlobalVariables(data) {
  KNOWN_ASSET_MAPPING = data.aliases || {};
  GROUP_ORDER = data.groups || FALLBACK_GROUPS;

  // Créer UNIFIED_ASSET_GROUPS (format inversé)
  UNIFIED_ASSET_GROUPS = {};
  GROUP_ORDER.forEach(group => {
    UNIFIED_ASSET_GROUPS[group] = [];
  });

  Object.entries(KNOWN_ASSET_MAPPING).forEach(([symbol, group]) => {
    if (UNIFIED_ASSET_GROUPS[group]) {
      UNIFIED_ASSET_GROUPS[group].push(symbol);
    }
  });
}

// Fonction pour obtenir la liste des groupes (exportée)
export async function getGroupList() {
  const taxonomy = await loadTaxonomyData();
  return taxonomy.groups;
}

// Format inversé pour compatibilité (group -> symbols array)
export async function getUnifiedAssetGroups() {
  const taxonomy = await loadTaxonomyData();
  const groups = {};

  // Initialiser tous les groupes
  taxonomy.groups.forEach(group => {
    groups[group] = [];
  });

  // Remplir avec les aliases
  Object.entries(taxonomy.aliases).forEach(([symbol, group]) => {
    if (groups[group]) {
      groups[group].push(symbol);
    }
  });

  return groups;
}

// Classification synchrone simple utilisant les données chargées
export function getAssetGroup(symbol) {
  const upperSymbol = symbol?.toUpperCase();

  if (!upperSymbol) return 'Others';

  // Si les données ne sont pas encore chargées, essayer de charger depuis l'API de façon synchrone
  if (Object.keys(KNOWN_ASSET_MAPPING).length === 0) {
    (window.debugLogger?.warn || console.warn)('⚠️ Taxonomy data not loaded yet, trying sync load...');
    try {
      loadTaxonomyDataSync();
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('⚠️ Sync load failed, using fallback:', error.message);
      return autoClassifySymbolFallback(upperSymbol);
    }

    // Vérifier encore après le chargement sync
    if (Object.keys(KNOWN_ASSET_MAPPING).length === 0) {
      (window.debugLogger?.warn || console.warn)('⚠️ Sync load returned empty mapping, using fallback');
      return autoClassifySymbolFallback(upperSymbol);
    }
  }

  // D'abord vérifier le mapping explicite
  if (KNOWN_ASSET_MAPPING[upperSymbol]) {
    return KNOWN_ASSET_MAPPING[upperSymbol];
  }

  // Sinon utiliser la classification automatique (patterns)
  return autoClassifySymbolFallback(upperSymbol);
}

// Version async pour compatibilité (deprecated)
export async function getAssetGroupAsync(symbol) {
  return getAssetGroup(symbol);
}

// Grouper des assets par classification (synchrone)
export function groupAssetsByClassification(items) {
  const groups = new Map();

  items.forEach(item => {
    const symbol = (item.symbol || '').toUpperCase();
    const foundGroup = getAssetGroup(symbol);

    if (foundGroup) {
      if (!groups.has(foundGroup)) {
        groups.set(foundGroup, {
          label: foundGroup,
          value: 0,
          assets: []
        });
      }
      const group = groups.get(foundGroup);
      group.value += parseFloat(item.value_usd || 0);
      group.assets.push(symbol);
    }
  });

  return Array.from(groups.values());
}

// Convertir au format attendu par l'alias manager (symbol -> group mapping)
export async function getAliasMapping() {
  const taxonomy = await loadTaxonomyData();
  return taxonomy.aliases;
}

// Obtenir tous les groupes disponibles
export async function getAllGroups() {
  const taxonomy = await loadTaxonomyData();
  return taxonomy.groups;
}

// Compatibilité avec l'ancien format (group -> [symbols])
export async function getGroupsFormat() {
  return await getUnifiedAssetGroups();
}

// Force reload taxonomy data (clear cache)
export function forceReloadTaxonomy() {
  (window.debugLogger?.debug || console.log)('🔄 Forcing taxonomy reload...');
  taxonomyCache = null;
  cacheTimestamp = 0;

  // Clear global variables
  KNOWN_ASSET_MAPPING = {};
  UNIFIED_ASSET_GROUPS = {};
  GROUP_ORDER = [];

  // Reload synchronously
  initializeTaxonomySync();

  (window.debugLogger?.info || console.log)('✅ Taxonomy reload completed');
}

// Debug: afficher la classification complète
export async function debugClassification() {
  const groups = await getUnifiedAssetGroups();
  const aliases = await getAliasMapping();

  console.table(groups);
  (window.debugLogger?.debug || console.log)('Total groups:', Object.keys(groups).length);
  (window.debugLogger?.debug || console.log)('Total symbols:', Object.values(groups).flat().length);
  (window.debugLogger?.debug || console.log)('Aliases mapping:', aliases);
}

// Fonction synchrone pour la compatibilité avec l'ancien code - deprecated
export function getAssetGroupSync(symbol) {
  return getAssetGroup(symbol);
}
