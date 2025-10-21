/**
 * Memory Leak Diagnostic Tool
 *
 * Usage:
 * 1. Open dashboard.html
 * 2. Open DevTools Console
 * 3. Copy-paste this entire file
 * 4. Run: startMemoryDiagnostic()
 * 5. Refresh page 5 times (F5 x 5)
 * 6. Wait 10 seconds
 * 7. Run: stopMemoryDiagnostic()
 */

let diagnosticData = {
    snapshots: [],
    intervals: [],
    listeners: [],
    charts: [],
    startTime: null
};

function startMemoryDiagnostic() {
    console.log('%c🔍 MEMORY DIAGNOSTIC STARTED', 'color: cyan; font-size: 16px; font-weight: bold');

    diagnosticData.startTime = Date.now();
    diagnosticData.snapshots = [];

    // Take initial snapshot
    takeSnapshot('Initial');

    // Monitor every 2 seconds
    const monitorInterval = setInterval(() => {
        takeSnapshot('Monitor');
    }, 2000);

    diagnosticData.monitorInterval = monitorInterval;

    console.log('%c📊 Monitoring every 2 seconds. Refresh the page 5 times, then run stopMemoryDiagnostic()', 'color: yellow');
}

function takeSnapshot(label) {
    if (!performance.memory) {
        console.warn('performance.memory not available. Use Chrome with --enable-precise-memory-info flag');
        return;
    }

    const snapshot = {
        timestamp: Date.now() - diagnosticData.startTime,
        label,
        usedJSHeapSize: performance.memory.usedJSHeapSize,
        totalJSHeapSize: performance.memory.totalJSHeapSize,
        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit,

        // Count active resources
        intervals: countIntervals(),
        listeners: countEventListeners(),
        charts: countCharts(),
        domNodes: document.getElementsByTagName('*').length,

        // Memory in MB
        usedMB: (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2),
        totalMB: (performance.memory.totalJSHeapSize / 1024 / 1024).toFixed(2)
    };

    diagnosticData.snapshots.push(snapshot);

    console.log(`📸 Snapshot: ${snapshot.usedMB} MB used | Intervals: ${snapshot.intervals} | Listeners: ~${snapshot.listeners} | DOM: ${snapshot.domNodes} nodes`);
}

function countIntervals() {
    // Estimate active intervals by checking high interval IDs
    // This is a heuristic, not exact
    let maxId = 0;
    try {
        // Try to get highest interval ID
        const testInterval = setInterval(() => {}, 999999);
        maxId = testInterval;
        clearInterval(testInterval);
    } catch (e) {}

    return maxId;
}

function countEventListeners() {
    // Count known event targets
    let count = 0;

    // Window listeners (estimate)
    const windowEvents = ['storage', 'dataSourceChanged', 'bourseSourceChanged', 'configChanged', 'currencyRateUpdated', 'beforeunload'];
    windowEvents.forEach(event => {
        try {
            // Chrome DevTools trick
            if (getEventListeners && getEventListeners(window)[event]) {
                count += getEventListeners(window)[event].length;
            }
        } catch (e) {}
    });

    // Document listeners
    const docEvents = ['DOMContentLoaded', 'click', 'keydown'];
    docEvents.forEach(event => {
        try {
            if (getEventListeners && getEventListeners(document)[event]) {
                count += getEventListeners(document)[event].length;
            }
        } catch (e) {}
    });

    return count || 'unknown';
}

function countCharts() {
    let count = 0;
    if (window.portfolioChart) count++;
    if (window.Chart && window.Chart.instances) {
        count += Object.keys(window.Chart.instances).length;
    }
    return count;
}

function stopMemoryDiagnostic() {
    clearInterval(diagnosticData.monitorInterval);

    console.log('%c🛑 MEMORY DIAGNOSTIC STOPPED', 'color: red; font-size: 16px; font-weight: bold');
    console.log('');

    // Analyze snapshots
    analyzeSnapshots();

    console.log('%c📋 Full diagnostic data available in: window.diagnosticData', 'color: cyan');
    window.diagnosticData = diagnosticData;
}

function analyzeSnapshots() {
    const snapshots = diagnosticData.snapshots;

    if (snapshots.length < 2) {
        console.warn('Not enough snapshots to analyze');
        return;
    }

    const first = snapshots[0];
    const last = snapshots[snapshots.length - 1];

    const memoryGrowth = parseFloat(last.usedMB) - parseFloat(first.usedMB);
    const timeElapsed = (last.timestamp - first.timestamp) / 1000;
    const growthRate = (memoryGrowth / timeElapsed).toFixed(2);

    console.log('%c📊 ANALYSIS RESULTS:', 'color: green; font-size: 14px; font-weight: bold');
    console.log('');
    console.log(`⏱️  Time elapsed: ${timeElapsed.toFixed(1)}s`);
    console.log(`📈 Memory growth: ${memoryGrowth.toFixed(2)} MB`);
    console.log(`📉 Growth rate: ${growthRate} MB/s`);
    console.log('');
    console.log(`🔢 Initial memory: ${first.usedMB} MB`);
    console.log(`🔢 Final memory: ${last.usedMB} MB`);
    console.log('');
    console.log(`🔄 Intervals: ${first.intervals} → ${last.intervals} (Δ ${last.intervals - first.intervals})`);
    console.log(`👂 Event listeners: ${first.listeners} → ${last.listeners}`);
    console.log(`📊 Charts: ${first.charts} → ${last.charts}`);
    console.log(`🌳 DOM nodes: ${first.domNodes} → ${last.domNodes} (Δ ${last.domNodes - first.domNodes})`);
    console.log('');

    // Verdict
    if (memoryGrowth > 100) {
        console.log('%c❌ CRITICAL LEAK DETECTED!', 'color: red; font-size: 14px; font-weight: bold');
        console.log(`Memory grew by ${memoryGrowth.toFixed(2)} MB in ${timeElapsed.toFixed(1)}s`);
        console.log('');

        // Identify likely culprits
        const intervalGrowth = last.intervals - first.intervals;
        const domGrowth = last.domNodes - first.domNodes;

        if (intervalGrowth > 10) {
            console.log(`⚠️  SUSPECT: Intervals grew by ${intervalGrowth} - likely setInterval() not cleared`);
        }
        if (domGrowth > 1000) {
            console.log(`⚠️  SUSPECT: DOM nodes grew by ${domGrowth} - likely DOM elements not removed`);
        }
        if (last.charts > 1) {
            console.log(`⚠️  SUSPECT: Multiple charts (${last.charts}) - charts may not be destroyed`);
        }

    } else if (memoryGrowth > 50) {
        console.log('%c⚠️  MODERATE LEAK DETECTED', 'color: orange; font-size: 14px; font-weight: bold');
        console.log(`Memory grew by ${memoryGrowth.toFixed(2)} MB - acceptable but could be improved`);
    } else {
        console.log('%c✅ NO SIGNIFICANT LEAK DETECTED', 'color: green; font-size: 14px; font-weight: bold');
        console.log(`Memory growth (${memoryGrowth.toFixed(2)} MB) is within acceptable range`);
    }

    console.log('');
    console.log('%c💡 TIP: Run window.gc() if available to force garbage collection', 'color: blue');
}

// Force garbage collection if available (Chrome with --js-flags=--expose-gc)
function forceGC() {
    if (window.gc) {
        console.log('🗑️  Running garbage collection...');
        window.gc();
        setTimeout(() => {
            takeSnapshot('After GC');
        }, 1000);
    } else {
        console.warn('⚠️  window.gc() not available. Start Chrome with: --js-flags="--expose-gc"');
    }
}

console.log('%c🔍 Memory Leak Diagnostic Tool Loaded', 'color: green; font-size: 14px; font-weight: bold');
console.log('%cRun: startMemoryDiagnostic()', 'color: cyan; font-weight: bold');
console.log('Then refresh 5 times, wait 10s, and run: stopMemoryDiagnostic()');
