/**
 * Flyout Panel Component - Reusable
 *
 * Crée un panneau latéral détachable avec système hover/pin
 *
 * @example
 * import { createFlyoutPanel } from './components/flyout-panel.js';
 *
 * createFlyoutPanel({
 *   sourceSelector: '.sidebar',
 *   title: '🎯 Risk Snapshot',
 *   handleText: '🎯 Risk',
 *   persistKey: 'risk_dashboard_flyout',
 *   removeToggleButton: true,
 *   pushContainers: ['.dashboard-layout', '#governance-container', '.controls']
 * });
 */

/**
 * Crée et initialise un flyout panel
 * @param {Object} options - Configuration options
 * @param {string} options.sourceSelector - Sélecteur CSS du contenu source à déplacer
 * @param {string} options.title - Titre du panneau (défaut: "Panel")
 * @param {string} options.handleText - Texte de la poignée (défaut: "📋 Info")
 * @param {string} options.persistKey - Clé localStorage pour persistance (défaut: "flyout_panel")
 * @param {boolean} options.removeToggleButton - Supprimer le bouton toggle du source (défaut: true)
 * @param {string[]} options.pushContainers - Sélecteurs CSS des containers à pousser quand épinglé (défaut: [])
 * @param {number} options.baseOffset - Décalage de base en px (défaut: 40)
 * @param {number} options.pinnedOffset - Décalage additionnel quand épinglé en px (défaut: 340)
 * @returns {HTMLElement|null} - L'élément flyout créé ou null si disabled
 */
export function createFlyoutPanel(options = {}) {
  const {
    sourceSelector,
    title = 'Panel',
    handleText = '📋 Info',
    persistKey = 'flyout_panel',
    removeToggleButton = true,
    pushContainers = [],
    baseOffset = 40,
    pinnedOffset = 340
  } = options;

  // Feature flag check
  const flyoutEnabled = localStorage.getItem('__ui.flyout.enabled') === '1';
  if (!flyoutEnabled) {
    console.log('🎛️ Flyout panel disabled (set __ui.flyout.enabled=1 to enable)');
    return null;
  }

  // Ajouter classe au body pour le décalage
  document.body.classList.add('flyout-enabled');

  // Créer le flyout
  const flyout = document.createElement('div');
  flyout.className = 'flyout-panel';
  flyout.innerHTML = `
    <div class="flyout-handle">${handleText}</div>
    <div class="flyout-header">
      <h2>${title}</h2>
      <button class="pin-btn" type="button" aria-pressed="false">📌 Épingler</button>
    </div>
    <div class="flyout-content" id="flyout-content-${persistKey}"></div>
  `;

  document.body.appendChild(flyout);

  // Déplacer le contenu source
  const source = document.querySelector(sourceSelector);
  const flyoutContent = flyout.querySelector(`#flyout-content-${persistKey}`);

  if (source && flyoutContent) {
    // Déplacer tous les enfants (garde les event listeners et mises à jour)
    while (source.firstChild) {
      flyoutContent.appendChild(source.firstChild);
    }

    // Masquer complètement la source et ajuster le layout
    source.style.display = 'none';
    const layout = document.querySelector('.dashboard-layout');
    if (layout) {
      layout.style.gridTemplateColumns = '1fr'; // Une seule colonne
    }

    console.log(`✅ Source content moved from "${sourceSelector}" to flyout`);
  }

  // Supprimer le bouton toggle si demandé
  if (removeToggleButton) {
    const toggleBtn = flyoutContent.querySelector('#sidebar-toggle');
    if (toggleBtn) {
      toggleBtn.remove();
      console.log('✅ Toggle button removed from flyout');
    }
  }

  // Fonction pour push/unpush le contenu
  function updateLayoutPush(pinned) {
    const totalOffset = pinned ? (baseOffset + pinnedOffset) : 0;

    pushContainers.forEach(selector => {
      const container = document.querySelector(selector);
      if (container) {
        container.style.marginLeft = pinned ? `${totalOffset}px` : '';
      }
    });
  }

  // Gérer le bouton pin
  const pinBtn = flyout.querySelector('.pin-btn');
  const fullPersistKey = `__ui.flyout.${persistKey}.pinned`;
  const isPinned = localStorage.getItem(fullPersistKey) === 'true';

  if (isPinned) {
    flyout.classList.add('is-pinned');
    pinBtn.setAttribute('aria-pressed', 'true');
    pinBtn.textContent = '📌 Épinglé';
    updateLayoutPush(true);
  }

  pinBtn.addEventListener('click', () => {
    const currentlyPinned = flyout.classList.contains('is-pinned');
    const willBePinned = !currentlyPinned;

    flyout.classList.toggle('is-pinned');
    pinBtn.setAttribute('aria-pressed', String(willBePinned));
    pinBtn.textContent = willBePinned ? '📌 Épinglé' : '📌 Épingler';
    localStorage.setItem(fullPersistKey, String(willBePinned));

    updateLayoutPush(willBePinned);
  });

  console.log(`✅ Flyout Panel initialized (persist key: ${fullPersistKey})`);
  return flyout;
}

/**
 * Détruit un flyout panel existant
 * @param {string} persistKey - La clé de persistance du flyout à détruire
 */
export function destroyFlyoutPanel(persistKey = 'flyout_panel') {
  const flyout = document.querySelector('.flyout-panel');
  if (flyout) {
    flyout.remove();
    document.body.classList.remove('flyout-enabled');
    console.log(`✅ Flyout Panel destroyed (key: ${persistKey})`);
  }
}
