# api/taxonomy.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import re

# ---------------------------
# 1) Alias & Groupes par défaut
# ---------------------------

# Stablecoins (incluant devises fiat vues par CoinTracking)
STABLES = {
    "USDT","USDC","DAI","FDUSD","TUSD","BUSD","USDBC","USDCE","USDC.E",
    "EURT","EUR","USD","CHF"
}

# Variantes à re-mapper vers un alias "maître"
VARIANTS = {
    # BTC
    "TBTC":"BTC", "WBTC":"BTC", "BTCB":"BTC",
    # ETH
    "WETH":"ETH","STETH":"ETH","WSTETH":"ETH","RETH":"ETH","CBETH":"ETH","BETH3":"ETH",
    # SOL
    "SOL2":"SOL","JITOSOL":"SOL","JUPSOL":"SOL",
    # Autres cas fréquents vus dans ton dump
    "ATOM2":"ATOM","DOT2":"DOT","IOTA2":"IOTA","ICP2":"ICP","EGLD3":"EGLD",
    "FIL":"FIL","NEAR":"NEAR","AVAX":"AVAX","ADA":"ADA","BNB":"BNB","TRX":"TRX",
    "XRP":"XRP","XLM":"XLM","LTC":"LTC","ETC":"ETC","TONCOIN":"TON","TIA3":"TIA",
    "SUI3":"SUI","APT3":"APT"
}

# L1/L0 majeurs (hors BTC/ETH/SOL)
L1_L0_MAJORS = {
    "ADA","AVAX","ATOM","NEAR","DOT","KAVA","ALGO","ICP","EGLD","FIL",
    "TRX","XRP","XLM","LTC","ETC","TON","SUI","TIA","APT","BNB","XMR","XTZ"
}

# Ordre d’affichage
GROUP_ORDER = ["BTC","ETH","Stablecoins","SOL","L1/L0 majors","Others"]

@dataclass(frozen=True)
class Row:
    symbol: str
    amount: float
    value_usd: float
    # facultatif: exchange/wallet pour la suite
    location: str | None = None

class Taxonomy:
    def __init__(self,
                 stables: set[str] = STABLES,
                 variants: Dict[str,str] = VARIANTS,
                 l1majors: set[str] = L1_L0_MAJORS):
        self.stables = set(s.upper() for s in stables)
        self.variants = {k.upper(): v.upper() for k,v in variants.items()}
        self.l1majors = set(s.upper() for s in l1majors)

    # --- Normalisation symboles -> alias maître
    def normalize_symbol(self, sym: str) -> str:
        s = (sym or "").upper().strip()

        # enlever suffixes purement numériques (ex: "ATOM2" -> "ATOM")
        base = re.sub(r"\d+$", "", s)

        # appliquer le mapping variantes -> alias
        if s in self.variants:
            return self.variants[s]
        if base in self.variants:
            return self.variants[base]
        return base

    # --- Déterminer le groupe d’un alias
    def group_of_alias(self, alias: str) -> str:
        a = alias.upper()
        if a == "BTC":
            return "BTC"
        if a == "ETH":
            return "ETH"
        if a in self.stables:
            return "Stablecoins"
        if a == "SOL":
            return "SOL"
        if a in self.l1majors:
            return "L1/L0 majors"
        return "Others"

    # --- Agrégation
    def aggregate(self, rows: List[Dict[str, Any]], min_usd: float = 1.0) -> Dict[str, Any]:
        """
        rows: liste de dicts {"symbol","amount","value_usd", ...}
        """
        normalized: List[Tuple[Row, str, str]] = []
        portfolio_total = 0.0

        for r in rows:
            try:
                symbol = str(r.get("symbol","")).upper()
                amount = float(r.get("amount", 0) or 0)
                value_usd = float(r.get("value_usd", 0) or 0)
                location = r.get("location")
            except Exception:
                continue

            if value_usd < min_usd:
                continue

            alias = self.normalize_symbol(symbol)
            group = self.group_of_alias(alias)
            normalized.append((Row(symbol, amount, value_usd, location), alias, group))
            portfolio_total += value_usd

        # totaux par groupe et détail
        groups: Dict[str, Dict[str, Any]] = {g: {"group": g, "total_usd": 0.0, "items": []} for g in GROUP_ORDER}
        groups.setdefault("Others", {"group":"Others","total_usd":0.0,"items":[]})

        unknown_aliases = set()

        for row, alias, group in normalized:
            if group not in groups:
                groups[group] = {"group": group, "total_usd": 0.0, "items": []}
            groups[group]["total_usd"] += row.value_usd
            groups[group]["items"].append({
                "symbol": row.symbol,
                "alias": alias,
                "amount": row.amount,
                "value_usd": row.value_usd,
                "location": row.location
            })

            # tracer les alias qui finissent dans Others (potentiel need de mapping)
            if group == "Others" and alias not in STABLES and alias not in {"BTC","ETH","SOL"} and alias not in L1_L0_MAJORS:
                unknown_aliases.add(alias)

        # formater la sortie
        ordered_groups = [groups[g] for g in GROUP_ORDER if g in groups] + \
                         [v for k,v in groups.items() if k not in GROUP_ORDER]

        # poids %
        for g in ordered_groups:
            g["weight_pct"] = (g["total_usd"] / portfolio_total * 100.0) if portfolio_total > 0 else 0.0

        return {
            "total_usd": portfolio_total,
            "groups": ordered_groups,
            "unknown_aliases": sorted(unknown_aliases),
        }
