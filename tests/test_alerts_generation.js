(function() {
    const API_BASE = window.location.origin;
    
    function log(message, level = 'INFO') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${level}: ${message}\n`;
        const logsEl = document.getElementById('logs');
        if (logsEl) {
            logsEl.textContent += logEntry;
            logsEl.scrollTop = logsEl.scrollHeight;
        }
    }

    function showResult(containerId, message, isSuccess) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const div = document.createElement('div');
        div.className = `result ${isSuccess ? 'success' : 'error'}`;
        div.textContent = message;
        container.appendChild(div);
    }

    async function apiCall(endpoint, method = 'GET', data = null) {
        try {
            log(`${method} ${endpoint}`, 'REQUEST');
            
            const options = {
                method,
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer test-token', // Basic auth for testing
                    'X-User': 'system_user' // Fallback user header
                }
            };
            
            if (data) options.body = JSON.stringify(data);
            
            const response = await fetch(`${API_BASE}${endpoint}`, options);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            log(`Response OK: ${JSON.stringify(result).substring(0, 150)}...`, 'RESPONSE');
            return result;
            
        } catch (error) {
            log(`Error: ${error.message}`, 'ERROR');
            throw error;
        }
    }

    // Tests de base
    async function testAlertTypes() {
        try {
            const result = await apiCall('/api/alerts/types');
            showResult('basic-results', 
                `Types charges: ${result.alert_types?.length || 0} types, ${result.severities?.length || 0} severites`, 
                true);
        } catch (error) {
            showResult('basic-results', `Test types failed: ${error.message}`, false);
        }
    }

    async function testAlertHealth() {
        try {
            const result = await apiCall('/api/alerts/health');
            showResult('basic-results', 
                `Sante systeme: ${result.status} (${result.host_id || 'unknown'})`, 
                result.status === 'healthy');
        } catch (error) {
            showResult('basic-results', `Test sante failed: ${error.message}`, false);
        }
    }

    async function testAlertMetrics() {
        try {
            const result = await apiCall('/api/alerts/metrics');
            showResult('basic-results', 
                `Metriques chargees - timestamp: ${result.timestamp}`, 
                true);
        } catch (error) {
            showResult('basic-results', `Test metriques failed: ${error.message}`, false);
        }
    }

    async function testAlertConfig() {
        try {
            const result = await apiCall('/api/alerts/config/current');
            showResult('basic-results', 
                `Config: ${result.config_file_path}`, 
                true);
        } catch (error) {
            showResult('basic-results', `Test config failed: ${error.message}`, false);
        }
    }

    // Alertes actives
    async function loadActiveAlerts() {
        try {
            const alerts = await apiCall('/api/alerts/active');
            const container = document.getElementById('alerts-display');
            if (!container) return;
            
            container.innerHTML = '';
            
            if (alerts && alerts.length > 0) {
                alerts.forEach((alert, index) => {
                    const div = document.createElement('div');
                    div.className = `alert-item alert-${alert.severity.toLowerCase()}`;
                    div.innerHTML = `
                        <strong>${alert.alert_type}</strong> - ${alert.severity}<br>
                        <small>ID: ${alert.id}</small><br>
                        <small>Created: ${new Date(alert.created_at).toLocaleString()}</small><br>
                        <small>Data: ${JSON.stringify(alert.data).substring(0, 80)}...</small><br>
                        <button class="btn btn-success" data-action="quickAcknowledge" data-alert-id="${alert.id}">ACK</button>
                        <button class="btn btn-primary" data-action="quickSnooze" data-alert-id="${alert.id}">Snooze</button>
                    `;
                    container.appendChild(div);
                });
            } else {
                container.innerHTML = '<p>Aucune alerte active</p>';
            }
            
            showResult('alerts-display', `${alerts?.length || 0} alertes trouvees`, true);
        } catch (error) {
            showResult('alerts-display', `Erreur chargement: ${error.message}`, false);
        }
    }

    async function loadAlertHistory() {
        try {
            const result = await apiCall('/api/alerts/history?limit=10');
            const container = document.getElementById('alerts-display');
            if (!container) return;
            
            container.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
            showResult('alerts-display', 'Historique charge', true);
        } catch (error) {
            showResult('alerts-display', `Erreur historique: ${error.message}`, false);
        }
    }

    // Actions sur alertes
    async function acknowledgeAlert() {
        const alertId = document.getElementById('alert-id')?.value;
        if (!alertId) {
            showResult('actions-results', 'Veuillez entrer un ID d\'alerte', false);
            return;
        }
        
        try {
            await apiCall(`/api/alerts/test/acknowledge/${alertId}`, 'POST');
            showResult('actions-results', `Alerte ${alertId} acknowledged`, true);
            loadActiveAlerts(); // refresh
        } catch (error) {
            showResult('actions-results', `Erreur acknowledge: ${error.message}`, false);
        }
    }

    async function snoozeAlert() {
        const alertId = document.getElementById('alert-id')?.value;
        if (!alertId) {
            showResult('actions-results', 'Veuillez entrer un ID d\'alerte', false);
            return;
        }
        
        try {
            await apiCall(`/api/alerts/test/snooze/${alertId}`, 'POST', {minutes: 60});
            showResult('actions-results', `Alerte ${alertId} snoozed 60min`, true);
            loadActiveAlerts(); // refresh
        } catch (error) {
            showResult('actions-results', `Erreur snooze: ${error.message}`, false);
        }
    }

    async function quickAcknowledge(alertId) {
        try {
            await apiCall(`/api/alerts/test/acknowledge/${alertId}`, 'POST');
            showResult('alerts-display', `Quick ACK: ${alertId}`, true);
            loadActiveAlerts();
        } catch (error) {
            showResult('alerts-display', `Quick ACK failed: ${error.message}`, false);
        }
    }

    async function quickSnooze(alertId) {
        try {
            await apiCall(`/api/alerts/test/snooze/${alertId}`, 'POST', {minutes: 60});
            showResult('alerts-display', `Quick Snooze: ${alertId}`, true);
            loadActiveAlerts();
        } catch (error) {
            showResult('alerts-display', `Quick Snooze failed: ${error.message}`, false);
        }
    }

    // Tests post-refactoring
    async function testNewEndpoints() {
        const endpoints = [
            '/api/alerts/active',
            '/api/alerts/types', 
            '/api/alerts/health',
            '/api/alerts/metrics',
            '/api/ml/status',
            '/api/risk/status'
        ];
        
        const container = document.getElementById('refactor-results');
        if (container) container.innerHTML = '';
        
        for (const endpoint of endpoints) {
            try {
                const response = await fetch(`${API_BASE}${endpoint}`);
                showResult('refactor-results', 
                    `✓ ${endpoint} (${response.status})`, 
                    response.ok);
            } catch (error) {
                showResult('refactor-results', 
                    `✗ ${endpoint} failed: ${error.message}`, 
                    false);
            }
        }
    }

    async function testRemovedEndpoints() {
        const removedEndpoints = [
            '/api/realtime/publish',
            '/api/realtime/broadcast',
            '/api/ml-predictions/predict', 
            '/api/alerts/test/generate'
        ];
        
        for (const endpoint of removedEndpoints) {
            try {
                const response = await fetch(`${API_BASE}${endpoint}`, {method: 'POST'});
                if (response.status === 404) {
                    showResult('refactor-results', 
                        `✓ ${endpoint} correctly removed (404)`, 
                        true);
                } else {
                    showResult('refactor-results', 
                        `⚠ ${endpoint} still exists (${response.status})`, 
                        false);
                }
            } catch (error) {
                showResult('refactor-results', 
                    `✓ ${endpoint} correctly removed (network error)`, 
                    true);
            }
        }
    }

    function clearLogs() {
        const logsEl = document.getElementById('logs');
        if (logsEl) logsEl.textContent = '';
    }

    // Action dispatcher
    const actions = {
        testAlertTypes,
        testAlertHealth,
        testAlertMetrics,
        testAlertConfig,
        loadActiveAlerts,
        loadAlertHistory,
        acknowledgeAlert,
        snoozeAlert,
        testNewEndpoints,
        testRemovedEndpoints,
        clearLogs,
        quickAcknowledge,
        quickSnooze
    };

    // Event delegation for buttons
    document.addEventListener('click', function(e) {
        const action = e.target.getAttribute('data-action');
        if (action && actions[action]) {
            const alertId = e.target.getAttribute('data-alert-id');
            if (alertId) {
                actions[action](alertId);
            } else {
                actions[action]();
            }
        }
    });

    // Initialize when DOM is ready
    function initialize() {
        log('Alert test page loaded successfully', 'INFO');
        log('Ready to test alert system endpoints', 'INFO');
        
        // Auto-test on load
        setTimeout(() => {
            testAlertTypes();
            loadActiveAlerts();
        }, 500);
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();