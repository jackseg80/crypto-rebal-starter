# api/taxonomy.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

DEFAULT_GROUPS_ORDER: List[str] = [
    "BTC",
    "ETH",
    "Stablecoins",
    "SOL",
    "L1/L0 majors",
    "Others",
]

# mapping symbole -> alias (alias sert à déterminer le groupe)
DEFAULT_ALIASES: Dict[str, str] = {
    # BTC
    "BTC": "BTC",
    "TBTC": "BTC",
    "WBTC": "BTC",

    # ETH
    "ETH": "ETH",
    "WETH": "ETH",
    "STETH": "ETH",
    "WSTETH": "ETH",
    "RETH": "ETH",

    # SOL
    "SOL": "SOL",
    "JUPSOL": "SOL",
    "JITOSOL": "SOL",

    # Stablecoins / cash
    "USD": "USD",
    "USDT": "USDT",
    "USDC": "USDC",
    "EUR": "EUR",
    "TUSD": "TUSD",

    # Divers alias → alias identique pour éviter "inconnu" par défaut
    "TONCOIN": "TON",
    "APT3": "APT",
    "TAO6": "TAO",
    "VVV3": "VVV",
    "WLD3": "WLD",
    "GMT5": "GMT",
    "LUNA2": "LUNA",
    "LUNA3": "LUNA",
    "S5": "S",
    "SPX3": "SPX",
    "SEI2": "SEI",
    "FLR2": "FLR",
    "JUP2": "JUP",
    "WAL3": "WAL",
}

def _storage_path() -> str:
    # Emplacement de persistance (env var ou ./taxonomy.json)
    return os.environ.get("TAXONOMY_FILE", os.path.join(os.getcwd(), "taxonomy.json"))

@dataclass
class Taxonomy:
    groups_order: List[str] = field(default_factory=lambda: list(DEFAULT_GROUPS_ORDER))
    aliases: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ALIASES))

    @classmethod
    def load(cls) -> "Taxonomy":
        path = _storage_path()
        if not os.path.exists(path):
            # première exécution : on laisse les valeurs par défaut
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # si fichier corrompu -> valeurs par défaut
            return cls()

        groups = data.get("groups_order")
        aliases = data.get("aliases")
        t = cls()
        if isinstance(groups, list) and groups:
            t.groups_order = [str(g) for g in groups]
        if isinstance(aliases, dict):
            # merge: on garde les défauts + on surcharge par le fichier
            merged = dict(DEFAULT_ALIASES)
            for k, v in aliases.items():
                merged[str(k).upper()] = str(v).upper()
            t.aliases = merged
        return t

    def save(self) -> None:
        path = _storage_path()
        data = {
            "groups_order": self.groups_order,
            "aliases": self.aliases,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
