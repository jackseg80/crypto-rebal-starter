/**
 * SimControls - Interface de contrôle pour le simulateur
 * Sliders, toggles, presets avec debounce et badges automatiques
 */

console.debug('🎛️ SIM: SimControls loaded');

export class SimControls {
  constructor(containerId, onUpdateCallback) {
    this.container = document.getElementById(containerId);
    this.onUpdate = onUpdateCallback;
    this.debounceTimer = null;
    this.controlsWidth = 400;
    this.activePresetIndex = '';
    this.isLoadingPreset = false;
    this.presets = [];
    this.state = this.getDefaultState();

    document.documentElement.style.setProperty('--sim-controls-width', `${this.controlsWidth}px`);

    this.init();
  }

  getDefaultState() {
    return {
      // Decision Inputs
      cycleScore: 50,
      onChainScore: 50,
      riskScore: 50,
      cycleConf: 0.7,
      onchainConf: 0.6,
      regimeConf: 0.5,
      contradictionPenalty: 0.1,
      backendDecision: null,

      // Phase Engine
      phaseEngine: {
        enabled: false,
        mode: 'shadow',
        forcedPhase: null,
        offset: 0
      },

      // Risk Budget
      riskBudget: {
        curve: 'linear',
        min_stables: 10,
        max_stables: 60,
        hysteresis: { on: false, upDays: 3, downDays: 5 },
        circuit_breakers: { vol_z_gt: 2.5, dd_90d_pct_lt: -20, floor_stables_if_trigger: 70 }
      },

      // Market Overlays pour circuit breakers
      marketOverlays: {
        vol_z: 1.5,        // Z-score volatilité actuelle
        dd_90d_pct: -5,    // Drawdown 90j (%)
        breadth: 0.6       // Breadth du marché (0-1)
      },

      // Governance
      governance: {
        caps: {
          L2: 15,
          DeFi: 10,
          Gaming: 5,
          Memes: 8,
          Others: 5
        },
        max_btc: 50,
        max_eth: 35
      },

      // Execution
      execution: {
        global_delta_threshold_pct: 2,
        bucket_delta_threshold_pct: 1,
        min_lot_eur: 10,
        slippage_bps: 20
      },

      presetInfo: { name: 'Custom', desc: '' }
    };
  }

  init() {
    this.render();
    this.attachEventListeners();
    this.applyControlsWidth(this.controlsWidth);
  }

  render() {
    this.container.innerHTML = `
      <div class="sim-controls-wrapper">
        <div class="controls-header">
          <h3>🎛️ Contrôles de Simulation</h3>
          <div class="preset-controls">
            <select id="sim-preset-select" class="preset-select">
              <option value="">Choisir un preset...</option>
            </select>
            <button id="sim-export-btn" class="btn secondary">📤 Export</button>
            <button id="sim-reset-btn" class="btn secondary">🔄 Reset</button>
          </div>
        </div>

        <div class="controls-width">
          <label for="sim-controls-width">Largeur panneau</label>
          <div class="controls-width-input">
            <input type="range" id="sim-controls-width" min="320" max="540" step="10" value="${this.controlsWidth}">
            <span id="sim-controls-width-value">${this.controlsWidth}px</span>
          </div>
        </div>

        <div class="controls-content">
          <!-- Decision Inputs Section -->
          <div class="control-section">
            <h4>📊 Decision Inputs</h4>
            <div class="controls-grid">
              ${this.renderSlider('cycleScore', 'Cycle Score', 0, 100, 1, '%')}
              ${this.renderSlider('onChainScore', 'OnChain Score', 0, 100, 1, '%')}
              ${this.renderSlider('riskScore', 'Risk Score', 0, 100, 1, '%')}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('cycleConf', 'Cycle Confidence', 0, 1, 0.1, '', 100)}
              ${this.renderSlider('onchainConf', 'OnChain Confidence', 0, 1, 0.1, '', 100)}
              ${this.renderSlider('regimeConf', 'Regime Confidence', 0, 1, 0.1, '', 100)}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('contradictionPenalty', 'Contradiction Penalty', 0, 0.5, 0.05, '', 100)}
              <div class="control-group">
                <label>Backend Decision Override</label>
                <div class="backend-override">
                  <input type="checkbox" id="backend-enabled" />
                  <input type="number" id="backend-score" min="0" max="100" step="1" placeholder="Score" disabled />
                </div>
              </div>
            </div>
          </div>

          <!-- Phase Engine Section -->
          <div class="control-section">
            <h4>🌊 Phase Engine</h4>
            <div class="controls-grid">
              <div class="control-group">
                <label>
                  <input type="checkbox" id="phase-enabled" /> Phase Engine activé
                </label>
              </div>
              <div class="control-group">
                <label>Mode</label>
                <select id="phase-mode">
                  <option value="shadow">Shadow (log only)</option>
                  <option value="apply">Apply (real tilts)</option>
                </select>
              </div>
              <div class="control-group">
                <label>Phase forcée</label>
                <select id="phase-forced">
                  <option value="">Auto-détection</option>
                  <option value="risk_off">Risk Off</option>
                  <option value="eth_expansion">ETH Expansion</option>
                  <option value="largecap_alt">Large-cap Altseason</option>
                  <option value="full_altseason">Full Altseason</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Risk Budget Section -->
          <div class="control-section">
            <h4>💰 Risk Budget</h4>
            <div class="controls-grid">
              <div class="control-group">
                <label>Courbe DI→Stables</label>
                <select id="risk-curve">
                  <option value="linear">Linéaire</option>
                  <option value="sigmoid">Sigmoïde</option>
                </select>
              </div>
              ${this.renderSlider('min_stables', 'Min Stables', 5, 50, 1, '%')}
              ${this.renderSlider('max_stables', 'Max Stables', 30, 80, 1, '%')}
            </div>
            <div class="controls-grid">
              <div class="control-group">
                <label>
                  <input type="checkbox" id="hysteresis-enabled" /> Hystérésis
                </label>
              </div>
              ${this.renderSlider('hysteresis_up', 'Hystérésis Up (jours)', 1, 10, 1, 'j')}
              ${this.renderSlider('hysteresis_down', 'Hystérésis Down (jours)', 1, 15, 1, 'j')}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('cb_vol', 'CB Vol Z-Score', 1.5, 4, 0.1, 'σ')}
              ${this.renderSlider('cb_dd', 'CB Drawdown', -50, -5, 1, '%')}
              ${this.renderSlider('cb_floor', 'CB Floor Stables', 50, 90, 1, '%')}
            </div>
          </div>

          <!-- Governance Section -->
          <div class="control-section">
            <h4>🏛️ Governance Caps</h4>
            <div class="controls-grid">
              ${this.renderSlider('cap_L2', 'Cap L2/Scaling', 5, 30, 1, '%')}
              ${this.renderSlider('cap_DeFi', 'Cap DeFi', 2, 20, 1, '%')}
              ${this.renderSlider('cap_Gaming', 'Cap Gaming/NFT', 1, 15, 1, '%')}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('cap_Memes', 'Cap Memecoins', 1, 20, 1, '%')}
              ${this.renderSlider('cap_Others', 'Cap Others', 1, 15, 1, '%')}
              ${this.renderSlider('max_btc', 'Max BTC', 30, 70, 1, '%')}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('max_eth', 'Max ETH', 15, 50, 1, '%')}
            </div>
          </div>

          <!-- Execution Section -->
          <div class="control-section">
            <h4>⚡ Execution (Simulation)</h4>
            <div class="controls-grid">
              ${this.renderSlider('global_threshold', 'Seuil Global', 0.5, 10, 0.1, '%')}
              ${this.renderSlider('bucket_threshold', 'Seuil Bucket', 0.2, 5, 0.1, '%')}
              ${this.renderSlider('min_lot', 'Lot Minimum', 5, 100, 5, '€')}
            </div>
            <div class="controls-grid">
              ${this.renderSlider('slippage', 'Slippage', 5, 100, 5, 'bps')}
            </div>
          </div>
        </div>

        <!-- Badges Section -->
        <div class="sim-badges" id="sim-badges">
          <!-- Badges générés dynamiquement -->
        </div>
      </div>
    `;

    this.loadPresets();
    this.updateUI();
  }

  renderSlider(id, label, min, max, step, unit, multiplier = 1) {
    const value = this.getNestedValue(this.state, id);
    const displayValue = multiplier === 100 ? Math.round(value * 100) : value;

    return `
      <div class="control-group">
        <label for="sim-${id}">
          ${label}
          <span class="value-display" id="sim-${id}-value">${displayValue}${unit}</span>
        </label>
        <input
          type="range"
          id="sim-${id}"
          min="${min}"
          max="${max}"
          step="${step}"
          value="${displayValue}"
          data-multiplier="${multiplier}"
          class="sim-slider"
        />
      </div>
    `;
  }

  getNestedValue(obj, path) {
    try {
      // Mapping spécifique pour les valeurs complexes
      if (path === 'min_stables') return obj.riskBudget?.min_stables || 10;
      if (path === 'max_stables') return obj.riskBudget?.max_stables || 60;
      if (path === 'hysteresis_up') return obj.riskBudget?.hysteresis?.upDays || 3;
      if (path === 'hysteresis_down') return obj.riskBudget?.hysteresis?.downDays || 5;
      if (path === 'cb_vol') return obj.riskBudget?.circuit_breakers?.vol_z_gt || 2.5;
      if (path === 'cb_dd') return obj.riskBudget?.circuit_breakers?.dd_90d_pct_lt || -20;
      if (path === 'cb_floor') return obj.riskBudget?.circuit_breakers?.floor_stables_if_trigger || 70;
      if (path === 'cap_L2') return obj.governance?.caps?.L2 || 15;
      if (path === 'cap_DeFi') return obj.governance?.caps?.DeFi || 10;
      if (path === 'cap_Gaming') return obj.governance?.caps?.Gaming || 5;
      if (path === 'cap_Memes') return obj.governance?.caps?.Memes || 8;
      if (path === 'cap_Others') return obj.governance?.caps?.Others || 5;
      if (path === 'max_btc') return obj.governance?.max_btc || 50;
      if (path === 'max_eth') return obj.governance?.max_eth || 35;
      if (path === 'global_threshold') return obj.execution?.global_delta_threshold_pct || 2;
      if (path === 'bucket_threshold') return obj.execution?.bucket_delta_threshold_pct || 1;
      if (path === 'min_lot') return obj.execution?.min_lot_eur || 10;
      if (path === 'slippage') return obj.execution?.slippage_bps || 20;

      // Valeurs directes
      return obj[path] || 0;
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('🎛️ SIM: getNestedValue error for path:', path, error);
      return 0;
    }
  }

  attachEventListeners() {
    // Sliders avec debounce
    this.container.querySelectorAll('.sim-slider').forEach(slider => {
      slider.addEventListener('input', (e) => {
        this.updateState(e.target);
        this.updateValueDisplay(e.target);
        this.debouncedUpdate();
      });
    });

    // Inputs numériques (ex: overrides, thresholds)
    this.container.querySelectorAll('input[type="number"]').forEach(input => {
      input.addEventListener('input', (e) => {
        this.updateState(e.target);
        this.debouncedUpdate();
      });
    });

    // Toggles et selects
    this.container.addEventListener('change', (e) => {
      if (e.target.id === 'sim-preset-select') {
        return;
      }

      if (e.target.type === 'checkbox' || e.target.tagName === 'SELECT') {
        this.updateState(e.target);
        this.debouncedUpdate();
      }
    });

    // Backend override
    document.getElementById('backend-enabled')?.addEventListener('change', (e) => {
      const scoreInput = document.getElementById('backend-score');
      scoreInput.disabled = !e.target.checked;
      if (!e.target.checked) {
        this.state.backendDecision = null;
      }
      this.debouncedUpdate();
    });

    // Preset select
    document.getElementById('sim-preset-select')?.addEventListener('change', (e) => {
      const value = e.target.value;
      if (value) {
        this.loadPreset(value);
      } else {
        this.markCustomPreset(true);
        this.debouncedUpdate();
      }
    });

    // Export/Reset buttons
    document.getElementById('sim-export-btn')?.addEventListener('click', () => {
      this.exportState();
    });

    document.getElementById('sim-reset-btn')?.addEventListener('click', () => {
      this.resetToDefault();
    });

    // Controls width slider
    document.getElementById('sim-controls-width')?.addEventListener('input', (e) => {
      const value = parseInt(e.target.value, 10);
      if (!Number.isNaN(value)) {
        this.applyControlsWidth(value);
      }
    });
  }

  updateValueDisplay(slider) {
    const valueSpan = document.getElementById(slider.id + '-value');
    if (valueSpan) {
      const multiplier = parseFloat(slider.dataset.multiplier) || 1;
      const unit = valueSpan.textContent.match(/[^\d.-]/g)?.join('') || '';
      const value = multiplier === 100 ? Math.round(slider.value) : parseFloat(slider.value);
      valueSpan.textContent = value + unit;
    }
  }

  updateState(element) {
    const id = element.id.replace('sim-', '');
    const value = element.type === 'checkbox' ? element.checked :
                 element.type === 'range' ? parseFloat(element.value) :
                 element.value;

    // Mapping spécifique selon l'ID
    this.mapValueToState(id, value, element);

    if (!this.isLoadingPreset) {
      this.markCustomPreset();
    }
  }

  mapValueToState(id, value, element) {
    const multiplier = parseFloat(element.dataset?.multiplier) || 1;
    const adjustedValue = multiplier === 100 ? value / 100 : value;

    try {
      switch (id) {
        case 'cycleScore':
        case 'onChainScore':
        case 'riskScore':
          this.state[id] = value;
          break;

        case 'cycleConf':
        case 'onchainConf':
        case 'regimeConf':
        case 'contradictionPenalty':
          this.state[id] = adjustedValue;
          break;

        case 'phase-enabled':
          this.state.phaseEngine.enabled = value;
          break;

        case 'phase-mode':
          this.state.phaseEngine.mode = value;
          break;

        case 'phase-forced':
          this.state.phaseEngine.forcedPhase = value || null;
          break;

        case 'risk-curve':
          this.state.riskBudget.curve = value;
          break;

        case 'min-stables':
          this.state.riskBudget.min_stables = value;
          break;

        case 'max-stables':
          this.state.riskBudget.max_stables = value;
          break;

        case 'hysteresis-enabled':
          this.state.riskBudget.hysteresis.on = value;
          break;

        case 'hysteresis-up':
          this.state.riskBudget.hysteresis.upDays = value;
          break;

        case 'hysteresis-down':
          this.state.riskBudget.hysteresis.downDays = value;
          break;

        case 'cb-vol':
          this.state.riskBudget.circuit_breakers.vol_z_gt = adjustedValue;
          break;

        case 'cb-dd':
          this.state.riskBudget.circuit_breakers.dd_90d_pct_lt = value;
          break;

        case 'cb-floor':
          this.state.riskBudget.circuit_breakers.floor_stables_if_trigger = value;
          break;

        case 'cap-L2':
          this.state.governance.caps.L2 = value;
          break;

        case 'cap-DeFi':
          this.state.governance.caps.DeFi = value;
          break;

        case 'cap-Gaming':
          this.state.governance.caps.Gaming = value;
          break;

        case 'cap-Memes':
          this.state.governance.caps.Memes = value;
          break;

        case 'cap-Others':
          this.state.governance.caps.Others = value;
          break;

        case 'max-btc':
          this.state.governance.max_btc = value;
          break;

        case 'max-eth':
          this.state.governance.max_eth = value;
          break;

        case 'global-threshold':
          this.state.execution.global_delta_threshold_pct = adjustedValue;
          break;

        case 'bucket-threshold':
          this.state.execution.bucket_delta_threshold_pct = adjustedValue;
          break;

        case 'min-lot':
          this.state.execution.min_lot_eur = value;
          break;

        case 'slippage':
          this.state.execution.slippage_bps = value;
          break;

        case 'backend-score':
          if (document.getElementById('backend-enabled')?.checked) {
            this.state.backendDecision = { score: value, confidence: 0.9 };
          }
          break;

        default:
          (window.debugLogger?.warn || console.warn)('🎛️ SIM: Unknown control ID:', id);
          break;
      }
    } catch (error) {
      console.error('🎛️ SIM: mapValueToState error:', error, { id, value });
    }
  }

  debouncedUpdate() {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      this.updateBadges();
      if (this.onUpdate) {
        this.onUpdate(this.state);
      }
    }, 200); // 200ms debounce
  }

  updateBadges() {
    const badges = [];

    // Hystérésis
    if (this.state.riskBudget.hysteresis.on) {
      badges.push({ text: 'HYSTERESIS', type: 'info' });
    }

    // Circuit breakers
    if (this.state.riskBudget.circuit_breakers.vol_z_gt < 2.0) {
      badges.push({ text: 'CB_VOL', type: 'warning' });
    }
    if (this.state.riskBudget.circuit_breakers.dd_90d_pct_lt > -15) {
      badges.push({ text: 'CB_DD', type: 'warning' });
    }

    // Phase Engine
    if (this.state.phaseEngine.enabled && this.state.phaseEngine.mode === 'apply') {
      badges.push({ text: 'PHASE_TILTS', type: 'success' });
    }

    // Caps déclenchés (simulation)
    const strictCaps = Object.values(this.state.governance.caps).some(cap => cap < 10);
    if (strictCaps) {
      badges.push({ text: 'CAPS_TRIGGERED', type: 'warning' });
    }

    // Confiances faibles
    const lowConf = Math.min(this.state.cycleConf, this.state.onchainConf, this.state.regimeConf) < 0.4;
    if (lowConf) {
      badges.push({ text: 'LOW_CONF', type: 'danger' });
    }

    // Contradiction penalty
    if (this.state.contradictionPenalty > 0.2) {
      badges.push({ text: 'CONTRADICTION_PENALTY', type: 'warning' });
    }

    // Backend forcé
    if (this.state.backendDecision) {
      badges.push({ text: 'BACKEND_FORCED', type: 'info' });
    }

    this.renderBadges(badges);
  }

  renderBadges(badges) {
    const container = document.getElementById('sim-badges');
    if (!container) return;

    container.innerHTML = badges.map(badge =>
      `<span class="sim-badge sim-badge-${badge.type}">${badge.text}</span>`
    ).join('');
  }

  async loadPresets() {
    try {
      // Cache bust pour forcer le rechargement des presets v2
      const cacheBust = new Date().getTime();
      const response = await fetch(`./presets/sim_presets.json?v=${cacheBust}`);
      const data = await response.json();

      const select = document.getElementById('sim-preset-select');
      if (select && data.presets) {
        data.presets.forEach((preset, index) => {
          const option = document.createElement('option');
          option.value = index;
          option.textContent = `${preset.name} - ${preset.desc}`;
          // Tooltip détaillé au survol
          if (preset.tooltip) {
            option.title = preset.tooltip;
          }
          select.appendChild(option);
        });
      }

      this.presets = data.presets || [];
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('🎭 SIM: Failed to load presets:', error);
      this.presets = [];
    }
  }

  loadPreset(presetIndex) {
    const preset = this.presets[presetIndex];
    if (!preset) return;

    this.isLoadingPreset = true;
    this.activePresetIndex = String(presetIndex);

    const defaults = this.getDefaultState();

    // Importer les valeurs du preset
    this.state = {
      ...defaults,
      ...(preset.inputs || {}),
      phaseEngine: { ...defaults.phaseEngine, ...(preset.regime_phase || {}) },
      riskBudget: { ...defaults.riskBudget, ...(preset.risk_budget || {}) },
      marketOverlays: { ...defaults.marketOverlays, ...(preset.market_overlays || {}) },
      governance: { ...defaults.governance, ...(preset.governance || {}) },
      execution: { ...defaults.execution, ...(preset.execution || {}) },
      presetInfo: { name: preset.name, desc: preset.desc || '', tooltip: preset.tooltip || '' }
    };

    this.updateUI();
    this.isLoadingPreset = false;
    this.debouncedUpdate();

    (window.debugLogger?.debug || console.log)('🎭 SIM: presetLoaded -', { name: preset.name, version: preset.version });
  }

  updateUI() {
    // Mettre à jour tous les contrôles avec les valeurs du state
    Object.entries(this.state).forEach(([key, value]) => {
      if (typeof value === 'number') {
        const slider = document.getElementById(`sim-${key}`);
        if (slider) {
          const multiplier = parseFloat(slider.dataset.multiplier) || 1;
          slider.value = multiplier === 100 ? value * 100 : value;
          this.updateValueDisplay(slider);
        }
      }
    });

    // Cas spéciaux
    const phaseEnabled = document.getElementById('phase-enabled');
    if (phaseEnabled) phaseEnabled.checked = this.state.phaseEngine.enabled;

    const phaseMode = document.getElementById('phase-mode');
    if (phaseMode) phaseMode.value = this.state.phaseEngine.mode;

    const hysteresisEnabled = document.getElementById('hysteresis-enabled');
    if (hysteresisEnabled) hysteresisEnabled.checked = this.state.riskBudget.hysteresis.on;

    const presetSelect = document.getElementById('sim-preset-select');
    if (presetSelect) {
      presetSelect.value = this.activePresetIndex || '';
    }

    this.applyControlsWidth(this.controlsWidth);

    this.updateBadges();
  }

  exportState() {
    const exportData = {
      version: '1.0',
      created_with: 'simulator-ui-v1',
      name: prompt('Nom du preset:') || 'Custom Preset',
      desc: prompt('Description:') || 'Preset créé via UI',
      created_at: new Date().toISOString(),
      ...this.state
    };

    const dataStr = JSON.stringify(exportData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `preset_${exportData.name.replace(/\s+/g, '_')}.json`;
    a.click();

    URL.revokeObjectURL(url);
  }

  resetToDefault() {
    if (confirm('Remettre tous les contrôles par défaut ?')) {
      this.state = this.getDefaultState();
      this.activePresetIndex = '';
      this.markCustomPreset(true);
      this.updateUI();
      this.debouncedUpdate();
    }
  }

  getState() {
    return { ...this.state };
  }

  setState(newState) {
    this.state = { ...this.state, ...newState };
    if (!this.state.presetInfo) {
      this.state.presetInfo = { name: 'Custom', desc: '' };
    }
    this.activePresetIndex = '';
    this.updateUI();
  }

  applyControlsWidth(value) {
    const clamped = Math.min(Math.max(value, 320), 540);
    this.controlsWidth = clamped;
    document.documentElement.style.setProperty('--sim-controls-width', `${clamped}px`);

    const slider = document.getElementById('sim-controls-width');
    if (slider && Number(slider.value) !== clamped) {
      slider.value = clamped;
    }

    const label = document.getElementById('sim-controls-width-value');
    if (label) {
      label.textContent = `${clamped}px`;
    }
  }

  markCustomPreset(force = false) {
    if (this.isLoadingPreset && !force) {
      return;
    }

    this.activePresetIndex = '';
    this.state.presetInfo = { name: 'Custom', desc: '' };

    const presetSelect = document.getElementById('sim-preset-select');
    if (presetSelect && presetSelect.value !== '') {
      presetSelect.value = '';
    }
  }
}

// CSS pour les contrôles (injecté dynamiquement)
const controlsCSS = `
  .sim-controls-wrapper {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
    max-height: none;
    overflow: visible;
    width: 100%;
  }

  .controls-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: var(--space-sm);
    margin-bottom: var(--space-md);
    padding-bottom: var(--space-sm);
    border-bottom: 1px solid var(--theme-border);
  }

  .preset-controls {
    display: flex;
    gap: var(--space-sm);
    align-items: center;
  }

  .preset-select {
    padding: 0.5rem;
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-sm);
    background: var(--theme-bg);
    color: var(--theme-text);
    min-width: 200px;
  }

  .controls-width {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-md);
    flex-wrap: wrap;
    background: var(--theme-bg);
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-md);
    padding: var(--space-sm) var(--space-md);
    margin-bottom: var(--space-md);
  }

  .controls-width label {
    font-size: 0.9rem;
    color: var(--theme-text-muted);
  }

  .controls-width-input {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .controls-width-input input[type="range"] {
    width: 160px;
  }

  .controls-width-input span {
    font-family: monospace;
    font-size: 0.85rem;
    color: var(--theme-text);
  }

  .control-section {
    margin-bottom: var(--space-lg);
    padding: var(--space-md);
    background: var(--theme-bg);
    border-radius: var(--radius-md);
    border: 1px solid var(--theme-border);
  }

  .control-section h4 {
    margin: 0 0 var(--space-md) 0;
    color: var(--theme-text);
    font-size: 1rem;
    font-weight: 600;
  }

  .controls-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-md);
    margin-bottom: var(--space-md);
  }

  .control-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .control-group label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--theme-text);
  }

  .value-display {
    font-family: monospace;
    color: var(--brand-primary);
    font-weight: 600;
    background: var(--theme-surface);
    padding: 0.2rem 0.4rem;
    border-radius: var(--radius-xs);
    border: 1px solid var(--theme-border);
    min-width: 50px;
    text-align: center;
  }

  .sim-slider {
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: var(--theme-border);
    outline: none;
    -webkit-appearance: none;
  }

  .sim-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--brand-primary);
    cursor: pointer;
    border: 2px solid var(--theme-surface);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }

  .sim-slider::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--brand-primary);
    cursor: pointer;
    border: 2px solid var(--theme-surface);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }

  .backend-override {
    display: flex;
    gap: var(--space-sm);
    align-items: center;
  }

  .backend-override input[type="number"] {
    padding: 0.4rem;
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-sm);
    background: var(--theme-bg);
    color: var(--theme-text);
    width: 80px;
  }

  .backend-override input[type="number"]:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .sim-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-top: var(--space-md);
    padding-top: var(--space-md);
    border-top: 1px solid var(--theme-border);
  }

  .sim-badge {
    padding: 0.3rem 0.6rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .sim-badge-info {
    background: color-mix(in oklab, var(--brand-primary) 20%, transparent);
    color: var(--brand-primary);
    border: 1px solid var(--brand-primary);
  }

  .sim-badge-success {
    background: color-mix(in oklab, var(--success) 20%, transparent);
    color: var(--success);
    border: 1px solid var(--success);
  }

  .sim-badge-warning {
    background: color-mix(in oklab, var(--warning) 20%, transparent);
    color: var(--warning);
    border: 1px solid var(--warning);
  }

  .sim-badge-danger {
    background: color-mix(in oklab, var(--danger) 20%, transparent);
    color: var(--danger);
    border: 1px solid var(--danger);
  }

  .btn.secondary {
    padding: 0.5rem 1rem;
    border: 1px solid var(--theme-border);
    background: var(--theme-surface);
    color: var(--theme-text);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
  }

  .btn.secondary:hover {
    background: var(--brand-primary);
    color: white;
    border-color: var(--brand-primary);
  }

  select, input[type="checkbox"] {
    accent-color: var(--brand-primary);
  }

  @media (max-width: 768px) {
    .controls-header {
      flex-direction: column;
      gap: var(--space-sm);
      align-items: stretch;
    }

    .controls-grid {
      grid-template-columns: 1fr;
    }

    .preset-controls {
      flex-direction: column;
      width: 100%;
    }

    .preset-select {
      min-width: auto;
      width: 100%;
    }
  }
`;

// Injecter le CSS
if (!document.getElementById('sim-controls-css')) {
  const style = document.createElement('style');
  style.id = 'sim-controls-css';
  style.textContent = controlsCSS;
  document.head.appendChild(style);
}
