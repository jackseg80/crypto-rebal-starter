# Crypto Rebalancer - Security Guide

## Overview

Ce document décrit les mesures de sécurité implementées dans Crypto Rebalancer et les meilleures pratiques à suivre.

## 🔒 Mesures de sécurité implementées

### 1. Protection des credentials

- ❌ **Jamais committer** `.env` avec des vraies clés API
- ✅ Utiliser `.env.example` comme template sanitisé
- ✅ Pre-commit hooks avec `gitleaks` et `detect-secrets`
- ✅ `.gitignore` configuré pour bloquer `.env`

### 2. Headers de sécurité HTTP

Notre API expose automatiquement ces headers de sécurité :

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; ...
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

### 3. Code Quality & Logs

- ✅ ESLint configuré avec `no-console` et `no-eval`
- ✅ Migration automatique `console.log` → `debugLogger`
- ✅ Logs conditionnels (silencieux en production)
- ✅ Tests automatisés pour headers de sécurité

### 4. API Security

- ✅ Rate limiting configuré
- ✅ CORS restrictif (pas de `*` en production)
- ✅ Validation Pydantic sur tous les endpoints
- ✅ Gestion d'erreurs sans fuite d'informations

## 🛠 Outils de sécurité

### Scan automatique des secrets

```bash
# Installation
pip install detect-secrets pre-commit
pre-commit install

# Scan manuel
detect-secrets scan --baseline .secrets.baseline
gitleaks detect --verbose
```

### Audit de sécurité

```powershell
# Script d'audit complet
.\tools\security-audit.ps1
```

### Tests de sécurité

```bash
# Tests des headers HTTP
pytest tests/test_security_headers.py -v

# Smoke tests étendus
python tests/smoke_test_refactored_endpoints.py
```

## 🚀 Configuration de production

### Variables d'environnement critiques

```bash
# .env (NE JAMAIS COMMITTER)
DEBUG=false
COINGECKO_API_KEY=your_real_key_here
FRED_API_KEY=your_real_key_here
CT_API_KEY=your_real_key_here
CT_API_SECRET=your_real_secret_here
DEBUG_TOKEN=strong_random_token_for_debug_endpoints
```

### Headers CSP strictes

En production, s'assurer que la CSP ne contient pas `'unsafe-inline'` ou `'unsafe-eval'` sans nonce approprié.

### Rate limiting

```python
# config/settings.py
RATE_LIMIT_PER_MINUTE = 100  # Ajuster selon le trafic
```

## 🔍 Monitoring de sécurité

### Endpoints de santé sécurisés

- `GET /api/ml/status` - Statut ML (sans infos sensibles)
- `GET /api/risk/status` - Statut risk management
- `GET /api/alerts/active` - Alertes actives (authentifiées)

### Endpoints d'admin protégés

- `GET /api/ml/debug/*` - Nécessite `X-Admin-Key`
- `POST /api/execution/approve/*` - Nécessite authentification

## ⚠️ Pratiques à éviter

### ❌ Ne pas faire

```javascript
// MAUVAIS - Log sensible
console.log('API Key:', apiKey);

// MAUVAIS - Eval dynamique
eval(userInput);

// MAUVAIS - Headers permissifs
"Access-Control-Allow-Origin": "*"
```

### ✅ Faire plutôt

```javascript
// BON - Log conditionnel
debugLogger.info('API call successful');

// BON - Validation stricte
const validated = UserInputSchema.parse(input);

// BON - CORS restrictif
"Access-Control-Allow-Origin": "https://mondomaine.com"
```

## 📋 Checklist de sécurité

Avant chaque déploiement :

- [ ] `.env` non commité
- [ ] Clés API révoquées/régénérées si exposées
- [ ] Pre-commit hooks activés
- [ ] `.\tools\security-audit.ps1` passe
- [ ] Tests de sécurité verts
- [ ] CSP configurée sans `unsafe-*`
- [ ] Rate limiting activé
- [ ] Logs de debug désactivés en production

## 🚨 En cas d'incident

### Clés API compromises

1. **Immédiatement** révoquer les clés dans les services externes
2. Générer de nouvelles clés
3. Purger l'historique git si nécessaire :
   ```bash
   git filter-repo --invert-paths --path fichier_avec_secrets.py
   ```
4. Notifier l'équipe

### Vulnérabilité détectée

1. Évaluer la criticité
2. Appliquer un correctif temporaire si nécessaire
3. Développer et tester le correctif permanent
4. Déployer et vérifier

## 📚 Ressources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [CSP Generator](https://report-uri.com/home/generate)
- [Git Secrets Detection](https://github.com/awslabs/git-secrets)

---

**⚡ Règle d'or :** En cas de doute sur la sécurité, toujours choisir l'option la plus restrictive.