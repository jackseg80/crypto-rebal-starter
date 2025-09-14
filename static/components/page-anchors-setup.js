// Script d'initialisation des ancres pour toutes les pages canoniques
// Import automatique selon la page actuelle

const pageAnchors = {
  'dashboard.html': {
    'overview': 'Vue d\'ensemble',
    'crypto': 'Crypto Portfolio',
    'bourse': 'Actions & ETF',
    'banque': 'Comptes bancaires',
    'divers': 'Actifs divers',
    'fx': 'Devises & Changes'
  },
  'analytics-unified.html': {
    'unified': 'Analytics Unifiés',
    'ml': 'Machine Learning',
    'cycles': 'Analyse des Cycles',
    'performance': 'Performance',
    'monitoring': 'Monitoring'
  },
  'risk-dashboard.html': {
    'governance': 'Gouvernance',
    'stress': 'Tests de Stress',
    'risk-attribution': 'Attribution des Risques',
    'limits': 'Limites & Contrôles'
  },
  'rebalance.html': {
    'proposed-targets': 'Objectifs Proposés',
    'bourse': 'Rebalance Bourse',
    'funding-plan': 'Plan de Financement',
    'dca-schedule': 'Planning DCA',
    'constraints': 'Contraintes'
  },
  'execution.html': {
    'orders': 'Ordres',
    'history': 'Historique',
    'costs': 'Coûts',
    'venues': 'Plateformes'
  },
  'settings.html': {
    'integrations': 'Intégrations',
    'security': 'Sécurité',
    'logs': 'Logs',
    'monitoring': 'Monitoring',
    'tools': 'Outils'
  }
};

// Auto-détection de la page et initialisation
const currentPage = location.pathname.split('/').pop() || 'index.html';
const anchors = pageAnchors[currentPage];

if (anchors) {
  import('./deep-links.js').then(({ initDeepLinks }) => {
    initDeepLinks(anchors);
  });
}