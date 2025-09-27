# Modules Patrimoniaux — État ACTUEL + Roadmap

Le cockpit patrimoine vise à intégrer **plusieurs modules** (Crypto, Bourse, Banques) dans une logique unifiée.
**Aujourd'hui** :
- **Crypto** : pleinement intégré (analytics/risk/rebalance)
- **Bourse (Saxo)** : présent via pages dédiées `saxo-dashboard.html` et `saxo-upload.html`
- **Banques** : non intégré

## UI (AUJOURD'HUI)
- **Crypto** : `analytics-unified.html`, `risk-dashboard.html`, `rebalance.html`
- **Bourse (Saxo)** : `saxo-dashboard.html` (dashboard), `saxo-upload.html` (import)
- **Banques** : n/a
- **Dashboard** : `dashboard.html` (majoritairement Crypto à ce stade)

## 1. Module Crypto

**Intégration native** avec CoinTracking CSV/API et exchanges.

### Sources de données
- **CoinTracking API** : Balances temps réel par exchange
- **CoinTracking CSV** : Import Balance by Exchange / Current Balance
- **Prix** : CoinGecko, CoinGlass, APIs exchanges
- **On-chain** : Metrics glassnode, données blockchain

### Fonctionnalités
- Rebalancing intelligent avec allocations dynamiques CCS
- Execution hints par exchange (fees, liquidité)
- Risk management avec VaR/CVaR crypto-spécifiques
- Analytics ML : volatilité, sentiment, régimes marché

### Comptes supportés
- Trading (actif)
- Hold (long-terme)
- Staking (rewards)
- DeFi (pools LP, yield farming)

---

## 2. Module Bourse (Saxo)

**État actuel** : intégration **via CSV/XLSX** avec pages **dédiées**.
- UI actuelle :
  - `saxo-upload.html` : chargement de fichiers
  - `saxo-dashboard.html` : consultation des positions Saxo
- Endpoints actuels usuels : `/api/saxo/*`

**Limites connues** :
- Flux séparé de Crypto (UX pas encore unifiée)
- P&L Today dépend des données de clôture (peut être 0 en fallback)

### Sources de données
- **Saxo CSV/XLSX** : Positions, transactions, cash
- **Prix** : Saxo feed + fallbacks Yahoo Finance / Bloomberg
- **Référentiels** : ISIN, symboles, devises

### Mapping colonnes
```
Position ID → Saxo Internal ID
Instrument → Symbol / ISIN
Quantity → Position Size
Market Value → EUR/USD/CHF equivalent
Currency → Base Currency
Asset Class → Equity / Bond / ETF / Option
```

### Fonctionnalités
- Allocation tactique actions/obligations
- Rebalance avec contraintes fiscales
- Risk attribution sector/geographic
- Performance vs benchmarks (MSCI, S&P500)

---

## 3. Module Banque

**Saisie manuelle/CSV** pour comptes bancaires et épargne.

### Types de comptes
- **Courants** : CHF, EUR, USD
- **Épargne** : Livrets, comptes terme
- **Assurance Vie** : UC, fonds euros
- **Immobilier** : Valorisation estimative

### Fonctionnalités
- Conversion FX temps réel
- Tracking inflation-adjusted returns
- Optimisation fiscale épargne
- Planning liquidités (cash flow)

### Format CSV import
```csv
Account,Type,Currency,Balance,LastUpdate
"UBS Courant","checking","CHF",25000.00,"2024-01-15"
"Livret A","savings","EUR",15000.00,"2024-01-15"
"AV Generali","insurance","EUR",45000.00,"2024-01-15"
```

---

## 4. Module Divers

**Actifs alternatifs** et investissements illiquides.

### Types d'actifs
- **Immobilier** : Résidence principale, locatif, SCPI
- **Private Equity** : Participations, startups
- **Commodities** : Or physique, matières premières
- **Art & Collectibles** : Œuvres d'art, vins, montres

### Valorisation
- **Méthode** : Réévaluation manuelle périodique
- **Fréquence** : Trimestrielle ou semestrielle
- **Benchmarks** : Indices sectoriels (IPD immobilier, gold spot)

---

## 4. Roadmap (résumé)
**Objectif** : unifier Bourse/Banques sur le même schéma que Crypto (mêmes pages miroirs : analytics/risk/rebalance), via un namespace **Wealth**.

Étapes majeures :
1. **Contrats communs** (côté backend) : AccountModel, InstrumentModel, PositionModel, PricePoint, ProposedTrade
2. **Endpoints Wealth** :
   - `GET /api/wealth/modules`
   - `GET /api/wealth/{module}/accounts|instruments|positions|prices`
   - `POST /api/wealth/{module}/rebalance/preview`
3. **UI miroirs Bourse** :
   - `analytics-equities.html`, `risk-equities.html`, `rebalance-equities.html`
4. **Settings** :
   - Intégrer l'upload Saxo dans `settings.html` (section "Sources")
5. **Banques** :
   - Adapter CASH/flux, page `analytics-banks.html` (plus tard)

> Détails et cases à cocher : voir `docs/TODO_WEALTH_MERGE.md`.