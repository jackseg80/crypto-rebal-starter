import os, json, random
from typing import Any, Dict

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cointracking_balances.json")

async def get_current_balances(source: str = "cointracking") -> Dict[str, Any]:
    """Stub de connecteur.
    Modes:
      - COINTRACKING_MODE=file : lit data/cointracking_balances.json
      - COINTRACKING_MODE=stub : génère des données de démo
    """
    mode = os.getenv("COINTRACKING_MODE", "stub").lower()
    if mode == "file" and os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"items": data}

    # Démo (valeurs proches de ce qui a été vu)
    demo = [
        {"symbol":"BTC","usd_value":185000},
        {"symbol":"TBTC","usd_value":15700},
        {"symbol":"WBTC","usd_value":1100},

        {"symbol":"ETH","usd_value":31200},
        {"symbol":"WSTETH","usd_value":46400},
        {"symbol":"RETH","usd_value":20950},
        {"symbol":"STETH","usd_value":3790},
        {"symbol":"WETH","usd_value":1580},

        {"symbol":"USD","usd_value":12050},
        {"symbol":"USDT","usd_value":10350},
        {"symbol":"USDC","usd_value":1425},
        {"symbol":"EUR","usd_value":245},

        {"symbol":"SOL","usd_value":3770},
        {"symbol":"JUPSOL","usd_value":2310},
        {"symbol":"JITOSOL","usd_value":2240},

        {"symbol":"LINK","usd_value":7900},
        {"symbol":"DOGE","usd_value":6020},
        {"symbol":"AAVE","usd_value":5500},
    ]
    return {"items": demo}
