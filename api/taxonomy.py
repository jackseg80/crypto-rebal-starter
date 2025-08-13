# api/taxonomy.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, DefaultDict
from collections import defaultdict

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TAXO_PATH = DATA_DIR / "taxonomy.json"

_DEFAULT = {
    "groups_order": ["BTC", "ETH", "Stablecoins", "SOL", "L1/L0 majors", "Others"],
    "aliases": {
        "BTC": ["BTC", "TBTC", "WBTC"],
        "ETH": ["ETH", "WSTETH", "STETH", "RETH", "WETH"],
        "SOL": ["SOL", "JUPSOL", "JITOSOL"],
        "Stablecoins": ["USD", "USDT", "USDC", "DAI", "USDP", "EUR", "TUSD"],
        "L1/L0 majors": [
            "XRP","BNB","XMR","ADA","NEAR","ATOM","XLM","SUI","TRX","LTC","DOT","AVAX",
            "XTZ","EGLD","ETC","TON","ALGO","KAVA","FIL","TIA","APT","ICP"
        ],
        "Others": []
    }
}

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

class Taxonomy:
    def __init__(self, groups_order: List[str], aliases: Dict[str, List[str]]):
        # tout en MAJ
        self.groups_order = list(groups_order)
        self.aliases: Dict[str, List[str]] = {
            g: sorted({a.upper() for a in lst}) for g, lst in aliases.items()
        }

    @classmethod
    def load(cls) -> "Taxonomy":
        data = _load_json(TAXO_PATH)
        if not data:
            _save_json(TAXO_PATH, _DEFAULT)
            data = _DEFAULT
        groups_order = data.get("groups_order") or _DEFAULT["groups_order"]
        aliases = data.get("aliases") or _DEFAULT["aliases"]
        # normalise les clés de groupes
        aliases = {str(g): [a.upper() for a in lst] for g, lst in aliases.items()}
        return cls(groups_order=groups_order, aliases=aliases)

    def save(self) -> None:
        _save_json(TAXO_PATH, {"groups_order": self.groups_order, "aliases": self.aliases})

    def to_dict(self) -> dict:
        return {"groups_order": self.groups_order, "aliases": self.aliases}

    def group_of_alias(self, alias: str) -> Optional[str]:
        if not alias:
            return None
        a = alias.upper()
        for g, lst in self.aliases.items():
            if a in lst:
                return g
        return None

    def add_mapping(self, alias: str, group: str) -> None:
        a = alias.upper()
        if group not in self.aliases:
            self.aliases[group] = []
        # enlever des autres groupes s'il existait
        for gg, lst in self.aliases.items():
            if gg != group and a in lst:
                lst.remove(a)
        if a not in self.aliases[group]:
            self.aliases[group].append(a)

    def unknown_aliases_from_rows(self, rows: List[Dict[str, Any]], min_usd: float = 0.0) -> List[Dict[str, Any]]:
        acc: Dict[str, float] = {}
        for r in rows:
            alias = (r.get("alias") or r.get("name") or r.get("symbol") or "").upper()
            usd = float(r.get("value_usd") or r.get("usd_value") or r.get("usd") or 0.0)
            if usd < min_usd:
                continue
            if self.group_of_alias(alias) is None:
                acc[alias] = acc.get(alias, 0.0) + usd
        return [{"alias": a, "total_usd": v} for a, v in sorted(acc.items(), key=lambda kv: kv[1], reverse=True)]

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # Agrégation principale utilisée par /portfolio/groups et le plan
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    def aggregate(self, rows: List[Dict[str, Any]], min_usd: float = 1.0) -> Dict[str, Any]:
        groups_map: Dict[str, Dict[str, Any]] = {
            g: {"group": g, "total_usd": 0.0, "items": []} for g in self.groups_order
        }
        unknown_acc: DefaultDict[str, float] = defaultdict(float)

        total_usd = 0.0

        for r in rows or []:
            symbol = (r.get("symbol") or r.get("name") or "").upper()
            alias = (r.get("alias") or symbol).upper()
            value_usd = float(r.get("value_usd") or r.get("usd_value") or r.get("usd") or 0.0)
            amount = float(r.get("amount") or 0.0)
            location = r.get("location")

            if value_usd < float(min_usd):
                continue

            group = self.group_of_alias(alias)
            if group is None:
                # on range en "Others" mais on remonte aussi dans unknown_aliases
                unknown_acc[alias] += value_usd
                group = "Others"
                if group not in groups_map:
                    groups_map[group] = {"group": group, "total_usd": 0.0, "items": []}

            groups_map[group]["items"].append({
                "symbol": symbol,
                "alias": alias,
                "amount": amount,
                "value_usd": value_usd,
                "location": location
            })
            groups_map[group]["total_usd"] += value_usd
            total_usd += value_usd

        # ordonner les groupes dans l’ordre défini et calc % poids
        ordered_groups: List[Dict[str, Any]] = []
        for g in self.groups_order:
            if g in groups_map:
                ordered_groups.append(groups_map[g])
        # ajouter les groupes éventuels ajoutés à chaud
        for g, data in groups_map.items():
            if g not in self.groups_order:
                ordered_groups.append(data)

        for g in ordered_groups:
            g["weight_pct"] = (g["total_usd"] / total_usd * 100.0) if total_usd > 0 else 0.0

        unknown_aliases = [
            {"alias": a, "total_usd": v} for a, v in sorted(unknown_acc.items(), key=lambda kv: kv[1], reverse=True)
        ]

        return {
            "total_usd": total_usd,
            "groups": ordered_groups,
            "unknown_aliases": unknown_aliases,
        }
