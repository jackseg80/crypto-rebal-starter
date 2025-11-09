# Bugs à Corriger - Session Suivante

**Date** : 9 Oct 2025
**Priorité** : Moyenne (non-bloquants, mais polluent les logs)
**Temps estimé** : 10-15 minutes

---

## Bug #1 : Pydantic Validation Error (btc_cycle.position)

### Logs Observés

```
WARNING api.execution_endpoints: Error building unified signals: 1 validation error for CycleSignals
btc_cycle.position
  Input should be a valid number, unable to parse string as a number [type=float_parsing, input_value='mid_cycle', input_type=str]
    For further information visit https://errors.pydantic.dev/2.9/v/float_parsing
```

### Diagnostic

**Fichier probable** : `api/execution_endpoints.py`

**Problème** : Le modèle Pydantic `CycleSignals` attend un `float` pour `btc_cycle.position`, mais reçoit une string `'mid_cycle'`.

**Root cause** : Incohérence type entre :
- Ce qui est envoyé : `btc_cycle.position = 'mid_cycle'` (string)
- Ce qui est attendu : `position: float` (Pydantic model)

### Solution Probable

**Option A** : Changer le type Pydantic pour accepter string
```python
# api/execution_endpoints.py ou models/
class BTCCycle(BaseModel):
    position: str  # ou Union[str, float]
    # ...
```

**Option B** : Convertir la string en float avant validation
```python
# Mapper string → float
position_map = {
    'early_cycle': 0.25,
    'mid_cycle': 0.50,
    'late_cycle': 0.75,
    'peak': 1.0
}
btc_cycle.position = position_map.get(position_str, 0.5)
```

### Fichiers à Vérifier

```bash
# Trouver le modèle CycleSignals
grep -r "class CycleSignals" api/ models/

# Trouver où btc_cycle.position est assigné
grep -r "btc_cycle.position" api/
```

---

## Bug #2 : Sentiment Analysis Error (dict × int)

### Logs Observés

```
ERROR api.unified_ml_endpoints: Error in sentiment analysis for BTC: unsupported operand type(s) for *: 'dict' and 'int'
```

### Diagnostic

**Fichier** : `api/unified_ml_endpoints.py`

**Problème** : Tentative de multiplier un dict par un int (opération invalide)

**Scénario probable** :
```python
# Quelque part dans sentiment analysis
sentiment = get_sentiment('BTC')  # Retourne un dict
score = sentiment * 100  # ❌ dict × int = erreur
```

### Solution Probable

**Extraire la valeur du dict avant multiplication** :
```python
# Avant (bug)
sentiment = get_sentiment('BTC')  # {'score': 0.75, 'confidence': 0.8}
score = sentiment * 100  # ❌

# Après (fix)
sentiment = get_sentiment('BTC')
score = sentiment.get('score', 0.5) * 100  # ✅ 75
```

### Localiser le Bug

```bash
# Trouver la fonction sentiment analysis
grep -r "sentiment analysis for BTC" api/

# Chercher multiplication dans sentiment code
grep -A5 -B5 "sentiment.*\*" api/unified_ml_endpoints.py
```

### Ligne Probable

Dans `api/unified_ml_endpoints.py`, chercher :
- Fonction `get_sentiment()` ou `analyze_sentiment()`
- Ligne avec `sentiment * X` ou `X * sentiment`

---

## Bug #3 : Alert Broadcast Error (missing 'message')

### Logs Observés

```
ERROR services.alerts.alert_engine: Error broadcasting alert ALR-20251009-102715-a6f43727 via Phase 3B: 'Alert' object has no attribute 'message'
```

### Diagnostic

**Fichier** : `services/alerts/alert_engine.py`

**Problème** : Code essaie d'accéder à `alert.message`, mais l'objet `Alert` n'a pas cet attribut.

**Scénario probable** :
```python
# services/alerts/alert_engine.py
def broadcast_alert(alert):
    message = alert.message  # ❌ AttributeError
    # send(message)
```

### Solution Probable

**Option A** : L'attribut s'appelle différemment
```python
# Vérifier le vrai nom
message = alert.text  # ou alert.description, alert.content, etc.
```

**Option B** : Construire le message manuellement
```python
# Si pas d'attribut message direct
message = f"{alert.alert_type}: {alert.reason} (severity: {alert.severity})"
```

### Localiser le Bug

```bash
# Trouver la ligne exacte
grep -n "alert.message" services/alerts/alert_engine.py

# Voir la définition de Alert
grep -A20 "class Alert" services/alerts/ models/
```

### Fichiers Concernés

- `services/alerts/alert_engine.py` : Code qui broadcast
- `services/alerts/alert_types.py` ou `models/alerts.py` : Définition `Alert` class

---

## Ordre de Correction Recommandé

### 1. Bug #2 (Sentiment) - 3 minutes

**Le plus simple** : Juste une ligne à fixer (extraire valeur du dict)

```bash
# Ouvrir le fichier
code api/unified_ml_endpoints.py

# Chercher "sentiment analysis for BTC"
# Remplacer sentiment * X par sentiment.get('score', 0.5) * X
```

---

### 2. Bug #3 (Alert message) - 3 minutes

**Simple** : Identifier le bon attribut ou construire le message

```bash
# Voir la définition Alert
grep -A20 "class Alert" services/alerts/

# Corriger la ligne qui utilise alert.message
code services/alerts/alert_engine.py
```

---

### 3. Bug #1 (Pydantic) - 5-10 minutes

**Plus complexe** : Décision design (accepter string ou mapper)

```bash
# Trouver le modèle
grep -r "class CycleSignals" api/ models/

# Option facile : Changer type en Union[str, float]
# Option propre : Créer mapper string → float
```

---

## Validation

**Après chaque fix**, vérifier que l'erreur disparaît :

```bash
# Lancer serveur
python -m uvicorn api.main:app

# Monitorer logs (chercher les 3 erreurs)
# Bug #1 : "Error building unified signals"
# Bug #2 : "Error in sentiment analysis"
# Bug #3 : "Error broadcasting alert"

# Si une erreur disparaît → fix validé ✅
```

---

## Tests Post-Fix

### Bug #1 (CycleSignals)
```bash
# Déclencher via endpoint governance
curl http://localhost:8080/execution/governance/state
# Vérifier logs : plus d'erreur Pydantic
```

### Bug #2 (Sentiment)
```bash
# Déclencher via endpoint ML
curl http://localhost:8080/api/ml/sentiment/symbol/BTC
# Vérifier logs : plus d'erreur dict × int
```

### Bug #3 (Alert)
```bash
# Attendre qu'une alert se déclenche naturellement
# Ou simuler via AlertEngine
# Vérifier logs : plus d'erreur 'message' attribute
```

---

## Commits Attendus

```bash
# Après correction
git add api/unified_ml_endpoints.py
git commit -m "fix(ml): extract sentiment score before multiplication

Bug: 'dict' × int TypeError in sentiment analysis
Fix: Use sentiment.get('score', 0.5) instead of raw dict

Closes: Bug #2 from BUGS_TO_FIX_NEXT.md"

git add services/alerts/alert_engine.py
git commit -m "fix(alerts): use correct Alert attribute for broadcast

Bug: 'Alert' object has no attribute 'message'
Fix: Use alert.reason (or construct message manually)

Closes: Bug #3 from BUGS_TO_FIX_NEXT.md"

git add api/execution_endpoints.py models/
git commit -m "fix(governance): accept string for btc_cycle.position

Bug: Pydantic expects float but receives 'mid_cycle' string
Fix: Change type to Union[str, float] or add mapper

Closes: Bug #1 from BUGS_TO_FIX_NEXT.md"
```

---

## Notes Importantes

### Ces Bugs Sont Non-Bloquants

- Système fonctionne malgré les erreurs
- Juste pollution des logs
- Pas d'impact utilisateur visible

### Peuvent Attendre

- Priorité basse si autres features urgentes
- Mais bon de fixer pour logs propres

### Quick Wins

- 3 fixes rapides (3-5 min chacun)
- Logs plus propres = meilleur monitoring
- Bonne pratique pour maintenance

---

## Pour Reprendre (Nouvelle Session)

**Dire à GPT-5** :
> "Il reste 3 bugs à corriger (détails dans `docs/BUGS_TO_FIX_NEXT.md`). On commence par lequel ?"

**Ou** :
> "Corrige les 3 bugs dans `BUGS_TO_FIX_NEXT.md` dans l'ordre recommandé"

---

**Document créé** : 9 Oct 2025
**Durée estimée totale** : 10-15 minutes
**Impact** : Logs propres, meilleur monitoring

