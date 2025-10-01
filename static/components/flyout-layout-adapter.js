// static/components/flyout-layout-adapter.js
// Adapte automatiquement le layout de la page quand la sidebar flyout est épinglée

/**
 * Active l'adaptation automatique du layout pour les pages avec flyout-panel
 * @param {string} mainSelector - Sélecteur CSS du conteneur principal à décaler (ex: '.container', '.dashboard-layout')
 * @param {object} options - Options de configuration
 * @param {number} options.offset - Offset supplémentaire en pixels (défaut: 20px de padding)
 * @param {string} options.transition - Durée de la transition CSS (défaut: '0.3s ease')
 */
export function enableFlyoutLayoutAdapter(mainSelector = '.container', options = {}) {
  const {
    offset = 20,
    transition = '0.3s ease'
  } = options;

  const mainEl = document.querySelector(mainSelector);
  if (!mainEl) {
    console.warn(`[FlyoutLayoutAdapter] Element not found: ${mainSelector}`);
    return;
  }

  // Ajouter la transition CSS
  mainEl.style.transition = `margin-left ${transition}, margin-right ${transition}`;

  // Écouter les changements d'état du flyout
  document.addEventListener('flyout-state-change', (e) => {
    const { pinned, width, position } = e.detail;

    if (pinned) {
      if (position === 'left') {
        mainEl.style.marginLeft = `${width + offset}px`;
        mainEl.style.marginRight = '0';
      } else if (position === 'right') {
        mainEl.style.marginRight = `${width + offset}px`;
        mainEl.style.marginLeft = '0';
      }
    } else {
      mainEl.style.marginLeft = '0';
      mainEl.style.marginRight = '0';
    }
  });

  // Déclencher l'état initial
  const flyoutPanel = document.querySelector('flyout-panel');
  if (flyoutPanel) {
    const persistKey = flyoutPanel.getAttribute('persist-key') || 'flyout';
    const persisted = JSON.parse(localStorage.getItem(`flyout:${persistKey}`) || '{}');
    if (persisted.pinned) {
      const width = Number(flyoutPanel.getAttribute('width')) || 340;
      const position = flyoutPanel.getAttribute('position') || 'left';
      if (position === 'left') {
        mainEl.style.marginLeft = `${width + offset}px`;
      } else {
        mainEl.style.marginRight = `${width + offset}px`;
      }
    }
  }
}
