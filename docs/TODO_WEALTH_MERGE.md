# TODO — Migration Wealth (Bourse/Banques) — Roadmap

But : unifier Bourse/Banques avec Crypto, tout en conservant des **vues dédiées** par classe d'actifs (analytics / risk / rebalance).

## État actuel (résumé)
- Crypto : OK (analytics-unified, risk-dashboard, rebalance)
- Bourse : pages dédiées `saxo-upload.html` + `saxo-dashboard.html`, endpoints `/api/saxo/*`
- Banques : non intégré
- Wealth (`/api/wealth/*`) : amorcé dans certaines branches, **non** voie par défaut

## Étapes recommandées

### 1) Contrats communs (Backend)
- [ ] Créer `models/wealth.py` : `AccountModel`, `InstrumentModel`, `PositionModel`, `PricePoint`, `ProposedTrade`
- [ ] Adapter `adapters/saxo_adapter.py` pour retourner ces modèles (EQUITY/ETF avec `meta.isin/exchange`)
- [ ] (Optionnel) `adapters/banks_adapter.py` (CASH/flux)

### 2) Endpoints Wealth
- [ ] `GET /api/wealth/modules`
- [ ] `GET /api/wealth/{module}/accounts|instruments|positions|prices`
- [ ] `POST /api/wealth/{module}/rebalance/preview`
- [ ] Fallback P&L Today = 0 si `prev_close` indisponible (alignement Crypto)

### 3) Frontend unifié (nouvelles pages bourse)
- [ ] `static/analytics-equities.html`
- [ ] `static/risk-equities.html`
- [ ] `static/rebalance-equities.html`
- [ ] `static/stores/wealth-store.js` (sélecteurs par module)
- [ ] `dashboard.html` : tuiles Crypto/Bourse/Banques (valeur, P&L Today, nb positions)

### 4) Settings / Imports
- [ ] Intégrer l'upload Saxo dans `settings.html` (remplacer `saxo-upload.html`)
- [ ] Indiquer la dernière importation, #positions, as-of

### 5) Nettoyage & transitions
- [ ] Déplacer `saxo-dashboard.html` hors menu (garder accessible le temps de la migration)
- [ ] Rediriger vers `analytics-equities.html` quand prête

### 6) Tests & scripts
- [ ] Smoke Wealth : `GET /api/wealth/modules` (attend `"saxo"` si snapshot présent)
- [ ] `GET /api/wealth/saxo/positions` retourne >0 positions
- [ ] `POST /api/wealth/saxo/rebalance/preview` renvoie une liste (même vide)

## Notes d'implémentation
- Timezone : Europe/Zurich pour les calculs "Today"
- Pricing : Crypto via CoinGecko; Bourse via snapshot + provider secondaire si besoin
- FX : normaliser l'affichage en devise de base (étape ultérieure)