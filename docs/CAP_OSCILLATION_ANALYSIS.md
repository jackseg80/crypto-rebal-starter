# Cap Oscillation - Analyse & Solutions

**Date** : Oct 2025
**Problème** : Cap oscille entre 7%, 7.7%, 8% malgré fixes frontend/backend

---

## Sources d'Oscillation Identifiées

### 1. Inputs Instables (contradiction/confidence)

**Fichier** : `services/execution/governance.py:505-528`

**Logique actuelle** :
```python
if contradiction > 0.7:
    cap_raw = 3-12%  # Défensif
elif prudent_mode or confidence < 0.6:
    cap_raw = 7%     # Rotation
elif confidence > 0.8 and contradiction < 0.2:
    cap_raw = 12%    # Agressif
else:
    cap_raw = 8%     # Normal
```

**Problème** :
- Si `contradiction` oscille autour de 0.45 (seuil hystérésis prudent)
- Si `confidence` varie entre 0.55-0.65
- Alors `cap_raw` oscille entre 7% et 8%

**Impact** : Même avec smoothing 0.7/0.3, variation persiste

---

### 2. Smoothing Insuffisant pour Petites Variations

**Fichier** : `services/execution/governance.py:531`

**Formule** : `cap_smoothed = 0.7 * last_cap + 0.3 * cap_raw`

**Scénario** :
```
Iteration 1: cap_raw=8%  → cap_smoothed = 0.7×0.077 + 0.3×0.08  = 0.0779 (7.79%)
Iteration 2: cap_raw=7%  → cap_smoothed = 0.7×0.0779 + 0.3×0.07 = 0.0755 (7.55%)
Iteration 3: cap_raw=8%  → cap_smoothed = 0.7×0.0755 + 0.3×0.08 = 0.0769 (7.69%)
```

**Résultat** : Variation lente mais continue 7.5% ↔ 7.9%

**Pire cas** : Si cap_raw oscille chaque run, smoothing ne converge jamais

---

### 3. Hystérésis Stale Flip-Flop

**Fichier** : `services/execution/governance.py:828-846`

**Config** :
```python
stale_activate_seconds: 3600     # 1h
stale_deactivate_seconds: 1800   # 30min
trend_stability_required: 3      # 3 points stables
```

**Problème** :
```
ML refresh OK   → signals_age=30s   → stale OFF → cap=cap_engine (7.7%)
ML refresh fail → signals_age=3700s → stale ON  → cap=8% (OVERRIDE)
ML refresh OK   → signals_age=30s   → stale OFF → cap=7.7%
```

**Impact** : Priorité `cap_stale` (ligne 598) override le cap smoothé

**Scénario réel** :
- Si ML orchestrator timeout intermittent
- Si réseau API externe flaky
- Oscillation 7.7% ↔ 8%

---

### 4. Priorité Caps qui Override le Smoothing

**Fichier** : `services/execution/governance.py:592-601`

**Ordre de priorité** :
```python
if cap_error is not None:    # Error > 2h
    cap = cap_error           # 5%
elif cap_stale is not None:  # Stale > 1h  ← PROBLÈME
    cap = min(cap, cap_stale) # 8% OVERRIDE
elif alert_reduction > 0:
    cap = cap_alert
else:
    cap = cap_engine          # Cap smoothé (ex: 7.7%)
```

**Problème** :
- Quand stale flip-flop, il override le cap_engine smoothé
- Le smoothing (lignes 530-541) est annulé par la priorité stale

**Conséquence** : Les efforts de smoothing/garde-fou sont contournés

---

### 5. Contradiction Index Calculation

**Fichier** : `services/execution/governance.py:427-475`

**Méthode** : `_compute_contradiction_index()`

**Facteurs** :
1. Volatilité vs Régime (high vol + bull = 0.3 contradiction)
2. Sentiment vs Régime (fear/greed extrêmes = 0.25)
3. Corrélations élevées (avg_corr > 0.7 = 0.2)

**Problème potentiel** :
- Si inputs (vol, sentiment, regime) changent fréquemment
- Contradiction oscille → prudent_mode flip-flop → cap_raw change

**Dépendance** :
- Données externes (Fear & Greed Index, ML predictions)
- Si ces sources sont bruyantes, contradiction est instable

---

## Solutions Proposées

### Solution 1 : Augmenter Smoothing (Quick Win)

**Changement** : `governance.py:531`

```python
# Avant
cap_smoothed = 0.7 * self._last_cap + 0.3 * cap_raw

# Après
cap_smoothed = 0.85 * self._last_cap + 0.15 * cap_raw
```

**Impact** :
- Réaction plus lente aux changements → stabilité++
- Mais : réactivité-- aux vrais changements de market

**Trade-off** : 85/15 = très stable mais lent, 70/30 = équilibré

**Recommandation** : Tester 80/20 comme compromis

---

### Solution 2 : Dead Zone pour cap_raw (Hysteresis Cap)

**Nouveau code** : `governance.py:541` (après smoothing)

```python
# Dead zone : ignorer variations < 0.5% (50 bps)
DEAD_ZONE_BPS = 0.005  # 0.5%

if abs(cap_raw - self._last_cap) < DEAD_ZONE_BPS:
    cap_raw = self._last_cap  # Keep stable
```

**Impact** :
- Si cap_raw oscille 7.7% ↔ 8% (diff 30bps < 50bps) → garde 7.7%
- Évite le churning sur micro-variations

**Avantage** : Simple, préserve réactivité sur vrais changements (>0.5%)

---

### Solution 3 : Désactiver Override Stale sur Cap Smoothé

**Changement** : `governance.py:592-601`

```python
# Avant
if cap_stale is not None:
    cap = min(cap, cap_stale)  # OVERRIDE cap_engine

# Après
if cap_stale is not None:
    cap = min(cap_smoothed, cap_stale)  # Utilise le smoothed, pas override
    # Ou même : ignorer cap_stale si variation < seuil
    if abs(cap_smoothed - cap_stale) < 0.01:  # <1% diff
        cap = cap_smoothed  # Keep smoothed
```

**Impact** :
- Préserve le smoothing même en mode stale
- Stale devient un "plafond" plutôt qu'un override brutal

---

### Solution 4 : Rate Limiter sur Contradiction (Advanced)

**Nouveau code** : `governance.py:485` (début de `_derive_execution_policy`)

```python
# Rate limiter : limiter variation contradiction par run
MAX_CONTRADICTION_CHANGE = 0.05  # 5 points max

if hasattr(self, '_last_contradiction'):
    contradiction_delta = abs(contradiction - self._last_contradiction)
    if contradiction_delta > MAX_CONTRADICTION_CHANGE:
        # Clamp variation
        if contradiction > self._last_contradiction:
            contradiction = self._last_contradiction + MAX_CONTRADICTION_CHANGE
        else:
            contradiction = self._last_contradiction - MAX_CONTRADICTION_CHANGE

self._last_contradiction = contradiction
```

**Impact** :
- Empêche les sauts brusques de contradiction (ex: 0.3 → 0.7)
- Lisse les transitions prudent/normal

**Trade-off** : Retard sur détection de vraies crises

---

### Solution 5 : Logging Renforcé (Diagnostic)

**Ajout** : `governance.py:662-664` (avant return policy)

```python
# Log détaillé pour debug oscillation
logger.info(
    f"[CAP_FLOW] contradiction={contradiction:.3f}, confidence={confidence:.3f}, "
    f"cap_raw={cap_raw:.1%}, cap_smoothed={cap_smoothed:.1%}, "
    f"cap_stale={cap_stale or 'N/A'}, cap_error={cap_error or 'N/A'}, "
    f"cap_alert={cap_alert:.1%}, cap_final={cap:.1%}, "
    f"var_state={var_state}, stale_state={stale_state}, "
    f"signals_age={signals_age:.0f}s, prudent_mode={self._prudent_mode}"
)
```

**Impact** :
- Visibilité complète sur chaque run
- Permet de diagnostiquer quelle variable oscille

**Usage** :
```bash
# Lancer serveur et grep logs
.venv\Scripts\python.exe -m uvicorn api.main:app | findstr CAP_FLOW
```

---

## Recommandations Immédiates

### Phase 1 : Diagnostic (1-2 jours)

1. ✅ Ajouter logging renforcé (Solution 5)
2. Monitorer pendant 24h pour identifier pattern exact
3. Analyser logs : quelle variable change réellement ?

### Phase 2 : Quick Wins (1 jour)

4. Implémenter Dead Zone 0.5% (Solution 2) - simple et safe
5. Augmenter smoothing 70/30 → 80/20 (Solution 1) - test A/B

### Phase 3 : Structural Fix (2-3 jours)

6. Désactiver override stale (Solution 3) - préserve smoothing
7. Rate limiter contradiction (Solution 4) si logs montrent spikes

### Phase 4 : Validation (1-2 jours)

8. Unit tests pour oscillation scenarios
9. Regression tests avec données historiques
10. Monitoring production 48h

---

## Tests à Implémenter

```python
# tests/unit/test_cap_stability.py

def test_cap_no_oscillation_on_micro_variations():
    """Cap ne doit pas osciller sur variations <0.5%"""
    engine = GovernanceEngine()

    # Run 1: cap_raw=7%
    signals1 = MLSignals(contradiction=0.42, confidence=0.65)
    policy1 = engine._derive_execution_policy()

    # Run 2: cap_raw=8% (micro-variation)
    signals2 = MLSignals(contradiction=0.39, confidence=0.65)
    policy2 = engine._derive_execution_policy()

    # Variation doit être <0.5% (dead zone)
    assert abs(policy2.cap_daily - policy1.cap_daily) < 0.005

def test_cap_smoothing_converges():
    """Smoothing doit converger, pas osciller indéfiniment"""
    engine = GovernanceEngine()

    caps = []
    for i in range(20):
        # Oscillation artificielle 7% ↔ 8%
        signals = MLSignals(
            contradiction=0.42 if i % 2 == 0 else 0.39,
            confidence=0.65
        )
        policy = engine._derive_execution_policy()
        caps.append(policy.cap_daily)

    # Après 20 runs, variation doit être <1%
    recent_caps = caps[-5:]
    assert max(recent_caps) - min(recent_caps) < 0.01

def test_stale_does_not_override_smoothing():
    """Cap stale ne doit pas annuler le smoothing"""
    engine = GovernanceEngine()

    # Run 1: Normal, cap=7.7%
    policy1 = engine._derive_execution_policy()

    # Run 2: Stale triggered (signals old)
    engine.current_state.signals.as_of = datetime.now() - timedelta(hours=2)
    policy2 = engine._derive_execution_policy()

    # Cap stale (8%) ne doit pas override brutalement
    # Variation doit être lissée
    assert abs(policy2.cap_daily - policy1.cap_daily) < 0.01
```

---

## Conclusion

**Diagnostic** : L'oscillation actuelle (7% ↔ 8%) est probablement due à :
1. **Priorité cap_stale override** le cap smoothé
2. **Hystérésis stale flip-flop** si refresh ML intermittent
3. **Smoothing 70/30 insuffisant** pour micro-variations

**Solution recommandée** :
- **Court terme** : Dead zone + logging (Solutions 2 + 5)
- **Moyen terme** : Désactiver override stale (Solution 3)
- **Long terme** : Rate limiter contradiction (Solution 4)

**Principe clé** : Le smoothing/hystérésis doivent être **préservés** par le système de priorité caps, pas **contournés**.
