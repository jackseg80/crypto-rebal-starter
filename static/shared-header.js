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
    'alias-manager': { title: '🏷️ Aliases', url: 'alias-manager.html', icon: '🏷️' },
    'settings': { title: '⚙️ Settings', url: 'settings.html', icon: '⚙️' }
  };

  // Section 2: Execution Engine & Diagnostics (Interface Technique)
  const enginePages = {
    'execution': { title: '🚀 Execute', url: 'execution.html', icon: '🚀' },
    'execution-history': { title: '📈 History', url: 'execution_history.html', icon: '📈' },
    'monitoring': { title: '🔍 Monitor', url: 'monitoring_advanced.html', icon: '🔍' }
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

      let linkContent = `${page.icon} ${page.title.replace(/[📊🛡️⚖️🏷️⚙️🚀📈🔍]\s*/, '')}`;

      // Logique spéciale pour Alias Manager
      if (pageId === 'alias-manager') {
        const unknownCount = window.globalConfig?.getUnknownAliasesCount() || 0;
        if (unknownCount > 0) {
          linkClass += ' has-badge';
          return `<a href="${page.url}" class="${linkClass}" data-count="${unknownCount}">${linkContent}</a>`;
        }
      }

      return `<a href="${page.url}" class="${linkClass}">${linkContent}</a>`;
    }).join('');
  };

  // Créer les sections de navigation
  const analyticsLinks = createSectionLinks(analyticsPages, 'section-analytics');
  const engineLinks = createSectionLinks(enginePages, 'section-engine');

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
      <div class="config-indicators">
        <div class="config-indicator">
          <span>Source:</span>
          <strong id="current-source">${sourceLabels[currentSource] || 'Inconnu'}</strong>
        </div>
        <div class="config-indicator">
          <span>Pricing:</span>
          <strong id="current-pricing">${pricingLabels[currentPricing] || 'Inconnu'}</strong>
        </div>
      </div>
    `;
  }

  return `
    <header>
      <div class="wrap">
        <div>
          <h1>${title}</h1>
          <div class="theme-toggle" onclick="toggleTheme()" title="Basculer le thème">
            <span class="theme-toggle-icon" id="light-icon">☀️</span>
            <span class="theme-toggle-icon" id="dark-icon">🌙</span>
          </div>
        </div>
        <nav class="nav">
          <div class="nav-section analytics-section">
            <div class="section-links">
              ${analyticsLinks}
            </div>
          </div>
          <div class="nav-section engine-section">
            <div class="section-links">
              ${engineLinks}
            </div>
          </div>
        </nav>
        ${configIndicators}
      </div>
    </header>
  `;
}

// Fonction d'initialisation du header partagé
function initializeSharedHeader(activePageId = 'dashboard', showConfigIndicators = false) {
  // Injecter le CSS partagé
  if (!document.getElementById('shared-nav-styles')) {
    const styleSheet = document.createElement('style');
    styleSheet.id = 'shared-nav-styles';
    styleSheet.textContent = SHARED_NAV_CSS;
    document.head.appendChild(styleSheet);
  }
  
  // Injecter le HTML du header
  const headerContainer = document.getElementById('shared-header');
  if (headerContainer) {
    headerContainer.innerHTML = createSharedHeader(activePageId, showConfigIndicators);
  }
}

// CSS partagé pour la navigation bi-section - Style inspiré de CoinTracking
const SHARED_NAV_CSS = `
  /* Header principal */
  header {
    background: var(--theme-surface);
    border-bottom: 1px solid var(--theme-border);
    margin-bottom: 30px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  }

  .wrap {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
  }

  /* En-tête avec titre et bouton thème */
  header > .wrap > div:first-child {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 0 15px 0;
    border-bottom: 1px solid var(--theme-border);
  }

  header h1 {
    color: var(--theme-text);
    font-size: 24px;
    font-weight: 600;
    margin: 0;
  }

  /* Navigation principale */
  .nav {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 0;
    padding: 15px 0;
  }

  /* Supprimer le séparateur */
  .nav-separator {
    display: none;
  }

  /* Sections de navigation */
  .nav-section {
    display: flex;
    align-items: center;
    gap: 0;
  }

  .section-label {
    display: none; /* Cacher les labels de section */
  }

  .section-links {
    display: flex;
    gap: 0;
    background: var(--theme-surface-elevated);
    border-radius: 12px;
    padding: 4px;
    border: 1px solid var(--theme-border);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  /* Styles des liens de navigation */
  .nav-link {
    padding: 10px 20px;
    border-radius: 8px;
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;
    color: var(--theme-text-muted);
    background: transparent;
    border: none;
    margin: 0;
    white-space: nowrap;
  }

  .nav-link:hover {
    color: var(--theme-text);
    background: var(--theme-surface-hover);
  }

  .nav-link.active {
    color: var(--brand-primary);
    background: var(--brand-primary-bg);
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(45, 212, 191, 0.15);
  }

  /* Espacement entre les sections */
  .analytics-section {
    margin-right: 30px;
  }

  /* Style pour éléments désactivés */
  .nav-link.disabled {
    color: var(--theme-text-disabled) !important;
    background: var(--theme-surface-disabled) !important;
    cursor: not-allowed;
    font-style: italic;
    opacity: 0.6;
  }

  /* Style pour badge avec count */
  .nav-link.has-badge {
    position: relative;
  }

  .nav-link.has-badge::after {
    content: attr(data-count);
    position: absolute;
    top: -5px;
    right: -5px;
    background: var(--warning);
    color: white;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    font-size: 10px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
  }

  /* Styles pour le bouton de thème */
  .theme-toggle {
    cursor: pointer;
    padding: 10px;
    border-radius: 8px;
    background: var(--theme-surface);
    border: 1px solid var(--theme-border);
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
  }

  .theme-toggle:hover {
    background: var(--theme-surface-hover);
    border-color: var(--brand-accent);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(45, 212, 191, 0.1);
  }

  .theme-toggle-icon {
    font-size: 20px;
    transition: all 0.2s ease;
  }

  /* Indicateurs de configuration */
  .config-indicators {
    display: flex;
    gap: 20px;
    padding: 15px 0;
    border-top: 1px solid var(--theme-border);
    font-size: 13px;
    color: var(--theme-text-muted);
  }

  .config-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .config-indicator strong {
    color: var(--brand-accent);
    font-weight: 600;
  }

  /* Responsive */
  @media (max-width: 1024px) {
    .nav {
      flex-direction: column;
      gap: 15px;
      align-items: stretch;
    }

    .analytics-section {
      margin-right: 0;
      margin-bottom: 15px;
    }

    .section-links {
      flex-wrap: wrap;
      justify-content: center;
    }

    header > .wrap > div:first-child {
      flex-direction: column;
      gap: 15px;
      align-items: flex-start;
    }

    .theme-toggle {
      align-self: flex-end;
    }
  }

  @media (max-width: 768px) {
    .wrap {
      padding: 0 15px;
    }

    header h1 {
      font-size: 20px;
    }

    .nav-link {
      padding: 8px 16px;
      font-size: 13px;
    }

    .section-links {
      gap: 4px;
      padding: 3px;
    }

    .config-indicators {
      flex-direction: column;
      gap: 10px;
    }
  }

  @media (max-width: 480px) {
    .nav-link {
      padding: 6px 12px;
      font-size: 12px;
    }

    .section-links {
      flex-direction: column;
      gap: 2px;
    }
  }
`;

// Fonction d'initialisation pour injecter le header
function initSharedHeader(activePageId, options = {}) {
  console.log('🚀 initSharedHeader appelé pour la page:', activePageId);

  // Injecter le CSS s'il n'existe pas déjà
  if (!document.getElementById('shared-nav-styles')) {
    console.log('🎨 Injection du CSS de navigation');
    const style = document.createElement('style');
    style.id = 'shared-nav-styles';
    style.textContent = SHARED_NAV_CSS;
    document.head.appendChild(style);
  }

  // Remplacer le header existant ou l'injecter au début du body
  const existingHeader = document.querySelector('header');
  const headerHTML = createSharedHeader(activePageId, options.showConfigIndicators);

  if (existingHeader) {
    console.log('🔄 Remplacement du header existant');
    existingHeader.outerHTML = headerHTML;
  } else {
    console.log('➕ Injection du nouveau header');
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

  // Initialiser le thème
  console.log('🎨 Initialisation du thème...');
  initTheme();
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

// Fonctions de gestion du thème
function getCurrentTheme() {
  return localStorage.getItem('theme') || 'light';
}

function setTheme(theme) {
  console.log('🎨 setTheme appelé avec:', theme);
  localStorage.setItem('theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
  console.log('✅ data-theme défini sur:', theme);

  // Mettre à jour les icônes du toggle
  const lightIcon = document.getElementById('light-icon');
  const darkIcon = document.getElementById('dark-icon');
  console.log('🔍 Recherche des icônes - light:', lightIcon, 'dark:', darkIcon);

  if (lightIcon && darkIcon) {
    console.log('✅ Icônes trouvées, mise à jour de l\'affichage');
    if (theme === 'light') {
      lightIcon.style.display = 'block';
      darkIcon.style.display = 'none';
      console.log('☀️ Affichage icône lumière');
    } else {
      lightIcon.style.display = 'none';
      darkIcon.style.display = 'block';
      console.log('🌙 Affichage icône nuit');
    }
  } else {
    console.log('❌ Icônes non trouvées - le bouton theme-toggle n\'existe pas dans le DOM');
  }
}

function toggleTheme() {
  const currentTheme = getCurrentTheme();
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  setTheme(newTheme);
}

// Initialiser le thème au chargement
function initTheme() {
  console.log('🎨 initTheme appelé');
  const savedTheme = getCurrentTheme();
  console.log('💾 Thème sauvegardé:', savedTheme);
  setTheme(savedTheme);
}

// Export pour utilisation
window.initSharedHeader = initSharedHeader;
window.updateConfigIndicators = updateConfigIndicators;
window.toggleTheme = toggleTheme;
window.getCurrentTheme = getCurrentTheme;
window.setTheme = setTheme;
window.initTheme = initTheme;
