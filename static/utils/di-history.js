/**
 * di-history.js — Gestion historique Decision Index (DI)
 *
 * Fonctionnalités:
 * - Persistence localStorage avec scoping (user_id, source, prod/sim)
 * - Timezone Europe/Zurich pour date-civil
 * - Validation stricte (Number.isFinite)
 * - Delta threshold (enregistrement conditionnel)
 * - Rolling window (max 30 jours)
 */

/**
 * Obtenir la date du jour en timezone Europe/Zurich (format YYYY-MM-DD)
 * @returns {string} Date au format ISO (ex: "2025-10-01")
 */
export function getTodayCH() {
  const fmt = new Intl.DateTimeFormat('fr-CH', {
    timeZone: 'Europe/Zurich',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
  const parts = fmt.formatToParts(new Date());
  const y = parts.find(p => p.type === 'year')?.value;
  const m = parts.find(p => p.type === 'month')?.value;
  const d = parts.find(p => p.type === 'day')?.value;
  return `${y}-${m}-${d}`;
}

/**
 * Générer clé localStorage scopée par user/source/contexte
 * @param {Object} opts - Options { user, source, suffix }
 * @param {string} opts.user - ID utilisateur (défaut: 'demo')
 * @param {string} opts.source - Source de données (défaut: 'cointracking')
 * @param {string} opts.suffix - Suffixe contexte (défaut: '_prod', ou '_sim' pour simulation)
 * @returns {string} Clé localStorage (ex: "di_history_demo_cointracking_prod")
 */
export function makeKey({ user = 'demo', source = 'cointracking', suffix = '_prod' } = {}) {
  return `di_history_${user}_${source}${suffix}`;
}

/**
 * Charger historique depuis localStorage avec sanitization
 * @param {string} key - Clé localStorage
 * @param {number} max - Nombre maximum d'entrées à conserver (défaut: 30)
 * @returns {Array<{date: string, di: number, timestamp: string}>} Historique sanitisé
 */
export function loadHistory(key, max = 30) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];

    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) {
      console.warn('⚠️ DI history: format invalide, expected array');
      return [];
    }

    // Sanitize: garder seulement entrées valides
    const cleaned = arr.filter(e => {
      if (!e || typeof e !== 'object') return false;
      if (typeof e.date !== 'string') return false;
      if (!Number.isFinite(e.di)) return false;
      return true;
    });

    // Trim au max le plus récent
    const trimmed = cleaned.slice(-max);

    return trimmed;
  } catch (e) {
    console.warn('⚠️ DI history load error:', e);
    return [];
  }
}

/**
 * Sauvegarder historique dans localStorage
 * @param {string} key - Clé localStorage
 * @param {Array} history - Historique à sauvegarder
 */
export function saveHistory(key, history) {
  try {
    localStorage.setItem(key, JSON.stringify(history));
  } catch (e) {
    console.error('❌ DI history save error:', e);
  }
}

/**
 * Ajouter entrée DI si nécessaire (date différente OU delta > seuil)
 * @param {Object} opts - Options
 * @param {string} opts.key - Clé localStorage
 * @param {Array} opts.history - Historique actuel
 * @param {string} opts.today - Date du jour (format YYYY-MM-DD)
 * @param {number} opts.di - Score Decision Index
 * @param {number} opts.max - Maximum d'entrées (défaut: 30)
 * @param {number} opts.minDelta - Delta minimum pour enregistrement (défaut: 0.1)
 * @returns {{history: Array, added: boolean}} Nouvel historique et flag ajout
 */
export function pushIfNeeded({ key, history, today, di, max = 30, minDelta = 0.1 }) {
  // Validation stricte du score
  if (!Number.isFinite(di)) {
    console.warn('⚠️ DI history: score invalide (not finite):', di);
    return { history, added: false };
  }

  const last = history[history.length - 1];

  // Déterminer si on doit ajouter
  const need =
    !last ||                                          // Pas d'historique
    last.date !== today ||                            // Nouveau jour
    Math.abs((last.di ?? di) - di) > minDelta;       // Delta significatif

  if (!need) {
    return { history, added: false };
  }

  // Créer nouvelle entrée
  const entry = {
    date: today,
    di,
    timestamp: new Date().toISOString()
  };

  // Ajouter et trim
  const next = [...history, entry].slice(-max);

  // Persister
  saveHistory(key, next);

  return { history: next, added: true };
}

/**
 * Migrer depuis ancien format legacy (s?.di_history)
 * @param {Array} legacyHistory - Historique legacy (array de numbers ou {di: number})
 * @param {number} max - Maximum d'entrées à conserver
 * @returns {Array} Historique au nouveau format
 */
export function migrateLegacy(legacyHistory, max = 30) {
  if (!Array.isArray(legacyHistory)) return [];

  const today = getTodayCH();

  const migrated = legacyHistory
    .filter(e => {
      // Accepter number direct ou object avec .di
      const val = typeof e === 'number' ? e : e?.di;
      return Number.isFinite(val);
    })
    .map((e, idx) => {
      const val = typeof e === 'number' ? e : e.di;
      // Générer dates rétroactives (approximation)
      const daysAgo = legacyHistory.length - 1 - idx;
      const date = new Date();
      date.setDate(date.getDate() - daysAgo);
      const dateStr = date.toISOString().split('T')[0];

      return {
        date: dateStr,
        di: val,
        timestamp: date.toISOString(),
        migrated: true
      };
    })
    .slice(-max);

  return migrated;
}
