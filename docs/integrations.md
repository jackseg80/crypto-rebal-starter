# Intégrations

## CoinTracking
- API: clés `CT_API_KEY`/`CT_API_SECRET` (ou alias `COINTRACKING_*`).
- CSV: export `Current Balance`, `Balance by Exchange`, `Coins by Exchange`.
- Endpoint utilitaire: `POST /csv/download` (téléchargement automatisé).

## Kraken
- Endpoints: `/kraken/*` (status, prices, balance, orders).
- Utiliser l’UI `static/execution.html` pour surveiller et tester.

## FRED / Données macro
- Résumé d’intégration et indicateurs disponibles (voir FRED_INTEGRATION_SUMMARY.md pour historique).

Notes: les guides détaillés historiques (docs/KRAKEN_INTEGRATION.md, FRED_INTEGRATION_SUMMARY.md) sont conservés pour référence mais considérés dépréciés au profit de cette page.

