// Composant de navigation unifié (ES module, zéro dépendance)
// Injecte un <header class="app-header"> sticky avec liens actifs et menu Admin.

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
      @media (max-width: 1024px) { .app-header nav { display: flex; flex-wrap: wrap; gap: .25rem; } .app-header .nav-inner { gap: .5rem; } }
      @media (max-width: 720px) { .app-header nav a { padding: .4rem .6rem; font-size: 14px; } }
    `;
    document.head.appendChild(style);

    const header = document.createElement('header');
    header.className = 'app-header';
    header.innerHTML = `
      <div class="nav-inner">
        <div class="brand">Crypto Rebal</div>
        <nav class="main-nav" aria-label="Navigation principale">
          <ul class="menu">
            <li><a href="dashboard.html" data-route="dashboard.html">Dashboard</a></li>
            <li class="has-submenu">
              <a href="analytics-unified.html" data-route="analytics-unified.html">Analytics</a>
              <div class="submenu" role="menu">
                <a href="risk-dashboard.html" data-route="risk-dashboard.html">Risk Dashboard</a>
                <a href="performance-monitor.html" data-route="performance-monitor.html">Performance Monitor</a>
                <a href="advanced-analytics.html" data-route="advanced-analytics.html">Advanced Analytics</a>
                <a href="cycle-analysis.html" data-route="cycle-analysis.html">Cycle Analysis</a>
                <a href="portfolio-optimization.html" data-route="portfolio-optimization.html">Portfolio Optimization</a>
              </div>
            </li>
            <li><a href="rebalance.html" data-route="rebalance.html">Rebalancing</a></li>
            <li class="has-submenu">
              <a href="ai-dashboard.html" data-route="ai-dashboard.html">AI</a>
              <div class="submenu" role="menu">
                <a href="ai-dashboard.html" data-route="ai-dashboard.html">AI Dashboard</a>
                <a href="ml-showcase.html" data-route="ml-showcase.html">ML Showcase</a>
              </div>
            </li>
            <li class="has-submenu">
              <a href="execution.html" data-route="execution.html">Execution</a>
              <div class="submenu" role="menu">
                <a href="execution.html" data-route="execution.html">Live / Plan</a>
                <a href="execution_history.html" data-route="execution_history.html">History</a>
              </div>
            </li>
            <li><a href="settings.html" data-route="settings.html">Settings</a></li>
          </ul>
        </nav>
        <div class="spacer"></div>
        <div class="admin">
          <button class="admin-btn" id="admin-toggle" aria-haspopup="true" aria-expanded="false">Admin ▾</button>
          <div class="dropdown" id="admin-dropdown" role="menu">
            <a href="backtesting.html">Backtesting</a>
            <a href="alias-manager.html">Alias Manager</a>
            <a href="debug-menu.html">Debug</a>
          </div>
        </div>
      </div>
    `;

    const maybeInsertBefore = document.body.firstElementChild;
    if (maybeInsertBefore) {
      document.body.insertBefore(header, maybeInsertBefore);
    } else {
      document.body.appendChild(header);
    }

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

    // Dropdown Admin
    const toggle = header.querySelector('#admin-toggle');
    const dropdown = header.querySelector('#admin-dropdown');
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
  } catch (err) {
    console.error('Nav init error:', err);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUnifiedNav);
} else {
  initUnifiedNav();
}

export {}; // ESM no-op
