# services/rebalance.py
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from api.taxonomy import Taxonomy

L1L0_MAJORS = {
    "XRP","BNB","XMR","ADA","NEAR","ATOM","XLM","SUI","TRX","LTC","DOT","AVAX",
    "XTZ","EGLD","ETC","TON","ALGO","KAVA","FIL","TIA","APT","ICP",
}

STABLES = {"USD","USDT","USDC","EUR","TUSD"}

def _group_for_alias(alias: str) -> str:
    a = alias.upper()
    if a == "BTC":
        return "BTC"
    if a == "ETH":
        return "ETH"
    if a in STABLES:
        return "Stablecoins"
    if a == "SOL":
        return "SOL"
    if a in L1L0_MAJORS:
        return "L1/L0 majors"
    return "Others"

def _normalize_rows(raw_rows: List[Dict[str, Any]], aliases_map: Dict[str, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in raw_rows:
        sym = str(r.get("symbol", "")).upper()
        usd = float(r.get("usd_value") or r.get("value_usd") or 0.0)
        alias = aliases_map.get(sym, sym)  # si pas mappé, alias = symbole
        grp = _group_for_alias(alias)
        rows.append({
            "symbol": sym,
            "alias": alias,
            "group": grp,
            "value_usd": usd,
        })
    return rows

def _sum_by_group(rows: List[Dict[str, Any]]) -> Tuple[float, Dict[str, float]]:
    totals: Dict[str, float] = defaultdict(float)
    total = 0.0
    for r in rows:
        usd = float(r["value_usd"])
        totals[r["group"]] += usd
        total += usd
    return total, totals

def _proportions(items: List[Tuple[str,float]]) -> List[Tuple[str,float]]:
    s = sum(v for _, v in items)
    if s <= 0:
        n = len(items) or 1
        return [(k, 1.0/n) for k,_ in items]
    return [(k, v/s) for k, v in items]

def _round2(x: float) -> float:
    return round(float(x), 2)

def plan_rebalance(
    rows: List[Dict[str, Any]],
    group_targets_pct: Dict[str, float],
    min_usd: float,
    sub_allocation: str = "proportional",
    primary_symbols: Dict[str, List[str]] | None = None,
    min_trade_usd: float = 25.0,
) -> Dict[str, Any]:
    """
    - primary_symbols: dict { "BTC": ["BTC","TBTC","WBTC"], "ETH": [...], "SOL": [...] }
      S'applique **uniquement** aux ACHATS (pas aux ventes).
    - min_trade_usd: filtre les lignes d'action très petites.
    """
    tx = Taxonomy.load()
    norm_rows = _normalize_rows(rows, tx.aliases)

    total_usd, curr_by_group = _sum_by_group(norm_rows)
    # poids actuels
    curr_weights = {g: _round2(100.0 * v / total_usd) if total_usd > 0 else 0.0
                    for g, v in curr_by_group.items()}

    # cibles en USD
    targets_usd: Dict[str, float] = {}
    for g, pct in group_targets_pct.items():
        targets_usd[g] = _round2(total_usd * float(pct) / 100.0)

    # deltas
    deltas_by_group: Dict[str, float] = {
        g: _round2(targets_usd.get(g, 0.0) - curr_by_group.get(g, 0.0))
        for g in tx.groups_order
    }

    # regrouper par (group -> alias -> [(symbol, usd)])
    by_group_alias: Dict[str, Dict[str, List[Tuple[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for r in norm_rows:
        by_group_alias[r["group"]][r["alias"]].append((r["symbol"], float(r["value_usd"])))

    actions: List[Dict[str, Any]] = []

    # VENTES : pour les groupes en excès (delta < 0), on vend proportionnellement aux positions détenues
    for g, delta in deltas_by_group.items():
        if delta >= 0:
            continue
        sell_left = abs(delta)
        # vente d'abord dans toutes les alias de ce groupe, proportionnelles
        for alias, sym_list in by_group_alias.get(g, {}).items():
            # proportion par symbole au sein de l'alias
            for sym, usd in _proportions(sym_list):
                amount = _round2(sell_left * usd)  # usd = proportion (0..1)
                if amount >= min_trade_usd:
                    actions.append({
                        "group": g, "alias": alias, "symbol": sym,
                        "action": "sell", "usd": -amount,
                        "est_quantity": None, "price_used": None
                    })
            # on a vendu sur l'ensemble du groupe ; on stop après répartition
            # car on a pris sell_left proportionnellement
            break

    # ACHATS : pour les groupes en manque (delta > 0)
    prim = {k.upper(): [s.upper() for s in v] for k, v in (primary_symbols or {}).items()}
    for g, delta in deltas_by_group.items():
        if delta <= 0:
            continue
        buy_left = float(delta)

        # choix des symboles cibles :
        # - si primary_symbols[g] existe : on achète sur cet ensemble (même s'ils ne sont pas déjà détenus)
        # - sinon : on répartit proportionnellement aux positions détenues dans ce groupe
        target_symbols: List[Tuple[str, str]] = []  # (alias, symbol)
        if g in prim and prim[g]:
            # alias de ce groupe = pour BTC -> "BTC", ETH -> "ETH", SOL -> "SOL", Stables -> on force "USD"
            if g == "Stablecoins":
                alias_name = "USD"
                for sym in prim[g]:
                    if sym in {"USD","USDT","USDC","EUR","TUSD"}:
                        target_symbols.append((sym, sym))
                if not target_symbols:
                    target_symbols.append((alias_name, alias_name))
            else:
                alias_name = g if g in {"BTC","ETH","SOL"} else None
                # si pas alias direct (L1/L0/ou Others), on achète proportionnellement à ce qu'on détient
                if alias_name:
                    for sym in prim[g]:
                        target_symbols.append((alias_name, sym))
        if not target_symbols:
            # fallback: proportionnel sur ce qu'on détient
            sym_list_all: List[Tuple[str, float]] = []
            for alias, sym_list in by_group_alias.get(g, {}).items():
                for sym, usd in sym_list:
                    sym_list_all.append((f"{alias}:{sym}", usd))
            if not sym_list_all:
                # rien détenu ; si Stablecoins à acheter, on prend USD
                if g == "Stablecoins":
                    target_symbols = [("USD","USD")]
                elif g in {"BTC","ETH","SOL"}:
                    target_symbols = [(g, g)]
                else:
                    # groupe flou sans positions et sans primary -> on ne crée pas d'achats
                    target_symbols = []
            else:
                for id_combined, prop in _proportions(sym_list_all):
                    alias_name, sym = id_combined.split(":", 1)
                    target_symbols.append((alias_name, sym))

        # répartition des achats
        if target_symbols:
            # si target_symbols est une liste (alias,symbol), on répartit égalitairement
            n = len(target_symbols)
            for alias, sym in target_symbols:
                amount = _round2(buy_left / n)
                if amount >= min_trade_usd:
                    actions.append({
                        "group": g, "alias": alias, "symbol": sym,
                        "action": "buy", "usd": amount,
                        "est_quantity": None, "price_used": None
                    })

    # Filtre min_trade_usd (au cas où)
    actions = [a for a in actions if abs(float(a["usd"])) >= float(min_trade_usd)]

    # Ajustement net → ~0
    net = _round2(sum(a["usd"] for a in actions))
    if abs(net) >= 0.01:
        # On compense côté stablecoin USD si présent sinon on n'ajoute rien.
        actions.append({
            "group": "Stablecoins", "alias": "USD", "symbol": "USD",
            "action": ("sell" if net > 0 else "buy"),
            "usd": -net,
            "est_quantity": None, "price_used": None
        })

    # unknown_aliases (dans ce plan) = symboles non mappés par taxonomy
    unknown = sorted({
        r["symbol"]
        for r in rows
        if r.get("symbol") and r["symbol"].upper() not in tx.aliases
    })

    result = {
        "total_usd": _round2(total_usd),
        "current_by_group": {g: _round2(v) for g, v in curr_by_group.items()},
        "current_weights_pct": curr_weights,
        "target_weights_pct": {g: float(p) for g, p in group_targets_pct.items()},
        "targets_usd": {g: _round2(v) for g, v in targets_usd.items()},
        "deltas_by_group_usd": deltas_by_group,
        "actions": actions,
        "advice": [],
        "unknown_aliases": unknown,
    }
    return result
