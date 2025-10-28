# Market Opportunities System

> **Date:** October 2025
> **Status:** Production
> **Module:** ML Bourse - Market Opportunities
> **Author:** Crypto Rebalancer Team

## Vue d'ensemble

Le **Market Opportunities System** identifie automatiquement des opportunités d'investissement **en dehors du portefeuille actuel**, en analysant les gaps sectoriels et en suggérant des réallocations intelligentes.

**Objectifs:**
- Détecter les secteurs sous-représentés ou manquants
- Identifier les meilleures opportunités d'achat (actions + ETFs)
- Suggérer des ventes intelligentes pour financer les opportunités
- Simuler l'impact de la réallocation sur le risque et la diversification

**Différence avec Recommendations Tab:**
- **Recommendations Tab**: Analyse positions existantes (BUY/HOLD/SELL)
- **Market Opportunities Tab**: Identifie nouvelles opportunités hors portfolio

---

## Architecture

### Backend Components

```
services/ml/bourse/
├── opportunity_scanner.py       # Scan secteurs S&P 500 vs portfolio
├── sector_analyzer.py           # Analyse momentum/value/diversification
└── portfolio_gap_detector.py    # Suggestions ventes intelligentes
```

### Frontend UI

```
static/saxo-dashboard.html
└── Onglet "Market Opportunities"
    ├── Portfolio Gaps (Cards secteurs manquants)
    ├── Top Opportunities (Tableau triable)
    ├── Suggested Sales (Suggestions ventes)
    └── Impact Simulator (Allocation avant/après)
```

### API Endpoint

```
GET /api/bourse/opportunities
    ?user_id=<user>
    &horizon=<short|medium|long>
    &file_key=<optional>
    &min_gap_pct=<float>
```

---

## Méthodologie de Scoring

### 3-Pillar Scoring System

Chaque gap sectoriel est scoré sur une échelle 0-100 selon 3 piliers:

#### 1. Momentum Score (40%)

**Indicateurs:**
- Price momentum 3M/6M (rendements récents)
- RSI (14-day) - Détection surachat/survente
- Relative strength vs SPY (performance relative)

**Formule:**
```python
momentum_score = (
    price_momentum_score * 0.35 +
    rsi_score * 0.35 +
    relative_strength_score * 0.30
)
```

**Interprétation:**
- **>70**: Momentum fort (secteur en tendance haussière)
- **50-70**: Momentum modéré
- **<50**: Momentum faible (attendre meilleur timing)

#### 2. Value Score (30%)

**Indicateurs:**
- P/E Ratio (valorisation vs moyenne marché)
- PEG Ratio (croissance ajustée, si disponible)
- Dividend Yield (rendement dividendes)

**Formule:**
```python
value_score = (
    pe_score * 0.40 +
    peg_score * 0.35 +
    div_yield_score * 0.25
)
```

**Interprétation:**
- **>70**: Secteur sous-évalué (bon point d'entrée)
- **50-70**: Valorisation neutre
- **<50**: Secteur surévalué (attendre correction)

#### 3. Diversification Score (30%)

**Indicateurs:**
- Corrélation avec positions existantes
- Volatilité relative
- Exposition sectorielle manquante

**Formule:**
```python
diversification_score = (
    correlation_score * 0.50 +
    volatility_score * 0.30 +
    sector_exposure_score * 0.20
)
```

**Interprétation:**
- **>70**: Excellente diversification (faible corrélation)
- **50-70**: Diversification modérée
- **<50**: Faible diversification (redondant avec positions)

### Composite Opportunity Score

```python
opportunity_score = (
    momentum_score * 0.40 +
    value_score * 0.30 +
    diversification_score * 0.30
)
```

**Seuils décision:**
- **≥75**: Opportunité exceptionnelle (strong buy)
- **60-75**: Opportunité solide (buy)
- **50-60**: Opportunité acceptable (considérer)
- **<50**: Opportunité faible (éviter)

---

## Secteurs Standard (GICS Level 1)

Le système utilise les 11 secteurs GICS standard du S&P 500:

| Secteur | Range Cible | ETF Proxy | Description |
|---------|-------------|-----------|-------------|
| **Technology** | 15-30% | XLK | Information Technology |
| **Healthcare** | 10-18% | XLV | Healthcare |
| **Financials** | 10-18% | XLF | Financial Services |
| **Consumer Discretionary** | 8-15% | XLY | Consumer Cyclical |
| **Communication Services** | 8-15% | XLC | Communication Services |
| **Industrials** | 8-15% | XLI | Industrials |
| **Consumer Staples** | 5-12% | XLP | Consumer Defensive |
| **Energy** | 3-10% | XLE | Energy |
| **Utilities** | 2-8% | XLU | Utilities |
| **Real Estate** | 2-8% | XLRE | Real Estate / REITs |
| **Materials** | 2-8% | XLB | Materials |

**Note:** Les secteurs Yahoo Finance sont mappés automatiquement aux secteurs GICS standard.

---

## Horizons Temporels

### Short-term (1-3 mois)

**Objectif:** Tactical plays, rotations sectorielles courtes

**Pondérations scoring:**
- Momentum: 50% (priorité tendance court terme)
- Value: 20%
- Diversification: 30%

**Recommandations:**
- ETFs sectoriels (liquidité élevée)
- Pas d'actions individuelles (trop volatiles)

### Mid-term (6-12 mois)

**Objectif:** Thématiques sectorielles, positionnement stratégique

**Pondérations scoring:**
- Momentum: 40% (équilibré)
- Value: 30%
- Diversification: 30%

**Recommandations:**
- Mix ETFs + actions solides (large caps)
- Secteurs en tendance structurelle

### Long-term (2-3 ans)

**Objectif:** Mégatrends, allocation stratégique durable

**Pondérations scoring:**
- Momentum: 30%
- Value: 40% (priorité valorisation long terme)
- Diversification: 30%

**Recommandations:**
- Actions quality (large caps stables)
- ETFs diversifiés
- Focus dividendes et croissance durable

---

## Contraintes de Réallocation

### Protection Portfolio (Hard Limits)

| Contrainte | Valeur | Rationale |
|------------|--------|-----------|
| **Max vente par position** | 30% | Évite liquidation forcée |
| **Top N holdings protégés** | 3 | Préserve colonne vertébrale portfolio |
| **Détention minimale** | 30 jours | Évite wash sales, frais transaction |
| **Max allocation par secteur** | 25% | Diversification obligatoire |
| **Protection stop loss** | Validation | Respect trailing stops existants |

### Logique de Détection des Ventes

**Critères prioritaires:**

1. **Over-concentration (>15% portfolio)**
   - Score: +50 points si >15%
   - Rationale: "Over-concentrated (X% of portfolio)"

2. **Weak momentum (3M return <-10%)**
   - Score: +50 points si <-10%
   - Rationale: "Weak momentum (-X% 3M)"

3. **Negative return (<0%)**
   - Score: +20 points
   - Rationale: "Negative momentum (-X% 3M)"

4. **Near stop loss (-10% to -5%)**
   - Score: ×0.5 (réduction score vente)
   - Rationale: "Near stop loss (reduce caution)"

**Exclusions:**
- Top 3 holdings (jamais vendus)
- Positions <30 jours (trop récentes)
- Positions protégées par stop loss

---

## API Reference

### Endpoint Principal

```http
GET /api/bourse/opportunities
```

**Query Parameters:**

| Paramètre | Type | Requis | Default | Description |
|-----------|------|--------|---------|-------------|
| `user_id` | string | ✅ | - | User ID (multi-tenant) |
| `horizon` | string | ❌ | `"medium"` | Time horizon: `short`/`medium`/`long` |
| `file_key` | string | ❌ | `null` | Saxo CSV file key (optional) |
| `min_gap_pct` | float | ❌ | `5.0` | Minimum gap percentage (0-50) |

**Response Format:**

```json
{
  "gaps": [
    {
      "sector": "Utilities",
      "current_pct": 0.0,
      "target_pct": 12.0,
      "gap_pct": 12.0,
      "etf": "XLU",
      "score": 87.3,
      "confidence": 0.85,
      "momentum_score": 82.0,
      "value_score": 91.0,
      "diversification_score": 89.0
    }
  ],
  "opportunities": [
    {
      "symbol": "XLU",
      "name": "Utilities Select Sector SPDR",
      "sector": "Utilities",
      "type": "ETF",
      "score": 87.3,
      "confidence": 0.85,
      "action": "BUY",
      "horizon": "medium",
      "capital_needed": 12000.0,
      "rationale": "Utilities sector gap: 12.0% underweight"
    }
  ],
  "suggested_sales": [
    {
      "symbol": "NVDA",
      "current_value": 25000.0,
      "sale_pct": 30.0,
      "sale_value": 7500.0,
      "rationale": "Over-concentrated (25.0% of portfolio)",
      "stop_loss_safe": true
    }
  ],
  "impact": {
    "before": {
      "Technology": 52.0,
      "Healthcare": 10.0,
      "Utilities": 0.0
    },
    "after": {
      "Technology": 38.0,
      "Healthcare": 10.0,
      "Utilities": 12.0
    },
    "risk_before": 7.2,
    "risk_after": 6.4,
    "total_freed": 15000.0,
    "total_invested": 12000.0
  },
  "summary": {
    "total_gaps": 3,
    "total_opportunities": 5,
    "total_sales": 2,
    "capital_needed": 12000.0,
    "capital_freed": 15000.0,
    "sufficient_capital": true
  },
  "horizon": "medium",
  "generated_at": "2025-10-28T14:30:00Z"
}
```

---

## Frontend UI Guide

### Onglet "Market Opportunities"

**Accès:** Dashboard Bourse → Tab "Market Opportunities"

### 1. Horizon Selector

```
┌─────────────────────────────────────────────────┐
│ Investment Horizon                              │
│ [1-3 Months] [6-12 Months (✓)] [2-3 Years]     │
│ [🔍 Scan for Opportunities]                     │
└─────────────────────────────────────────────────┘
```

**Actions:**
- Sélectionner horizon → Adapte scoring
- Cliquer "Scan" → Lance analyse complète

### 2. Portfolio Gaps (Cards)

```
┌────────────┐ ┌────────────┐ ┌────────────┐
│ Utilities  │ │ Financials │ │ Real Estate│
│ Score: 87  │ │ Score: 78  │ │ Score: 72  │
│ 0% → 12%   │ │ 0% → 8%    │ │ 0% → 5%    │
│ Gap: 12%   │ │ Gap: 8%    │ │ Gap: 5%    │
│ ETF: XLU   │ │ ETF: XLF   │ │ ETF: XLRE  │
└────────────┘ └────────────┘ └────────────┘
```

**Interprétation:**
- **Score >70** (vert): Opportunité forte
- **Score 50-70** (orange): Opportunité modérée
- **Score <50** (gris): Opportunité faible

### 3. Top Opportunities (Table)

| Symbol | Sector | Score | Type | Capital Needed | Rationale |
|--------|--------|-------|------|----------------|-----------|
| XLU | Utilities | 87 | ETF | €12,000 | Utilities sector gap: 12.0% underweight |
| XLF | Financials | 78 | ETF | €8,000 | Financials sector gap: 8.0% underweight |

**Actions:**
- Tri par colonne (Symbol, Score, Capital)
- Top 10 opportunités affichées

### 4. Suggested Sales (Table)

| Symbol | Current Value | Sell % | Frees | Rationale |
|--------|---------------|--------|-------|-----------|
| NVDA | €25,000 | 30% | +€7,500 | Over-concentrated (25.0% of portfolio) |
| META | €10,000 | 50% | +€5,000 | High valuation, weak momentum |

**Actions:**
- Visualisation des positions à réduire
- Capital libéré pour financer opportunités

### 5. Impact Simulator

```
┌──────────────────────────────────────────────────┐
│ Risk Score: 7.2 → 6.4                            │
│ Capital Freed: €15,000                           │
│ Capital Invested: €12,000                        │
├──────────────────────────────────────────────────┤
│ Sector Allocation Changes                        │
│ Technology:  52% → 38% (-14%)                    │
│ Utilities:    0% → 12% (+12%)                    │
│ Financials:   0% → 8% (+8%)                      │
└──────────────────────────────────────────────────┘
```

**Interprétation:**
- Avant/Après allocation sectorielle
- Impact sur risk score
- Capital net libéré

---

## Exemples d'utilisation

### Cas 1: Portfolio Tech-Heavy

**Situation:**
- Tech: 52% (over-concentration)
- Utilities: 0%
- Financials: 0%
- Real Estate: 0%

**Action:**
```javascript
// User: Clic "Scan Opportunities" (horizon: medium 6-12M)
```

**Résultat:**
- **3 gaps détectés:** Utilities, Financials, Real Estate
- **Top opportunity:** XLU (Utilities ETF) - Score 87
- **Suggested sale:** NVDA 30% → Libère €8,000
- **Impact:** Tech 52% → 38%, Utilities 0% → 12%, Risk 7.2 → 6.4

### Cas 2: Portfolio Bien Diversifié

**Situation:**
- Allocation équilibrée sur 8 secteurs
- Aucun gap >5%

**Action:**
```javascript
// User: Clic "Scan Opportunities"
```

**Résultat:**
```
No significant sector gaps detected. Portfolio is well-diversified!
```

### Cas 3: Portfolio Sans Liquidité

**Situation:**
- Gaps détectés: Utilities (12%), Financials (8%)
- Aucune position sur-concentrée
- Top 3 holdings protégés

**Action:**
```javascript
// User: Clic "Scan Opportunities"
```

**Résultat:**
- Opportunités identifiées
- **Suggested sales:** Vide (aucune position éligible)
- Message: "No sales needed. Portfolio has sufficient liquidity..."

---

## Maintenance & Evolution

### P0 (Implémenté)

✅ Scan secteurs S&P 500 vs portfolio
✅ Scoring 3-pillar (Momentum/Value/Diversification)
✅ Suggestions ventes intelligentes (max 30%, top 3 protected)
✅ Impact simulator (avant/après allocation)
✅ Frontend UI complet (onglet dédié)

### P1 (Q1 2026)

- [ ] Top 3 stocks par secteur (pas seulement ETF)
- [ ] Backtesting suggestions (track performance)
- [ ] Alertes auto quand nouveaux gaps (>10%)
- [ ] Intégration module execution (buy/sell orders)

### P2 (Q2 2026)

- [ ] ML pour affiner scoring (historical winners)
- [ ] Corrélation cross-asset (bourse + crypto)
- [ ] Simulation Monte Carlo (scénarios multiples)
- [ ] Export rapport PDF (comme Recommendations)

---

## Troubleshooting

### Problème: Aucun gap détecté

**Cause:** Portfolio déjà bien diversifié ou `min_gap_pct` trop élevé

**Solution:**
```javascript
// Réduire le seuil min_gap_pct
const url = `/api/bourse/opportunities?user_id=jack&min_gap_pct=2.0`;
```

### Problème: Erreur "No positions found"

**Cause:** Fichier Saxo CSV non chargé ou user_id incorrect

**Solution:**
1. Vérifier que Saxo CSV est uploadé
2. Vérifier `localStorage.getItem('activeUser')`
3. Vérifier `file_key` dans URL

### Problème: Scores tous à 50

**Cause:** Données Yahoo Finance indisponibles (rate limit ou symbole invalide)

**Solution:**
- Attendre quelques minutes (rate limit Yahoo Finance)
- Vérifier logs backend: `logs/app.log`
- Vérifier que ETF proxy est valide (XLU, XLF, etc.)

### Problème: Suggested sales vide malgré gaps

**Cause:** Aucune position éligible (toutes protégées ou récentes <30j)

**Solution:**
- Normal si top 3 holdings représentent >80% portfolio
- Vérifier dates d'acquisition des positions
- Réduire protection (modifier `TOP_N_PROTECTED` dans code)

---

## Dépendances

### Backend

```python
# services/ml/bourse/opportunity_scanner.py
from services.ml.bourse.sector_analyzer import SectorAnalyzer

# services/ml/bourse/sector_analyzer.py
from services.ml/bourse.data_sources import StocksDataSource
from services.ml.bourse.technical_indicators import TechnicalIndicators
import yfinance as yf  # Free Yahoo Finance API

# services/ml/bourse/portfolio_gap_detector.py
from services.ml.bourse.stop_loss_calculator import StopLossCalculator
```

### Frontend

```javascript
// Dépendances globales
window.API_BASE_URL  // Config API
window.safeFetch()   // HTTP wrapper
localStorage.getItem('activeUser')  // Multi-user
formatCurrency()     // Formatage devises
```

---

## Sources de Données

### Yahoo Finance (yfinance)

**Utilisé pour:**
- Prix OHLCV (ETFs sectoriels)
- Fundamental data (P/E, PEG, Dividend Yield)
- Benchmarks (SPY)

**Limites:**
- Rate limit: ~2000 requests/hour
- Délai données: 15 min (free tier)
- Pas de top holdings ETF (future P1)

**Fallback:**
- Cache local (TTL 4h pour secteurs)
- Scores neutres (50) si données manquantes

### S&P 500 Secteurs (Static)

**Configuration:**
- 11 secteurs GICS Level 1
- Targets ranges basés sur composition S&P 500
- ETF proxy par secteur (XLK, XLV, etc.)

**Mise à jour:**
- Annuelle (composition secteurs S&P change peu)
- Fichier: `opportunity_scanner.py` → `STANDARD_SECTORS`

---

## Sécurité & Permissions

### Multi-Tenant Isolation

```python
# Backend: TOUJOURS user_id dans query
@router.get("/api/bourse/opportunities")
async def get_market_opportunities(
    user_id: str = Query(..., description="User ID")  # Required!
):
    # ...
```

```javascript
// Frontend: TOUJOURS activeUser
const activeUser = localStorage.getItem('activeUser') || 'demo';
const url = `/api/bourse/opportunities?user_id=${activeUser}`;
```

### Data Privacy

- **Pas de logs positions** (seulement agrégats)
- **Pas de sharing inter-users**
- **Cache isolé par user**

---

## Performance

### Backend

**Optimisations:**
- Cache Yahoo Finance data (4h TTL)
- Async/await pour paralléliser fetches
- Limit top 10 opportunities (pas tout S&P 500)

**Latence moyenne:**
- Cold start (no cache): ~8-12s
- Warm cache: ~2-3s

### Frontend

**Optimisations:**
- Lazy loading onglet (charge au clic)
- Pas de refresh auto (user trigger manual)
- Render incrémental (gaps → opportunities → sales → impact)

**UX:**
- Loading states pendant scan
- Feedback immédiat (bouton "Scanning...")
- Success message ("✅ Scan Complete")

---

## Logs & Debugging

### Backend Logs

```bash
# Lire logs scan opportunities
Get-Content logs\app.log -Wait -Tail 50 | Select-String "Market opportunities"

# Logs typiques
# INFO: 🔍 Market opportunities requested (user=jack, horizon=medium)
# INFO: Detected 3 sector gaps
# INFO: ✅ Scan complete: 3 gaps scored, top 3 selected
```

### Frontend Debug

```javascript
// Console logs (si debugLogger enabled)
debugLogger.info('Loading market opportunities (horizon: medium)');
debugLogger.info('Market opportunities loaded:', data);

// Inspect last data
console.log(lastOpportunitiesData);
```

---

## Changelog

### v1.0 (October 2025)

- ✅ Initial release
- ✅ 3-pillar scoring system
- ✅ Intelligent sales suggestions
- ✅ Impact simulator
- ✅ Full UI integration

---

*Documentation générée pour Market Opportunities System - Crypto Rebalancer*
*Pour questions: Voir CLAUDE.md section "Features Avancées"*
