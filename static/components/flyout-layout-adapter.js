// static/components/flyout-layout-adapter.js
// Adapte automatiquement le layout de la page quand la sidebar flyout est épinglée

/**
 * Active l'adaptation automatique du layout pour les pages avec flyout-panel
 * @param {string} mainSelector - Sélecteur CSS du conteneur principal à décaler (ex: '.container', '.dashboard-layout')
 * @param {object} options - Options de configuration
 * @param {number} options.offset - Offset supplémentaire en pixels (défaut: 20px de padding)
 * @param {string} options.transition - Durée de la transition CSS (défaut: '0.3s ease')
 */
export function enableFlyoutLayoutAdapter(mainSelector = 'body', options = {}) {
  const {
    offset = 20,
    transition = '0.3s ease'
  } = options;

  const init = () => {
    const mainEl = document.querySelector(mainSelector);
    if (!mainEl) {
      debugLogger.warn(`[FlyoutLayoutAdapter] Element not found: ${mainSelector}`);
      return;
    }

    debugLogger.debug(`[FlyoutLayoutAdapter] Initializing for ${mainSelector}`, { offset, transition });

    // Ajouter la transition CSS et un padding permanent à gauche pour la poignée du flyout
    mainEl.style.transition = `margin-left ${transition}, margin-right ${transition}`;
    mainEl.style.paddingLeft = '48px'; // Espace pour la poignée du flyout (handle)

    // Écouter les changements d'état du flyout
    document.addEventListener('flyout-state-change', (e) => {
      const { pinned, width, position } = e.detail;
      debugLogger.debug('[FlyoutLayoutAdapter] State change:', { pinned, width, position });

      if (pinned) {
        if (position === 'left') {
          mainEl.style.marginLeft = `${width + offset}px`;
          mainEl.style.marginRight = 'auto';
          debugLogger.debug(`[FlyoutLayoutAdapter] Applied margin-left: ${width + offset}px`);
        } else if (position === 'right') {
          mainEl.style.marginRight = `${width + offset}px`;
          mainEl.style.marginLeft = 'auto';
          debugLogger.debug(`[FlyoutLayoutAdapter] Applied margin-right: ${width + offset}px`);
        }
      } else {
        mainEl.style.marginLeft = 'auto';
        mainEl.style.marginRight = 'auto';
        debugLogger.debug('[FlyoutLayoutAdapter] Reset margins to auto');
      }
    });

    // Déclencher l'état initial après un court délai pour laisser le Web Component s'initialiser
    setTimeout(() => {
      const flyoutPanel = document.querySelector('flyout-panel');
      if (flyoutPanel) {
        const persistKey = flyoutPanel.getAttribute('persist-key') || 'flyout';
        const persisted = JSON.parse(localStorage.getItem(`flyout:${persistKey}`) || '{}');
        debugLogger.debug('[FlyoutLayoutAdapter] Initial state from localStorage:', { persistKey, persisted });

        if (persisted.pinned) {
          const width = Number(flyoutPanel.getAttribute('width')) || 340;
          const position = flyoutPanel.getAttribute('position') || 'left';
          if (position === 'left') {
            mainEl.style.marginLeft = `${width + offset}px`;
            mainEl.style.marginRight = 'auto';
            debugLogger.debug(`[FlyoutLayoutAdapter] Initial margin-left: ${width + offset}px`);
          } else {
            mainEl.style.marginRight = `${width + offset}px`;
            mainEl.style.marginLeft = 'auto';
            debugLogger.debug(`[FlyoutLayoutAdapter] Initial margin-right: ${width + offset}px`);
          }
        } else {
          mainEl.style.marginLeft = 'auto';
          mainEl.style.marginRight = 'auto';
        }
      } else {
        debugLogger.warn('[FlyoutLayoutAdapter] flyout-panel element not found');
      }
    }, 100);
  };

  // Attendre que le DOM soit prêt
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}
