# services/rebalance.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, DefaultDict
from collections import defaultdict

from api.taxonomy import Taxonomy

def _price_or_none(amount: float, value_usd: float) -> float | None:
    try:
        if amount and abs(amount) > 0:
            return value_usd / amount
    except Exception:
        pass
    return None

def snapshot_groups(rows: List[Dict[str, Any]], min_usd: float = 1.0) -> Dict[str, Any]:
    """
    Agrège via Taxonomy (même logique que /debug/snapshot).
    """
    tx = Taxonomy()
    snap = tx.aggregate(rows, min_usd=min_usd)
    # structure utile pour le plan
    alias_summary: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {"alias": "", "total_usd": 0.0, "coins": []})
    for g in snap["groups"]:
        for it in g["items"]:
            alias = it["alias"]
            d = alias_summary[alias]
            d["alias"] = alias
            d["total_usd"] += it["value_usd"]
            d["coins"].append({
                "symbol": it["symbol"],
                "alias": alias,
                "amount": it["amount"],
                "value_usd": it["value_usd"],
                "price_usd": _price_or_none(it["amount"], it["value_usd"]),
                "group": g["group"]
            })
    return {
        "total_usd": snap["total_usd"],
        "groups": snap["groups"],
        "alias_summary": list(alias_summary.values()),
        "unknown_aliases": snap["unknown_aliases"],
    }

def _group_of_alias(alias: str, tx: Taxonomy) -> str:
    return tx.group_of_alias(alias)

def plan_rebalance(
    rows: List[Dict[str, Any]],
    group_targets_pct: Dict[str, float],
    min_usd: float = 1.0,
    sub_allocation: str = "proportional",
    primary_symbols: Dict[str, str] | None = None,
    min_trade_usd: float = 10.0,
) -> Dict[str, Any]:
    """
    Calcule le plan d’ordres à partir des cibles de groupes.
    - sub_allocation: "proportional" (par défaut) conserve le mix actuel des variantes au sein d’un alias.
                      "prefer_primary" concentre sur le symbole primaire donné dans primary_symbols.
    - primary_symbols: ex {"BTC":"BTC","ETH":"ETH","Stablecoins":"USDC","SOL":"SOL"}
    """
    tx = Taxonomy()
    snap = snapshot_groups(rows, min_usd=min_usd)
    total = snap["total_usd"] or 0.0
    groups = snap["groups"]

    # totaux actuels par groupe
    current_by_group = {g["group"]: g["total_usd"] for g in groups}
    # normaliser les cibles (accepter qu’elles ne couvrent pas 100%)
    tgt_pct = {k: float(v) for k, v in group_targets_pct.items()}
    sum_pct = sum(tgt_pct.values()) or 0.0
    if sum_pct and abs(sum_pct - 100.0) > 1e-6:
        # on normalise pour que ça fasse 100% (option simple)
        tgt_pct = {k: v * 100.0 / sum_pct for k, v in tgt_pct.items()}

    targets_usd = {k: total * (v / 100.0) for k, v in tgt_pct.items()}
    deltas_by_group = {k: targets_usd.get(k, 0.0) - current_by_group.get(k, 0.0) for k in set(current_by_group) | set(targets_usd)}

    # index rapide: coins par alias et par groupe
    coins_by_alias: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    alias_group: Dict[str, str] = {}
    for g in groups:
        for it in g["items"]:
            a = it["alias"]
            coins_by_alias[a].append(it)
            alias_group[a] = g["group"]

    actions: List[Dict[str, Any]] = []
    advice: List[str] = []

    def add_action(group: str, alias: str, symbol: str, action: str, usd: float, price: float | None):
        if abs(usd) < min_trade_usd:
            return  # ignorer micro-trades
        qty = (usd / price) if (price and price > 0) else None
        actions.append({
            "group": group, "alias": alias, "symbol": symbol,
            "action": action, "usd": round(float(usd), 2),
            "est_quantity": None if qty is None else round(float(qty), 8),
            "price_used": price
        })

    # Pour chaque groupe: répartir delta sur les alias présents dans ce groupe
    # Règle simple: on ventile proportionnellement aux valeurs USD actuelles des alias
    # Si le groupe n'a aucun alias actuel mais a une cible > 0, on utilise primary_symbols (si fourni) sinon on émet un conseil.
    # NB: l’utilisateur pourra préciser plus tard une "sub-taxonomie" si besoin.
    # Préparer distribution alias->valeur dans le groupe
    group_alias_values: DefaultDict[str, Dict[str, float]] = defaultdict(dict)
    for alias, coins in coins_by_alias.items():
        g = alias_group.get(alias, tx.group_of_alias(alias))
        group_alias_values[g][alias] = sum(c["value_usd"] for c in coins)

    # Boucle groupes
    for g_name, g_delta in deltas_by_group.items():
        alias_values = group_alias_values.get(g_name, {})
        alias_total = sum(alias_values.values())

        if abs(g_delta) < 1e-6:
            continue

        if g_delta < 0:  # on réduit (sell)
            if alias_total <= 0:
                continue
            for alias, a_val in alias_values.items():
                part = a_val / alias_total if alias_total else 0.0
                usd_to_sell_alias = g_delta * part  # négatif
                # au sein de l'alias, répartir sur ses coins
                coins = coins_by_alias.get(alias, [])
                alias_coin_total = sum(c["value_usd"] for c in coins) or 0.0
                for c in coins:
                    share = c["value_usd"] / alias_coin_total if alias_coin_total else 0.0
                    usd_coin = usd_to_sell_alias * share
                    add_action(g_name, alias, c["symbol"], "sell", usd_coin, c.get("price_usd"))
        else:  # g_delta > 0 : on achète
            if alias_total > 0:
                # Ventile proportionnellement aux alias existants
                for alias, a_val in alias_values.items():
                    part = a_val / alias_total if alias_total else 0.0
                    usd_to_buy_alias = g_delta * part
                    coins = coins_by_alias.get(alias, [])
                    if sub_allocation == "prefer_primary":
                        # tout sur un seul symbole primaire si connu
                        prim = (primary_symbols or {}).get(g_name) or (coins[0]["symbol"] if coins else alias)
                        price = None
                        # si prim déjà présent, récupère un price
                        for c in coins:
                            if c["symbol"].upper() == prim.upper():
                                price = c.get("price_usd")
                                break
                        add_action(g_name, alias, prim, "buy", usd_to_buy_alias, price)
                    else:
                        # proportional: conserve le mix actuel des coins de l'alias
                        alias_coin_total = sum(c["value_usd"] for c in coins) or 0.0
                        if alias_coin_total <= 0 and coins:
                            # si pas de valeur (edge), tout sur le premier
                            c = coins[0]
                            add_action(g_name, alias, c["symbol"], "buy", usd_to_buy_alias, c.get("price_usd"))
                        else:
                            for c in coins:
                                share = c["value_usd"] / alias_coin_total if alias_coin_total else 0.0
                                usd_coin = usd_to_buy_alias * share
                                add_action(g_name, alias, c["symbol"], "buy", usd_coin, c.get("price_usd"))
            else:
                # Aucun alias existant dans ce groupe => besoin d'un choix par défaut
                prim = (primary_symbols or {}).get(g_name)
                if prim:
                    add_action(g_name, prim, prim, "buy", g_delta, None)
                else:
                    advice.append(
                        f"Groupe '{g_name}' sans positions actuelles : spécifie un symbole primaire (ex: USDC pour Stablecoins, BTC, ETH, SOL…)."
                    )

    # Résumé lisible
    current_weights = {g: (current_by_group.get(g, 0.0) / total * 100.0 if total > 0 else 0.0) for g in current_by_group}
    target_weights = tgt_pct
    result = {
        "total_usd": round(float(total), 2),
        "current_by_group": current_by_group,
        "current_weights_pct": {k: round(v, 3) for k, v in current_weights.items()},
        "target_weights_pct": {k: round(v, 3) for k, v in target_weights.items()},
        "targets_usd": {k: round(float(v), 2) for k, v in targets_usd.items()},
        "deltas_by_group_usd": {k: round(float(v), 2) for k, v in deltas_by_group.items()},
        "actions": actions,
        "advice": advice,
        "unknown_aliases": snap["unknown_aliases"],
    }
    return result
