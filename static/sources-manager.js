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
  (window.debugLogger?.debug || console.log)(`[${type.toUpperCase()}] ${message}`);
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
  (window.debugLogger?.debug || console.log)('[Sources] Initializing sources manager...');

  // Charger les données initiales
  await refreshSourcesStatus();

  // Démarrer le polling
  startSourcesPolling();

  // Setup événements
  setupSourcesEventHandlers();

  (window.debugLogger?.debug || console.log)('[Sources] Sources manager initialized');
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
    (window.debugLogger?.debug || console.log)('[Sources] Status refreshed:', sourcesData);

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

      // 🔥 NOUVELLE LOGIQUE: Valeur basée sur le nom de fichier pour correspondre au système existant
      const sourceValue = `csv_${index}`;
      const isSelected = isSourceCurrentlySelected(moduleName, sourceValue);

      sources.push(`
        <label class="source-option">
          <input type="radio" name="source-select-${moduleName}" value="${sourceValue}"
                 data-file="${file.name}" data-module="${moduleName}"
                 onchange="selectActiveSource('${moduleName}', '${sourceValue}', '${file.name}')"
                 ${isSelected ? 'checked' : ''}>
          <span class="source-details">
            📄 <strong>${file.name}</strong> <small>(${sizeStr} • ${dateStr}) ${legacyBadge}</small>
          </span>
        </label>
      `);
    });
  }

  // Ajouter l'option API si disponible
  if (module.modes.includes('api')) {
    const apiValue = `${moduleName}_api`;
    const isSelected = isSourceCurrentlySelected(moduleName, apiValue);

    sources.push(`
      <label class="source-option">
        <input type="radio" name="source-select-${moduleName}" value="${apiValue}"
               data-module="${moduleName}"
               onchange="selectActiveSource('${moduleName}', '${apiValue}', null)"
               ${isSelected ? 'checked' : ''}>
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

  // Bouton Tester la source (si API disponible)
  if (module.modes.includes('api')) {
    actions.push(`
      <button class="btn warning btn-sm" onclick="testActiveSource('${module.name}')">
        🧪 Tester la source
      </button>
    `);
  }

  // Bouton Upload (pour modules supportant les fichiers)
  const modulesWithUpload = ['cointracking', 'saxobank', 'banks'];
  if (modulesWithUpload.includes(module.name)) {
    actions.push(`
      <button class="btn secondary btn-sm" onclick="showUploadDialog('${module.name}')">
        📁 Uploader
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
    (window.debugLogger?.debug || console.log)(`[Sources] Scanning module: ${moduleName}`);

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
    (window.debugLogger?.debug || console.log)(`[Sources] Importing selected source: ${selectedSource} from ${moduleName}`);

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
    (window.debugLogger?.debug || console.log)(`[Sources] Importing module: ${moduleName}`);

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
    (window.debugLogger?.debug || console.log)(`[Sources] Refreshing API for module: ${moduleName}`);

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
    (window.debugLogger?.debug || console.log)('[Sources] Scanning all sources...');

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
    (window.debugLogger?.debug || console.log)('[Sources] Scan results:', scanData);

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
  (window.debugLogger?.debug || console.log)(`[Sources] Scan results for ${moduleName}:`, moduleData);
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

  // 🔥 PATCH 5: Écouter les changements d'utilisateur
  // Écouter les changements du sélecteur d'utilisateur
  const userSelector = document.getElementById('user-selector');
  if (userSelector) {
    userSelector.addEventListener('change', () => {
      (window.debugLogger?.debug || console.log)('[Sources] User changed, refreshing sources data...');
      // Rafraîchir immédiatement avec le nouvel utilisateur
      refreshSourcesStatus();
    });
  }

  // Écouter les événements custom de changement d'utilisateur (comme dans nav.js)
  window.addEventListener('userChanged', (event) => {
    (window.debugLogger?.debug || console.log)('[Sources] User changed via event:', event.detail);
    refreshSourcesStatus();
  });
}

/**
 * Vérifie si une source est actuellement sélectionnée pour un module
 */
function isSourceCurrentlySelected(moduleName, sourceValue) {
  try {
    const userConfig = JSON.parse(localStorage.getItem('userConfig') || '{}');
    const currentUser = getCurrentUser();

    if (!userConfig[currentUser]) return false;

    const config = userConfig[currentUser];

    // Pour l'API
    if (sourceValue.includes('_api')) {
      return config.data_source === `${moduleName}_api`;
    }

    // Pour les fichiers CSV - vérifier le fichier spécifique via csv_glob
    if (sourceValue.startsWith('csv_')) {
      if (config.data_source !== 'cointracking') return false;
      // Récupérer le fichier correspondant à sourceValue dans les sources détectées
      const detectedSources = window.sourcesData?.modules?.find(m => m.name === moduleName)?.detected_files || [];
      const sourceIndex = parseInt(sourceValue.replace('csv_', ''));
      const expectedFile = detectedSources[sourceIndex];
      if (!expectedFile) return false;
      // Vérifier si csv_glob correspond à ce fichier spécifique (en enlevant les wildcards)
      if (!config.csv_glob) return false;
      const cleanGlob = config.csv_glob.replace(/\*/g, '');
      return expectedFile.name === cleanGlob || expectedFile.name.includes(cleanGlob) || cleanGlob.includes(expectedFile.name);
    }

    return false;
  } catch (error) {
    console.error('[Sources] Error checking selection:', error);
    return false;
  }
}

/**
 * Sélectionne une source active pour un module
 */
async function selectActiveSource(moduleName, sourceValue, fileName) {
  try {
    (window.debugLogger?.debug || console.log)(`[Sources] Selecting source: ${moduleName} -> ${sourceValue} (${fileName})`);

    const currentUser = getCurrentUser();
    const updateData = {};

    // Déterminer la configuration selon le type de source
    if (sourceValue.includes('_api')) {
      updateData.data_source = sourceValue;
      updateData.csv_glob = '';
    } else if (sourceValue.startsWith('csv_')) {
      updateData.data_source = 'cointracking';
      updateData.csv_glob = fileName ? `*${fileName}*` : '*.csv';
    }

    // ⚠️ CRITIQUE: Récupérer d'abord la config complète pour préserver les clés API
    let completeSettings = {};
    try {
      const getResponse = await safeFetch(`${SOURCES_CONFIG.apiBase.replace('/sources', '')}/users/settings`, {
        headers: { 'X-User': currentUser }
      });
      if (getResponse.ok) {
        completeSettings = await getResponse.json();
      }
    } catch (e) {
      (window.debugLogger?.warn || console.warn)('[Sources] Could not load existing settings, proceeding with partial update:', e);
    }

    // Fusionner les modifications dans la config complète
    Object.assign(completeSettings, updateData);

    // 🐛 DEBUG: Log avant sauvegarde
    (window.debugLogger?.debug || console.log)('[Sources] About to save complete settings:', {
      hasApiKey: !!completeSettings.cointracking_api_key,
      hasApiSecret: !!completeSettings.cointracking_api_secret,
      dataSource: completeSettings.data_source,
      completeSettingsKeys: Object.keys(completeSettings)
    });

    // Appel API pour sauvegarder la config COMPLÈTE
    const response = await safeFetch(`${SOURCES_CONFIG.apiBase.replace('/sources', '')}/users/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User': currentUser
      },
      body: JSON.stringify(completeSettings)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    // Mettre à jour le localStorage local
    const userConfig = JSON.parse(localStorage.getItem('userConfig') || '{}');
    if (!userConfig[currentUser]) userConfig[currentUser] = {};
    Object.assign(userConfig[currentUser], updateData);
    localStorage.setItem('userConfig', JSON.stringify(userConfig));

    // ✅ Synchroniser globalConfig pour le dashboard
    if (window.globalConfig) {
      window.globalConfig.set('data_source', updateData.data_source);
      if (updateData.csv_glob) {
        window.globalConfig.set('csv_glob', updateData.csv_glob);
      }
    }

    // Notifier les autres onglets
    window.dispatchEvent(new CustomEvent('sourceChanged', {
      detail: { user: currentUser, source: sourceValue, module: moduleName }
    }));

    // ✅ Notifier le dashboard pour rafraîchissement immédiat
    window.dispatchEvent(new CustomEvent('dataSourceChanged', {
      detail: {
        oldSource: 'unknown',
        newSource: updateData.data_source,
        user: currentUser
      }
    }));

    (window.debugLogger?.debug || console.log)(`[Sources] ✅ Source selected and saved: ${sourceValue}`);

    // Afficher un feedback visuel temporaire
    showTemporaryFeedback(`Source sélectionnée: ${fileName || sourceValue}`);

  } catch (error) {
    console.error('[Sources] Error selecting source:', error);
    showTemporaryFeedback('❌ Erreur lors de la sélection', 'error');
  }
}

/**
 * Affiche un feedback temporaire à l'utilisateur
 */
function showTemporaryFeedback(message, type = 'success') {
  const feedback = document.createElement('div');
  feedback.className = `temporary-feedback ${type}`;
  feedback.textContent = message;
  feedback.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 10px 15px;
    border-radius: 4px;
    color: white;
    font-weight: 500;
    z-index: 10000;
    transition: opacity 0.3s ease;
    background: ${type === 'error' ? 'var(--danger)' : 'var(--success)'};
  `;

  document.body.appendChild(feedback);

  setTimeout(() => {
    feedback.style.opacity = '0';
    setTimeout(() => feedback.remove(), 300);
  }, 2000);
}

/**
 * Teste la source active pour un module
 */
async function testActiveSource(moduleName) {
  try {
    (window.debugLogger?.debug || console.log)(`[Sources] Testing source for module: ${moduleName}`);

    const currentUser = getCurrentUser();

    // Changer temporairement l'utilisateur actif pour le test
    const originalUser = localStorage.getItem('activeUser');
    localStorage.setItem('activeUser', currentUser);

    // Afficher feedback immédiat
    showTemporaryFeedback('🧪 Test de la source en cours...', 'info');

    // Utiliser la fonction testConnection existante de global-config.js
    if (window.globalConfig && typeof window.globalConfig.testConnection === 'function') {
      const results = await window.globalConfig.testConnection();

      // Restaurer l'utilisateur original
      if (originalUser) {
        localStorage.setItem('activeUser', originalUser);
      }

      // Formater et afficher les résultats
      const status = results.balances === 'Vide' ? 'error' : 'success';
      const message = `📊 Test terminé:
Backend: ${results.backend}
Données: ${results.balances}
Source: ${results.source}`;

      showExtendedFeedback(message, status);
      (window.debugLogger?.debug || console.log)('[Sources] Test results:', results);

    } else {
      throw new Error('testConnection() non disponible');
    }

  } catch (error) {
    console.error(`[Sources] Error testing ${moduleName}:`, error);
    showExtendedFeedback(`❌ Erreur lors du test: ${error.message}`, 'error');
  }
}

/**
 * Affiche un feedback étendu avec plus de détails
 */
function showExtendedFeedback(message, type = 'info') {
  const feedback = document.createElement('div');
  feedback.className = `extended-feedback ${type}`;
  feedback.style.cssText = `
    position: fixed;
    top: 80px;
    right: 20px;
    padding: 15px 20px;
    border-radius: 6px;
    color: white;
    font-weight: 500;
    z-index: 10001;
    max-width: 350px;
    white-space: pre-line;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    transition: opacity 0.3s ease;
    background: ${type === 'error' ? 'var(--danger)' : type === 'success' ? 'var(--success)' : 'var(--info)'};
    border-left: 4px solid rgba(255,255,255,0.3);
  `;

  feedback.textContent = message;
  document.body.appendChild(feedback);

  // Clic pour fermer
  feedback.addEventListener('click', () => {
    feedback.style.opacity = '0';
    setTimeout(() => feedback.remove(), 300);
  });

  // Fermeture automatique après 8s
  setTimeout(() => {
    if (feedback.parentNode) {
      feedback.style.opacity = '0';
      setTimeout(() => feedback.remove(), 300);
    }
  }, 8000);
}

/**
 * Récupère l'utilisateur actuel
 */
function getCurrentUser() {
  const userSelector = document.getElementById('user-selector');
  return userSelector ? userSelector.value : 'demo';
}

// Fonctions d'upload

/**
 * Afficher la boîte de dialogue d'upload
 */
function showUploadDialog(moduleName) {
  (window.debugLogger?.debug || console.log)(`[Sources] Showing upload dialog for: ${moduleName}`);

  const moduleDisplayName = getModuleName(moduleName);
  const allowedExtensions = getModuleAllowedExtensions(moduleName);

  // Créer la modal d'upload
  const modalHTML = `
    <div id="uploadModal" class="modal-overlay">
      <div class="modal-content">
        <div class="modal-header">
          <h3>📁 Upload de fichiers - ${moduleDisplayName}</h3>
          <button class="close-btn" type="button">&times;</button>
        </div>
        <div class="modal-body">
          <p>Extensions autorisées : <strong>${allowedExtensions.join(', ')}</strong></p>
          <p>Taille max : <strong>10MB par fichier, 50MB total</strong></p>

          <div class="upload-area" id="uploadArea">
            <div class="upload-placeholder">
              📄 Cliquez ici ou glissez-déposez vos fichiers
            </div>
            <input type="file" id="fileInput" multiple accept="${allowedExtensions.join(',')}" style="display: none;">
          </div>

          <div id="fileList" class="file-list"></div>

          <div class="upload-progress" id="uploadProgress" style="display: none;">
            <div class="progress-bar">
              <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="progress-text" id="progressText"></div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" type="button" id="cancelBtn">Annuler</button>
          <button class="btn primary" type="button" id="uploadBtn" disabled>
            📤 Uploader
          </button>
        </div>
      </div>
    </div>
  `;

  // Ajouter la modal au DOM
  document.body.insertAdjacentHTML('beforeend', modalHTML);

  // Ajouter les event listeners après création de la modal
  setupModalEvents(moduleName);

  // Gérer le drag & drop
  setupDragAndDrop();
}

/**
 * Configurer les événements de la modal
 */
function setupModalEvents(moduleName) {
  const modal = document.getElementById('uploadModal');
  const closeBtn = modal.querySelector('.close-btn');
  const cancelBtn = document.getElementById('cancelBtn');
  const uploadBtn = document.getElementById('uploadBtn');
  const uploadArea = document.getElementById('uploadArea');
  const fileInput = document.getElementById('fileInput');

  // Fermeture avec le bouton X
  if (closeBtn) {
    closeBtn.addEventListener('click', () => closeUploadDialog());
  }

  // Fermeture avec le bouton Annuler
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => closeUploadDialog());
  }

  // Upload avec le bouton principal
  if (uploadBtn) {
    uploadBtn.addEventListener('click', () => uploadFiles(moduleName));
  }

  // Clic sur la zone d'upload
  if (uploadArea) {
    uploadArea.addEventListener('click', () => {
      if (fileInput) fileInput.click();
    });
  }

  // Changement de fichier
  if (fileInput) {
    fileInput.addEventListener('change', handleFileSelection);
  }

  // Fermeture en cliquant sur l'overlay (mais pas sur le contenu)
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeUploadDialog();
      }
    });
  }

  // Fermeture avec la touche Escape
  document.addEventListener('keydown', function escapeHandler(e) {
    if (e.key === 'Escape') {
      closeUploadDialog();
      document.removeEventListener('keydown', escapeHandler);
    }
  });

  (window.debugLogger?.debug || console.log)('[Sources] Modal events configured');
}

/**
 * Fermer la boîte de dialogue d'upload
 */
function closeUploadDialog(event) {
  // Si c'est un clic sur l'overlay, vérifier que c'est bien l'overlay et pas un enfant
  if (event && event.target && !event.target.classList.contains('modal-overlay')) {
    return;
  }

  (window.debugLogger?.debug || console.log)('[Sources] Closing upload dialog');

  const modal = document.getElementById('uploadModal');
  if (modal) {
    // Ajouter une animation de fermeture
    modal.style.opacity = '0';
    setTimeout(() => {
      if (modal.parentNode) {
        modal.remove();
      }
    }, 200);
  }
}

/**
 * Forcer la fermeture de la modal (fallback)
 */
function forceCloseUploadDialog() {
  (window.debugLogger?.debug || console.log)('[Sources] Force closing upload dialog');
  const modal = document.getElementById('uploadModal');
  if (modal) {
    modal.remove();
  }

  // Nettoyer aussi d'éventuelles modals orphelines
  const orphanModals = document.querySelectorAll('.modal-overlay');
  orphanModals.forEach(m => m.remove());
}

/**
 * Configurer le drag & drop
 */
function setupDragAndDrop() {
  const uploadArea = document.getElementById('uploadArea');
  if (!uploadArea) return;

  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
  });

  uploadArea.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
  });

  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');

    const files = Array.from(e.dataTransfer.files);
    document.getElementById('fileInput').files = e.dataTransfer.files;
    handleFileSelection();
  });
}

/**
 * Gérer la sélection de fichiers
 */
function handleFileSelection() {
  const fileInput = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const uploadBtn = document.getElementById('uploadBtn');

  if (!fileInput || !fileList || !uploadBtn) return;

  const files = Array.from(fileInput.files);

  if (files.length === 0) {
    fileList.innerHTML = '';
    uploadBtn.disabled = true;
    return;
  }

  // Afficher la liste des fichiers
  fileList.innerHTML = files.map(file => `
    <div class="file-item">
      <span class="file-name">📄 ${file.name}</span>
      <span class="file-size">${formatFileSize(file.size)}</span>
    </div>
  `).join('');

  uploadBtn.disabled = false;
}

/**
 * Uploader les fichiers
 */
async function uploadFiles(moduleName) {
  const fileInput = document.getElementById('fileInput');
  const uploadProgress = document.getElementById('uploadProgress');
  const progressFill = document.getElementById('progressFill');
  const progressText = document.getElementById('progressText');
  const uploadBtn = document.getElementById('uploadBtn');

  if (!fileInput || !fileInput.files.length) {
    showNotification('Aucun fichier sélectionné', 'warning');
    return;
  }

  try {
    // Afficher la progression
    uploadProgress.style.display = 'block';
    uploadBtn.disabled = true;
    progressFill.style.width = '0%';
    progressText.textContent = 'Préparation...';

    // Préparer les données
    const formData = new FormData();
    formData.append('module', moduleName);

    Array.from(fileInput.files).forEach(file => {
      formData.append('files', file);
    });

    const currentUser = getCurrentUser();

    // Upload avec progression
    const response = await fetch(`${SOURCES_CONFIG.apiBase}/upload`, {
      method: 'POST',
      headers: {
        'X-User': currentUser
      },
      body: formData
    });

    progressFill.style.width = '100%';
    progressText.textContent = 'Traitement...';

    const result = await response.json();

    if (result.success) {
      showNotification(result.message, 'success');
      closeUploadDialog();
      // Rafraîchir les sources après upload
      setTimeout(() => refreshSourcesStatus(), 1000);
    } else {
      showNotification(`Erreur d'upload: ${result.error || result.message}`, 'error');
    }

  } catch (error) {
    console.error(`[Sources] Upload error:`, error);
    showNotification('Erreur lors de l\'upload', 'error');
  } finally {
    uploadBtn.disabled = false;
    uploadProgress.style.display = 'none';
  }
}

/**
 * Obtenir les extensions autorisées pour un module
 */
function getModuleAllowedExtensions(moduleName) {
  const extensions = {
    'cointracking': ['.csv'],
    'saxobank': ['.csv', '.json'],
    'banks': ['.csv', '.xlsx', '.json']
  };
  return extensions[moduleName] || ['.csv'];
}

// Export des fonctions principales pour l'usage dans settings.html
window.initSourcesManager = initSourcesManager;
window.refreshSourcesStatus = refreshSourcesStatus;
window.scanAllSources = scanAllSources;
window.scanModule = scanModule;
window.importModule = importModule;
window.refreshModuleApi = refreshModuleApi;
window.selectActiveSource = selectActiveSource;
window.isSourceCurrentlySelected = isSourceCurrentlySelected;
window.testActiveSource = testActiveSource;
window.showUploadDialog = showUploadDialog;
window.forceCloseUploadDialog = forceCloseUploadDialog;