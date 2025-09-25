/**
 * Sélecteurs centralisés pour les données de gouvernance
 * Source unique de vérité pour contradiction_index et autres métriques governance
 */

/**
 * Sélecteur principal pour contradiction (valeur 0-1 normalisée)
 * @param {Object} state - État unifié
 * @returns {number} - Valeur 0-1 (0 = pas de contradiction, 1 = contradiction maximale)
 */
export function selectContradiction01(state) {
  const raw = state?.governance?.contradiction_index ?? 0;
  const c = raw > 1 ? raw / 100 : raw; // Normalise 0-100 vers 0-1
  return Math.max(0, Math.min(1, Number.isFinite(c) ? c : 0));
}

/**
 * Sélecteur pour contradiction en pourcentage (affichage UI)
 * @param {Object} state - État unifié
 * @returns {number} - Valeur 0-100 (entier arrondi)
 */
export function selectContradictionPct(state) {
  return Math.round(selectContradiction01(state) * 100);
}

/**
 * Sélecteur avec compatibilité legacy (temporaire)
 * @param {Object} state - État unifié
 * @returns {number} - Valeur 0-100 avec fallback
 */
export function getContradictionPctCompat(state) {
  const primary = selectContradictionPct(state);
  if (Number.isFinite(primary) && primary > 0) return primary;

  // Fallback vers anciennes sources (à supprimer progressivement)
  console.warn("⚠️ Fallback to legacy contradiction source - update code to use governance.contradiction_index");
  const legacyCount = state?.scores?.contradictory_signals?.length ??
                     state?.contradictions?.length ?? 0;
  return Math.min(100, legacyCount * 20); // 0-5 signals → 0-100%
}

/**
 * Sélecteur pour le timestamp de dernière mise à jour
 * @param {Object} state - État unifié
 * @returns {string|null} - ISO timestamp ou null
 */
export function selectGovernanceTimestamp(state) {
  return state?.governance?.ml_signals?.updated ||
         state?.governance?.ml_signals_timestamp ||
         state?.governance?.next_update_time ||
         state?.governance?.updated ||
         null;
}

/**
 * Sélecteur pour la source de décision ML
 * @param {Object} state - État unifié
 * @returns {string} - 'backend'|'blended'|'fallback'
 */
export function selectDecisionSource(state) {
  return state?.governance?.ml_signals?.decision_source ||
         state?.governance?.decision_source ||
         'backend';
}

function normalizeCapToPercent(raw) {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) {
    return null;
  }
  const absolute = Math.abs(raw);
  const percent = absolute <= 1 ? absolute * 100 : absolute;
  const rounded = Math.round(percent);
  return Number.isFinite(rounded) ? rounded : null;
}

export function selectPolicyCapPercent(state) {
  try {
    const raw = state?.governance?.active_policy?.cap_daily ??
                state?.governance?.policy?.cap_daily;
    return normalizeCapToPercent(raw);
  } catch (error) {
    console.debug('selectPolicyCapPercent failed', error);
    return null;
  }
}

export function selectEngineCapPercent(state) {
  try {
    const raw = state?.governance?.engine_cap_daily ??
                state?.governance?.caps?.engine_cap ??
                state?.governance?.computed_cap;
    return normalizeCapToPercent(raw);
  } catch (error) {
    console.debug('selectEngineCapPercent failed', error);
    return null;
  }
}

export function selectCapPercent(state) {
  try {
    const policyCap = selectPolicyCapPercent(state);
    if (policyCap != null) {
      return policyCap;
    }

    const engineCap = selectEngineCapPercent(state);
    if (engineCap != null) {
      return engineCap;
    }
  } catch (error) {
    console.debug('selectCapPercent failed', error);
  }
  return null;
}

/**
 * Sélecteur pour le cap effectif (priorité: error > stale > alert > engine > policy)
 * @param {Object} state - État unifié
 * @returns {number|null} - Cap effectif en pourcentage
 */
export function selectEffectiveCap(state) {
  try {
    const backendStatus = state?.ui?.apiStatus?.backend;
    if (backendStatus === 'error' || backendStatus === 'failed') {
      return 5;
    }

    const updated = selectGovernanceTimestamp(state);
    const stale = (() => {
      if (!updated) return true;
      const ts = new Date(updated);
      if (Number.isNaN(ts.getTime())) return true;
      return Date.now() - ts.getTime() > 30 * 60 * 1000;
    })();
    if (backendStatus === 'stale' || stale) {
      return 8;
    }

    const alertCap = normalizeCapToPercent(state?.governance?.caps?.alert_cap ?? state?.alerts?.active_cap);
    if (alertCap != null) {
      return alertCap;
    }

    const policyCap = selectCapPercent(state);
    if (policyCap != null) {
      return policyCap;
    }

    const engineCap = selectEngineCapPercent(state);
    if (engineCap != null) {
      return engineCap;
    }
  } catch (error) {
    console.debug('selectEffectiveCap failed', error);
  }
  return null;
}

/**
 * Sélecteur pour le nombre d'overrides actifs
 * @param {Object} state - État unifié
 * @returns {number} - Nombre d'overrides (0 si aucun)
 */
export function selectOverridesCount(state) {
  try {
    const overrides = state?.governance?.overrides ||
                     state?.governance?.active_overrides ||
                     state?.overrides ||
                     [];

    if (Array.isArray(overrides)) {
      return overrides.length;
    }

    if (typeof overrides === 'object' && overrides !== null) {
      return Object.keys(overrides).filter(key => overrides[key]).length;
    }

    // Check specific override flags
    let count = 0;
    if (state?.governance?.flags?.euphoria_override) count++;
    if (state?.governance?.flags?.divergence_override) count++;
    if (state?.governance?.flags?.risk_low_override) count++;

    return count;
  } catch (error) {
    console.warn("Error counting overrides:", error);
    return 0;
  }
}