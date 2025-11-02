// Active user helper for per-user settings
function getActiveUser() {
  try {
    const u = localStorage.getItem('activeUser');
    return u && typeof u === 'string' ? u : 'demo';
  } catch (_) { return 'demo'; }
}
// Back-compat: expose currentUser
window.currentUser = getActiveUser();
// Construit dynamiquement les contrôles de source de données à partir de la source centralisée
// Construit le dropdown de sélection rapide dans l'onglet Résumé
async function buildQuickSourceDropdown() {
  try {
    // Utiliser le nouveau système sources qui lit depuis data/
    const response = await fetch('/api/sources/list', {
      headers: { 'X-User': getActiveUser() }
    });

    if (!response.ok) return;

    const data = await response.json();
    const sources = [];

    // Construire la liste des sources depuis les modules
    for (const module of (data.modules || [])) {
      // Ajouter l'option API si disponible
      if (module.modes.includes('api')) {
        sources.push({
          key: `${module.name}_api`,
          label: `${module.name === 'cointracking' ? 'CoinTracking' : 'Saxo'} API`,
          type: 'api',
          module: module.name
        });
      }

      // Ajouter chaque fichier CSV détecté
      if (module.detected_files && module.detected_files.length > 0) {
        module.detected_files.forEach((file, index) => {
          sources.push({
            key: `csv_${module.name}_${index}`,
            label: `${module.name === 'cointracking' ? 'CoinTracking' : 'Saxo'}: ${file.name}`,
            type: 'csv',
            module: module.name,
            file_name: file.name,
            file_path: file.relative_path
          });
        });
      }
    }

    window.availableSources = sources; // Pour lookup lors de la sélection

    const quickSelect = document.getElementById('quick_data_source');
    if (quickSelect) {
      quickSelect.innerHTML = '';
      for (const source of sources) {
        const opt = document.createElement('option');
        opt.value = source.key;
        opt.textContent = source.label;
        quickSelect.appendChild(opt);
      }
    }
  } catch (error) {
    debugLogger.error('Error loading sources for dropdown:', error);
  }
}

// Système de debounce unique et global pour toutes les sauvegardes
if (!window.settingsSaveTimeout) {
  window.settingsSaveTimeout = null;
}
window.debouncedSaveSettings = function() {
  if (window.settingsSaveTimeout) clearTimeout(window.settingsSaveTimeout);
  window.settingsSaveTimeout = setTimeout(async () => {
    try {
      await saveSettings();
      showNotification('✓ Sauvegardé', 'success', 1500);
    } catch (err) {
      debugLogger.error('Auto-save failed:', err);
      showNotification('✗ Erreur sauvegarde', 'error', 2500);
    }
  }, 800);
};

// Initialisation des réglages rapides (onglet Résumé)
async function initQuickSettings() {
  const s = window.userSettings || getDefaultSettings();
  await buildQuickSourceDropdown();

  // Valeurs initiales
  if (document.getElementById('quick_data_source')) {
    const quickEl = document.getElementById('quick_data_source');
    quickEl.value = s.data_source || 'stub_balanced';
    // Si un CSV spécifique a été choisi, refléter la clé correspondante
    try {
      const list = window.availableSources || [];
      if ((s.data_source === 'csv' || s.data_source === 'cointracking' || s.data_source === 'saxobank') && s.csv_selected_file) {
        const match = list.find(src => src.type === 'csv' && src.file_name === s.csv_selected_file);
        if (match) quickEl.value = match.key;
      } else if (s.data_source && s.data_source.endsWith('_api')) {
        const match = list.find(src => src.key === s.data_source);
        if (match) quickEl.value = match.key;
      }
    } catch (_) { }
  }
  document.getElementById('quick_pricing').value = s.pricing || 'auto';
  document.getElementById('quick_min_usd').value = (s.min_usd_threshold ?? 1);
  document.getElementById('quick_currency').value = s.display_currency || 'USD';
  document.getElementById('quick_theme').value = s.theme || 'auto';
  document.getElementById('quick_api_base_url').value = s.api_base_url || window.location.origin;

  // Note: Le cochage des radios est maintenant géré par updateUI() qui est appelé APRÈS
  // buildDataSourceControls(), donc les radios existent déjà quand updateUI() s'exécute

  // Listeners: appliquent immédiatement + auto-save vers backend
  if (document.getElementById('quick_data_source')) {
    document.getElementById('quick_data_source').addEventListener('change', async (e) => {
      const key = e.target.value;
      // Si l'utilisateur choisit un CSV spécifique via le select, enregistrer le fichier
      try {
        const src = (window.availableSources || []).find(s => s.key === key);
        if (src && src.type === 'csv') {
          const fname = src.file_name;  // Utiliser directement file_name
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.data_source = src.module;  // cointracking ou saxobank
          window.userSettings.csv_selected_file = fname || null;
          if (window.globalConfig) {
            window.globalConfig.set('data_source', src.module);
            window.globalConfig.set('csv_selected_file', fname);
          }
          await saveSettings(); // Auto-save immédiat pour changement de source
          updateStatusSummary();
          showNotification('✓ Source changée et sauvegardée', 'success');
          return;
        } else if (src && src.type === 'api') {
          // Mode API sélectionné
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.data_source = src.key;  // cointracking_api ou saxobank_api
          window.userSettings.csv_selected_file = null;
          if (window.globalConfig) {
            window.globalConfig.set('data_source', src.key);
            window.globalConfig.set('csv_selected_file', null);
          }
          await saveSettings(); // Auto-save immédiat pour changement de source
          updateStatusSummary();
          showNotification('✓ Source changée et sauvegardée', 'success');
          return;
        }
      } catch (err) {
        console.error('Error selecting source:', err);
      }
      // Fallback sur l'ancien système
      await selectDataSource(key);
    });
  }
  document.getElementById('quick_pricing').addEventListener('change', async (e) => {
    await selectPricing(e.target.value);
    // selectPricing() already calls debouncedSaveSettings()
  });
  document.getElementById('quick_min_usd').addEventListener('change', (e) => {
    if (!window.userSettings) window.userSettings = getDefaultSettings();
    const val = parseFloat(e.target.value) || 0;
    window.userSettings.min_usd_threshold = val;
    if (window.globalConfig) window.globalConfig.set('min_usd_threshold', val);
    // Synchroniser l'autre champ
    const mainInput = document.getElementById('min_usd_threshold');
    if (mainInput) mainInput.value = val;
    window.debouncedSaveSettings();
  });
  document.getElementById('quick_currency').addEventListener('change', async (e) => {
    const val = e.target.value;
    if (!window.userSettings) window.userSettings = getDefaultSettings();
    window.userSettings.display_currency = val;
    if (window.globalConfig) window.globalConfig.set('display_currency', val);
    const mainSel = document.getElementById('display_currency');
    if (mainSel) mainSel.value = val;
    try { if (window.currencyManager && val !== 'USD') await window.currencyManager.ensureRate(val); } catch (_) { }
    updateStatusSummarySync();
    window.debouncedSaveSettings();
  });
  document.getElementById('quick_theme').addEventListener('change', async (e) => {
    await selectTheme(e.target.value);
    // selectTheme() already calls debouncedSaveSettings()
  });
  document.getElementById('quick_api_base_url').addEventListener('change', (e) => {
    if (!window.userSettings) window.userSettings = getDefaultSettings();
    window.userSettings.api_base_url = e.target.value;
    window.debouncedSaveSettings();
  });

  // Actions - Boutons supprimés (sauvegarde automatique active)
  // Les paramètres sont sauvegardés via window.debouncedSaveSettings() (système unique)
}

// Fonction helper pour obtenir les settings par défaut
function getDefaultSettings() {
  return {
    data_source: "csv",
    api_base_url: "http://localhost:8000",
    display_currency: "USD",
    min_usd_threshold: 1.0,
    csv_glob: "csv/*.csv",
    cointracking_api_key: "",
    cointracking_api_secret: "",
    coingecko_api_key: "",
    fred_api_key: "",
    debug_token: "",
    pricing: "local",
    refresh_interval: 5,
    enable_coingecko_classification: true,
    enable_portfolio_snapshots: true,
    enable_performance_tracking: true,
    theme: "auto",
    debug_mode: false
  };
}

// Charger les settings depuis l'API utilisateur ET localStorage
async function loadSettings() {
  // D'abord, charger depuis localStorage (globalConfig) comme fallback immédiat
  const localSettings = window.globalConfig ? window.globalConfig.getAll() : {};

  try {
    const response = await fetch('/api/users/settings', {
      headers: { 'X-User': getActiveUser() }
    });
    if (response.ok) {
      const backendSettings = await response.json();
      // Fusionner: localStorage a priorité sur les valeurs récentes non sync
      window.userSettings = { ...getDefaultSettings(), ...backendSettings, ...localSettings };
      debugLogger.info('✓ Settings loaded from backend + localStorage');
    } else {
      debugLogger.warn('Failed to load user settings from backend, using localStorage');
      window.userSettings = { ...getDefaultSettings(), ...localSettings };
    }
  } catch (error) {
    debugLogger.error('Error loading user settings from backend:', error);
    window.userSettings = { ...getDefaultSettings(), ...localSettings };
  }

  // Synchroniser globalConfig avec les settings chargés
  if (window.globalConfig) {
    Object.keys(window.userSettings).forEach(key => {
      if (window.userSettings[key] !== undefined) {
        window.globalConfig.settings[key] = window.userSettings[key];
      }
    });
  }

  // Mettre à jour l'interface
  // IMPORTANT: buildDataSourceControls() doit être appelé AVANT updateUI()
  // pour que les radios existent quand on essaie de les cocher
  if (window.globalConfig) await initQuickSettings(); // Crée les radios
  updateUI(); // Coche les radios
  await updateStatusSummary();
}

// Sauvegarder les settings via l'API utilisateur ET localStorage
async function saveSettings() {
  // 1. Sauvegarder dans localStorage immédiatement (pour ne jamais perdre de données)
  if (window.globalConfig && window.userSettings) {
    Object.keys(window.userSettings).forEach(key => {
      if (window.userSettings[key] !== undefined) {
        window.globalConfig.settings[key] = window.userSettings[key];
      }
    });
    window.globalConfig.save(); // Force immediate save to localStorage
    debugLogger.debug('✓ Settings saved to localStorage');
  }

  // 2. Sauvegarder vers le backend (pour sync multi-device)
  try {
    const response = await fetch('/api/users/settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User': getActiveUser()
      },
      body: JSON.stringify(window.userSettings)
    });

    if (response.ok) {
      debugLogger.info('✓ Settings saved to backend');
    } else {
      const error = await response.json();
      debugLogger.error('Failed to save user settings to backend:', error);
      showNotification('⚠️ Sauvegardé localement uniquement', 'warning', 2000);
    }
  } catch (error) {
    debugLogger.error('Error saving user settings to backend:', error);
    showNotification('⚠️ Sauvegardé localement uniquement', 'warning', 2000);
  }
}

// Mettre à jour l'interface avec les valeurs actuelles
function updateUI() {
  const globalSettings = window.userSettings || getDefaultSettings();

  // Nettoyer les sélections précédentes
  document.querySelectorAll('.radio-option').forEach(el => el.classList.remove('selected'));

  // Source de données
  let srcSelected = false;
  if ((globalSettings.data_source === 'csv' || globalSettings.data_source === 'cointracking') && globalSettings.csv_selected_file) {
    const byFile = document.querySelector(`.radio-option input[name="data_source"][data-file="${globalSettings.csv_selected_file}"]`);
    if (byFile) {
      byFile.checked = true;
      const parent = byFile.closest('.radio-option');
      if (parent) {
        parent.classList.add('selected');
      } else {
        debugLogger.warn(`⚠️ updateUI: Could not find .radio-option parent for ${globalSettings.csv_selected_file}`);
      }
      srcSelected = true;
    } else {
      debugLogger.warn(`❌ updateUI: No radio found for file ${globalSettings.csv_selected_file}`);
    }
  }
  if (!srcSelected) {
    const srcInput = document.getElementById(`source_${globalSettings.data_source}`);
    if (srcInput) {
      srcInput.checked = true;
      const parent = document.querySelector(`.radio-option input[name="data_source"][value="${globalSettings.data_source}"]`);
      if (parent && parent.parentElement) parent.parentElement.classList.add('selected');
    }
  }

  // Pricing
  document.getElementById(`pricing_${globalSettings.pricing}`).checked = true;
  document.querySelector(`.radio-option input[value="${globalSettings.pricing}"]`).parentElement.classList.add('selected');

  // Thème
  document.getElementById(`theme_${globalSettings.theme}`).checked = true;
  document.querySelector(`.radio-option input[value="${globalSettings.theme}"]`).parentElement.classList.add('selected');

  // Autres champs
  document.getElementById('display_currency').value = globalSettings.display_currency;
  // Synchroniser le select rapide avec la valeur principale
  const quickCurr = document.getElementById('quick_currency');
  if (quickCurr) quickCurr.value = globalSettings.display_currency;
  document.getElementById('min_usd_threshold').value = globalSettings.min_usd_threshold;

  // Clés API masquées
  document.getElementById('coingecko_api_key').value = globalSettings.coingecko_api_key ? maskApiKey(globalSettings.coingecko_api_key) : '';
  document.getElementById('cointracking_api_key').value = globalSettings.cointracking_api_key ? maskApiKey(globalSettings.cointracking_api_key) : '';
  document.getElementById('cointracking_api_secret').value = globalSettings.cointracking_api_secret ? maskApiKey(globalSettings.cointracking_api_secret) : '';
  document.getElementById('fred_api_key').value = globalSettings.fred_api_key ? maskApiKey(globalSettings.fred_api_key) : '';
  document.getElementById('debug_token').value = globalSettings.debug_token ? maskApiKey(globalSettings.debug_token) : '';

  // Mettre à jour les statuts des clés
  updateApiKeyStatus('coingecko', !!globalSettings.coingecko_api_key);
  updateApiKeyStatus('cointracking_key', !!globalSettings.cointracking_api_key);
  updateApiKeyStatus('cointracking_secret', !!globalSettings.cointracking_api_secret);
  updateApiKeyStatus('fred', !!globalSettings.fred_api_key);

  document.getElementById('api_base_url').value = globalSettings.api_base_url;
  document.getElementById('refresh_interval').value = globalSettings.refresh_interval;
  document.getElementById('enable_coingecko_classification').checked = globalSettings.enable_coingecko_classification;
  document.getElementById('enable_portfolio_snapshots').checked = globalSettings.enable_portfolio_snapshots;
  document.getElementById('enable_performance_tracking').checked = globalSettings.enable_performance_tracking;
}

// Auto-save pour TOUS les champs de settings (tous les onglets)
document.addEventListener('DOMContentLoaded', () => {
  // === PRICING TAB ===
  const mainCurrency = document.getElementById('display_currency');
  if (mainCurrency) {
    mainCurrency.addEventListener('change', async (e) => {
      const val = e.target.value;
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.display_currency = val;
      if (window.globalConfig) window.globalConfig.set('display_currency', val);
      const quick = document.getElementById('quick_currency');
      if (quick) quick.value = val;
      try { if (window.currencyManager && val !== 'USD') await window.currencyManager.ensureRate(val); } catch (_) { }
      updateStatusSummarySync();
      window.debouncedSaveSettings();
    });
  }

  const minUsdThreshold = document.getElementById('min_usd_threshold');
  if (minUsdThreshold) {
    minUsdThreshold.addEventListener('change', (e) => {
      const val = parseFloat(e.target.value) || 0;
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.min_usd_threshold = val;
      if (window.globalConfig) window.globalConfig.set('min_usd_threshold', val);
      const quickMinUsd = document.getElementById('quick_min_usd');
      if (quickMinUsd) quickMinUsd.value = val;
      window.debouncedSaveSettings();
    });
  }

  // === INTERFACE TAB ===
  const apiBaseUrl = document.getElementById('api_base_url');
  if (apiBaseUrl) {
    apiBaseUrl.addEventListener('change', (e) => {
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.api_base_url = e.target.value;
      if (window.globalConfig) window.globalConfig.set('api_base_url', e.target.value);
      const quickApiUrl = document.getElementById('quick_api_base_url');
      if (quickApiUrl) quickApiUrl.value = e.target.value;
      window.debouncedSaveSettings();
    });
  }

  const refreshInterval = document.getElementById('refresh_interval');
  if (refreshInterval) {
    refreshInterval.addEventListener('change', (e) => {
      const val = parseInt(e.target.value) || 5;
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.refresh_interval = val;
      if (window.globalConfig) window.globalConfig.set('refresh_interval', val);
      window.debouncedSaveSettings();
    });
  }

  // Checkboxes Interface tab
  const coingeckoCheck = document.getElementById('enable_coingecko_classification');
  if (coingeckoCheck) {
    coingeckoCheck.addEventListener('change', (e) => {
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.enable_coingecko_classification = e.target.checked;
      if (window.globalConfig) window.globalConfig.set('enable_coingecko_classification', e.target.checked);
      window.debouncedSaveSettings();
    });
  }

  const snapshotsCheck = document.getElementById('enable_portfolio_snapshots');
  if (snapshotsCheck) {
    snapshotsCheck.addEventListener('change', (e) => {
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.enable_portfolio_snapshots = e.target.checked;
      if (window.globalConfig) window.globalConfig.set('enable_portfolio_snapshots', e.target.checked);
      window.debouncedSaveSettings();
    });
  }

  const perfCheck = document.getElementById('enable_performance_tracking');
  if (perfCheck) {
    perfCheck.addEventListener('change', (e) => {
      if (!window.userSettings) window.userSettings = getDefaultSettings();
      window.userSettings.enable_performance_tracking = e.target.checked;
      if (window.globalConfig) window.globalConfig.set('enable_performance_tracking', e.target.checked);
      window.debouncedSaveSettings();
    });
  }
});

// Mettre à jour le résumé du statut
async function updateStatusSummary() {
  const summary = document.getElementById('status-summary');
  const globalSettings = window.userSettings || getDefaultSettings();

  // Récupérer le label de source depuis l'API utilisateur
  let sourceLabel = 'Aucune source';
  try {
    const response = await fetch('/api/users/sources', {
      headers: { 'X-User': getActiveUser() }
    });
    if (response.ok) {
      const data = await response.json();
      let currentSource = data.sources.find(s => s.key === globalSettings.data_source);
      // Si CSV générique, essayer de trouver l'entrée par nom de fichier sélectionné
      if ((!currentSource) && (globalSettings.data_source === 'csv' || globalSettings.data_source === 'cointracking') && globalSettings.csv_selected_file) {
        currentSource = data.sources.find(s => s.type === 'csv' && (s.file_path || '').split(/[/\\]/).pop() === globalSettings.csv_selected_file);
      }
      if (currentSource) {
        sourceLabel = currentSource.label;
      } else if (data.sources.length === 0) {
        sourceLabel = 'Aucune source';
      } else {
        sourceLabel = globalSettings.data_source;
      }
    }
  } catch (error) {
    console.debug('Could not load source labels:', error);
  }

  const pricingLabels = {
    'local': '🏠 Prix locaux',
    'auto': '🚀 Prix automatiques'
  };

  const themeLabels = {
    'auto': '🌓 Auto',
    'light': '☀️ Clair',
    'dark': '🌙 Sombre'
  };

  summary.innerHTML = `
  <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px;">
    <span class="status-indicator status-ok">
      ${sourceLabel}
  </span>
    <span class="status-indicator status-ok">
      ${pricingLabels[globalSettings.pricing]}
    </span>
    <span class="status-indicator status-ok">
      ${themeLabels[globalSettings.theme]}
    </span>
    <span class="status-indicator status-ok">
      ${globalSettings.display_currency}
    </span>
  </div>
  `;
}

// Version synchrone rapide sans requête API (pour quick updates)
function updateStatusSummarySync() {
  const summary = document.getElementById('status-summary');
  if (!summary) return;

  const globalSettings = window.userSettings || getDefaultSettings();

  const pricingLabels = {
    'local': '🏠 Prix locaux',
    'auto': '🚀 Prix automatiques'
  };

  const themeLabels = {
    'auto': '🌓 Auto',
    'light': '☀️ Clair',
    'dark': '🌙 Sombre'
  };

  // Use current data source label without API call
  const sourceLabel = globalSettings.data_source || 'Non configurée';

  summary.innerHTML = `
  <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px;">
    <span class="status-indicator status-ok">
      ${sourceLabel}
    </span>
    <span class="status-indicator status-ok">
      ${pricingLabels[globalSettings.pricing] || globalSettings.pricing}
    </span>
    <span class="status-indicator status-ok">
      ${themeLabels[globalSettings.theme] || globalSettings.theme}
    </span>
    <span class="status-indicator status-ok">
      ${globalSettings.display_currency}
    </span>
  </div>
  `;
}

// Sélection de source de données
async function selectDataSource(source) {
  // Ne retirer la sélection que pour le groupe des sources
  document.querySelectorAll('input[name="data_source"]').forEach(inp => {
    if (inp && inp.parentElement) inp.parentElement.classList.remove('selected');
  });
  if (!window.userSettings) window.userSettings = getDefaultSettings();

  // ⚠️ CRITIQUE: Préserver les clés API avant modification
  // Recharger depuis le serveur pour éviter la perte des clés API
  try {
    const response = await fetch('/api/users/settings', {
      headers: { 'X-User': getActiveUser() }
    });
    if (response.ok) {
      const currentSettings = await response.json();
      // Fusionner TOUTES les clés API depuis le serveur (plus sûr)
      const apiKeys = ['coingecko_api_key', 'cointracking_api_key', 'cointracking_api_secret', 'fred_api_key', 'debug_token'];
      apiKeys.forEach(key => {
        if (currentSettings[key]) {
          window.userSettings[key] = currentSettings[key];
        }
      });
    }
  } catch (e) {
    debugLogger.warn('Could not reload settings to preserve API keys:', e);
  }

  // Vider tous les caches quand la source change
  const oldSource = window.userSettings.data_source;
  const oldFile = window.userSettings.csv_selected_file;
  const isCsvKey = typeof source === 'string' && source.startsWith('csv_');
  const effectiveNew = isCsvKey ? 'cointracking' : source;

  // Déterminer le nouveau fichier si CSV
  let newFile = null;
  if (isCsvKey) {
    const src = (window.availableSources || []).find(s => s.key === source);
    if (src && src.file_path) {
      newFile = src.file_path.split(/[/\\]/).pop();
    } else {
      debugLogger.warn(`❌ No source found for key: ${source} OR no file_path`);
    }
  }

  // Vider caches si changement réel de source OU de fichier CSV
  const sourceChanged = oldSource && oldSource !== effectiveNew;
  const fileChanged = effectiveNew === 'cointracking' && oldFile !== newFile;

  if (sourceChanged || fileChanged) {

    // Vider le cache balance
    if (typeof window.clearBalanceCache === 'function') {
      window.clearBalanceCache();
    }

    // Vider localStorage cache
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('cache:') || key.includes('risk_score') || key.includes('balance_')) {
        localStorage.removeItem(key);
      }
    });

    // Mettre à jour global config aussi
    if (typeof window.globalConfig !== 'undefined') {
      window.globalConfig.set('data_source', effectiveNew);
    }
  }

  // Mettre à jour la valeur stockée
  if (isCsvKey) {
    window.userSettings.data_source = 'cointracking';
    window.userSettings.csv_selected_file = newFile;
  } else {
    window.userSettings.data_source = source;
    window.userSettings.csv_selected_file = null; // Réinitialiser si on passe à API
  }

  // Synchroniser le select rapide (Résumé)
  const quickSelect = document.getElementById('quick_data_source');
  if (quickSelect) {
    if (isCsvKey) {
      quickSelect.value = source;
    } else if ((window.userSettings.data_source === 'cointracking' || window.userSettings.data_source === 'csv') && window.userSettings.csv_selected_file) {
      try {
        const list = window.availableSources || [];
        const match = list.find(s => s.type === 'csv' && (s.file_path || '').split(/[/\\]/).pop() === window.userSettings.csv_selected_file);
        if (match) quickSelect.value = match.key; else quickSelect.value = window.userSettings.data_source;
      } catch (_) { quickSelect.value = window.userSettings.data_source; }
    } else {
      quickSelect.value = window.userSettings.data_source;
    }
  }

  // Cocher la radio correspondante (onglet Source)
  let radioMarked = false;
  if ((window.userSettings.data_source === 'cointracking' || window.userSettings.data_source === 'csv') && window.userSettings.csv_selected_file) {
    const byFile = document.querySelector(`.radio-option input[name="data_source"][data-file="${window.userSettings.csv_selected_file}"]`);
    if (byFile) {
      byFile.checked = true;
      if (byFile.parentElement) byFile.parentElement.classList.add('selected');
      radioMarked = true;
    }
  }
  if (!radioMarked) {
    const radio = document.getElementById(`source_${source}`);
    if (radio) {
      radio.checked = true;
      const parent = document.querySelector(`.radio-option input[name=\"data_source\"][value=\"${source}\"]`);
      if (parent && parent.parentElement) parent.parentElement.classList.add('selected');
    }
  }
  await updateStatusSummary();

  // Persister la sélection si changement réel (source OU fichier CSV)
  if (sourceChanged || fileChanged) {
    try { await saveSettings(); } catch (_) { }
  }

  // 🔧 FIX: Force radio selection update AFTER all async operations
  // Use requestAnimationFrame to ensure DOM has fully rendered
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      // Ensure the correct radio is visually selected
      const allRadios = document.querySelectorAll('.radio-option input[name="data_source"]');
      allRadios.forEach(inp => {
        if (inp.parentElement) inp.parentElement.classList.remove('selected');
      });

      if ((window.userSettings.data_source === 'cointracking' || window.userSettings.data_source === 'csv') && window.userSettings.csv_selected_file) {
        const byFile = document.querySelector(`.radio-option input[name="data_source"][data-file="${window.userSettings.csv_selected_file}"]`);
        if (byFile) {
          byFile.checked = true;
          if (byFile.parentElement) {
            byFile.parentElement.classList.add('selected');
          }
        }
      }
    });
  });
}

// Sélection de pricing
async function selectPricing(pricing) {
  document.querySelectorAll('.radio-option').forEach(el => el.classList.remove('selected'));
  if (!window.userSettings) window.userSettings = getDefaultSettings();
  window.userSettings.pricing = pricing;
  if (window.globalConfig) window.globalConfig.set('pricing', pricing);
  document.getElementById(`pricing_${pricing}`).checked = true;
  document.querySelector(`.radio-option input[value="${pricing}"]`).parentElement.classList.add('selected');
  // Auto-save backend
  if (window.debouncedSaveSettings) window.debouncedSaveSettings();
}

// Sélection de thème (optimized - no blocking API calls)
async function selectTheme(theme) {
  console.debug('Setting theme to:', theme);
  document.querySelectorAll('.radio-option').forEach(el => el.classList.remove('selected'));

  if (!window.userSettings) window.userSettings = getDefaultSettings();
  window.userSettings.theme = theme;
  if (window.globalConfig) window.globalConfig.set('theme', theme);
  // Appliquer le thème directement
  document.documentElement.setAttribute('data-theme', theme);

  // Mettre à jour l'interface
  document.getElementById(`theme_${theme}`).checked = true;
  document.querySelector(`.radio-option input[value="${theme}"]`).parentElement.classList.add('selected');

  // Appliquer immédiatement le thème
  if (window.applyAppearance) {
    window.applyAppearance();
  }

  // Auto-save backend
  if (window.debouncedSaveSettings) window.debouncedSaveSettings();

  console.debug('Theme applied, current userSettings theme:', (window.userSettings || getDefaultSettings()).theme);
}

// Sauvegarder tous les settings
async function saveAllSettings() {
  // Récupérer toutes les valeurs des champs et les stocker dans userSettings
  if (!window.userSettings) window.userSettings = getDefaultSettings();

  window.userSettings.display_currency = document.getElementById('display_currency').value;
  if (window.globalConfig) window.globalConfig.set('display_currency', window.userSettings.display_currency);
  window.userSettings.min_usd_threshold = parseFloat(document.getElementById('min_usd_threshold').value);
  // Synchroniser le champ rapide
  const quickMinUsd = document.getElementById('quick_min_usd');
  if (quickMinUsd) quickMinUsd.value = window.userSettings.min_usd_threshold;
  if (window.globalConfig) window.globalConfig.set('min_usd_threshold', window.userSettings.min_usd_threshold);

  // Clés API: sauvegarder si champ visible OU si valeur différente du masque actuel
  function saveSecretIfProvided(fieldId, settingKey) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    const current = (window.userSettings || getDefaultSettings())[settingKey] || '';
    const masked = current ? maskApiKey(current) : '';
    const incoming = (field.value || '').trim();

    // Si le champ est vide, effacer la clé (userSettings + globalConfig)
    if (!incoming) {
      window.userSettings[settingKey] = '';
      if (window.globalConfig) {
        window.globalConfig.set(settingKey, '');
      }
      return;
    }

    // Si le champ est visible (type=text) ou si la valeur est différente du masque
    if (field.type === 'text' || incoming !== masked) {
      window.userSettings[settingKey] = incoming;
      if (window.globalConfig) {
        window.globalConfig.set(settingKey, incoming);
      }
    }
  }

  saveSecretIfProvided('coingecko_api_key', 'coingecko_api_key');
  saveSecretIfProvided('cointracking_api_key', 'cointracking_api_key');
  saveSecretIfProvided('cointracking_api_secret', 'cointracking_api_secret');
  saveSecretIfProvided('fred_api_key', 'fred_api_key');
  saveSecretIfProvided('debug_token', 'debug_token');

  window.userSettings.api_base_url = document.getElementById('api_base_url').value;
  if (window.globalConfig) window.globalConfig.set('api_base_url', window.userSettings.api_base_url);
  window.userSettings.refresh_interval = parseInt(document.getElementById('refresh_interval').value);
  if (window.globalConfig) window.globalConfig.set('refresh_interval', window.userSettings.refresh_interval);

  window.userSettings.enable_coingecko_classification = document.getElementById('enable_coingecko_classification').checked;
  if (window.globalConfig) window.globalConfig.set('enable_coingecko_classification', window.userSettings.enable_coingecko_classification);
  window.userSettings.enable_portfolio_snapshots = document.getElementById('enable_portfolio_snapshots').checked;
  if (window.globalConfig) window.globalConfig.set('enable_portfolio_snapshots', window.userSettings.enable_portfolio_snapshots);
  window.userSettings.enable_performance_tracking = document.getElementById('enable_performance_tracking').checked;
  if (window.globalConfig) window.globalConfig.set('enable_performance_tracking', window.userSettings.enable_performance_tracking);

  // Mettre à jour les statuts
  updateApiKeyStatus('coingecko', !!window.userSettings.coingecko_api_key);
  updateApiKeyStatus('cointracking_key', !!window.userSettings.cointracking_api_key);
  updateApiKeyStatus('cointracking_secret', !!window.userSettings.cointracking_api_secret);
  updateApiKeyStatus('fred', !!window.userSettings.fred_api_key);

  await saveSettings();

  // Notification
  showNotification('⚙️ Configuration sauvegardée !', 'success');
}

// Test de la source de données
async function testDataSource() {
  const testDiv = document.getElementById('data-source-test');
  testDiv.innerHTML = '<div class="test-result">🧪 Test en cours...</div>';

  try {
    const balanceResult = await window.loadBalanceData(true);
    const data = balanceResult.csvText
      ? { items: parseCSVBalancesAuto(balanceResult.csvText), source_used: 'CSV' }
      : (balanceResult.data || { items: [] });

    if (data.items && data.items.length > 0) {
      testDiv.innerHTML = `
    <div class="test-result" style="color: var(--pos);">
      ✅ <strong>Succès</strong><br>
      Source: ${data.source_used}<br>
      Assets trouvés: ${data.items.length}<br>
      Premier asset: ${data.items[0].symbol} (${data.items[0].value_usd || 0} USD)
    </div>
  `;
    } else {
      testDiv.innerHTML = `
    <div class="test-result" style="color: var(--warning);">
      ⚠️ <strong>Aucune donnée</strong><br>
      La source répond mais ne retourne pas d'assets
    </div>
  `;
    }
  } catch (error) {
    testDiv.innerHTML = `
  <div class="test-result" style="color: var(--danger);">
    ❌ <strong>Erreur</strong><br>
    ${error.message}
  </div>
`;
  }
}

// Auto-détecter le DEBUG_TOKEN depuis l'environnement
async function autoDetectDebugToken() {
  // Vérifier le rate limiting
  const lastAttempt = localStorage.getItem('debug_token_detection_last');
  const now = Date.now();
  if (lastAttempt && (now - parseInt(lastAttempt)) < 60000) { // 1 minute
    console.debug('🔍 DEBUG_TOKEN auto-détection rate-limitée, skip');
    return;
  }
  localStorage.setItem('debug_token_detection_last', now.toString());

  // Pour l'instant, essayer une liste de tokens courants pour le dev
  const commonTokens = [
    'crypto-rebal-debug-2025-secure',
    'dev-token-2025',
    'debug-crypto-rebal'
  ];

  for (let i = 0; i < commonTokens.length; i++) {
    const token = commonTokens[i];
    try {
      const response = await fetch(`${(window.userSettings || getDefaultSettings()).api_base_url}/debug/api-keys?debug_token=${token}`, {
        headers: { 'X-User': getActiveUser() }
      });
      if (response.ok) {
        if (!window.userSettings) window.userSettings = getDefaultSettings();
        window.userSettings.debug_token = token;
        document.getElementById('debug_token').value = maskApiKey(token);
        console.debug('DEBUG_TOKEN auto-détecté et configuré');
        showNotification('🔑 DEBUG_TOKEN auto-détecté', 'success');
        return;
      }
      // Rate limit les tentatives
      if (response.status === 429) {
        console.debug(`🚦 Rate limite atteinte, attendre avant prochaine tentative`);
        await new Promise(resolve => setTimeout(resolve, 2000)); // 2 secondes
      }
    } catch (e) {
      // Continuer avec le token suivant
      console.debug(`Token ${token} échoué:`, e.message);
    }

    // Délai entre les tentatives pour éviter rate limiting
    if (i < commonTokens.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 1000)); // 1 seconde entre tentatives
    }
  }

  console.debug('DEBUG_TOKEN non trouvé automatiquement, saisie manuelle requise');
}

// Auto-détecter les clés depuis .env du serveur
async function autoDetectApiKeys() {
  try {
    const globalSettings = window.userSettings || getDefaultSettings();
    // Essayer de récupérer les clés depuis le backend
    const debugToken = (window.userSettings || getDefaultSettings()).debug_token;
    if (!debugToken) {
      console.debug('Auto-détection désactivée: DEBUG_TOKEN requis');
      return;
    }
    const response = await fetch(`${globalSettings.api_base_url}/debug/api-keys?debug_token=${debugToken}`, {
      headers: { 'X-User': getActiveUser() }
    });
    if (response.ok) {
      const data = await response.json();
      let foundKeys = false;

      // CoinGecko - ne pas sauvegarder les clés masquées du serveur
      if (data.coingecko_api_key && data.coingecko_api_key.endsWith('...')) {
        // Clé masquée du serveur - ne pas l'assigner aux settings utilisateur
        console.debug('CoinGecko API key found on server (masked)');
      } else if (data.coingecko_api_key && !globalSettings.coingecko_api_key) {
        if (!window.userSettings) window.userSettings = getDefaultSettings();
        window.userSettings.coingecko_api_key = data.coingecko_api_key;
        foundKeys = true;
      }
      if ((window.userSettings || getDefaultSettings()).coingecko_api_key) {
        document.getElementById('coingecko_api_key').value = maskApiKey((window.userSettings || getDefaultSettings()).coingecko_api_key);
        updateApiKeyStatus('coingecko', true);
      }

      // FRED - ne pas sauvegarder les clés masquées du serveur
      if (data.fred_api_key && data.fred_api_key.endsWith('...')) {
        // Clé masquée du serveur - ne pas l'assigner aux settings utilisateur
        console.debug('FRED API key found on server (masked)');
      } else if (data.fred_api_key && !globalSettings.fred_api_key) {
        if (!window.userSettings) window.userSettings = getDefaultSettings();
        window.userSettings.fred_api_key = data.fred_api_key;
        foundKeys = true;
      }
      if ((window.userSettings || getDefaultSettings()).fred_api_key) {
        document.getElementById('fred_api_key').value = maskApiKey((window.userSettings || getDefaultSettings()).fred_api_key);
        updateApiKeyStatus('fred', true);
      }

      // CoinTracking Key - ne pas sauvegarder les clés masquées du serveur
      if (data.cointracking_api_key && data.cointracking_api_key.endsWith('...')) {
        // Clé masquée du serveur - ne pas l'assigner aux settings utilisateur
        console.debug('CoinTracking API key found on server (masked)');
      } else if (data.cointracking_api_key && !globalSettings.cointracking_api_key) {
        if (!window.userSettings) window.userSettings = getDefaultSettings();
        window.userSettings.cointracking_api_key = data.cointracking_api_key;
        foundKeys = true;
      }
      if ((window.userSettings || getDefaultSettings()).cointracking_api_key) {
        document.getElementById('cointracking_api_key').value = maskApiKey((window.userSettings || getDefaultSettings()).cointracking_api_key);
        updateApiKeyStatus('cointracking_key', true);
      }

      // CoinTracking Secret - ne pas sauvegarder les clés masquées du serveur
      if (data.cointracking_api_secret && data.cointracking_api_secret === '***masked***') {
        // Clé masquée du serveur - ne pas l'assigner aux settings utilisateur
        console.debug('CoinTracking API secret found on server (masked)');
      } else if (data.cointracking_api_secret && !globalSettings.cointracking_api_secret) {
        if (!window.userSettings) window.userSettings = getDefaultSettings();
        window.userSettings.cointracking_api_secret = data.cointracking_api_secret;
        foundKeys = true;
      }
      if ((window.userSettings || getDefaultSettings()).cointracking_api_secret) {
        document.getElementById('cointracking_api_secret').value = maskApiKey((window.userSettings || getDefaultSettings()).cointracking_api_secret);
        updateApiKeyStatus('cointracking_secret', true);
      }

      if (foundKeys) {
        saveSettings(); // Sauvegarder les nouvelles clés
        showNotification('🔑 Clés API détectées depuis .env', 'success');
      }
    }
  } catch (e) {
    console.debug('Auto-détection des clés non disponible:', e.message);
  }
}

// Masquer une clé API pour l'affichage
function maskApiKey(key) {
  if (!key || key.length < 8) return key;
  return key.substring(0, 4) + '•'.repeat(key.length - 8) + key.substring(key.length - 4);
}

// Mettre à jour le statut d'une clé API
function updateApiKeyStatus(keyType, hasKey) {
  const statusEl = document.getElementById(`${keyType}_status`);
  if (statusEl) {
    if (hasKey) {
      statusEl.textContent = 'Configurée';
      statusEl.className = 'status-indicator status-ok';
    } else {
      statusEl.textContent = 'Vide';
      statusEl.className = 'status-indicator status-warning';
    }
  }
}

// Basculer la visibilité d'une clé API
function toggleApiKeyVisibility(fieldId) {
  const field = document.getElementById(fieldId);
  const isPassword = field.type === 'password';

  if (isPassword) {
    // Afficher la vraie clé
    const settingKey = fieldId; // même nom que dans globalConfig
    field.type = 'text';
    field.value = (window.userSettings || getDefaultSettings())[settingKey] || '';
  } else {
    // Masquer avec des points
    field.type = 'password';
    const settingKey = fieldId;
    const value = (window.userSettings || getDefaultSettings())[settingKey];
    field.value = value ? maskApiKey(value) : '';
  }
}

// Synchroniser depuis .env
async function syncApiKeysFromEnv() {
  try {
    const debugToken = (window.userSettings || getDefaultSettings()).debug_token;
    if (!debugToken) {
      showNotification('❌ DEBUG_TOKEN requis pour synchroniser depuis .env', 'error');
      return;
    }
    const response = await fetch(`${(window.userSettings || getDefaultSettings()).api_base_url}/debug/api-keys?debug_token=${debugToken}`);
    if (response.ok) {
      const data = await response.json();
      let foundKeys = false;

      // Forcer le rechargement de toutes les clés depuis .env (ne pas sauver les masquées)
      if (data.coingecko_api_key) {
        if (!data.coingecko_api_key.endsWith('...')) {
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.coingecko_api_key = data.coingecko_api_key;
        }
        document.getElementById('coingecko_api_key').value = maskApiKey(data.coingecko_api_key);
        updateApiKeyStatus('coingecko', true);
        foundKeys = true;
      } else {
        updateApiKeyStatus('coingecko', false);
      }

      if (data.fred_api_key) {
        if (!data.fred_api_key.endsWith('...')) {
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.fred_api_key = data.fred_api_key;
        }
        document.getElementById('fred_api_key').value = maskApiKey(data.fred_api_key);
        updateApiKeyStatus('fred', true);
        foundKeys = true;
      } else {
        updateApiKeyStatus('fred', false);
      }

      if (data.cointracking_api_key) {
        if (!data.cointracking_api_key.endsWith('...')) {
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.cointracking_api_key = data.cointracking_api_key;
        }
        document.getElementById('cointracking_api_key').value = maskApiKey(data.cointracking_api_key);
        updateApiKeyStatus('cointracking_key', true);
        foundKeys = true;
      } else {
        updateApiKeyStatus('cointracking_key', false);
      }

      if (data.cointracking_api_secret) {
        if (data.cointracking_api_secret !== '***masked***') {
          if (!window.userSettings) window.userSettings = getDefaultSettings();
          window.userSettings.cointracking_api_secret = data.cointracking_api_secret;
        }
        document.getElementById('cointracking_api_secret').value = maskApiKey(data.cointracking_api_secret);
        updateApiKeyStatus('cointracking_secret', true);
        foundKeys = true;
      } else {
        updateApiKeyStatus('cointracking_secret', false);
      }

      if (foundKeys) {
        saveSettings();
        showNotification('📥 Clés rechargées depuis .env', 'success');
      } else {
        showNotification('⚠️ Aucune clé trouvée dans .env', 'warning');
      }
    } else {
      showNotification('❌ Erreur lecture .env', 'error');
    }
  } catch (e) {
    showNotification(`❌ Erreur: ${e.message}`, 'error');
  }
}

// Synchroniser vers .env
async function syncApiKeysToEnv() {
  const payload = {
    coingecko_api_key: (window.userSettings || getDefaultSettings()).coingecko_api_key || '',
    cointracking_api_key: (window.userSettings || getDefaultSettings()).cointracking_api_key || '',
    cointracking_api_secret: (window.userSettings || getDefaultSettings()).cointracking_api_secret || '',
    fred_api_key: (window.userSettings || getDefaultSettings()).fred_api_key || ''
  };

  try {
    const debugToken = (window.userSettings || getDefaultSettings()).debug_token;
    if (!debugToken) {
      showNotification('❌ DEBUG_TOKEN requis pour sauvegarder vers .env', 'error');
      return;
    }
    const response = await fetch(`${(window.userSettings || getDefaultSettings()).api_base_url}/debug/api-keys?debug_token=${debugToken}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User': getActiveUser() },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      const result = await response.json();
      if (result.updated) {
        showNotification('💾 Clés sauvées vers .env', 'success');
      } else {
        showNotification('⚪ Aucune clé à sauvegarder', 'info');
      }
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (e) {
    showNotification(`❌ Erreur sauvegarde: ${e.message}`, 'error');
  }
}

// Test des clés API
async function testApiKeys() {
  const testDiv = document.getElementById('api-keys-test');
  testDiv.innerHTML = '<div class="test-result">🧪 Test des APIs...</div>';

  let results = [];
  const globalSettings = window.userSettings || getDefaultSettings();

  // Test CoinGecko
  if (globalSettings.coingecko_api_key) {
    try {
      const response = await fetch(`${globalSettings.api_base_url}/taxonomy/test-coingecko-api?api_key=${encodeURIComponent(globalSettings.coingecko_api_key)}`, {
        headers: { 'X-User': getActiveUser() }
      });
      const data = await response.json();
      results.push(`🥷 CoinGecko: ${data.ok ? '✅ OK' : '❌ Erreur'}`);
      if (!data.ok && data.message) {
        results.push(`   └─ ${data.message}`);
      }
    } catch (e) {
      results.push(`🥷 CoinGecko: ❌ ${e.message}`);
    }
  } else {
    results.push(`🥷 CoinGecko: ⚪ Pas de clé configurée`);
  }

  // Test FRED via backend proxy
  if (globalSettings.fred_api_key) {
    try {
      const response = await fetch(`${globalSettings.api_base_url}/proxy/fred/bitcoin?limit=1`, {
        headers: { 'X-User': getActiveUser() }
      });
      const data = await response.json();
      results.push(`🏛️ FRED: ${response.ok && data.success ? '✅ OK' : '❌ Erreur'}`);
      if (!response.ok && data.detail) {
        results.push(`   └─ ${data.detail}`);
      } else if (!data.success && data.error) {
        results.push(`   └─ ${data.error}`);
      }
    } catch (e) {
      results.push(`🏛️ FRED: ❌ ${e.message}`);
    }
  } else {
    results.push(`🏛️ FRED: ⚪ Pas de clé configurée`);
  }

  // Test CoinTracking API
  if (globalSettings.cointracking_api_key && globalSettings.cointracking_api_secret) {
    try {
      const originalSource = globalConfig.get('data_source');
      globalConfig.set('data_source', 'cointracking_api');
      const result = await window.loadBalanceData(true);
      globalConfig.set('data_source', originalSource);
      results.push(`📊 CoinTracking API: ${result.success && result.data?.items ? '✅ OK' : '❌ Erreur'}`);
    } catch (e) {
      results.push(`📊 CoinTracking API: ❌ ${e.message}`);
    }
  } else {
    results.push(`📊 CoinTracking API: ⚪ Clés manquantes`);
  }

  // Test Backend disponibilité
  try {
    const response = await fetch(`${globalSettings.api_base_url}/health`, {
      headers: { 'X-User': getActiveUser() }
    });
    results.push(`🏥 Backend: ${response.ok ? '✅ OK' : '❌ Indisponible'}`);
  } catch (e) {
    results.push(`🏥 Backend: ❌ ${e.message}`);
  }

  testDiv.innerHTML = `
  <div class="test-result">
    <strong>Résultats des tests:</strong><br>
      ${results.join('<br>')}
  </div>
  `;
}

// Test complet du système
async function runFullSystemTest() {
  const testDiv = document.getElementById('full-system-test');
  testDiv.innerHTML = '<div class="test-result">🚀 Test complet en cours...</div>';

  let results = [];
  const globalSettings = window.userSettings || getDefaultSettings();

  // Test backend
  try {
    const healthResponse = await fetch(`${globalSettings.api_base_url}/healthz`, { headers: { 'X-User': getActiveUser() } });
    results.push(`🏥 Backend: ${healthResponse.ok ? '✅ OK' : '❌ Erreur'}`);
  } catch (e) {
    results.push(`🏥 Backend: ❌ ${e.message}`);
  }

  // Test source de données
  try {
    const balanceResult = await window.loadBalanceData(true);
    const balanceData = balanceResult.csvText
      ? { items: parseCSVBalancesAuto(balanceResult.csvText) }
      : (balanceResult.data || { items: [] });
    results.push(`📊 Balances: ${balanceData.items?.length > 0 ? '✅ OK (' + balanceData.items.length + ' assets)' : '❌ Vide'}`);
  } catch (e) {
    results.push(`📊 Balances: ❌ ${e.message}`);
  }

  // Test portfolio analytics
  try {
    const metricsData = await globalConfig.apiRequest('/portfolio/metrics', {
      params: { source: globalSettings.data_source }
    });
    // Accept ok:true even with zero balances (endpoint is working)
    results.push(`📈 Analytics: ${metricsData.ok ? '✅ OK' : '❌ Erreur'}`);
    if (!metricsData.ok && metricsData.error) {
      results.push(`   └─ ${metricsData.error}`);
    }
  } catch (e) {
    results.push(`📈 Analytics: ❌ ${e.message}`);
  }

  // Test taxonomie
  try {
    const taxData = await globalConfig.apiRequest('/taxonomy/suggestions');
    results.push(`🏷️ Taxonomie: ${taxData ? '✅ OK' : '❌ Erreur'}`);
  } catch (e) {
    results.push(`🏷️ Taxonomie: ❌ ${e.message}`);
  }

  testDiv.innerHTML = `
  <div class="test-result">
    <strong>🧪 Résultats du test complet:</strong><br>
      ${results.join('<br>')}
      <br><br>
        <strong>Configuration testée:</strong><br>
          Source: ${globalSettings.data_source}<br>
            Pricing: ${globalSettings.pricing}<br>
              API: ${globalSettings.api_base_url}
            </div>
            `;
}

// Utilitaires
function resetToDefaults() {
  if (confirm('Restaurer la configuration par défaut ?')) {
    globalConfig.reset();
    location.reload();
  }
}

function exportSettings() {
  globalConfig.export();
}

async function importSettings() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      try {
        await globalConfig.importFromFile(file);
        location.reload();
      } catch (err) {
        alert('Erreur import: ' + err.message);
      }
    }
  };
  input.click();
}

function clearCache() {
  if (confirm('Vider tout le cache local ?')) {
    localStorage.removeItem('lastPortfolioSnapshot');
    showNotification('🗑️ Cache vidé !', 'success');
  }
}

function resetAllData() {
  if (confirm('⚠️ ATTENTION: Supprimer TOUTES les données et configurations ?')) {
    localStorage.clear();
    showNotification('⚠️ Toutes les données supprimées !', 'warning');
    setTimeout(() => location.reload(), 1000);
  }
}

function showNotification(message, type = 'info', duration = 2000) {
  // Remove existing notification if any
  const existing = document.querySelector('.settings-notification');
  if (existing) existing.remove();

  const notification = document.createElement('div');
  notification.className = 'settings-notification';
  notification.textContent = message;
  notification.style.cssText = `
            position: fixed; bottom: 20px; right: 20px; z-index: 1000;
            padding: 8px 12px; border-radius: 6px; font-size: 13px;
            color: white; font-weight: 500;
            background: ${type === 'success' ? 'var(--pos)' : type === 'warning' ? 'var(--warning)' : type === 'error' ? 'var(--danger)' : 'var(--accent)'};
            opacity: 0; transition: opacity 0.2s ease;
            `;
  document.body.appendChild(notification);

  // Fade in
  requestAnimationFrame(() => {
    notification.style.opacity = '1';
  });

  // Fade out and remove
  setTimeout(() => {
    notification.style.opacity = '0';
    setTimeout(() => notification.remove(), 200);
  }, duration);
}

// Appliquer le thème dès que possible
function applyThemeImmediately() {
  console.debug('Applying theme immediately for settings page...');
  if (window.globalConfig && window.globalConfig.applyTheme) {
    window.globalConfig.applyTheme();
  }
  if (window.applyAppearance) {
    window.applyAppearance();
  }
  console.debug('Theme applied, current theme:', document.documentElement.getAttribute('data-theme'));
}

// Ajouter le header partagé et initialiser
document.addEventListener('DOMContentLoaded', () => {
  // Appliquer le thème immédiatement
  applyThemeImmediately();

  loadSettings().then(() => {
    // Tenter de récupérer le DEBUG_TOKEN depuis le serveur
    autoDetectDebugToken();
  });
  // Auto-détection des clés désactivée pour respecter le choix utilisateur
  // Utilisez le bouton "Sync depuis .env" manuellement si besoin
  // autoDetectApiKeys();

  // Écouter les changements de thème système pour mettre à jour l'interface
  window.addEventListener('themeChanged', (event) => {
    console.debug('🎨 Thème changé:', event.detail);
    // L'interface n'a pas besoin d'être mise à jour car elle suit déjà globalConfig
  });

  // 🔧 FIX GLOBAL: Event delegation pour capturer TOUS les clics sur les radios data_source
  // Ceci fonctionne même si les radios sont créés dynamiquement
  document.addEventListener('click', async (e) => {
    const target = e.target;

    // Vérifier si on a cliqué sur un label ou input radio de data_source
    let radio = null;
    if (target.tagName === 'INPUT' && target.type === 'radio' && target.name === 'data_source') {
      radio = target;
    } else if (target.tagName === 'LABEL') {
      const forAttr = target.getAttribute('for');
      if (forAttr && forAttr.startsWith('source_')) {
        radio = document.getElementById(forAttr);
      }
    }

    if (radio && radio.name === 'data_source') {
      // Attendre un tick pour que le radio soit coché
      await new Promise(resolve => setTimeout(resolve, 10));

      if (radio.checked) {
        await selectDataSource(radio.value);
      }
    }
  }, true); // useCapture=true pour capturer avant les autres handlers
});

// ===== FONCTIONS TÉLÉCHARGEMENT CSV =====

async function downloadCSVFiles() {
  const downloadBtn = document.getElementById('download-btn-text');
  const statusDiv = document.getElementById('csv-download-status');

  // Vérifier les clés API
  const userSettings = window.userSettings || getDefaultSettings();
  const apiKey = userSettings.cointracking_api_key;
  const apiSecret = userSettings.cointracking_api_secret;

  if (!apiKey || !apiSecret) {
    statusDiv.innerHTML = '<div class="error">❌ Clés API CoinTracking requises pour le téléchargement automatique.</div>';
    return;
  }

  downloadBtn.textContent = '⏳ Téléchargement...';
  statusDiv.innerHTML = '<div class="info">🔄 Téléchargement en cours...</div>';

  try {
    const selectedFiles = getSelectedFiles();
    const downloadPath = document.getElementById('csv_download_path').value || 'data/raw/';

    const results = [];

    for (const fileType of selectedFiles) {
      try {
        const result = await downloadSingleCSV(fileType, downloadPath);
        results.push(result);
      } catch (error) {
        results.push({
          type: fileType,
          success: false,
          error: error.message
        });
      }
    }

    displayDownloadResults(results);

  } catch (error) {
    statusDiv.innerHTML = `<div class="error">❌ Erreur téléchargement: ${error.message}</div>`;
  } finally {
    downloadBtn.textContent = '📥 Télécharger Maintenant';
  }
}

function getSelectedFiles() {
  const files = [];
  if (document.getElementById('download_current_balance').checked) {
    files.push('current_balance');
  }
  if (document.getElementById('download_balance_by_exchange').checked) {
    files.push('balance_by_exchange');
  }
  if (document.getElementById('download_coins_by_exchange').checked) {
    files.push('coins_by_exchange');
  }
  return files;
}

async function downloadSingleCSV(fileType, downloadPath) {
  // Appeler l'API backend pour télécharger le CSV
  const response = await globalConfig.apiRequest('/csv/download', {
    method: 'POST',
    body: JSON.stringify({
      file_type: fileType,
      download_path: downloadPath,
      auto_name: true  // Utilise automatiquement le nom avec date
    })
  });

  if (response.success) {
    return {
      type: fileType,
      success: true,
      filename: response.filename,
      path: response.path,
      size: response.size
    };
  } else {
    throw new Error(response.error || 'Téléchargement échoué');
  }
}

function displayDownloadResults(results) {
  const statusDiv = document.getElementById('csv-download-status');
  let html = '<div style="margin-top: 16px;"><h4>Résultats du téléchargement:</h4><ul>';

  results.forEach(result => {
    const icon = result.success ? '✅' : '❌';
    const fileLabel = getFileLabel(result.type);

    if (result.success) {
      html += `<li>${icon} <strong>${fileLabel}</strong>: ${result.filename} (${formatFileSize(result.size)})</li>`;
    } else {
      html += `<li>${icon} <strong>${fileLabel}</strong>: ${result.error}</li>`;
    }
  });

  html += '</ul></div>';
  statusDiv.innerHTML = html;

  // Actualiser le status des fichiers après téléchargement
  setTimeout(checkCSVStatus, 1000);
}

function getFileLabel(type) {
  const labels = {
    'current_balance': 'Current Balance',
    'balance_by_exchange': 'Balance by Exchange',
    'coins_by_exchange': 'Coins by Exchange'
  };
  return labels[type] || type;
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

async function checkCSVStatus() {
  const statusDiv = document.getElementById('csv-download-status');
  if (!statusDiv) {
    console.debug('CSV status div not found, skipping CSV status check');
    return;
  }

  try {
    const response = await globalConfig.apiRequest('/csv/status');

    if (response.success) {
      displayCSVStatus(response.files);
    } else {
      statusDiv.innerHTML = '<div class="error">❌ Impossible de vérifier le status des fichiers CSV.</div>';
    }
  } catch (error) {
    statusDiv.innerHTML = `<div class="error">❌ Erreur vérification: ${error.message}</div>`;
  }
}

function displayCSVStatus(files) {
  const statusDiv = document.getElementById('csv-download-status');

  if (!files || files.length === 0) {
    statusDiv.innerHTML = '<div class="warning">⚠️ Aucun fichier CSV trouvé pour ce profil</div>';
    return;
  }

  let html = '<div style="margin-top: 16px;"><h4>Fichiers CSV disponibles:</h4><ul>';

  files.forEach(file => {
    const age = getFileAge(file.modified);
    const ageClass = age.days > 1 ? 'warning' : age.hours > 12 ? 'info' : 'success';

    html += `<li>
      <span class="status-indicator status-${ageClass}">📄</span>
      <strong>${file.name}</strong>
      (${formatFileSize(file.size)}, ${age.text})
    </li>`;
  });

  html += '</ul></div>';
  statusDiv.innerHTML = html;
}

function getFileAge(modifiedTimestamp) {
  const now = Date.now();
  const modified = new Date(modifiedTimestamp).getTime();
  const diffMs = now - modified;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return { days: diffDays, hours: diffHours, text: `${diffDays}j` };
  } else if (diffHours > 0) {
    return { days: 0, hours: diffHours, text: `${diffHours}h` };
  } else {
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    return { days: 0, hours: 0, text: `${diffMinutes}min` };
  }
}

function browseDownloadFolder() {
  // Pour l'instant, juste permettre de saisir manuellement
  // Dans une vraie application, on utiliserait l'API File System
  const currentPath = document.getElementById('csv_download_path').value;
  const newPath = prompt('Chemin du dossier de téléchargement:', currentPath);
  if (newPath) {
    document.getElementById('csv_download_path').value = newPath;
  }
}

// Charger le status des CSV au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
  // loadSettings() est déjà appelé dans le premier DOMContentLoaded (ligne ~2438)
  // donc pas besoin de l'appeler ici à nouveau
  setTimeout(checkCSVStatus, 1000); // Attendre que globalConfig soit prêt
  setTimeout(loadSaxoIntegrationStatus, 1500); // Load Saxo status

  // Écouter les changements d'utilisateur pour recharger les settings
  const userSelector = document.getElementById('user-selector');
  if (userSelector) {
    userSelector.addEventListener('change', async (e) => {
      try {
        await loadSettings();
      } catch (error) {
        debugLogger.error('Failed to reload settings after user change:', error);
      }
    });
  }
});

// ========== SAXO INTEGRATION MANAGEMENT ==========

async function loadSaxoIntegrationStatus() {
  try {
    const data = await globalConfig.apiRequest('/api/saxo/portfolios');
    updateSaxoStatus(data);

  } catch (error) {
    console.debug('Saxo integration not available or error:', error.message);
    // Fallback graceful avec état vide
    updateSaxoStatus({
      portfolios: [],
      error: 'Service temporairement indisponible',
      status: 'unavailable'
    });
  }
}

function updateSaxoStatus(data) {
  const countSpan = document.getElementById('saxo-portfolios-count');
  const dashboardBtn = document.getElementById('saxo-dashboard-btn');
  const stockValueSpan = document.getElementById('stock-value');

  if (data.portfolios && data.portfolios.length > 0) {
    const totalValue = data.portfolios.reduce((sum, p) => sum + p.total_value_usd, 0);

    if (countSpan) {
      countSpan.textContent = `${data.portfolios.length} portfolio(s) - $${totalValue.toLocaleString()}`;
      countSpan.style.color = 'var(--success)';
    }

    if (dashboardBtn) {
      dashboardBtn.disabled = false;
      dashboardBtn.style.opacity = '1';
    }

    // Update stock value in summary
    if (stockValueSpan) {
      stockValueSpan.textContent = `$${totalValue.toLocaleString()}`;
      stockValueSpan.style.color = 'var(--brand-primary)';
    }

  } else {
    if (countSpan) {
      countSpan.textContent = 'Aucun portfolio importé';
      countSpan.style.color = 'var(--theme-text-muted)';
    }

    if (dashboardBtn) {
      dashboardBtn.disabled = true;
      dashboardBtn.style.opacity = '0.5';
    }
  }
}

// === SAXO UPLOAD FUNCTIONS ===
async function handleSaxoUpload(event) {
  const file = event.target.files[0];
  if (!file) return;


  const progressDiv = document.getElementById('saxo-upload-progress');
  const resultDiv = document.getElementById('saxo-upload-result');

  // Show progress
  progressDiv.style.display = 'block';
  resultDiv.style.display = 'none';

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch((window.userSettings || getDefaultSettings()).api_base_url + '/api/saxo/upload', {
      method: 'POST',
      body: formData,
      headers: {
        'X-User': getActiveUser()
      }
    });

    const result = await response.json();

    if (response.ok) {
      // Success
      resultDiv.innerHTML = `
        <div style="padding: 1rem; background: var(--success-bg); border: 1px solid var(--success); border-radius: var(--radius-md); color: var(--success);">
          <strong>✅ Upload réussi!</strong><br>
          ${result.portfolios_count || 1} portfolio(s) importé(s) • ${result.positions_count || 0} positions
        </div>
      `;

      // Update status immediately
      await refreshSaxoStatus();

      // Show success toast (if available)
      if (window.showToast) {
        window.showToast('Portfolio Saxo importé avec succès!', 'success');
      }


    } else {
      throw new Error(result.error || result.detail || 'Upload failed');
    }

  } catch (error) {
    debugLogger.error('❌ Saxo upload error:', error);

    resultDiv.innerHTML = `
      <div style="padding: 1rem; background: var(--danger-bg); border: 1px solid var(--danger); border-radius: var(--radius-md); color: var(--danger);">
        <strong>❌ Erreur d'upload</strong><br>
        ${error.message}
      </div>
    `;
  } finally {
    progressDiv.style.display = 'none';
    resultDiv.style.display = 'block';

    // Clear file input
    event.target.value = '';

    // Hide result after 10 seconds
    setTimeout(() => {
      resultDiv.style.display = 'none';
    }, 10000);
  }
}

async function refreshSaxoStatus() {

  const statusSpan = document.getElementById('saxo-status-display');
  const dashboardBtn = document.getElementById('saxo-dashboard-btn');

  if (statusSpan) statusSpan.textContent = '🔄 Vérification...';

  try {
    // Use the wealth store utility
    const { fetchSaxoSummary, formatCurrency } = await import('../modules/wealth-saxo-summary.js');
    const summary = await fetchSaxoSummary();

    if (summary.isEmpty || summary.error) {
      if (statusSpan) {
        statusSpan.textContent = '📂 Aucun portfolio importé';
        statusSpan.style.color = 'var(--theme-text-muted)';
      }
      if (dashboardBtn) {
        dashboardBtn.disabled = true;
        dashboardBtn.style.opacity = '0.5';
      }
    } else {
      if (statusSpan) {
        statusSpan.innerHTML = `✅ Dernier import : ${summary.asof} • ${summary.positions_count} positions • ${formatCurrency(summary.total_value)}`;
        statusSpan.style.color = 'var(--success)';
      }
      if (dashboardBtn) {
        dashboardBtn.disabled = false;
        dashboardBtn.style.opacity = '1';
      }
    }

  } catch (error) {
    console.debug('[Settings Saxo] Error refreshing status:', error.message);
    if (statusSpan) {
      if (error.message?.includes('Failed to import')) {
        statusSpan.textContent = '⚠️ Module non disponible';
        statusSpan.style.color = 'var(--theme-text-muted)';
      } else {
        statusSpan.textContent = '❌ Service temporairement indisponible';
        statusSpan.style.color = 'var(--danger)';
      }
    }
    if (dashboardBtn) {
      dashboardBtn.disabled = true;
      dashboardBtn.style.opacity = '0.5';
    }
  }
}

// Initialize Saxo status on page load
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(refreshSaxoStatus, 1000); // Slight delay to ensure modules are loaded
});

// Make functions globally available
window.getActiveUser = getActiveUser;
window.buildQuickSourceDropdown = buildQuickSourceDropdown;
window.initQuickSettings = initQuickSettings;
window.getDefaultSettings = getDefaultSettings;
window.loadSettings = loadSettings;
window.saveSettings = saveSettings;
window.updateUI = updateUI;
window.updateStatusSummary = updateStatusSummary;
window.selectDataSource = selectDataSource;
window.selectPricing = selectPricing;
window.selectTheme = selectTheme;
window.saveAllSettings = saveAllSettings;
window.testDataSource = testDataSource;
window.autoDetectDebugToken = autoDetectDebugToken;
window.autoDetectApiKeys = autoDetectApiKeys;
window.maskApiKey = maskApiKey;
window.updateApiKeyStatus = updateApiKeyStatus;
window.toggleApiKeyVisibility = toggleApiKeyVisibility;
window.syncApiKeysFromEnv = syncApiKeysFromEnv;
window.syncApiKeysToEnv = syncApiKeysToEnv;
window.testApiKeys = testApiKeys;
window.runFullSystemTest = runFullSystemTest;
window.resetToDefaults = resetToDefaults;
window.exportSettings = exportSettings;
window.importSettings = importSettings;
window.clearCache = clearCache;
window.resetAllData = resetAllData;
window.showNotification = showNotification;
window.downloadCSVFiles = downloadCSVFiles;
window.getSelectedFiles = getSelectedFiles;
window.downloadSingleCSV = downloadSingleCSV;
window.displayDownloadResults = displayDownloadResults;
window.getFileLabel = getFileLabel;
window.formatFileSize = formatFileSize;
window.checkCSVStatus = checkCSVStatus;
window.displayCSVStatus = displayCSVStatus;
window.getFileAge = getFileAge;
window.browseDownloadFolder = browseDownloadFolder;
window.loadSaxoIntegrationStatus = loadSaxoIntegrationStatus;
window.updateSaxoStatus = updateSaxoStatus;
window.handleSaxoUpload = handleSaxoUpload;
window.refreshSaxoStatus = refreshSaxoStatus;
