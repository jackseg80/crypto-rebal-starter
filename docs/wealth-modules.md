# Modules Patrimoniaux

Le cockpit patrimoine intègre **4 modules principaux** avec gestion unifiée des risques et allocation cross-asset.

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

**Intégration Saxo Bank** via CSV/XLSX avec mapping automatique.

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

## WealthContextBar - Filtrage Cross-Module

### Filtres disponibles

**Household**
- `all` : Vue consolidée tous patrimoines
- `main` : Patrimoine principal
- `secondary` : Patrimoine conjoint/enfants

**Compte**
- `all` : Tous comptes confondus
- `trading` : Comptes actifs (crypto + bourse)
- `hold` : Investissements long-terme
- `staking` : Revenus passifs

**Module**
- `all` : Vue cross-asset complète
- `crypto` : Crypto uniquement
- `bourse` : Actions/obligations Saxo
- `banque` : Comptes bancaires/épargne
- `divers` : Alternatifs/immobilier

**Devise**
- `USD` : Référence dollar (par défaut)
- `EUR` : Référence euro
- `CHF` : Référence franc suisse

### Persistance & Synchronisation

**localStorage** : Clé `wealthCtx`
```json
{
  "household": "main",
  "account": "trading",
  "module": "crypto",
  "currency": "EUR"
}
```

**QueryString** : Paramètres URL synchronisés
```
?household=main&account=trading&module=crypto&ccy=EUR
```

**Événements** : `wealth:change` émis à chaque modification

### Impact sur les Pages

**Rebalance** (`rebalance.html`)
- Filtre les propositions selon module sélectionné
- Adapte les contraintes et limites
- Conversion devise automatique

**Execution** (`execution.html`)
- Affiche ordres du module/compte sélectionné
- Filtre historique par critères
- Coûts dans la devise de référence

**Analytics** (`analytics-unified.html`)
- Métriques calculées sur périmètre filtré
- Corrélations intra/inter-modules
- Performance relative ajustée

---

## Allocation Cross-Asset

### Budget de Risque Global
- **VaR total** : 4% seuil critique
- **Répartition** : 50% crypto / 30% bourse / 15% banque / 5% divers
- **Corrélations** : Matrices cross-asset temps réel
- **Rebalance** : Déclenchement automatique si dérive >3%

### Contraintes par Module
- **Crypto** : Max 60% du patrimoine total
- **Single asset** : Max 25% (BTC exception 35%)
- **Illiquides** : Max 20% (immobilier + divers)
- **Cash** : Min 10% liquidités (banque)

### Signaux Unifiés
**Decision Engine** agrège les signaux de tous les modules pour optimisation globale avec gouvernance centralisée.