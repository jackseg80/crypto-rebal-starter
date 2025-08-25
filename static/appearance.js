// static/appearance.js
(function () {
    const SETTINGS_KEY = 'crypto_rebalancer_settings'; // même clé que global-config

    function getTheme() {
        try {
            const pref = window.globalConfig?.get?.('theme') || 'auto';
            if (pref === 'dark' || pref === 'light') return pref;
            const mql = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
            return mql && mql.matches ? 'dark' : 'light';
        } catch (e) { return 'light'; }
    }

    function getStyle() {
        try { return window.globalConfig?.get?.('style') || 'modern'; }
        catch (e) { return 'modern'; }
    }

    function applyAppearance() {
        const t = getTheme();
        const s = getStyle();
        document.documentElement.setAttribute('data-theme', t);
        document.documentElement.setAttribute('data-style', s);
        // journaliser doucement pour debug si besoin
        // console.log(`[appearance] applied: theme=${t}, style=${s}`);
    }

    // Expose global pour settings.html (appliquer instantanément)
    window.applyAppearance = applyAppearance;

    // Appliquer au chargement
    document.addEventListener('DOMContentLoaded', applyAppearance);

    // Re-appliquer si l’onglet revient en avant-plan
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) applyAppearance();
    });

    // Suivre le système (auto) — écoute les changements OS
    try {
        const mql = window.matchMedia('(prefers-color-scheme: dark)');
        if (mql && mql.addEventListener) {
            mql.addEventListener('change', () => {
                if ((window.globalConfig?.get?.('theme') || 'auto') === 'auto') applyAppearance();
            });
        }
    } catch (_) { }

    // Synchroniser entre pages/onglets : réagir aux modifications de settings
    window.addEventListener('storage', (e) => {
        if (e.key === SETTINGS_KEY) applyAppearance();
    });

    // Aussi réagir aux events locaux émis par global-config (même page)
    window.addEventListener('themeChanged', applyAppearance);
    window.addEventListener('styleChanged', applyAppearance);
})();
