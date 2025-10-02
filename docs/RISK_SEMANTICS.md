# Risk Semantics — Source de Vérité

> **⚠️ Règle Canonique — Sémantique Risk (Option A)**
>
> Le **Risk Score** est un indicateur **positif** de robustesse, borné **[0..100]**.
>
> **Convention** : Plus haut = plus robuste (risque perçu plus faible).
>
> **Conséquence** : Dans le Decision Index (DI), Risk contribue **positivement** :
> ```
> DI = wCycle·scoreCycle + wOnchain·scoreOnchain + wRisk·scoreRisk
> ```
>
> **❌ Interdit** : Ne jamais inverser avec `100 - scoreRisk` (calculs, visualisations, contributions).
>
> **Visualisation** : Contribution = `(poids × score) / Σ(poids × score)`
>
> 📖 **Source de vérité** : [docs/RISK_SEMANTICS.md](RISK_SEMANTICS.md)

---

## Architecture Centralisée (Oct 2025)

### 🏛️ Single Source of Truth

**Module central** : [`services/risk_scoring.py`](../services/risk_scoring.py)

Toute logique de calcul Risk Score et mapping score→level **DOIT** être importée depuis ce module.

**❌ Anti-pattern** : Dupliquer la logique dans d'autres services (risque de divergence).

### 📊 Dual Score System

| Score | Type | Base de calcul | Usage |
|-------|------|---------------|--------|
| **`risk_score`** | Autoritaire | VaR + Sharpe + Drawdown + Volatilité | UI, Decision Index, communication |
| **`risk_score_structural`** | Structurel | `risk_score` + GRI + Concentration + Structure | Garde-fou allocation, caps governance |

**Recommandation** : Approche hybride pour niveau final
```python
final_level = max(level(risk_score), level(risk_score_structural))
```

### 🔢 Mapping Canonique Score → Level

```python
# Thresholds (services/risk_scoring.py:RISK_LEVEL_THRESHOLDS)
score >= 80  → "very_low"     # Très robuste
score >= 65  → "low"          # Robuste
score >= 50  → "medium"       # Modéré
score >= 35  → "high"         # Fragile
score >= 20  → "very_high"    # Très fragile
score < 20   → "critical"     # Critique
```

**⚠️ CRITIQUE** : Ce mapping est **inversé** car score = robustesse (score élevé = risque faible).

### 📝 Formule Risk Score (Quantitatif - Autoritaire)

```python
score = 50.0  # Baseline neutre

# VaR impact (VaR ↑ → robustesse ↓ → score ↓)
if var_95 > 0.25:  score -= 30
elif var_95 < 0.05: score += 10

# Sharpe impact (Sharpe ↑ → robustesse ↑ → score ↑)
if sharpe > 2.0:   score += 20
elif sharpe < 0:   score -= 15

# Drawdown impact (DD ↑ → robustesse ↓ → score ↓)
if |dd| > 0.50:    score -= 25
elif |dd| < 0.10:  score += 10

# Volatility impact (Vol ↑ → robustesse ↓ → score ↓)
if vol > 1.0:      score -= 10
elif vol < 0.20:   score += 10

score = clamp(score, 0, 100)
level = score_to_level(score)
```

### 🏗️ Formule Risk Score Structural

**Base** : `risk_score` (autoritaire)

**Ajustements structurels** :
- **GRI (Group Risk Index)** : Exposition pondérée par risque de groupe (0-10)
- **Concentration** : Top5 holdings, HHI (Herfindahl-Hirschman Index)
- **Structure** : % Stablecoins, diversification ratio

**Exemple** : Portfolio BTC-heavy (43%)
- Risk Score : 65 (robuste historiquement)
- Risk Structural : 37 (pénalisé pour concentration)

### 📊 Metadata Audit & Traçabilité

**Réponse API** (`/api/risk/dashboard`) :
```json
{
  "risk_metrics": {
    "risk_score": 65.0,
    "risk_score_structural": 37.0,
    "structural_breakdown": {
      "var_95": -8.0,
      "sharpe": 10.0,
      "drawdown": 5.0,
      "volatility": 5.0,
      "stables": -2.0,
      "concentration": 3.0,
      "gri": 6.0
    },
    "window_used": {
      "price_history_days": 365,
      "lookback_days": 90,
      "actual_data_points": 55
    }
  }
}
```

### 🧪 Tests Non-Régression

**Fichier** : [`tests/unit/test_risk_scoring.py`](../tests/unit/test_risk_scoring.py)

**Couvre** :
- Mapping score→level (85→very_low, 40→high, etc.)
- Sémantique Option A (VaR ↑ → score ↓, Sharpe ↑ → score ↑)
- Breakdown contributions (sum validation)
- Clamping [0, 100]

---

## QA Checklist (Étendue)

- [ ] Aucun `100 - scoreRisk` dans le code ni dans les docs
- [ ] Contribution Risk cohérente avec son poids configuré
- [ ] Visualisations et agrégations vérifiées côté UI et backend
- [ ] **NOUVEAU** : Aucune duplication de logique scoring (import depuis `risk_scoring.py` uniquement)
- [ ] **NOUVEAU** : Endpoint n'override PAS le `overall_risk_level` du service (pas de re-mapping)
- [ ] **NOUVEAU** : Tests non-régression passent (`pytest tests/unit/test_risk_scoring.py`)
- [ ] **NOUVEAU** : API expose `structural_breakdown` et `window_used` pour audit
