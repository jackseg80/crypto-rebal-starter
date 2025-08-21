/**
 * Module de navigation partagé pour toutes les pages
 * Injecte automatiquement le header unifié avec la navigation
 */

function createSharedHeader(activePageId, showConfigIndicators = false) {
  const pages = {
    'dashboard': { title: '💎 Portfolio Analytics', url: 'dashboard.html', icon: '📊' },
    'rebalance': { title: '⚖️ Crypto Rebalancer', url: 'rebalance.html', icon: '⚖️' },
    'alias-manager': { title: '🏷️ Alias Manager', url: 'alias-manager.html', icon: '🏷️' },
    'settings': { title: '⚙️ Configuration', url: 'settings.html', icon: '⚙️' }
  };
  
  const activePage = pages[activePageId];
  const title = activePage ? activePage.title : '🚀 Crypto Rebalancer';
  
  // Navigation links avec gestion de l'état Alias Manager
  const navLinks = Object.entries(pages).map(([pageId, page]) => {
    const isActive = pageId === activePageId;
    let linkClass = isActive ? 'active' : '';
    let linkContent = `${page.icon} ${page.title.replace(/[💎⚖️🏷️⚙️]\s*/, '')}`;
    
    // Logique spéciale pour Alias Manager
    if (pageId === 'alias-manager') {
      const hasPlan = window.globalConfig?.hasPlan() || false;
      const unknownCount = window.globalConfig?.getUnknownAliasesCount() || 0;
      
      if (!hasPlan) {
        linkClass += ' disabled';
        linkContent += ' (Générez un plan d\'abord)';
        return `<span class="${linkClass}" title="Générez d'abord un plan de rebalancing pour activer cette fonctionnalité">${linkContent}</span>`;
      } else if (unknownCount > 0) {
        linkContent += ` (${unknownCount})`;
        linkClass += ' has-badge';
      }
    }
    
    return `<a href="${page.url}" class="${linkClass}">${linkContent}</a>`;
  }).join('');
  
  // Configuration indicators (pour dashboard principalement)
  let configIndicators = '';
  if (showConfigIndicators && window.globalConfig) {
    const sourceLabels = {
      'stub': '🧪 Démo',
      'cointracking': '📄 CSV',
      'cointracking_api': '🌐 API'
    };
    
    const pricingLabels = {
      'local': '🏠 Local',
      'auto': '🚀 Auto'
    };
    
    const currentSource = window.globalConfig?.get('data_source') || 'cointracking';
    const currentPricing = window.globalConfig?.get('pricing') || 'local';
    
    configIndicators = `
      <div style="font-size: 12px; color: var(--muted); margin-top: 8px;">
        <span>Source: <span style="color: var(--accent);" id="current-source">${sourceLabels[currentSource] || 'Inconnu'}</span></span>
        <span style="margin-left: 16px;">Pricing: <span style="color: var(--accent);" id="current-pricing">${pricingLabels[currentPricing] || 'Inconnu'}</span></span>
      </div>
    `;
  }
  
  return `
    <header>
      <div class="wrap">
        <h1>${title}</h1>
        <nav class="nav">
          ${navLinks}
        </nav>
        ${configIndicators}
      </div>
    </header>
  `;
}

// CSS partagé pour la navigation
const SHARED_NAV_CSS = `
  .nav{display:flex;gap:12px;margin:12px 0;flex-wrap:wrap}
  .nav a{padding:8px 16px;border-radius:8px;text-decoration:none;color:var(--muted);border:1px solid var(--border);transition:all 0.2s}
  .nav a.active, .nav a:hover{background:var(--accent);color:#07211e;border-color:var(--accent)}
  
  /* Style pour Alias Manager désactivé */
  .nav span.disabled{
    padding:8px 16px;border-radius:8px;color:#4a5568;border:1px dashed #2d3748;
    cursor:not-allowed;font-style:italic;opacity:0.6;
  }
  
  /* Style pour badge avec count */
  .nav a.has-badge{
    background:#1a202c;border-color:#f59e0b;color:#f59e0b;
    animation:pulse 2s infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
  
  @media(max-width: 768px){
    .nav{gap:8px}
    .nav a, .nav span{padding:6px 12px;font-size:12px}
  }
`;

// Fonction d'initialisation pour injecter le header
function initSharedHeader(activePageId, options = {}) {
  // Injecter le CSS s'il n'existe pas déjà
  if (!document.getElementById('shared-nav-styles')) {
    const style = document.createElement('style');
    style.id = 'shared-nav-styles';
    style.textContent = SHARED_NAV_CSS;
    document.head.appendChild(style);
  }
  
  // Remplacer le header existant ou l'injecter au début du body
  const existingHeader = document.querySelector('header');
  const headerHTML = createSharedHeader(activePageId, options.showConfigIndicators);
  
  if (existingHeader) {
    existingHeader.outerHTML = headerHTML;
  } else {
    document.body.insertAdjacentHTML('afterbegin', headerHTML);
  }
  
  // Écouter les changements de configuration pour mettre à jour les indicateurs
  if (options.showConfigIndicators && window.globalConfig) {
    window.addEventListener('configChanged', () => {
      updateConfigIndicators();
    });
  }
  
  // Écouter les événements de génération de plan pour rafraîchir la navigation
  window.addEventListener('planGenerated', () => {
    refreshNavigation(activePageId, options);
  });
  
  window.addEventListener('planReset', () => {
    refreshNavigation(activePageId, options);
  });
}

// Fonction pour rafraîchir dynamiquement la navigation
function refreshNavigation(activePageId, options = {}) {
  const existingHeader = document.querySelector('header');
  if (existingHeader) {
    const headerHTML = createSharedHeader(activePageId, options.showConfigIndicators);
    existingHeader.outerHTML = headerHTML;
  }
}

// Mise à jour des indicateurs de configuration
function updateConfigIndicators() {
  if (!window.globalConfig) return;
  
  const sourceLabels = {
    'stub': '🧪 Démo',
    'cointracking': '📄 CSV',
    'cointracking_api': '🌐 API'
  };
  
  const pricingLabels = {
    'local': '🏠 Local',
    'auto': '🚀 Auto'
  };
  
  const sourceEl = document.getElementById('current-source');
  const pricingEl = document.getElementById('current-pricing');
  
  if (sourceEl) {
    sourceEl.textContent = sourceLabels[globalConfig.get('data_source')] || 'Inconnu';
  }
  if (pricingEl) {
    pricingEl.textContent = pricingLabels[globalConfig.get('pricing')] || 'Inconnu';
  }
}

// Export pour utilisation
window.initSharedHeader = initSharedHeader;
window.updateConfigIndicators = updateConfigIndicators;