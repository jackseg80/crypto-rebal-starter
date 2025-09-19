// Système de redirections douces vers les ancres canoniques (ES module)
// Redirige les anciennes pages vers les nouvelles ancres sans 404

const legacyRedirects = {
  // AI & Intelligence pages → analytics-unified.html#ml
  'ai-dashboard.html': 'analytics-unified.html#ml',
  'intelligence-dashboard.html': 'analytics-unified.html#ml',
  'unified-ml-dashboard.html': 'analytics-unified.html#ml',
  'advanced-analytics.html': 'analytics-unified.html#ml',

  // Performance & Monitoring → analytics-unified.html
  'performance-monitor.html': 'analytics-unified.html#performance',
  'monitoring-unified.html': 'monitoring.html',
  'unified-scores.html': 'analytics-unified.html#unified',

  // Cycle analysis → analytics-unified.html#cycles
  'cycle-analysis.html': 'analytics-unified.html#cycles',

  // Portfolio optimization → dashboard.html#overview
  'portfolio-optimization.html': 'dashboard.html#overview',

  // Execution history → execution.html#history
  'execution_history.html': 'execution.html#history',

  // Tools & debug → settings.html#tools
  'debug-menu.html': 'settings.html#tools',
  'alias-manager.html': 'settings.html#tools',

  // Backtesting → analytics-unified.html#performance
  'backtesting.html': 'analytics-unified.html#performance'
};

const createRedirectPage = (targetUrl) => {
  const [targetPage, targetAnchor] = targetUrl.split('#');
  const anchorText = targetAnchor ? `#${targetAnchor}` : '';

  return `<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redirection - Crypto Rebalancer</title>
    <link rel="stylesheet" href="shared-theme.css">
    <meta http-equiv="refresh" content="3;url=${targetUrl}">
    <style>
        .redirect-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            text-align: center;
            padding: 2rem;
            background: var(--theme-bg);
        }
        .redirect-message {
            background: var(--theme-surface);
            border: 1px solid var(--theme-border);
            border-radius: var(--radius-lg);
            padding: 2rem;
            max-width: 600px;
            box-shadow: var(--shadow-lg);
        }
        .redirect-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--brand-primary);
            margin-bottom: 1rem;
        }
        .redirect-text {
            color: var(--theme-text);
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        .redirect-link {
            background: var(--brand-primary);
            color: white;
            text-decoration: none;
            padding: 0.75rem 1.5rem;
            border-radius: var(--radius-md);
            font-weight: 600;
            display: inline-block;
            transition: background var(--transition-fast);
        }
        .redirect-link:hover {
            background: color-mix(in oklab, var(--brand-primary) 80%, black);
        }
        .spinner {
            width: 24px;
            height: 24px;
            border: 2px solid var(--theme-border);
            border-top: 2px solid var(--brand-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="redirect-container">
        <div class="redirect-message">
            <div class="spinner"></div>
            <h1 class="redirect-title">🔄 Redirection en cours</h1>
            <p class="redirect-text">
                Cette page a été déplacée vers la nouvelle navigation consolidée.<br>
                Vous allez être redirigé vers <strong>${targetPage}${anchorText}</strong> dans quelques secondes.
            </p>
            <a href="${targetUrl}" class="redirect-link">Accéder maintenant</a>
        </div>
    </div>

    <script>
        // Redirection immédiate si JavaScript activé
        setTimeout(() => {
            window.location.replace('${targetUrl}');
        }, 1500);
    </script>
</body>
</html>`;
};

// Fonction pour vérifier et rediriger si nécessaire
const checkLegacyRedirect = () => {
  const currentPage = location.pathname.split('/').pop();
  const redirectTarget = legacyRedirects[currentPage];

  if (redirectTarget) {
    console.info(\`🔄 Legacy redirect: \${currentPage} → \${redirectTarget}\`);

    // Utiliser replace pour éviter l'ajout à l'historique
    window.location.replace(redirectTarget);
    return true;
  }

  return false;
};

// Fonction pour générer tous les fichiers de redirection
const generateRedirectFiles = () => {
  const files = {};

  Object.entries(legacyRedirects).forEach(([legacyPage, targetUrl]) => {
    files[legacyPage] = createRedirectPage(targetUrl);
  });

  return files;
};

// Auto-check au chargement
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', checkLegacyRedirect);
} else {
  checkLegacyRedirect();
}

export { legacyRedirects, checkLegacyRedirect, generateRedirectFiles };
