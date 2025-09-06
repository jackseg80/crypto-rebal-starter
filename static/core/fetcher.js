/**
 * Cache basique avec RAM + localStorage
 * Simple retry logic, pas de circuit breaker
 */

// RAM cache
const RAM_CACHE = new Map();

// TTL configurations per data type
const CACHE_CONFIG = {
  signals: { ram: 2 * 60 * 1000, disk: 10 * 60 * 1000 },      // 2min RAM, 10min disk
  risk: { ram: 5 * 60 * 1000, disk: 30 * 60 * 1000 },         // 5min RAM, 30min disk  
  portfolio: { ram: 1 * 60 * 1000, disk: 5 * 60 * 1000 },     // 1min RAM, 5min disk
  cycles: { ram: 10 * 60 * 1000, disk: 6 * 60 * 60 * 1000 }   // 10min RAM, 6h disk
};

/**
 * Fetch with unified cache (RAM + localStorage)
 */
export async function fetchCached(key, fetchFn, cacheType = 'signals') {
  const config = CACHE_CONFIG[cacheType];
  const now = Date.now();
  
  // Try RAM cache first
  const ramEntry = RAM_CACHE.get(key);
  if (ramEntry && (now - ramEntry.timestamp) < config.ram) {
    console.debug(`Cache hit (RAM): ${key}`);
    return ramEntry.data;
  }
  
  // Try localStorage cache
  try {
    const diskKey = `cache:${key}`;
    const diskEntry = localStorage.getItem(diskKey);
    if (diskEntry) {
      const parsed = JSON.parse(diskEntry);
      if ((now - parsed.timestamp) < config.disk) {
        console.debug(`Cache hit (disk): ${key}`);
        // Also store in RAM for faster access
        RAM_CACHE.set(key, { data: parsed.data, timestamp: now });
        return parsed.data;
      }
    }
  } catch (error) {
    console.warn(`Failed to read disk cache for ${key}:`, error);
  }
  
  // Cache miss - fetch fresh data
  console.debug(`Cache miss: ${key}, fetching...`);
  
  try {
    const data = await retryFetch(fetchFn);
    
    // Store in both caches
    const entry = { data, timestamp: now };
    RAM_CACHE.set(key, entry);
    
    try {
      localStorage.setItem(`cache:${key}`, JSON.stringify(entry));
    } catch (error) {
      console.warn(`Failed to write disk cache for ${key}:`, error);
    }
    
    return data;
    
  } catch (error) {
    console.error(`Failed to fetch ${key}:`, error);
    
    // Try to return stale data as fallback
    const staleEntry = RAM_CACHE.get(key) || 
      tryParseLocalStorage(`cache:${key}`);
    
    if (staleEntry?.data) {
      console.warn(`Returning stale data for ${key}`);
      return staleEntry.data;
    }
    
    throw error;
  }
}

/**
 * Simple retry logic
 */
async function retryFetch(fetchFn, maxRetries = 2, baseDelay = 500) {
  let lastError;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await withTimeout(fetchFn(), 8000);
    } catch (error) {
      lastError = error;
      
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt);
        console.debug(`Retry ${attempt + 1}/${maxRetries} after ${delay}ms`);
        await sleep(delay);
      }
    }
  }
  
  throw lastError;
}

/**
 * Add timeout to promise
 */
function withTimeout(promise, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error(`Timeout after ${timeoutMs}ms`));
    }, timeoutMs);
    
    promise
      .then(result => {
        clearTimeout(timeoutId);
        resolve(result);
      })
      .catch(error => {
        clearTimeout(timeoutId);
        reject(error);
      });
  });
}

/**
 * Sleep utility
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Safe localStorage parsing
 */
function tryParseLocalStorage(key) {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : null;
  } catch (error) {
    return null;
  }
}

/**
 * Clear all caches
 */
export function clearCache() {
  RAM_CACHE.clear();
  
  // Clear localStorage cache entries
  const keysToRemove = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('cache:')) {
      keysToRemove.push(key);
    }
  }
  keysToRemove.forEach(key => localStorage.removeItem(key));
  
  console.debug('All caches cleared');
}

/**
 * Get cache stats for debugging
 */
export function getCacheStats() {
  const ramSize = RAM_CACHE.size;
  let diskCount = 0;
  
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith('cache:')) {
      diskCount++;
    }
  }
  
  return { ramSize, diskCount };
}
