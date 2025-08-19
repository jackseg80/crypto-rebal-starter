from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _normalize_targets(targets_raw: Any) -> Dict[str, float]:
    """
    Accepte différents formats:
      - dict {"BTC": 35, "ETH": 25, ...}
      - list [{"group":"BTC","weight_pct":35}, ...]
    Retourne toujours un dict {group: weight_pct_float}.
    """
    out: Dict[str, float] = {}

    if isinstance(targets_raw, dict):
        for k, v in targets_raw.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                pass
        return out

    if isinstance(targets_raw, list):
        for item in targets_raw:
            if not isinstance(item, dict):
                continue
            g = item.get("group")
            w = item.get("weight_pct")
            if g is None or w is None:
                continue
            try:
                out[str(g)] = float(w)
            except Exception:
                pass

    return out


def _canonize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Assure un format propre pour chaque ligne:
      - group: chaîne (si liste -> on prend le 1er élément)
      - alias: chaîne (fallback sur symbol)
      - value_usd: float depuis value_usd ou usd_value
    """
    canon: List[Dict[str, Any]] = []
    for r in rows or []:
        # group -> string
        g = r.get("group")
        if isinstance(g, list):
            g = next((x for x in g if isinstance(x, str) and x), None)
        if not isinstance(g, str) or not g:
            g = "Others"

        # alias / symbol
        symbol = r.get("symbol") or r.get("name") or ""
        alias = r.get("alias") or symbol

        # value_usd
        val = r.get("value_usd")
        if val is None:
            val = r.get("usd_value")
        try:
            value_usd = float(val or 0.0)
        except Exception:
            value_usd = 0.0

        canon.append(
            {
                "group": g,
                "alias": alias,
                "symbol": symbol or alias,
                "value_usd": value_usd,
                "location": r.get("location") or "unknown",
            }
        )
    return canon


def _sum_by_group(rows: List[Dict[str, Any]], min_usd: float) -> Tuple[float, Dict[str, float], Dict[str, List[Dict[str, Any]]]]:
    """
    Retourne (total, current_by_group, items_by_group)
    en filtrant les trop petites lignes (< min_usd).
    """
    total = 0.0
    by_group: Dict[str, float] = {}
    items_by_group: Dict[str, List[Dict[str, Any]]] = {}

    for it in rows:
        v = float(it.get("value_usd") or 0.0)
        if v < min_usd:
            continue
        g = it["group"]  # déjà une chaîne grâce à _canonize_rows
        total += v
        by_group[g] = by_group.get(g, 0.0) + v
        items_by_group.setdefault(g, []).append(it)

    return total, by_group, items_by_group


def _targets_usd(total: float, group_targets_pct: Dict[str, float]) -> Dict[str, float]:
    return {g: round(total * (pct / 100.0), 2) for g, pct in group_targets_pct.items()}


def _sell_actions_for_group(items: List[Dict[str, Any]], sell_amount: float) -> List[Dict[str, Any]]:
    """
    Ventes proportionnelles à la taille des positions du groupe.
    sell_amount est négatif (ex: -1200.0)
    """
    actions: List[Dict[str, Any]] = []
    group_total = sum(float(x["value_usd"]) for x in items) or 1.0  # eviter /0

    remaining = abs(sell_amount)
    for it in sorted(items, key=lambda x: x["value_usd"], reverse=True):
        if remaining <= 0:
            break
        share = float(it["value_usd"]) / group_total
        usd = round(-min(remaining, share * abs(sell_amount)), 2)
        if usd == 0:
            continue
        actions.append(
            {
                "group": it["group"],
                "alias": it["alias"],
                "symbol": it["symbol"],
                "action": "sell",
                "usd": usd,  # négatif
                "est_quantity": None,
                "price_used": None,
            }
        )
        remaining -= abs(usd)

    return actions


def _buy_actions_for_group(
    group: str,
    buy_amount: float,
    primary_symbols: Optional[Dict[str, List[str]]],
) -> List[Dict[str, Any]]:
    """
    Achats répartis uniquement sur primary_symbols[group] s’il existe,
    sinon un seul achat “group” (ex: alias=BTC, symbol=BTC).
    buy_amount est positif.
    """
    actions: List[Dict[str, Any]] = []
    targets = []
    if isinstance(primary_symbols, dict):
        arr = primary_symbols.get(group)
        if isinstance(arr, list) and arr:
            targets = [s for s in arr if isinstance(s, str) and s]

    if not targets:
        # fallback: un seul achat sur le groupe lui-même
        targets = [group]

    n = len(targets)
    if n == 0:
        return actions

    share = round(buy_amount / n, 2)
    for sym in targets:
        actions.append(
            {
                "group": group,
                "alias": group,   # on regroupe par alias de groupe
                "symbol": sym,
                "action": "buy",
                "usd": share,     # positif
                "est_quantity": None,
                "price_used": None,
            }
        )

    # ajuster le dernier pour compenser les arrondis
    diff = round(buy_amount - sum(a["usd"] for a in actions), 2)
    if diff != 0 and actions:
        actions[-1]["usd"] = round(actions[-1]["usd"] + diff, 2)

    return actions


# services/rebalance.py

from typing import Any, Dict, List, Tuple
from services.taxonomy import Taxonomy

def plan_rebalance(
    rows: List[Dict[str, Any]],
    group_targets_pct: Dict[str, float],
    min_usd: float = 0.0,
    sub_allocation: str = "proportional",
    primary_symbols: Dict[str, List[str]] | None = None,
    min_trade_usd: float = 25.0,
) -> Dict[str, Any]:
    """
    rows: [{symbol, alias, value_usd, location, ...}]
    group_targets_pct: {"BTC": 35, "ETH": 25, ...}  (somme ~100)
    primary_symbols: {"BTC": ["BTC","TBTC","WBTC"], "ETH": ["ETH","WSTETH",...], ...}
      -> utilisé pour les ACHATS seulement. Les ventes se font proportionnellement
         aux positions actuelles dans chaque groupe (peu importe primary_symbols).
    """
    # Recharge la taxonomie pour avoir les dernières données
    tx = Taxonomy.load(reload=True)

    # Ordre des groupes (fallback si vide)
    groups_order = list(tx.groups_order or [])
    if not groups_order:
        groups_order = ["BTC", "ETH", "Stablecoins", "SOL", "L1/L0 majors", "Others"]

    by_group: Dict[str, List[Dict[str, Any]]] = {g: [] for g in groups_order}
    fallback_group = "Others" if "Others" in by_group else groups_order[0]

    def pick_group_for_alias(a: str) -> str:
        g = tx.group_for_alias(a)
        if isinstance(g, (list, tuple)):
            for cand in g:
                if isinstance(cand, str) and cand in by_group:
                    return cand
            for cand in g:
                if isinstance(cand, str):
                    return cand
            return fallback_group
        if isinstance(g, str):
            return g if g in by_group else fallback_group
        return fallback_group

    # Normalise & filtre
    items: List[Dict[str, Any]] = []
    for it in rows or []:
        symbol = (it.get("symbol") or it.get("name") or it.get("coin") or "").strip()
        alias = (it.get("alias") or it.get("name") or symbol or "").strip()
        v = it.get("value_usd")
        if v is None:
            v = it.get("usd_value")
        value_usd = float(v or 0.0)
        if value_usd < float(min_usd or 0.0):
            continue
        g = pick_group_for_alias(alias)
        items.append({
            "group": g,
            "alias": alias or symbol,
            "symbol": symbol,
            "value_usd": value_usd,
            "location": it.get("location") or "unknown",
        })

    total_usd = sum(x["value_usd"] for x in items) or 0.0

    # Répartition courante par groupe
    current_by_group: Dict[str, float] = {g: 0.0 for g in groups_order}
    for it in items:
        current_by_group[it["group"]] = current_by_group.get(it["group"], 0.0) + it["value_usd"]

    current_weights_pct = {
        g: round(100.0 * (current_by_group.get(g, 0.0) / total_usd), 3) if total_usd else 0.0
        for g in groups_order
    }

    # Cibles
    # On garde les pct tels que reçus (tu peux normaliser si tu veux)
    target_weights_pct = {k: float(v) for k, v in (group_targets_pct or {}).items()}
    targets_usd = {g: round(total_usd * (target_weights_pct.get(g, 0.0) / 100.0), 2) for g in groups_order}
    deltas_by_group_usd = {g: round(targets_usd.get(g, 0.0) - current_by_group.get(g, 0.0), 2) for g in groups_order}

    # Index par groupe (positions actuelles)
    for it in items:
        by_group[it["group"]].append(it)

    # Helpers d’allocation
    def allocate_proportional(total: float, buckets: List[Tuple[str, float]]) -> Dict[str, float]:
        """
        buckets: [(alias, poids_de_répartition >=0)]
        Retourne {alias: usd_alloué} somme ≈ total
        """
        alloc: Dict[str, float] = {}
        base = sum(max(w, 0.0) for _, w in buckets)
        if base <= 0:
            # si pas de base, on répartit à parts égales
            n = len(buckets)
            if n == 0:
                return {}
            q = round(total / n, 2)
            # ajustement ultime sur le 1er pour retomber pile au total
            running = 0.0
            for i, (a, _) in enumerate(buckets):
                if i < n - 1:
                    alloc[a] = q
                    running += q
                else:
                    alloc[a] = round(total - running, 2)
            return alloc

        # allocation proportionnelle
        running = 0.0
        for i, (a, w) in enumerate(buckets):
            if i < len(buckets) - 1:
                x = round(total * (max(w, 0.0) / base), 2)
                alloc[a] = x
                running += x
            else:
                alloc[a] = round(total - running, 2)
        return alloc

    actions: List[Dict[str, Any]] = []

    # 1) VENTES (groupes surpondérés) – proportionnel au poids des positions du groupe
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta >= -1e-9:
            continue
        to_sell = -delta  # positif
        positions = by_group.get(g, [])
        # buckets par alias dans ce groupe
        buckets: Dict[str, float] = {}
        for p in positions:
            a = p["alias"]
            buckets[a] = buckets.get(a, 0.0) + p["value_usd"]
        alloc = allocate_proportional(to_sell, list(buckets.items()))
        for alias, usd in alloc.items():
            if abs(usd) < 1e-9:
                continue
            actions.append({
                "group": g, "alias": alias, "symbol": alias,  # symbol = alias (agrégé)
                "action": "sell",
                "usd": -round(usd, 2),
                "est_quantity": None,
                "price_used": None,
            })

    # 2) ACHATS (groupes sous-pondérés) – répartis sur primary_symbols[g] si fourni, sinon proportionnel aux alias existants
    ps = primary_symbols or {}
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta <= 1e-9:
            continue
        to_buy = delta  # positif
        positions = by_group.get(g, [])

        primary_list = [s.strip() for s in (ps.get(g) or []) if isinstance(s, str) and s.strip()]
        if primary_list:
            # parts égales sur les primary
            buckets = [(a, 1.0) for a in primary_list]
        else:
            # sinon proportionnel au poids existant des alias du groupe
            agg: Dict[str, float] = {}
            for p in positions:
                a = p["alias"]
                agg[a] = agg.get(a, 0.0) + p["value_usd"]
            # si pas de positions (groupe vide), on met tout sur le nom du groupe
            buckets = list(agg.items()) if agg else [(g, 1.0)]

        alloc = allocate_proportional(to_buy, buckets)
        for alias, usd in alloc.items():
            if abs(usd) < 1e-9:
                continue
            actions.append({
                "group": g, "alias": alias, "symbol": alias,
                "action": "buy",
                "usd": round(usd, 2),
                "est_quantity": None,
                "price_used": None,
            })

    # 3) Filtre min_trade_usd + petit rééquilibrage pour net ≈ 0
    actions = [a for a in actions if abs(a["usd"]) >= float(min_trade_usd or 0.0)]

    net = round(sum(a["usd"] for a in actions), 2)
    if abs(net) >= 0.01 and actions:
        # on compense sur la plus grosse action en valeur absolue
        idx = max(range(len(actions)), key=lambda i: abs(actions[i]["usd"]))
        actions[idx]["usd"] = round(actions[idx]["usd"] - net, 2)
        net = round(sum(a["usd"] for a in actions), 2)

    # Vérifie à la fois les alias et groupes existants
    known_aliases = set(tx.aliases.keys())
    known_groups = set(tx.groups_order or [])
    
    unknown_aliases_set = {
        it["alias"] for it in items
        if it["alias"]
        and it["alias"] not in known_aliases
        and it["alias"] not in known_groups
    }

    return {
        "total_usd": round(total_usd, 2),
        "current_by_group": {g: round(current_by_group.get(g, 0.0), 2) for g in groups_order},
        "current_weights_pct": current_weights_pct,
        "target_weights_pct": {g: round(float(group_targets_pct.get(g, 0.0)), 3) for g in groups_order},
        "targets_usd": {g: round(targets_usd.get(g, 0.0), 2) for g in groups_order},
        "deltas_by_group_usd": {g: round(deltas_by_group_usd.get(g, 0.0), 2) for g in groups_order},
        "actions": actions,
        "advice": [],
        "unknown_aliases": sorted(list(unknown_aliases_set)),
    }

