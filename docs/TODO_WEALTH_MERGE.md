# TODO — Migration Wealth (Bourse/Banques) — Roadmap

But : unifier Bourse/Banques avec Crypto, tout en conservant des **vues dédiées** par classe d'actifs (analytics / risk / rebalance).

## État actuel (Phase 2 complétée - Sept 2025)
- Crypto : OK (analytics-unified, risk-dashboard, rebalance)
- Bourse : **🏦 Phase 2 terminée** - Tuile Dashboard + Upload Settings + pages dédiées stables
- Banques : non intégré
- Wealth (`/api/wealth/*`) : endpoints disponibles, modèles créés, lecture legacy active

## Phase 2 Accomplie ✅

### 1) Contrats communs (Backend)
- [x] Créer `models/wealth.py` : `AccountModel`, `InstrumentModel`, `PositionModel`, `PricePoint`, `ProposedTrade`
- [x] Adapter `adapters/saxo_adapter.py` pour retourner ces modèles (EQUITY/ETF avec `meta.isin/exchange`)
- [ ] (Optionnel) `adapters/banks_adapter.py` (CASH/flux)

### 2) Endpoints Wealth
- [x] `GET /api/wealth/modules`
- [x] `GET /api/wealth/{module}/accounts|instruments|positions|prices`
- [x] `POST /api/wealth/{module}/rebalance/preview`
- [x] Fallback P&L Today = 0 si `prev_close` indisponible (alignement Crypto)

### 3) Frontend intégration (Phase 2)
- [x] `dashboard.html` : tuile Bourse (Saxo) avec valeur totale, positions, date import
- [x] `static/modules/wealth-saxo-summary.js` (store partagé Dashboard/Settings)
- [x] `static/modules/equities-utils.js` (utilitaires manipulation données bourse)
- [x] Stabilisation `saxo-dashboard.html` (error handling, empty states, bandeau)
- [x] `static/analytics-equities.html` *(Beta, lecture legacy)*
- [ ] `static/risk-equities.html` *(Phase 3)*
- [ ] `static/rebalance-equities.html` *(Phase 3)*

### 4) Settings / Imports
- [x] Intégrer l'upload Saxo dans `settings.html` avec progress et statut temps réel
- [x] Affichage dernière importation, #positions, valeur totale
- [x] Conserver `saxo-upload.html` en parallèle pendant la transition

### 5) Nettoyage & transitions
- [ ] Déplacer `saxo-dashboard.html` hors menu (garder accessible le temps de la migration)
- [ ] Rediriger vers `analytics-equities.html` quand prête

### 5) Tests & scripts
- [x] Smoke Wealth : `tests/wealth_smoke.ps1` opérationnel
- [x] `GET /api/wealth/modules` (attend `"saxo"` si snapshot présent)
- [x] `GET /api/wealth/saxo/positions` retourne >0 positions
- [x] `POST /api/wealth/saxo/rebalance/preview` renvoie une liste (même vide)

## Phase 3 (À venir)

### Objectifs
- Migration progressive de la lecture legacy `/api/saxo/*` vers `/api/wealth/saxo/*`
- Création des pages dédiées `analytics-equities.html`, `risk-equities.html`, `rebalance-equities.html`
- Unification UI avec sélection module Crypto/Bourse dans les analytics

### Transition sécurisée
1. **Validation parité** : s'assurer que `/api/wealth/saxo/positions` retourne exactement les mêmes données que `/api/saxo/positions`
2. **Feature flag** : basculement progressif avec possibilité de rollback
3. **Analytics équités** : nouvelles pages en version beta avant migration complète

## Notes d'implémentation
- Timezone : Europe/Zurich pour les calculs "Today"
- Pricing : Crypto via CoinGecko; Bourse via snapshot + provider secondaire si besoin
- FX : normaliser l'affichage en devise de base (étape ultérieure)