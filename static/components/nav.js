// Composant de navigation unifié (ES module, zéro dépendance)
// Injecte un <header class="app-header"> sticky avec liens actifs et menu Admin.

// Import dynamique du WealthContextBar
const loadWealthContextBar = async () => {
  try {
    await import('./WealthContextBar.js');
  } catch (error) {
    console.debug('WealthContextBar not loaded:', error);
  }
};

// Initialisation du sélecteur d'utilisateur
const initUserSwitcher = async () => {
  try {
    // Charger la liste des utilisateurs depuis config/users.json
    const usersResponse = await fetch('/config/users.json', { cache: 'no-store' });
    if (!usersResponse.ok) {
      console.warn('Could not load users config');
      return;
    }

    const usersConfig = await usersResponse.json();
    const users = usersConfig.users || [];
    const defaultUser = usersConfig.default || 'demo';

    // Récupérer l'utilisateur actuel depuis localStorage
    const currentUser = localStorage.getItem('activeUser') || defaultUser;

    // Remplir le sélecteur
    const selector = document.getElementById('user-selector');
    if (!selector) return;

    selector.innerHTML = '';
    users.forEach(user => {
      const option = document.createElement('option');
      option.value = user.id;
      option.textContent = user.label;  // Plus de mode affiché
      if (user.id === currentUser) {
        option.selected = true;
      }
      selector.appendChild(option);
    });

    // Ajouter l'event listener pour le changement d'utilisateur
    selector.addEventListener('change', (e) => {
      const newUser = e.target.value;
      if (newUser !== currentUser) {
        switchUser(newUser);
      }
    });

    console.debug(`User switcher initialized, current user: ${currentUser}`);

  } catch (error) {
    console.error('Failed to initialize user switcher:', error);
  }
};

// Fonction pour changer d'utilisateur
const switchUser = (newUserId) => {
  try {
    const oldUser = localStorage.getItem('activeUser');
    localStorage.setItem('activeUser', newUserId);

    console.log(`Switching from user '${oldUser}' to '${newUserId}'`);

    // Émettre un événement pour informer les autres composants
    const event = new CustomEvent('active-user-changed', {
      detail: { oldUser, newUser: newUserId }
    });
    window.dispatchEvent(event);

    // Purger les caches pour éviter les données croisées
    if (window.clearCache) {
      window.clearCache();
    }

    // Vider les caches localStorage liés aux données
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('risk_score') || key.startsWith('cache:') || key.startsWith('portfolio_'))) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));

    // Recharger la page pour appliquer les changements
    setTimeout(() => {
      window.location.reload();
    }, 100);

  } catch (error) {
    console.error('Error switching user:', error);
  }
};

// Vérification des rôles RBAC pour menu Admin
const checkAdminRole = () => {
  try {
    // MODE DEV : Forcer admin si localhost ou dev
    const isDev = location.hostname === 'localhost' || location.hostname === '127.0.0.1' ||
                  location.hostname.includes('dev') || location.port === '8000';

    if (isDev) {
      console.debug('🔧 Dev mode detected - Admin role forced');
      return true;
    }

    // Vérifier localStorage pour rôles utilisateur
    const userRoles = localStorage.getItem('user_roles');
    if (userRoles) {
      const roles = JSON.parse(userRoles);
      return roles.includes('governance_admin') || roles.includes('ml_admin');
    }

    // Fallback: vérifier variables globales ou cookies
    if (window.userRoles) {
      return window.userRoles.includes('governance_admin') || window.userRoles.includes('ml_admin');
    }

    // Par défaut, masquer le menu Admin
    return false;
  } catch (error) {
    console.debug('Error checking admin roles:', error);
    return false;
  }
};

const initUnifiedNav = () => {
  try {
    if (window.__navInitialized) return;
    // Ne pas injecter quand nav=off (ex: iframes intégrées)
    const params = new URLSearchParams(location.search);
    if (params.get('nav') === 'off') return;

    window.__navInitialized = true;

    const style = document.createElement('style');
    style.textContent = `
      .app-header { position: sticky; top: 0; z-index: 1000; background: var(--theme-surface); border-bottom: 1px solid var(--theme-border); box-shadow: var(--shadow-sm); }
      .app-header .nav-inner { max-width: 1200px; margin: 0 auto; padding: 0.5rem 1rem; display: flex; align-items: center; gap: 1rem; }
      .app-header .brand { font-weight: 700; color: var(--theme-text); letter-spacing: .3px; }
      .app-header nav a { color: var(--theme-text-muted); text-decoration: none; padding: .5rem .75rem; border-radius: var(--radius-sm); transition: background var(--transition-fast), color var(--transition-fast); }
      .app-header nav a:hover { background: var(--theme-bg); color: var(--theme-text); }
      .app-header nav a.active { color: var(--brand-primary); background: color-mix(in oklab, var(--brand-primary) 12%, transparent); }
      .app-header .main-nav { position: relative; }
      .app-header .main-nav ul { list-style: none; display: flex; gap: .25rem; margin: 0; padding: 0; }
      .app-header .main-nav li { position: relative; }
      .app-header .main-nav li > a { display: inline-block; }
      .app-header .main-nav .has-submenu > a::after { content: '▾'; margin-left: .35rem; font-size: .8em; opacity: .7; }
      .app-header .submenu { display: none; position: absolute; top: 100%; left: 0; background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); box-shadow: var(--shadow-md); min-width: 220px; padding: .35rem; z-index: 1100; }
      .app-header .submenu a { display: block; padding: .5rem .6rem; white-space: nowrap; }
      .app-header .submenu a:hover { background: var(--theme-bg); }
      .app-header .menu-separator { height: 1px; background: var(--theme-border); margin: .4rem .25rem; }
      .app-header .main-nav .has-submenu:hover > .submenu,
      .app-header .main-nav .has-submenu.open > .submenu { display: block; }
      .app-header .spacer { flex: 1; }
      .app-header .admin { position: relative; }
      .app-header .admin-btn { background: var(--theme-surface); color: var(--theme-text); border: 1px solid var(--theme-border); border-radius: var(--radius-sm); padding: .4rem .6rem; cursor: pointer; display: inline-flex; align-items: center; gap: .35rem; }
      .app-header .admin-btn:hover { background: var(--theme-bg); }
      .app-header .dropdown { position: absolute; right: 0; top: calc(100% + 6px); background: var(--theme-surface); border: 1px solid var(--theme-border); border-radius: var(--radius-md); box-shadow: var(--shadow-md); min-width: 200px; padding: .35rem; display: none; }
      .app-header .dropdown.open { display: block; }
      .app-header .dropdown a { display: block; padding: .5rem .6rem; color: var(--theme-text); border-radius: var(--radius-sm); text-decoration: none; }
      .app-header .dropdown a:hover { background: var(--theme-bg); }
      .app-header .notifications { position: relative; display: flex; align-items: center; }
      .app-header .notification-badge { background: var(--brand-danger); color: white; border: none; border-radius: var(--radius-full); padding: .4rem .6rem; cursor: pointer; display: flex; align-items: center; gap: .35rem; font-size: .8em; font-weight: 600; box-shadow: var(--shadow-sm); transition: all var(--transition-fast); }
      .app-header .notification-badge:hover { background: color-mix(in oklab, var(--brand-danger) 80%, black); transform: scale(1.05); }
      .app-header .notification-badge:active { transform: scale(0.95); }
      .app-header .badge-icon { font-size: 1.1em; }
      .app-header .badge-count { background: rgba(255,255,255,0.9); color: var(--brand-danger); border-radius: var(--radius-full); padding: .1rem .35rem; font-size: .75em; min-width: 1.2em; text-align: center; }
      .app-header .user-switcher { display: flex; align-items: center; margin-right: 1rem; }
      .app-header .user-switcher label { margin: 0; }
      .app-header .user-switcher select { min-width: 120px; }
      @media (max-width: 1024px) { .app-header nav { display: flex; flex-wrap: wrap; gap: .25rem; } .app-header .nav-inner { gap: .5rem; } }
      @media (max-width: 720px) { .app-header nav a { padding: .4rem .6rem; font-size: 14px; } .app-header .notification-badge { padding: .3rem .5rem; font-size: .75em; } }
    `;
    document.head.appendChild(style);

    // Vérifier si l'élément navigation-container existe déjà
    let header = document.getElementById('navigation-container');

    if (!header) {
      // Créer un nouvel élément header si aucun n'existe
      header = document.createElement('header');
      header.id = 'navigation-container';
      header.className = 'app-header';

      const maybeInsertBefore = document.body.firstElementChild;
      if (maybeInsertBefore) {
        document.body.insertBefore(header, maybeInsertBefore);
      } else {
        document.body.appendChild(header);
      }
    } else {
      // Utiliser l'élément existant et s'assurer qu'il a la bonne classe
      header.className = 'app-header';
    }

    // Vérifier les rôles utilisateur pour affichage Admin RBAC
    const hasAdminRole = checkAdminRole();

    // Injecter le contenu de la navigation
    header.innerHTML = `
      <div class="nav-inner">
        <div class="brand">Crypto Rebal</div>
        <nav class="main-nav" aria-label="Navigation principale">
          <ul class="menu">
            <li><a href="dashboard.html" data-route="dashboard.html">Portfolio</a></li>
            <li><a href="analytics-unified.html" data-route="analytics-unified.html">Analytics</a></li>
            <li><a href="risk-dashboard.html" data-route="risk-dashboard.html">Risk</a></li>
            <li><a href="saxo-dashboard.html" data-route="saxo-dashboard.html">Bourse</a></li>
            <li><a href="rebalance.html" data-route="rebalance.html">Rebalance</a></li>
            <li><a href="execution.html" data-route="execution.html">Execution</a></li>
            <li><a href="settings.html" data-route="settings.html">Settings</a></li>
          </ul>
        </nav>
        
        <!-- Notification Badge for Human-in-the-loop -->
        <div class="notifications" id="nav-notifications">
          <button class="notification-badge" id="human-loop-badge" onclick="openHumanLoopPanel()" style="display: none;">
            <span class="badge-icon">🧠</span>
            <span class="badge-count" id="badge-count">0</span>
          </button>
        </div>
        
        <div class="spacer"></div>
        <!-- User Switcher (independent from Admin) -->
        <div class="user-switcher">
          <label style="font-size: 0.85em; color: var(--theme-text-muted); margin-right: 0.5rem;">Utilisateur:</label>
          <select id="user-selector" style="padding: 0.3rem 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--theme-border); background: var(--theme-bg); color: var(--theme-text); font-size: 0.9em;">
            <option value="demo">Chargement...</option>
          </select>
        </div>

        ${hasAdminRole ? `
        <div class="admin">
          <button class="admin-btn" id="admin-toggle" aria-haspopup="true" aria-expanded="false">Admin ▾</button>
          <div class="dropdown" id="admin-dropdown" role="menu">
            <a href="analytics-unified.html#ml">ML Command Center</a>
            <a href="analytics-unified.html#ml">Model Registry/Jobs</a>
            <div class="menu-separator"></div>
            <a href="settings.html#integrations">Imports & Connecteurs</a>
            <a href="debug-menu.html">Tools & Debug</a>
            <div class="menu-separator"></div>
            <a href="static/archive/index.html">Archive</a>
          </div>
        </div>
        ` : ''}
      </div>
    `;

    // Activer le lien courant
    const current = location.pathname.split('/').pop() || 'index.html';
    const links = header.querySelectorAll('nav a');
    links.forEach(a => {
      const route = a.getAttribute('data-route') || a.getAttribute('href');
      if (current.endsWith(route)) a.classList.add('active');
    });

    // Open the parent submenu if an item inside is active
    const activeLink = header.querySelector('nav a.active');
    if (activeLink) {
      const li = activeLink.closest('.has-submenu');
      if (li) li.classList.add('open');
    }

    // Improve submenu usability: keep open on hover with slight delay, allow first click to open on touch
    const submenus = header.querySelectorAll('.main-nav .has-submenu');
    submenus.forEach(li => {
      let hideTimer = null;
      li.addEventListener('mouseenter', () => {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        li.classList.add('open');
      });
      li.addEventListener('mouseleave', () => {
        hideTimer = setTimeout(() => li.classList.remove('open'), 200);
      });
      const trigger = li.querySelector(':scope > a');
      if (trigger) {
        trigger.addEventListener('click', (e) => {
          // If submenu is not open yet, open it and prevent navigation on first tap/click
          if (!li.classList.contains('open')) {
            e.preventDefault();
            li.classList.add('open');
          }
        });
      }
    });

    // Dropdown Admin (seulement si visible pour utilisateur RBAC)
    const toggle = header.querySelector('#admin-toggle');
    const dropdown = header.querySelector('#admin-dropdown');
    if (toggle && dropdown && hasAdminRole) {
      const closeDropdown = () => {
        dropdown.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      };
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(isOpen));
      });
      document.addEventListener('click', (e) => {
        if (!dropdown.classList.contains('open')) return;
        if (!dropdown.contains(e.target) && e.target !== toggle) closeDropdown();
      });
      window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDropdown();
      });
    }

    // ===== Human-in-the-loop Badge Management =====

    let websocketConnection = null;
    let fallbackInterval = null;

    function updateHumanLoopBadgeFromData(data) {
      const pendingCount = data.pending_decisions?.length || 0;

      const badge = document.getElementById('human-loop-badge');
      const countElement = document.getElementById('badge-count');

      if (pendingCount > 0) {
        countElement.textContent = pendingCount;
        badge.style.display = 'flex';
        badge.title = `${pendingCount} décision(s) IA en attente`;
      } else {
        badge.style.display = 'none';
      }
    }

    async function fallbackBadgeUpdate() {
      try {
        const response = await fetch('/api/phase3/intelligence/human-decisions');
        if (response.ok) {
          const data = await response.json();
          updateHumanLoopBadgeFromData(data);
        }
      } catch (error) {
        console.debug('Fallback badge update failed (normal if Phase 3C disabled):', error);
        const badge = document.getElementById('human-loop-badge');
        if (badge) badge.style.display = 'none';
      }
    }

    function initWebSocketConnection() {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/realtime/ws?client_id=nav_badge`;

        websocketConnection = new WebSocket(wsUrl);

        websocketConnection.onopen = () => {
          console.debug('WebSocket connection opened for navigation badge');

          // Subscribe to system events for human-loop notifications
          const subscribeMessage = {
            type: 'subscribe',
            subscriptions: ['system', 'all']
          };
          websocketConnection.send(JSON.stringify(subscribeMessage));

          // Clear fallback polling if WebSocket works
          if (fallbackInterval) {
            clearInterval(fallbackInterval);
            fallbackInterval = null;
          }
        };

        websocketConnection.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            // Handle human-loop decision updates
            if (message.event_type === 'system_status' || message.type === 'system_update') {
              // Trigger a fetch for latest decision count
              fallbackBadgeUpdate();
            }
          } catch (error) {
            console.debug('Error parsing WebSocket message:', error);
          }
        };

        websocketConnection.onclose = () => {
          console.debug('WebSocket connection closed, falling back to polling');
          websocketConnection = null;

          // Fall back to polling every 30 seconds
          if (!fallbackInterval) {
            fallbackInterval = setInterval(fallbackBadgeUpdate, 30000);
          }
        };

        websocketConnection.onerror = (error) => {
          console.debug('WebSocket error, will fall back to polling:', error);
        };

      } catch (error) {
        console.debug('Failed to initialize WebSocket, falling back to polling:', error);
        // Fall back to polling immediately
        if (!fallbackInterval) {
          fallbackInterval = setInterval(fallbackBadgeUpdate, 30000);
        }
      }
    }

    // Global function for opening human-loop panel
    window.openHumanLoopPanel = function () {
      // Check if we're on a page that can handle the panel
      if (window.location.pathname.includes('intelligence-dashboard.html')) {
        // Already on intelligence dashboard, just scroll to decisions
        const decisionsSection = document.querySelector('.pending-decisions');
        if (decisionsSection) {
          decisionsSection.scrollIntoView({ behavior: 'smooth' });
        }
      } else {
        // Redirect to intelligence dashboard
        window.location.href = 'intelligence-dashboard.html#decisions';
      }
    };

    // Initialize badge system - try WebSocket first, fall back to polling
    fallbackBadgeUpdate(); // Initial check
    initWebSocketConnection();

    // Initialize user switcher (always available)
    initUserSwitcher();

    // Load WealthContextBar after nav is initialized
    loadWealthContextBar();

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      if (websocketConnection) {
        websocketConnection.close();
      }
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
      }
    });

  } catch (err) {
    console.error('Nav init error:', err);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUnifiedNav);
} else {
  initUnifiedNav();
}

export { }; // ESM no-op
