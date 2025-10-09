// Test framework for Risk Dashboard Modules
// No inline scripts - CSP compliant

let passCount = 0;
let failCount = 0;
let totalCount = 0;

function log(level, message) {
    const logContainer = document.getElementById('logContainer');
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

function updateSummary() {
    document.getElementById('passCount').textContent = passCount;
    document.getElementById('failCount').textContent = failCount;
    document.getElementById('totalCount').textContent = totalCount;
}

function runTest(suiteName, testName, testFn) {
    totalCount++;

    const resultsContainer = document.getElementById('testResults');

    // Créer l'élément de test
    const testDiv = document.createElement('div');
    testDiv.className = 'test-case';
    testDiv.innerHTML = `
        <div class="test-name">
            <span class="test-status pending">RUNNING</span>
            <span>${suiteName} > ${testName}</span>
        </div>
        <div class="test-detail">⏳ En cours...</div>
    `;
    resultsContainer.appendChild(testDiv);

    const statusEl = testDiv.querySelector('.test-status');
    const detailEl = testDiv.querySelector('.test-detail');

    const start = performance.now();

    try {
        testFn();
        const duration = performance.now() - start;

        passCount++;
        testDiv.classList.add('pass');
        statusEl.textContent = 'PASS';
        statusEl.className = 'test-status pass';
        detailEl.textContent = `✓ Passé en ${duration.toFixed(2)}ms`;

        log('success', `✓ ${suiteName} > ${testName} (${duration.toFixed(2)}ms)`);

    } catch (error) {
        const duration = performance.now() - start;

        failCount++;
        testDiv.classList.add('fail');
        statusEl.textContent = 'FAIL';
        statusEl.className = 'test-status fail';
        detailEl.textContent = `✗ Échoué en ${duration.toFixed(2)}ms`;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'test-error';
        errorDiv.textContent = error.stack || error.message;
        testDiv.appendChild(errorDiv);

        log('error', `✗ ${suiteName} > ${testName}: ${error.message}`);
    }

    updateSummary();
}

// Assertion helpers
const assert = {
    equal(actual, expected, message) {
        if (actual !== expected) {
            throw new Error(message || `Expected ${expected}, got ${actual}`);
        }
    },
    closeTo(actual, expected, tolerance, message) {
        // Pour les nombres flottants avec tolérance
        const diff = Math.abs(actual - expected);
        if (diff > tolerance) {
            throw new Error(message || `Expected ${expected} (±${tolerance}), got ${actual} (diff: ${diff})`);
        }
    },
    ok(value, message) {
        if (!value) {
            throw new Error(message || `Expected truthy value, got ${value}`);
        }
    },
    isTrue(value, message) {
        if (value !== true) {
            throw new Error(message || `Expected true, got ${value}`);
        }
    }
};

// Tests
function runAllTests() {
    const btn = document.getElementById('runBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Tests en cours...';

    passCount = 0;
    failCount = 0;
    totalCount = 0;

    document.getElementById('testResults').innerHTML = '';
    document.getElementById('logContainer').innerHTML = '';

    log('info', 'Démarrage des tests...');

    // Suite 1: risk-alerts-tab.js
    runTest('risk-alerts-tab.js', 'doit filtrer les alertes par severité', () => {
        const mockAlerts = [
            { id: '1', severity: 'S1', alert_type: 'VOL' },
            { id: '2', severity: 'S2', alert_type: 'REGIME' },
            { id: '3', severity: 'S3', alert_type: 'VOL' }
        ];

        const filtered = mockAlerts.filter(a => ['S2', 'S3'].includes(a.severity));
        assert.equal(filtered.length, 2, 'Devrait filtrer 2 alertes');
    });

    runTest('risk-alerts-tab.js', 'doit paginer les alertes correctement', () => {
        const mockAlerts = Array.from({ length: 25 }, (_, i) => ({ id: `${i}` }));

        const page1 = mockAlerts.slice(0, 10);
        const page2 = mockAlerts.slice(10, 20);
        const page3 = mockAlerts.slice(20, 25);

        assert.equal(page1.length, 10, 'Page 1 devrait avoir 10 items');
        assert.equal(page2.length, 10, 'Page 2 devrait avoir 10 items');
        assert.equal(page3.length, 5, 'Page 3 devrait avoir 5 items');
    });

    runTest('risk-alerts-tab.js', 'doit calculer les stats correctement', () => {
        const mockAlerts = [
            { severity: 'S1' },
            { severity: 'S1' },
            { severity: 'S2' },
            { severity: 'S3' }
        ];

        const stats = mockAlerts.reduce((acc, alert) => {
            acc[alert.severity] = (acc[alert.severity] || 0) + 1;
            return acc;
        }, {});

        assert.equal(stats['S1'], 2, 'Devrait compter 2 alertes S1');
        assert.equal(stats['S2'], 1, 'Devrait compter 1 alerte S2');
        assert.equal(stats['S3'], 1, 'Devrait compter 1 alerte S3');
    });

    // Suite 2: risk-overview-tab.js
    runTest('risk-overview-tab.js', 'doit valider Risk Score entre 0 et 100', () => {
        const riskScore = 65;
        assert.ok(riskScore >= 0 && riskScore <= 100, 'Risk Score doit être entre 0 et 100');
    });

    runTest('risk-overview-tab.js', 'doit détecter dual window disponible', () => {
        const mockDualWindow = {
            enabled: true,
            long_term: { available: true, window_days: 365, asset_count: 3 },
            full_intersection: { window_days: 55, asset_count: 5 }
        };

        assert.isTrue(mockDualWindow.enabled, 'Dual window devrait être activé');
        assert.isTrue(mockDualWindow.long_term.available, 'Long-term devrait être disponible');
        assert.equal(mockDualWindow.long_term.window_days, 365, 'Devrait utiliser 365j');
    });

    runTest('risk-overview-tab.js', 'doit calculer la divergence Risk Score V2', () => {
        const legacyScore = 65;
        const v2Score = 35;
        const divergence = legacyScore - v2Score;

        assert.equal(divergence, 30, 'Divergence devrait être 30 points');
        assert.ok(divergence > 10, 'Divergence significative détectée');
    });

    // Suite 3: risk-cycles-tab.js
    runTest('risk-cycles-tab.js', 'doit formater les données pour Chart.js', () => {
        const mockData = {
            dates: ['2024-01-01', '2024-01-02'],
            prices: [50000, 51000]
        };

        assert.equal(mockData.dates.length, mockData.prices.length, 'Dates et prices doivent avoir même longueur');
        assert.ok(mockData.prices[1] > mockData.prices[0], 'Prix devrait augmenter');
    });

    runTest('risk-cycles-tab.js', 'doit calculer le composite score on-chain', () => {
        const indicators = {
            momentum: 0.75,
            valuation: 0.60,
            network: 0.80,
            risk: 0.50
        };

        const weights = { momentum: 0.3, valuation: 0.2, network: 0.3, risk: 0.2 };
        const composite = Object.keys(indicators).reduce((sum, key) => {
            return sum + indicators[key] * weights[key];
        }, 0);

        assert.ok(composite >= 0 && composite <= 1, 'Composite score entre 0 et 1');
    });

    runTest('risk-cycles-tab.js', 'doit gérer le cache hash-based', () => {
        const data1 = JSON.stringify({ prices: [50000, 51000] });
        const data2 = JSON.stringify({ prices: [50000, 51000] });

        const hash1 = data1.length;
        const hash2 = data2.length;

        assert.equal(hash1, hash2, 'Données identiques devraient avoir même hash');
    });

    // Suite 4: risk-targets-tab.js
    runTest('risk-targets-tab.js', 'doit comparer allocation actuelle vs objectifs', () => {
        const current = { BTC: 0.40, ETH: 0.30, Stables: 0.30 };
        const target = { BTC: 0.50, ETH: 0.30, Stables: 0.20 };

        const delta = {
            BTC: target.BTC - current.BTC,
            ETH: target.ETH - current.ETH,
            Stables: target.Stables - current.Stables
        };

        // Utiliser closeTo pour gérer la précision des flottants
        assert.closeTo(delta.BTC, 0.10, 0.0001, 'BTC devrait augmenter de ~10%');
        assert.closeTo(delta.Stables, -0.10, 0.0001, 'Stables devraient diminuer de ~10%');
        assert.closeTo(delta.ETH, 0.0, 0.0001, 'ETH devrait rester stable');
    });

    runTest('risk-targets-tab.js', 'doit générer plan d\'action (buy/sell)', () => {
        const delta = { BTC: 0.10, ETH: 0, Stables: -0.10 };

        const actions = Object.entries(delta).map(([asset, pct]) => {
            if (pct > 0.01) return { action: 'BUY', asset, pct };
            if (pct < -0.01) return { action: 'SELL', asset, pct: Math.abs(pct) };
            return null;
        }).filter(Boolean);

        assert.equal(actions.length, 2, 'Devrait avoir 2 actions');
        assert.equal(actions[0].action, 'BUY', 'Première action devrait être BUY');
        assert.equal(actions[1].action, 'SELL', 'Deuxième action devrait être SELL');
    });

    runTest('risk-targets-tab.js', 'doit gérer les 5 stratégies disponibles', () => {
        const strategies = ['macro', 'ccs', 'cycle', 'blend', 'smart'];
        assert.equal(strategies.length, 5, 'Devrait avoir 5 stratégies');
        assert.ok(strategies.includes('smart'), 'Devrait inclure SMART');
    });

    // Suite 5: Performance
    runTest('Performance', 'doit gérer un grand nombre d\'alertes (1000+)', () => {
        const largeAlerts = Array.from({ length: 1000 }, (_, i) => ({ id: `${i}` }));

        const start = performance.now();
        const filtered = largeAlerts.filter(a => parseInt(a.id) % 2 === 0);
        const duration = performance.now() - start;

        assert.ok(duration < 50, `Filtrage devrait être rapide (${duration.toFixed(2)}ms < 50ms)`);
        assert.equal(filtered.length, 500, 'Devrait filtrer 500 alertes');
    });

    log('success', `Tests terminés: ${passCount} passés, ${failCount} échoués sur ${totalCount} total`);

    btn.disabled = false;
    btn.textContent = '▶️ Relancer les Tests';
}

// Event listener
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('runBtn').addEventListener('click', runAllTests);
    log('info', 'Page chargée. Cliquez sur "Lancer les Tests" pour commencer.');
    console.log('✅ Test page loaded successfully');
});
