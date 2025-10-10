/**
 * Optimisateur de performances pour Crypto Rebalancer
 * 
 * Gère les gros portfolios (1000+ assets) avec techniques d'optimisation :
 * - Lazy loading et pagination
 * - Debouncing des événements UI
 * - Cache intelligent des calculs
 * - Web Workers pour calculs lourds
 */

// Lazy Loading System intégré
class LazyLoadManager {
    constructor() {
        this.lazyElements = new Map();
        this.intersectionObserver = this.setupIntersectionObserver();
        this.loadedResources = new Set();
    }

    setupIntersectionObserver() {
        if (!window.IntersectionObserver) return null;
        
        return new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.loadLazyElement(entry.target);
                }
            });
        }, {
            rootMargin: '100px',
            threshold: 0.1
        });
    }

    markForLazyLoad(element, type, source) {
        if (!this.intersectionObserver) return;
        
        element.dataset.lazyType = type;
        element.dataset.lazySrc = source;
        this.lazyElements.set(element, { type, source, loaded: false });
        this.intersectionObserver.observe(element);
    }

    async loadLazyElement(element) {
        const lazyData = this.lazyElements.get(element);
        if (!lazyData || lazyData.loaded) return;

        const { type, source } = lazyData;
        
        try {
            switch (type) {
                case 'script':
                    await this.loadScript(source);
                    break;
                case 'component':
                    await this.loadComponent(element, source);
                    break;
                case 'data':
                    await this.loadData(element, source);
                    break;
            }
            
            lazyData.loaded = true;
            element.classList.add('lazy-loaded');
            this.intersectionObserver.unobserve(element);
            
        } catch (error) {
            debugLogger.error(`Failed to lazy load ${type}:`, error);
            element.classList.add('lazy-error');
        }
    }

    async loadScript(src) {
        if (this.loadedResources.has(src)) return;
        
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = () => {
                this.loadedResources.add(src);
                resolve();
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async loadComponent(element, componentName) {
        // Charger les composants spécialisés selon le besoin
        if (componentName === 'Chart' && !window.Chart) {
            await this.loadScript('https://cdn.jsdelivr.net/npm/chart.js');
        }
        
        // Initialiser le composant
        const event = new CustomEvent('lazyComponentLoaded', {
            detail: { element, componentName }
        });
        element.dispatchEvent(event);
    }

    async loadData(element, dataSource) {
        const loadingIndicator = element.querySelector('.loading-placeholder');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
        }

        try {
            const response = await fetch(dataSource);
            const data = await response.json();
            
            const event = new CustomEvent('lazyDataLoaded', {
                detail: { element, data }
            });
            element.dispatchEvent(event);
            
        } finally {
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        }
    }

    // Optimisation pour les grandes listes
    setupVirtualScrolling(container, items, renderItem, itemHeight = 50) {
        const visibleCount = Math.ceil(container.clientHeight / itemHeight) + 2;
        let startIndex = 0;
        
        const scrollHandler = () => {
            const scrollTop = container.scrollTop;
            const newStartIndex = Math.floor(scrollTop / itemHeight);
            
            if (newStartIndex !== startIndex) {
                startIndex = newStartIndex;
                this.renderVisibleItems(container, items, renderItem, startIndex, visibleCount, itemHeight);
            }
        };
        
        container.addEventListener('scroll', this.debounce(scrollHandler, 16));
        
        // Rendu initial
        this.renderVisibleItems(container, items, renderItem, startIndex, visibleCount, itemHeight);
    }

    renderVisibleItems(container, items, renderItem, startIndex, visibleCount, itemHeight) {
        const endIndex = Math.min(startIndex + visibleCount, items.length);
        
        container.innerHTML = '';
        container.style.height = `${items.length * itemHeight}px`;
        container.style.position = 'relative';
        
        for (let i = startIndex; i < endIndex; i++) {
            const item = renderItem(items[i], i);
            item.style.position = 'absolute';
            item.style.top = `${i * itemHeight}px`;
            item.style.height = `${itemHeight}px`;
            container.appendChild(item);
        }
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

class PerformanceOptimizer {
    constructor() {
        this.cache = new Map();
        this.cacheTTL = 5 * 60 * 1000; // 5 minutes
        this.debounceTimers = new Map();
        
        // Initialiser le gestionnaire de lazy loading
        this.lazyLoadManager = new LazyLoadManager();
        
        // Seuils de performance
        this.thresholds = {
            large_portfolio: 500,      // Nombre d'assets pour déclencher optimisations
            pagination_size: 100,      // Nombre d'assets par page
            debounce_delay: 300,       // ms
            render_batch_size: 50,     // Nombre d'éléments DOM par batch
            worker_threshold: 1000     // Utiliser Web Worker si plus d'assets
        };
        
        // Statistiques de performance
        this.stats = {
            cache_hits: 0,
            cache_misses: 0,
            render_batches: 0,
            worker_computations: 0,
            lazy_loads: 0
        };
        
        // Initialiser l'optimisation automatique des pages
        this.initPageOptimization();
        
        log.info('PerformanceOptimizer initialized with thresholds:', this.thresholds);
    }
    
    /**
     * Initialiser l'optimisation automatique des pages
     */
    initPageOptimization() {
        // Attendre que le DOM soit prêt
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.optimizeCurrentPage());
        } else {
            this.optimizeCurrentPage();
        }
    }
    
    /**
     * Optimiser la page courante
     */
    optimizeCurrentPage() {
        // Identifier et optimiser les sections lourdes
        this.optimizeCharts();
        this.optimizeTables();
        this.optimizeImages();
        this.setupSmartPagination();
        
        log.info('Page optimization completed');
    }
    
    /**
     * Optimiser les graphiques pour le lazy loading
     */
    optimizeCharts() {
        const chartSelectors = [
            'canvas[id*="chart"]',
            '.chart-container:not([data-critical])',
            '[data-chart-type]'
        ];
        
        chartSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(element => {
                if (!element.dataset.optimized) {
                    this.lazyLoadManager.markForLazyLoad(element, 'component', 'Chart');
                    element.dataset.optimized = 'true';
                }
            });
        });
    }
    
    /**
     * Optimiser les tables avec beaucoup de données
     */
    optimizeTables() {
        document.querySelectorAll('table.data-table, .large-table').forEach(table => {
            const rows = table.querySelectorAll('tbody tr');
            
            if (rows.length > this.thresholds.pagination_size) {
                this.setupTablePagination(table, rows);
            }
        });
    }
    
    /**
     * Optimiser les images
     */
    optimizeImages() {
        document.querySelectorAll('img:not([loading])').forEach(img => {
            const rect = img.getBoundingClientRect();
            const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
            
            if (!isVisible) {
                img.loading = 'lazy';
            }
        });
    }
    
    /**
     * Configurer la pagination intelligente pour une table
     */
    setupTablePagination(table, rows) {
        const container = table.parentElement;
        const tbody = table.querySelector('tbody');
        const pageSize = this.thresholds.pagination_size;
        
        // Créer les contrôles de pagination
        const paginationControls = this.createPaginationControls(rows.length, pageSize);
        container.appendChild(paginationControls);
        
        // Fonction de rendu de page
        const renderPage = (pageIndex) => {
            const start = pageIndex * pageSize;
            const end = Math.min(start + pageSize, rows.length);
            
            // Cacher toutes les lignes
            rows.forEach(row => row.style.display = 'none');
            
            // Afficher les lignes de la page courante
            for (let i = start; i < end; i++) {
                rows[i].style.display = '';
            }
            
            this.stats.render_batches++;
        };
        
        // Rendu initial
        renderPage(0);
        
        // Configuration des événements de pagination
        this.setupPaginationEvents(paginationControls, rows.length, pageSize, renderPage);
    }
    
    /**
     * Créer les contrôles de pagination
     */
    createPaginationControls(totalItems, pageSize) {
        const totalPages = Math.ceil(totalItems / pageSize);
        
        const container = document.createElement('div');
        container.className = 'pagination-controls';
        container.style.cssText = `
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin: 1rem 0;
            align-items: center;
        `;
        
        // Bouton précédent
        const prevBtn = document.createElement('button');
        prevBtn.className = 'btn btn-secondary pagination-prev';
        prevBtn.textContent = '« Précédent';
        prevBtn.disabled = true;
        
        // Indicateur de page
        const pageIndicator = document.createElement('span');
        pageIndicator.className = 'page-indicator';
        pageIndicator.textContent = `1 / ${totalPages}`;
        pageIndicator.style.cssText = 'margin: 0 1rem; font-weight: 500;';
        
        // Bouton suivant
        const nextBtn = document.createElement('button');
        nextBtn.className = 'btn btn-secondary pagination-next';
        nextBtn.textContent = 'Suivant »';
        nextBtn.disabled = totalPages <= 1;
        
        container.append(prevBtn, pageIndicator, nextBtn);
        return container;
    }
    
    /**
     * Configurer les événements de pagination
     */
    setupPaginationEvents(controls, totalItems, pageSize, renderPage) {
        const totalPages = Math.ceil(totalItems / pageSize);
        let currentPage = 0;
        
        const prevBtn = controls.querySelector('.pagination-prev');
        const nextBtn = controls.querySelector('.pagination-next');
        const indicator = controls.querySelector('.page-indicator');
        
        const updateControls = () => {
            prevBtn.disabled = currentPage === 0;
            nextBtn.disabled = currentPage === totalPages - 1;
            indicator.textContent = `${currentPage + 1} / ${totalPages}`;
        };
        
        prevBtn.addEventListener('click', () => {
            if (currentPage > 0) {
                currentPage--;
                renderPage(currentPage);
                updateControls();
            }
        });
        
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages - 1) {
                currentPage++;
                renderPage(currentPage);
                updateControls();
            }
        });
    }
    
    /**
     * Configurer la pagination intelligente
     */
    setupSmartPagination() {
        // Auto-détecter les contenus qui bénéficieraient de la pagination
        document.querySelectorAll('.portfolio-list, .assets-list').forEach(list => {
            const items = list.querySelectorAll('.portfolio-item, .asset-item');
            
            if (items.length > this.thresholds.pagination_size) {
                this.convertToPaginatedList(list, items);
            }
        });
    }
    
    /**
     * Cache intelligent avec TTL
     */
    setCache(key, value, customTTL = null) {
        const ttl = customTTL || this.cacheTTL;
        this.cache.set(key, {
            value,
            timestamp: Date.now(),
            ttl
        });
        log.debug('Cache set:', key);
    }
    
    getCache(key) {
        const item = this.cache.get(key);
        if (!item) {
            this.stats.cache_misses++;
            return null;
        }
        
        if (Date.now() - item.timestamp > item.ttl) {
            this.cache.delete(key);
            this.stats.cache_misses++;
            return null;
        }
        
        this.stats.cache_hits++;
        log.debug('Cache hit:', key);
        return item.value;
    }
    
    clearCache(pattern = null) {
        if (pattern) {
            for (const key of this.cache.keys()) {
                if (key.includes(pattern)) {
                    this.cache.delete(key);
                }
            }
        } else {
            this.cache.clear();
        }
        log.info('Cache cleared:', pattern || 'all');
    }
    
    /**
     * Debouncing pour événements fréquents
     */
    debounce(key, func, delay = null) {
        const debounceDelay = delay || this.thresholds.debounce_delay;
        
        // Annuler le timer précédent
        if (this.debounceTimers.has(key)) {
            clearTimeout(this.debounceTimers.get(key));
        }
        
        // Créer nouveau timer
        const timer = setTimeout(() => {
            func();
            this.debounceTimers.delete(key);
        }, debounceDelay);
        
        this.debounceTimers.set(key, timer);
    }
    
    /**
     * Pagination automatique pour gros datasets
     */
    paginate(items, page = 1, pageSize = null) {
        const size = pageSize || this.thresholds.pagination_size;
        const start = (page - 1) * size;
        const end = start + size;
        
        return {
            items: items.slice(start, end),
            currentPage: page,
            totalPages: Math.ceil(items.length / size),
            totalItems: items.length,
            pageSize: size,
            hasNext: end < items.length,
            hasPrev: page > 1
        };
    }
    
    /**
     * Rendu par batch pour éviter le blocage UI
     */
    async renderInBatches(items, renderFunction, container, batchSize = null) {
        const size = batchSize || this.thresholds.render_batch_size;
        const total = items.length;
        
        log.perf(`Rendering ${total} items in batches of ${size}`);
        
        for (let i = 0; i < total; i += size) {
            const batch = items.slice(i, i + size);
            
            // Traiter le batch
            const fragment = document.createDocumentFragment();
            for (const item of batch) {
                const element = renderFunction(item);
                if (element) fragment.appendChild(element);
            }
            
            // Ajouter au DOM
            if (container) {
                container.appendChild(fragment);
            }
            
            // Yield control to browser
            if (i + size < total) {
                await this.nextTick();
            }
            
            this.stats.render_batches++;
        }
        
        log.perfEnd(`Rendering ${total} items in batches of ${size}`);
        log.debug(`Rendered in ${Math.ceil(total / size)} batches`);
    }
    
    /**
     * Yield control au navigateur
     */
    nextTick() {
        return new Promise(resolve => {
            if (window.requestIdleCallback) {
                requestIdleCallback(resolve);
            } else {
                setTimeout(resolve, 0);
            }
        });
    }
    
    /**
     * Calculs lourds dans Web Worker
     */
    async computeInWorker(data, computation) {
        if (data.length < this.thresholds.worker_threshold) {
            // Dataset petit, calcul direct
            return computation(data);
        }
        
        try {
            log.perf(`Computing ${data.length} items in Web Worker`);
            
            // Créer Web Worker inline
            const workerCode = `
                self.onmessage = function(e) {
                    const { data, computationType } = e.data;
                    let result;
                    
                    try {
                        switch(computationType) {
                            case 'groupAssets':
                                result = groupAssets(data);
                                break;
                            case 'calculateDeltas':
                                result = calculateDeltas(data);
                                break;
                            default:
                                throw new Error('Unknown computation type');
                        }
                        
                        self.postMessage({ success: true, result });
                    } catch (error) {
                        self.postMessage({ success: false, error: error.message });
                    }
                };
                
                // Fonctions de calcul
                function groupAssets(items) {
                    const groups = new Map();
                    for (const item of items) {
                        const group = item.group || 'Others';
                        if (!groups.has(group)) {
                            groups.set(group, { value: 0, assets: [] });
                        }
                        const groupData = groups.get(group);
                        groupData.value += item.value_usd;
                        groupData.assets.push(item.symbol);
                    }
                    return Array.from(groups.entries()).map(([name, data]) => ({
                        label: name,
                        value: data.value,
                        assets: data.assets
                    }));
                }
                
                function calculateDeltas(data) {
                    // Calcul simplifié pour démo
                    return data.map(item => ({
                        ...item,
                        delta: Math.random() * 1000 - 500
                    }));
                }
            `;
            
            const blob = new Blob([workerCode], { type: 'application/javascript' });
            const worker = new Worker(URL.createObjectURL(blob));
            
            const result = await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    worker.terminate();
                    reject(new Error('Worker timeout'));
                }, 10000); // 10s timeout
                
                worker.onmessage = (e) => {
                    clearTimeout(timeout);
                    worker.terminate();
                    URL.revokeObjectURL(blob.url);
                    
                    if (e.data.success) {
                        resolve(e.data.result);
                    } else {
                        reject(new Error(e.data.error));
                    }
                };
                
                worker.onerror = (error) => {
                    clearTimeout(timeout);
                    worker.terminate();
                    reject(error);
                };
                
                worker.postMessage({ data, computationType: 'groupAssets' });
            });
            
            this.stats.worker_computations++;
            log.perfEnd(`Computing ${data.length} items in Web Worker`);
            return result;
            
        } catch (error) {
            log.warn('Worker computation failed, falling back to main thread:', error.message);
            return computation(data);
        }
    }
    
    /**
     * Optimise un tableau de données selon sa taille
     */
    async optimizeDataset(items, operations) {
        const isLarge = items.length > this.thresholds.large_portfolio;
        
        if (!isLarge) {
            // Dataset small, traitement normal
            log.debug(`Small dataset (${items.length} items), normal processing`);
            return operations(items);
        }
        
        log.info(`Large dataset (${items.length} items), applying optimizations`);
        
        // Cache le résultat
        const cacheKey = `dataset_${items.length}_${this.hashData(items)}`;
        const cached = this.getCache(cacheKey);
        if (cached) {
            log.debug('Using cached result for large dataset');
            return cached;
        }
        
        // Calcul optimisé
        const result = await this.computeInWorker(items, operations);
        
        // Cache le résultat
        this.setCache(cacheKey, result);
        
        return result;
    }
    
    /**
     * Hash simple pour cache key
     */
    hashData(data) {
        const str = JSON.stringify(data).substring(0, 100); // Limiter pour perf
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return Math.abs(hash).toString(36);
    }
    
    /**
     * Lazy loading d'éléments DOM
     */
    enableLazyLoading(container, itemHeight = 50) {
        if (!container) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const element = entry.target;
                    if (element.dataset.lazy) {
                        this.loadLazyElement(element);
                        observer.unobserve(element);
                    }
                }
            });
        }, {
            rootMargin: '100px'
        });
        
        // Observer tous les éléments lazy
        container.querySelectorAll('[data-lazy]').forEach(el => {
            observer.observe(el);
        });
        
        return observer;
    }
    
    loadLazyElement(element) {
        const content = element.dataset.lazy;
        try {
            const data = JSON.parse(content);
            element.innerHTML = this.renderAssetRow(data);
            element.removeAttribute('data-lazy');
            log.debug('Lazy loaded element:', data.symbol);
        } catch (error) {
            log.error('Failed to lazy load element:', error);
        }
    }
    
    renderAssetRow(asset) {
        return `
            <div class="asset-row">
                <span class="symbol">${asset.symbol}</span>
                <span class="value">$${asset.value_usd?.toFixed(2) || '0.00'}</span>
                <span class="balance">${asset.balance?.toFixed(6) || '0.000000'}</span>
            </div>
        `;
    }
    
    /**
     * Retourne les statistiques de performance
     */
    getStats() {
        const cacheHitRate = this.stats.cache_hits + this.stats.cache_misses > 0 
            ? (this.stats.cache_hits / (this.stats.cache_hits + this.stats.cache_misses) * 100).toFixed(1)
            : '0.0';
            
        return {
            ...this.stats,
            cache_size: this.cache.size,
            cache_hit_rate: `${cacheHitRate}%`,
            active_debounces: this.debounceTimers.size
        };
    }
    
    /**
     * Détecte si le portfolio est "gros" et nécessite optimisations
     */
    isLargePortfolio(itemCount) {
        return itemCount > this.thresholds.large_portfolio;
    }
    
    /**
     * Recommandations d'optimisation basées sur la taille du dataset
     */
    getOptimizationRecommendations(itemCount) {
        const recommendations = [];
        
        if (itemCount > this.thresholds.large_portfolio) {
            recommendations.push('💡 Portfolio volumineux détecté - optimisations automatiques activées');
        }
        
        if (itemCount > this.thresholds.worker_threshold) {
            recommendations.push('⚡ Calculs lourds déplacés vers Web Workers');
        }
        
        if (itemCount > this.thresholds.pagination_size * 2) {
            recommendations.push('📄 Pagination automatique recommandée');
        }
        
        return recommendations;
    }
}

// Instance globale
const performanceOptimizer = new PerformanceOptimizer();

// Export pour utilisation
window.performanceOptimizer = performanceOptimizer;

// Fonctions utilitaires
window.optimizeData = (items, operations) => performanceOptimizer.optimizeDataset(items, operations);
window.renderBatched = (items, renderFunc, container) => performanceOptimizer.renderInBatches(items, renderFunc, container);
window.debounce = (key, func, delay) => performanceOptimizer.debounce(key, func, delay);

log.info('Performance Optimizer loaded - Large portfolio support active');