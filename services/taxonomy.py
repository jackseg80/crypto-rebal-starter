# services/taxonomy.py
from __future__ import annotations

import json, os
from dataclasses import dataclass, field
from typing import Dict, List

# Ordre de référence des groupes (libellés exacts utilisés partout)
DEFAULT_GROUPS_ORDER: List[str] = [
    "BTC",
    "ETH",
    "Stablecoins",
    "SOL",
    "L1/L0 majors",
    "Others",
]

# Mapping par défaut : symbole/alias -> groupe (canonique)
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
    "DAI": "Stablecoins",
    "USD": "Stablecoins",
    "USDT": "Stablecoins",
    "USDC": "Stablecoins",
    "USDP": "Stablecoins",
    "EUR": "Stablecoins",
    "TUSD": "Stablecoins",

    # L1/L0 majors
    "ADA": "L1/L0 majors",
    "ALGO": "L1/L0 majors",
    "APT": "L1/L0 majors",
    "ATOM": "L1/L0 majors",
    "AVAX": "L1/L0 majors",
    "BNB": "L1/L0 majors",
    "DOT": "L1/L0 majors",
    "EGLD": "L1/L0 majors",
    "ETC": "L1/L0 majors",
    "FIL": "L1/L0 majors",
    "ICP": "L1/L0 majors",
    "KAVA": "L1/L0 majors",
    "LTC": "L1/L0 majors",
    "NEAR": "L1/L0 majors",
    "SUI": "L1/L0 majors",
    "TIA": "L1/L0 majors",
    "TON": "L1/L0 majors",
    "TRX": "L1/L0 majors",
    "XLM": "L1/L0 majors",
    "XMR": "L1/L0 majors",
    "XRP": "L1/L0 majors",
    "XTZ": "L1/L0 majors",

    # Divers alias techniques -> alias “humain”
    "TONCOIN": "L1/L0 majors",
    "APT3": "L1/L0 majors",
    "TAO6": "Others",
    "VVV3": "Others",
    "WLD3": "Others",
    "GMT5": "Others",
    "LUNA2": "Others",
    "LUNA3": "Others",
    "S5": "Others",
    "SPX3": "Others",
    "SEI2": "Others",
    "FLR2": "Others",
    "JUP2": "Others",
    "WAL3": "Others",

    # Par défaut, tout ce qui n’est pas mappé => Others (géré dynamiquement)
}

def _storage_path() -> str:
    """
    Emplacement de persistance.
    - Si TAXONOMY_FILE est défini, on l'utilise.
    - Sinon, ./taxonomy.json (cwd).
    """
    return os.environ.get("TAXONOMY_FILE", os.path.join(os.getcwd(), "data", "taxonomy.json"))

def _keynorm(s: str) -> str:
    # Normalisation pour comparer sans casse/espaces
    return "".join(str(s).split()).upper()

def _canonical_group(name: str, groups: List[str]) -> str:
    """
    Retourne le nom de groupe tel qu'il apparaît dans groups_order
    (comparaison insensible à la casse/espaces). Si non trouvé,
    on retourne tel quel (permet des groupes personnalisés).
    """
    if not name:
        return name
    k = _keynorm(name)
    for g in groups:
        if _keynorm(g) == k:
            return g
    return name

def _canonicalize_alias_mapping(aliases: Dict[str, str], groups: List[str]) -> Dict[str, str]:
    """
    S'assure que:
    - toutes les clés (symboles/aliases) sont en MAJUSCULES
    - toutes les valeurs (groupes) sont les libellés exacts de groups_order
      quand c'est possible.
    """
    fixed: Dict[str, str] = {}
    for sym, grp in (aliases or {}).items():
        sym_u = str(sym).upper()
        canon_grp = _canonical_group(str(grp), groups)
        fixed[sym_u] = canon_grp
    return fixed

@dataclass
class Taxonomy:
    groups_order: List[str] = field(default_factory=lambda: list(DEFAULT_GROUPS_ORDER))
    # aliases: symbole/alias -> groupe (libellé exact)
    aliases: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ALIASES))

    _instance = None  # Singleton instance
    
    @classmethod
    def load(cls, reload: bool = False) -> "Taxonomy":
        if cls._instance and not reload:
            return cls._instance
            
        path = _storage_path()
        # Base par défaut
        t = cls()

        if not os.path.exists(path):
            # Pas de fichier => on garde les défauts
            return t

        # Lecture tolerant BOM
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        # groups_order
        groups = data.get("groups_order")
        if isinstance(groups, list) and groups:
            t.groups_order = [str(g) for g in groups]

        # aliases (symbol/alias -> group)
        raw_aliases = data.get("aliases")
        if isinstance(raw_aliases, dict):
            # Merge avec défauts, puis canonisation
            merged = dict(DEFAULT_ALIASES)
            for k, v in raw_aliases.items():
                merged[str(k).upper()] = str(v)
            t.aliases = _canonicalize_alias_mapping(merged, t.groups_order)
        else:
            # seulement canoniser les défauts
            t.aliases = _canonicalize_alias_mapping(t.aliases, t.groups_order)

        return t

    def save(self) -> None:
        path = _storage_path()
        data = {
            "groups_order": self.groups_order,
            "aliases": self.aliases,
        }
        # Écriture UTF-8 (sans BOM)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # === API utilitaires ===

    def group_for_alias(self, alias: str) -> str:
        """
        Retourne le groupe pour un alias/symbole donné.
        - si l'alias est déjà un groupe (ex: "Stablecoins"), on renvoie la version canonique
        - sinon on cherche dans le mapping
        - sinon fallback "Others"
        """
        if not alias:
            return "Others"
        # match direct contre un libellé de groupe
        cg = _canonical_group(alias, self.groups_order)
        if _keynorm(cg) in {_keynorm(g) for g in self.groups_order}:
            # alias fourni == un libellé de groupe
            return cg

        # lookup alias/symbole
        grp = self.aliases.get(str(alias).upper())
        if grp:
            return _canonical_group(grp, self.groups_order)

        # fallback
        return "Others"

    def to_dict(self) -> Dict[str, object]:
        return {
            "groups_order": list(self.groups_order),
            "aliases": dict(self.aliases),
        }
