# Crypto Rebal Starter (FastAPI)

Un squelette minimal pour démarrer ton projet de rééquilibrage en **Python + FastAPI**,
tout en gardant ton dashboard HTML actuel comme front.

## Lancer en local (sans Docker)

1) Crée un venv et installe les dépendances :
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2) Copie `.env.example` vers `.env` et renseigne les clés CoinTracking (facultatif pour tester en CSV) :
```bash
cp .env.example .env
# édite .env
```

3) Démarre l'API :
```bash
uvicorn api.main:app --reload --port 8000
```

4) Vérifie :
```bash
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/balances/current?source=stub"
```

## Endpoints clés

- `GET /health` — statut simple
- `GET /balances/current?source=stub|csv|cointracking`  
  - `stub` : renvoie des données d'exemple
  - `csv`  : body JSON `{"csv_current":"/chemin/Current Balance.csv"}` (optionnel: `csv_by_exchange`)
  - `cointracking` : nécessite `.env` (`COINTRACKING_KEY`, `COINTRACKING_SECRET`)
- `POST /rebalance/plan` — calcule un plan à partir des soldes + cibles

### Exemple body `/rebalance/plan`
```json
{
  "source": "stub",
  "targets": [
    {"symbol":"BTC","target_weight":0.40},
    {"symbol":"ETH","target_weight":0.30},
    {"symbol":"USDT","target_weight":0.30}
  ],
  "constraints": {"min_trade_usd": 25, "fee_bps": 10}
}
```

## Docker (optionnel)
```bash
docker compose up --build
# API sur http://127.0.0.1:8000
```

## Prochaines étapes
- Brancher ton dashboard HTML sur `/balances/current` et `/rebalance/plan`.
- Ajouter CCXT + workers pour l'exécution réelle des ordres.
- Ajouter Prefect pour l'orchestration (imports périodiques, rapports).
