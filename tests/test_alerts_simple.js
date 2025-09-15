(function() {
    const API_BASE = window.location.origin;
    let alertsData = [];
    let simulatedActions = new Map(); // For client-side simulation
    
    function log(message, level = 'INFO') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${level}: ${message}\n`;
        const logsEl = document.getElementById('logs');
        if (logsEl) {
            logsEl.textContent += logEntry;
            logsEl.scrollTop = logsEl.scrollHeight;
        }
    }

    function showResult(message, isSuccess = true) {
        const container = document.getElementById('results');
        if (!container) return;
        
        const div = document.createElement('div');
        div.className = `result ${isSuccess ? 'success' : 'error'}`;
        div.textContent = message;
        container.appendChild(div);
    }

    async function apiCall(endpoint, method = 'GET') {
        try {
            log(`${method} ${endpoint}`, 'REQUEST');
            const response = await fetch(`${API_BASE}${endpoint}`, { method });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            log(`Response OK: ${JSON.stringify(result).substring(0, 100)}...`, 'RESPONSE');
            return result;
        } catch (error) {
            log(`Error: ${error.message}`, 'ERROR');
            throw error;
        }
    }

    // Simulate some test alerts for demonstration
    function generateTestAlerts() {
        return [
            {
                id: "TEST-SIMPLE-001",
                alert_type: "PORTFOLIO_DRIFT",
                severity: "S2", 
                created_at: new Date().toISOString(),
                data: {
                    current_drift: 0.15,
                    threshold: 0.10,
                    test_alert: true
                }
            },
            {
                id: "TEST-SIMPLE-002", 
                alert_type: "VOL_Q90_CROSS",
                severity: "S3",
                created_at: new Date(Date.now() - 5*60*1000).toISOString(),
                data: {
                    volatility: 0.28,
                    threshold: 0.15,
                    test_alert: true
                }
            },
            {
                id: "TEST-SIMPLE-003",
                alert_type: "REGIME_FLIP", 
                severity: "S1",
                created_at: new Date(Date.now() - 10*60*1000).toISOString(),
                data: {
                    old_regime: "bull",
                    new_regime: "bear",
                    confidence: 0.89,
                    test_alert: true
                }
            }
        ];
    }

    // Event handlers
    const actions = {
        async testTypes() {
            try {
                const result = await apiCall('/api/alerts/types');
                showResult(`Types: ${result.alert_types?.length || 0} types, ${result.severities?.length || 0} severités`);
            } catch (error) {
                showResult(`Erreur types: ${error.message}`, false);
            }
        },

        async testHealth() {
            try {
                const result = await apiCall('/api/alerts/health');
                showResult(`Santé: ${result.status} (${result.host_id || 'unknown'})`);
            } catch (error) {
                showResult(`Erreur santé: ${error.message}`, false);
            }
        },

        async testMetrics() {
            try {
                const result = await apiCall('/api/alerts/metrics');
                showResult(`Métriques chargées - timestamp: ${result.timestamp}`);
            } catch (error) {
                showResult(`Erreur métriques: ${error.message}`, false);
            }
        },

        async loadAlerts() {
            try {
                // Try to get real alerts first
                const realAlerts = await apiCall('/api/alerts/active');
                
                if (realAlerts && realAlerts.length > 0) {
                    alertsData = realAlerts;
                    log(`Loaded ${realAlerts.length} real alerts from API`, 'SUCCESS');
                } else {
                    // Fallback to simulated alerts
                    alertsData = generateTestAlerts();
                    log(`No real alerts found, using ${alertsData.length} simulated alerts`, 'INFO');
                }
                
                displayAlerts();
                showResult(`${alertsData.length} alertes chargées (${realAlerts?.length > 0 ? 'real' : 'simulated'})`);
            } catch (error) {
                // If API fails, use simulated alerts
                alertsData = generateTestAlerts();
                log(`API failed, using ${alertsData.length} simulated alerts`, 'WARN');
                displayAlerts();
                showResult(`${alertsData.length} alertes simulées chargées (API indisponible)`, false);
            }
        },

        clearSimulation() {
            simulatedActions.clear();
            log('SIMULATION: Cleared all simulated actions', 'INFO');
            displayAlerts();
        },

        clearLogs() {
            const logsEl = document.getElementById('logs');
            if (logsEl) logsEl.textContent = 'Logs cleared\n';
        },

        async testNewEndpoints() {
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
                    const div = document.createElement('div');
                    div.className = `result ${response.ok ? 'success' : 'error'}`;
                    div.textContent = `${response.ok ? '✓' : '✗'} ${endpoint} (${response.status})`;
                    if (container) container.appendChild(div);
                } catch (error) {
                    const div = document.createElement('div');
                    div.className = 'result error';
                    div.textContent = `✗ ${endpoint} failed: ${error.message}`;
                    if (container) container.appendChild(div);
                }
            }
        },

        async testRemovedEndpoints() {
            const removedEndpoints = [
                '/api/realtime/publish',
                '/api/realtime/broadcast',
                '/api/ml-predictions/predict', 
                '/api/alerts/test/generate'
            ];
            
            const container = document.getElementById('refactor-results');
            
            for (const endpoint of removedEndpoints) {
                try {
                    const response = await fetch(`${API_BASE}${endpoint}`, {method: 'POST'});
                    const div = document.createElement('div');
                    div.className = `result ${response.status === 404 ? 'success' : 'error'}`;
                    div.textContent = response.status === 404 ? 
                        `✓ ${endpoint} correctly removed (404)` : 
                        `⚠ ${endpoint} still exists (${response.status})`;
                    if (container) container.appendChild(div);
                } catch (error) {
                    const div = document.createElement('div');
                    div.className = 'result success';
                    div.textContent = `✓ ${endpoint} correctly removed (network error)`;
                    if (container) container.appendChild(div);
                }
            }
        },

        simulateAck(alertId) {
            simulatedActions.set(alertId, {
                action: 'acknowledged',
                user: 'test_user',
                timestamp: new Date().toLocaleTimeString()
            });
            log(`SIMULATION: Alert ${alertId} acknowledged`, 'SUCCESS');
            displayAlerts();
        },

        simulateSnooze(alertId) {
            simulatedActions.set(alertId, {
                action: 'snoozed',
                user: 'test_user',
                timestamp: new Date().toLocaleTimeString(),
                snooze_until: new Date(Date.now() + 60*60*1000).toLocaleTimeString()
            });
            log(`SIMULATION: Alert ${alertId} snoozed for 60 minutes`, 'SUCCESS');
            displayAlerts();
        }
    };

    function displayAlerts() {
        const container = document.getElementById('alerts-display');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (alertsData.length === 0) {
            container.innerHTML = '<p>Aucune alerte active</p>';
            return;
        }

        alertsData.forEach(alert => {
            // Check if alert has been simulated as acknowledged/snoozed
            const simAction = simulatedActions.get(alert.id);
            
            const div = document.createElement('div');
            div.className = 'alert-item';
            div.innerHTML = `
                <strong>${alert.alert_type}</strong> - ${alert.severity}<br>
                <small>ID: ${alert.id}</small><br>
                <small>Created: ${new Date(alert.created_at).toLocaleString()}</small><br>
                ${simAction ? `<span style="color: #10b981;">✓ ${simAction.action} by ${simAction.user} at ${simAction.timestamp}</span><br>` : ''}
                <small>Data: ${JSON.stringify(alert.data).substring(0, 80)}...</small><br>
                <button class="btn btn-success" data-action="simulateAck" data-alert-id="${alert.id}" ${simAction?.action === 'acknowledged' ? 'disabled' : ''}>ACK</button>
                <button class="btn btn-primary" data-action="simulateSnooze" data-alert-id="${alert.id}" ${simAction?.action === 'snoozed' ? 'disabled' : ''}>Snooze</button>
            `;
            container.appendChild(div);
        });
    }

    // Event delegation for button clicks
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
        log('Simple alert test page loaded successfully', 'INFO');
        log('Using client-side simulation for ACK/Snooze actions', 'INFO');
        
        // Auto-test on load
        setTimeout(() => {
            actions.testTypes();
            actions.loadAlerts();
        }, 500);
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();