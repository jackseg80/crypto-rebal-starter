// Migration Controls Component - PR-C
// Interface utilisateur pour contrôler la migration Strategy API
// Permet de basculer entre legacy et nouvelle API, comparer les résultats

import { StrategyConfig, getAvailableStrategyTemplates, compareStrategyTemplates } from '../core/strategy-api-adapter.js';

/**
 * Crée les contrôles de migration dans un container
 * @param {HTMLElement} container - Element conteneur
 */
export function createMigrationControls(container) {
  if (!container) return;
  
  // Créer le panel de contrôles
  const controlPanel = document.createElement('div');
  controlPanel.className = 'migration-controls';
  controlPanel.innerHTML = `
    <div class="migration-panel">
      <h4>🚀 Strategy API Migration (PR-C)</h4>
      
      <div class="migration-toggle">
        <label>
          <input type="checkbox" id="migration-enabled" checked>
          Utiliser Strategy API Backend
        </label>
      </div>
      
      <div class="template-selector">
        <label for="default-template">Template par défaut:</label>
        <select id="default-template">
          <option value="balanced">Balanced</option>
          <option value="conservative">Conservative</option>
          <option value="aggressive">Aggressive</option>
          <option value="phase_follower">Phase Follower</option>
          <option value="contradiction_averse">Contradiction Averse</option>
        </select>
      </div>
      
      <div class="migration-actions">
        <button id="clear-cache">Clear Cache</button>
        <button id="compare-templates">Compare Templates</button>
        <button id="toggle-debug">Debug Mode</button>
      </div>
      
      <div class="migration-status">
        <div id="migration-info">
          <span class="status-indicator">●</span>
          <span id="status-text">Strategy API Ready</span>
        </div>
        <div id="last-result" class="result-display"></div>
      </div>
    </div>
  `;
  
  // Ajouter les styles
  const style = document.createElement('style');
  style.textContent = `
    .migration-controls {
      position: fixed;
      top: 10px;
      right: 10px;
      z-index: 9999;
      background: var(--bg-secondary, #1a1a1a);
      border: 1px solid var(--border, #333);
      border-radius: 8px;
      padding: 12px;
      max-width: 300px;
      font-size: 13px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    
    .migration-panel h4 {
      margin: 0 0 10px 0;
      color: var(--text-primary, #fff);
      font-size: 14px;
    }
    
    .migration-toggle {
      margin-bottom: 10px;
    }
    
    .migration-toggle label {
      display: flex;
      align-items: center;
      color: var(--text-secondary, #ccc);
      cursor: pointer;
    }
    
    .migration-toggle input {
      margin-right: 6px;
    }
    
    .template-selector {
      margin-bottom: 10px;
    }
    
    .template-selector label {
      display: block;
      color: var(--text-secondary, #ccc);
      margin-bottom: 4px;
    }
    
    .template-selector select {
      width: 100%;
      padding: 4px;
      border: 1px solid var(--border, #333);
      border-radius: 4px;
      background: var(--bg-primary, #000);
      color: var(--text-primary, #fff);
    }
    
    .migration-actions {
      margin-bottom: 10px;
    }
    
    .migration-actions button {
      margin: 2px;
      padding: 4px 8px;
      font-size: 11px;
      border: 1px solid var(--border, #333);
      border-radius: 4px;
      background: var(--bg-primary, #000);
      color: var(--text-primary, #fff);
      cursor: pointer;
    }
    
    .migration-actions button:hover {
      background: var(--accent, #007acc);
    }
    
    .migration-status {
      border-top: 1px solid var(--border, #333);
      padding-top: 8px;
    }
    
    .status-indicator {
      color: var(--success, #4caf50);
    }
    
    .status-indicator.error {
      color: var(--danger, #f44336);
    }
    
    .result-display {
      margin-top: 6px;
      padding: 6px;
      background: var(--bg-primary, #000);
      border-radius: 4px;
      font-family: monospace;
      font-size: 11px;
      color: var(--text-secondary, #ccc);
      max-height: 100px;
      overflow-y: auto;
    }
    
    .migration-controls.minimized .migration-panel > *:not(h4) {
      display: none;
    }
    
    .migration-controls.minimized {
      max-width: 200px;
    }
    
    .migration-controls h4 {
      cursor: pointer;
      user-select: none;
    }
  `;
  
  container.appendChild(style);
  container.appendChild(controlPanel);
  
  // État des contrôles
  let debugMode = false;
  let templates = {};
  
  // Références DOM
  const enabledCheckbox = controlPanel.querySelector('#migration-enabled');
  const templateSelect = controlPanel.querySelector('#default-template');
  const clearCacheBtn = controlPanel.querySelector('#clear-cache');
  const compareBtn = controlPanel.querySelector('#compare-templates');
  const debugBtn = controlPanel.querySelector('#toggle-debug');
  const statusText = controlPanel.querySelector('#status-text');
  const statusIndicator = controlPanel.querySelector('.status-indicator');
  const resultDisplay = controlPanel.querySelector('#last-result');
  const panelTitle = controlPanel.querySelector('h4');
  
  // Update status display
  function updateStatus(status, isError = false) {
    statusText.textContent = status;
    statusIndicator.className = isError ? 'status-indicator error' : 'status-indicator';
  }
  
  // Event listeners
  enabledCheckbox.addEventListener('change', (e) => {
    StrategyConfig.setEnabled(e.target.checked);
    updateStatus(e.target.checked ? 'Strategy API Enabled' : 'Legacy Mode');
  });
  
  templateSelect.addEventListener('change', (e) => {
    StrategyConfig.setDefaultTemplate(e.target.value);
    updateStatus(`Template: ${e.target.value}`);
  });
  
  clearCacheBtn.addEventListener('click', () => {
    StrategyConfig.clearCache();
    updateStatus('Cache Cleared');
    resultDisplay.textContent = '';
  });
  
  debugBtn.addEventListener('click', () => {
    debugMode = !debugMode;
    StrategyConfig.setDebugMode(debugMode);
    debugBtn.textContent = debugMode ? 'Debug ON' : 'Debug Mode';
    updateStatus(debugMode ? 'Debug Enabled' : 'Debug Disabled');
  });
  
  compareBtn.addEventListener('click', async () => {
    try {
      updateStatus('Comparing templates...');
      const comparison = await compareStrategyTemplates(['conservative', 'balanced', 'aggressive']);
      
      const results = Object.entries(comparison.comparisons || {})
        .map(([id, data]) => `${id}: ${data.decision_score?.toFixed(1) || 'N/A'}`)
        .join(', ');
      
      resultDisplay.textContent = `Scores: ${results}`;
      updateStatus('Comparison Complete');
    } catch (error) {
      updateStatus('Comparison Failed', true);
      resultDisplay.textContent = `Error: ${error.message}`;
    }
  });
  
  // Minimize/maximize panel
  panelTitle.addEventListener('click', () => {
    controlPanel.parentElement.classList.toggle('minimized');
  });
  
  // Charger les templates disponibles
  async function loadTemplates() {
    try {
      templates = await getAvailableStrategyTemplates();
      
      // Update template selector
      templateSelect.innerHTML = '';
      Object.entries(templates).forEach(([id, info]) => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = `${info.name} (${info.risk_level})`;
        templateSelect.appendChild(option);
      });
      
      updateStatus(`${Object.keys(templates).length} templates loaded`);
    } catch (error) {
      updateStatus('Failed to load templates', true);
    }
  }
  
  // Initialisation
  loadTemplates();
}

/**
 * Crée un indicateur de migration simple pour les dashboards
 * @param {HTMLElement} container - Container
 * @param {function} onToggle - Callback quand migration toggle
 */
export function createMigrationIndicator(container, onToggle) {
  if (!container) return;
  
  const indicator = document.createElement('div');
  indicator.className = 'migration-indicator';
  indicator.innerHTML = `
    <div class="indicator-content">
      <span class="indicator-icon">🚀</span>
      <span class="indicator-text">Strategy API</span>
      <button class="indicator-toggle" title="Toggle Strategy API">
        <span class="toggle-switch"></span>
      </button>
    </div>
  `;
  
  const style = document.createElement('style');
  style.textContent = `
    .migration-indicator {
      display: inline-flex;
      align-items: center;
      background: var(--bg-secondary, #1a1a1a);
      border: 1px solid var(--border, #333);
      border-radius: 16px;
      padding: 4px 8px;
      font-size: 12px;
      color: var(--text-secondary, #ccc);
    }
    
    .indicator-content {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    
    .indicator-icon {
      font-size: 14px;
    }
    
    .indicator-toggle {
      background: none;
      border: none;
      cursor: pointer;
      padding: 2px;
    }
    
    .toggle-switch {
      display: block;
      width: 24px;
      height: 12px;
      background: var(--bg-primary, #000);
      border-radius: 6px;
      position: relative;
      transition: background 0.3s;
    }
    
    .toggle-switch:before {
      content: '';
      position: absolute;
      top: 1px;
      left: 1px;
      width: 10px;
      height: 10px;
      background: var(--text-secondary, #ccc);
      border-radius: 50%;
      transition: transform 0.3s;
    }
    
    .indicator-toggle.active .toggle-switch {
      background: var(--success, #4caf50);
    }
    
    .indicator-toggle.active .toggle-switch:before {
      transform: translateX(12px);
      background: white;
    }
  `;
  
  container.appendChild(style);
  container.appendChild(indicator);
  
  const toggleBtn = indicator.querySelector('.indicator-toggle');
  const config = StrategyConfig.getConfig();
  
  // État initial
  toggleBtn.classList.toggle('active', config.enabled);
  
  // Event listener
  toggleBtn.addEventListener('click', () => {
    const newState = !StrategyConfig.getConfig().enabled;
    StrategyConfig.setEnabled(newState);
    toggleBtn.classList.toggle('active', newState);
    
    if (onToggle) {
      onToggle(newState);
    }
  });
  
  return indicator;
}