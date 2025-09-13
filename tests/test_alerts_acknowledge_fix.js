(function() {
    const API_BASE = window.location.origin;
    
    function showResult(containerId, message, isSuccess = true) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const div = document.createElement('div');
        div.className = `result ${isSuccess ? 'success' : 'error'}`;
        div.textContent = message;
        container.appendChild(div);
    }
    
    async function testEndpoints() {
        const container = document.getElementById('endpoint-results');
        container.innerHTML = '';
        
        const endpoints = [
            '/api/alerts/test/acknowledge/TEST-001',
            '/api/alerts/test/snooze/TEST-001',
            '/api/alerts/active',
            '/api/alerts/types'
        ];
        
        for (const endpoint of endpoints) {
            try {
                const method = endpoint.includes('/acknowledge/') || endpoint.includes('/snooze/') ? 'POST' : 'GET';
                const response = await fetch(`${API_BASE}${endpoint}`, { method });
                showResult('endpoint-results', 
                    `${method} ${endpoint}: ${response.status} ${response.statusText}`, 
                    response.ok || response.status === 404); // 404 is OK for non-existent alert IDs
            } catch (error) {
                showResult('endpoint-results', 
                    `${endpoint}: Error - ${error.message}`, false);
            }
        }
    }
    
    async function generateTestAlert() {
        const container = document.getElementById('alert-generation-result');
        container.innerHTML = '';
        
        try {
            // Try primary endpoint
            let response = await fetch(`${API_BASE}/api/alerts/test/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    alert_type: "PORTFOLIO_DRIFT",
                    severity: "S2",
                    data: { test: true, drift: 0.15 }
                })
            });

            // Fallbacks if 404 (some environments may not register alias)
            if (response.status === 404) {
                try {
                    response = await fetch(`${API_BASE}/api/alerts/test/generate/1`, { method: 'POST' });
                } catch (_) {}
            }
            if (response.status === 404) {
                try {
                    response = await fetch(`${API_BASE}/api/alerts/test/generate`, { method: 'GET' });
                } catch (_) {}
            }
            
            if (response.ok) {
                const result = await response.json();
                showResult('alert-generation-result', 
                    `Alert generated: ${result.alert_id || 'Success'}`, true);
                document.getElementById('alertId').value = result.alert_id || 'TEST-ACK-001';
            } else {
                showResult('alert-generation-result', 
                    `Failed to generate alert: ${response.status}`, false);
            }
        } catch (error) {
            showResult('alert-generation-result', 
                `Error generating alert: ${error.message}`, false);
        }
    }
    
    async function testAcknowledge() {
        const alertId = document.getElementById('alertId').value;
        const container = document.getElementById('action-results');
        
        try {
            const response = await fetch(`${API_BASE}/api/alerts/test/acknowledge/${alertId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: "test_user" })
            });
            
            if (response.ok) {
                const result = await response.json();
                showResult('action-results', 
                    `✓ Acknowledge successful for ${alertId}: ${result.message || 'OK'}`, true);
            } else {
                showResult('action-results', 
                    `✗ Acknowledge failed for ${alertId}: ${response.status}`, false);
            }
        } catch (error) {
            showResult('action-results', 
                `✗ Acknowledge error for ${alertId}: ${error.message}`, false);
        }
    }
    
    async function testSnooze() {
        const alertId = document.getElementById('alertId').value;
        const container = document.getElementById('action-results');
        
        try {
            const response = await fetch(`${API_BASE}/api/alerts/test/snooze/${alertId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    user_id: "test_user",
                    snooze_duration_minutes: 60
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                showResult('action-results', 
                    `✓ Snooze successful for ${alertId}: ${result.message || 'OK'}`, true);
            } else {
                showResult('action-results', 
                    `✗ Snooze failed for ${alertId}: ${response.status}`, false);
            }
        } catch (error) {
            showResult('action-results', 
                `✗ Snooze error for ${alertId}: ${error.message}`, false);
        }
    }
    
    // Event delegation for button clicks
    document.addEventListener('click', function(e) {
        const action = e.target.getAttribute('data-action');
        if (action) {
            switch(action) {
                case 'testEndpoints':
                    testEndpoints();
                    break;
                case 'generateTestAlert':
                    generateTestAlert();
                    break;
                case 'testAcknowledge':
                    testAcknowledge();
                    break;
                case 'testSnooze':
                    testSnooze();
                    break;
            }
        }
    });
    
    // Auto-run endpoint test on load
    window.addEventListener('load', () => {
        setTimeout(testEndpoints, 1000);
    });
})();
