from __future__ import annotations
from typing import Any, Dict, List
from constants import get_exchange_priority, normalize_exchange_name
from services.taxonomy import Taxonomy


def _keynorm(s: str) -> str:
    return "".join(str(s).split()).upper()


def _format_hint_for_location(location: str, action_type: str) -> str:
    priorities = {
        # CEX
        "Binance": 1, "Kraken": 2, "Coinbase": 3, "Bitget": 4, "Bybit": 5, "OKX": 6,
        "Huobi": 7, "KuCoin": 8, "Kraken Earn": 10, "Coinbase Pro": 11,
        # Wallets
        "MetaMask": 20, "Phantom": 21, "Rabby": 22, "TrustWallet": 23,
        # DeFi
        "DeFi": 30, "Uniswap": 31, "PancakeSwap": 32, "SushiSwap": 33, "Curve": 34,
        # Hardware / fallback
        "Ledger": 40, "Trezor": 41, "Cold Storage": 42,
        "Portfolio": 50, "CoinTracking": 51, "Demo Wallet": 52, "Unknown": 60, "Manually": 61,
    }

    key = (location or "Unknown").strip()
    if key.endswith(" Balance"):
        key = key[:-8].strip()
    key = key.title()
    prio = priorities.get(key, 100)

    if action_type == "sell":
        if prio < 15:        return f"Sell on {key}"
        elif prio < 30:      return f"Sell on {key} (DApp)"
        elif prio < 40:      return f"Sell on {key} (DeFi)"
        else:                return f"Sell on {key} (complex)"
    elif action_type == "buy":
        if prio < 15:        return f"Buy on {key}"
        elif prio < 30:      return f"Buy on {key} (DApp)"
        elif prio < 40:      return f"Buy on {key} (DeFi)"
        else:                return f"Buy on {key} (manual)"
    return f"Trade on {key}"


def _get_exec_hint(action: Dict[str, Any], items_by_group: Dict[str, List[Dict[str, Any]]]) -> str:
    group = action.get("group", "")
    action_type = action.get("action", "")
    if action.get("location"):
        return _format_hint_for_location(action["location"], action_type)

    group_items = items_by_group.get(group, [])
    if not group_items:
        return "Trade on primary exchange"

    # Utilisation des priorités centralisées
    def prio(loc: str) -> int:
        return get_exchange_priority(loc)

    # somme des valeurs par location
    loc_vals: Dict[str, float] = {}
    for it in group_items:
        loc = normalize_exchange_name(it.get("location") or "Unknown")
        v = float(it.get("value_usd") or 0.0)
        if v > 0:
            loc_vals[loc] = loc_vals.get(loc, 0.0) + v

    if not loc_vals:
        return "Trade on primary exchange"

    ordered = sorted(loc_vals.items(), key=lambda kv: (prio(kv[0]), -kv[1]))

    if action_type == "sell":
        cex = [l for l, _ in ordered if prio(l) < 15]
        main = (cex[0] if cex else ordered[0][0])
        return _format_hint_for_location(main, "sell")

    main = ordered[0][0]
    return _format_hint_for_location(main, "buy")


# ------------------------------------------------------------------
# services/rebalance.plan_rebalance
# ------------------------------------------------------------------


def plan_rebalance(
    rows: List[Dict[str, Any]],
    group_targets_pct: Dict[str, float],
    min_usd: float = 0.0,
    sub_allocation: str = "proportional",
    primary_symbols: Dict[str, List[str]] | None = None,
    min_trade_usd: float = 25.0,
) -> Dict[str, Any]:

    # ---------- helpers ----------
    def clean_loc(loc_raw: str) -> str:
        s = (loc_raw or "Unknown").strip()
        if s.endswith(" Balance"):
            s = s[:-8].strip()
        return s.title()

    priorities = {
        # CEX (vente rapide en priorité)
        "Binance": 1, "Kraken": 2, "Coinbase": 3, "Bitget": 4, "Bybit": 5, "OKX": 6,
        "Huobi": 7, "Kucoin": 8, "Coinbase Pro": 9,
        # DeFi / DEX
        "Uniswap": 30, "Pancakeswap": 31, "Sushiswap": 32, "Curve": 33, "Defi": 34,
        # Wallets / divers
        "Metamask": 20, "Phantom": 21, "Rabby": 22, "Trustwallet": 23,
        # Hardware / cold (en dernier)
        "Ledger": 40, "Trezor": 41, "Cold Storage": 42,
        # Fallbacks
        "Portfolio": 50, "Cointracking": 51, "Demo Wallet": 52, "Unknown": 60, "Manually": 61,
    }

    def prio(loc: str) -> int:
        return priorities.get(loc, 100)

    def fmt_hint(loc: str, action_type: str) -> str:
        # petit suffixe selon la “famille”
        p = prio(loc)
        if action_type == "sell":
            if p < 15:   return f"Sell on {loc}"
            elif p < 30: return f"Sell on {loc} (DApp)"
            elif p < 40: return f"Sell on {loc} (DeFi)"
            else:        return f"Sell on {loc} (complex)"
        else:
            if p < 15:   return f"Buy on {loc}"
            elif p < 30: return f"Buy on {loc} (DApp)"
            elif p < 40: return f"Buy on {loc} (DeFi)"
            else:        return f"Buy on {loc} (manual)"

    def allocate_proportional(total: float, buckets: List[tuple[str, float]]) -> Dict[str, float]:
        """Répartit 'total' proportionnellement aux poids 'buckets' -> {key: usd}."""
        alloc: Dict[str, float] = {}
        base = sum(max(w, 0.0) for _, w in buckets)
        if base <= 0:
            n = len(buckets)
            if n == 0:
                return {}
            q = round(total / n, 2)
            run = 0.0
            for i, (a, _) in enumerate(buckets):
                if i < n - 1:
                    alloc[a] = q; run += q
                else:
                    alloc[a] = round(total - run, 2)
            return alloc
        run = 0.0
        for i, (a, w) in enumerate(buckets):
            if i < len(buckets) - 1:
                x = round(total * (max(w, 0.0) / base), 2)
                alloc[a] = x; run += x
            else:
                alloc[a] = round(total - run, 2)
        return alloc

    # ---------- normalisation / grouping ----------
    tx = Taxonomy.load(reload=True)
    groups_order = list(tx.groups_order or []) or ["BTC", "ETH", "Stablecoins", "SOL", "L1/L0 majors", "Others"]

    # items normalisés (on conserve bien la location de chaque ligne)
    items: List[Dict[str, Any]] = []
    for it in rows or []:
        symbol = (it.get("symbol") or it.get("name") or it.get("coin") or "").strip()
        alias = (it.get("alias") or it.get("name") or symbol or "").strip()
        v = it.get("value_usd") if it.get("value_usd") is not None else it.get("usd_value")
        value_usd = float(v or 0.0)
        if value_usd < float(min_usd or 0.0):
            continue
        loc = clean_loc(it.get("location") or "Unknown")
        g = tx.group_for_alias(alias)
        if isinstance(g, (list, tuple)):
            g = next((x for x in g if isinstance(x, str) and x in groups_order), (g[0] if g else "Others"))
        if not isinstance(g, str) or g not in groups_order:
            g = "Others" if "Others" in groups_order else groups_order[0]

        items.append({
            "group": g, "alias": alias or symbol, "symbol": symbol or alias,
            "value_usd": value_usd, "location": loc,
        })

    total_usd = sum(x["value_usd"] for x in items) or 0.0

    # agrégats par groupe / alias / location (pour caper les ventes par “où c’est détenu”)
    by_group: Dict[str, List[Dict[str, Any]]] = {g: [] for g in groups_order}
    hold_by_gal: Dict[str, Dict[str, Dict[str, float]]] = {}
    current_by_group: Dict[str, float] = {g: 0.0 for g in groups_order}
    for it in items:
        g, a, loc, val = it["group"], it["alias"], it["location"], it["value_usd"]
        by_group[g].append(it)
        current_by_group[g] += val
        hold_by_gal.setdefault(g, {}).setdefault(a, {})
        hold_by_gal[g][a][loc] = hold_by_gal[g][a].get(loc, 0.0) + val

    current_weights_pct = {
        g: round(100.0 * (current_by_group.get(g, 0.0) / total_usd), 3) if total_usd else 0.0
        for g in groups_order
    }
    target_weights_pct = {g: float(group_targets_pct.get(g, 0.0)) for g in groups_order}
    targets_usd = {g: round(total_usd * (target_weights_pct.get(g, 0.0) / 100.0), 2) for g in groups_order}
    deltas_by_group_usd = {g: round(targets_usd.get(g, 0.0) - current_by_group.get(g, 0.0), 2) for g in groups_order}

    actions: List[Dict[str, Any]] = []

    # ---------- VENTES : répartition par alias PUIS par location avec priorité ----------
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta >= -1e-9:
            continue
        to_sell = -delta

        # poids par alias = taille de la position
        agg_alias: Dict[str, float] = {}
        for p in by_group.get(g, []):
            a = p["alias"]
            agg_alias[a] = agg_alias.get(a, 0.0) + p["value_usd"]

        alloc_alias = allocate_proportional(to_sell, list(agg_alias.items()))

        for alias, usd_need in alloc_alias.items():
            remaining = float(usd_need or 0.0)
            loc_map = (hold_by_gal.get(g, {}).get(alias, {}) or {}).copy()

            # ordre de vente : CEX (prio faible) > DApp/DeFi > Hardware
            ordered_locs = sorted(loc_map.items(), key=lambda kv: (prio(kv[0]), -kv[1]))

            for loc, capacity in ordered_locs:
                if remaining <= 1e-9:
                    break
                slice_usd = round(min(capacity, remaining), 2)
                if slice_usd < float(min_trade_usd or 0.0):
                    continue
                actions.append({
                    "group": g, "alias": alias, "symbol": alias,
                    "action": "sell",
                    "usd": -slice_usd,
                    "location": loc,
                    "exec_hint": fmt_hint(loc, "sell"),
                    "est_quantity": None, "price_used": None,
                })
                remaining = round(remaining - slice_usd, 2)

            # si un reste minuscule subsiste (< min_trade_usd), on l’ignore (friction)
            # si un gros reste subsiste (peu probable), on le met sur la meilleure loc
            if remaining >= max(2 * float(min_trade_usd or 0.0), 50.0) and ordered_locs:
                loc = ordered_locs[0][0]
                actions.append({
                    "group": g, "alias": alias, "symbol": alias,
                    "action": "sell",
                    "usd": -round(remaining, 2),
                    "location": loc,
                    "exec_hint": fmt_hint(loc, "sell"),
                    "est_quantity": None, "price_used": None,
                })

    # ---------- ACHATS : une seule location “meilleure” (simple) ----------
    ps = primary_symbols or {}
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta <= 1e-9:
            continue
        to_buy = delta

        prim = [s.strip() for s in (ps.get(g) or []) if isinstance(s, str) and s.strip()]
        # poids d’allocation par alias pour l’achat
        if prim:
            buckets = [(a, 1.0) for a in prim]
        else:
            agg: Dict[str, float] = {}
            for p in by_group.get(g, []):
                a = p["alias"]
                agg[a] = agg.get(a, 0.0) + p["value_usd"]
            buckets = list(agg.items()) if agg else [(g, 1.0)]

        alloc_alias = allocate_proportional(to_buy, buckets)

        # choisir la meilleure location : là où l’alias existe déjà, sinon
        # la “grosse” location du groupe, sinon CoinTracking
        # (achat non fractionné pour rester simple)
        # total par loc pour le groupe
        group_loc_size: Dict[str, float] = {}
        for p in by_group.get(g, []):
            L = p["location"]
            group_loc_size[L] = group_loc_size.get(L, 0.0) + p["value_usd"]
        best_group_loc = None
        if group_loc_size:
            best_group_loc = sorted(group_loc_size.items(), key=lambda kv: (prio(kv[0]), -kv[1]))[0][0]

        for alias, usd in alloc_alias.items():
            if usd < float(min_trade_usd or 0.0):
                continue
            loc_map = hold_by_gal.get(g, {}).get(alias, {})
            if loc_map:
                loc = sorted(loc_map.items(), key=lambda kv: (prio(kv[0]), -kv[1]))[0][0]
            elif best_group_loc:
                loc = best_group_loc
            else:
                loc = "CoinTracking"
            actions.append({
                "group": g, "alias": alias, "symbol": alias,
                "action": "buy",
                "usd": round(float(usd), 2),
                "location": loc,
                "exec_hint": fmt_hint(loc, "buy"),
                "est_quantity": None, "price_used": None,
            })

    # ---------- Nettoyage net 0 et sortie ----------
    # (pas d’ajustement net ici, car on a déjà capé par positions réelles)
    # filtrer les toutes petites actions
    actions = [a for a in actions if abs(a.get("usd", 0.0)) >= float(min_trade_usd or 0.0)]

    unknown_aliases_set = set()
    known_aliases = set(Taxonomy.load().aliases.keys())
    known_groups = set(Taxonomy.load().groups_order or [])
    known_groups_norm = {"".join(g.split()).upper() for g in known_groups}
    for it in rows or []:
        alias = (it.get("alias") or it.get("name") or it.get("symbol") or "").strip()
        v = it.get("value_usd") if it.get("value_usd") is not None else it.get("usd_value")
        if float(v or 0.0) < float(min_usd or 0.0):
            continue
        if alias and alias.upper() not in known_aliases and "".join(alias.split()).upper() not in known_groups_norm:
            unknown_aliases_set.add(alias)

    return {
        "total_usd": round(total_usd, 2),
        "current_by_group": {g: round(current_by_group.get(g, 0.0), 2) for g in groups_order},
        "current_weights_pct": current_weights_pct,
        "target_weights_pct": {g: round(float(target_weights_pct.get(g, 0.0)), 3) for g in groups_order},
        "targets_usd": {g: round(targets_usd.get(g, 0.0), 2) for g in groups_order},
        "deltas_by_group_usd": {g: round(deltas_by_group_usd.get(g, 0.0), 2) for g in groups_order},
        "actions": actions,
        "advice": [],
        "unknown_aliases": sorted(list(unknown_aliases_set)),
    }
