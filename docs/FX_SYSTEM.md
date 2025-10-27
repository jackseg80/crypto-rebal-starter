# FX (Foreign Exchange) System

> **Unified currency conversion system with live rates and fallback**
> Last updated: Oct 2025

## 🎯 Overview

Système unifié de conversion de devises utilisé par l'ensemble de l'application (backend + frontend) garantissant la cohérence des conversions entre toutes les sources de données.

**Caractéristiques principales :**
- ✅ Taux de change en temps réel (API externe)
- ✅ Cache intelligent (4h TTL)
- ✅ Fallback robuste si API externe indisponible
- ✅ Source unique de vérité (backend)
- ✅ Support de 165+ devises mondiales
- ✅ Initialisation automatique au démarrage

### ✅ Note : Système ML/Bourse Unifié

Le module `ForexConverter` ([MULTI_CURRENCY_IMPLEMENTATION.md](MULTI_CURRENCY_IMPLEMENTATION.md)) utilisé par les recommandations ML/Bourse **utilise maintenant fx_service en backend**.

**Status actuel :**
- ✅ `fx_service` (ce document) : Système central utilisé partout
- ✅ `ForexConverter` : Wrapper async vers fx_service (compatibilité)

**Résultat :** **Source unique de taux** pour toute l'application = cohérence garantie.

---

## 📁 Architecture

### Backend

```
services/fx_service.py          # Service central de conversion FX
api/fx_endpoints.py             # Endpoints REST pour accès aux taux
api/startup.py                  # Initialisation au démarrage
```

### Frontend

```
static/global-config.js         # currencyManager (consomme API backend)
static/saxo-dashboard.html      # Modal Edit Cash avec conversion temps réel
```

### Connecteurs

```
connectors/saxo_import.py       # Parser CSV Saxo (conversion EUR→USD)
adapters/banks_adapter.py       # Comptes bancaires multi-devises
adapters/saxo_adapter.py        # Positions Saxo
```

---

## 🔧 Service Backend

### services/fx_service.py

**Fonctions publiques :**

| Fonction | Description | Usage |
|----------|-------------|-------|
| `convert(amount, from_ccy, to_ccy)` | Convertit un montant entre deux devises | `convert(1000, "EUR", "USD")` |
| `get_rates(base_currency="USD")` | Retourne tous les taux pour une devise de base | `get_rates("USD")` |
| `get_supported_currencies()` | Liste des devises supportées | `get_supported_currencies()` |
| `initialize_rates()` | Initialise les taux au démarrage | Appelé par startup |
| `get_cache_info()` | Métadonnées du cache | Debug/monitoring |

**Flux de fonctionnement :**

```
1. Démarrage → initialize_rates() fetch taux externes (5 sec)
2. Cache valide 4h
3. Après 4h → _ensure_rates_fresh() refresh auto à la prochaine requête
4. Si API externe échoue → Utilise FALLBACK_RATES (Oct 2025)
```

**Source externe :**
- API : `https://open.exchangerate-api.com/v6/latest/USD`
- Gratuit : 1500 requêtes/mois (largement suffisant avec cache 4h)
- Timeout : 5 secondes
- Fallback automatique si erreur

**Taux de fallback (Oct 2025) :**
```python
_FALLBACK_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.087,   # 1 EUR = 1.087 USD
    "CHF": 1.136,   # 1 CHF = 1.136 USD
    "GBP": 1.30,
    # ... + 7 autres devises
}
```

---

## 🌐 API Endpoints

### GET /api/fx/rates?base=USD

Retourne tous les taux de change pour une devise de base.

**Request :**
```bash
curl "http://localhost:8000/api/fx/rates?base=USD"
```

**Response :**
```json
{
  "ok": true,
  "data": {
    "base": "USD",
    "rates": {
      "USD": 1.0,
      "EUR": 0.8599,
      "CHF": 0.7960,
      "GBP": 0.7508,
      "JPY": 153.0001,
      ...
    }
  },
  "meta": {
    "currencies": 165,
    "updated": "2025-10-27"
  }
}
```

**Note :** Les taux sont inversés pour le frontend.
Backend stocke `1 EUR = 1.087 USD`, API retourne `1 USD = 0.8599 EUR`.

### GET /api/fx/currencies

Liste des devises supportées.

**Response :**
```json
{
  "ok": true,
  "data": ["USD", "EUR", "CHF", "GBP", "JPY", ...],
  "meta": {
    "count": 165
  }
}
```

### GET /api/fx/cache-info

Informations sur le cache (monitoring).

**Response :**
```json
{
  "ok": true,
  "data": {
    "cached_currencies": 165,
    "cache_age_seconds": 245.2,
    "cache_ttl_seconds": 14400,
    "cache_fresh": true,
    "last_update": "2025-10-27T14:32:10"
  }
}
```

---

## 💻 Frontend (currencyManager)

### static/global-config.js

**Usage :**

```javascript
// Assurer qu'un taux est disponible
await window.currencyManager.ensureRate('EUR');

// Récupérer un taux synchrone (depuis cache)
const rate = window.currencyManager.getRateSync('EUR');
// rate = 0.8599 (1 USD = 0.8599 EUR)

// Conversion manuelle
const usdAmount = eurAmount / rate;
```

**Fonctionnement :**
- Fetch automatique depuis `/api/fx/rates` au chargement de la page
- Cache 1h côté frontend
- Fallback local si backend indisponible
- Events `currencyRateUpdated` pour réactivité

**Fallback frontend (synchronisé avec backend) :**
```javascript
const FALLBACK_RATES = {
  USD: 1.0,
  EUR: 0.920,  // Inversé depuis backend (1/1.087)
  CHF: 0.880,  // Inversé depuis backend (1/1.136)
  ...
}
```

---

## 🏦 Cas d'usage : CSV Saxo

### Problème résolu

Le CSV Saxo Bank a une structure trompeuse :

| Instrument | Market Value | Currency |
|------------|--------------|----------|
| Tesla Inc. | 11 720,15    | USD      |
| NVIDIA Corp. | 8 186,68   | USD      |

**Piège :**
- `Market Value` est en **EUR** (devise du compte)
- `Currency` indique la **devise de cotation** de l'instrument (USD)

### Solution (connectors/saxo_import.py:247-288)

```python
# Distinction claire
account_base_currency = "EUR"      # Devise du Market Value
instrument_currency = "USD"        # Devise de cotation

# Conversion correcte
market_value_usd = convert(11720.15, "EUR", "USD")
# 11720.15 EUR × 1.163 = 13,630 USD ✅
```

**Avant la correction :**
```python
# ❌ Confusion entre devise compte et devise instrument
currency = "USD"
market_value_usd = convert(11720.15, "USD", "USD")
# Pas de conversion ! → $11,720.15 (FAUX)
```

**Impact :**
- Tesla : $11,720 → $13,630 (+16.3%)
- NVIDIA : $8,187 → $9,521 (+16.3%)

---

## 🎨 Interface Utilisateur

### Modal Edit Cash (saxo-dashboard.html)

**Features :**
- Sélecteur de devise : EUR / USD / CHF
- Conversion temps réel affichée
- Sauvegarde de la préférence (localStorage)
- Enregistrement en USD pour cohérence

**Exemple :**
```
Devise : EUR
Montant : 5000
💱 Équivalent USD : $5,815.00 USD (taux: 0.8599)
```

**Code (lignes 3473-3664) :**
- `editCashAmount()` : Affiche modal avec conversion live
- `saveCashAmount()` : Convertit et enregistre en USD
- `updateConversion()` : Rafraîchit affichage en temps réel

---

## 🔄 Cycle de mise à jour

```
Démarrage serveur
    ↓
initialize_rates() → Fetch API externe (5 sec)
    ↓
Cache backend valide 4h
    ↓
Frontend fetch /api/fx/rates (cache 1h)
    ↓
Après 4h backend → Auto-refresh à la prochaine requête
    ↓
Si API externe échoue → Fallback rates (Oct 2025)
```

**Fréquence d'appels API externe :**
- ~6 appels/jour (cache 4h)
- Bien en dessous de la limite gratuite (1500/mois)

---

## 📊 Cohérence garantie

Toutes les conversions utilisent maintenant la même source :

| Composant | Taux utilisés | Source |
|-----------|---------------|--------|
| Modal Edit Cash | Taux du jour | `fx_service` ✅ |
| Positions CSV Saxo | Taux du jour | `fx_service` ✅ |
| Portfolio Summary | Taux du jour | `fx_service` ✅ |
| Banks adapter | Taux du jour | `fx_service` ✅ |
| Wealth endpoints | Taux du jour | `fx_service` ✅ |

**Avant (système fragmenté) :**
- Backend : Taux fixes (EUR: 1.07, CHF: 1.10)
- Frontend : API externe (EUR: 0.92, CHF: 0.88)
- ❌ Incohérence jusqu'à 5-10%

**Après (système unifié) :**
- Backend : Source unique avec live rates
- Frontend : Consomme backend
- ✅ Cohérence parfaite

---

## 🧪 Tests

### Test backend
```bash
# Vérifier les taux
curl http://localhost:8000/api/fx/rates | jq '.data.rates.EUR'

# Info cache
curl http://localhost:8000/api/fx/cache-info

# Logs serveur
# Devrait afficher :
# [wealth][fx] ✅ Fetched 165 live rates from API
# [wealth][fx] ✅ FX rates initialized with live data
```

### Test frontend
```javascript
// Console browser
await window.currencyManager.ensureRate('EUR');
console.log(window.currencyManager.getRateSync('EUR'));
// → 0.8599 (taux du jour)
```

### Test conversion Saxo
```bash
# Logs après import CSV
# Devrait afficher :
# [saxo_import] Tesla Inc.: 11720.15 EUR → 13630.00 USD (instrument quoted in USD)
# [saxo_import] NVIDIA Corp.: 8186.68 EUR → 9521.00 USD (instrument quoted in USD)
```

---

## 🛠️ Maintenance

### Mise à jour des taux de fallback

Si l'API externe est durablement inaccessible, mettre à jour les fallbacks :

**Backend (services/fx_service.py:13-24) :**
```python
_FALLBACK_RATES_TO_USD = {
    "EUR": 1.087,  # Mettre à jour ici
    "CHF": 1.136,
}
```

**Frontend (static/global-config.js:826-838) :**
```javascript
const FALLBACK_RATES = {
  EUR: 0.920,  // Inversé : 1/1.087
  CHF: 0.880,  // Inversé : 1/1.136
}
```

**⚠️ Important :** Garder la cohérence entre backend et frontend !

### Monitoring

Surveiller les logs :
```bash
# Succès
[wealth][fx] ✅ Fetched 165 live rates from API

# Fallback utilisé
[wealth][fx] ⚠️ FX rates initialized with fallback data
[wealth][fx] Failed to fetch live rates: ...
```

### Changement d'API

Pour changer de provider FX (services/fx_service.py:47) :

```python
# Option 1: exchangerate-api.com (actuel, gratuit 1500/mois)
url = "https://open.exchangerate-api.com/v6/latest/USD"

# Option 2: fixer.io (nécessite API key)
url = f"https://api.fixer.io/latest?access_key={API_KEY}&base=USD"

# Option 3: exchangerate.host (gratuit illimité mais CORS)
url = "https://api.exchangerate.host/latest?base=USD"
```

---

## 📝 Logs utiles

**Démarrage serveur :**
```
[wealth][fx] Initializing FX rates on startup...
[wealth][fx] ✅ Fetched 165 live rates from API
[wealth][fx] ✅ FX rates initialized with live data
```

**Conversion automatique :**
```
[wealth][fx] convert 1000.00 EUR -> 1163.00 USD (asof=latest)
```

**Refresh cache (après 4h) :**
```
[wealth][fx] Cache expired (age: 14401s), fetching live rates...
[wealth][fx] ✅ Fetched 165 live rates from API
```

**Erreur API (fallback) :**
```
[wealth][fx] Failed to fetch live rates: HTTP 429, using fallback rates
```

---

## 🎯 Best Practices

1. **Toujours utiliser `fx_service.convert()`** au lieu de taux hardcodés
2. **Ne jamais stocker de taux** dans la config/base de données
3. **Vérifier les logs** au démarrage pour confirmer le fetch des taux
4. **Mettre à jour les fallbacks** une fois par trimestre si nécessaire
5. **Tester la conversion** après chaque import CSV Saxo

---

## 🔀 ForexConverter: Wrapper de Compatibilité

`ForexConverter` ([MULTI_CURRENCY_IMPLEMENTATION.md](MULTI_CURRENCY_IMPLEMENTATION.md)) est maintenant un **wrapper léger** vers `fx_service`.

| Aspect | fx_service | ForexConverter |
|--------|------------|----------------|
| **Rôle** | Système central | Wrapper async |
| **Fichier** | `services/fx_service.py` | `services/ml/bourse/forex_converter.py` |
| **API externe** | exchangerate-api.com | Aucune (délégué) |
| **Cache** | 4h | Délégué à fx_service |
| **Devises** | 165+ | 165+ (via fx_service) |
| **Interface** | Synchrone | Async (compatibilité) |

### Quand utiliser quoi ?

**fx_service (recommandé) :**
```python
from services.fx_service import convert
usd_amount = convert(100, 'CHF', 'USD')  # Synchrone, simple
```

**ForexConverter (legacy) :**
```python
from services.ml.bourse.forex_converter import ForexConverter
converter = ForexConverter()
usd_amount = await converter.convert(100, 'CHF', 'USD')  # Async, pour compatibilité
```

**Résultat identique**, `ForexConverter` appelle `fx_service` en interne.

---

## 🔗 Références

- API externe : https://www.exchangerate-api.com/
- Backend service : [services/fx_service.py](../services/fx_service.py)
- API endpoints : [api/fx_endpoints.py](../api/fx_endpoints.py)
- Frontend manager : [static/global-config.js:823-946](../static/global-config.js#L823-L946)
- Saxo parser : [connectors/saxo_import.py:356-391](../connectors/saxo_import.py#L356-L391)
- ML/Bourse system : [MULTI_CURRENCY_IMPLEMENTATION.md](MULTI_CURRENCY_IMPLEMENTATION.md)

---

*Système FX unifié - Garantit la cohérence des conversions de devises à travers toute l'application.*
