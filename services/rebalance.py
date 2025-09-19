from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
from constants import get_exchange_priority, normalize_exchange_name, format_exec_hint
from services.taxonomy import Taxonomy

log = logging.getLogger(__name__)


def _keynorm(s: str) -> str:
    return "".join(str(s).split()).upper()


def _format_hint_for_location(location: str, action_type: str) -> str:
    return format_exec_hint(location, action_type)


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
# Priority allocation helpers
# ------------------------------------------------------------------

def _allocate_priority_buy(total_usd: float, scored_coins: List, config: Dict[str, Any],
                          pinned: List[str], blacklist: List[str], min_trade_usd: float) -> Dict[str, float]:
    """
    Alloue un montant total selon le mode priority (Top-N + decay/softmax).

    Returns:
        Dict[alias, usd_amount]
    """
    if total_usd <= 0 or not scored_coins:
        return {}

    allocation_config = config.get("allocation", {})
    top_n = allocation_config.get("top_n", 3)
    distribution_mode = allocation_config.get("distribution_mode", "decay")
    decay_weights = allocation_config.get("decay", [0.5, 0.3, 0.2])
    softmax_temp = allocation_config.get("softmax_temp", 1.0)

    # Filtrer selon pinned/blacklist
    filtered_coins = []
    for coin in scored_coins:
        alias = coin.meta.alias.upper()
        if alias in blacklist:
            continue
        filtered_coins.append(coin)

    # Priorité aux pinned
    pinned_coins = [c for c in filtered_coins if c.meta.alias.upper() in pinned]
    other_coins = [c for c in filtered_coins if c.meta.alias.upper() not in pinned]

    # Sélection Top-N
    selected_coins = pinned_coins + other_coins[:max(0, top_n - len(pinned_coins))]
    selected_coins = selected_coins[:top_n]

    if not selected_coins:
        log.warning("No coins selected after filtering")
        return {}

    # Distribution des poids
    if distribution_mode == "decay" and len(decay_weights) >= len(selected_coins):
        weights = decay_weights[:len(selected_coins)]
    elif distribution_mode == "softmax":
        scores = [coin.score for coin in selected_coins]
        max_score = max(scores) if scores else 0
        exp_scores = [exp((score - max_score) / softmax_temp) for score in scores]
        total_exp = sum(exp_scores)
        weights = [exp_score / total_exp for exp_score in exp_scores] if total_exp > 0 else [1.0 / len(selected_coins)] * len(selected_coins)
    else:
        # Fallback égal
        weights = [1.0 / len(selected_coins)] * len(selected_coins)

    # Normalisation des poids
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # Allocation finale
    allocation = {}
    remaining = total_usd

    for i, (coin, weight) in enumerate(zip(selected_coins, weights)):
        if i == len(selected_coins) - 1:
            # Dernière allocation : tout le reste
            amount = remaining
        else:
            amount = round(total_usd * weight, 2)
            remaining -= amount

        if amount >= min_trade_usd:
            allocation[coin.meta.alias] = amount

    log.debug(f"Priority allocation: {len(allocation)} coins, total {sum(allocation.values()):.2f} USD")
    return allocation


def _prioritize_sell_targets(hold_by_alias: Dict[str, Dict[str, float]], scored_coins: List,
                           pinned: List[str], min_trade_usd: float) -> List[Tuple[str, str, float]]:
    """
    Priorise les cibles de vente : score faible d'abord, en respectant les pinned.

    Returns:
        List[(alias, location, max_amount)] triée par priorité de vente
    """
    # Créer un mapping score par alias
    score_by_alias = {}
    for coin in scored_coins:
        score_by_alias[coin.meta.alias.upper()] = coin.score

    # Préparer les cibles de vente
    sell_targets = []
    for alias, locations in hold_by_alias.items():
        if alias.upper() in pinned:
            continue  # Skip pinned

        score = score_by_alias.get(alias.upper(), 0.0)

        for location, amount in locations.items():
            if amount >= min_trade_usd:
                sell_targets.append((alias, location, amount, score))

    # Tri par score croissant (pires scores en premier)
    sell_targets.sort(key=lambda x: x[3])

    # Retourner sans le score
    return [(alias, loc, amount) for alias, loc, amount, _ in sell_targets]


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

    def prio(loc: str) -> int:
        return get_exchange_priority(loc)

    def fmt_hint(loc: str, action_type: str) -> str:
        return format_exec_hint(loc, action_type)

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
        loc = normalize_exchange_name(it.get("location") or "Unknown")
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

    # ---------- PRIORITY MODE HANDLING ----------
    priority_universe = None
    universe_fallbacks = set()  # Groupes qui retombent en proportionnel

    if sub_allocation == "priority":
        try:
            from services.universe import get_universe_cached
            log.info(f"Attempting priority allocation for {len(groups_order)} groups")

            # Charger l'univers scoré avec le portfolio actuel
            priority_universe = get_universe_cached(
                groups=groups_order,
                current_portfolio=items,
                mode="prefer_cache"
            )

            if priority_universe:
                log.info(f"Priority universe loaded for {len(priority_universe)} groups")
            else:
                log.warning("Priority universe unavailable, falling back to proportional for all groups")
                universe_fallbacks.update(groups_order)

        except Exception as e:
            log.error(f"Priority mode failed, falling back to proportional: {e}")
            universe_fallbacks.update(groups_order)

    # ---------- VENTES : répartition par alias PUIS par location avec priorité ----------
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta >= -1e-9:
            continue
        to_sell = -delta

        # Mode de sélection des ventes selon sub_allocation
        if sub_allocation == "priority" and priority_universe and g in priority_universe and g not in universe_fallbacks:
            # MODE PRIORITY : vendre d'abord les faibles scores
            try:
                from services.universe import get_universe_manager
                config = get_universe_manager()._load_config()
                pinned = set(str(p).upper() for p in config.get("lists", {}).get("pinned_by_group", {}).get(g, []))

                scored_coins = priority_universe[g]
                group_hold_by_alias = hold_by_gal.get(g, {})

                # Obtenir les cibles prioritaires pour la vente
                sell_targets = _prioritize_sell_targets(group_hold_by_alias, scored_coins, pinned, min_trade_usd)

                remaining_to_sell = to_sell
                for alias, loc, capacity in sell_targets:
                    if remaining_to_sell <= 1e-9:
                        break

                    slice_usd = round(min(capacity, remaining_to_sell), 2)
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
                    remaining_to_sell = round(remaining_to_sell - slice_usd, 2)

                # Si on n'a pas pu tout vendre (pinned, min_trade_usd...), fallback proportionnel pour le reste
                if remaining_to_sell >= float(min_trade_usd or 0.0):
                    log.warning(f"UNIVERSE_FALLBACK_TO_PROPORTIONAL[g={g}] for remaining sell: {remaining_to_sell:.2f} USD")
                    # Fallback pour le reste seulement
                    agg_alias: Dict[str, float] = {}
                    for p in by_group.get(g, []):
                        a = p["alias"]
                        if a.upper() not in pinned:  # Exclure les pinned
                            remaining_capacity = hold_by_gal.get(g, {}).get(a, {})
                            total_capacity = sum(remaining_capacity.values()) - sum(
                                abs(action["usd"]) for action in actions
                                if action["group"] == g and action["alias"] == a and action["action"] == "sell"
                            )
                            if total_capacity > 0:
                                agg_alias[a] = total_capacity

                    alloc_alias = allocate_proportional(remaining_to_sell, list(agg_alias.items()))
                    # [Suite du code proportionnel pour le reste...]

                log.debug(f"Priority sell for group {g}: {len([a for a in actions if a['group']==g and a['action']=='sell'])} actions")
                continue  # Passer au groupe suivant

            except Exception as e:
                log.error(f"Priority sell failed for group {g}: {e}, falling back to proportional")
                universe_fallbacks.add(g)
                # Continuer vers le mode proportionnel ci-dessous

        # MODE PROPORTIONNEL (défaut ou fallback)
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

    # ---------- ACHATS : une seule location "meilleure" (simple) ----------
    ps = primary_symbols or {}
    for g in groups_order:
        delta = deltas_by_group_usd.get(g, 0.0)
        if delta <= 1e-9:
            continue
        to_buy = delta

        # Mode de sélection des achats selon sub_allocation
        if sub_allocation == "priority" and priority_universe and g in priority_universe and g not in universe_fallbacks:
            # MODE PRIORITY : acheter les meilleurs scores selon Top-N + decay
            try:
                from services.universe import get_universe_manager
                config = get_universe_manager()._load_config()
                blacklist = set(str(b).upper() for b in config.get("lists", {}).get("global_blacklist", []))
                pinned = [str(p).upper() for p in config.get("lists", {}).get("pinned_by_group", {}).get(g, [])]

                scored_coins = priority_universe[g]
                alloc_alias = _allocate_priority_buy(to_buy, scored_coins, config, pinned, blacklist, min_trade_usd)

                log.debug(f"Priority buy for group {g}: {len(alloc_alias)} coins, {sum(alloc_alias.values()):.2f} USD")

            except Exception as e:
                log.error(f"Priority buy failed for group {g}: {e}, falling back to proportional")
                universe_fallbacks.add(g)
                alloc_alias = None

            # Si priority a fonctionné, utiliser ses résultats
            if g not in universe_fallbacks and alloc_alias:
                pass  # alloc_alias est déjà défini
            else:
                # Fallback proportionnel
                alloc_alias = None

        else:
            # MODE PROPORTIONNEL (par défaut)
            alloc_alias = None

        # Fallback ou mode proportionnel
        if alloc_alias is None:
            prim = [s.strip() for s in (ps.get(g) or []) if isinstance(s, str) and s.strip()]
            # poids d'allocation par alias pour l'achat
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

    # Métadonnées priority mode pour debugging/UI
    priority_meta = {}
    if sub_allocation == "priority":
        priority_meta = {
            "mode": "priority",
            "universe_available": priority_universe is not None,
            "groups_with_fallback": sorted(list(universe_fallbacks)),
            "universe_groups": sorted(list(priority_universe.keys())) if priority_universe else [],
        }

        # Ajouter détails par groupe si univers disponible
        if priority_universe:
            priority_meta["groups_details"] = {}
            for g in groups_order:
                if g in priority_universe:
                    scored_coins = priority_universe[g]
                    top_3 = scored_coins[:3] if scored_coins else []
                    priority_meta["groups_details"][g] = {
                        "total_coins": len(scored_coins),
                        "top_suggestions": [
                            {
                                "alias": coin.meta.alias,
                                "score": round(coin.score, 3),
                                "rank": coin.meta.market_cap_rank,
                                "volume_24h": coin.meta.volume_24h,
                                "momentum_30d": coin.meta.price_change_30d
                            }
                            for coin in top_3
                        ],
                        "fallback_used": g in universe_fallbacks
                    }

    result = {
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

    # Ajouter métadonnées priority si applicable
    if priority_meta:
        result["priority_meta"] = priority_meta

    return result
