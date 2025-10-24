# Stop Loss Frontend Implementation Guide

> **Backend :** ✅ Complété (Fixed Variable implemented)
> **Frontend :** ⏳ À Implémenter
> **Target File:** `static/saxo-dashboard.html`
> **Temps Estimé:** 1-2h

---

## 🎯 Objectif

Remplacer l'actuel stop loss "Fixed 5% partout" par "Fixed Variable (4-6-8%) selon volatilité".

---

## 📊 Changements Requis

### 1. Ajouter Calcul Volatilité

```javascript
/**
 * Calculate annualized volatility from historical price data
 *
 * @param {Array} historicalData - Array of OHLC objects with 'close' property
 * @returns {number} Annualized volatility (e.g., 0.45 for 45%)
 */
function calculateVolatility(historicalData) {
    if (!historicalData || historicalData.length < 30) {
        return 0.30;  // Default to moderate volatility
    }

    // Calculate daily returns
    const returns = [];
    for (let i = 1; i < historicalData.length; i++) {
        const prevClose = historicalData[i-1].close;
        const currClose = historicalData[i].close;

        if (prevClose > 0) {
            returns.push(Math.log(currClose / prevClose));
        }
    }

    if (returns.length < 20) {
        return 0.30;  // Default
    }

    // Calculate standard deviation
    const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
    const stdDev = Math.sqrt(variance);

    // Annualize (252 trading days)
    const annualVol = stdDev * Math.sqrt(252);

    return annualVol;
}
```

### 2. Mapper Volatilité → Stop %

```javascript
/**
 * Get stop loss percentage based on volatility bucket
 *
 * @param {number} volatility - Annualized volatility (0-1)
 * @returns {object} { stopPct, bucket, reasoning }
 */
function getStopLossByVolatility(volatility) {
    let stopPct, bucket, reasoning;

    if (volatility > 0.40) {
        // High volatility (NVDA, TSLA, crypto)
        stopPct = 0.08;
        bucket = "high";
        reasoning = `8% stop for high volatility (${(volatility*100).toFixed(0)}% annual)`;
    } else if (volatility > 0.25) {
        // Moderate volatility (AAPL, MSFT, most stocks)
        stopPct = 0.06;
        bucket = "moderate";
        reasoning = `6% stop for moderate volatility (${(volatility*100).toFixed(0)}% annual)`;
    } else {
        // Low volatility (KO, SPY, defensive/ETFs)
        stopPct = 0.04;
        bucket = "low";
        reasoning = `4% stop for low volatility (${(volatility*100).toFixed(0)}% annual)`;
    }

    return {
        stopPct,
        bucket,
        volatility,
        reasoning
    };
}
```

### 3. Intégrer dans Recommendations

```javascript
// Dans la fonction qui génère les recommendations
async function generateRecommendations(positions) {
    for (const position of positions) {
        const symbol = position.symbol;
        const currentPrice = position.current_price;

        // Fetch historical data (90 days minimum)
        const historicalData = await fetchHistoricalData(symbol, 90);

        // Calculate volatility
        const volatility = calculateVolatility(historicalData);

        // Get adaptive stop loss
        const stopLossInfo = getStopLossByVolatility(volatility);

        // Calculate stop price
        const stopLossPrice = currentPrice * (1 - stopLossInfo.stopPct);

        // Add to recommendation
        position.stopLoss = {
            price: stopLossPrice.toFixed(2),
            percentage: (stopLossInfo.stopPct * 100).toFixed(1),
            distance: ((stopLossPrice - currentPrice) / currentPrice * 100).toFixed(1),
            volatility: (volatility * 100).toFixed(1),
            bucket: stopLossInfo.bucket,
            reasoning: stopLossInfo.reasoning,
            method: "Fixed Variable (Recommended)"
        };
    }

    return positions;
}
```

---

## 🎨 Affichage UI (Suggestions)

### Badge Volatilité

```javascript
function renderVolatilityBadge(bucket) {
    const colors = {
        high: '#ef4444',      // Rouge
        moderate: '#f59e0b',  // Orange
        low: '#22c55e'        // Vert
    };

    const labels = {
        high: 'High Vol',
        moderate: 'Moderate Vol',
        low: 'Low Vol'
    };

    return `<span style="
        background: ${colors[bucket]}15;
        color: ${colors[bucket]};
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    ">${labels[bucket]}</span>`;
}
```

### Colonne Stop Loss (Tableau)

```html
<td>
    <!-- Stop Loss Price -->
    <div style="font-weight: 600; color: #ef4444;">
        $${recommendation.stopLoss.price}
    </div>

    <!-- Stop % + Volatility Badge -->
    <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">
        ${recommendation.stopLoss.percentage}% stop
        ${renderVolatilityBadge(recommendation.stopLoss.bucket)}
    </div>

    <!-- Reasoning (Tooltip) -->
    <div style="font-size: 11px; color: #9ca3af; margin-top: 2px;" title="${recommendation.stopLoss.reasoning}">
        ${recommendation.stopLoss.reasoning}
    </div>
</td>
```

### Modal Détails

```html
<!-- Dans le modal de recommendation -->
<div class="stop-loss-section">
    <h3>🛡️ Stop Loss (Adaptive)</h3>

    <div class="stop-loss-card">
        <!-- Price -->
        <div class="sl-row">
            <span class="sl-label">Stop Price:</span>
            <span class="sl-value">${recommendation.stopLoss.price}</span>
        </div>

        <!-- Percentage -->
        <div class="sl-row">
            <span class="sl-label">Stop %:</span>
            <span class="sl-value">${recommendation.stopLoss.percentage}%</span>
        </div>

        <!-- Volatility -->
        <div class="sl-row">
            <span class="sl-label">Volatility:</span>
            <span class="sl-value">
                ${recommendation.stopLoss.volatility}% annual
                ${renderVolatilityBadge(recommendation.stopLoss.bucket)}
            </span>
        </div>

        <!-- Max Loss -->
        <div class="sl-row">
            <span class="sl-label">Max Loss:</span>
            <span class="sl-value" style="color: #ef4444;">
                ${recommendation.stopLoss.distance}%
                (€${(position.size * parseFloat(recommendation.stopLoss.distance) / 100).toFixed(0)})
            </span>
        </div>

        <!-- Reasoning -->
        <div class="sl-reasoning">
            ℹ️ ${recommendation.stopLoss.reasoning}
        </div>
    </div>
</div>

<style>
.stop-loss-card {
    background: #f9fafb;
    padding: 16px;
    border-radius: 8px;
    border-left: 4px solid #ef4444;
}

.sl-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #e5e7eb;
}

.sl-row:last-child {
    border-bottom: none;
}

.sl-label {
    color: #6b7280;
    font-size: 14px;
}

.sl-value {
    font-weight: 600;
    color: #1f2937;
    font-size: 14px;
}

.sl-reasoning {
    margin-top: 12px;
    padding: 12px;
    background: white;
    border-radius: 6px;
    font-size: 13px;
    color: #6b7280;
}
</style>
```

---

## 🔧 Intégration Backend

Le backend retourne déjà Fixed Variable via l'API :

```python
# /api/ml/bourse/recommendations
{
    "symbol": "NVDA",
    "current_price": 182.16,
    "price_targets": {
        "stop_loss": 167.43,  # Calculé avec Fixed Variable
        "stop_loss_analysis": {
            "recommended_method": "fixed_variable",
            "stop_loss_levels": {
                "fixed_variable": {
                    "price": 167.43,
                    "percentage": 0.08,  # 8% pour high vol
                    "volatility_bucket": "high",
                    "annual_volatility": 0.45,
                    "reasoning": "8% stop for high volatility (45% annual)",
                    "quality": "high"
                },
                "atr_2x": { ... },  # Autres méthodes pour référence
                "fixed_pct": { ... }
            }
        }
    }
}
```

**Frontend doit juste utiliser :**
```javascript
const stopLossInfo = recommendation.price_targets.stop_loss_analysis.stop_loss_levels.fixed_variable;
```

---

## ✅ Checklist Implémentation

### Étape 1 : Ajouter Helpers (15 min)
- [ ] Copier `calculateVolatility()` dans saxo-dashboard.html
- [ ] Copier `getStopLossByVolatility()` dans saxo-dashboard.html
- [ ] Copier `renderVolatilityBadge()` dans saxo-dashboard.html

### Étape 2 : Modifier generateRecommendations() (30 min)
- [ ] Ajouter appel `calculateVolatility(historicalData)`
- [ ] Remplacer `stopLoss = price * 0.95` par `getStopLossByVolatility(vol)`
- [ ] Enrichir objet `position.stopLoss` avec infos volatilité

### Étape 3 : Mettre à Jour UI (30 min)
- [ ] Ajouter badge volatilité dans colonne Stop Loss
- [ ] Afficher stop % adaptatif au lieu de "5%"
- [ ] Ajouter section détaillée dans modal

### Étape 4 : Tester (15 min)
- [ ] Vérifier NVDA → Stop 8% (high vol)
- [ ] Vérifier AAPL → Stop 6% (moderate vol)
- [ ] Vérifier SPY → Stop 4% (low vol)
- [ ] Vérifier calcul perte max en €

---

## 🧪 Test Cases

### Test 1 : NVDA (High Vol)

```javascript
// Input
const nvda = {
    symbol: "NVDA",
    current_price: 182.16,
    historical_data: [...] // 90 jours, vol ~45%
};

// Expected Output
{
    stopLoss: {
        price: "167.59",      // 182.16 * 0.92
        percentage: "8.0",
        distance: "-8.0",
        volatility: "45.0",
        bucket: "high",
        reasoning: "8% stop for high volatility (45% annual)"
    }
}
```

### Test 2 : SPY (Low Vol)

```javascript
// Input
const spy = {
    symbol: "SPY",
    current_price: 575.00,
    historical_data: [...] // 90 jours, vol ~18%
};

// Expected Output
{
    stopLoss: {
        price: "552.00",      // 575 * 0.96
        percentage: "4.0",
        distance: "-4.0",
        volatility: "18.0",
        bucket: "low",
        reasoning: "4% stop for low volatility (18% annual)"
    }
}
```

---

## 📝 Notes Importantes

### Fallback Comportement

Si données historiques insuffisantes (<30 jours) :
```javascript
// Utiliser volatilité par défaut (moderate = 6%)
const volatility = historicalData.length < 30 ? 0.30 : calculateVolatility(historicalData);
```

### Cache Volatilité

Pour performance, cacher volatilité calculée :
```javascript
const volatilityCache = {};

function getVolatilityWithCache(symbol, historicalData) {
    const cacheKey = `${symbol}_${historicalData.length}`;

    if (volatilityCache[cacheKey]) {
        return volatilityCache[cacheKey];
    }

    const vol = calculateVolatility(historicalData);
    volatilityCache[cacheKey] = vol;

    return vol;
}
```

### Affichage Comparaison (Optionnel)

Pour montrer l'amélioration vs Fixed 5% :
```html
<div class="stop-loss-comparison" style="font-size: 12px; color: #6b7280; margin-top: 8px;">
    Old (Fixed 5%): $${(currentPrice * 0.95).toFixed(2)}
    → New (Adaptive): $${stopLoss.price}
    <span style="color: #22c55e;">
        (+${((stopLoss.price - currentPrice * 0.95) / (currentPrice * 0.95) * 100).toFixed(1)}% better)
    </span>
</div>
```

---

## 🎯 Résultat Attendu

**Avant :**
```
NVDA: Stop $172.05 (5%)  ← Trop serré, sorties prématurées
AAPL: Stop $165.73 (5%)  ← Trop serré
SPY:  Stop $546.25 (5%)  ← Trop large
```

**Après :**
```
NVDA: Stop $167.59 (8%) [High Vol] ← Adapté ✅
AAPL: Stop $163.94 (6%) [Moderate Vol] ← Adapté ✅
SPY:  Stop $552.00 (4%) [Low Vol] ← Adapté ✅
```

**Impact:** +8% performance globale validé par backtest

---

## 📚 Références

- **Backend Implementation:** `services/ml/bourse/stop_loss_calculator.py`
- **Backtest Results:** `docs/STOP_LOSS_BACKTEST_RESULTS.md`
- **API Endpoint:** `/api/ml/bourse/recommendations`

---

**Status:** ✅ Backend Done | ⏳ Frontend Pending | 📅 ETA: 1-2h
