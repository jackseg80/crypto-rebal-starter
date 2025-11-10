# SmartFolio - Migration Docker vers Linux NUC

Guide complet de migration depuis Windows vers Ubuntu 24.04.2 LTS avec Docker.

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Phase 1 : Préparation (Windows)](#phase-1--préparation-windows)
4. [Phase 2 : Transfert vers NUC](#phase-2--transfert-vers-nuc)
5. [Phase 3 : Build & Démarrage](#phase-3--build--démarrage)
6. [Phase 4 : Tests & Validation](#phase-4--tests--validation)
7. [Workflow Dev Windows → Prod NUC](#workflow-dev-windows--prod-nuc)
8. [Commandes Utiles](#commandes-utiles)
9. [Troubleshooting](#troubleshooting)

---

## Vue d'ensemble

### Architecture Docker

```
┌─────────────────────────────────────────┐
│         NUC Ubuntu 24.04.2 LTS          │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │     Docker Compose Stack          │  │
│  │                                   │  │
│  │  ┌─────────────┐  ┌────────────┐ │  │
│  │  │   Redis     │  │ SmartFolio │ │  │
│  │  │   Alpine    │←→│    API     │ │  │
│  │  │   (Cache)   │  │  (Python)  │ │  │
│  │  └─────────────┘  └────────────┘ │  │
│  │         ↓               ↓         │  │
│  │  ┌──────────────────────────┐    │  │
│  │  │   Named Volume           │    │  │
│  │  │   redis_data             │    │  │
│  │  └──────────────────────────┘    │  │
│  │         ↓               ↓         │  │
│  │  ┌──────────┐    ┌──────────┐   │  │
│  │  │ ./data/  │    │ ./logs/  │   │  │
│  │  │ (bind)   │    │ (bind)   │   │  │
│  │  └──────────┘    └──────────┘   │  │
│  └───────────────────────────────────┘  │
│                 ↑                        │
│          Port 8080 (LAN)                 │
└─────────────────────────────────────────┘
              ↑
       Windows Browser
   http://<nuc-ip>:8080
```

### Nouveaux Fichiers Créés

- **`Dockerfile.prod`** : Image optimisée avec healthcheck, Python 3.11
- **`docker-compose.prod.yml`** : Stack complète (Redis + API + volumes + auto-start)
- **`.env.docker.example`** : Template configuration Docker-ready

### Avantages Docker

✅ **Setup simplifié** : 1 commande pour tout démarrer
✅ **Auto-start** : Redémarrage automatique au boot NUC
✅ **Isolation** : Conteneurs séparés (pas de pollution système)
✅ **Healthchecks** : Redémarrage auto si panne
✅ **Redis intégré** : Cache + streaming opérationnels
✅ **Portabilité** : Fonctionne sur n'importe quel Linux avec Docker

---

## Prérequis

### Sur Windows

- ✅ Git installé
- ✅ Accès SSH au NUC (`ssh user@nuc-ip`)
- ✅ Projet SmartFolio fonctionnel

### Sur NUC Ubuntu 24.04.2 LTS

- ✅ Docker installé (vous l'avez déjà)
- ✅ Docker Compose installé
- ✅ Accès internet (APIs externes : CoinGecko, Binance, etc.)
- ✅ Port 8080 disponible

**Vérifier Docker sur NUC :**

```bash
# Via SSH sur NUC
docker --version          # Doit afficher : Docker version 24.x.x
docker-compose --version  # Doit afficher : docker-compose version 1.29.x ou 2.x
docker ps                 # Doit fonctionner sans erreur
```

---

## Phase 1 : Préparation (Windows)

### Étape 1.1 : Vérifier les fichiers Docker créés

```powershell
# Vérifier que les 3 fichiers existent
ls Dockerfile.prod
ls docker-compose.prod.yml
ls .env.docker.example
```

### Étape 1.2 : Test de build local (OPTIONNEL mais recommandé)

```powershell
# Test build pour détecter erreurs avant transfert NUC
docker-compose -f docker-compose.prod.yml build

# Si succès, vous verrez :
# Successfully built <image-id>
# Successfully tagged smartfolio-api:latest
```

⚠️ **Note Windows** : Le build peut être lent (~5-10 min première fois). Sur NUC Linux, ce sera plus rapide.

### Étape 1.3 : Commit et push vers Git

```powershell
# Ajouter les nouveaux fichiers Docker
git add Dockerfile.prod docker-compose.prod.yml .env.docker.example README-DOCKER.md
git commit -m "feat(docker): add production Docker setup for Linux NUC

- Dockerfile.prod with healthcheck and optimizations
- docker-compose.prod.yml with Redis and auto-start
- .env.docker template for Docker networking
- Migration guide README-DOCKER.md

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

git push
```

---

## Phase 2 : Transfert vers NUC

### Étape 2.1 : Connexion SSH et clone projet

```bash
# Sur NUC (via SSH)
ssh user@<nuc-ip>

# Créer dossier projet (exemple : /opt/smartfolio)
cd /opt
sudo mkdir -p smartfolio
sudo chown $USER:$USER smartfolio
cd smartfolio

# Cloner le repository
git clone <votre-repo-url> .

# Vérifier que les fichiers Docker sont présents
ls -la Dockerfile.prod docker-compose.prod.yml .env.docker.example
```

### Étape 2.2 : Transférer données utilisateurs

```powershell
# Sur Windows (PowerShell)
# Remplacer <nuc-ip> et <user> par vos valeurs

# Transférer data/users/ (portfolios, cache, config)
scp -r data/users/* <user>@<nuc-ip>:/opt/smartfolio/data/users/

# Transférer P&L history
scp data/portfolio_history.json <user>@<nuc-ip>:/opt/smartfolio/data/

# Transférer secrets API (CRITIQUE)
scp data/users/demo/secrets.json <user>@<nuc-ip>:/opt/smartfolio/data/users/demo/
scp data/users/jack/secrets.json <user>@<nuc-ip>:/opt/smartfolio/data/users/jack/
```

**Vérifier transfert réussi :**

```bash
# Sur NUC
ls -R data/users/
# Doit afficher : demo/, jack/ avec leurs fichiers
```

### Étape 2.3 : Créer .env depuis template

```bash
# Sur NUC
cd /opt/smartfolio

# Copier template
cp .env.docker.example .env

# Optionnel : éditer si besoin de personnaliser
nano .env
# Vérifier HOST=0.0.0.0, PORT=8080, REDIS_URL=redis://redis:6379/0
```

---

## Phase 3 : Build & Démarrage

### Étape 3.1 : Build image Docker

```bash
# Sur NUC
cd /opt/smartfolio

# Build l'image (première fois : 5-8 min)
docker-compose -f docker-compose.prod.yml build

# Sortie attendue :
# Successfully built <hash>
# Successfully tagged smartfolio-smartfolio:latest
```

### Étape 3.2 : Démarrer le stack

```bash
# Démarrer en background (-d = detached)
docker-compose -f docker-compose.prod.yml up -d

# Sortie attendue :
# Creating network "smartfolio-network" ... done
# Creating volume "smartfolio-redis-data" ... done
# Creating smartfolio-redis ... done
# Creating smartfolio-api ... done
```

### Étape 3.3 : Vérifier démarrage

```bash
# Voir les conteneurs actifs
docker ps

# Sortie attendue :
# CONTAINER ID   IMAGE                      STATUS                 PORTS                    NAMES
# abc123def456   smartfolio-smartfolio      Up 30s (healthy)       0.0.0.0:8080->8080/tcp   smartfolio-api
# 789ghi012jkl   redis:7-alpine             Up 35s (healthy)       6379/tcp                 smartfolio-redis

# Voir les logs en temps réel
docker-compose -f docker-compose.prod.yml logs -f

# Attendre ces lignes :
# smartfolio-redis | Ready to accept connections
# smartfolio-api   | Application startup complete
# smartfolio-api   | Redis ready at redis://redis:6379/0
# smartfolio-api   | Scheduler initialized (RUN_SCHEDULER=1)
```

**Appuyer sur Ctrl+C pour quitter les logs** (conteneurs continuent de tourner).

---

## Phase 4 : Tests & Validation

### Étape 4.1 : Test API local (sur NUC)

```bash
# Sur NUC
curl http://localhost:8080/docs
# Doit retourner HTML (Swagger UI)

curl http://localhost:8080/balances/current?user_id=demo
# Doit retourner JSON avec balances

curl http://localhost:8080/api/ml/sentiment/symbol/BTC
# Doit retourner JSON avec sentiment ML
```

### Étape 4.2 : Test accès LAN (depuis Windows)

```
Ouvrir navigateur Windows :

http://<nuc-ip>:8080/
http://<nuc-ip>:8080/dashboard.html
http://<nuc-ip>:8080/analytics-unified.html
```

**Trouver IP NUC :**

```bash
# Sur NUC
ip addr show | grep inet
# Exemple : inet 192.168.1.50/24
```

### Étape 4.3 : Vérifier healthchecks

```bash
# Sur NUC
docker ps

# Colonne STATUS doit afficher "healthy" :
# Up 2 minutes (healthy)
```

Si "unhealthy", voir [Troubleshooting](#troubleshooting).

### Étape 4.4 : Tester auto-start au boot

```bash
# Sur NUC
sudo reboot

# Attendre 2-3 minutes, puis reconnecter SSH
ssh user@<nuc-ip>

# Vérifier que les conteneurs sont UP
docker ps

# Les 2 conteneurs doivent être présents (smartfolio-api, smartfolio-redis)

# Tester API
curl http://localhost:8080/docs
```

✅ **Si succès = Migration terminée !**

---

## Workflow Dev Windows → Prod NUC

### Après modifications sur Windows

```powershell
# 1. Commit & push
git add .
git commit -m "feat: description changement"
git push
```

### Déploiement sur NUC

```bash
# 2. SSH vers NUC
ssh user@<nuc-ip>
cd /opt/smartfolio

# 3. Pull dernières modifications
git pull

# 4. Rebuild & restart (rebuild seulement si code Python modifié)
docker-compose -f docker-compose.prod.yml up -d --build

# Rebuild : 30-60 sec (Docker cache layers)

# 5. Vérifier logs
docker-compose -f docker-compose.prod.yml logs -f --tail 50

# Attendre "Application startup complete"
```

### Changements data/ ou logs/ uniquement

Si vous modifiez uniquement `data/` ou `logs/` (pas de code Python) :

```bash
# Simple restart (pas de rebuild)
docker-compose -f docker-compose.prod.yml restart
```

---

## Commandes Utiles

### Gestion conteneurs

```bash
# Voir conteneurs actifs
docker ps

# Voir TOUS les conteneurs (actifs + arrêtés)
docker ps -a

# Arrêter le stack
docker-compose -f docker-compose.prod.yml down

# Arrêter ET supprimer volumes (⚠️ perte données Redis)
docker-compose -f docker-compose.prod.yml down -v

# Redémarrer un service spécifique
docker-compose -f docker-compose.prod.yml restart smartfolio
docker-compose -f docker-compose.prod.yml restart redis
```

### Logs & Debug

```bash
# Logs temps réel (tous services)
docker-compose -f docker-compose.prod.yml logs -f

# Logs temps réel (service spécifique)
docker-compose -f docker-compose.prod.yml logs -f smartfolio
docker-compose -f docker-compose.prod.yml logs -f redis

# Logs récents (50 dernières lignes)
docker-compose -f docker-compose.prod.yml logs --tail 50

# Logs depuis timestamp
docker-compose -f docker-compose.prod.yml logs --since 2024-01-01T10:00:00
```

### Accès shell conteneur

```bash
# Shell interactif dans conteneur API
docker exec -it smartfolio-api bash

# Exemples commandes dans conteneur :
ls /app/data/users/           # Voir données users
cat /app/logs/app.log         # Lire logs
python -m pytest tests/       # Lancer tests
exit                          # Sortir

# Shell Redis (redis-cli)
docker exec -it smartfolio-redis redis-cli
# Commandes Redis :
ping               # Doit retourner PONG
keys *             # Voir toutes les clés
get <key>          # Lire valeur
exit               # Sortir
```

### Nettoyage Docker

```bash
# Supprimer images inutilisées (libérer espace)
docker image prune -a

# Supprimer volumes orphelins
docker volume prune

# Nettoyage complet (⚠️ supprime TOUT ce qui n'est pas actif)
docker system prune -a --volumes
```

### Monitoring ressources

```bash
# Utilisation CPU/RAM en temps réel
docker stats

# Sortie :
# CONTAINER ID   NAME               CPU %   MEM USAGE / LIMIT   MEM %   NET I/O
# abc123def456   smartfolio-api     15%     1.2GB / 16GB        7.5%    2MB / 1MB
# 789ghi012jkl   smartfolio-redis   2%      50MB / 16GB         0.3%    500KB / 300KB
```

---

## Troubleshooting

### Problème : Conteneur "unhealthy"

**Symptômes :**
```bash
docker ps
# STATUS: Up 5 minutes (unhealthy)
```

**Solution :**
```bash
# Voir logs détaillés
docker-compose -f docker-compose.prod.yml logs smartfolio

# Erreurs communes :
# - "Redis connection refused" → Vérifier Redis actif
# - "Port 8080 already in use" → Changer PORT dans .env
# - "Playwright browser not found" → Rebuild image
```

### Problème : Redis connection refused

**Symptômes :**
```
ConnectionError: Error 111 connecting to redis:6379. Connection refused.
```

**Solution :**
```bash
# Vérifier Redis actif
docker ps | grep redis

# Si absent, redémarrer
docker-compose -f docker-compose.prod.yml up -d redis

# Vérifier healthcheck Redis
docker inspect smartfolio-redis | grep Health -A 10
```

### Problème : Port 8080 déjà utilisé

**Symptômes :**
```
Error starting userland proxy: listen tcp 0.0.0.0:8080: bind: address already in use
```

**Solution :**
```bash
# Trouver processus utilisant port 8080
sudo lsof -i :8080
# ou
sudo netstat -tlnp | grep 8080

# Tuer processus (remplacer <PID>)
sudo kill <PID>

# OU changer port dans .env
nano .env
# PORT=8081
docker-compose -f docker-compose.prod.yml up -d
```

### Problème : Données utilisateurs introuvables

**Symptômes :**
```
FileNotFoundError: data/users/demo/secrets.json
```

**Solution :**
```bash
# Vérifier ownership volumes
ls -la data/users/

# Si permissions incorrectes :
sudo chown -R $USER:$USER data/

# Vérifier montage volumes Docker
docker inspect smartfolio-api | grep -A 20 Mounts
```

### Problème : Image build échoue

**Symptômes :**
```
ERROR: failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
```

**Solution :**
```bash
# Vérifier requirements.txt existe
cat requirements.txt

# Rebuild sans cache
docker-compose -f docker-compose.prod.yml build --no-cache

# Si problème persiste, vérifier connexion internet NUC
ping pypi.org
```

### Problème : Logs "disk full"

**Solution :**
```bash
# Vérifier espace disque
df -h

# Purger logs Docker
docker system prune -a --volumes

# Logs applicatifs (auto-rotation 5MB x4)
ls -lh logs/
# Si trop gros, supprimer manuellement
rm logs/app.log.2 logs/app.log.3
```

---

## Ressources Additionnelles

### Documentation Projet

- **Architecture** : `docs/ARCHITECTURE.md`
- **Redis Setup** : `docs/REDIS_SETUP.md`
- **Multi-tenant** : `CLAUDE.md` (section Multi-Tenant)
- **Logging** : `docs/LOGGING.md`

### Docker Documentation

- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Docker Healthchecks](https://docs.docker.com/engine/reference/builder/#healthcheck)
- [Docker Volumes](https://docs.docker.com/storage/volumes/)

---

## Notes Performances

### Estimations NUC (i5-7260U, 16GB RAM)

| Métrique | Valeur | Commentaire |
|----------|--------|-------------|
| **Build initial** | 5-8 min | Première fois (télécharge images, compile deps) |
| **Rebuild après modif** | 30-60 sec | Docker cache layers (seul code Python recompile) |
| **Startup time** | 20-40 sec | Redis ~5s, API ~15-35s (Playwright init) |
| **RAM utilisée** | 1.5-2.5 GB | Redis ~50MB, API ~1-2GB, Docker engine ~300MB |
| **CPU idle** | 5-10% | Scheduler + warmers |
| **CPU peak** | 40-80% | ML inference + Playwright scraping |

### Optimisations Possibles

Si ressources limitées, décommenter dans `docker-compose.prod.yml` :

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Max 2 cores
      memory: 4G       # Max 4GB RAM
```

---

**🎉 Migration terminée ! Votre SmartFolio tourne maintenant sur Linux avec Docker.**

Pour questions ou problèmes : ouvrir une issue GitHub ou consulter `CLAUDE.md`.
