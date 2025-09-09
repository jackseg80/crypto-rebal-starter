/**
 * GovernancePanel.js - Composant UI pour la gouvernance des décisions
 * 
 * Fonctionnalités :
 * - Affichage du statut de gouvernance en temps réel
 * - Modal d'approbation pour les décisions proposées
 * - Contrôles freeze/unfreeze du système
 * - Indicateurs ML (contradiction index, confidence, etc.)
 */

import { store } from '../core/risk-dashboard-store.js';

class GovernancePanel {
  constructor(container) {
    this.container = container;
    this.isVisible = false;
    this.refreshInterval = null;
    
    this.init();
  }
  
  init() {
    this.render();
    this.bindEvents();
    this.startAutoRefresh();
  }
  
  render() {
    const html = `
      <div class="governance-panel" id="governance-panel">
        <div class="governance-header">
          <h3>🏛️ Decision Engine</h3>
          <button class="governance-toggle" id="governance-toggle">
            <span class="toggle-icon">▲</span>
          </button>
        </div>
        
        <div class="governance-content" id="governance-content">
          <!-- Status Section -->
          <div class="governance-section">
            <h4>📊 System Status</h4>
            <div class="status-grid">
              <div class="status-item">
                <label>State:</label>
                <span class="status-badge" id="gov-state">LOADING...</span>
              </div>
              <div class="status-item">
                <label>Mode:</label>
                <span class="mode-badge" id="gov-mode">manual</span>
              </div>
              <div class="status-item">
                <label>Policy:</label>
                <span class="policy-info" id="gov-policy">Normal 8%</span>
              </div>
              <div class="status-item">
                <label>Contradiction:</label>
                <span class="contradiction-meter" id="gov-contradiction">0%</span>
              </div>
            </div>
          </div>
          
          <!-- ML Signals Section -->
          <div class="governance-section">
            <h4>🧠 ML Signals</h4>
            <div class="signals-grid" id="ml-signals">
              <div class="signal-item">
                <label>Confidence:</label>
                <div class="signal-bar">
                  <div class="signal-fill" id="confidence-fill"></div>
                  <span class="signal-value" id="confidence-value">--</span>
                </div>
              </div>
              <div class="signal-item">
                <label>Decision Score:</label>
                <div class="signal-bar">
                  <div class="signal-fill" id="decision-fill"></div>
                  <span class="signal-value" id="decision-value">--</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Mode Selection Section -->
          <div class="governance-section">
            <h4>🎛️ Governance Mode</h4>
            <div class="mode-selector" id="mode-selector">
              <select class="gov-select" id="governance-mode-select">
                <option value="manual">🤝 Manual</option>
                <option value="ai_assisted">🤖 AI Assisted</option>
                <option value="full_ai">🚀 Full AI</option>
              </select>
              <button class="gov-btn secondary" id="btn-change-mode">
                Change Mode
              </button>
            </div>
          </div>

          <!-- Actions Section -->
          <div class="governance-section">
            <h4>⚡ Actions</h4>
            <div class="actions-grid">
              <button class="gov-btn primary" id="btn-refresh" title="Refresh governance state">
                🔄 Refresh
              </button>
              <button class="gov-btn secondary" id="btn-propose" title="Propose test decision">
                📋 Propose
              </button>
              <button class="gov-btn warning" id="btn-freeze" title="Freeze system (emergency stop)">
                ❄️ Freeze
              </button>
              <button class="gov-btn success" id="btn-unfreeze" title="Unfreeze system" disabled>
                🔥 Unfreeze
              </button>
            </div>
          </div>
          
          <!-- Pending Decision Section (shown when DRAFT state) -->
          <div class="governance-section pending-decision" id="pending-decision" style="display: none;">
            <h4>📋 Pending Decision</h4>
            <div class="decision-summary" id="decision-summary">
              <p>No pending decisions</p>
            </div>
            <div class="decision-actions">
              <button class="gov-btn success" id="btn-approve">
                ✅ Approve
              </button>
              <button class="gov-btn danger" id="btn-reject">
                ❌ Reject
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Approval Modal -->
      <div class="governance-modal" id="approval-modal" style="display: none;">
        <div class="modal-content">
          <div class="modal-header">
            <h3>📋 Decision Approval</h3>
            <button class="modal-close" id="modal-close">&times;</button>
          </div>
          <div class="modal-body" id="modal-body">
            <!-- Dynamic content -->
          </div>
          <div class="modal-footer">
            <button class="gov-btn secondary" id="modal-cancel">Cancel</button>
            <button class="gov-btn danger" id="modal-reject">Reject</button>
            <button class="gov-btn success" id="modal-approve">Approve</button>
          </div>
        </div>
      </div>
    `;
    
    this.container.innerHTML = html;
  }
  
  bindEvents() {
    // Toggle panel
    document.getElementById('governance-toggle').addEventListener('click', () => {
      this.togglePanel();
    });
    
    // Mode selector
    document.getElementById('btn-change-mode').addEventListener('click', () => {
      this.changeGovernanceMode();
    });

    // Action buttons
    document.getElementById('btn-refresh').addEventListener('click', () => {
      this.refreshState();
    });

    document.getElementById('btn-propose').addEventListener('click', () => {
      this.proposeDecision();
    });
    
    document.getElementById('btn-freeze').addEventListener('click', () => {
      this.freezeSystem();
    });
    
    document.getElementById('btn-unfreeze').addEventListener('click', () => {
      this.unfreezeSystem();
    });
    
    document.getElementById('btn-approve').addEventListener('click', () => {
      this.showApprovalModal();
    });
    
    document.getElementById('btn-reject').addEventListener('click', () => {
      this.rejectDecision();
    });
    
    // Modal events
    document.getElementById('modal-close').addEventListener('click', () => {
      this.hideApprovalModal();
    });
    
    document.getElementById('modal-cancel').addEventListener('click', () => {
      this.hideApprovalModal();
    });
    
    document.getElementById('modal-approve').addEventListener('click', () => {
      this.approveDecision();
    });
    
    document.getElementById('modal-reject').addEventListener('click', () => {
      this.rejectDecision();
      this.hideApprovalModal();
    });
  }
  
  togglePanel() {
    const content = document.getElementById('governance-content');
    const icon = document.querySelector('.toggle-icon');
    
    this.isVisible = !this.isVisible;
    content.style.display = this.isVisible ? 'block' : 'none';
    icon.textContent = this.isVisible ? '▼' : '▲';
    
    // Save state
    localStorage.setItem('governance_panel_visible', this.isVisible.toString());
  }
  
  async refreshState() {
    try {
      const refreshBtn = document.getElementById('btn-refresh');
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '⏳ Refreshing...';
      
      // Sync governance state
      await store.syncGovernanceState();
      await store.syncMLSignals();
      
      // Update UI
      this.updateDisplay();
      
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '🔄 Refresh';
      
    } catch (error) {
      console.error('Failed to refresh governance state:', error);
      this.showNotification('Failed to refresh state', 'error');
    }
  }
  
  updateDisplay() {
    const governanceStatus = store.getGovernanceStatus();
    const governance = store.get('governance');
    const mlSignals = store.get('governance.ml_signals');
    
    // Update status badges
    const stateEl = document.getElementById('gov-state');
    stateEl.textContent = governanceStatus.state;
    stateEl.className = `status-badge ${this.getStateClass(governanceStatus.state)}`;
    
    document.getElementById('gov-mode').textContent = governanceStatus.mode;
    
    // Update mode selector
    const modeSelect = document.getElementById('governance-mode-select');
    if (modeSelect) {
      modeSelect.value = governanceStatus.mode === 'freeze' ? 'manual' : governanceStatus.mode;
    }
    
    // Update policy info from active_policy
    const activePolicy = governance?.active_policy;
    if (activePolicy) {
      const capPercent = Math.round(activePolicy.cap_daily * 100);
      document.getElementById('gov-policy').textContent = `${activePolicy.mode} ${capPercent}%`;
    } else {
      document.getElementById('gov-policy').textContent = 'Normal 8%';
    }
    
    // Update contradiction index
    const contradiction = governance?.contradiction_index || 0;
    const contradictionEl = document.getElementById('gov-contradiction');
    contradictionEl.textContent = `${Math.round(contradiction * 100)}%`;
    contradictionEl.className = `contradiction-meter ${this.getContradictionClass(contradiction)}`;
    
    // Update ML signals
    if (mlSignals) {
      this.updateMLSignals(mlSignals);
    }
    
    // Update freeze/unfreeze buttons
    const freezeBtn = document.getElementById('btn-freeze');
    const unfreezeBtn = document.getElementById('btn-unfreeze');
    
    // Check if system is frozen based on governance mode
    const isFrozen = governanceStatus.mode === 'freeze';
    if (isFrozen) {
      freezeBtn.disabled = true;
      unfreezeBtn.disabled = false;
    } else {
      freezeBtn.disabled = false;
      unfreezeBtn.disabled = true;
    }
    
    // Show/hide pending decision section
    this.updatePendingDecision(governanceStatus);
  }
  
  updateMLSignals(signals) {
    // Update confidence bar
    const confidence = signals.confidence || 0;
    const confidenceFill = document.getElementById('confidence-fill');
    const confidenceValue = document.getElementById('confidence-value');
    
    confidenceFill.style.width = `${confidence * 100}%`;
    confidenceFill.className = `signal-fill ${this.getConfidenceClass(confidence)}`;
    confidenceValue.textContent = `${Math.round(confidence * 100)}%`;
    
    // Update decision score bar
    const decisionScore = signals.decision_score || 0;
    const decisionFill = document.getElementById('decision-fill');
    const decisionValue = document.getElementById('decision-value');
    
    decisionFill.style.width = `${decisionScore * 100}%`;
    decisionFill.className = `signal-fill ${this.getDecisionClass(decisionScore)}`;
    decisionValue.textContent = `${Math.round(decisionScore * 100)}%`;
  }
  
  updatePendingDecision(governanceStatus) {
    const pendingSection = document.getElementById('pending-decision');
    
    if (governanceStatus.state === 'DRAFT') {
      pendingSection.style.display = 'block';
      const summary = document.getElementById('decision-summary');
      summary.innerHTML = `
        <div class="decision-preview">
          <p><strong>Proposed Decision:</strong> New allocation targets available</p>
          <p><strong>Confidence:</strong> ${governanceStatus.confidence || 'N/A'}</p>
          <p><strong>Contradiction:</strong> ${governanceStatus.contradiction_level || 'Low'}</p>
          <p><strong>Recommended Action:</strong> Review and approve if confident</p>
        </div>
      `;
    } else {
      pendingSection.style.display = 'none';
    }
  }
  
  async freezeSystem() {
    try {
      const result = await store.freezeSystem('Manual freeze from UI');
      if (result) {
        this.showNotification('System frozen successfully', 'success');
        this.refreshState();
      } else {
        this.showNotification('Failed to freeze system', 'error');
      }
    } catch (error) {
      console.error('Freeze system error:', error);
      this.showNotification('Error freezing system', 'error');
    }
  }
  
  async unfreezeSystem() {
    try {
      const result = await store.unfreezeSystem();
      if (result) {
        this.showNotification('System unfrozen successfully', 'success');
        this.refreshState();
      } else {
        this.showNotification('Failed to unfreeze system', 'error');
      }
    } catch (error) {
      console.error('Unfreeze system error:', error);
      this.showNotification('Error unfreezing system', 'error');
    }
  }

  async changeGovernanceMode() {
    try {
      const modeSelect = document.getElementById('governance-mode-select');
      const selectedMode = modeSelect.value;
      const currentMode = store.getGovernanceStatus().mode;
      
      if (selectedMode === currentMode) {
        this.showNotification('Mode already set to ' + selectedMode, 'warning');
        return;
      }

      const btn = document.getElementById('btn-change-mode');
      btn.disabled = true;
      btn.textContent = 'Changing...';

      const result = await store.setGovernanceMode(selectedMode, `Mode change: ${currentMode} → ${selectedMode}`);
      if (result) {
        this.showNotification(`Mode changed to ${selectedMode}`, 'success');
        this.refreshState();
      } else {
        this.showNotification('Failed to change mode', 'error');
      }

      btn.disabled = false;
      btn.textContent = 'Change Mode';
      
    } catch (error) {
      console.error('Change mode error:', error);
      this.showNotification('Error changing mode', 'error');
    }
  }

  async proposeDecision() {
    try {
      const btn = document.getElementById('btn-propose');
      btn.disabled = true;
      btn.textContent = 'Proposing...';

      const currentMode = store.getGovernanceStatus().mode;
      const reason = `Test proposal in ${currentMode} mode`;
      
      const result = await store.proposeDecision(null, reason);
      if (result) {
        this.showNotification('Decision proposed successfully', 'success');
        this.refreshState();
      } else {
        this.showNotification('Failed to propose decision', 'error');
      }

      btn.disabled = false;
      btn.textContent = '📋 Propose';
      
    } catch (error) {
      console.error('Propose decision error:', error);
      this.showNotification('Error proposing decision', 'error');
    }
  }
  
  showApprovalModal() {
    const modal = document.getElementById('approval-modal');
    const modalBody = document.getElementById('modal-body');
    
    const governance = store.get('governance');
    const mlSignals = store.get('governance.ml_signals');
    
    modalBody.innerHTML = `
      <div class="approval-details">
        <div class="detail-section">
          <h4>📊 Decision Summary</h4>
          <p>The system has proposed a new allocation strategy based on current ML signals.</p>
        </div>
        
        <div class="detail-section">
          <h4>🧠 ML Analysis</h4>
          <table class="details-table">
            <tr>
              <td>Confidence Level:</td>
              <td><strong>${Math.round((mlSignals?.confidence || 0) * 100)}%</strong></td>
            </tr>
            <tr>
              <td>Decision Score:</td>
              <td><strong>${Math.round((mlSignals?.decision_score || 0) * 100)}%</strong></td>
            </tr>
            <tr>
              <td>Contradiction Index:</td>
              <td><strong>${Math.round((governance?.contradiction_index || 0) * 100)}%</strong></td>
            </tr>
            <tr>
              <td>Market Regime:</td>
              <td><strong>${this.getRegimeSummary(mlSignals)}</strong></td>
            </tr>
          </table>
        </div>
        
        <div class="detail-section">
          <h4>⚙️ Execution Policy</h4>
          <table class="details-table">
            <tr>
              <td>Mode:</td>
              <td><strong>${governance?.mode || 'manual'}</strong></td>
            </tr>
            <tr>
              <td>State:</td>
              <td><strong>${governance?.current_state || 'IDLE'}</strong></td>
            </tr>
            <tr>
              <td>Contradiction:</td>
              <td><strong>${Math.round((governance?.contradiction_index || 0) * 100)}%</strong></td>
            </tr>
          </table>
        </div>
        
        <div class="detail-section warning">
          <h4>⚠️ Important Notes</h4>
          <ul>
            <li>This decision will override current allocation targets</li>
            <li>Execution will follow the policy constraints above</li>
            <li>You can freeze the system anytime to stop execution</li>
          </ul>
        </div>
      </div>
    `;
    
    modal.style.display = 'flex';
  }
  
  hideApprovalModal() {
    document.getElementById('approval-modal').style.display = 'none';
  }
  
  async approveDecision() {
    try {
      const decisionId = store.get('governance.last_decision_id') || 'current';
      const result = await store.approveDecision(decisionId, true, 'Approved from UI');
      if (result) {
        this.showNotification('Decision approved successfully', 'success');
        this.hideApprovalModal();
        this.refreshState();
      } else {
        this.showNotification('Failed to approve decision', 'error');
      }
    } catch (error) {
      console.error('Approve decision error:', error);
      this.showNotification('Error approving decision', 'error');
    }
  }
  
  async rejectDecision() {
    try {
      // For now, we'll just reset to manual mode
      // In a full implementation, this would call a reject endpoint
      this.showNotification('Decision rejected (feature in development)', 'warning');
    } catch (error) {
      console.error('Reject decision error:', error);
      this.showNotification('Error rejecting decision', 'error');
    }
  }
  
  startAutoRefresh() {
    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(() => {
      if (this.isVisible) {
        this.refreshState();
      }
    }, 30000);
  }
  
  destroy() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }
  
  // Helper methods for styling
  getStateClass(state) {
    switch (state) {
      case 'ACTIVE': return 'success';
      case 'DRAFT': return 'warning';
      case 'FROZEN': return 'danger';
      default: return 'secondary';
    }
  }
  
  getContradictionClass(level) {
    if (level > 0.7) return 'high';
    if (level > 0.4) return 'medium';
    return 'low';
  }
  
  getConfidenceClass(confidence) {
    if (confidence > 0.8) return 'excellent';
    if (confidence > 0.6) return 'good';
    if (confidence > 0.4) return 'fair';
    return 'poor';
  }
  
  getDecisionClass(score) {
    if (score > 0.7) return 'strong';
    if (score > 0.5) return 'moderate';
    return 'weak';
  }
  
  getRegimeSummary(signals) {
    if (!signals?.regime) return 'Unknown';
    
    const regime = signals.regime;
    const maxRegime = Object.keys(regime).reduce((a, b) => 
      regime[a] > regime[b] ? a : b
    );
    
    return maxRegime.charAt(0).toUpperCase() + maxRegime.slice(1);
  }
  
  showNotification(message, type = 'info') {
    // Simple notification system
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 16px;
      border-radius: 4px;
      z-index: 10000;
      max-width: 300px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    `;
    
    // Type-specific styling
    switch (type) {
      case 'success':
        notification.style.backgroundColor = '#d4edda';
        notification.style.color = '#155724';
        break;
      case 'error':
        notification.style.backgroundColor = '#f8d7da';
        notification.style.color = '#721c24';
        break;
      case 'warning':
        notification.style.backgroundColor = '#fff3cd';
        notification.style.color = '#856404';
        break;
      default:
        notification.style.backgroundColor = '#d1ecf1';
        notification.style.color = '#0c5460';
    }
    
    document.body.appendChild(notification);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 3000);
  }
}

export { GovernancePanel };