/**
 * Lazy Loader - Système de chargement paresseux pour optimiser les performances
 * Charge les ressources (scripts, styles, images) seulement quand nécessaire
 */

class LazyLoader {
    constructor() {
        this.loadedScripts = new Set();
        this.loadedStyles = new Set();
        this.pendingLoads = new Map();
        this.intersectionObserver = this.setupIntersectionObserver();
        this.initializeLazyLoading();
    }

    /**
     * Configurer l'Intersection Observer pour le lazy loading visuel
     */
    setupIntersectionObserver() {
        if (typeof IntersectionObserver === 'undefined') {
            console.warn('IntersectionObserver not supported, falling back to immediate loading');
            return null;
        }

        return new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadVisibleElement(entry.target);
                }
            });
        }, {
            rootMargin: '50px',
            threshold: 0.1
        });
    }

    /**
     * Initialiser le lazy loading pour tous les éléments marqués
     */
    initializeLazyLoading() {
        // Charger les éléments avec l'attribut data-lazy-load
        document.querySelectorAll('[data-lazy-load]').forEach(el => {
            if (this.intersectionObserver) {
                this.intersectionObserver.observe(el);
            } else {
                // Fallback: charger immédiatement
                this.loadVisibleElement(el);
            }
        });

        // Écouter les nouveaux éléments ajoutés au DOM
        this.observeNewElements();
    }

    /**
     * Observer les nouveaux éléments ajoutés dynamiquement
     */
    observeNewElements() {
        if (typeof MutationObserver !== 'undefined') {
            const mutationObserver = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            const lazyElements = node.querySelectorAll('[data-lazy-load]');
                            lazyElements.forEach(el => {
                                if (this.intersectionObserver) {
                                    this.intersectionObserver.observe(el);
                                } else {
                                    this.loadVisibleElement(el);
                                }
                            });
                        }
                    });
                });
            });

            mutationObserver.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    }

    /**
     * Charger un élément devenu visible
     */
    async loadVisibleElement(element) {
        const lazyType = element.dataset.lazyLoad;
        const src = element.dataset.lazySrc;

        if (this.intersectionObserver) {
            this.intersectionObserver.unobserve(element);
        }

        try {
            switch (lazyType) {
                case 'script':
                    await this.loadScript(src);
                    break;
                case 'style':
                    await this.loadStyle(src);
                    break;
                case 'image':
                    await this.loadImage(element, src);
                    break;
                case 'component':
                    await this.loadComponent(element);
                    break;
                default:
                    console.warn(`Unknown lazy load type: ${lazyType}`);
            }

            element.classList.add('lazy-loaded');
            element.dispatchEvent(new CustomEvent('lazyLoaded'));

        } catch (error) {
            console.error(`Failed to lazy load ${lazyType}:`, error);
            element.classList.add('lazy-error');
        }
    }

    /**
     * Charger un script de manière paresseuse
     */
    async loadScript(src) {
        if (this.loadedScripts.has(src)) {
            return Promise.resolve();
        }

        if (this.pendingLoads.has(src)) {
            return this.pendingLoads.get(src);
        }

        const promise = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.async = true;
            
            script.onload = () => {
                this.loadedScripts.add(src);
                this.pendingLoads.delete(src);
                resolve();
            };

            script.onerror = () => {
                this.pendingLoads.delete(src);
                reject(new Error(`Failed to load script: ${src}`));
            };

            document.head.appendChild(script);
        });

        this.pendingLoads.set(src, promise);
        return promise;
    }

    /**
     * Charger une feuille de style de manière paresseuse
     */
    async loadStyle(href) {
        if (this.loadedStyles.has(href)) {
            return Promise.resolve();
        }

        if (this.pendingLoads.has(href)) {
            return this.pendingLoads.get(href);
        }

        const promise = new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;

            link.onload = () => {
                this.loadedStyles.add(href);
                this.pendingLoads.delete(href);
                resolve();
            };

            link.onerror = () => {
                this.pendingLoads.delete(href);
                reject(new Error(`Failed to load stylesheet: ${href}`));
            };

            document.head.appendChild(link);
        });

        this.pendingLoads.set(href, promise);
        return promise;
    }

    /**
     * Charger une image de manière paresseuse
     */
    async loadImage(imgElement, src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            
            img.onload = () => {
                imgElement.src = src;
                imgElement.classList.remove('lazy-placeholder');
                resolve();
            };

            img.onerror = () => {
                imgElement.classList.add('lazy-error');
                reject(new Error(`Failed to load image: ${src}`));
            };

            img.src = src;
        });
    }

    /**
     * Charger un composant dynamiquement
     */
    async loadComponent(element) {
        const componentName = element.dataset.lazyComponent;
        const componentSrc = element.dataset.lazySrc;

        if (componentSrc) {
            await this.loadScript(componentSrc);
        }

        if (componentName && window[componentName]) {
            try {
                const component = new window[componentName](element);
                if (typeof component.init === 'function') {
                    await component.init();
                }
            } catch (error) {
                console.error(`Failed to initialize component ${componentName}:`, error);
            }
        }
    }

    /**
     * Précharger des ressources critiques
     */
    async preload(resources) {
        const preloadPromises = resources.map(resource => {
            if (typeof resource === 'string') {
                return this.loadScript(resource);
            } else if (resource.type === 'script') {
                return this.loadScript(resource.src);
            } else if (resource.type === 'style') {
                return this.loadStyle(resource.href);
            }
        });

        return Promise.allSettled(preloadPromises);
    }

    /**
     * Charger des ressources en lot avec priorité
     */
    async loadBatch(resources, options = {}) {
        const { priority = 'normal', delay = 0 } = options;

        if (delay > 0) {
            await new Promise(resolve => setTimeout(resolve, delay));
        }

        const promises = resources.map(resource => {
            if (resource.type === 'script') {
                return this.loadScript(resource.src);
            } else if (resource.type === 'style') {
                return this.loadStyle(resource.href);
            }
        });

        return Promise.allSettled(promises);
    }

    /**
     * Obtenir les statistiques de chargement
     */
    getStats() {
        return {
            loadedScripts: this.loadedScripts.size,
            loadedStyles: this.loadedStyles.size,
            pendingLoads: this.pendingLoads.size,
            scriptList: Array.from(this.loadedScripts),
            styleList: Array.from(this.loadedStyles)
        };
    }

    /**
     * Nettoyer les ressources
     */
    cleanup() {
        if (this.intersectionObserver) {
            this.intersectionObserver.disconnect();
        }
        this.pendingLoads.clear();
    }
}

/**
 * Utilitaires pour marquer les éléments pour le lazy loading
 */
class LazyUtils {
    /**
     * Créer un élément script lazy
     */
    static createLazyScript(src, container = document.body) {
        const placeholder = document.createElement('div');
        placeholder.dataset.lazyLoad = 'script';
        placeholder.dataset.lazySrc = src;
        placeholder.style.display = 'none';
        container.appendChild(placeholder);
        return placeholder;
    }

    /**
     * Créer un élément style lazy
     */
    static createLazyStyle(href, container = document.head) {
        const placeholder = document.createElement('div');
        placeholder.dataset.lazyLoad = 'style';
        placeholder.dataset.lazySrc = href;
        placeholder.style.display = 'none';
        container.appendChild(placeholder);
        return placeholder;
    }

    /**
     * Créer une image lazy avec placeholder
     */
    static createLazyImage(src, alt = '', className = '') {
        const img = document.createElement('img');
        img.dataset.lazyLoad = 'image';
        img.dataset.lazySrc = src;
        img.alt = alt;
        img.className = `lazy-placeholder ${className}`.trim();
        
        // Placeholder SVG en base64 pour éviter les requêtes
        img.src = 'data:image/svg+xml;base64,' + btoa(`
            <svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
                <rect width="100%" height="100%" fill="#f0f0f0"/>
                <text x="50%" y="50%" text-anchor="middle" dy=".3em" font-family="sans-serif" font-size="14" fill="#999">
                    Chargement...
                </text>
            </svg>
        `);
        
        return img;
    }

    /**
     * Convertir les scripts existants en lazy loading
     */
    static convertScriptsToLazy(selector = 'script[data-lazy="true"]') {
        document.querySelectorAll(selector).forEach(script => {
            const src = script.src;
            if (src) {
                const placeholder = LazyUtils.createLazyScript(src, script.parentNode);
                script.remove();
            }
        });
    }

    /**
     * Marquer les composants pour le lazy loading
     */
    static markComponentForLazyLoad(element, componentName, componentSrc = null) {
        element.dataset.lazyLoad = 'component';
        element.dataset.lazyComponent = componentName;
        if (componentSrc) {
            element.dataset.lazySrc = componentSrc;
        }
    }
}

// Instance globale
const lazyLoader = new LazyLoader();

// Export pour utilisation en module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LazyLoader, LazyUtils, lazyLoader };
}

// Mise à disposition globale
window.LazyLoader = LazyLoader;
window.LazyUtils = LazyUtils;
window.lazyLoader = lazyLoader;

// Styles CSS pour le lazy loading
const lazyStyles = `
    .lazy-placeholder {
        background: #f0f0f0;
        color: #999;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: opacity 0.3s ease;
    }

    .lazy-loaded {
        animation: fadeIn 0.3s ease-in;
    }

    .lazy-error {
        background: #fee;
        color: #c53030;
        border: 1px solid #fed7d7;
        border-radius: 4px;
        padding: 1rem;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .lazy-loading::after {
        content: '';
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid #ddd;
        border-top: 2px solid #3b82f6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;

// Injecter les styles
const styleSheet = document.createElement('style');
styleSheet.textContent = lazyStyles;
document.head.appendChild(styleSheet);

console.log('🚀 Lazy Loader initialized successfully');