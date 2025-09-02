/**
 * Menu de navigation simple et compact
 */

class SimpleNavigation {
  constructor(options = {}) {
    this.options = {
      activePageId: null,
      ...options
    };
    
    this.currentSubmenu = null;
    this._hideSubmenuTimeout = null;
    
    this.init();
  }
  
  init() {
    this.detectCurrentPage();
    this.createNavigation();
    this.bindEvents();
    this.applyLayout();
  }
  
  detectCurrentPage() {
    if (this.options.activePageId) {
      return;
    }
    
    const path = window.location.pathname;
    const filename = path.split('/').pop().replace('.html', '');
    this.options.activePageId = filename || 'dashboard';
  }
  
  createNavigation() {
    // Créer le conteneur
    const container = document.createElement('nav');
    container.className = 'simple-nav-container';
    container.id = 'simple-navigation';
    
    container.innerHTML = `
      <div class="simple-nav">
        <div class="simple-nav-header">
          <h2 class="simple-nav-title">🎯 Crypto AI</h2>
        </div>
        <div class="simple-nav-items">
          ${this.generateNavItems()}
        </div>
      </div>
      ${this.generateSubmenus()}
    `;
    
    // Insérer au début du body
    document.body.insertBefore(container, document.body.firstChild);
  }
  
  generateNavItems() {
    const themes = this.getThemes();
    
    return themes.map(theme => `
      <div class="simple-nav-item" data-theme="${theme.id}">
        <a href="#" class="simple-nav-icon ${this.isThemeActive(theme) ? 'active' : ''}"
           title="${theme.title}">
          ${theme.icon}
        </a>
      </div>
    `).join('');
  }
  
  generateSubmenus() {
    const themes = this.getThemes();
    
    return themes.map(theme => `
      <div class="simple-submenu" id="submenu-${theme.id}">
        <div class="simple-submenu-header">
          <h3 class="simple-submenu-title">
            <span>${theme.icon}</span>
            ${theme.title}
          </h3>
        </div>
        <div class="simple-submenu-links">
          ${Object.entries(theme.pages).map(([pageId, page]) => `
            <a href="${page.url}" 
               class="simple-submenu-link ${pageId === this.options.activePageId ? 'active' : ''}"
               data-page="${pageId}">
              <span class="simple-submenu-link-icon">${page.icon}</span>
              <span>${page.title}</span>
            </a>
          `).join('')}
        </div>
      </div>
    `).join('');
  }
  
  getThemes() {
    // Données simplifiées pour test
    return [
      {
        id: 'strategy',
        title: 'Stratégie',
        icon: '🎯',
        pages: {
          'dashboard': { title: 'Dashboard', icon: '📊', url: 'dashboard.html' },
          'rebalance': { title: 'Rebalance', icon: '⚖️', url: 'rebalance.html' },
          'multi-asset-dashboard': { title: 'Multi-Asset', icon: '📈', url: 'multi-asset-dashboard.html' },
          'enhanced-dashboard': { title: 'Dashboard Enhanced', icon: '✨', url: 'enhanced-dashboard.html' },
          'cycle-analysis': { title: 'Analyse Cycles', icon: '🔄', url: 'cycle-analysis.html' }
        }
      },
      {
        id: 'portfolio',
        title: 'Portfolio',
        icon: '💼',
        pages: {
          'portfolio-optimization': { title: 'Optimisation', icon: '⚡', url: 'portfolio-optimization.html' }
        }
      },
      {
        id: 'execution',
        title: 'Exécution',
        icon: '🚀',
        pages: {
          'execution': { title: 'Trading', icon: '💹', url: 'execution.html' },
          'execution-history': { title: 'Historique', icon: '📋', url: 'execution_history.html' }
        }
      },
      {
        id: 'risk',
        title: 'Risque',
        icon: '🛡️',
        pages: {
          'risk-dashboard': { title: 'Dashboard Risque', icon: '📊', url: 'risk-dashboard.html' },
          'monitoring-unified': { title: 'Monitoring', icon: '👁️', url: 'monitoring-unified.html' }
        }
      },
      {
        id: 'ai',
        title: 'Intelligence IA',
        icon: '🧠',
        pages: {
          'ai-dashboard': { title: 'Dashboard IA', icon: '🤖', url: 'ai-dashboard.html' },
          'ml-showcase': { title: 'ML Showcase', icon: '⚡', url: 'ml-showcase.html' },
          'ai-components-demo': { title: 'Composants IA', icon: '🔬', url: 'ai-components-demo.html' }
        }
      },
      {
        id: 'tools',
        title: 'Outils Avancés',
        icon: '🔬',
        pages: {
          'backtesting': { title: 'Backtesting', icon: '🔄', url: 'backtesting.html' },
          'performance-monitor': { title: 'Performance', icon: '⚡', url: 'performance-monitor.html' }
        }
      },
      {
        id: 'config',
        title: 'Configuration',
        icon: '⚙️',
        pages: {
          'settings': { title: 'Paramètres', icon: '🔧', url: 'settings.html' },
          'alias-manager': { title: 'Alias', icon: '🏷️', url: 'alias-manager.html' },
          'debug-menu': { title: 'Debug & Tests', icon: '🐛', url: 'debug-menu.html' }
        }
      }
    ];
  }
  
  isThemeActive(theme) {
    return Object.keys(theme.pages).includes(this.options.activePageId);
  }
  
  bindEvents() {
    const navItems = document.querySelectorAll('.simple-nav-item');
    
    navItems.forEach(item => {
      const icon = item.querySelector('.simple-nav-icon');
      const themeId = item.dataset.theme;
      
      // Click pour naviguer vers la page par défaut
      icon.addEventListener('click', (e) => {
        e.preventDefault();
        this.navigateToDefaultPage(themeId);
      });
      
      // Hover pour montrer le sous-menu
      item.addEventListener('mouseenter', () => {
        clearTimeout(this._hideSubmenuTimeout);
        this.showSubmenu(themeId, item);
      });
      
      item.addEventListener('mouseleave', () => {
        this._hideSubmenuTimeout = setTimeout(() => {
          if (!this.isHoveringSubmenu(themeId)) {
            this.hideSubmenu();
          }
        }, 300);
      });
    });
    
    // Events pour les sous-menus
    const submenus = document.querySelectorAll('.simple-submenu');
    submenus.forEach(submenu => {
      submenu.addEventListener('mouseenter', () => {
        clearTimeout(this._hideSubmenuTimeout);
      });
      
      submenu.addEventListener('mouseleave', () => {
        this._hideSubmenuTimeout = setTimeout(() => {
          this.hideSubmenu();
        }, 300);
      });
    });
  }
  
  showSubmenu(themeId, navItem) {
    // Masquer le sous-menu actuel
    this.hideSubmenu();
    
    const submenu = document.getElementById(`submenu-${themeId}`);
    if (!submenu) return;
    
    // Positionner le sous-menu
    const rect = navItem.getBoundingClientRect();
    submenu.style.top = `${rect.top}px`;
    
    // Afficher
    submenu.classList.add('show');
    this.currentSubmenu = submenu;
  }
  
  hideSubmenu() {
    if (this.currentSubmenu) {
      this.currentSubmenu.classList.remove('show');
      this.currentSubmenu = null;
    }
  }
  
  isHoveringSubmenu(themeId) {
    const submenu = document.getElementById(`submenu-${themeId}`);
    return submenu && submenu.matches(':hover');
  }
  
  navigateToDefaultPage(themeId) {
    const themes = this.getThemes();
    const theme = themes.find(t => t.id === themeId);
    
    if (!theme) return;
    
    // Obtenir la page par défaut selon la logique demandée
    let defaultPageId;
    const pages = Object.keys(theme.pages);
    
    if (themeId === 'config') {
      // Pour settings, prendre la dernière page (alias-manager)
      defaultPageId = pages[pages.length - 1];
    } else {
      // Pour les autres thèmes, prendre la première page
      defaultPageId = pages[0];
    }
    
    const defaultPage = theme.pages[defaultPageId];
    if (defaultPage && defaultPage.url) {
      window.location.href = defaultPage.url;
    }
  }
  
  applyLayout() {
    // Ajouter la classe au body pour décaler le contenu
    document.body.classList.add('has-simple-nav');
    
    // Forcer le style inline pour être sûr
    document.body.style.marginLeft = '80px';
    document.body.style.transition = 'margin-left 0.3s ease';
    
    console.log('🎯 Menu simple appliqué - décalage: 80px');
  }
}

// Fonction d'initialisation
function createSimpleNavigation(activePageId, options = {}) {
  const navigation = new SimpleNavigation({
    activePageId: activePageId,
    ...options
  });
  
  window.simpleNavigation = navigation;
  return navigation;
}

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { SimpleNavigation, createSimpleNavigation };
}