# Dev to Production Checklist

> Checklist complète pour sécuriser et préparer le passage en production.

## Variables d'Environnement

### OBLIGATOIRE : Vérifier ces variables dans `.env`

```bash
# Environnement
DEBUG=false
ENVIRONMENT=production

# Debug & Testing Features (MUST BE DISABLED)
DEBUG_SIMULATION=false
ENABLE_ALERTS_TEST_ENDPOINTS=false

# Data source settings
ALLOW_STUB_SOURCES=false
COMPUTE_ON_STUB_SOURCES=false

# Rate limiting (MUST BE ENABLED)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO  # ou WARNING en prod
```

### Clés API (remplir avec vraies valeurs)

```bash
COINGECKO_API_KEY=your_real_key_here
FRED_API_KEY=your_real_key_here
CT_API_KEY=your_real_key_here
CT_API_SECRET=your_real_secret_here
```

### CORS (production strict)

```bash
# Remplacer localhost par vos vrais domaines
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

---

## Endpoints à Neutraliser/Protéger

### 1. Performance Endpoints (api/performance_endpoints.py)

**Status actuel** : Pas d'auth, accessible sans token

**Endpoints concernés** :
- `POST /api/performance/cache/clear` - Efface les caches
- `GET /api/performance/optimization/benchmark` - Calculs lourds
- `POST /api/performance/optimization/precompute` - Pré-calculs

**Action requise** :
- ✅ Vérifier que `@dev_only()` decorator est appliqué
- ✅ Tester accès en mode production → doit retourner 403

### 2. Realtime Endpoints (api/realtime_endpoints.py)

**Status actuel** : WebSocket accepte connexions anonymes

**Endpoints concernés** :
- `WS /api/realtime/ws` - WebSocket temps réel (pas d'auth obligatoire)
- `POST /api/realtime/dev/simulate` - Simulation events (protégé par DEBUG_SIMULATION)
- `GET /api/realtime/demo` - Page démo HTML

**Action requise** :
- ✅ Vérifier que `/dev/simulate` retourne 403 si `DEBUG_SIMULATION=false`
- ⚠️ WebSocket `/ws` : Ajouter auth token optionnelle via query param
- ✅ `/demo` : Désactiver en prod ou protéger par auth

### 3. Alerts Test Endpoints (api/alerts_endpoints.py)

**Status actuel** : Protégé par `ENABLE_ALERTS_TEST_ENDPOINTS`

**Endpoints concernés** :
- `/api/alerts/test/*` - Endpoints de test alerts

**Action requise** :
- ✅ Vérifier que `ENABLE_ALERTS_TEST_ENDPOINTS=false` dans `.env`
- ✅ Tester accès en mode production → doit retourner 404

---

## Tests de Sécurité à Lancer

### 1. Variables d'environnement

```bash
# Vérifier que DEBUG est désactivé
grep "DEBUG=false" .env

# Vérifier environment production
grep "ENVIRONMENT=production" .env

# Vérifier rate limiting activé
grep "RATE_LIMIT_ENABLED=true" .env
```

### 2. Endpoints protégés

```bash
# Activer .venv
.venv\Scripts\Activate.ps1

# Test 1: Endpoint /cache/clear doit être bloqué
curl -X POST http://localhost:8080/api/performance/cache/clear
# Attendu: 403 Forbidden en prod

# Test 2: Endpoint /dev/simulate doit être bloqué
curl -X POST "http://localhost:8080/api/realtime/dev/simulate?kind=risk_alert"
# Attendu: 403 Forbidden si DEBUG_SIMULATION=false

# Test 3: Rate limiting actif
for i in {1..100}; do curl -s http://localhost:8080/api/risk/dashboard > /dev/null; done
# Attendu: 429 Too Many Requests après ~60 requêtes
```

### 3. CORS strict

```bash
# Tester origin non autorisée
curl -H "Origin: https://evil.com" http://localhost:8080/api/risk/dashboard -v
# Attendu: Pas de header Access-Control-Allow-Origin dans la réponse
```

### 4. CSP Headers

```bash
# Vérifier headers de sécurité
curl -I http://localhost:8080/static/dashboard.html
# Attendu: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options
```

---

## Middleware & Sécurité

### Vérifications (api/main.py)

- ✅ `HTTPSRedirectMiddleware` activé (`if not DEBUG`)
- ✅ `TrustedHostMiddleware` strict (pas `allowed_hosts=["*"]`)
- ✅ `RateLimitMiddleware` activé (`if ENVIRONMENT == "production"`)
- ✅ `CORS allow_headers` pas `["*"]` (limiter aux headers nécessaires)
- ✅ CSP headers complets (via `add_security_headers` middleware)

### Headers de Sécurité Attendus

```
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; ...
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Configuration Settings (config/settings.py)

### Validation automatique

Le code dans `settings.py` bloque automatiquement :
- ❌ `DEBUG=true` en production → ValueError
- ✅ `environment` doit être dans `['development', 'staging', 'production']`

### CSP Configuration

Vérifier que les sources CSP sont strictes :

```python
# Production uniquement
csp_script_src: ["'self'", "https://cdn.jsdelivr.net"]  # Pas de 'unsafe-inline'
csp_style_src: ["'self'", "https://cdn.jsdelivr.net"]   # Limiter 'unsafe-inline'
csp_frame_ancestors: ["'self'"]  # Pas de domaines externes
```

---

## Logs & Monitoring

### 1. Niveau de logs

```bash
LOG_LEVEL=INFO  # ou WARNING pour réduire verbosité
```

### 2. Logs sensibles

Vérifier qu'aucun log ne contient :
- ❌ Clés API en clair
- ❌ Tokens/secrets
- ❌ Données utilisateur sensibles (emails, wallets)

### 3. Monitoring Production

Mettre en place :
- ✅ Alertes sur erreurs 500 (serveur)
- ✅ Alertes sur 429 (rate limit atteint trop souvent)
- ✅ Monitoring uptime endpoint `/health`
- ✅ Dashboard métriques Redis (si utilisé)

---

## Tests Automatisés

### Suite de tests à lancer avant prod

```bash
# Activer .venv
.venv\Scripts\Activate.ps1

# Tests unitaires
pytest tests/unit -v

# Tests intégration
pytest tests/integration -v

# Smoke tests endpoints
python tests/smoke_test_refactored_endpoints.py

# Tests sécurité headers
pytest tests/test_security_headers.py -v
```

---

## Checklist Finale

Avant de déployer en production :

- [ ] Variables `.env` vérifiées (DEBUG=false, ENVIRONMENT=production)
- [ ] Clés API remplies avec vraies valeurs
- [ ] `DEBUG_SIMULATION=false` et `ENABLE_ALERTS_TEST_ENDPOINTS=false`
- [ ] Rate limiting activé
- [ ] CORS configuré avec vrais domaines (pas localhost)
- [ ] Tests sécurité passés (endpoints protégés retournent 403)
- [ ] Tests automatisés verts (unit + integration + smoke)
- [ ] Headers de sécurité vérifiés (CSP, X-Frame-Options, etc.)
- [ ] Logs configurés (niveau INFO/WARNING, pas de secrets)
- [ ] Monitoring production configuré (alertes, uptime)
- [ ] Documentation mise à jour (README, API docs)
- [ ] Backup base de données/config effectué
- [ ] Plan de rollback défini en cas de problème

---

## Ressources

- [CLAUDE.md](../CLAUDE.md) - Guide complet pour agents
- [config/settings.py](../config/settings.py) - Configuration centralisée
- [api/main.py](../api/main.py) - Middleware et sécurité
- [tests/](../tests/) - Suite de tests

---

**Dernière mise à jour** : Oct 2025
**Mainteneur** : Crypto Rebal Team

