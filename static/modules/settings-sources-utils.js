// Fonctions utilitaires pour la section Sources

function showSourcesConfiguration() {
  const details = document.getElementById('sources_config_details');
  if (details) {
    details.open = true;
    details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

async function saveSourcesConfiguration() {
  const ttl = document.getElementById('sources_snapshot_ttl').value;
  const warning = document.getElementById('sources_warning_threshold').value;
  const autoRefresh = document.getElementById('sources_auto_refresh').checked;

  // Sauvegarde via API pour persistance multi-device
  try {
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const response = await fetch('/api/users/settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User': activeUser
      },
      body: JSON.stringify({
        sources_snapshot_ttl: parseInt(ttl),
        sources_warning_threshold: parseInt(warning),
        sources_auto_refresh: autoRefresh
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();
    debugLogger.debug('Sources settings saved:', result);

    // Backup localStorage pour compatibilité
    localStorage.setItem('sources_auto_refresh', autoRefresh);

    showNotification('✅ Configuration sources sauvegardée', 'success');
  } catch (error) {
    debugLogger.error('Failed to save sources settings:', error);
    // Fallback localStorage
    localStorage.setItem('sources_auto_refresh', autoRefresh);
    showNotification('⚠️ Sauvegarde locale uniquement (API indisponible)', 'warning');
  }
}

function toggleSourcesLogs() {
  const logsDiv = document.getElementById('sources_logs');
  if (logsDiv) {
    logsDiv.style.display = logsDiv.style.display === 'none' ? 'block' : 'none';
  }
}

function clearSourcesLogs() {
  const logsContent = document.getElementById('sources_logs_content');
  if (logsContent) {
    logsContent.innerHTML = '';
  }
}

// Initialisation automatique quand l'onglet Sources est activé
document.addEventListener('DOMContentLoaded', function() {
  // Fonction d'initialisation
  function tryInitSourcesManager() {
    setTimeout(() => {
      if (typeof initSourcesManager === 'function') {
        initSourcesManager();
      } else {
        debugLogger.warn('[Sources] sources-manager.js not loaded');
      }
    }, 100);
  }

  // Observer les changements d'onglet
  const sourcesTab = document.querySelector('button[data-target="#tab-sources"]');
  if (sourcesTab) {
    sourcesTab.addEventListener('click', function() {
      tryInitSourcesManager();
    });
  }

  // Initialiser automatiquement si on arrive directement sur l'onglet Sources
  if (window.location.hash === '#tab-sources') {
    // Attendre que la page soit complètement chargée
    setTimeout(tryInitSourcesManager, 500);
  }
});

// Make functions globally available
window.showSourcesConfiguration = showSourcesConfiguration;
window.saveSourcesConfiguration = saveSourcesConfiguration;
window.toggleSourcesLogs = toggleSourcesLogs;
window.clearSourcesLogs = clearSourcesLogs;
