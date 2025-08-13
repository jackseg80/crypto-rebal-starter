# Crypto Rebal Starter — Pack prêt à l'emploi

Ce pack reprend l'API FastAPI + la page `rebalance.html` prêtes à l'emploi.

## Démarrage rapide

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

- UI locale : ouvrez `static/rebalance.html`
- Swagger : http://127.0.0.1:8000/docs

## Points clés

- **/rebalance/plan** : calcule un plan (ventes proportionnelles, achats sur *primary_symbols*)
- **/taxonomy** : persiste les groupes et alias dans `data/taxonomy.json`
- **/taxonomy/aliases (POST)** : `{ "aliases": { "WBTC": "BTC", ... } }`
- **/taxonomy/unknown_aliases** : liste des alias non-mappés au-dessus d'un seuil

Le connecteur `connectors/cointracking.py` supporte deux modes :
- `stub` (par défaut) : génère des données de démo
- `file` : lit `data/cointracking_balances.json` si présent

Si vous avez déjà un connecteur réel, remplacez ce fichier par le vôtre.
