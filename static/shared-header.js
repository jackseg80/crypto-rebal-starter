/**
 * Module de navigation partagé pour toutes les pages
 * Injecte automatiquement le header unifié avec la navigation
 */

function createSharedHeader(activePageId, showConfigIndicators = false) {
  // Section 1: Analytics & Decision Making (Interface Business)
  const analyticsPages = {
    'dashboard': { title: '📊 Dashboard', url: 'dashboard.html', icon: '📊' },
    'risk-dashboard': { title: '🛡️ Risk Dashboard', url: 'risk-dashboard.html', icon: '🛡️' },
    'rebalance': { title: '⚖️ Rebalance', url: 'rebalance.html', icon: '⚖️' },
    'alias-manager': { title: '🏷️ Aliases', url: 'alias-manager.html', icon: '🏷️' }
  };

  // Section 2: Execution Engine & Diagnostics (Interface Technique)
  const enginePages = {
    'execution': { title: '🚀 Execute', url: 'execution.html', icon: '🚀' },
    'execution-history': { title: '📈 History', url: 'execution_history.html', icon: '📈' },
    'monitoring-unified': { title: '📊 Monitor', url: 'monitoring-unified.html', icon: '📊' }
  };

  // Section 3: Configuration (Settings à droite)
  const configPages = {
    'settings': { title: '⚙️ Settings', url: 'settings.html', icon: '⚙️' }
  };

  const allPages = { ...analyticsPages, ...enginePages };
  const activePage = allPages[activePageId];
  const title = activePage ? activePage.title : '🚀 Crypto Rebalancer';

  // Fonction pour créer les liens d'une section
  const createSectionLinks = (pages, sectionClass = '') => {
    return Object.entries(pages).map(([pageId, page]) => {
      const isActive = pageId === activePageId;
      let linkClass = `nav-link ${sectionClass}`;
      if (isActive) linkClass += ' active';

      let linkContent = `${page.icon} ${page.title.replace(/[^\w\s]/gu, '').trim()}`;

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
  };

  // Créer les sections de navigation
  const analyticsLinks = createSectionLinks(analyticsPages, 'section-analytics');
  const engineLinks = createSectionLinks(enginePages, 'section-engine');
  const configLinks = createSectionLinks(configPages, 'section-config');

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
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h1>${title}</h1>
          <div class="theme-toggle" onclick="toggleTheme()">
            <div class="theme-toggle-icon" id="light-icon">☀️</div>
            <div class="theme-toggle-icon" id="dark-icon">🌙</div>
          </div>
        </div>
        <nav class="nav">
          <div class="nav-section analytics-section">
            <div class="section-links">
              ${analyticsLinks}
            </div>
          </div>
          <div class="nav-separator">|</div>
          <div class="nav-section engine-section">
            <div class="section-links">
              ${engineLinks}
            </div>
          </div>
          <div class="nav-separator">|</div>
          <div class="nav-section config-section">
            <div class="section-links">
              ${configLinks}
            </div>
          </div>
        </nav>
        ${configIndicators}
      </div>
    </header>
  `;
}

// CSS partagé pour la navigation tri-section
const SHARED_NAV_CSS = `
  .nav{
    display:flex;
    gap:12px;
    margin:12px 0;
    flex-wrap:wrap;
    align-items:center;
    justify-content:space-between;
  }
  
  /* Structure des sections */
  .nav-section{
    display:flex;
    align-items:center;
    gap:8px;
  }
  
  .section-links{
    display:flex;
    gap:8px;
    flex-wrap:wrap;
  }
  
  /* Séparateur entre sections */
  .nav-separator{
    color:var(--border);
    font-size:20px;
    opacity:0.3;
    margin:0 4px;
    align-self:center;
  }
  
  /* Styles des liens par section */
  .nav-link{
    padding:8px 14px;
    border-radius:8px;
    text-decoration:none;
    font-size:13px;
    font-weight:500;
    transition:all 0.2s;
    border:1px solid transparent;
    white-space:nowrap;
  }
  
  /* Section Analytics - Couleurs bleues/vertes */
  .section-analytics .nav-link{
    color:#64748b;
    background:rgba(59, 130, 246, 0.05);
    border-color:rgba(59, 130, 246, 0.1);
  }
  .section-analytics .nav-link:hover{
    background:rgba(59, 130, 246, 0.1);
    border-color:rgba(59, 130, 246, 0.3);
    color:#3b82f6;
  }
  .section-analytics .nav-link.active{
    background:#3b82f6;
    color:white;
    border-color:#3b82f6;
  }
  
  /* Section Engine - Couleurs oranges/rouges */
  .section-engine .nav-link{
    color:#64748b;
    background:rgba(249, 115, 22, 0.05);
    border-color:rgba(249, 115, 22, 0.1);
  }
  .section-engine .nav-link:hover{
    background:rgba(249, 115, 22, 0.1);
    border-color:rgba(249, 115, 22, 0.3);
    color:#f97316;
  }
  .section-engine .nav-link.active{
    background:#f97316;
    color:white;
    border-color:#f97316;
  }
  
  /* Section Configuration - Couleurs violettes */
  .section-config .nav-link{
    color:#64748b;
    background:rgba(139, 92, 246, 0.05);
    border-color:rgba(139, 92, 246, 0.1);
  }
  .section-config .nav-link:hover{
    background:rgba(139, 92, 246, 0.1);
    border-color:rgba(139, 92, 246, 0.3);
    color:#8b5cf6;
  }
  .section-config .nav-link.active{
    background:#8b5cf6;
    color:white;
    border-color:#8b5cf6;
  }
  
  /* Style pour éléments désactivés */
  .nav-link.disabled{
    color:#4a5568 !important;
    background:rgba(55, 65, 81, 0.1) !important;
    border:1px dashed rgba(55, 65, 81, 0.3) !important;
    cursor:not-allowed;
    font-style:italic;
    opacity:0.6;
  }
  
  /* Style pour badge avec count */
  .nav-link.has-badge{
    background:rgba(245, 158, 11, 0.15) !important;
    border-color:#f59e0b !important;
    color:#f59e0b !important;
    animation:pulse 2s infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
  
  /* Responsive */
  @media(max-width: 1024px){
    .nav{
      flex-direction:column;
      gap:16px;
      align-items:flex-start;
    }
    .nav-separator{
      display:none;
    }
    .section-links{
      gap:6px;
    }
    .nav-link{
      padding:6px 12px;
      font-size:12px;
    }
  }
  
  @media(max-width: 768px){
    .nav-link{
      padding:6px 10px;
      font-size:11px;
    }
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

  // Initialize theme after header is created
  setTimeout(() => {
    initTheme();
  }, 100);
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

// Alias pour compatibilité
function initializeSharedHeader(activePageId, options = {}) {
  return initSharedHeader(activePageId, options);
}

// Theme management functions
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcons(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';

  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeIcons(newTheme);
}

function updateThemeIcons(theme) {
  const lightIcon = document.getElementById('light-icon');
  const darkIcon = document.getElementById('dark-icon');

  if (lightIcon && darkIcon) {
    if (theme === 'light') {
      lightIcon.classList.add('active');
      darkIcon.classList.remove('active');
    } else {
      lightIcon.classList.remove('active');
      darkIcon.classList.add('active');
    }
  }
}

// Export pour utilisation
window.initSharedHeader = initSharedHeader;
window.initializeSharedHeader = initializeSharedHeader;
window.updateConfigIndicators = updateConfigIndicators;
window.toggleTheme = toggleTheme;
window.initTheme = initTheme;
