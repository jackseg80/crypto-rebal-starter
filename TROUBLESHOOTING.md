# 🔧 Guide de Troubleshooting - Crypto Rebalancer

Ce guide vous aide à diagnostiquer et résoudre les problèmes courants avec l'application Crypto Rebalancer.

---

## 🔥 **CORRECTION RÉCENTE** - Balances vides (27 Août 2025)

### ❌ **Problème résolu** : "📊 Balances: ❌ Vide" dans Settings

**Symptômes identifiés :**
- Settings.html affichait "📊 Balances: ❌ Vide"
- Analytics retournaient des erreurs à cause des balances vides  
- API `/balances/current` retournait 0 items au lieu de 945 assets

**✅ **Solution appliquée** :**
1. **Correction API backend** (`api/main.py:370`) :
   ```python
   # AVANT (bug)
   for r in raw or []:  # raw est un dict, pas une liste !
   
   # APRÈS (corrigé)
   for r in raw.get("items", []):  # Accès correct aux items
   ```

2. **CSV detection améliorée** (`connectors/cointracking.py`) :
   - Support des fichiers datés : `CoinTracking - Balance by Exchange - 26.08.2025.csv`
   - Recherche dans `data/raw/` avec patterns dynamiques
   - Tri par date de modification (plus récent en premier)

3. **Frontend unifié** (`global-config.js`) :
   ```javascript
   // AVANT - accès direct aux fichiers (échec)
   csvResponse = await fetch('/data/raw/CoinTracking - Current Balance.csv');
   
   // APRÈS - via API backend (succès)
   csvResponse = await fetch(`${apiBaseUrl}/balances/current?source=cointracking`);
   ```

**🧪 Test de validation :**
```bash
# Tester l'API directement
curl -s "http://localhost:8080/balances/current?source=cointracking&min_usd=100"
# Doit retourner : {"items": [...], "source_used": "cointracking"} avec 116+ items

# Tester dans la console navigateur
window.loadBalanceData().then(console.log)
# Doit retourner : {success: true, data: {...}}
```

---

## 🚨 Problèmes critiques

### 1. "Impossible de charger les données du portfolio"

**Symptômes :**
- Dashboard vide ou erreur de chargement
- Message "Fichier CSV du portfolio non accessible"
- APIs retournent des erreurs 404/500

**Solutions :**

1. **Vérifier les fichiers CSV** :
```bash
# Vérifier la présence des fichiers CSV
ls -la data/raw/
# Doit contenir : CoinTracking - Current Balance.csv
```

2. **Tester la connectivité API** :
```bash
curl http://127.0.0.1:8000/healthz
# Doit retourner {"status": "ok"}
```

3. **Vérifier uvicorn** :
```bash
uvicorn api.main:app --reload --port 8000
# Le serveur doit démarrer sans erreur
```

**Configuration debug** :
```javascript
// Dans la console du navigateur
toggleDebug()  // Active les logs détaillés
```

---

### 2. "Clés API CoinTracking invalides"

**Symptômes :**
- Erreur "API Error: 401" ou "403 Forbidden"
- Source données bloquée sur "stub"
- Settings indiquent "API Key: Non configuré"

**Solutions :**

1. **Vérifier le fichier .env** :
```env
# Format correct (sans guillemets)
CT_API_KEY=votre_cle_api_ici
CT_API_SECRET=votre_secret_api_ici
```

2. **Tester les clés via API** :
```bash
curl "http://127.0.0.1:8000/debug/ctapi"
# Doit afficher le statut des clés
```

3. **Régénérer les clés CoinTracking** :
- Aller sur CoinTracking.info → Account → API
- Générer de nouvelles clés
- Mettre à jour le fichier `.env`

---

### 3. "Plan de rebalancement vide ou incorrect"

**Symptômes :**
- Aucune action générée
- Total des pourcentages ≠ 100%
- Message "Aucun asset trouvé"

**Solutions :**

1. **Vérifier les targets** :
```javascript
// Console navigateur - vérifier validation
validateTargets({
    BTC: 35, ETH: 25, Stablecoins: 10, 
    SOL: 10, "L1/L0 majors": 10, Others: 10
});
```

2. **Contrôler le seuil minimum** :
- Settings → Montant minimum USD → Réduire à 1.00
- Vérifier que vos assets dépassent ce seuil

3. **Vérifier les alias** :
- Alias Manager → Rechercher les "unknown_aliases"
- Classifier manuellement ou utiliser l'auto-classification

---

## 💡 Problèmes courants

### 4. Interface lente avec gros portfolio (500+ assets)

**Symptômes :**
- Dashboard met >5s à charger
- Navigation saccadée
- Navigateur ralentit

**Solutions automatiques** :
- **Optimisations activées automatiquement** pour >500 assets
- Pagination automatique, lazy loading, Web Workers

**Solutions manuelles** :
```javascript
// Console - voir les optimisations actives
performanceOptimizer.getStats()
// Augmenter le seuil de pagination si nécessaire
performanceOptimizer.thresholds.pagination_size = 50
```

---

### 5. "CORS policy" erreurs

**Symptômes :**
- Console montre "blocked by CORS policy"
- API calls échouent depuis GitHub Pages

**Solution** :
```env
# Dans .env - ajouter vos domaines
CORS_ORIGINS=https://votre-user.github.io,http://localhost:3000
```

---

### 6. Données non synchronisées entre dashboards

**Symptômes :**
- Totaux différents entre Dashboard et Risk Dashboard
- Nombre d'assets incohérent

**Solution** :
```javascript
// Forcer refresh de toutes les données
globalConfig.clearCache()
location.reload()
```

---

### 7. Mode debug bloqué ON/OFF

**Symptômes :**
- Trop de logs en production
- Ou pas assez d'informations pour debugger

**Solutions** :
```javascript
// Console navigateur
toggleDebug()                    // Switch mode
debugLogger.setDebugMode(true)   // Force ON
debugLogger.setDebugMode(false)  // Force OFF
localStorage.removeItem('crypto_debug_mode')  // Reset
```

---

## 🔍 Outils de diagnostic

### Console Debug Commands

```javascript
// === DIAGNOSTIC GÉNÉRAL ===
debugLogger.stats()              // Stats du logger
globalConfig.validate()          // Validation config
performanceOptimizer.getStats()  // Stats performance

// === TEST CONNECTIVITÉ ===
globalConfig.testConnection()    // Test API backend
loadBalanceData()               // Test chargement données

// === VALIDATION DONNÉES ===
validateTargets(targets)        // Valider targets rebalancement
validateConfig(globalConfig.getAll()) // Valider config

// === CACHE & PERFORMANCE ===
globalConfig.clearCache()       // Clear cache global
performanceOptimizer.clearCache() // Clear cache performance
```

### Endpoints de debug API

```bash
# Santé générale
GET http://127.0.0.1:8000/healthz

# État CoinTracking API
GET http://127.0.0.1:8000/debug/ctapi

# Test des balances
GET http://127.0.0.1:8000/balances/current?source=cointracking

# Clés API configurées
GET http://127.0.0.1:8000/debug/api-keys
```

---

## ⚙️ Variables d'environnement debug

### Mode développement

```env
# Activer debug serveur
DEBUG=true
DEBUG_TOKEN=dev-secret-2024

# Niveau logs détaillé
LOG_LEVEL=DEBUG
```

### Mode production

```env
# Désactiver debug
DEBUG=false

# Logs minimaux
LOG_LEVEL=ERROR
```

---

## 📊 Monitoring des erreurs

### Erreurs critiques à surveiller

1. **HTTP 5xx** : Problème serveur/API
2. **NetworkError** : Connectivité réseau
3. **ValidationError** : Données utilisateur invalides
4. **CacheError** : Problème stockage local

### Log patterns à rechercher

```bash
# Errors backend (uvicorn logs)
grep "ERROR" uvicorn.log
grep "Exception" uvicorn.log

# Errors frontend (console navigateur)
grep "❌" console.log
grep "⚠️" console.log
```

---

## 🎯 Checklist de résolution

### Avant de signaler un bug

- [ ] **Vérifier .env** : Clés API correctes et format valide
- [ ] **Tester API** : `curl http://127.0.0.1:8000/healthz`
- [ ] **Console debug** : Activer mode debug et reproduire
- [ ] **Cache** : Vider cache et localStorage
- [ ] **Version** : Vérifier dernière version du code
- [ ] **CSV** : Vérifier présence et format des fichiers

### Informations à fournir

1. **Version navigateur** et OS
2. **Taille du portfolio** (nombre d'assets)
3. **Source de données** utilisée (CSV/API/stub)
4. **Console logs** avec debug activé
5. **Fichier .env** (en masquant les clés)

---

## 🆘 Support avancé

### Réinitialisation complète

```javascript
// ⚠️ ATTENTION: Efface toute configuration
localStorage.clear()
sessionStorage.clear()
indexedDB.deleteDatabase('crypto-rebalancer')
globalConfig.reset()
```

### Export diagnostic complet

```javascript
const diagnostic = {
    config: globalConfig.getAll(),
    debug_stats: debugLogger.stats ? debugLogger.stats : 'N/A',
    performance_stats: performanceOptimizer.getStats(),
    cache_size: localStorage.length,
    user_agent: navigator.userAgent,
    timestamp: new Date().toISOString()
};

console.log('DIAGNOSTIC REPORT:', JSON.stringify(diagnostic, null, 2));
// Copier le résultat pour support
```

---

## 📝 Changelog des corrections

### Version Août 2025
- ✅ **Système de logging conditionnel** : Debug désactivable en production
- ✅ **Validation des inputs** : Prévention des erreurs utilisateur
- ✅ **Optimisations performance** : Support portfolios 1000+ assets
- ✅ **Gestion d'erreurs robuste** : Try/catch appropriés + UI feedback

### Améliorations en cours
- 🔧 **Retry automatique** : Nouvelle tentative sur échec réseau
- 🔧 **Cache intelligent** : TTL adaptatif selon usage
- 🔧 **Alertes proactives** : Détection problèmes avant l'utilisateur

---

**🎯 Cette documentation évolue avec le projet. Pour des problèmes non couverts, activer le mode debug et analyser les logs détaillés.**