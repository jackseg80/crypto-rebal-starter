# Intégrations - Sources de Données Cross-Asset

**Intégrations consolidées** pour modules Crypto, Bourse, Banque et Divers.

## CoinTracking
- Variables d’environnement (API):
  - `CT_API_KEY`/`CT_API_SECRET` ou `COINTRACKING_API_KEY`/`COINTRACKING_API_SECRET`
  - Option: `CT_API_BASE` (défaut: `https://cointracking.info/api/v1/`)
- CSV pris en charge:
  - `Balance by Exchange` (préféré, contient les locations)
  - `Current Balance` (fallback)
  - `Coins by Exchange` (détails par exchange)
- Fallback intelligent: le parsing privilégie “Balance by Exchange” puis “Current Balance”.
- Endpoint utilitaire: `POST /csv/download` pour automatiser l'export (avec nom daté, `data/raw/`).

## Saxo Bank - CSV/XLSX Import

### Format supporté
```csv
Position ID,Instrument,Quantity,Market Value,Currency,Asset Class
12345,AAPL,100,15000.00,USD,Equity
67890,ISIN:IE00B4L5Y983,500,25000.00,EUR,ETF
```

### Mapping colonnes automatique
- **Symboles** : Ticker/ISIN → Standardisation
- **Devises** : EUR/USD/CHF → Conversion FX temps réel
- **Classes d'actifs** : Equity/Bond/ETF/Option → Catégorisation

### Endpoint
- `POST /saxo/import` : Upload CSV/XLSX avec validation

## Kraken
- Endpoints clés: `/kraken/status`, `/kraken/prices`, `/kraken/balance`, `/kraken/validate-order`, `/kraken/orders`.
- UI associée: `static/execution.html` (monitoring connexions, gestion d’ordres, historique).

## FRED / Données macro
- Résumé d’intégration et indicateurs disponibles; pour le détail complet, voir l’archive `docs/_legacy/`.

Notes: les guides détaillés historiques sont conservés en archive et cette page sert de référence intermédiaire maintenable.
