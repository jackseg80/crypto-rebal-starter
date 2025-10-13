// WealthContextBar - Barre de contexte patrimoine globale (ES module)
// Filtres household/account/module/ccy persistés localStorage + querystring

class WealthContextBar {
  constructor() {
    this.storageKey = 'wealthCtx';
    this.defaults = {
      account: 'all',
      bourse: 'all',
      module: 'all',
      currency: 'USD'
    };
    this.context = this.loadContext();
    this.isInitialized = false;
    this.abortController = null; // Pour annuler fetch en cours lors du switch user
    this.bourseAbortController = null; // Pour annuler fetch Bourse

    // Anti-PUT rafale + idempotence
    this.settingsPutController = null; // AbortController pour PUT /api/users/settings
    this.lastAppliedSettings = null; // JSON string des derniers settings appliqués
    this.sourcesCache = null; // Cache pour /api/users/sources
    this.sourcesCacheTime = 0; // Timestamp du cache
    this.sourcesCacheTTL = 60000; // 60 secondes

    // Debounce pour changement de source
    this.accountChangeDebounceTimer = null;
    this.accountChangeDebounceDelay = 250; // 250ms
    this.bourseChangeDebounceTimer = null;
  }

  loadContext() {
    try {
      // Priorité : querystring > localStorage (namespacé par user) > defaults
      const params = new URLSearchParams(location.search);
      const activeUser = localStorage.getItem('activeUser') || 'demo';
      const userKey = `wealth_ctx:${activeUser}`;
      const stored = JSON.parse(localStorage.getItem(userKey) || '{}');

      return {
        account: params.get('account') || stored.account || this.defaults.account,
        bourse: params.get('bourse') || stored.bourse || this.defaults.bourse,
        module: params.get('module') || stored.module || this.defaults.module,
        currency: params.get('ccy') || stored.currency || this.defaults.currency
      };
    } catch (error) {
      console.debug('Error loading wealth context:', error);
      return { ...this.defaults };
    }
  }

  saveContext() {
    try {
      // Sauvegarder dans localStorage namespacé par user
      const activeUser = localStorage.getItem('activeUser') || 'demo';
      const userKey = `wealth_ctx:${activeUser}`;
      localStorage.setItem(userKey, JSON.stringify(this.context));

      this.updateQueryString();

      // Émettre événement avec structure canonique
      this.emit('wealth:change', {
        ...this.context,
        account: this.parseAccountValue(this.context.account),
        sourceValue: this.context.account || 'all'
      });
    } catch (error) {
      debugLogger.error('Error saving wealth context:', error);
    }
  }

  parseAccountValue(rawValue) {
    if (!rawValue || rawValue === 'all') {
      return { type: 'all', key: null };
    }
    const parts = rawValue.split(':');
    if (parts.length === 2) {
      return { type: parts[0], key: parts[1] };
    }
    // Fallback pour anciennes valeurs (trading, hold, staking)
    return { type: 'legacy', key: rawValue };
  }

  updateQueryString() {
    const params = new URLSearchParams(location.search);

    // Mettre à jour les paramètres (ne pas ajouter si valeur par défaut)
    Object.entries(this.context).forEach(([key, value]) => {
      const paramKey = key === 'currency' ? 'ccy' : key;
      if (value !== this.defaults[key] && value !== 'all') {
        params.set(paramKey, value);
      } else {
        params.delete(paramKey);
      }
    });

    // Mettre à jour l'URL sans recharger
    const newUrl = `${location.pathname}${params.toString() ? '?' + params.toString() : ''}${location.hash}`;
    history.replaceState({}, '', newUrl);
  }

  emit(eventName, data) {
    window.dispatchEvent(new CustomEvent(eventName, {
      detail: data,
      bubbles: true
    }));
  }

  async loadAccountSources() {
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const now = Date.now();

    // Utiliser cache si valide (< 60s) et même user
    if (this.sourcesCache &&
        this.sourcesCacheTime > 0 &&
        (now - this.sourcesCacheTime) < this.sourcesCacheTTL &&
        this.sourcesCache.user === activeUser) {
      console.debug('WealthContextBar: Using cached sources');
      return this.buildAccountOptions(this.sourcesCache.sources || []);
    }

    // Annuler fetch précédent si en cours
    if (this.abortController) {
      this.abortController.abort();
    }

    this.abortController = new AbortController();

    try {
      const response = await fetch('/api/users/sources', {
        headers: { 'X-User': activeUser },
        signal: this.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      // Mettre en cache
      this.sourcesCache = {
        user: activeUser,
        sources: data.sources || []
      };
      this.sourcesCacheTime = now;

      return this.buildAccountOptions(data.sources || []);

    } catch (error) {
      if (error.name === 'AbortError') {
        console.debug('Account sources fetch aborted (user switch)');
        return null; // Retourner null pour indiquer abort
      }
      debugLogger.warn('Failed to load account sources, using fallback:', error);
      return this.buildFallbackAccountOptions();
    } finally {
      this.abortController = null;
    }
  }

  buildAccountOptions(sources) {
    // Trier : API d'abord (alphabétique), puis CSV (alphabétique)
    const apis = sources
      .filter(s => s.type === 'api')
      .sort((a, b) => a.label.localeCompare(b.label));

    const csvs = sources
      .filter(s => s.type === 'csv' && s.module === 'cointracking')
      .sort((a, b) => a.label.localeCompare(b.label));

    let html = '<option value="all">Tous</option>';

    if (apis.length > 0) {
      html += '<option disabled>──── API ────</option>';
      apis.forEach(s => {
        const value = `${s.type}:${s.key}`;
        html += `<option value="${value}" data-type="${s.type}">${s.label}</option>`;
      });
    }

    if (csvs.length > 0) {
      html += '<option disabled>──── CSV ────</option>';
      csvs.forEach(s => {
        const value = `${s.type}:${s.key}`;
        html += `<option value="${value}" data-type="${s.type}">${s.label}</option>`;
      });
    }

    return html;
  }

  buildFallbackAccountOptions() {
    return '<option value="all">Tous</option>';
  }

  async loadBourseSources() {
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const now = Date.now();

    // Utiliser cache si valide
    if (this.sourcesCache &&
        this.sourcesCacheTime > 0 &&
        (now - this.sourcesCacheTime) < this.sourcesCacheTTL &&
        this.sourcesCache.user === activeUser) {
      console.debug('WealthContextBar: Using cached bourse sources');
      return this.buildBourseOptions(this.sourcesCache.sources || []);
    }

    // Annuler fetch précédent si en cours
    if (this.bourseAbortController) {
      this.bourseAbortController.abort();
    }

    this.bourseAbortController = new AbortController();

    try {
      const response = await fetch('/api/users/sources', {
        headers: { 'X-User': activeUser },
        signal: this.bourseAbortController.signal
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      // Cache partagé avec account sources
      if (!this.sourcesCache || this.sourcesCache.user !== activeUser) {
        this.sourcesCache = {
          user: activeUser,
          sources: data.sources || []
        };
        this.sourcesCacheTime = now;
      }

      return this.buildBourseOptions(data.sources || []);

    } catch (error) {
      if (error.name === 'AbortError') {
        console.debug('Bourse sources fetch aborted (user switch)');
        return null;
      }
      debugLogger.warn('Failed to load bourse sources, using fallback:', error);
      return '<option value="all">Tous</option>';
    } finally {
      this.bourseAbortController = null;
    }
  }

  buildBourseOptions(sources) {
    // Filtrer uniquement les CSV Saxo (module saxobank)
    const saxoCSVs = sources
      .filter(s => s.type === 'csv' && s.module === 'saxobank')
      .sort((a, b) => a.label.localeCompare(b.label));

    let html = '<option value="all">Tous</option>';

    if (saxoCSVs.length > 0) {
      html += '<option disabled>──── CSV Saxo ────</option>';
      saxoCSVs.forEach(s => {
        const value = `saxo:${s.key}`;
        html += `<option value="${value}" data-type="saxo">${s.label}</option>`;
      });
    }

    return html;
  }

  async persistSettingsSafely(settings, source) {
    const payload = JSON.stringify(settings);

    // Idempotence: ne pas persister si rien n'a changé
    if (payload === this.lastAppliedSettings) {
      console.debug('WealthContextBar: Settings unchanged, skipping PUT');
      return { ok: true, skipped: true };
    }

    // Annuler PUT en cours (anti-rafale)
    if (this.settingsPutController) {
      console.debug('WealthContextBar: Aborting previous PUT request');
      this.settingsPutController.abort();
      this.settingsPutController = null;
    }

    this.settingsPutController = new AbortController();
    const activeUser = localStorage.getItem('activeUser') || 'demo';

    try {
      const response = await fetch('/api/users/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User': activeUser
        },
        body: payload,
        signal: this.settingsPutController.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }

      this.lastAppliedSettings = payload;
      console.debug('WealthContextBar: Settings persisted successfully');

      return { ok: true };

    } catch (error) {
      if (error.name === 'AbortError') {
        console.debug('WealthContextBar: PUT aborted (newer request started)');
        return { ok: false, aborted: true };
      }

      debugLogger.error('WealthContextBar: Failed to persist settings:', error);
      return { ok: false, error };

    } finally {
      if (this.settingsPutController) {
        this.settingsPutController = null;
      }
    }
  }

  async handleAccountChange(selectedValue, options = {}) {
    const { skipSave = false, skipNotification = false } = options;

    console.debug(`WealthContextBar: Account changed to "${selectedValue}" (skipSave=${skipSave})`);

    // Si "all", ne rien faire de spécial
    if (selectedValue === 'all') {
      this.context.account = 'all';
      if (!skipSave) {
        this.saveContext();
      }
      return;
    }

    // Parse la valeur : type:key (ex: csv:csv_latest ou api:cointracking_api)
    const parts = selectedValue.split(':');
    if (parts.length !== 2) {
      debugLogger.warn(`WealthContextBar: Invalid account value format: ${selectedValue}`);
      return;
    }

    const [type, key] = parts;

    // Charger les sources disponibles si pas déjà chargé
    if (!window.availableSources) {
      try {
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        const response = await fetch('/api/users/sources', {
          headers: { 'X-User': activeUser }
        });
        if (response.ok) {
          const data = await response.json();
          window.availableSources = data.sources || [];
        }
      } catch (error) {
        debugLogger.error('Failed to load sources:', error);
        return;
      }
    }

    // Trouver la source correspondante
    const source = window.availableSources.find(s => s.key === key && s.type === type);
    if (!source) {
      debugLogger.warn(`WealthContextBar: Source not found for key=${key}, type=${type}`);
      return;
    }

    // Initialiser userSettings si nécessaire
    if (!window.userSettings) {
      window.userSettings = {
        data_source: 'csv',
        csv_selected_file: null
      };
    }

    // Préserver les clés API (critique!)
    try {
      const activeUser = localStorage.getItem('activeUser') || 'demo';
      const response = await fetch('/api/users/settings', {
        headers: { 'X-User': activeUser }
      });
      if (response.ok) {
        const currentSettings = await response.json();
        const apiKeys = ['coingecko_api_key', 'cointracking_api_key', 'cointracking_api_secret', 'fred_api_key', 'debug_token'];
        apiKeys.forEach(k => {
          if (currentSettings[k]) {
            window.userSettings[k] = currentSettings[k];
          }
        });
      }
    } catch (e) {
      debugLogger.warn('Could not reload settings to preserve API keys:', e);
    }

    // Déterminer l'ancienne et nouvelle source
    const oldSource = window.userSettings.data_source;
    const oldFile = window.userSettings.csv_selected_file;

    let effectiveNew, newFile = null;

    if (type === 'csv') {
      effectiveNew = 'cointracking';
      newFile = source.file_path ? source.file_path.split(/[/\\]/).pop() : null;
    } else if (type === 'api' && key === 'cointracking_api') {
      effectiveNew = 'cointracking_api';
    } else {
      effectiveNew = key; // Autre type de source
    }

    // Vider caches si changement réel
    const sourceChanged = oldSource && oldSource !== effectiveNew;
    const fileChanged = effectiveNew === 'cointracking' && oldFile !== newFile;

    if (sourceChanged || fileChanged) {
      console.debug(`WealthContextBar: Source changed from ${oldSource}/${oldFile} to ${effectiveNew}/${newFile}`);

      // Vider cache balance
      if (typeof window.clearBalanceCache === 'function') {
        window.clearBalanceCache();
      }

      // Vider localStorage cache
      Object.keys(localStorage).forEach(key => {
        if (key.startsWith('cache:') || key.includes('risk_score') || key.includes('balance_')) {
          localStorage.removeItem(key);
        }
      });

      // Mettre à jour globalConfig
      if (typeof window.globalConfig !== 'undefined') {
        window.globalConfig.set('data_source', effectiveNew);
      }
    }

    // Mettre à jour userSettings
    if (type === 'csv') {
      window.userSettings.data_source = 'cointracking';
      window.userSettings.csv_selected_file = newFile;
    } else {
      window.userSettings.data_source = effectiveNew;
      window.userSettings.csv_selected_file = null;
    }

    // Mettre à jour context interne
    this.context.account = selectedValue;

    // Sauvegarder dans localStorage seulement si pas skipSave
    if (!skipSave) {
      this.saveContext();
    }

    // Émettre événement dataSourceChanged pour que les pages rechargent
    if (sourceChanged || fileChanged) {
      console.debug(`WealthContextBar: Emitting dataSourceChanged event (${oldSource} → ${effectiveNew})`);

      // Event personnalisé pour recharger les données dans la même page
      window.dispatchEvent(new CustomEvent('dataSourceChanged', {
        detail: {
          oldSource: oldSource,
          newSource: effectiveNew,
          oldFile: oldFile,
          newFile: newFile
        }
      }));
    }

    // Sauvegarder dans le backend avec protection anti-rafale
    if (sourceChanged || fileChanged) {
      // Sauvegarder état AVANT modification pour rollback si échec
      const rollbackState = {
        source: oldSource,
        file: oldFile,
        globalConfigValue: oldSource,
        userSettingsSource: oldSource,
        userSettingsFile: oldFile,
        contextAccount: this.context.account
      };

      const persistResult = await this.persistSettingsSafely(window.userSettings, source);

      if (!persistResult.ok && !persistResult.aborted) {
        // ROLLBACK UI si erreur réseau/serveur
        debugLogger.error('WealthContextBar: Persistence failed, rolling back UI...');

        // Restaurer globalConfig
        if (typeof window.globalConfig !== 'undefined') {
          window.globalConfig.set('data_source', rollbackState.globalConfigValue);
        }

        // Restaurer userSettings
        window.userSettings.data_source = rollbackState.userSettingsSource;
        window.userSettings.csv_selected_file = rollbackState.userSettingsFile;

        // Restaurer dropdown
        const accountSelect = document.getElementById('wealth-account');
        if (accountSelect) {
          // Retrouver la valeur originale dans le dropdown
          const originalValue = rollbackState.userSettingsFile
            ? `csv:csv_${rollbackState.userSettingsFile.replace('.csv', '').toLowerCase().replace(/[^a-z0-9_]/g, '_')}`
            : rollbackState.userSettingsSource === 'cointracking_api' ? 'api:cointracking_api' : 'all';
          accountSelect.value = originalValue;
          this.context.account = originalValue;
        }

        // Notification erreur
        if (typeof window.showNotification === 'function') {
          window.showNotification(`❌ Échec changement source: ${persistResult.error?.message || 'Erreur réseau'}`, 'error');
        }

        return; // Arrêter ici, pas de reload
      }

      // Si succès ou aborté (nouvelle requête en cours)
      if (persistResult.ok && !persistResult.skipped && !skipNotification) {
        // Notification visuelle avec reload automatique
        if (typeof window.showNotification === 'function') {
          window.showNotification(`✅ Source changée: ${source.label}`, 'success');
        }

        // Reload conditionnel (intelligent)
        this.scheduleSmartReload();
      }
    }
  }

  async handleBourseChange(selectedValue, options = {}) {
    const { skipSave = false, skipNotification = false } = options;

    console.debug(`WealthContextBar: Bourse changed to "${selectedValue}" (skipSave=${skipSave})`);

    // Si "all", ne rien faire de spécial
    if (selectedValue === 'all') {
      this.context.bourse = 'all';
      if (!skipSave) {
        this.saveContext();
      }
      return;
    }

    // Parse la valeur : saxo:key (ex: saxo:saxo_latest)
    const parts = selectedValue.split(':');
    if (parts.length !== 2 || parts[0] !== 'saxo') {
      debugLogger.warn(`WealthContextBar: Invalid bourse value format: ${selectedValue}`);
      return;
    }

    const [, key] = parts;

    // Charger les sources disponibles si pas déjà chargé
    if (!window.availableSources) {
      try {
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        const response = await fetch('/api/users/sources', {
          headers: { 'X-User': activeUser }
        });
        if (response.ok) {
          const data = await response.json();
          window.availableSources = data.sources || [];
        }
      } catch (error) {
        debugLogger.error('Failed to load sources:', error);
        return;
      }
    }

    // Trouver la source correspondante
    const source = window.availableSources.find(s => s.key === key && s.module === 'saxobank');
    if (!source) {
      debugLogger.warn(`WealthContextBar: Saxo source not found for key=${key}`);
      return;
    }

    // Pour Bourse/Saxo, mettre à jour le contexte seulement (pas de globalConfig)
    // car c'est géré séparément par le module Wealth
    this.context.bourse = selectedValue;

    // Sauvegarder dans localStorage seulement si pas skipSave
    if (!skipSave) {
      this.saveContext();
    }

    // Émettre événement pour que les pages Bourse rechargent
    console.debug(`WealthContextBar: Emitting bourseSourceChanged event`);
    window.dispatchEvent(new CustomEvent('bourseSourceChanged', {
      detail: {
        source: source,
        key: key,
        value: selectedValue
      }
    }));

    // Notification visuelle
    if (!skipNotification && typeof window.showNotification === 'function') {
      window.showNotification(`✅ Source Bourse changée: ${source.label}`, 'success');
    }
  }

  scheduleSmartReload() {
    // Feature flag dev: ?noReload=1
    if (/[?&]noReload=1/.test(location.search)) {
      console.debug('WealthContextBar: Reload skipped (noReload=1 flag)');
      return;
    }

    // Détecter si des listeners dataSourceChanged sont présents
    let hasListener = false;
    const listenerDetector = () => {
      hasListener = true;
      window.removeEventListener('dataSourceChanged', listenerDetector);
    };
    window.addEventListener('dataSourceChanged', listenerDetector, { once: true });

    // Attendre 300ms pour laisser les listeners s'enregistrer
    setTimeout(() => {
      if (hasListener) {
        console.debug('WealthContextBar: Soft reload (dataSourceChanged listeners detected)');
        // Les listeners vont recharger les données, pas besoin de reload complet
      } else {
        console.debug('WealthContextBar: Hard reload (no listeners, full page refresh)');
        window.location.reload();
      }
    }, 300);
  }

  async setupUserSwitchListener() {
    window.addEventListener('activeUserChanged', async (e) => {
      console.debug(`WealthContextBar: User switched from ${e.detail.oldUser} to ${e.detail.newUser}`);

      // Annuler fetch en cours
      if (this.abortController) {
        this.abortController.abort();
      }
      if (this.bourseAbortController) {
        this.bourseAbortController.abort();
      }

      // Recharger les sources Account pour le nouvel utilisateur
      const accountSelect = document.getElementById('wealth-account');
      if (accountSelect) {
        // Afficher état de chargement
        accountSelect.setAttribute('aria-busy', 'true');
        accountSelect.innerHTML = '<option>Chargement…</option>';

        const accountHTML = await this.loadAccountSources();

        // Si le fetch a été aborté (null), ne rien faire
        if (accountHTML !== null) {
          accountSelect.innerHTML = accountHTML;
          accountSelect.removeAttribute('aria-busy');

          // Restaurer sélection depuis localStorage namespacé du nouveau user
          const newUserKey = `wealth_ctx:${e.detail.newUser}`;
          const storedCtx = JSON.parse(localStorage.getItem(newUserKey) || '{}');
          const restoredValue = storedCtx.account || 'all';

          // Vérifier que l'option existe avant de la définir
          const optionExists = Array.from(accountSelect.options).some(opt => opt.value === restoredValue);

          if (optionExists) {
            accountSelect.value = restoredValue;
            this.context.account = restoredValue;
            console.debug(`WealthContextBar: Account restored to "${restoredValue}" for user ${e.detail.newUser}`);

            // Appeler handleAccountChange pour synchroniser globalConfig/userSettings
            if (restoredValue !== 'all') {
              await this.handleAccountChange(restoredValue, { skipSave: true, skipNotification: true });
            }
          } else {
            console.warn(`WealthContextBar: Saved account "${restoredValue}" not found for user ${e.detail.newUser}, using "all"`);
            accountSelect.value = 'all';
            this.context.account = 'all';
          }
        }
      }

      // Recharger les sources Bourse pour le nouvel utilisateur
      const bourseSelect = document.getElementById('wealth-bourse');
      if (bourseSelect) {
        bourseSelect.setAttribute('aria-busy', 'true');
        bourseSelect.innerHTML = '<option>Chargement…</option>';

        const bourseHTML = await this.loadBourseSources();

        if (bourseHTML !== null) {
          bourseSelect.innerHTML = bourseHTML;
          bourseSelect.removeAttribute('aria-busy');

          // Restaurer sélection Bourse
          const newUserKey = `wealth_ctx:${e.detail.newUser}`;
          const storedCtx = JSON.parse(localStorage.getItem(newUserKey) || '{}');
          const restoredBourse = storedCtx.bourse || 'all';

          // Vérifier que l'option existe avant de la définir
          const optionExists = Array.from(bourseSelect.options).some(opt => opt.value === restoredBourse);

          if (optionExists) {
            bourseSelect.value = restoredBourse;
            this.context.bourse = restoredBourse;
            console.debug(`WealthContextBar: Bourse restored to "${restoredBourse}" for user ${e.detail.newUser}`);

            if (restoredBourse !== 'all') {
              await this.handleBourseChange(restoredBourse, { skipSave: true, skipNotification: true });
            }
          } else {
            console.warn(`WealthContextBar: Saved bourse "${restoredBourse}" not found for user ${e.detail.newUser}, using "all"`);
            bourseSelect.value = 'all';
            this.context.bourse = 'all';
          }
        }
      }
    });
  }

  async render() {
    if (this.isInitialized) return;

    const style = document.createElement('style');
    style.textContent = `
      .wealth-context-bar {
        background: var(--theme-surface);
        border-bottom: 1px solid var(--theme-border);
        padding: 0.5rem 1rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        font-size: 0.85rem;
        z-index: 999;
        position: sticky;
        top: var(--header-height, 60px);
      }
      .wealth-context-bar .context-group {
        display: flex;
        align-items: center;
        gap: 0.5rem;
      }
      .wealth-context-bar .context-label {
        color: var(--theme-text-muted);
        font-weight: 600;
      }
      .wealth-context-bar select {
        background: var(--theme-bg);
        border: 1px solid var(--theme-border);
        border-radius: var(--radius-sm);
        padding: 0.25rem 0.5rem;
        color: var(--theme-text);
        font-size: 0.85rem;
        min-width: 100px;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      /* Dropdown (options) affiche le nom complet */
      .wealth-context-bar select option {
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
      }
      .wealth-context-bar select:focus {
        outline: none;
        border-color: var(--brand-primary);
        box-shadow: 0 0 0 2px color-mix(in oklab, var(--brand-primary) 20%, transparent);
      }
      .wealth-context-bar .spacer {
        flex: 1;
      }
      .wealth-context-bar .reset-btn {
        background: none;
        border: 1px solid var(--theme-border);
        border-radius: var(--radius-sm);
        color: var(--theme-text-muted);
        padding: 0.25rem 0.5rem;
        cursor: pointer;
        font-size: 0.75rem;
      }
      .wealth-context-bar .reset-btn:hover {
        background: var(--theme-bg);
        border-color: var(--brand-primary);
        color: var(--brand-primary);
      }
    `;
    document.head.appendChild(style);

    const bar = document.createElement('div');
    bar.className = 'wealth-context-bar';
    bar.innerHTML = `
      <div class="context-group">
        <span class="context-label">Cointracking:</span>
        <select id="wealth-account" aria-busy="true">
          <option>Chargement…</option>
        </select>
      </div>

      <div class="context-group">
        <span class="context-label">Bourse:</span>
        <select id="wealth-bourse" aria-busy="true">
          <option>Chargement…</option>
        </select>
      </div>

      <div class="context-group">
        <span class="context-label">Module:</span>
        <select id="wealth-module">
          <option value="all">Tous</option>
          <option value="crypto">Crypto</option>
          <option value="bourse">Bourse</option>
          <option value="banque">Banque</option>
          <option value="divers">Divers</option>
        </select>
      </div>

      <div class="context-group">
        <span class="context-label">Devise:</span>
        <select id="wealth-currency">
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
          <option value="CHF">CHF</option>
        </select>
      </div>

      <div class="spacer"></div>

      <!-- Global Status Badge -->
      <div class="context-group">
        <div id="global-status-badge"></div>
      </div>

      <button class="reset-btn" id="wealth-reset">⟲ Reset</button>
    `;

    // Insérer après le header navigation
    const header = document.querySelector('.app-header');
    if (header) {
      header.insertAdjacentElement('afterend', bar);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }

    this.bindEvents();
    this.isInitialized = true;

    // Charger les sources de comptes de manière asynchrone
    this.loadAndPopulateAccountSources();
    this.loadAndPopulateBourseSources();

    // Setup listener pour changement d'utilisateur
    this.setupUserSwitchListener();

    // Mettre à jour les autres selects (module, currency)
    this.updateSelects();

    // Initialize global status badge
    this.initGlobalBadge();

    // Emit initial state
    setTimeout(() => {
      this.emit('wealth:change', this.context);
    }, 100);
  }

  async loadAndPopulateAccountSources() {
    const accountSelect = document.getElementById('wealth-account');
    if (!accountSelect) return;

    const accountHTML = await this.loadAccountSources();

    // Si le fetch a été aborté (null), ne rien faire
    if (accountHTML === null) return;

    accountSelect.innerHTML = accountHTML;
    accountSelect.removeAttribute('aria-busy');

    // Restaurer sélection depuis localStorage namespacé
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const userKey = `wealth_ctx:${activeUser}`;
    const stored = JSON.parse(localStorage.getItem(userKey) || '{}');
    const restoredValue = stored.account || 'all';

    // Vérifier que la valeur existe dans les options avant de la définir
    const optionExists = Array.from(accountSelect.options).some(opt => opt.value === restoredValue);

    if (optionExists) {
      accountSelect.value = restoredValue;
      console.debug(`WealthContextBar: Account restored to "${restoredValue}"`);

      // IMPORTANT: Appeler handleAccountChange pour synchroniser globalConfig/userSettings
      // Cela garantit que la source restaurée est bien appliquée dans tout le projet
      // skipSave=true car la valeur vient du localStorage (évite boucle)
      // skipNotification=true car c'est une restauration, pas un changement utilisateur
      if (restoredValue !== 'all') {
        await this.handleAccountChange(restoredValue, { skipSave: true, skipNotification: true });
      }
    } else {
      // Si l'option n'existe plus (ex: API key supprimée), réinitialiser à "all"
      console.warn(`WealthContextBar: Saved value "${restoredValue}" not found in options, resetting to "all"`);
      accountSelect.value = 'all';
      this.context.account = 'all';
      this.saveContext(); // Mettre à jour localStorage pour éviter de répéter cette erreur
    }
  }

  async loadAndPopulateBourseSources() {
    const bourseSelect = document.getElementById('wealth-bourse');
    if (!bourseSelect) return;

    const bourseHTML = await this.loadBourseSources();

    // Si le fetch a été aborté (null), ne rien faire
    if (bourseHTML === null) return;

    bourseSelect.innerHTML = bourseHTML;
    bourseSelect.removeAttribute('aria-busy');

    // Restaurer sélection depuis localStorage namespacé
    const activeUser = localStorage.getItem('activeUser') || 'demo';
    const userKey = `wealth_ctx:${activeUser}`;
    const stored = JSON.parse(localStorage.getItem(userKey) || '{}');
    const restoredValue = stored.bourse || 'all';

    // Vérifier que la valeur existe dans les options avant de la définir
    const optionExists = Array.from(bourseSelect.options).some(opt => opt.value === restoredValue);

    if (optionExists) {
      bourseSelect.value = restoredValue;
      console.debug(`WealthContextBar: Bourse restored to "${restoredValue}"`);

      // Appeler handleBourseChange pour synchroniser
      if (restoredValue !== 'all') {
        await this.handleBourseChange(restoredValue, { skipSave: true, skipNotification: true });
      }
    } else {
      // Si l'option n'existe plus, réinitialiser à "all"
      console.warn(`WealthContextBar: Saved bourse value "${restoredValue}" not found in options, resetting to "all"`);
      bourseSelect.value = 'all';
      this.context.bourse = 'all';
      this.saveContext(); // Mettre à jour localStorage pour éviter de répéter cette erreur
    }
  }

  bindEvents() {
    // Gestion des changements
    ['module', 'currency'].forEach(key => {
      const select = document.getElementById(`wealth-${key}`);
      if (select) {
        select.addEventListener('change', (e) => {
          this.context[key] = e.target.value;
          this.saveContext();
        });
      }
    });

    // Gestion spéciale pour 'account' qui doit changer la source de données
    // Avec debounce 250ms pour éviter PUT multiples lors navigation clavier
    const accountSelect = document.getElementById('wealth-account');
    if (accountSelect) {
      accountSelect.addEventListener('change', (e) => {
        const selectedValue = e.target.value;

        // Annuler timer précédent
        if (this.accountChangeDebounceTimer) {
          clearTimeout(this.accountChangeDebounceTimer);
        }

        // Debounce 250ms
        this.accountChangeDebounceTimer = setTimeout(async () => {
          await this.handleAccountChange(selectedValue);
          this.accountChangeDebounceTimer = null;
        }, this.accountChangeDebounceDelay);
      });
    }

    // Gestion spéciale pour 'bourse' qui doit changer la source Saxo
    // Avec debounce 250ms identique
    const bourseSelect = document.getElementById('wealth-bourse');
    if (bourseSelect) {
      bourseSelect.addEventListener('change', (e) => {
        const selectedValue = e.target.value;

        // Annuler timer précédent
        if (this.bourseChangeDebounceTimer) {
          clearTimeout(this.bourseChangeDebounceTimer);
        }

        // Debounce 250ms
        this.bourseChangeDebounceTimer = setTimeout(async () => {
          await this.handleBourseChange(selectedValue);
          this.bourseChangeDebounceTimer = null;
        }, this.accountChangeDebounceDelay);
      });
    }

    // Reset button
    const resetBtn = document.getElementById('wealth-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.context = { ...this.defaults };
        this.updateSelects();
        this.saveContext();
      });
    }

    // Écouter les changements d'URL (back/forward)
    window.addEventListener('popstate', () => {
      this.context = this.loadContext();
      this.updateSelects();
      this.emit('wealth:change', this.context);
    });
  }

  updateSelects() {
    ['account', 'bourse', 'module', 'currency'].forEach(key => {
      const select = document.getElementById(`wealth-${key}`);
      if (select) {
        select.value = this.context[key];
      }
    });
  }

  // API publique
  getContext() {
    return { ...this.context };
  }

  setContext(newContext) {
    this.context = { ...this.context, ...newContext };
    this.updateSelects();
    this.saveContext();
  }

  async initGlobalBadge() {
    try {
      // Import the badges component dynamically
      const { renderBadges } = await import('./Badges.js');

      const badgeContainer = document.getElementById('global-status-badge');
      if (badgeContainer) {
        // Connect to real data sources
        this.connectToRealData(badgeContainer, renderBadges);
        (window.debugLogger?.info || console.log)('✅ Global status badge initialized with real data sources');
      } else {
        (window.debugLogger?.warn || console.warn)('⚠️ global-status-badge container not found');
      }
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to initialize global status badge:', error);
    }
  }

  async connectToRealData(badgeContainer, renderBadges) {
    // Setup real data fetching from working APIs
    this.setupAPIDataFetching(badgeContainer, renderBadges);

    // Try to connect to existing stores and data sources
    this.setupRealDataIntegration(badgeContainer, renderBadges);

    // Auto-refresh every 30 seconds with real data
    setInterval(() => {
      this.refreshBadgeWithRealData(badgeContainer, renderBadges);
    }, 30000);
  }

  async setupAPIDataFetching(badgeContainer, renderBadges) {
    try {
      // Fetch real data from working APIs
      await this.fetchAndUpdateRealData();

      // Render with fresh data
      renderBadges(badgeContainer);
      (window.debugLogger?.info || console.log)('✅ Badge updated with real API data');
    } catch (error) {
      (window.debugLogger?.warn || console.warn)('API data fetch failed:', error);
      renderBadges(badgeContainer); // Fallback to default
    }
  }

  async fetchAndUpdateRealData() {
    try {
      // Parallel fetch of all available APIs
      const [riskData, balancesData] = await Promise.allSettled([
        fetch('/api/risk/dashboard').then(r => r.json()),
        fetch('/balances/current').then(r => r.json())
      ]);

      // Extract successful responses
      const risk = riskData.status === 'fulfilled' ? riskData.value : null;
      const balances = balancesData.status === 'fulfilled' ? balancesData.value : null;

      // Get ML status separately to avoid breaking main flow
      let mlStatus = null;
      try {
        const { getUnifiedMLStatus } = await import('../shared-ml-functions.js');
        mlStatus = await getUnifiedMLStatus();
        (window.debugLogger?.info || console.log)('✅ ML status loaded from unified source');
      } catch (error) {
        (window.debugLogger?.warn || console.warn)('⚠️ Unified ML source failed:', error.message);
        mlStatus = null;
      }

      // Determine data source priority: ML > Risk > Fallback
      let dataSource = 'backend';
      let timestamp = new Date().toISOString();
      let contradiction = 0.3; // Default fallback
      let engineCap = 20; // Default fallback
      let apiStatus = 'stale';

      // Use unified ML status from centralized source
      let modelsLoaded = 0;
      if (mlStatus) {
        dataSource = mlStatus.source;
        timestamp = mlStatus.timestamp;
        modelsLoaded = mlStatus.totalLoaded;

        // Use ML confidence for contradiction calculation
        const confidence = mlStatus.confidence || 0;
        contradiction = Math.max(0.1, Math.min(0.9, 1 - confidence));
        engineCap = Math.round(confidence < 0.5 ? 25 : 15 + ((1-confidence) * 10));
        apiStatus = mlStatus.source !== 'error' ? 'healthy' : 'stale';

        (window.debugLogger?.debug || console.log)(`🎯 Unified ML: ${modelsLoaded}/${mlStatus.totalModels} models, source: ${dataSource}, confidence: ${(confidence*100).toFixed(1)}%`);
      } else {
        // Fallback if unified ML fails - try Risk data first
        if (risk?.risk_metrics) {
          dataSource = 'risk_backend';
          timestamp = risk.timestamp || new Date().toISOString();
          modelsLoaded = 0; // No ML models from risk data
          contradiction = Math.min(0.5, risk.risk_metrics.volatility_annualized || 0.3);
          engineCap = Math.abs(risk.risk_metrics.var_95_1d || 0.03) * 100;
          apiStatus = 'healthy';
          (window.debugLogger?.debug || console.log)(`📊 Risk Backend: VaR ${risk.risk_metrics.var_95_1d?.toFixed(3)}, Vol ${(contradiction*100).toFixed(1)}%`);
        } else {
          // Final fallback
          dataSource = 'fallback';
          modelsLoaded = 4;
          const dayOfYear = Math.floor((Date.now() - new Date(new Date().getFullYear(), 0, 0)) / (1000 * 60 * 60 * 24));
          contradiction = 0.15 + ((dayOfYear % 7) * 0.01);
          engineCap = 18 + (dayOfYear % 5);
          apiStatus = 'stale';
          (window.debugLogger?.debug || console.log)(`⚠️ Badge using final fallback data`);
        }
      }

      // Risk Data section is now handled above
      if (false) { // Disabled - moved to else clause above
      } // End of disabled risk section

      // Detect overrides from portfolio state
      let overrides = [];
      if (balances?.items) {
        const totalValue = balances.items.reduce((sum, item) => sum + item.value_usd, 0);
        const topAsset = balances.items[0];
        const concentration = topAsset?.value_usd / totalValue || 0;

        // Add concentration override if BTC > 50%
        if (concentration > 0.5 && topAsset?.symbol === 'BTC') {
          overrides.push('btc_concentration_override');
        }
      }

      // Create unified store with best available data
      window.realDataStore = {
        risk,
        balances,
        mlStatus, // Unified ML status
        governance: {
          ml_signals: {
            decision_source: dataSource,
            updated: timestamp,
            models_loaded: modelsLoaded
          },
          status: {
            contradiction: contradiction
          },
          caps: {
            engine_cap: engineCap,
            active_policy: { cap_daily: 0.20 }
          },
          overrides: overrides
        },
        ui: {
          apiStatus: {
            backend: apiStatus
          }
        }
      };

      (window.debugLogger?.debug || console.log)(`🔗 Unified data: source=${dataSource}, models=${modelsLoaded}, contradiction=${(contradiction*100).toFixed(1)}%, cap=${engineCap}%, overrides=${overrides.length}`);

    } catch (error) {
      (window.debugLogger?.warn || console.warn)('Failed to fetch real API data:', error);
    }
  }

  async refreshBadgeWithRealData(badgeContainer, renderBadges) {
    try {
      // Refresh real data
      await this.fetchAndUpdateRealData();

      // Re-render badge
      renderBadges(badgeContainer);
    } catch (error) {
      console.debug('Badge refresh with real data failed:', error);
      // Fallback to basic refresh
      renderBadges(badgeContainer);
    }
  }

  setupRealDataIntegration(badgeContainer, renderBadges) {
    // Listen for governance state changes
    if (window.store && typeof window.store.subscribe === 'function') {
      (window.debugLogger?.debug || console.log)('🔗 Connected to window.store for real-time updates');
      window.store.subscribe(() => {
        try {
          renderBadges(badgeContainer);
        } catch (error) {
          console.debug('Store-triggered badge update failed:', error);
        }
      });
    }

    // Listen for wealth context changes (from this component)
    window.addEventListener('wealth:change', () => {
      setTimeout(() => renderBadges(badgeContainer), 100);
    });

    // Listen for governance updates if available
    window.addEventListener('governance:updated', () => {
      setTimeout(() => renderBadges(badgeContainer), 100);
    });

    // Listen for ML signals updates if available
    window.addEventListener('ml:signals:updated', () => {
      setTimeout(() => renderBadges(badgeContainer), 100);
    });

    (window.debugLogger?.debug || console.log)('🔗 Real data event listeners setup for badge updates');
  }
}

// Instance globale
const wealthContextBar = new WealthContextBar();

// Auto-init si DOM ready
const initWealthContextBar = () => {
  // Ne pas injecter si nav=off
  const params = new URLSearchParams(location.search);
  if (params.get('nav') === 'off') return;

  wealthContextBar.render();
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWealthContextBar);
} else {
  initWealthContextBar();
}

// Export pour usage externe
window.wealthContextBar = wealthContextBar;

export { wealthContextBar };