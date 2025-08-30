"""
Module centralisé pour la gestion des exchanges et de leurs priorités.
Unifie les constantes dupliquées à travers le projet.
"""
from typing import Dict, List

# Classifications d'exchanges
FAST_SELL_EXCHANGES: List[str] = [
    "Kraken", "Binance", "Coinbase", "Bitget", "OKX", "Bybit", 
    "KuCoin", "Bittrex", "Bitstamp", "Gemini"
]

DEFI_HINTS: List[str] = [
    "Aave", "Lido", "Rocket Pool", "Curve", "Uniswap", "Sushiswap", 
    "Jupiter", "Osmosis", "Thorchain"
]

COLD_HINTS: List[str] = [
    "Ledger", "Trezor", "Cold", "Vault", "Hardware"
]

# Système de priorités unifié pour tous les exchanges
EXCHANGE_PRIORITIES: Dict[str, int] = {
    # CEX rapides (priorité 1-15)
    "Binance": 1,
    "Kraken": 2, 
    "Coinbase": 3,
    "Bitget": 4,
    "Bybit": 5,
    "OKX": 6,
    "Huobi": 7,
    "KuCoin": 8,
    "Poloniex": 9,
    "Kraken Earn": 10,
    "Coinbase Pro": 11,
    "Bittrex": 12,
    "Ftx": 13,
    "Swissborg": 14,
    
    # Wallets software (priorité 20-29)
    "MetaMask": 20,
    "Phantom": 21,
    "Rabby": 22,
    "TrustWallet": 23,
    
    # Wallets spécialisés (priorité 25)
    "Metamask": 25,  # Note: variante de casse pour compatibilité
    "Solana": 25,
    "Ron": 25,
    "Siacoin": 25,
    "Vsync": 25,
    
    # DeFi (priorité 30-39)
    "DeFi": 30,
    "Uniswap": 31,
    "PancakeSwap": 32,
    "SushiSwap": 33,
    "Curve": 34,
    
    # Hardware/Cold (priorité 40+)
    "Ledger": 40,
    "Ledger Wallets": 40,
    "Trezor": 41,
    "Cold Storage": 42,
    
    # Autres (priorité 50+)
    "Portfolio": 50,
    "CoinTracking": 51,
    "Demo Wallet": 52,
    "Unknown": 60,
    "Manually": 61,
}

# Priorité par défaut pour exchanges non répertoriés
DEFAULT_EXCHANGE_PRIORITY: int = 99

# Priorité spéciale pour wallets avec préfixes spéciaux
SPECIAL_WALLET_PRIORITY: int = 25
SPECIAL_WALLET_PREFIXES: List[str] = ["Metamask", "Solana", "Ron", "Siacoin", "Vsync"]


def normalize_exchange_name(exchange_name: str) -> str:
    """
    Normalise le nom d'un exchange pour standardiser les comparaisons.
    
    Args:
        exchange_name: Nom brut de l'exchange
        
    Returns:
        Nom normalisé de l'exchange
    """
    if not exchange_name:
        return "Unknown"
    
    # Nettoyage de base
    name = exchange_name.strip()
    name = name.replace("_", " ").replace("-", " ")
    name = name.title()
    
    # Suppression des suffixes communs
    suffixes_to_remove = [" Balance", " Wallet", " Account", " Wallets"]
    for suffix in suffixes_to_remove:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    
    return name


def get_exchange_priority(exchange_name: str) -> int:
    """
    Retourne la priorité d'un exchange (plus petit = plus prioritaire).
    
    Args:
        exchange_name: Nom de l'exchange
        
    Returns:
        Priorité numérique (1 = plus haute priorité)
    """
    normalized_name = normalize_exchange_name(exchange_name)
    
    # Vérifier d'abord les priorités exactes
    if normalized_name in EXCHANGE_PRIORITIES:
        return EXCHANGE_PRIORITIES[normalized_name]
    
    # Vérifier les préfixes spéciaux
    for prefix in SPECIAL_WALLET_PREFIXES:
        if normalized_name.startswith(prefix):
            return SPECIAL_WALLET_PRIORITY
    
    # Priorité par défaut
    return DEFAULT_EXCHANGE_PRIORITY


def classify_exchange_type(exchange_name: str) -> str:
    """
    Classifie un exchange en catégorie (CEX, DeFi, Cold, etc.).
    
    Args:
        exchange_name: Nom de l'exchange
        
    Returns:
        Type d'exchange ('CEX', 'DeFi', 'Cold', 'Software', 'Other')
    """
    normalized_name = normalize_exchange_name(exchange_name)
    priority = get_exchange_priority(normalized_name)
    
    if priority < 15:
        return "CEX"
    elif priority < 30:
        return "Software"
    elif priority < 40:
        return "DeFi"  
    elif priority < 50:
        return "Cold"
    else:
        return "Other"


def is_fast_sell_exchange(exchange_name: str) -> bool:
    """
    Vérifie si un exchange permet des ventes rapides.
    
    Args:
        exchange_name: Nom de l'exchange
        
    Returns:
        True si l'exchange permet des ventes rapides
    """
    normalized_name = normalize_exchange_name(exchange_name)
    return any(normalized_name.startswith(fast_ex) for fast_ex in FAST_SELL_EXCHANGES)


def is_defi_exchange(exchange_name: str) -> bool:
    """
    Vérifie si un exchange est de type DeFi.
    
    Args:
        exchange_name: Nom de l'exchange
        
    Returns:
        True si l'exchange est DeFi
    """
    normalized_name = normalize_exchange_name(exchange_name)
    return any(hint in normalized_name for hint in DEFI_HINTS)


def is_cold_storage(exchange_name: str) -> bool:
    """
    Vérifie si un exchange est du cold storage.
    
    Args:
        exchange_name: Nom de l'exchange
        
    Returns:
        True si l'exchange est du cold storage
    """
    normalized_name = normalize_exchange_name(exchange_name)
    return any(hint in normalized_name for hint in COLD_HINTS)


def format_exec_hint(location: str, action_type: str) -> str:
    """Génère un hint d'exécution court basé sur la priorité (venue class).

    Exemples:
      - "Sell on Binance"
      - "Sell on Uniswap (DeFi)"
      - "Buy on Ledger (manual)"
    """
    loc = normalize_exchange_name(location)
    p = get_exchange_priority(loc)
    if action_type == "sell":
        if p < 15:
            return f"Sell on {loc}"
        elif p < 30:
            return f"Sell on {loc} (DApp)"
        elif p < 40:
            return f"Sell on {loc} (DeFi)"
        else:
            return f"Sell on {loc} (complex)"
    else:
        if p < 15:
            return f"Buy on {loc}"
        elif p < 30:
            return f"Buy on {loc} (DApp)"
        elif p < 40:
            return f"Buy on {loc} (DeFi)"
        else:
            return f"Buy on {loc} (manual)"
