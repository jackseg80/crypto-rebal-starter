/**
 * Gestionnaire du nouveau système Sources unifié
 * Remplace la logique CSV et Intégrations par un système centralisé
 */

// Utilitaire fetch simple avec retry et headers utilisateur
async function safeFetch(url, options = {}) {
  const maxRetries = 3;
  let lastError;

  // Ajouter les headers par défaut incluant X-User
  const currentUser = window.getCurrentUser ? window.getCurrentUser() : 'demo';
  const defaultHeaders = {
    'X-User': currentUser, // Utilisateur actuel depuis nav.js
    'Content-Type': 'application/json'
  };

  const mergedOptions = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers
    }
  };

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, mergedOptions);
      return response; // Retourne même les erreurs HTTP pour que le caller puisse les gérer
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
    }
  }

  throw lastError;
}

// Utilitaire pour les notifications
function showNotification(message, type = 'info') {
  console.log(`[${type.toUpperCase()}] ${message}`);
  // Fallback simple - chercher un element notification existant ou créer
  let notificationArea = document.querySelector('.notification-area');
  if (!notificationArea) {
    notificationArea = document.createElement('div');
    notificationArea.className = 'notification-area';
    notificationArea.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
    document.body.appendChild(notificationArea);
  }

  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.style.cssText = `
    background: var(--theme-surface);
    border: 1px solid var(--theme-border);
    border-radius: 4px;
    padding: 12px 16px;
    margin-bottom: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    max-width: 300px;
    animation: slideIn 0.3s ease-out;
  `;

  // Couleurs selon le type
  if (type === 'success') notification.style.borderLeftColor = '#28a745';
  if (type === 'error') notification.style.borderLeftColor = '#dc3545';
  if (type === 'warning') notification.style.borderLeftColor = '#ffc107';

  notification.textContent = message;
  notificationArea.appendChild(notification);

  // Auto-dismiss après 5s
  setTimeout(() => {
    notification.remove();
    if (notificationArea.children.length === 0) {
      notificationArea.remove();
    }
  }, 5000);
}

// Configuration globale
const SOURCES_CONFIG = {
  apiBase: '/api/sources',
  modules: ['cointracking', 'saxobank'],
  refreshInterval: 30000, // 30s
};

// État global
let sourcesData = null;
let refreshTimer = null;

/**
 * Initialise le gestionnaire de sources
 */
async function initSourcesManager() {
  console.log('[Sources] Initializing sources manager...');

  // Charger les données initiales
  await refreshSourcesStatus();

  // Démarrer le polling
  startSourcesPolling();

  // Setup événements
  setupSourcesEventHandlers();

  console.log('[Sources] Sources manager initialized');
}

/**
 * Rafraîchit le status de toutes les sources
 */
async function refreshSourcesStatus() {
  try {
    const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/list`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    sourcesData = await response.json();
    console.log('[Sources] Status refreshed:', sourcesData);

    // Mettre à jour l'UI
    updateSourcesUI(sourcesData);

    return sourcesData;

  } catch (error) {
    console.error('[Sources] Error refreshing status:', error);

    // Affichage d'erreur
    const statusEl = document.getElementById('sources_status');
    if (statusEl) {
      statusEl.textContent = 'Erreur de connexion';
      statusEl.className = 'error';
    }

    return null;
  }
}

/**
 * Met à jour l'interface utilisateur avec les données sources
 */
function updateSourcesUI(data) {
  if (!data || !data.modules) return;

  // Mettre à jour les statuts globaux
  updateGlobalStatus(data);

  // Mettre à jour la grille des modules
  updateModulesGrid(data.modules);
}

/**
 * Met à jour les statuts globaux
 */
function updateGlobalStatus(data) {
  const activeCount = data.modules.filter(m => m.enabled).length;
  const lastActivity = data.modules
    .filter(m => m.last_import_at)
    .sort((a, b) => new Date(b.last_import_at) - new Date(a.last_import_at))[0];

  // Compteur actif
  const activeCountEl = document.getElementById('sources_active_count');
  if (activeCountEl) {
    activeCountEl.textContent = `${activeCount}/${data.modules.length}`;
  }

  // Dernière activité
  const lastActivityEl = document.getElementById('sources_last_activity');
  if (lastActivityEl) {
    if (lastActivity) {
      const date = new Date(lastActivity.last_import_at);
      lastActivityEl.textContent = formatRelativeTime(date);
    } else {
      lastActivityEl.textContent = 'Aucune activité';
    }
  }

  // Status global
  const statusEl = document.getElementById('sources_status');
  if (statusEl) {
    const hasStale = data.modules.some(m => m.staleness.state === 'stale');
    const hasWarning = data.modules.some(m => m.staleness.state === 'warning');

    if (hasStale) {
      statusEl.textContent = 'Données obsolètes';
      statusEl.className = 'error';
    } else if (hasWarning) {
      statusEl.textContent = 'Avertissement';
      statusEl.className = 'warning';
    } else {
      statusEl.textContent = 'Opérationnel';
      statusEl.className = 'success';
    }
  }
}

/**
 * Met à jour la grille des modules
 */
function updateModulesGrid(modules) {
  const gridEl = document.getElementById('sources_modules_grid');
  if (!gridEl) return;

  gridEl.innerHTML = '';

  for (const module of modules) {
    const card = createModuleCard(module);
    gridEl.appendChild(card);
  }
}

/**
 * Crée une carte de module
 */
function createModuleCard(module) {
  const card = document.createElement('div');
  card.className = 'module-card';
  card.dataset.module = module.name;

  const staleness = module.staleness || {};
  const statusClass = getStatusClass(staleness.state);

  card.innerHTML = `
    <div class="module-header">
      <h4>${getModuleIcon(module.name)} ${getModuleName(module.name)}</h4>
      <span class="status-badge ${statusClass}">${getStatusText(staleness.state, staleness.age_hours)}</span>
    </div>

    <div class="module-content">
      <p>${getModuleDescription(module.name)}</p>

      <div class="module-stats">
        <div class="stat-item">
          <span class="label">Fichiers détectés:</span>
          <span class="value">${module.files_detected || 0}</span>
        </div>

        <div class="stat-item">
          <span class="label">Modes:</span>
          <span class="value">${module.modes.join(', ')}</span>
        </div>

        ${module.last_import_at ? `
        <div class="stat-item">
          <span class="label">Dernier import:</span>
          <span class="value">${formatRelativeTime(new Date(module.last_import_at))}</span>
        </div>
        ` : ''}
      </div>

      ${(module.detected_files && module.detected_files.length > 0) || module.modes.includes('api') ? `
      <div class="sources-section">
        <h5>📥 Source d'import</h5>
        <div class="sources-list" id="sources-list-${module.name}">
          ${createSourcesList(module.name, module)}
        </div>
      </div>
      ` : ''}
    </div>

    <div class="module-actions">
      ${createModuleActions(module)}
    </div>
  `;

  return card;
}

/**
 * Crée la liste des sources avec radio buttons (fichiers + API)
 */
function createSourcesList(moduleName, module) {
  const sources = [];

  // Ajouter les fichiers
  if (module.detected_files) {
    module.detected_files.forEach((file, index) => {
      const sizeStr = formatFileSize(file.size_bytes);
      const dateStr = formatRelativeTime(new Date(file.modified_at));
      const legacyBadge = file.is_legacy ? '<small class="legacy">Legacy</small>' : '';

      sources.push(`
        <label class="source-option">
          <input type="radio" name="source-${moduleName}" value="file:${file.relative_path}"
                 ${index === 0 ? 'checked' : ''}>
          <span class="source-details">
            📄 <strong>${file.name}</strong> <small>(${sizeStr} • ${dateStr}) ${legacyBadge}</small>
          </span>
        </label>
      `);
    });
  }

  // Ajouter l'option API si disponible
  if (module.modes.includes('api')) {
    sources.push(`
      <label class="source-option">
        <input type="radio" name="source-${moduleName}" value="api">
        <span class="source-details">
          🌐 <strong>API</strong> <small>(données temps réel)</small>
        </span>
      </label>
    `);
  }

  return sources.join('');
}

/**
 * Formate la taille d'un fichier
 */
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
  return Math.round(bytes / (1024 * 1024)) + ' MB';
}

/**
 * Récupère la source sélectionnée pour un module
 */
function getSelectedSource(moduleName) {
  const radioButton = document.querySelector(`input[name="source-${moduleName}"]:checked`);
  return radioButton ? radioButton.value : null;
}

/**
 * Crée les boutons d'action pour un module
 */
function createModuleActions(module) {
  const actions = [];

  // Bouton Scanner (toujours disponible)
  actions.push(`
    <button class="btn info btn-sm" onclick="scanModule('${module.name}')">
      🔍 Scanner
    </button>
  `);

  // Bouton Import unifié (si sources disponibles)
  if ((module.detected_files && module.detected_files.length > 0) || module.modes.includes('api')) {
    actions.push(`
      <button class="btn primary btn-sm" onclick="importSelectedSource('${module.name}')">
        📥 Importer
      </button>
    `);
  }

  return actions.join('');
}

// Fonctions utilitaires

function getModuleIcon(moduleName) {
  const icons = {
    cointracking: '🪙',
    saxobank: '🏦',
    banks: '🏪'
  };
  return icons[moduleName] || '📊';
}

function getModuleName(moduleName) {
  const names = {
    cointracking: 'CoinTracking',
    saxobank: 'Saxo Bank',
    banks: 'Banques'
  };
  return names[moduleName] || moduleName;
}

function getModuleDescription(moduleName) {
  const descriptions = {
    cointracking: 'Cryptomonnaies via API CoinTracking et imports CSV',
    saxobank: 'Positions boursières via imports CSV Saxo Bank',
    banks: 'Comptes bancaires et liquidités'
  };
  return descriptions[moduleName] || 'Module de données financières';
}

function getStatusClass(state) {
  const classes = {
    fresh: 'enabled success',
    warning: 'warning',
    stale: 'disabled error'
  };
  return classes[state] || 'disabled';
}

function getStatusText(state, ageHours) {
  if (state === 'fresh') return 'À jour';
  if (state === 'warning') return `Attention (${ageHours}h)`;
  if (state === 'stale') return ageHours ? `Obsolète (${ageHours}h)` : 'Obsolète';
  return 'Non configuré';
}

function formatRelativeTime(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `${diffDays}j`;
  } else if (diffHours > 0) {
    return `${diffHours}h`;
  } else {
    return 'Maintenant';
  }
}

// Actions des modules

/**
 * Scanner un module pour voir les fichiers détectés
 */
async function scanModule(moduleName) {
  try {
    console.log(`[Sources] Scanning module: ${moduleName}`);

    const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/scan`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const scanData = await response.json();
    const moduleData = scanData.modules[moduleName];

    if (moduleData) {
      showScanResults(moduleName, moduleData);
    } else {
      showNotification(`Aucun fichier détecté pour ${getModuleName(moduleName)}`, 'info');
    }

  } catch (error) {
    console.error(`[Sources] Error scanning ${moduleName}:`, error);
    showNotification(`Erreur lors du scan de ${getModuleName(moduleName)}`, 'error');
  }
}

/**
 * Importer la source sélectionnée (fichier ou API)
 */
async function importSelectedSource(moduleName) {
  const selectedSource = getSelectedSource(moduleName);

  if (!selectedSource) {
    showNotification('Aucune source sélectionnée', 'warning');
    return;
  }

  try {
    console.log(`[Sources] Importing selected source: ${selectedSource} from ${moduleName}`);

    let requestBody;

    if (selectedSource === 'api') {
      // Import via API
      const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/refresh-api`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          module: moduleName
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        const recordsText = result.records_fetched ? ` (${result.records_fetched} enregistrements)` : '';
        showNotification(`API import réussi: ${result.message}${recordsText}`, 'success');
        setTimeout(() => refreshSourcesStatus(), 1000);
      } else {
        showNotification(`Erreur API: ${result.error || result.message}`, 'error');
      }

    } else if (selectedSource.startsWith('file:')) {
      // Import d'un fichier spécifique
      const filePath = selectedSource.substring(5); // Enlever "file:"

      const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          module: moduleName,
          files: [filePath]
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        showNotification(`Import réussi: ${result.message}`, 'success');
        setTimeout(() => refreshSourcesStatus(), 1000);
      } else {
        showNotification(`Erreur d'import: ${result.error || result.message}`, 'error');
      }
    }

  } catch (error) {
    console.error(`[Sources] Error importing selected source from ${moduleName}:`, error);
    showNotification(`Erreur lors de l'import de ${getModuleName(moduleName)}`, 'error');
  }
}

/**
 * Importer un module (legacy - utilise tous les fichiers)
 */
async function importModule(moduleName, force = false) {
  try {
    console.log(`[Sources] Importing module: ${moduleName}`);

    const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        module: moduleName,
        force: force
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      showNotification(`Import réussi: ${result.message}`, 'success');

      // Rafraîchir les données
      setTimeout(() => refreshSourcesStatus(), 1000);
    } else {
      showNotification(`Erreur d'import: ${result.error || result.message}`, 'error');
    }

  } catch (error) {
    console.error(`[Sources] Error importing ${moduleName}:`, error);
    showNotification(`Erreur lors de l'import de ${getModuleName(moduleName)}`, 'error');
  }
}

/**
 * Refresh API pour un module
 */
async function refreshModuleApi(moduleName) {
  try {
    console.log(`[Sources] Refreshing API for module: ${moduleName}`);

    const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/refresh-api`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        module: moduleName
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      const recordsText = result.records_fetched ? ` (${result.records_fetched} enregistrements)` : '';
      showNotification(`API rafraîchie: ${result.message}${recordsText}`, 'success');

      // Rafraîchir les données
      setTimeout(() => refreshSourcesStatus(), 1000);
    } else {
      showNotification(`Erreur API: ${result.error || result.message}`, 'error');
    }

  } catch (error) {
    console.error(`[Sources] Error refreshing API for ${moduleName}:`, error);
    showNotification(`Erreur lors du refresh API de ${getModuleName(moduleName)}`, 'error');
  }
}

/**
 * Scanner toutes les sources
 */
async function scanAllSources() {
  try {
    console.log('[Sources] Scanning all sources...');

    const response = await safeFetch(`${SOURCES_CONFIG.apiBase}/scan`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const scanData = await response.json();

    // Afficher un résumé
    const moduleCount = Object.keys(scanData.modules).length;
    const totalFiles = Object.values(scanData.modules).reduce((sum, m) => sum + m.files_detected.length, 0);

    showNotification(`Scan terminé: ${totalFiles} fichiers détectés dans ${moduleCount} modules`, 'success');

    // Optionnel: afficher détails dans console
    console.log('[Sources] Scan results:', scanData);

  } catch (error) {
    console.error('[Sources] Error scanning all sources:', error);
    showNotification('Erreur lors du scan global', 'error');
  }
}

/**
 * Affiche les résultats de scan pour un module
 */
function showScanResults(moduleName, moduleData) {
  const filesCount = moduleData.files_detected.length;
  const isLegacy = moduleData.is_legacy ? ' (legacy)' : '';

  let message = `${getModuleName(moduleName)}: ${filesCount} fichier(s) détecté(s)${isLegacy}`;

  if (moduleData.estimated_records) {
    message += ` (~${moduleData.estimated_records} enregistrements)`;
  }

  showNotification(message, 'info');

  // Log détaillé dans console
  console.log(`[Sources] Scan results for ${moduleName}:`, moduleData);
}

/**
 * Polling automatique
 */
function startSourcesPolling() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }

  refreshTimer = setInterval(() => {
    refreshSourcesStatus();
  }, SOURCES_CONFIG.refreshInterval);
}

function stopSourcesPolling() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

/**
 * Setup des événements
 */
function setupSourcesEventHandlers() {
  // Cleanup au changement de page
  window.addEventListener('beforeunload', () => {
    stopSourcesPolling();
  });

  // Visibilité de page pour optimiser le polling
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopSourcesPolling();
    } else {
      startSourcesPolling();
      refreshSourcesStatus(); // Refresh immédiat en reprenant focus
    }
  });
}

// Export des fonctions principales pour l'usage dans settings.html
window.initSourcesManager = initSourcesManager;
window.refreshSourcesStatus = refreshSourcesStatus;
window.scanAllSources = scanAllSources;
window.scanModule = scanModule;
window.importModule = importModule;
window.refreshModuleApi = refreshModuleApi;