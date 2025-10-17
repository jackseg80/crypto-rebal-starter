// Intelligence ML Tab - Simplified integration without external ML components

let mlTabInitialized = false;

// Initialisation quand l'onglet ML est sélectionné
function initializeMLTab() {
  debugLogger.debug('🤖 Initializing Intelligence ML tab...');

  try {
    // Démarrer les prédictions temps réel
    loadMLPredictions();
    loadMLPipelineStatus();

    // Refresh périodique des prédictions
    setInterval(loadMLPredictions, 60000); // 1 minute
    setInterval(loadMLPipelineStatus, 120000); // 2 minutes

    mlTabInitialized = true;
    debugLogger.debug('✅ Intelligence ML tab initialized');

  } catch (error) {
    debugLogger.error('❌ ML tab initialization failed:', error);
    showMLError('Initialization failed: ' + error.message);
  }
}

// Chargement du statut ML global et prédictions - UTILISE SOURCE CENTRALISÉE
async function loadMLPredictions() {
  try {
    // 1) Statut ML global depuis source unifiée
    const { getUnifiedMLStatus } = await import('./shared-ml-functions.js');
    const mlStatus = await getUnifiedMLStatus();

    if (mlStatus && mlStatus.individual) {
      // Statistiques globales depuis source centralisée
      document.getElementById('ml-active-models').textContent = `${mlStatus.totalLoaded}/${mlStatus.totalModels}`;

      // Confiance depuis source centralisée
      const confidencePercent = Math.round((mlStatus.confidence || 0) * 100);
      document.getElementById('ml-avg-confidence').textContent = `${confidencePercent}%`;

      // Dernière mise à jour depuis source centralisée
      document.getElementById('ml-last-update').textContent =
        mlStatus.timestamp ? new Date(mlStatus.timestamp).toLocaleTimeString('fr-FR') : '--';

      // Statuts des modèles individuels depuis source centralisée
      const individual = mlStatus.individual;

      // Volatility LSTM depuis source centralisée
      const volModelsLoaded = individual.volatility.loaded;
      const volSymbols = individual.volatility.symbols || 0;
      const volStatus = volModelsLoaded > 0 ? 'active' : 'inactive';
      const volStatusEl = document.getElementById('ml-vol-model-status');
      const volDetailsEl = document.getElementById('ml-vol-model-details');
      if (volStatusEl && volDetailsEl) {
        const icons = { 'active': '🟢', 'ready': '🟢', 'training': '🔄', 'error': '🔴', 'inactive': '⚪', 'unknown': '❓' };
        volStatusEl.textContent = `${icons[volStatus]} ${volStatus.charAt(0).toUpperCase() + volStatus.slice(1)}`;
        volDetailsEl.textContent = `${volModelsLoaded} modèles • ${volSymbols} symboles`;
      }

      // Regime HMM depuis source centralisée
      const regimeStatus = individual.regime.loaded > 0 ? 'active' : 'inactive';
      const regimeStatusEl = document.getElementById('ml-regime-model-status');
      const regimeDetailsEl = document.getElementById('ml-regime-model-details');
      if (regimeStatusEl && regimeDetailsEl) {
        const icons = { 'active': '🟢', 'ready': '🟢', 'training': '🔄', 'error': '🔴', 'inactive': '⚪', 'unknown': '❓' };
        regimeStatusEl.textContent = `${icons[regimeStatus]} ${regimeStatus.charAt(0).toUpperCase() + regimeStatus.slice(1)}`;
        regimeDetailsEl.textContent = individual.regime.available ? 'Modèle disponible' : 'Non disponible';
      }

      // Correlation Transformer depuis source centralisée
      const corrModelsLoaded = individual.correlation.loaded;
      const corrStatus = corrModelsLoaded > 0 ? 'active' : 'inactive';
      const corrStatusEl = document.getElementById('ml-corr-model-status');
      const corrDetailsEl = document.getElementById('ml-corr-model-details');
      if (corrStatusEl && corrDetailsEl) {
        const icons = { 'active': '🟢', 'ready': '🟢', 'training': '🔄', 'error': '🔴', 'inactive': '⚪', 'unknown': '❓' };
        corrStatusEl.textContent = `${icons[corrStatus]} ${corrStatus.charAt(0).toUpperCase() + corrStatus.slice(1)}`;
        corrDetailsEl.textContent = `${corrModelsLoaded} modèles chargés`;
      }

      // Sentiment Composite depuis source centralisée
      const sentStatusEl = document.getElementById('ml-sent-model-status');
      const sentDetailsEl = document.getElementById('ml-sent-model-details');
      if (sentStatusEl && sentDetailsEl) {
        const sentStatus = individual.sentiment.loaded > 0 ? 'active' : 'inactive';
        const icons = { 'active': '🟢', 'inactive': '⚪' };
        sentStatusEl.textContent = `${icons[sentStatus]} ${sentStatus.charAt(0).toUpperCase() + sentStatus.slice(1)}`;
        sentDetailsEl.textContent = individual.sentiment.available ? 'API composite disponible' : 'Non disponible';
      }

      debugLogger.debug(`✅ ML Status chargé depuis source centralisée: ${mlStatus.source}`);
    } else {
      debugLogger.warn('⚠️ Impossible de charger le statut ML unifié, utilisation des API individuelles...');
      // Fallback vers l'ancien système si source centralisée échoue
      await loadMLPredictionsFallback();
    }

    // 2) Volatilité BTC/ETH
    const volResponse = await fetch('/api/ml/volatility/predict/BTC?horizon_days=1');
    if (volResponse.ok) {
      const volData = await volResponse.json();
      const vol = volData.volatility_forecast?.volatility_forecast || volData.volatility;
      document.getElementById('ml-vol-btc').textContent =
        vol ? `${(vol * 100).toFixed(1)}%` : '--';
    }

    const volETHResponse = await fetch('/api/ml/volatility/predict/ETH?horizon_days=1');
    if (volETHResponse.ok) {
      const volETHData = await volETHResponse.json();
      const vol = volETHData.volatility_forecast?.volatility_forecast || volETHData.volatility;
      document.getElementById('ml-vol-eth').textContent =
        vol ? `${(vol * 100).toFixed(1)}%` : '--';
    }

    // 3) Régime de marché
    const regimeResponse = await fetch('/api/ml/regime/current');
    if (regimeResponse.ok) {
      const regimeData = await regimeResponse.json();
      const regimeEl = document.getElementById('ml-regime');
      if (regimeData.regime_prediction) {
        const regime = regimeData.regime_prediction.regime_name || '--';
        regimeEl.textContent = regime;
        regimeEl.className = `metric-value regime-${regime.toLowerCase() === 'sideways' ? 'neutral' : regime.toLowerCase()}`;
      }
    }

    // 4) Sentiment F&G
    const sentResponse = await fetch('/api/ml/sentiment/fear-greed?days=1');
    if (sentResponse.ok) {
      const sentData = await sentResponse.json();
      const sentEl = document.getElementById('ml-sentiment');
      if (sentData.aggregated_sentiment) {
        const score = Math.round(sentData.aggregated_sentiment.score * 100); // Score sur 100
        sentEl.textContent = score;
        sentEl.className = `metric-value sentiment-${score < 25 ? 'fear' : score > 75 ? 'greed' : 'neutral'}`;
      }
    }

  } catch (error) {
    debugLogger.warn('ML predictions update failed:', error);
  }
}

// Fallback vers ancien système si source centralisée échoue
async function loadMLPredictionsFallback() {
  try {
    // Ancien système comme fallback
    const statusResponse = await fetch('/api/ml/status');
    if (statusResponse.ok) {
      const statusData = await statusResponse.json();
      const pipeline = statusData.pipeline_status || {};

      const totalLoaded = Math.min(Math.max(0, pipeline.loaded_models_count || 0), 4);
      document.getElementById('ml-active-models').textContent = `${totalLoaded}/4`;

      const confidencePercent = Math.min(100, Math.round((totalLoaded / 4) * 100));
      document.getElementById('ml-avg-confidence').textContent = `${confidencePercent}%`;

      const lastUpdate = pipeline.timestamp || statusData.timestamp;
      document.getElementById('ml-last-update').textContent =
        lastUpdate ? new Date(lastUpdate).toLocaleTimeString('fr-FR') : '--';

      debugLogger.debug('⚠️ Using ML fallback system');
    }
  } catch (error) {
    debugLogger.error('ML fallback also failed:', error);
  }
}

// Chargement du statut pipeline ML
async function loadMLPipelineStatus() {
  try {
    const response = await fetch('/api/ml/debug/pipeline-info', {
      headers: { 'X-Admin-Key': 'crypto-rebal-admin-2024' }
    });

    const container = document.getElementById('ml-pipeline-container');

    if (response.ok) {
      const data = await response.json();
      container.innerHTML = `
        <div>Models Loaded: ${data.models_loaded || 0}/4</div>
        <div>Cache Size: ${data.cache_size || 0} entries</div>
        <div>Last Update: ${data.last_update || 'Never'}</div>
        <div>Status: <span style="color: var(--success);">${data.status || 'Unknown'}</span></div>
      `;
    } else if (response.status === 401 || response.status === 403) {
      container.innerHTML = '<div style="color: var(--warning);">⚠️ Admin access required for pipeline info</div>';
    } else {
      container.innerHTML = '<div style="color: var(--danger);">❌ Pipeline status unavailable</div>';
    }

  } catch (error) {
    debugLogger.warn('Pipeline status update failed:', error);
    document.getElementById('ml-pipeline-container').innerHTML =
      '<div style="color: var(--danger);">❌ Connection error</div>';
  }
}

// Actions Admin ML
window.triggerMLRetraining = async function () {
  if (!confirm('Déclencher le re-entrainement des modèles ML ? (Peut prendre plusieurs minutes)')) return;

  try {
    const response = await fetch('/api/ml/train', {
      method: 'POST',
      headers: { 'X-Admin-Key': 'crypto-rebal-admin-2024' }
    });

    if (response.ok) {
      alert('✅ Re-entrainement démarré en arrière-plan');
    } else {
      alert('❌ Erreur lors du démarrage: ' + response.statusText);
    }
  } catch (error) {
    alert('❌ Erreur: ' + error.message);
  }
};

window.clearMLCache = async function () {
  if (!confirm('Vider le cache ML ?')) return;

  try {
    const response = await fetch('/api/ml/cache/clear', {
      method: 'DELETE',
      headers: { 'X-Admin-Key': 'crypto-rebal-admin-2024' }
    });

    if (response.ok) {
      alert('✅ Cache ML vidé');
      location.reload();
    } else {
      alert('❌ Erreur: ' + response.statusText);
    }
  } catch (error) {
    alert('❌ Erreur: ' + error.message);
  }
};

window.downloadMLLogs = function () {
  window.open('/api/logs?component=ml&format=txt', '_blank');
};

window.showMLDebug = async function () {
  try {
    const response = await fetch('/api/ml/debug/pipeline-info', {
      headers: { 'X-Admin-Key': 'crypto-rebal-admin-2024' }
    });

    if (response.ok) {
      const data = await response.json();
      const debugWindow = window.open('', '_blank', 'width=800,height=600');
      debugWindow.document.write(`
        <html>
          <head><title>ML Debug Info</title></head>
          <body style="font-family: monospace; padding: 20px;">
            <h2>ML Debug Information</h2>
            <pre>${JSON.stringify(data, null, 2)}</pre>
          </body>
        </html>
      `);
    } else {
      alert('❌ Admin access required');
    }
  } catch (error) {
    alert('❌ Erreur: ' + error.message);
  }
};

function showMLError(message) {
  document.getElementById('tab-intelligence-ml').innerHTML = `
    <div class="panel-card" style="text-align: center; padding: 4rem; color: var(--danger);">
      <h3>⚠️ Intelligence ML Error</h3>
      <p>${message}</p>
      <button onclick="location.reload()" style="background: var(--brand-primary); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: var(--radius-md); cursor: pointer;">
        Retry
      </button>
    </div>
  `;
}

// Auto-initialisation quand l'onglet devient actif
document.addEventListener('DOMContentLoaded', () => {
  // Observer les changements d'onglets - intégration avec le système existant
  const tabButtons = document.querySelectorAll('.tab-btn');

  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const targetId = button.dataset.target;

      // Si c'est l'onglet Intelligence ML
      if (targetId === '#tab-intelligence-ml') {
        setTimeout(() => {
          if (!mlTabInitialized) {
            initializeMLTab();
          }
        }, 100); // Petit délai pour que l'onglet soit visible
      }
    });
  });

  // Initialisation préventive des données ML (même si l'onglet n'est pas actif)
  // Cela permet d'avoir les données prêtes quand l'utilisateur clique sur l'onglet
  setTimeout(() => {
    debugLogger.debug('🤖 Pre-loading ML data for Intelligence tab...');
    loadMLPredictions();
    loadMLPipelineStatus();
    mlTabInitialized = true;
  }, 1000); // Délai pour laisser la page se charger

  // Auto-init si l'URL contient #ml
  if (window.location.hash === '#ml' || window.location.search.includes('tab=ml')) {
    setTimeout(() => {
      const mlTab = document.querySelector('[data-target="#tab-intelligence-ml"]');
      mlTab?.click();
    }, 500);
  }
});
