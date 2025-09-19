# Runbooks - Incidents & Résolutions

## Incidents Système

### 1. Backend Stale/Error

**Symptômes :**
- Badges affichent "STALE" ou "ERROR"
- Données obsolètes >60min
- APIs retournent erreurs 5xx

**Actions :**
1. Vérifier logs API : `tail -f logs/api.log`
2. Redémarrer services : `systemctl restart crypto-rebal`
3. Vérifier connectivité CoinTracking/Saxo
4. Reset caps manuellement si nécessaire

**Rollback :**
- Mode manuel complet
- Désactiver automation jusqu'à résolution

---

### 2. VaR > 4% (Risque Critique)

**Symptômes :**
- Alerte S3 VaR excessive
- Freeze système automatique
- Badge rouge "Cap 0%"

**Actions :**
1. Analyser corrélations : `/api/risk/advanced/correlation-matrix`
2. Identifier asset(s) problématique(s)
3. Réduire exposure ou diversifier
4. Attendre VaR <3.5% pour sortie automatique

**Cap Effectif :** 0% jusqu'à résolution

---

### 3. Contradiction >55%

**Symptômes :**
- Modèles ML en désaccord
- Signaux contradictoires
- Allocations incohérentes

**Actions :**
1. Inspecter détails : `/api/ml/debug/model-comparison`
2. Identifier modèle(s) divergent(s)
3. Recalibrer ou désactiver temporairement
4. Override manuel si nécessaire

**Bypass :** Seuil 70% pour anti-circularité

---

### 4. Recompute 409 (Conflit Concurrence)

**Symptômes :**
- HTTP 409 sur `/api/risk/recompute`
- "Another computation in progress"
- Allocation figée

**Actions :**
1. Attendre 5min (timeout automatique)
2. Si persistant : supprimer le fichier de verrou (data/scheduler.lock) puis relancer le job de calcul du risque
3. Vérifier processes : `ps aux | grep python`
4. Kill si nécessaire avec `pkill -f risk_management`

**Prévention :** Idempotency key dans requests

---

### 5. Freeze S3 Sémantique

**Symptômes :**
- Système en mode freeze complet
- Aucune nouvelle position possible
- Badge "FROZEN" affiché

**Actions :**
1. Identifier cause : `/api/alerts/active`
2. Résoudre alertes S3 ou contradictions >70%
3. Validation manuelle governance_admin
4. `POST /execution/governance/unfreeze` avec justification

**Autorisation :** governance_admin uniquement

---

## Monitoring & KPIs

### Métriques Clés
- **p95_latency** : <100ms API responses
- **stale_duration** : <60min données obsolètes
- **var_exceedances** : Compteur dépassements VaR 4%
- **non_executable_delta** : € non exécutable (caps)
- **downgrade_aggressive** : Nombre downgrades auto

### Alertes Prometheus
```yaml
- alert: StaleDataAlert
  expr: stale_duration_minutes > 60
  for: 5m

- alert: VaRExceedance
  expr: portfolio_var_percent > 4.0
  for: 1m

- alert: SystemFreeze
  expr: system_freeze_active == 1
  for: 0s
```

### Health Checks
- `GET /api/health` : Status général
- `GET /api/ml/health` : Status modèles ML
- `GET /api/risk/health` : Status risk engine

---

## Procédures d'Urgence

### Arrêt d'Urgence
```bash
# Stop complet système
systemctl stop crypto-rebal
pkill -f "python.*api"

# Backup configuration
cp data/config.json data/config.backup.$(date +%s).json

# Mode manuel uniquement
echo "EMERGENCY_MODE=true" >> .env
```

### Restauration Backup
```bash
# Restore dernière config valide
cp data/config.backup.latest.json data/config.json

# Reset état gouvernance : le redémarrage recharge automatiquement l'état actif

# Restart services
systemctl restart crypto-rebal
```

### Contact Support
- **Urgent** : governance_admin via Slack #crypto-alerts
- **Non-urgent** : Ticket via `/api/support/create`
- **Logs** : Auto-upload via `/api/support/logs`

---

## Webhooks & Notifications

### Discord Integration
```json
{
  "webhook_url": "https://discord.com/api/webhooks/...",
  "events": ["S3_alert", "freeze_system", "var_exceedance"],
  "rate_limit": "1/5min"
}
```

### Escalation Matrix
1. **S1 Info** : Logs uniquement
2. **S2 Warning** : Notification Slack
3. **S3 Critical** : Discord + SMS governance_admin
4. **System Freeze** : Appel téléphonique d'urgence
