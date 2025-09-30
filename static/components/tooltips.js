// Système de tooltips réutilisable pour les tuiles
// Usage: <div data-tooltip="Description de la fonctionnalité">Contenu</div>

const initTooltips = () => {
  try {
    if (window.__tooltipsInitialized) return;
    window.__tooltipsInitialized = true;

    // Styles CSS pour les tooltips
    const style = document.createElement('style');
    style.textContent = `
      [data-tooltip] {
        position: relative;
        cursor: help;
      }

      [data-tooltip]:hover::after,
      [data-tooltip]:hover::before {
        opacity: 1;
        pointer-events: auto;
        visibility: visible;
      }

      [data-tooltip]::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-8px);
        background: var(--theme-surface);
        color: var(--theme-text);
        border: 1px solid var(--theme-border);
        border-radius: var(--radius-md);
        padding: 8px 12px;
        font-size: 13px;
        font-weight: 500;
        line-height: 1.4;
        white-space: normal;
        max-width: 280px;
        width: max-content;
        box-shadow: var(--shadow-lg);
        z-index: 1000;
        opacity: 0;
        pointer-events: none;
        visibility: hidden;
        transition: opacity 0.2s ease, transform 0.2s ease;
      }

      [data-tooltip]::before {
        content: '';
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-2px);
        width: 0;
        height: 0;
        border-left: 6px solid transparent;
        border-right: 6px solid transparent;
        border-top: 6px solid var(--theme-border);
        z-index: 1001;
        opacity: 0;
        pointer-events: none;
        visibility: hidden;
        transition: opacity 0.2s ease;
      }

      /* Tooltip sur les cartes (positionnement ajusté) */
      .card[data-tooltip]::after {
        bottom: auto;
        top: 100%;
        transform: translateX(-50%) translateY(8px);
        margin-top: 4px;
      }

      .card[data-tooltip]::before {
        bottom: auto;
        top: 100%;
        transform: translateX(-50%) translateY(2px);
        border-top: none;
        border-bottom: 6px solid var(--theme-border);
        margin-top: 4px;
      }

      /* Responsive - mobile */
      @media (max-width: 768px) {
        [data-tooltip]::after {
          max-width: 240px;
          font-size: 12px;
          padding: 6px 10px;
        }
        
        .card[data-tooltip]::after {
          position: fixed;
          top: auto;
          bottom: 20px;
          left: 10px;
          right: 10px;
          max-width: none;
          transform: none;
        }
        
        .card[data-tooltip]::before {
          display: none;
        }
      }

      /* Variantes de tooltips avec sources de données */
      [data-tooltip][data-source]::after {
        content: attr(data-tooltip) "\\A\\ASource: " attr(data-source);
        white-space: pre-line;
      }

      [data-source]::after {
        border-left: 3px solid var(--brand-accent);
      }

      /* Animation d'apparition */
      [data-tooltip]:hover::after {
        animation: tooltipFadeIn 0.2s ease forwards;
      }

      @keyframes tooltipFadeIn {
        from {
          opacity: 0;
          transform: translateX(-50%) translateY(-4px);
        }
        to {
          opacity: 1;
          transform: translateX(-50%) translateY(-8px);
        }
      }

      .card[data-tooltip]:hover::after {
        animation: tooltipFadeInDown 0.2s ease forwards;
      }

      @keyframes tooltipFadeInDown {
        from {
          opacity: 0;
          transform: translateX(-50%) translateY(4px);
        }
        to {
          opacity: 1;
          transform: translateX(-50%) translateY(8px);
        }
      }
    `;
    document.head.appendChild(style);

    // Améliorer l'accessibilité
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const tooltips = document.querySelectorAll('[data-tooltip]:hover');
        tooltips.forEach(el => el.blur());
      }
    });

    debugLogger.debug('📱 Tooltips système initialisé');
  } catch (err) {
    console.error('Erreur lors de l\'initialisation des tooltips:', err);
  }
};

// Fonction utilitaire pour ajouter des tooltips dynamiquement
const addTooltip = (element, text, source = null) => {
  if (!element) return;
  element.setAttribute('data-tooltip', text);
  if (source) {
    element.setAttribute('data-source', source);
  }
};

// Auto-initialisation
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTooltips);
} else {
  initTooltips();
}

// Export pour utilisation dans d'autres modules
if (typeof window !== 'undefined') {
  window.addTooltip = addTooltip;
}

export { initTooltips, addTooltip };