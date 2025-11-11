# Migration Linux - Résolution Finale (Nov 2025)

## ✅ Status : SUCCÈS

La migration de SmartFolio de Windows vers Linux Ubuntu 24.04.2 LTS (NUC 7i5BHN) est **terminée avec succès**.

## 🐛 Problème Rencontré

L'API CoinTracking retournait l'erreur :
```
RuntimeError: CT_API_KEY / CT_API_SECRET manquants (ou vides)
```

## 🔍 Diagnostic

Le problème avait **deux causes** :

### 1. Structure config.json (RÉSOLU)
**Problème :** Le fichier `data/users/jack/config.json` utilisait une structure imbriquée.

**Solution :** Utiliser la structure **plate** :
```json
{
  "cointracking_api_key": "9f878d12a6f1ce08f5f7fb7174d9c7d9",
  "cointracking_api_secret": "93ae0583c08f097e73cb6d4b6b0fe08f20c692ea3ab74f9b"
}
```

**PAS** la structure imbriquée :
```json
{
  "cointracking": {
    "api_key": "...",
    "api_secret": "..."
  }
}
```

### 2. Header X-User (RÉSOLU)
**Problème :** Les requêtes curl utilisaient `?user_id=jack` mais l'API utilise le header `X-User` pour l'authentification.

**Solution :** Utiliser le header correct :
```bash
curl -H "X-User: jack" "http://localhost:8000/balances/current?source=cointracking_api"
```

## 📝 Modifications Apportées

### Commits
- `c9b3925` - fix(api): pass API keys to load_ctapi_exchanges in legacy mode
- `44cc83f` - debug(api): add comprehensive logging for API key loading
- `587c08a` - fix(api): add RuntimeError catch and debug log in _try_api_mode
- `df94567` - debug(api): add detailed logging around CoinTracking API calls

### Fichiers Modifiés
1. **api/services/cointracking_helpers.py** - Ajout paramètres `api_key`/`api_secret` à `load_ctapi_exchanges()`
2. **services/balance_service.py** - Passage des clés API + catch RuntimeError + logs debug
3. **api/services/data_router.py** - Logs debug du chargement des credentials

## 🧪 Validation

### Test Réussi
```bash
curl -H "X-User: jack" "http://localhost:8000/balances/current?source=cointracking_api"
# ✅ Retourne 479 items avec succès
```

### Logs Confirmant le Succès
```
INFO services.balance_service: 🔑 DEBUG [_try_api_mode]: api_key='9f878d12a6...', len_key=32, len_secret=48
INFO services.balance_service: 🔄 DEBUG [_try_api_mode]: Calling CoinTracking API for user jack...
INFO services.balance_service: ✅ DEBUG [_try_api_mode]: CoinTracking API returned 479 items
INFO services.balance_service: ✅ API mode successful for user jack: 479 items
```

## 📋 Configuration NUC

### Système
- **OS :** Ubuntu 24.04.2 LTS
- **CPU :** Intel NUC 7i5BHN (i5-7260U)
- **RAM :** 16 GB
- **Python :** 3.11 (Docker)
- **Port :** 8000 (accessible sur LAN)

### Démarrage
```bash
cd ~/smartfolio
docker-compose up -d
```

### Logs
```bash
docker-compose logs -f
```

## 🎯 Points Clés à Retenir

1. **config.json doit avoir des clés PLATES** (underscore), pas imbriquées (dot notation)
2. **secrets.json n'est PAS utilisé** par le code actuel (fichier orphelin)
3. **Le header X-User est OBLIGATOIRE** pour l'authentification multi-utilisateur
4. **L'appel direct ?user_id=jack ne suffit PAS** - c'est le header qui compte

## 🔗 Références

- Architecture : `docs/ARCHITECTURE.md`
- Code CLAUDE.md : `CLAUDE.md` (règles multi-tenant)
- Historique complet : `prompt_claude.txt` (7251+ lignes)

---

**Date :** 11 novembre 2025
**Status :** ✅ Production Ready sur NUC
