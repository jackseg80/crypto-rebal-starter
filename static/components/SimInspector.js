/**
 * SimInspector - Arbre d'explication pas-à-pas du pipeline de simulation
 * Affiche la hiérarchie avant→après avec deltas et résumé en langage naturel
 */

console.debug('🔍 SIM: SimInspector loaded');

export class SimInspector {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.currentData = null;
    this.expanded = new Set(['root', 'di', 'riskBudget']); // Nœuds étendus par défaut

    this.init();
  }

  init() {
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="sim-inspector-wrapper">
        <div class="inspector-header">
          <h3>🔍 Pipeline Inspector</h3>
          <div class="inspector-controls">
            <button id="expand-all" class="btn secondary">📂 Tout étendre</button>
            <button id="collapse-all" class="btn secondary">📁 Tout réduire</button>
            <button id="export-log" class="btn secondary">📋 Export Log</button>
          </div>
        </div>

        <div class="inspector-content">
          <div id="pipeline-tree" class="pipeline-tree">
            <div class="empty-state">
              <div class="empty-icon">🎭</div>
              <p>Aucune simulation en cours</p>
              <small>Ajustez les contrôles pour voir le pipeline s'exécuter</small>
            </div>
          </div>

          <div id="natural-language" class="natural-language">
            <h4>📝 Résumé</h4>
            <div class="summary-content">
              <p class="empty-summary">En attente de simulation...</p>
            </div>
          </div>

          <div id="delta-comparison" class="delta-comparison">
            <h4>🔄 Comparaison Avant/Après</h4>
            <div class="delta-content">
              <!-- Sera rempli dynamiquement -->
            </div>
          </div>
        </div>
      </div>
    `;

    this.attachEventListeners();
  }

  attachEventListeners() {
    // Expand/Collapse controls
    document.getElementById('expand-all')?.addEventListener('click', () => {
      this.expandAll();
    });

    document.getElementById('collapse-all')?.addEventListener('click', () => {
      this.collapseAll();
    });

    document.getElementById('export-log')?.addEventListener('click', () => {
      this.exportLog();
    });

    // Tree node clicks (delegation)
    document.getElementById('pipeline-tree')?.addEventListener('click', (e) => {
      const nodeHeader = e.target.closest('.tree-node-header');
      if (nodeHeader) {
        const nodeId = nodeHeader.dataset.nodeId;
        this.toggleNode(nodeId);
      }
    });
  }

  updateInspector(simulationResult) {
    console.debug('🔍 SIM: updateInspector called');

    this.currentData = simulationResult;
    this.renderPipelineTree(simulationResult.explanation.explainTree);
    this.renderNaturalLanguage(simulationResult.explanation.summaryNL);
    this.renderDeltaComparison(simulationResult);
  }

  renderPipelineTree(explainTree) {
    const treeContainer = document.getElementById('pipeline-tree');
    if (!treeContainer || !explainTree) return;

    const treeHTML = this.renderTreeNode(explainTree.root, 'root', 0);
    treeContainer.innerHTML = treeHTML;
  }

  renderTreeNode(node, nodeId, depth) {
    if (!node) return '';

    const isExpanded = this.expanded.has(nodeId);
    const hasChildren = node.children && Object.keys(node.children).length > 0;

    const statusIcon = this.getStatusIcon(node.status);
    const indentClass = `depth-${Math.min(depth, 3)}`;

    let html = `
      <div class="tree-node ${indentClass}" data-node-id="${nodeId}">
        <div class="tree-node-header" data-node-id="${nodeId}">
          ${hasChildren ?
            `<span class="tree-toggle">${isExpanded ? '📂' : '📁'}</span>` :
            '<span class="tree-leaf">📄</span>'
          }
          <span class="tree-status">${statusIcon}</span>
          <span class="tree-label">${node.label}</span>
        </div>
    `;

    // Data section si présente
    if (node.data) {
      html += `<div class="tree-data">${this.renderNodeData(node.data, node.status)}</div>`;
    }

    // Children si étendus
    if (hasChildren && isExpanded) {
      html += '<div class="tree-children">';
      for (const [childId, child] of Object.entries(node.children)) {
        if (child) { // Skip null children
          html += this.renderTreeNode(child, childId, depth + 1);
        }
      }
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  renderNodeData(data, status) {
    if (!data || typeof data !== 'object') return '';

    let html = '<div class="node-data-grid">';

    for (const [key, value] of Object.entries(data)) {
      const formattedKey = key.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').toLowerCase();
      const formattedValue = this.formatValue(value);

      html += `
        <div class="data-item">
          <span class="data-key">${formattedKey}:</span>
          <span class="data-value">${formattedValue}</span>
        </div>
      `;
    }

    html += '</div>';
    return html;
  }

  formatValue(value) {
    if (typeof value === 'number') {
      return Number.isInteger(value) ? value.toString() : value.toFixed(2);
    }

    if (typeof value === 'boolean') {
      return value ? '✅' : '❌';
    }

    if (Array.isArray(value)) {
      return value.length > 0 ? `[${value.length} items]` : '[]';
    }

    if (typeof value === 'object' && value !== null) {
      // Pour les objets complexes, afficher les clés principales
      const keys = Object.keys(value);
      if (keys.length <= 3) {
        return keys.map(k => `${k}: ${this.formatValue(value[k])}`).join(', ');
      }
      return `{${keys.length} properties}`;
    }

    return String(value);
  }

  getStatusIcon(status) {
    const icons = {
      'completed': '✅',
      'warning': '⚠️',
      'error': '❌',
      'action': '🎯',
      'idle': '⭕',
      'in_progress': '🔄'
    };
    return icons[status] || '📋';
  }

  renderNaturalLanguage(summaryNL) {
    const container = document.querySelector('.summary-content');
    if (!container) return;

    if (summaryNL) {
      container.innerHTML = `<p class="summary-text">${summaryNL}</p>`;
    } else {
      container.innerHTML = '<p class="empty-summary">Résumé non disponible</p>';
    }
  }

  renderDeltaComparison(simulationResult) {
    const container = document.querySelector('.delta-content');
    if (!container || !simulationResult) return;

    const { targets, finalTargets, cappedTargets, orders } = simulationResult;

    // Comparaison des targets
    const targetComparison = this.createTargetComparison(targets, cappedTargets);

    // Ordres d'exécution
    const ordersSummary = this.createOrdersSummary(orders);

    container.innerHTML = `
      <div class="comparison-sections">
        <div class="comparison-section">
          <h5>🎯 Évolution des Targets</h5>
          ${targetComparison}
        </div>

        <div class="comparison-section">
          <h5>⚡ Plan d'Exécution</h5>
          ${ordersSummary}
        </div>
      </div>
    `;
  }

  createTargetComparison(initialTargets, finalTargets) {
    if (!initialTargets || !finalTargets) {
      return '<p class="no-data">Données de comparaison non disponibles</p>';
    }

    let html = '<div class="targets-comparison">';

    // Combiner toutes les clés
    const allGroups = new Set([...Object.keys(initialTargets), ...Object.keys(finalTargets)]);

    for (const group of allGroups) {
      const initial = initialTargets[group] || 0;
      const final = finalTargets[group] || 0;
      const delta = final - initial;
      const deltaClass = delta > 0.1 ? 'positive' : delta < -0.1 ? 'negative' : 'neutral';
      const deltaIcon = delta > 0.1 ? '📈' : delta < -0.1 ? '📉' : '➖';

      html += `
        <div class="target-comparison-row">
          <span class="group-name">${group}</span>
          <span class="initial-value">${initial.toFixed(1)}%</span>
          <span class="arrow">→</span>
          <span class="final-value">${final.toFixed(1)}%</span>
          <span class="delta ${deltaClass}">
            ${deltaIcon} ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%
          </span>
        </div>
      `;
    }

    html += '</div>';
    return html;
  }

  createOrdersSummary(orders) {
    if (!orders || !orders.orders) {
      return '<p class="no-data">Aucune donnée d\'exécution</p>';
    }

    const { summary, orders: ordersList } = orders;

    let html = `
      <div class="execution-summary">
        <div class="summary-stats">
          <div class="stat-item">
            <span class="stat-label">Delta Total:</span>
            <span class="stat-value">${summary.totalDelta}%</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Seuil:</span>
            <span class="stat-value">${summary.globalThreshold}%</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Statut:</span>
            <span class="stat-value ${summary.shouldExecute ? 'execute' : 'idle'}">
              ${summary.shouldExecute ? '🟢 Exécuter' : '🔴 Attendre'}
            </span>
          </div>
        </div>
      </div>
    `;

    if (ordersList.length > 0) {
      html += '<div class="orders-list">';
      ordersList.forEach((order, index) => {
        const actionIcon = order.action === 'BUY' ? '🟢' : '🔴';
        const priorityClass = order.priority === 'HIGH' ? 'high-priority' : 'normal-priority';

        html += `
          <div class="order-item ${priorityClass}">
            <span class="order-action">${actionIcon} ${order.action}</span>
            <span class="order-group">${order.group}</span>
            <span class="order-delta">${order.deltaPct > 0 ? '+' : ''}${order.deltaPct}%</span>
            <span class="order-amount">${order.estimatedLot}€</span>
          </div>
        `;
      });
      html += '</div>';
    } else if (summary.shouldExecute) {
      html += '<p class="no-orders">Aucun ordre généré (seuils non atteints)</p>';
    }

    return html;
  }

  toggleNode(nodeId) {
    if (this.expanded.has(nodeId)) {
      this.expanded.delete(nodeId);
    } else {
      this.expanded.add(nodeId);
    }

    // Re-render only the tree part
    if (this.currentData) {
      this.renderPipelineTree(this.currentData.explanation.explainTree);
    }
  }

  expandAll() {
    // Trouver tous les nœuds avec enfants et les étendre
    const allNodes = document.querySelectorAll('.tree-node[data-node-id]');
    allNodes.forEach(node => {
      const nodeId = node.dataset.nodeId;
      const hasChildren = node.querySelector('.tree-children') ||
                         node.querySelector('.tree-toggle');
      if (hasChildren) {
        this.expanded.add(nodeId);
      }
    });

    if (this.currentData) {
      this.renderPipelineTree(this.currentData.explanation.explainTree);
    }
  }

  collapseAll() {
    this.expanded.clear();
    this.expanded.add('root'); // Garder la racine

    if (this.currentData) {
      this.renderPipelineTree(this.currentData.explanation.explainTree);
    }
  }

  exportLog() {
    if (!this.currentData) {
      alert('Aucune donnée de simulation à exporter');
      return;
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const logData = {
      timestamp: this.currentData.timestamp,
      export_time: new Date().toISOString(),
      pipeline_data: this.currentData,
      summary: this.currentData.explanation.summaryNL
    };

    const dataStr = JSON.stringify(logData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `simulation_log_${timestamp}.json`;
    a.click();

    URL.revokeObjectURL(url);
  }

  clear() {
    this.currentData = null;
    this.expanded.clear();
    this.expanded.add('root');

    const treeContainer = document.getElementById('pipeline-tree');
    if (treeContainer) {
      treeContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🎭</div>
          <p>Aucune simulation en cours</p>
          <small>Ajustez les contrôles pour voir le pipeline s'exécuter</small>
        </div>
      `;
    }

    const summaryContainer = document.querySelector('.summary-content');
    if (summaryContainer) {
      summaryContainer.innerHTML = '<p class="empty-summary">En attente de simulation...</p>';
    }

    const deltaContainer = document.querySelector('.delta-content');
    if (deltaContainer) {
      deltaContainer.innerHTML = '';
    }
  }
}

// CSS pour l'inspecteur (injecté dynamiquement)
const inspectorCSS = `
  .sim-inspector-wrapper {
    background: var(--theme-surface);
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    max-height: 80vh;
    overflow-y: auto;
  }

  .inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-md);
    padding-bottom: var(--space-sm);
    border-bottom: 1px solid var(--theme-border);
  }

  .inspector-controls {
    display: flex;
    gap: var(--space-xs);
  }

  .inspector-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
  }

  .pipeline-tree {
    background: var(--theme-bg);
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-md);
    padding: var(--space-md);
    min-height: 200px;
  }

  .tree-node {
    margin-bottom: var(--space-xs);
  }

  .tree-node-header {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-xs) var(--space-sm);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background-color 0.2s;
    user-select: none;
  }

  .tree-node-header:hover {
    background: var(--theme-surface);
  }

  .depth-0 .tree-node-header {
    font-weight: 600;
    font-size: 1rem;
    background: var(--theme-surface);
  }

  .depth-1 .tree-node-header {
    margin-left: var(--space-md);
    font-weight: 500;
  }

  .depth-2 .tree-node-header {
    margin-left: calc(var(--space-md) * 2);
    font-size: 0.9rem;
  }

  .depth-3 .tree-node-header {
    margin-left: calc(var(--space-md) * 3);
    font-size: 0.85rem;
    opacity: 0.9;
  }

  .tree-toggle, .tree-leaf {
    font-size: 0.9rem;
    min-width: 1.2rem;
  }

  .tree-status {
    font-size: 1rem;
  }

  .tree-label {
    flex: 1;
    color: var(--theme-text);
  }

  .tree-data {
    margin-left: calc(var(--space-md) * 2);
    margin-top: var(--space-xs);
    padding: var(--space-sm);
    background: var(--theme-surface);
    border-radius: var(--radius-sm);
    border: 1px solid var(--theme-border);
  }

  .node-data-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-xs);
    font-size: 0.85rem;
  }

  .data-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .data-key {
    color: var(--theme-text-muted);
    text-transform: capitalize;
  }

  .data-value {
    font-family: monospace;
    font-weight: 500;
    color: var(--theme-text);
  }

  .tree-children {
    margin-left: var(--space-sm);
    border-left: 2px solid var(--theme-border);
    padding-left: var(--space-sm);
  }

  .empty-state {
    text-align: center;
    padding: var(--space-xl);
    color: var(--theme-text-muted);
  }

  .empty-icon {
    font-size: 3rem;
    margin-bottom: var(--space-md);
  }

  .natural-language {
    background: var(--theme-bg);
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-md);
    padding: var(--space-md);
  }

  .natural-language h4 {
    margin: 0 0 var(--space-sm) 0;
    color: var(--theme-text);
  }

  .summary-text {
    line-height: 1.6;
    color: var(--theme-text);
    margin: 0;
  }

  .empty-summary {
    color: var(--theme-text-muted);
    font-style: italic;
    margin: 0;
  }

  .delta-comparison {
    background: var(--theme-bg);
    border: 1px solid var(--theme-border);
    border-radius: var(--radius-md);
    padding: var(--space-md);
  }

  .delta-comparison h4 {
    margin: 0 0 var(--space-sm) 0;
    color: var(--theme-text);
  }

  .comparison-sections {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-lg);
  }

  .comparison-section h5 {
    margin: 0 0 var(--space-sm) 0;
    color: var(--theme-text);
    font-size: 0.9rem;
  }

  .targets-comparison {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .target-comparison-row {
    display: grid;
    grid-template-columns: 1fr auto auto auto auto;
    gap: var(--space-sm);
    align-items: center;
    padding: var(--space-xs);
    border-radius: var(--radius-sm);
    background: var(--theme-surface);
    font-size: 0.85rem;
  }

  .group-name {
    font-weight: 500;
    color: var(--theme-text);
  }

  .initial-value, .final-value {
    font-family: monospace;
    text-align: right;
  }

  .arrow {
    color: var(--theme-text-muted);
  }

  .delta {
    font-family: monospace;
    font-weight: 600;
    text-align: right;
  }

  .delta.positive {
    color: var(--success);
  }

  .delta.negative {
    color: var(--danger);
  }

  .delta.neutral {
    color: var(--theme-text-muted);
  }

  .execution-summary {
    margin-bottom: var(--space-md);
  }

  .summary-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    padding: var(--space-sm);
    background: var(--theme-surface);
    border-radius: var(--radius-sm);
    text-align: center;
  }

  .stat-label {
    font-size: 0.8rem;
    color: var(--theme-text-muted);
  }

  .stat-value {
    font-family: monospace;
    font-weight: 600;
    color: var(--theme-text);
  }

  .stat-value.execute {
    color: var(--success);
  }

  .stat-value.idle {
    color: var(--warning);
  }

  .orders-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .order-item {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    gap: var(--space-sm);
    align-items: center;
    padding: var(--space-xs) var(--space-sm);
    background: var(--theme-surface);
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
  }

  .order-item.high-priority {
    border-left: 3px solid var(--danger);
  }

  .order-action {
    font-weight: 600;
  }

  .order-group {
    color: var(--theme-text);
  }

  .order-delta, .order-amount {
    font-family: monospace;
    text-align: right;
  }

  .no-data, .no-orders {
    color: var(--theme-text-muted);
    font-style: italic;
    text-align: center;
    padding: var(--space-md);
  }

  @media (max-width: 768px) {
    .inspector-header {
      flex-direction: column;
      gap: var(--space-sm);
      align-items: stretch;
    }

    .inspector-controls {
      justify-content: center;
    }

    .comparison-sections {
      grid-template-columns: 1fr;
    }

    .node-data-grid {
      grid-template-columns: 1fr;
    }

    .target-comparison-row {
      grid-template-columns: 1fr;
      text-align: center;
    }

    .summary-stats {
      grid-template-columns: 1fr;
    }
  }
`;

// Injecter le CSS
if (!document.getElementById('sim-inspector-css')) {
  const style = document.createElement('style');
  style.id = 'sim-inspector-css';
  style.textContent = inspectorCSS;
  document.head.appendChild(style);
}