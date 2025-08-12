from typing import List, Dict
import math

def build_plan(balances: List[Dict], targets: List[Dict], constraints: Dict) -> Dict:
    """
    balances: [{symbol, name, usd_value}]
    targets:  [{symbol, target_weight}]
    constraints: {"min_trade_usd": float, "fee_bps": float}
    """
    min_trade = float(constraints.get("min_trade_usd", 25.0))
    fee_bps = float(constraints.get("fee_bps", 10.0))

    total = sum(b.get("usd_value", 0.0) for b in balances) or 0.0
    if total <= 0:
        return {"total_usd": 0, "legs": [], "deviation_bps": 0, "note": "Total nul"}

    current_map = {b["symbol"]: float(b.get("usd_value", 0)) for b in balances}
    target_map = {t["symbol"].upper(): float(t["target_weight"]) for t in targets}

    # normalise les weights si la somme != 1
    s = sum(target_map.values())
    if s > 0 and abs(s - 1.0) > 1e-6:
        target_map = {k: v/s for k,v in target_map.items()}

    # calcule diffs
    all_symbols = set(current_map) | set(target_map)
    legs = []
    deviation_abs = 0.0

    for sym in sorted(all_symbols):
        cur_usd = current_map.get(sym, 0.0)
        cur_w = cur_usd/total if total > 0 else 0.0
        tgt_w = target_map.get(sym, 0.0)
        diff_w = tgt_w - cur_w
        deviation_abs += abs(diff_w)
        usd_to_trade = diff_w * total

        if abs(usd_to_trade) < min_trade:
            continue

        side = "buy" if usd_to_trade > 0 else "sell"
        fee = abs(usd_to_trade) * (fee_bps/10000.0)
        legs.append({
            "exchange": "auto",
            "symbol": f"{sym}/USDT",
            "side": side,
            "amount_usd": round(usd_to_trade, 2),
            "fee_estimated_usd": round(fee, 2)
        })

    deviation_bps = int(round(deviation_abs * 10000 / 2))
    return {
        "total_usd": round(total, 2),
        "deviation_bps": deviation_bps,
        "legs": legs,
        "note": "Plan naïf par poids; routing/exchanges à implémenter"
    }
