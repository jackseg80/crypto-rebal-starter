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

## Dual Window System (Oct 2025) 🆕

### Problème Résolu

**Symptôme** : Portfolio avec cryptos récentes (ex: 55j historique) montre Sharpe -0.29 avec Risk Score 65 (robuste) — incohérence apparente.

**Cause** : Intersection temporelle courte (55j au lieu de 365j demandés) produit des ratios instables et négatifs — mathématiquement correct mais trompeur pour évaluation portfolio.

**Solution** : Système Dual-Window avec 2 vues :

#### 1️⃣ Long-Term Window (Autoritaire)
- **Objectif** : Métriques stables sur historique long
- **Cohorte** : Exclut assets récents, garde ≥80% valeur portfolio
- **Cascade Fallback** :
  - 365j + 80% couverture (priorité)
  - 180j + 70% couverture
  - 120j + 60% couverture
  - 90j + 50% couverture (dernier recours)
- **Garde-fous** : min 5 assets, min 180j historique
- **Usage** : Score autoritaire pour Decision Index et communication

#### 2️⃣ Full Intersection Window (Référence)
- **Objectif** : Vue complète incluant TOUS les assets
- **Période** : Intersection commune minimale (peut être courte)
- **Usage** : Détection divergences, alertes temporelles

### Architecture

**Service** : `services/portfolio_metrics.py:169` - `calculate_dual_window_metrics()`

**Paramètres** :
```python
min_history_days: int = 180      # Jours minimum cohorte LT
min_coverage_pct: float = 0.80   # % valeur minimum (80%)
min_asset_count: int = 5         # Nombre assets minimum
```

**Endpoint** : `/api/risk/dashboard?use_dual_window=true`

**Nouveaux Query Params** :
- `use_dual_window` (bool, défaut=True)
- `min_history_days` (int, défaut=180)
- `min_coverage_pct` (float, défaut=0.80)
- `min_asset_count` (int, défaut=5)

### Réponse API Étendue

```json
{
  "risk_metrics": {
    "risk_score": 65.0,
    "sharpe_ratio": 1.42,
    "window_used": {
      "dual_window_enabled": true,
      "risk_score_source": "long_term"
    },
    "dual_window": {
      "enabled": true,
      "long_term": {
        "available": true,
        "window_days": 365,
        "asset_count": 3,
        "coverage_pct": 0.80,
        "metrics": {
          "sharpe_ratio": 1.42,
          "volatility": 0.32,
          "risk_score": 65.0
        }
      },
      "full_intersection": {
        "window_days": 55,
        "asset_count": 5,
        "metrics": {
          "sharpe_ratio": -0.29,
          "volatility": 0.85,
          "risk_score": 38.0
        }
      },
      "exclusions": {
        "excluded_assets": [{"symbol": "PEPE", "reason": "history_55d_<_365d"}],
        "excluded_value_usd": 20000,
        "excluded_pct": 0.20,
        "included_assets": [...],
        "included_pct": 0.80,
        "target_days": 365,
        "achieved_days": 365,
        "reason": "success"
      }
    }
  }
}
```

### Frontend Display

**Badges Dual-Window** (risk-dashboard.html:4217) :
- 📈 **Long-Term** : Fenêtre + couverture + Sharpe (vert/autoritaire)
- 🔍 **Full Intersection** : Fenêtre + divergence vs LT (rouge si écart > 0.5)
- ⚠️ **Alerte Exclusion** : Si > 20% valeur exclue
- ✓ **Source** : Indique quelle fenêtre est autoritaire

### Tests

**Fichier** : `tests/unit/test_dual_window_metrics.py`

**Couverture** :
- ✅ Cohorte long-term disponible (cas nominal)
- ✅ Cascade fallback (365 → 180j)
- ✅ Aucune cohorte valide (fallback full intersection)
- ✅ Divergence Sharpe entre fenêtres
- ✅ Métadonnées exclusions précises
- ✅ Asset count insuffisant
- ✅ Fenêtres identiques quand tous assets ont historique long

**Commande** :
```bash
pytest tests/unit/test_dual_window_metrics.py -v
```

### Cas d'Usage

#### ✅ Bon Cas : Portfolio Mature
- 5 assets, tous 365j+ historique
- Long-Term = Full Intersection
- Risk Score stable et fiable

#### ⚠️ Attention : Portfolio Mixte
- 3 assets anciens (365j, 80% valeur)
- 2 assets récents (55j, 20% valeur)
- Long-Term exclut récents → score stable
- Full Intersection inclut récents → score instable (alerte)

#### ❌ Limitation : Portfolio Récent
- Tous assets < 90j
- Aucune cohorte long-term
- Fallback full intersection uniquement (warning)

### Fix Bonus : Score Structural

**Corrigé** : `api/risk_endpoints.py:73-84`

**Avant** (❌ Inversé) :
```python
if perf_ratio < 0.5: d_perf = +10  # Mauvais Sharpe augmentait le score
```

**Après** (✅ Correct) :
```python
if perf_ratio < 0:     d_perf = -15  # Négatif diminue score
elif perf_ratio < 0.5: d_perf = -10  # Faible diminue score
elif perf_ratio > 2.0: d_perf = +15  # Excellent augmente score
```

---

## QA Checklist (Étendue)

- [ ] Aucun `100 - scoreRisk` dans le code ni dans les docs
- [ ] Contribution Risk cohérente avec son poids configuré
- [ ] Visualisations et agrégations vérifiées côté UI et backend
- [ ] **NOUVEAU** : Aucune duplication de logique scoring (import depuis `risk_scoring.py` uniquement)
- [ ] **NOUVEAU** : Endpoint n'override PAS le `overall_risk_level` du service (pas de re-mapping)
- [ ] **NOUVEAU** : Tests non-régression passent (`pytest tests/unit/test_risk_scoring.py`)
- [ ] **NOUVEAU** : API expose `structural_breakdown` et `window_used` pour audit
- [ ] **🆕 Dual-Window** : Long-Term window disponible quand possible (≥80% couverture)
- [ ] **🆕 Dual-Window** : Alerte exclusion si > 20% valeur exclue
- [ ] **🆕 Dual-Window** : Tests dual-window passent (`pytest tests/unit/test_dual_window_metrics.py`)
- [ ] **🆕 Score Structural** : Sharpe/Volatility non inversés (bon → +score)
