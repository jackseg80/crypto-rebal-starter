# Risk Dashboard — Métriques et Fenêtres de Calcul

Ce document décrit le fonctionnement du Risk Dashboard, les fenêtres d'estimation utilisées par métrique, ainsi que les endpoints et sources de données.

## Sources de données
- Holdings: CoinTracking (CSV prioritaire) avec fallback API; revalorisation locale si `value_usd` manquant.
- Historique de prix: cache local (services/price_history.py) depuis Binance, avec fallbacks Kraken et Bitget; normalisation d’alias (ex: SOL2→SOL, TAO6→TAO).

Scripts utiles:
- Initialisation (365j typiquement): `python scripts/init_price_history.py --days 365 --force --verbose`
- Mise à jour quotidienne (incrémentale): `python scripts/update_price_history.py`

## Endpoint principal
```
GET /api/risk/dashboard?price_history_days=365&lookback_days=90
```
- `price_history_days`: quantité d’historique à charger (permet Calmar/MaxDD longs)
- `lookback_days`: fenêtre pour corrélations (90j par défaut dans l’UI)

Le backend calcule chaque métrique avec une fenêtre dédiée (cycle-aware):

- VaR 95/99 (1D): lookback 30j
- CVaR 95/99 (1D): 60j
- Volatilité (annualisée): 45j
- Sharpe: 90j
- Sortino: 120j
- Max drawdown / Ulcer: 180j
- Calmar: 365j
- Corrélations / Diversification: 90j (sélection fixée dans l’UI)

Note: “(1D)” indique l’horizon de perte (jour), pas le lookback utilisé pour estimer la distribution.

## Frontend
- `static/risk-dashboard.html` appelle `/api/risk/dashboard` et affiche les métriques.
- Le slider de lookback global et le sélecteur de corrélations ont été retirés; l’UI affiche des libellés "lookback" dans les titres de cartes.

## Bonnes pratiques
- Utiliser 30–60j pour évaluer VaR/CVaR et la réactivité tactical.
- Corrélations 90j pour la diversification (60j si marché très nerveux, 120–180j si très stable).
- Pour Calmar/MaxDD, garder 365j/180j pour une borne structurelle.

