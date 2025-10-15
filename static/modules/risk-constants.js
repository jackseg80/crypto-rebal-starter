/**
 * Risk Dashboard - Configuration Constants
 * Cache configuration and other static constants
 */

// ===== CACHE CONFIGURATION =====

/**
 * Cache TTL configuration for different data types
 * Each cache entry has a key (localStorage key) and TTL (time-to-live in ms)
 *
 * Usage: Access via CACHE_CONFIG.SCORES.key or CACHE_CONFIG.SCORES.ttl
 */
export const CACHE_CONFIG = {
  SCORES: {
    key: 'risk_scores_cache',
    ttl: 6 * 60 * 60 * 1000  // 6 heures (peut changer avec trades)
  },
  CCS_DATA: {
    key: 'ccs_data_cache',
    ttl: 6 * 60 * 60 * 1000  // 6 heures
  },
  ONCHAIN: {
    key: 'onchain_data_cache',
    ttl: 6 * 60 * 60 * 1000  // 6 heures (blockchain metrics)
  },
  RISK_METRICS: {
    key: 'risk_metrics_cache',
    ttl: 6 * 60 * 60 * 1000  // 6 heures
  },
  CYCLE_CONTENT: {
    key: 'cycle_content_cache',
    ttl: 24 * 60 * 60 * 1000  // 24 heures HTML (macro)
  },
  CYCLE_DATA: {
    key: 'cycle_data_cache',
    ttl: 24 * 60 * 60 * 1000  // 24 heures données (macro)
  },
  CYCLE_CHART: {
    key: 'cycle_chart_cache',
    ttl: 24 * 60 * 60 * 1000  // 24 heures graphique
  }
};

// ===== Export as default =====
export default CACHE_CONFIG;
