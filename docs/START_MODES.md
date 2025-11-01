# Start Modes - Guide de Démarrage

**Dernière mise à jour:** Oct 2025

Ce document explique les différents modes de démarrage de l'application via `start_dev.ps1` (Windows) ou `start_dev.sh` (Linux/macOS).

---

## 🎯 Modes Disponibles

### Mode 1: Dev Standard (Défaut)

**Commande:**
```powershell
.\start_dev.ps1
```

**Configuration:**
- ✅ **FastAPI** + Playwright (crypto-toolbox natif)
- ✅ **ML Models** (lazy loading)
- ✅ **Governance Engine**
- ✅ **Alert Engine**
- ❌ **Task Scheduler** (désactivé)
- ❌ **Hot Reload** (désactivé pour Playwright sur Windows)

**Quand utiliser:**
- Développement quotidien
- Test des pages frontend
- Debug des endpoints API

**Tâches manuelles:**
```powershell
# P&L snapshots
.venv\Scripts\python.exe scripts\pnl_snapshot.py

# OHLCV updates
.venv\Scripts\python.exe scripts\update_price_history.py
```

---

### Mode 2: Dev avec Scheduler

**Commande:**
```powershell
.\start_dev.ps1 -EnableScheduler
```

**Configuration:**
- ✅ **FastAPI** + Playwright
- ✅ **ML Models**
- ✅ **Governance Engine**
- ✅ **Alert Engine**
- ✅ **Task Scheduler** (activé)
  - P&L snapshots (intraday 15min, EOD 23:59)
  - OHLCV updates (daily 03:10, hourly :05)
  - Staleness monitor (hourly :15)
  - API warmers (every 10min)
- ❌ **Hot Reload** (désactivé pour éviter double exécution)

**Quand utiliser:**
- Test du système complet avec tâches automatiques
- Validation des snapshots P&L en conditions réelles
- Monitoring de la fraîcheur des données

**Tâches automatiques:**
- ✅ Tout se fait automatiquement selon les horaires
- Vérifier statut: `http://localhost:8080/api/scheduler/health`

---

### Mode 3: Flask Legacy avec Hot Reload

**Commande:**
```powershell
.\start_dev.ps1 -CryptoToolboxMode 0 -Reload
```

**Configuration:**
- ✅ **FastAPI** (proxy Flask pour crypto-toolbox)
- ✅ **ML Models**
- ✅ **Governance Engine**
- ✅ **Alert Engine**
- ❌ **Playwright** (utilise Flask externe)
- ❌ **Task Scheduler**
- ✅ **Hot Reload** (activé)

**Prérequis:**
- Serveur Flask lancé sur `http://localhost:8001`

**Quand utiliser:**
- Fallback si problème Playwright
- Test avec ancienne config
- Hot reload nécessaire pour itération rapide

---

### Mode 4: Production-like

**Commande:**
```powershell
.\start_dev.ps1 -EnableScheduler -Port 8080
```

**Configuration:**
- ✅ Tout activé (FastAPI, Playwright, Scheduler)
- ❌ Hot reload (mode production)

**Quand utiliser:**
- Test avant déploiement production
- Validation du comportement complet
- Benchmarks de performance

---

## 📊 Tableau Comparatif

| Feature | Dev Standard | + Scheduler | Flask Legacy | Production-like |
|---------|-------------|-------------|--------------|-----------------|
| FastAPI | ✅ | ✅ | ✅ | ✅ |
| Playwright | ✅ | ✅ | ❌ | ✅ |
| ML Models | ✅ | ✅ | ✅ | ✅ |
| Governance | ✅ | ✅ | ✅ | ✅ |
| Alerts | ✅ | ✅ | ✅ | ✅ |
| **Scheduler** | ❌ | ✅ | ❌ | ✅ |
| Hot Reload | ❌ | ❌ | ✅ | ❌ |
| **Tâches manuelles** | P&L, OHLCV | Aucune | P&L, OHLCV | Aucune |

---

## 🛠️ Paramètres du Script

### Windows (PowerShell)

```powershell
.\start_dev.ps1 [options]

Options:
  -CryptoToolboxMode <int>   # 0=Flask proxy, 1=Playwright (défaut: 1)
  -EnableScheduler           # Active le scheduler (switch, défaut: false)
  -Reload                    # Active hot reload (switch, défaut: false)
  -Port <int>                # Port du serveur (défaut: 8000)
  -Workers <int>             # Nombre de workers (défaut: 1)
```

### Linux/macOS (Bash)

```bash
./start_dev.sh [options]

Options:
  --crypto-toolbox-mode <int>  # 0=Flask proxy, 1=Playwright (défaut: 1)
  --enable-scheduler           # Active le scheduler (flag)
  --reload                     # Active hot reload (flag)
  --port <int>                 # Port du serveur (défaut: 8000)
  --workers <int>              # Nombre de workers (défaut: 1)
```

---

## 🔍 Vérifications

### Vérifier le mode actif

**Logs au démarrage:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 Starting Crypto Rebal Development Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 Crypto-Toolbox: FastAPI native (Playwright)
⏰ Task Scheduler: ENABLED
   • P&L snapshots (intraday 15min, EOD 23:59)
   • OHLCV updates (daily 03:10, hourly :05)
   • Staleness monitor (hourly :15)
   • API warmers (every 10min)
🔄 Hot Reload: DISABLED
   (auto-disabled: prevents double execution with scheduler)
```

### Endpoints de santé

```powershell
# Health général
curl http://localhost:8080/health

# Statut scheduler
curl http://localhost:8080/api/scheduler/health
```

**Réponse scheduler activé:**
```json
{
  "ok": true,
  "enabled": true,
  "jobs_count": 6,
  "jobs": {
    "pnl_intraday": {
      "last_run": "2025-10-02T14:30:00",
      "status": "success",
      "duration_ms": 245.3,
      "next_run": "2025-10-02T14:45:00+02:00",
      "name": "P&L Snapshot Intraday"
    }
  }
}
```

**Réponse scheduler désactivé:**
```json
{
  "ok": false,
  "enabled": false,
  "message": "Scheduler not running (RUN_SCHEDULER != 1)",
  "jobs": {}
}
```

---

## ⚠️ Limitations & Contraintes

### Hot Reload

**Incompatible avec:**
- ✅ Scheduler activé (double exécution des jobs)
- ✅ Playwright sur Windows (subprocess asyncio issue)

**Compatible avec:**
- ✅ Flask legacy mode (CryptoToolboxMode 0)

### Playwright

**Requis pour:**
- Crypto-Toolbox scraping natif
- Mode production

**Alternatives:**
- Flask legacy proxy (`-CryptoToolboxMode 0`)
- API CoinTracking directe

### Scheduler

**Incompatible avec:**
- Hot reload (risque de double exécution)

**Nécessite:**
- Mode normal (pas de `--reload`)

---

## 🚀 Cas d'Usage Recommandés

### Développement Frontend

```powershell
# Léger, rapide, pas de jobs en arrière-plan
.\start_dev.ps1
```

### Test Complet (Backend + Jobs)

```powershell
# Tout automatique comme en prod
.\start_dev.ps1 -EnableScheduler
```

### Debug avec Changements Fréquents

```powershell
# Hot reload + Flask legacy (si pas besoin de Playwright)
.\start_dev.ps1 -CryptoToolboxMode 0 -Reload
```

### Validation Pré-Production

```powershell
# Configuration identique à prod
.\start_dev.ps1 -EnableScheduler

# Vérifier health
curl http://localhost:8080/api/scheduler/health
```

---

## 📝 Scripts Manuels (Mode sans Scheduler)

### P&L Snapshots

```powershell
# Snapshot intraday
.venv\Scripts\python.exe scripts\pnl_snapshot.py --user_id jack --source cointracking_api

# Snapshot EOD (23:59)
.venv\Scripts\python.exe scripts\pnl_snapshot.py --eod

# PowerShell legacy
.\scripts\daily_snapshot.ps1 -UserId jack -Source cointracking_api
```

### OHLCV Updates

```powershell
# Mise à jour complète (1x/jour)
.venv\Scripts\python.exe scripts\update_price_history.py

# Mise à jour incrémentale (hourly)
.venv\Scripts\python.exe scripts\update_price_history.py --incremental
```

### Staleness Check

```powershell
curl http://localhost:8080/api/sources/list?user_id=jack
```

---

## 🐳 Docker / Production

En production, utilisez les variables d'environnement :

```dockerfile
# docker-compose.yml
environment:
  - RUN_SCHEDULER=1
  - CRYPTO_TOOLBOX_NEW=1
  - TZ=Europe/Zurich
```

Ou avec `.env` :

```bash
RUN_SCHEDULER=1
CRYPTO_TOOLBOX_NEW=1
SNAPSHOT_USER_ID=jack
SNAPSHOT_SOURCE=cointracking_api
```

---

## 📚 Documentation Liée

- [SCHEDULER.md](SCHEDULER.md) - Détails complets du scheduler
- [CRYPTO_TOOLBOX.md](CRYPTO_TOOLBOX.md) - Migration Flask → FastAPI
- [CLAUDE.md](../CLAUDE.md) - Guide complet pour agents
- [README.md](../README.md) - Documentation générale

---

**Dernière mise à jour:** Oct 2025
**Maintainer:** FastAPI Team

