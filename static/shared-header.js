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

  // Section 4: Debug Tests (conditionnelle)
  const debugTests = [
    // NOUVEAU: Menu Principal Debug
    { category: '🚀 MENU PRINCIPAL DEBUG', tests: [
      { title: '🔧 Menu Debug & Tests Complet', url: '/debug-menu.html', desc: '⭐ CENTRE DE CONTRÔLE - Tous les nouveaux modules', highlight: true },
      { title: '🩺 Diagnostic 11 Groupes', url: '/tests/html_debug/debug_11_groups_fix.html', desc: 'Diagnostic complet problème groupes' },
      { title: '⚡ Test Performance Système', url: '/tests/html_debug/test_performance_system.html', desc: 'Tests système performance' },
      { title: '💰 Test Multi-Asset System', url: '/tests/html_debug/test_multi_asset_system.html', desc: 'Tests système multi-actifs' }
    ]},
    // Core System
    { category: '🔧 Core System', tests: [
      { title: '11 Groups Test', url: '/tests/html_debug/debug_11_groups.html', desc: 'Test 11 groupes Strategic Targeting' },
      { title: 'Simple Targets', url: '/tests/html_debug/simple_test_targets.html', desc: 'Test direct des targets' },
      { title: 'V2 System', url: '/tests/html_debug/test-v2-comprehensive.html', desc: 'Test système V2 complet' },
      { title: 'Full Integration', url: '/tests/html_debug/test-full-integration.html', desc: 'Test intégration complète' }
    ]},
    // Scoring & CCS
    { category: '📊 Scoring & CCS', tests: [
      { title: 'Scoring V2', url: '/tests/html_debug/test-scoring-v2.html', desc: 'Système de scoring V2' },
      { title: 'CCS Check', url: '/tests/html_debug/debug_ccs_check.html', desc: 'Vérification CCS' },
      { title: 'Dynamic Weight', url: '/tests/html_debug/test-dynamic-weighting.html', desc: 'Pondération dynamique' },
      { title: 'Score Validator', url: '/tests/html_debug/score-consistency-validator.html', desc: 'Validation cohérence' }
    ]},
    // UI & Navigation  
    { category: '🎨 UI & Navigation', tests: [
      { title: 'Navigation UI', url: '/tests/html_debug/test_navigation_ui.html', desc: 'Interface navigation' },
      { title: 'Debug Dashboard', url: '/tests/html_debug/debug-dashboard.html', desc: 'Debug tableau de bord' },
      { title: 'Strategy Buttons', url: '/tests/html_debug/test_strategy_buttons.html', desc: 'Boutons stratégie' }
    ]},
    // Data & API
    { category: '🌐 Data & API', tests: [
      { title: 'CSV Access', url: '/tests/html_debug/test_csv_access.html', desc: 'Accès CSV' },
      { title: 'Data Flow', url: '/tests/html_debug/debug_data_flow.html', desc: 'Flux de données' },
      { title: 'Performance', url: '/tests/html_debug/performance-monitor.html', desc: 'Monitoring performance' }
    ]}
  ];

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

  // Fonction pour créer le dropdown debug
  const createDebugDropdown = () => {
    if (!window.globalConfig || !window.globalConfig.isDebugMode()) {
      return '';
    }

    const categoriesHTML = debugTests.map(category => `
      <div class="debug-category">
        <div class="debug-category-header">${category.category}</div>
        ${category.tests.map(test => `
          <a href="${test.url}" class="debug-test-link ${test.highlight ? 'debug-test-highlight' : ''}" title="${test.desc}">
            ${test.title}
          </a>
        `).join('')}
      </div>
    `).join('');

    return `
      <div class="nav-section debug-section">
        <button class="debug-dropdown-toggle" onclick="toggleDebugDropdown(event)">
          🛠️ Debug Tests
        </button>
        <div class="debug-dropdown-menu" id="debug-dropdown-menu">
          <div class="debug-dropdown-content">
            ${categoriesHTML}
          </div>
        </div>
      </div>
    `;
  };

  // Créer les sections de navigation
  const analyticsLinks = createSectionLinks(analyticsPages, 'section-analytics');
  const engineLinks = createSectionLinks(enginePages, 'section-engine');
  const configLinks = createSectionLinks(configPages, 'section-config');
  const debugDropdown = createDebugDropdown();

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
          ${debugDropdown ? `<div class="nav-separator">|</div>${debugDropdown}` : ''}
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
  
  /* Section Debug - Couleurs rouges/oranges */
  .debug-section{
    position:relative;
  }
  .debug-dropdown-toggle{
    padding:8px 14px;
    border-radius:8px;
    border:1px solid rgba(239, 68, 68, 0.2);
    background:rgba(239, 68, 68, 0.05);
    color:#64748b;
    font-size:13px;
    font-weight:500;
    cursor:pointer;
    transition:all 0.2s;
    white-space:nowrap;
  }
  .debug-dropdown-toggle:hover{
    background:rgba(239, 68, 68, 0.1);
    border-color:rgba(239, 68, 68, 0.4);
    color:#ef4444;
  }
  .debug-dropdown-toggle.active{
    background:#ef4444;
    color:white;
    border-color:#ef4444;
  }
  
  /* Menu dropdown debug */
  .debug-dropdown-menu{
    position:absolute;
    top:100%;
    right:0;
    z-index:1000;
    min-width:320px;
    max-width:400px;
    margin-top:8px;
    background:white;
    border:1px solid rgba(0,0,0,0.1);
    border-radius:12px;
    box-shadow:0 10px 40px rgba(0,0,0,0.15);
    display:none;
    animation:dropdownFadeIn 0.2s ease-out;
  }
  .debug-dropdown-menu.show{
    display:block;
  }
  
  @keyframes dropdownFadeIn {
    0% { opacity:0; transform:translateY(-10px); }
    100% { opacity:1; transform:translateY(0); }
  }
  
  .debug-dropdown-content{
    padding:16px;
    max-height:70vh;
    overflow-y:auto;
  }
  
  .debug-category{
    margin-bottom:16px;
  }
  .debug-category:last-child{
    margin-bottom:0;
  }
  
  .debug-category-header{
    font-size:12px;
    font-weight:600;
    color:#6b7280;
    text-transform:uppercase;
    letter-spacing:0.5px;
    margin-bottom:8px;
    border-bottom:1px solid #f3f4f6;
    padding-bottom:4px;
  }
  
  .debug-test-link{
    display:block;
    padding:8px 12px;
    margin:2px 0;
    border-radius:6px;
    text-decoration:none;
    color:#374151;
    font-size:13px;
    background:rgba(249, 250, 251, 0.5);
    border:1px solid transparent;
    transition:all 0.15s;
  }
  .debug-test-link:hover{
    background:#fef2f2;
    border-color:#fecaca;
    color:#dc2626;
    transform:translateX(2px);
  }
  
  /* Style spécial pour les éléments en surbrillance */
  .debug-test-highlight{
    background: linear-gradient(45deg, #00ff88, #00cc66) !important;
    color: #000 !important;
    font-weight: 600 !important;
    border: 2px solid #00ff88 !important;
    box-shadow: 0 2px 8px rgba(0, 255, 136, 0.3) !important;
    animation: pulseHighlight 2s ease-in-out infinite !important;
  }
  
  .debug-test-highlight:hover{
    background: linear-gradient(45deg, #00cc66, #00aa44) !important;
    transform: translateX(4px) scale(1.02) !important;
    box-shadow: 0 4px 16px rgba(0, 255, 136, 0.4) !important;
  }
  
  @keyframes pulseHighlight {
    0%, 100% { box-shadow: 0 2px 8px rgba(0, 255, 136, 0.3); }
    50% { box-shadow: 0 4px 16px rgba(0, 255, 136, 0.6); }
  }
  
  /* Dark theme support */
  [data-theme="dark"] .debug-dropdown-menu{
    background:#1f2937;
    border-color:rgba(255,255,255,0.1);
    box-shadow:0 10px 40px rgba(0,0,0,0.3);
  }
  [data-theme="dark"] .debug-category-header{
    color:#9ca3af;
    border-bottom-color:#374151;
  }
  [data-theme="dark"] .debug-test-link{
    color:#d1d5db;
    background:rgba(55, 65, 81, 0.5);
  }
  [data-theme="dark"] .debug-test-link:hover{
    background:#7f1d1d;
    border-color:#dc2626;
    color:#fca5a5;
  }
  
  /* Dark theme pour highlight */
  [data-theme="dark"] .debug-test-highlight{
    background: linear-gradient(45deg, #00ff88, #00cc66) !important;
    color: #000 !important;
  }
  
  [data-theme="dark"] .debug-test-highlight:hover{
    background: linear-gradient(45deg, #00cc66, #00aa44) !important;
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

  // Initialize theme after header is created using centralized system
  setTimeout(() => {
    if (window.globalConfig && window.globalConfig.applyTheme) {
      window.globalConfig.applyTheme();
    } else if (window.applyAppearance) {
      window.applyAppearance();
    }
  }, 50);

  // Activer la fonctionnalité debug
  enableDebugModeOnDoubleClick();

  // Écouter les changements de debug mode pour rafraîchir
  window.addEventListener('debugModeChanged', () => {
    setTimeout(() => {
      refreshNavigation(activePageId, options);
    }, 100);
  });
}

// Fonction pour rafraîchir dynamiquement la navigation
function refreshNavigation(activePageId, options = {}) {
  const existingHeader = document.querySelector('header');
  if (existingHeader) {
    const headerHTML = createSharedHeader(activePageId, options.showConfigIndicators);
    existingHeader.outerHTML = headerHTML;
  }
  // Réattacher le double‑clic Settings après réinjection du header
  enableDebugModeOnDoubleClick();
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
function toggleTheme() {
  if (window.globalConfig && window.globalConfig.setTheme) {
    const currentTheme = window.globalConfig.get('theme') || 'auto';
    let newTheme;

    if (currentTheme === 'auto') {
      // Si en mode auto, basculer vers le thème opposé au thème effectif actuel
      const effectiveTheme = window.globalConfig.getEffectiveTheme();
      newTheme = effectiveTheme === 'light' ? 'dark' : 'light';
    } else {
      // Si en mode manuel, basculer entre light et dark
      newTheme = currentTheme === 'light' ? 'dark' : 'light';
    }

    window.globalConfig.setTheme(newTheme);
    updateThemeIcons(window.globalConfig.getEffectiveTheme());
  } else {
    // Fallback pour compatibilité
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcons(newTheme);
  }
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

// Fonction pour toggle le dropdown debug
function toggleDebugDropdown(event) {
  event.preventDefault();
  event.stopPropagation();
  
  const menu = document.getElementById('debug-dropdown-menu');
  const toggle = event.target;
  
  if (!menu) return;
  
  const isOpen = menu.classList.contains('show');
  
  if (isOpen) {
    menu.classList.remove('show');
    toggle.classList.remove('active');
  } else {
    menu.classList.add('show');
    toggle.classList.add('active');
  }
  
  // Fermer le dropdown si on clique ailleurs
  if (!isOpen) {
    setTimeout(() => {
      document.addEventListener('click', function closeDropdown(e) {
        if (!menu.contains(e.target) && e.target !== toggle) {
          menu.classList.remove('show');
          toggle.classList.remove('active');
          document.removeEventListener('click', closeDropdown);
        }
      });
    }, 100);
  }
}

// Fonction pour activer le mode debug via double-click sur Settings
function enableDebugModeOnDoubleClick() {
  setTimeout(() => {
    // Le lien Settings a les classes: "nav-link section-config"
    const settingsLink = document.querySelector('a.nav-link.section-config');
    if (settingsLink && window.globalConfig) {
      let clickTimeout = null;
      let pendingNavigate = null;
      const navigateDelayMs = 300;

      settingsLink.addEventListener('click', function (e) {
        // Toujours empêcher la navigation immédiate pour permettre le double-clic
        e.preventDefault();

        // Si une navigation est en attente et qu'on reclique assez vite, considérer comme double-clic
        if (pendingNavigate) {
          clearTimeout(pendingNavigate);
          pendingNavigate = null;

          // Toggle debug mode
          const newMode = window.globalConfig.toggleDebugMode();

          // Afficher notification
          const notification = document.createElement('div');
          notification.innerHTML = `🛠️ Mode debug ${newMode ? 'activé' : 'désactivé'}`;
          notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${newMode ? '#10b981' : '#ef4444'};
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 9999;
            animation: slideInOut 3s ease-in-out forwards;
          `;

          const style = document.createElement('style');
          style.textContent = `
            @keyframes slideInOut {
              0% { transform: translateX(100%); opacity: 0; }
              15%, 85% { transform: translateX(0); opacity: 1; }
              100% { transform: translateX(100%); opacity: 0; }
            }
          `;

          document.head.appendChild(style);
          document.body.appendChild(notification);

          setTimeout(() => {
            notification.remove();
            style.remove();
            // Rafraîchir le header pour afficher/masquer le menu debug
            const active = document.querySelector('.nav-link.active');
            const pageId = active?.getAttribute('href')?.replace('.html', '') || 'dashboard';
            refreshNavigation(pageId, {});
          }, 1500);

          return; // pas de navigation sur double-clic
        }

        // Premier clic: démarrer un timer de navigation différée
        const href = settingsLink.getAttribute('href') || 'settings.html';
        pendingNavigate = setTimeout(() => {
          pendingNavigate = null;
          window.location.href = href;
        }, navigateDelayMs);
      });
    }
  }, 100);
}

// Export pour utilisation
window.initSharedHeader = initSharedHeader;
window.initializeSharedHeader = initializeSharedHeader;
window.updateConfigIndicators = updateConfigIndicators;
window.toggleTheme = toggleTheme;
window.toggleDebugDropdown = toggleDebugDropdown;

// Raccourci clavier: Alt+D pour toggler le mode debug
window.addEventListener('keydown', (e) => {
  try {
    if (e.altKey && (e.key === 'd' || e.key === 'D')) {
      if (!window.globalConfig?.toggleDebugMode) return;
      const newMode = window.globalConfig.toggleDebugMode();
      const note = document.createElement('div');
      note.textContent = `🛠️ Mode debug ${newMode ? 'activé' : 'désactivé'}`;
      note.style.cssText = `
        position: fixed; top: 20px; right: 20px; background: ${newMode ? '#10b981' : '#ef4444'}; color: white;
        padding: 10px 14px; border-radius: 8px; z-index: 9999; font-size: 13px; opacity: .95;
      `;
      document.body.appendChild(note);
      setTimeout(() => note.remove(), 1200);
      // Recréer le header pour refléter le changement
      const active = document.querySelector('.nav-link.active');
      const pageId = active?.getAttribute('href')?.replace('.html', '') || 'dashboard';
      refreshNavigation(pageId, {});
    }
  } catch (_) { /* no-op */ }
});
