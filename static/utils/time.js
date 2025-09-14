/**
 * Time utilities with Europe/Zurich timezone formatting
 * Used by Badges.js and other components requiring consistent timezone display
 */

/**
 * Format timestamp for Europe/Zurich timezone
 * @param {string|Date|number} ts - Timestamp (ISO string, Date object, or number)
 * @returns {string} - Formatted time as "HH:MM:SS" in Europe/Zurich timezone
 */
export function formatZurich(ts) {
  if (!ts) return '--:--:--';

  try {
    const date = new Date(ts);

    // Validate the date
    if (isNaN(date.getTime())) {
      return '--:--:--';
    }

    // Format in Europe/Zurich timezone
    return new Intl.DateTimeFormat('fr-CH', {
      timeZone: 'Europe/Zurich',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(date);

  } catch (error) {
    console.warn('Error formatting Zurich time:', error);
    return '--:--:--';
  }
}

/**
 * Get current time in Europe/Zurich timezone
 * @returns {string} - Current time as "HH:MM:SS"
 */
export function getCurrentZurichTime() {
  return formatZurich(new Date());
}

/**
 * Check if timestamp is stale based on TTL
 * @param {string|Date|number} ts - Timestamp to check
 * @param {number} ttlMinutes - TTL in minutes (default: 30)
 * @returns {boolean} - True if timestamp is stale
 */
export function isStale(ts, ttlMinutes = 30) {
  if (!ts) return true;

  try {
    const timestamp = new Date(ts).getTime();
    const now = Date.now();
    const diffMinutes = (now - timestamp) / (1000 * 60);

    return diffMinutes > ttlMinutes;
  } catch (error) {
    return true; // Consider invalid timestamps as stale
  }
}

/**
 * Format full date and time for Europe/Zurich
 * @param {string|Date|number} ts - Timestamp
 * @returns {string} - Formatted as "DD.MM.YYYY HH:MM:SS"
 */
export function formatZurichFull(ts) {
  if (!ts) return '--.--.---- --:--:--';

  try {
    const date = new Date(ts);

    if (isNaN(date.getTime())) {
      return '--.--.---- --:--:--';
    }

    return new Intl.DateTimeFormat('de-CH', {
      timeZone: 'Europe/Zurich',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(date);

  } catch (error) {
    console.warn('Error formatting full Zurich time:', error);
    return '--.--.---- --:--:--';
  }
}

/**
 * Get timezone offset for Europe/Zurich at a given time
 * @param {string|Date|number} ts - Timestamp (optional, defaults to now)
 * @returns {string} - Offset string like "CET" or "CEST"
 */
export function getZurichOffset(ts = new Date()) {
  try {
    const date = new Date(ts);

    // Use Intl.DateTimeFormat to get timezone name
    const formatter = new Intl.DateTimeFormat('en', {
      timeZone: 'Europe/Zurich',
      timeZoneName: 'short'
    });

    const parts = formatter.formatToParts(date);
    const tzPart = parts.find(part => part.type === 'timeZoneName');

    return tzPart ? tzPart.value : 'CET';
  } catch (error) {
    return 'CET'; // Fallback
  }
}

/**
 * Test function for manual timezone verification
 * Logs current time in different formats for debugging
 */
export function testZurichTime() {
  const now = new Date();

  console.log('=== Zurich Time Test ===');
  console.log('UTC:', now.toISOString());
  console.log('Zurich (HH:MM:SS):', formatZurich(now));
  console.log('Zurich (full):', formatZurichFull(now));
  console.log('Zurich offset:', getZurichOffset(now));
  console.log('Is stale (30min):', isStale(new Date(now.getTime() - 31 * 60 * 1000)));
  console.log('========================');
}

// Make test available globally for debugging
if (typeof window !== 'undefined') {
  window.testZurichTime = testZurichTime;
}