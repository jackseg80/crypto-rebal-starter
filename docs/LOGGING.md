# Logging System

> Configuration du système de logs pour le debugging et l'analyse par IA
> Date: Oct 2025

## 📁 Emplacement

```
logs/
  app.log         # Logs actifs (max 5 MB)
  app.log.1       # Backup 1
  app.log.2       # Backup 2
  app.log.3       # Backup 3
```

## 🎯 Configuration

**Taille et Rotation:**
- **5 MB par fichier** (optimisé pour lecture par IA)
- **3 fichiers de backup** (15 MB total max)
- Rotation automatique quand app.log atteint 5 MB
- Encoding: UTF-8

**Sorties:**
- Console (stdout) - logs en temps réel pendant l'exécution
- Fichier rotatif - historique persistant pour analyse

**Niveau de log:**
- Configurable via `LOG_LEVEL` dans `.env` ou config
- Par défaut: `INFO`
- Niveaux: DEBUG, INFO, WARNING, ERROR, CRITICAL

## 📝 Format des Logs

```
2025-10-17 17:09:29,339 INFO crypto-rebalancer: 📝 Logging initialized
2025-10-17 17:09:29,412 INFO services.execution.exchange_adapter: Registered exchange: simulator
2025-10-17 17:09:29,416 WARNING services.execution.exchange_adapter: Binance API key not found
2025-10-17 17:09:37,897 ERROR crypto-rebalancer: ❌ Test error
```

**Structure:**
```
YYYY-MM-DD HH:MM:SS,mmm LEVEL module_name: message
```

## 🔍 Utilisation pour Debug

### 1. Lecture en Temps Réel

**PowerShell (Windows):**
```bash
Get-Content logs\app.log -Wait -Tail 20
```

**Bash/WSL:**
```bash
tail -f logs/app.log -n 20
```

### 2. Recherche d'Erreurs

**Erreurs récentes:**
```bash
Select-String -Path "logs\app.log" -Pattern "ERROR" | Select-Object -Last 20
```

**Warnings + Errors:**
```bash
Select-String -Path "logs\app.log" -Pattern "ERROR|WARNING" | Select-Object -Last 50
```

**Filtrer par module:**
```bash
Select-String -Path "logs\app.log" -Pattern "services.execution" | Select-Object -Last 30
```

### 3. Analyse avec Claude Code

**Lire le fichier de log complet:**
```
@logs/app.log
```

**Analyser plusieurs fichiers (historique):**
```
@logs/app.log @logs/app.log.1 @logs/app.log.2
```

**Prompt exemple:**
```
Analyze @logs/app.log and find:
1. All ERROR entries in the last hour
2. Most frequent warnings
3. Performance bottlenecks (slow operations)
4. Unusual patterns or anomalies
```

## 🛠️ Configuration Avancée

### Changer le Niveau de Log

**Via .env:**
```bash
LOG_LEVEL=DEBUG  # Pour plus de détails
LOG_LEVEL=WARNING  # Pour moins de verbosité
```

**Via code (api/main.py):**
```python
LOG_LEVEL = settings.logging.log_level  # Lecture depuis config
```

### Ajuster Taille et Rétention

**Modifier api/main.py (ligne ~56):**
```python
RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=10*1024*1024,  # 10 MB au lieu de 5 MB
    backupCount=5,           # 5 backups au lieu de 3
    encoding="utf-8"
)
```

### Logs Séparés par Module

**Créer un logger spécifique:**
```python
import logging
module_logger = logging.getLogger("crypto-rebalancer.risk")
module_logger.info("Risk calculation completed")
```

**Filtrer dans les logs:**
```bash
Select-String -Path "logs\app.log" -Pattern "crypto-rebalancer.risk"
```

## 📊 Exemples de Patterns à Chercher

### Startup Issues
```bash
Select-String -Path "logs\app.log" -Pattern "initialized|startup|FastAPI" | Select-Object -First 50
```

### API Errors
```bash
Select-String -Path "logs\app.log" -Pattern "HTTP [45][0-9]{2}|Exception|Error" -Context 2,2
```

### Performance Problems
```bash
# Rechercher les opérations lentes (>1000ms dans les logs structurés)
Select-String -Path "logs\app.log" -Pattern "duration_ms.*[1-9][0-9]{3,}"
```

### User Actions
```bash
# Rechercher actions d'un user spécifique
Select-String -Path "logs\app.log" -Pattern "user_id.*jack"
```

## 🤖 Utilisation par les Agents IA

Les agents IA (Claude Code, etc.) peuvent:

1. **Lire les logs pour comprendre l'état du serveur:**
   - Erreurs récentes
   - Warnings non résolus
   - Performance issues

2. **Analyser les patterns:**
   - Fréquence des erreurs
   - Modules problématiques
   - Corrélation temporelle

3. **Débugger des issues:**
   ```
   User: "Le serveur crash au démarrage"
   AI: *lit logs/app.log*
   AI: "Je vois l'erreur ligne 45: Binance API key not found..."
   ```

4. **Générer des insights:**
   - Identification des bottlenecks
   - Suggestions d'optimisation
   - Détection d'anomalies

## 🔒 Sécurité

**⚠️ Les logs peuvent contenir des infos sensibles:**
- Ne jamais committer `logs/` dans git (déjà dans .gitignore)
- Vérifier qu'aucune clé API n'est loguée
- Pas de mots de passe ou tokens dans les logs

**Bonnes pratiques:**
```python
# ✅ Bon
logger.info(f"API call to {exchange} successful")

# ❌ Mauvais
logger.info(f"API key: {api_key}")  # Ne JAMAIS logger des secrets
```

## 📚 Ressources

- Python logging: https://docs.python.org/3/library/logging.html
- RotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler
- FastAPI logging: https://fastapi.tiangolo.com/tutorial/debugging/

---

**Note pour les développeurs:**
Le système de logging est configuré dans `api/main.py` (lignes 38-65).
Les logs sont disponibles immédiatement après le démarrage du serveur.
