# Risk Dashboard — Métriques et Fenêtres de Calcul

Ce document décrit le fonctionnement du Risk Dashboard, les fenêtres d'estimation utilisées par métrique, ainsi que les endpoints et sources de données.

## Sources de données
- Holdings: CoinTracking (CSV prioritaire) avec fallback API; revalorisation locale si `value_usd` manquant.
- Historique de prix: cache local (services/price_history.py) depuis Binance, avec fallbacks Kraken et Bitget; normalisation d'alias (ex: SOL2→SOL, TAO6→TAO).
- **Configuration dynamique**: Utilise `globalConfig` pour sélectionner la source (stub, cointracking, cointracking_api) via `settings.html`.

### Source de vérité centralisée (Settings)
- La liste des sources est centralisée dans `static/global-config.js` via `window.DATA_SOURCES` (+ ordre via `window.DATA_SOURCE_ORDER`).
- Dans `static/settings.html`, l’onglet “Source” et le sélecteur rapide du “Résumé” sont générés dynamiquement à partir de cette liste.
- Groupes affichés: “Sources de démo” (kind: `stub`) et “Sources CoinTracking” (kind: `csv`/`api`).

### ⚠️ Limitation de Couverture
- Seules ~51 cryptos sur 183 possèdent un historique de prix complet
- Les métriques de risque ne couvrent que ~28% du portefeuille en nombre d'assets
- Impact: VaR et corrélations potentiellement sous-estimées pour les cryptos sans historique

Scripts utiles:
- Initialisation (365j typiquement): `python scripts/init_price_history.py --days 365 --force --verbose`
- Mise à jour quotidienne (incrémentale): `python scripts/update_price_history.py`

## Endpoints principaux

### Production
```
GET /api/risk/dashboard?price_history_days=365&lookback_days=90&source=cointracking&min_usd=1.0
```

### Test (avec support source dynamique)
```
GET /api/risk/dashboard?source=cointracking&min_usd=1.0
```

**Paramètres** :
- `source`: Source des données (`cointracking`, `stub`, `cointracking_api`)
- `min_usd`: Seuil minimum en USD pour filtrer les assets
- `price_history_days`: quantité d'historique à charger (permet Calmar/MaxDD longs)
- `lookback_days`: fenêtre pour corrélations (90j par défaut dans l'UI)

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
- `static/risk-dashboard.html` appelle `/api/risk/dashboard` pour les métriques.
- **Configuration dynamique**: Utilise `globalConfig.get('data_source')` pour sélectionner automatiquement la source
- **Cache management**: Vide automatiquement le cache lors du changement de source via `dataSourceChanged` event
- Le slider de lookback global et le sélecteur de corrélations ont été retirés; l'UI affiche des libellés "lookback" dans les titres de cartes.

### Devise d’affichage et conversion
- La devise d’affichage se règle dans `settings.html` (Résumé ou onglet Pricing), partagée via `global-config`.
- Conversion réelle à l’affichage (et non un simple changement de symbole):
  - USD→EUR: `exchangerate.host`
  - USD→BTC: prix Binance `BTCUSDT` (USD→BTC = `1 / BTCUSD`)
- Si le taux n’est pas disponible, l’UI affiche `—` puis se met à jour automatiquement dès réception du taux.
- Formatage: locale `fr-FR`, suffixe “US” supprimé pour USD (affiche seulement `$`).

### Changements récents
- Suppression des métriques hardcodées, remplacées par des appels API réels
- Intégration avec le système de configuration global (`settings.html`)
- Support des sources multiples avec changement à chaud

## Bonnes pratiques
- Utiliser 30–60j pour évaluer VaR/CVaR et la réactivité tactical.
- Corrélations 90j pour la diversification (60j si marché très nerveux, 120–180j si très stable).
- Pour Calmar/MaxDD, garder 365j/180j pour une borne structurelle.
