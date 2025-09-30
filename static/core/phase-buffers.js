/**
 * Phase Buffers - Ring buffer system for time series data
 * Stores timestamped samples for phase detection calculations
 */

// In-memory ring buffer storage with timestamps
const timeSeriesBuffers = new Map(); // key -> [{t, v}, ...]

/**
 * Push a new sample to the ring buffer
 * @param {string} key - Buffer identifier (e.g., 'btc_dom', 'eth_btc')
 * @param {number} value - Sample value
 * @param {number} maxSize - Maximum buffer size (default: 60 samples)
 * @returns {Array} Updated buffer array
 */
export function pushSample(key, value, maxSize = 60) {
  if (typeof value !== 'number' || !isFinite(value)) {
    debugLogger.warn(`⚠️ PhaseBuffers: Invalid value for ${key}:`, value);
    return getSeries(key, 1); // Return current buffer without pushing
  }

  const arr = timeSeriesBuffers.get(key) ?? [];
  let t = Date.now();

  // Ensure unique timestamps by incrementing if collision detected
  const lastSample = arr[arr.length - 1];
  if (lastSample && t <= lastSample.t) {
    t = lastSample.t + 1; // Increment to ensure uniqueness
    console.debug(`⏰ PhaseBuffers: Adjusted timestamp for ${key} to avoid collision`);
  }

  arr.push({ t, v: value });

  // Maintain max size
  if (arr.length > maxSize) {
    const removed = arr.shift();
    console.debug(`🗑️ PhaseBuffers: Trimmed old ${key} sample from ${new Date(removed.t).toLocaleTimeString()}`);
  }

  timeSeriesBuffers.set(key, arr);
  console.debug(`📈 PhaseBuffers: Pushed ${key} sample:`, { value, bufferSize: arr.length, timestamp: new Date(t).toLocaleTimeString() });

  return arr;
}

/**
 * Get time series values (last N samples)
 * @param {string} key - Buffer identifier
 * @param {number} lastN - Number of recent samples to return (default: 14)
 * @returns {Array<number>} Array of values only
 */
export function getSeries(key, lastN = 14) {
  const arr = timeSeriesBuffers.get(key) ?? [];
  const series = arr.slice(-lastN).map(({v}) => v);

  if (series.length === 0) {
    console.debug(`📊 PhaseBuffers: No data for ${key}`);
    return [];
  }

  console.debug(`📊 PhaseBuffers: Retrieved ${key} series:`, {
    length: series.length,
    range: series.length > 0 ? `${series[0].toFixed(3)} → ${series[series.length-1].toFixed(3)}` : 'empty',
    requested: lastN
  });

  return series;
}

/**
 * Get time series with timestamps (last N samples)
 * @param {string} key - Buffer identifier
 * @param {number} lastN - Number of recent samples to return
 * @returns {Array<{t: number, v: number}>} Array of timestamped samples
 */
export function getSeriesWithTimestamps(key, lastN = 14) {
  const arr = timeSeriesBuffers.get(key) ?? [];
  return arr.slice(-lastN);
}

/**
 * Calculate slope (rate of change) over the series
 * @param {Array<number>} series - Time series values
 * @returns {number} Slope as relative change (0.02 = 2% increase)
 */
export function calculateSlope(series) {
  if (!series || series.length < 2) {
    return 0;
  }

  const first = series[0];
  const last = series[series.length - 1];

  if (first === 0 || !isFinite(first) || !isFinite(last)) {
    return 0;
  }

  // Relative change: (last - first) / |first|
  const slope = (last - first) / Math.abs(first);

  console.debug(`📈 PhaseBuffers: Calculated slope:`, {
    first: first.toFixed(4),
    last: last.toFixed(4),
    slope: (slope * 100).toFixed(2) + '%',
    seriesLength: series.length
  });

  return slope;
}

/**
 * Get buffer status for debugging
 * @returns {Object} Status summary of all buffers
 */
export function getBufferStatus() {
  const status = {};

  for (const [key, buffer] of timeSeriesBuffers.entries()) {
    const values = buffer.map(({v}) => v);
    status[key] = {
      size: buffer.length,
      latest: buffer[buffer.length - 1]?.v,
      latestTime: buffer[buffer.length - 1]?.t ? new Date(buffer[buffer.length - 1].t).toLocaleTimeString() : null,
      min: Math.min(...values),
      max: Math.max(...values),
      slope: calculateSlope(values.slice(-14))
    };
  }

  return status;
}

/**
 * Clear all buffers (useful for dev/testing)
 */
export function clearAllBuffers() {
  const count = timeSeriesBuffers.size;
  timeSeriesBuffers.clear();
  debugLogger.debug(`🗑️ PhaseBuffers: Cleared ${count} buffers`);
}

/**
 * Clear specific buffer
 * @param {string} key - Buffer identifier to clear
 */
export function clearBuffer(key) {
  const existed = timeSeriesBuffers.delete(key);
  if (existed) {
    debugLogger.debug(`🗑️ PhaseBuffers: Cleared buffer '${key}'`);
  } else {
    debugLogger.warn(`⚠️ PhaseBuffers: Buffer '${key}' not found`);
  }
}

// Development helpers
if (typeof window !== 'undefined' && window.location?.hostname === 'localhost') {
  window.debugPhaseBuffers = {
    getStatus: getBufferStatus,
    clearAll: clearAllBuffers,
    clearBuffer,
    pushSample,
    getSeries,
    calculateSlope
  };

  console.debug('🔧 Debug: window.debugPhaseBuffers available for inspection');
}

// Auto-cleanup on page unload (prevent memory leaks)
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    console.debug('🔄 PhaseBuffers: Auto-cleanup on page unload');
    clearAllBuffers();
  });
}