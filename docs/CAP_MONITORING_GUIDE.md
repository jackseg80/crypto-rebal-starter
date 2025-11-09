# Cap Monitoring Guide - Quick Start

**Date** : Oct 2025
**Objectif** : Monitorer le cap en temps réel après implémentation anti-oscillation

---

## Phase 1 + 2 Implémentées ✅

### Changements appliqués

1. **Dead Zone 0.5%** : Ignore variations < 50 bps (ex: 7.7% ↔ 7.9%)
2. **Smoothing 80/20** : Plus stable (avant 70/30)
3. **Logging CAP_FLOW** : Visibilité complète sur tous les caps

---

## Comment Monitorer

### Option 1 : Logs en Direct (Recommandé)

```bash
# Activer .venv
.venv\Scripts\Activate.ps1

# Lancer serveur avec filtre CAP_FLOW
python -m uvicorn api.main:app | findstr CAP_FLOW
```

**Sortie attendue** :
```
[CAP_FLOW] contradiction=0.420, confidence=0.650, cap_raw=0.0800 (8.00%), cap_smoothed=0.0796 (7.96%), cap_engine=0.0796 (7.96%), cap_stale=N/A, cap_error=N/A, cap_alert=0.0796 (7.96%), cap_final=0.0796 (7.96%), var_state=normal, stale_state=normal, signals_age=45s, prudent_mode=False, mode=Normal
```

### Option 2 : Logs dans Fichier

```bash
# Rediriger vers fichier
python -m uvicorn api.main:app > cap_logs.txt 2>&1

# Monitorer en temps réel
Get-Content cap_logs.txt -Wait | Select-String "CAP_FLOW"
```

### Option 3 : Grep Logs Existants

```bash
# Si serveur déjà lancé
Get-Content logs/api.log | Select-String "CAP_FLOW" | Select-Object -Last 20
```

---

## Interpréter les Logs

### Champs Clés

| Champ | Description | Valeur Normale |
|-------|-------------|----------------|
| `contradiction` | Index de contradiction (0-1) | 0.2-0.5 |
| `confidence` | Confiance ML (0-1) | 0.5-0.8 |
| `cap_raw` | Cap calculé avant smoothing | 7-12% |
| `cap_smoothed` | Cap après smoothing 80/20 | 7-10% |
| `cap_engine` | Cap après garde-fous | = cap_smoothed |
| `cap_stale` | Override si signals stale | N/A ou 8% |
| `cap_error` | Override si signals error | N/A ou 5% |
| `cap_final` | **Cap appliqué réellement** | 7-10% |
| `var_state` | Hystérésis VaR | normal/prudent |
| `stale_state` | Hystérésis staleness | normal/stale |
| `signals_age` | Age des signaux ML | 0-3600s |
| `prudent_mode` | Mode prudent actif | True/False |

### Scénarios d'Oscillation

#### ✅ **Stable (OK)**
```
cap_final=0.0796 (7.96%)
cap_final=0.0797 (7.97%)  # +1 bps ✅
cap_final=0.0796 (7.96%)
```
→ Variation < 0.5%, dead zone actif

#### ⚠️ **Oscillation Micro (Acceptable)**
```
cap_final=0.0770 (7.70%)
cap_final=0.0774 (7.74%)  # +4 bps
cap_final=0.0777 (7.77%)  # +3 bps (converge)
```
→ Smoothing 80/20 converge, OK

#### ❌ **Oscillation Problématique**
```
cap_final=0.0770 (7.70%)
cap_final=0.0800 (8.00%)  # +30 bps ❌ (bypass dead zone)
cap_final=0.0770 (7.70%)  # -30 bps ❌
```
→ Regarder `cap_stale`, `stale_state`, `contradiction`

---

## Diagnostics Rapides

### Cas 1 : cap_stale flip-flop

**Symptôme** :
```
stale_state=normal, cap_stale=N/A, cap_final=7.70%
stale_state=stale, cap_stale=8.00%, cap_final=8.00%  # OVERRIDE
stale_state=normal, cap_stale=N/A, cap_final=7.70%
```

**Cause** : ML refresh intermittent (timeout, rate limit)

**Solution Phase 3** :
- Désactiver override `cap_stale` brutal
- Ou : appliquer smoothing sur `cap_stale` aussi

### Cas 2 : contradiction spike

**Symptôme** :
```
contradiction=0.42, cap_raw=8.00%, cap_final=7.96%
contradiction=0.71, cap_raw=6.00%, cap_final=7.37%  # Jump -59 bps
contradiction=0.39, cap_raw=8.00%, cap_final=7.50%
```

**Cause** : Input ML instable (vol, sentiment, regime)

**Solution Phase 3** :
- Ajouter rate limiter sur `contradiction` (max Δ=0.05 par run)

### Cas 3 : prudent_mode flip-flop

**Symptôme** :
```
prudent_mode=False, cap_raw=8.00%, cap_final=7.96%
prudent_mode=True, cap_raw=7.00%, cap_final=7.77%  # -100 bps raw
prudent_mode=False, cap_raw=8.00%, cap_final=7.82%
```

**Cause** : `contradiction` oscille autour de 0.40-0.45 (seuils hystérésis)

**Solution** :
- Hystérésis déjà implémentée (activate 0.45, deactivate 0.40)
- Si persiste : élargir gap (0.50/0.35)

---

## Métriques de Succès

### Objectif : Variation < 10 bps par run

**Avant fix** :
- Oscillation 1% ↔ 7% ↔ 8% (600+ bps)

**Après Phase 1+2 (attendu)** :
- Variation < 10 bps (0.1%) par run
- Convergence en 5-10 runs

**Test** : Lancer serveur, monitorer 20 lignes CAP_FLOW :
```bash
python -m uvicorn api.main:app | findstr CAP_FLOW | Select-Object -First 20
```

Calculer :
```python
# Extraire cap_final de chaque ligne
caps = [0.0796, 0.0797, 0.0796, ...]  # Exemple

# Variation max
max_variation = max(caps) - min(caps)
print(f"Max variation: {max_variation*10000:.0f} bps")  # Doit être < 100 bps

# Variation moyenne entre runs
avg_delta = sum(abs(caps[i] - caps[i-1]) for i in range(1, len(caps))) / (len(caps)-1)
print(f"Avg delta: {avg_delta*10000:.0f} bps")  # Doit être < 10 bps
```

---

## Next Steps si Oscillation Persiste

### Si `stale_state` flip-flop → Phase 3A

**Fichier** : `services/execution/governance.py:597-598`

**Changement** :
```python
# Avant
elif cap_stale is not None:
    cap = min(cap, cap_stale)  # OVERRIDE brutal

# Après
elif cap_stale is not None:
    # Smooth stale clamp, don't override
    if abs(cap_smoothed - cap_stale) > 0.01:  # >1% diff
        cap = min(cap_smoothed, cap_stale)
    else:
        cap = cap_smoothed  # Keep smoothed if close
```

### Si `contradiction` spikes → Phase 3B

**Fichier** : `services/execution/governance.py:485`

**Ajout après lecture contradiction** :
```python
# Rate limiter contradiction
MAX_CONTRADICTION_CHANGE = 0.05  # 5 points max

if hasattr(self, '_last_contradiction'):
    delta = abs(contradiction - self._last_contradiction)
    if delta > MAX_CONTRADICTION_CHANGE:
        # Clamp variation
        if contradiction > self._last_contradiction:
            contradiction = self._last_contradiction + MAX_CONTRADICTION_CHANGE
        else:
            contradiction = self._last_contradiction - MAX_CONTRADICTION_CHANGE
        logger.warning(f"Contradiction rate limited: {self._last_contradiction:.3f} → {contradiction:.3f}")

self._last_contradiction = contradiction
```

---

## Checklist de Validation

- [ ] Logs CAP_FLOW visibles en temps réel
- [ ] `cap_final` varie < 10 bps par run (sur 20 runs)
- [ ] Dead zone actif (`cap_raw` stable si variation < 50 bps)
- [ ] Smoothing converge (tendance vers moyenne, pas flip-flop)
- [ ] `stale_state` stable (pas normal ↔ stale chaque run)
- [ ] `contradiction` stable (pas de spikes > 0.2 entre runs)

Si **tous les checks OK** → Problème résolu ✅

Si **oscillation persiste** → Analyser logs, identifier variable instable, implémenter Phase 3

---

## Contacts & Docs

- **Analyse complète** : `docs/CAP_OSCILLATION_ANALYSIS.md`
- **Code** : `services/execution/governance.py:530-677`
- **Commits** :
  - `1627e71` : feat(cap) anti-oscillation system
  - `79ade52` : fix(cap) frontend fallbacks
  - `645ad33` : fix(cap) backend ERROR fallbacks
