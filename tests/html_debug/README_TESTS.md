# Tests HTML Debug - Risk Dashboard

## Fichiers Disponibles

### ✅ test_risk_modules_v2.html (RECOMMANDÉ)

**URL** : `http://localhost:8000/tests/html_debug/test_risk_modules_v2.html`

**Description** : Version CSP-compliant avec JavaScript externe (test_risk_modules.js).

**Contenu** :
- 13 tests unitaires JS
- Interface interactive
- Logs en temps réel
- Compatible avec Content Security Policy

**Fichiers** :
- `test_risk_modules_v2.html` : Interface HTML
- `test_risk_modules.js` : Logique de tests (externe, CSP-compliant)

**Comment utiliser** :
```bash
# 1. Démarrer le serveur
python -m uvicorn api.main:app --reload --port 8000

# 2. Ouvrir dans le navigateur
http://localhost:8000/tests/html_debug/test_risk_modules_v2.html

# 3. Cliquer sur "▶️ Lancer les Tests"
```

### ❌ Versions Dépréciées

**test_risk_modules_simple.html** : Bloqué par CSP (scripts inline interdits)
**test_risk_modules.html** : Problème avec modules ES6

---

## Tests Inclus

### 1. risk-alerts-tab.js (3 tests)

- ✅ Filtrer les alertes par severité
- ✅ Paginer les alertes correctement (25 → 3 pages)
- ✅ Calculer les stats (S1:2, S2:1, S3:1)

### 2. risk-overview-tab.js (3 tests)

- ✅ Valider Risk Score entre 0 et 100
- ✅ Détecter dual window disponible
- ✅ Calculer divergence Risk Score V2

### 3. risk-cycles-tab.js (3 tests)

- ✅ Formater données pour Chart.js
- ✅ Calculer composite score on-chain
- ✅ Gérer cache hash-based

### 4. risk-targets-tab.js (3 tests)

- ✅ Comparer allocation actuelle vs objectifs
- ✅ Générer plan d'action (buy/sell)
- ✅ Gérer 5 stratégies disponibles

### 5. Performance (1 test)

- ✅ Gérer 1000+ alertes en < 50ms

---

## Résultats Attendus

```
Pass:  13
Fail:  0
Total: 13
```

Tous les tests devraient passer instantanément (< 100ms total).

---

## Troubleshooting

### La page ne charge pas

```bash
# Vérifier que le serveur est démarré
curl http://localhost:8000/tests/html_debug/test_risk_modules_simple.html
# Devrait retourner 200
```

### Les tests ne se lancent pas

1. Ouvrir la console du navigateur (F12)
2. Vérifier qu'il n'y a pas d'erreurs JavaScript
3. Vérifier que le message "Page chargée" apparaît dans les logs

### Erreurs JavaScript

Si vous voyez des erreurs dans la console :
- Rafraîchir la page (Ctrl+F5)
- Vider le cache du navigateur
- Essayer un autre navigateur (Chrome recommandé)

---

## Alternative : Tests CLI

Si les tests HTML ne fonctionnent pas, utiliser les tests pytest :

```bash
# Activer .venv
.venv\Scripts\Activate.ps1

# Tests backend (28 tests)
pytest tests/integration/test_risk_dashboard_modules.py -v

# Tests performance (10 tests)
pytest tests/performance/test_risk_dashboard_performance.py -v -s
```

---

**Créé** : Octobre 2025
**Statut** : ✅ Opérationnel
