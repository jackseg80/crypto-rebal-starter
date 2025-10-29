/**
 * Export Button Module - Unified export system for Crypto, Saxo, and Wealth
 *
 * Usage:
 *   import { renderExportButton } from './modules/export-button.js';
 *
 *   // Crypto export
 *   renderExportButton(container, 'crypto', {
 *     endpoint: '/api/portfolio/export-lists',
 *     filename: 'crypto-portfolio'
 *   });
 *
 *   // Saxo export
 *   renderExportButton(container, 'saxo', {
 *     endpoint: '/api/saxo/export-lists',
 *     filename: 'saxo-portfolio'
 *   });
 *
 *   // Banks export
 *   renderExportButton(container, 'banks', {
 *     endpoint: '/api/wealth/banks/export-lists',
 *     filename: 'bank-accounts'
 *   });
 */

/**
 * Render export button with modal for format selection
 *
 * @param {HTMLElement} container - Container element
 * @param {string} module - Module type (crypto, saxo, banks)
 * @param {Object} options - Options
 * @param {string} options.endpoint - API endpoint
 * @param {string} options.filename - Base filename for export
 */
export function renderExportButton(container, module, options) {
    const { endpoint, filename } = options;

    // Create button
    const button = document.createElement('button');
    button.className = 'export-btn';
    button.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        <span>Export Lists</span>
    `;

    // Add styles
    button.style.cssText = `
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: var(--theme-surface-elevated);
        color: var(--theme-text);
        border: 1px solid var(--theme-border);
        border-radius: var(--radius-md);
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all var(--transition-normal);
        margin-top: 12px;
        width: 100%;
        justify-content: center;
    `;

    // Hover effect
    button.addEventListener('mouseenter', () => {
        button.style.borderColor = 'var(--brand-primary)';
        button.style.color = 'var(--brand-primary)';
        button.style.background = 'var(--theme-surface-hover)';
    });

    button.addEventListener('mouseleave', () => {
        button.style.borderColor = 'var(--theme-border)';
        button.style.color = 'var(--theme-text)';
        button.style.background = 'var(--theme-surface-elevated)';
    });

    // Click handler - Open modal
    button.addEventListener('click', () => {
        // Get context data dynamically
        const cryptoSource = module === 'crypto' ?
            (window.globalConfig?.get('data_source') || localStorage.getItem('data_source') || 'cointracking') : null;
        const saxoFileKey = module === 'saxo' ? (window.currentFileKey || null) : null;

        openExportModal(module, endpoint, filename, cryptoSource, saxoFileKey);
    });

    container.appendChild(button);
}

/**
 * Open export modal for format selection
 *
 * @param {string} module - Module type (crypto, saxo, banks)
 * @param {string} endpoint - API endpoint
 * @param {string} filename - Base filename for export
 * @param {string} [source] - Optional source for crypto
 * @param {string} [fileKey] - Optional file_key for saxo
 */
export function openExportModal(module, endpoint, filename, source = null, fileKey = null) {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'export-modal-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        animation: fadeIn 0.2s ease;
    `;

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'export-modal';
    modal.style.cssText = `
        background: var(--theme-surface);
        border: 1px solid var(--theme-border);
        border-radius: var(--radius-lg);
        padding: 24px;
        max-width: 500px;
        width: 90%;
        box-shadow: var(--shadow-xl);
        animation: slideUp 0.3s ease;
    `;

    const moduleNames = {
        crypto: 'Crypto Portfolio',
        saxo: 'Saxo Bank Portfolio',
        banks: 'Bank Accounts'
    };

    modal.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="font-size: 20px; font-weight: 700; color: var(--theme-text);">
                📥 Export ${moduleNames[module] || 'Data'}
            </h2>
            <button class="close-btn" style="background: none; border: none; font-size: 24px; cursor: pointer; color: var(--theme-text-muted); padding: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 6px; transition: all 0.2s;">
                ×
            </button>
        </div>

        <p style="color: var(--theme-text-muted); margin-bottom: 20px; font-size: 14px;">
            Choose the export format for your ${moduleNames[module]?.toLowerCase() || 'data'}:
        </p>

        <div class="format-options" style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px;">
            <button class="format-btn" data-format="json" style="display: flex; align-items: center; gap: 12px; padding: 16px; background: var(--theme-surface-elevated); border: 2px solid var(--theme-border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.2s; text-align: left;">
                <div style="font-size: 24px;">📄</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--theme-text); margin-bottom: 4px;">JSON</div>
                    <div style="font-size: 12px; color: var(--theme-text-muted);">Structured data for developers & APIs</div>
                </div>
            </button>

            <button class="format-btn" data-format="csv" style="display: flex; align-items: center; gap: 12px; padding: 16px; background: var(--theme-surface-elevated); border: 2px solid var(--theme-border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.2s; text-align: left;">
                <div style="font-size: 24px;">📊</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--theme-text); margin-bottom: 4px;">CSV</div>
                    <div style="font-size: 12px; color: var(--theme-text-muted);">Spreadsheet-compatible (Excel, Google Sheets)</div>
                </div>
            </button>

            <button class="format-btn" data-format="markdown" style="display: flex; align-items: center; gap: 12px; padding: 16px; background: var(--theme-surface-elevated); border: 2px solid var(--theme-border); border-radius: var(--radius-md); cursor: pointer; transition: all 0.2s; text-align: left;">
                <div style="font-size: 24px;">📝</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: var(--theme-text); margin-bottom: 4px;">Markdown</div>
                    <div style="font-size: 12px; color: var(--theme-text-muted);">Human-readable formatted text</div>
                </div>
            </button>
        </div>

        <div class="export-status" style="padding: 12px; background: var(--theme-bg); border-radius: var(--radius-md); font-size: 13px; color: var(--theme-text-muted); display: none;">
            <span class="status-text">⏳ Exporting...</span>
        </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Add animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .format-btn:hover {
            border-color: var(--brand-primary) !important;
            background: var(--theme-surface-hover) !important;
            transform: translateX(4px);
        }

        .close-btn:hover {
            background: var(--theme-surface-hover) !important;
            color: var(--theme-text) !important;
        }
    `;
    document.head.appendChild(style);

    // Close handlers
    const closeBtn = modal.querySelector('.close-btn');
    closeBtn.addEventListener('click', () => {
        overlay.remove();
        style.remove();
    });

    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
            style.remove();
        }
    });

    // Format button handlers
    const formatBtns = modal.querySelectorAll('.format-btn');
    formatBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const format = btn.dataset.format;
            await handleExport(module, endpoint, filename, format, modal, source, fileKey);
        });
    });
}

/**
 * Handle export download
 */
async function handleExport(module, endpoint, filename, format, modal, source = null, fileKey = null) {
    const statusDiv = modal.querySelector('.export-status');
    const statusText = modal.querySelector('.status-text');

    try {
        // Show loading
        statusDiv.style.display = 'block';
        statusText.textContent = '⏳ Exporting...';
        statusText.style.color = 'var(--theme-text-muted)';

        // Build URL with format only
        const activeUser = localStorage.getItem('activeUser') || 'demo';
        let url = `${window.globalConfig?.API_BASE_URL || ''}${endpoint}?format=${format}`;

        // Add source for Crypto (passed as parameter or from context)
        if (module === 'crypto') {
            const cryptoSource = source || window.globalConfig?.get('data_source') || localStorage.getItem('data_source') || 'cointracking';
            url += `&source=${encodeURIComponent(cryptoSource)}`;
            console.debug(`📄 Export with crypto source: ${cryptoSource}`);
        }

        // Add file_key for Saxo if available (passed as parameter or from context)
        if (module === 'saxo' && (fileKey || window.currentFileKey)) {
            const saxoFileKey = fileKey || window.currentFileKey;
            url += `&file_key=${encodeURIComponent(saxoFileKey)}`;
            console.debug(`📄 Export with file_key: ${saxoFileKey}`);
        }

        // Fetch export with X-User header (multi-tenant)
        const response = await fetch(url, {
            headers: {
                'X-User': activeUser
            }
        });

        if (!response.ok) {
            throw new Error(`Export failed: ${response.statusText}`);
        }

        const blob = await response.blob();

        // Determine file extension
        const extensions = {
            json: 'json',
            csv: 'csv',
            markdown: 'md'
        };

        const ext = extensions[format] || format;
        const timestamp = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
        const downloadFilename = `${filename}_${timestamp}.${ext}`;

        // Download file
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = downloadFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(downloadUrl);

        // Show success
        statusText.textContent = `✅ Downloaded: ${downloadFilename}`;
        statusText.style.color = 'var(--success)';

        // Auto-close after 2s
        setTimeout(() => {
            const overlay = modal.closest('.export-modal-overlay');
            if (overlay) {
                overlay.remove();
            }
        }, 2000);

    } catch (error) {
        console.error('Export error:', error);
        statusText.textContent = `❌ Export failed: ${error.message}`;
        statusText.style.color = 'var(--danger)';
        statusDiv.style.display = 'block';
    }
}
