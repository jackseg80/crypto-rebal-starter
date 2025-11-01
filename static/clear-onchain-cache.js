// Script temporaire pour vider le cache SWR des indicateurs on-chain
// À exécuter dans la console du navigateur sur la page risk-dashboard.html

console.log('🧹 Clearing on-chain indicators cache...');

// Clear SWR localStorage cache
localStorage.removeItem('CTB_ONCHAIN_CACHE_V2');
console.log('✅ Removed CTB_ONCHAIN_CACHE_V2');

// Clear any other related caches
const keysToRemove = [];
for (let i = 0; i < localStorage.length; i++) {
  const key = localStorage.key(i);
  if (key.includes('onchain') || key.includes('crypto') || key.includes('CTB')) {
    keysToRemove.push(key);
  }
}

keysToRemove.forEach(key => {
  localStorage.removeItem(key);
  console.log(`✅ Removed ${key}`);
});

console.log('✅ Cache cleared! Reload the page (F5) to fetch fresh data.');
