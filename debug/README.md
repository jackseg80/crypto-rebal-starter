# Debug Tools

Ce dossier contient tous les outils de développement et de debug du projet.

## Structure

- `scripts/` - Scripts Python de debug et d'analyse
  - `debug_coingecko.py` - Debug de l'API CoinGecko
  - `debug_enhanced.py` - Debug des fonctionnalités avancées
  - `debug_eth_categories.py` - Debug des catégories ETH
  - `debug_suggestions_enhanced.py` - Debug du système de suggestions

- `html/` - Pages HTML de debug et test
  - `debug-dashboard.html` - Debug du dashboard principal
  - `debug_ccs_sync.html` - Debug de la synchronisation CCS

- `tools/` - Utilitaires et outils de développement (à venir)

## Usage

Ces outils sont destinés au développement et au debugging. Ils ne doivent pas être utilisés en production.

Pour utiliser un script de debug :
```bash
python debug/scripts/debug_coingecko.py
```

Pour accéder aux pages de debug HTML :
```
http://localhost:8000/debug/html/debug-dashboard.html
```