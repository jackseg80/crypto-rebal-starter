# Backtest Archive - Octobre 2025

> Archive des scripts et résultats du backtest Stop Loss Fixed Variable

## Contexte

**Date :** 24 Octobre 2025
**Durée :** ~6 heures
**Objectif :** Valider quelle méthode de stop loss est la meilleure

## Question initiale

Quelle méthode utiliser : ATR dynamique ou Fixed % ?

## Résultat

**Winner : Fixed Variable (4-6-8%)** ✅

### Performance
```
Fixed Variable:  $105,232  ✅ WINNER (+8.0% vs Fixed 5%)
Fixed 5%:        $ 97,642  (-7.2% vs Fixed Var)
ATR 2x:          $ 41,176  (-60.9% vs Fixed Var)
```

### Assets testés
- MSFT (5 ans) - Blue Chip
- NVDA (1 an) - Tech high vol
- TSLA (1 an) - Tech very high vol
- AAPL (1 an) - Blue Chip
- SPY (1 an) - ETF low vol
- KO (1 an) - Defensive

**Total :** 372 trades simulés

## Fichiers dans cette archive

### Scripts de backtest
- `run_backtest.py` - Test initial 3 assets
- `run_backtest_extended.py` - Test étendu 10 assets
- `run_backtest_fair.py` - Test final 3-way comparison
- `run_backtest_standalone.py` - Test standalone rapide

### Résultats
- `backtest_results.json` - Résultats test initial
- `backtest_results_extended.json` - Résultats 10 assets
- `backtest_results_fair.json` - **Résultats finaux (3-way)**

### Rapports
- `backtest_report.html` - Rapport HTML avec graphiques

## Documentation complète

Voir documentation principale :
- `docs/STOP_LOSS_BACKTEST_RESULTS.md` - Analyse détaillée
- `docs/BACKTEST_5_YEARS_RATIONALE.md` - Méthodologie
- `SESSION_RESUME_STOP_LOSS_2025-10-24.md` - Session complète

## Implémentation

**Backend :**
- `services/ml/bourse/stop_loss_calculator.py` - Fixed Variable implémenté
- `services/ml/bourse/price_targets.py` - TP adaptatifs (Option C)

**Frontend :**
- `static/saxo-dashboard.html` - Display 5 méthodes

## Conclusion

Simple bat complexe : Fixed Variable (3 règles) > ATR (calculs complexes)
