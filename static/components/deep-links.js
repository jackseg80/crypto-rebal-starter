// Système de deep linking avec scroll et highlight (ES module)
// Gère les ancres, scrollIntoView avec offset header, et highlighting temporaire

const initDeepLinks = (sectionAnchors = {}) => {
  try {
    // Style pour highlight temporaire
    if (!document.querySelector('#deep-links-style')) {
      const style = document.createElement('style');
      style.id = 'deep-links-style';
      style.textContent = `
        .is-target {
          background: color-mix(in oklab, var(--brand-primary) 15%, transparent) !important;
          border-left: 3px solid var(--brand-primary);
          padding-left: calc(1rem - 3px);
          transition: all 0.3s ease;
          animation: targetHighlight 2s ease-out;
        }
        @keyframes targetHighlight {
          0% { background: color-mix(in oklab, var(--brand-primary) 25%, transparent); }
          100% { background: color-mix(in oklab, var(--brand-primary) 15%, transparent); }
        }
      `;
      document.head.appendChild(style);
    }

    // Hauteur header sticky pour offset
    const getHeaderOffset = () => {
      const header = document.querySelector('.app-header');
      return header ? header.offsetHeight + 20 : 80; // 20px margin supplémentaire
    };

    // Highlight temporaire d'une section
    const highlightSection = (element) => {
      // Supprimer anciens highlights
      document.querySelectorAll('.is-target').forEach(el => {
        el.classList.remove('is-target');
      });

      if (element) {
        element.classList.add('is-target');
        setTimeout(() => {
          element.classList.remove('is-target');
        }, 2000);
      }
    };

    // Scroll vers une section avec offset
    const scrollToSection = (targetId) => {
      const element = document.getElementById(targetId);
      if (element) {
        const headerOffset = getHeaderOffset();
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

        window.scrollTo({
          top: offsetPosition,
          behavior: 'smooth'
        });

        highlightSection(element);
        return true;
      }
      return false;
    };

    // Gérer les clics sur liens internes avec ancres
    const handleAnchorLinks = () => {
      document.addEventListener('click', (e) => {
        const link = e.target.closest('a[href*="#"]');
        if (!link) return;

        const href = link.getAttribute('href');
        const [, anchor] = href.split('#');

        if (anchor && (href.startsWith('#') || href.includes(location.pathname))) {
          e.preventDefault();
          scrollToSection(anchor);
          history.pushState(null, '', `#${anchor}`);
        }
      });
    };

    // Gérer l'ancre au chargement de page
    const handleInitialAnchor = () => {
      const hash = location.hash.slice(1);
      if (hash) {
        // Attendre que le DOM soit complètement chargé
        setTimeout(() => {
          scrollToSection(hash);
        }, 100);
      }
    };

    // Créer les sections avec ancres si elles n'existent pas
    const createAnchors = () => {
      Object.entries(sectionAnchors).forEach(([anchorId, title]) => {
        let section = document.getElementById(anchorId);
        if (!section) {
          // Chercher par titre via filtrage JS (pas de :contains CSS)
          const headings = document.querySelectorAll('h1, h2, h3');
          const existingElement = Array.from(headings).find(el =>
            el.textContent.includes(title)
          );

          if (existingElement) {
            section = existingElement.closest('section, div, main') || existingElement;
            section.id = anchorId;
            console.debug(`🔗 Deep link anchor created: ${anchorId} → ${title}`);
          } else {
            // Ne pas créer de section placeholder - just skip
            console.debug(`🔗 Deep link anchor skipped (no content): ${anchorId} → ${title}`);
          }
        }
      });
    };

    // Initialisation
    createAnchors();
    handleInitialAnchor();
    handleAnchorLinks();

    // Gérer les changements d'URL (back/forward)
    window.addEventListener('popstate', () => {
      const hash = location.hash.slice(1);
      if (hash) {
        scrollToSection(hash);
      }
    });

    // Export pour usage externe
    window.scrollToSection = scrollToSection;

  } catch (error) {
    debugLogger.error('Deep links init error:', error);
  }
};

// Auto-init si DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initDeepLinks());
} else {
  initDeepLinks();
}

export { initDeepLinks };