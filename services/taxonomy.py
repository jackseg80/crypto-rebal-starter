# services/taxonomy.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

# Ordre de référence des groupes (libellés exacts utilisés partout)
DEFAULT_GROUPS_ORDER: List[str] = [
    "BTC",
    "ETH",
    "Stablecoins",
    "SOL",
    "L1/L0 majors",
    "L2/Scaling",
    "DeFi",
    "AI/Data",
    "Gaming/NFT",
    "Memecoins",
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

    # L2/Scaling
    "ARB": "L2/Scaling",
    "OP": "L2/Scaling",
    "MATIC": "L2/Scaling",
    "POL": "L2/Scaling", 
    "STRK": "L2/Scaling",
    "IMX": "L2/Scaling",
    "LRC": "L2/Scaling",
    "METIS": "L2/Scaling",

    # DeFi
    "UNI": "DeFi",
    "AAVE": "DeFi",
    "COMP": "DeFi",
    "MKR": "DeFi",
    "SNX": "DeFi",
    "CRV": "DeFi",
    "SUSHI": "DeFi",
    "1INCH": "DeFi",
    "YFI": "DeFi",
    "LDO": "DeFi",
    "RPL": "DeFi",
    "PENDLE": "DeFi",
    "RDNT": "DeFi",

    # AI/Data
    "FET": "AI/Data",
    "RENDER": "AI/Data",
    "TAO": "AI/Data",
    "OCEAN": "AI/Data",
    "GRT": "AI/Data",
    "WLD": "AI/Data",

    # Gaming/NFT
    "AXS": "Gaming/NFT",
    "SAND": "Gaming/NFT",
    "MANA": "Gaming/NFT",
    "ENJ": "Gaming/NFT",
    "GALA": "Gaming/NFT",
    "CHZ": "Gaming/NFT",
    "FLOW": "Gaming/NFT",

    # Memecoins
    "DOGE": "Memecoins",
    "SHIB": "Memecoins",
    "PEPE": "Memecoins",
    "BONK": "Memecoins",
    "WIF": "Memecoins",
    "FLOKI": "Memecoins",

    # Divers alias techniques -> alias "humain"
    "TONCOIN": "L1/L0 majors",
    "APT3": "L1/L0 majors",
    "TAO6": "AI/Data",
    "VVV3": "Others",
    "WLD3": "AI/Data",
    "GMT5": "Others",
    "LUNA2": "Others",
    "LUNA3": "Others",
    "S5": "Others",
    "SPX3": "Others",
    "SEI2": "L1/L0 majors",
    "FLR2": "L1/L0 majors",
    "JUP2": "Others",
    "WAL3": "Others",

    # Par défaut, tout ce qui n'est pas mappé => Others (géré dynamiquement)
}

# === CLASSIFICATION AUTOMATIQUE ===

# Règles de classification par motifs dans le symbole
AUTO_CLASSIFICATION_RULES = {
    # Stablecoins par pattern
    "stablecoins_patterns": [
        r".*USD[CT]?$",  # USDC, USDT, USD
        r".*DAI$",       # DAI, FRAX_DAI
        r".*BUSD$",      # BUSD
        r".*TUSD$",      # TUSD
        r".*GUSD$",      # GUSD
        r".*USDD$",      # USDD
        r".*FRAX$",      # FRAX
    ],
    
    # L2/Scaling par pattern
    "l2_patterns": [
        r".*ARB.*",      # Arbitrum ecosystem
        r".*OP$",        # Optimism
        r".*MATIC.*",    # Polygon
        r".*POL.*",      # POL tokens
        r".*STRK.*",     # Starknet
    ],
    
    # Memecoins par pattern
    "meme_patterns": [
        r".*DOGE.*",     # Dogecoin ecosystem
        r".*SHIB.*",     # Shiba ecosystem 
        r".*PEPE.*",     # Pepe variants
        r".*BONK.*",     # Bonk variants
        r".*WIF.*",      # WIF variants
        r".*FLOKI.*",    # Floki variants
        r".*MEME.*",     # Generic meme
        r".*MOON.*",     # Moon tokens
        r".*SAFE.*",     # Safe tokens (often memes)
    ],
    
    # AI/Data par keywords
    "ai_patterns": [
        r".*AI.*",       # AI tokens
        r".*GPT.*",      # GPT tokens
        r".*RENDER.*",   # Render variants
        r".*FET.*",      # Fetch.ai variants
        r".*OCEAN.*",    # Ocean Protocol
        r".*GRT.*",      # The Graph
    ],
    
    # Gaming/NFT par keywords
    "gaming_patterns": [
        r".*GAME.*",     # Gaming tokens
        r".*NFT.*",      # NFT tokens
        r".*SAND.*",     # Sandbox variants
        r".*MANA.*",     # Decentraland variants
        r".*AXS.*",      # Axie Infinity
        r".*ENJ.*",      # Enjin variants
        r".*GALA.*",     # Gala variants
    ]
}

def auto_classify_symbol(symbol: str) -> str:
    """
    Classification automatique d'un symbole crypto basée sur des patterns.
    Retourne le groupe suggéré ou "Others" si aucun pattern ne correspond.
    """
    import re
    
    if not symbol:
        return "Others"
    
    symbol_upper = symbol.upper()
    
    # Test patterns stablecoins
    for pattern in AUTO_CLASSIFICATION_RULES["stablecoins_patterns"]:
        if re.match(pattern, symbol_upper):
            return "Stablecoins"
    
    # Test patterns L2/Scaling
    for pattern in AUTO_CLASSIFICATION_RULES["l2_patterns"]:
        if re.match(pattern, symbol_upper):
            return "L2/Scaling"
    
    # Test patterns Memecoins
    for pattern in AUTO_CLASSIFICATION_RULES["meme_patterns"]:
        if re.match(pattern, symbol_upper):
            return "Memecoins"
    
    # Test patterns AI/Data
    for pattern in AUTO_CLASSIFICATION_RULES["ai_patterns"]:
        if re.match(pattern, symbol_upper):
            return "AI/Data"
    
    # Test patterns Gaming/NFT
    for pattern in AUTO_CLASSIFICATION_RULES["gaming_patterns"]:
        if re.match(pattern, symbol_upper):
            return "Gaming/NFT"
    
    # Fallback
    return "Others"

async def auto_classify_symbol_enhanced(symbol: str, use_coingecko: bool = True) -> str:
    """
    Classification automatique améliorée avec support CoinGecko.
    
    Args:
        symbol: Le symbole crypto à classifier
        use_coingecko: Utiliser CoinGecko comme source secondaire
    
    Returns:
        Le groupe suggéré ou "Others" si aucune classification trouvée
    """
    if not symbol:
        return "Others"
    
    # 1. D'abord, essayer les patterns regex existants
    regex_result = auto_classify_symbol(symbol)
    if regex_result != "Others":
        return regex_result
    
    # 2. Si échec et CoinGecko activé, essayer l'enrichissement
    if use_coingecko:
        try:
            from .coingecko import coingecko_service
            coingecko_result = await coingecko_service.classify_symbol(symbol)
            if coingecko_result:
                return coingecko_result
        except Exception as e:
            # Log l'erreur mais continue sans CoinGecko
            import logging
            logging.getLogger(__name__).debug(f"Erreur CoinGecko pour {symbol}: {e}")
    
    # 3. Fallback vers "Others"
    return "Others"

def get_classification_suggestions(unknown_symbols: List[str]) -> Dict[str, str]:
    """
    Génère des suggestions de classification pour une liste de symboles inconnus.
    Retourne un dictionnaire {symbol: suggested_group}
    """
    suggestions = {}
    for symbol in unknown_symbols:
        suggested_group = auto_classify_symbol(symbol)
        # Ne suggère que si ce n'est pas "Others" (pas de pattern trouvé)
        if suggested_group != "Others":
            suggestions[symbol.upper()] = suggested_group
    
    return suggestions

async def get_classification_suggestions_enhanced(unknown_symbols: List[str], use_coingecko: bool = True) -> Dict[str, str]:
    """
    Version améliorée avec support CoinGecko pour les suggestions de classification.
    
    Args:
        unknown_symbols: Liste des symboles à classifier
        use_coingecko: Utiliser CoinGecko comme source secondaire
    
    Returns:
        Dictionnaire {symbol: suggested_group} pour les symboles classifiés
    """
    suggestions = {}
    
    for symbol in unknown_symbols:
        suggested_group = await auto_classify_symbol_enhanced(symbol, use_coingecko)
        # Ne suggère que si ce n'est pas "Others" (pas de pattern trouvé)
        if suggested_group != "Others":
            suggestions[symbol.upper()] = suggested_group
    
    return suggestions

def _storage_path() -> str:
    """
    Emplacement de persistance - utilise le même fichier que les endpoints API.
    - Si TAXONOMY_FILE est défini, on l'utilise.
    - Sinon, data/taxonomy_aliases.json (même que API endpoints).
    """
    return os.environ.get("TAXONOMY_FILE", os.path.join(os.getcwd(), "data", "taxonomy_aliases.json"))

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

        if os.path.exists(path):
            # Lecture tolerant BOM
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)

            # Format des endpoints API : data = { "SYMBOL": "GROUP", ... }
            # Format ancien : data = { "groups_order": [...], "aliases": {...} }
            
            if isinstance(data, dict):
                if "groups_order" in data:
                    # Format ancien (structure complète)
                    groups = data.get("groups_order")
                    if isinstance(groups, list) and groups:
                        t.groups_order = [str(g) for g in groups]
                    raw_aliases = data.get("aliases", {})
                else:
                    # Format nouveau des endpoints (direct aliases)
                    raw_aliases = data
                
                if isinstance(raw_aliases, dict):
                    # Merge avec défauts, puis canonisation
                    merged = dict(DEFAULT_ALIASES)
                    for k, v in raw_aliases.items():
                        merged[str(k).upper()] = str(v)
                    t.aliases = _canonicalize_alias_mapping(merged, t.groups_order)
                else:
                    # seulement canoniser les défauts
                    t.aliases = _canonicalize_alias_mapping(t.aliases, t.groups_order)

        # Cache la nouvelle instance
        cls._instance = t
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