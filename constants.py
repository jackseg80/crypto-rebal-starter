from __future__ import annotations

"""
Centralized constants and helpers for exchange naming + priority + hints.

Keeps a single source of truth used by planning and UI hints.
"""

from typing import Dict

# Priority map: lower means preferred for fast executions (CEX first)
_EXCHANGE_PRIORITY: Dict[str, int] = {
    # CEX
    "Binance": 1,
    "Kraken": 2,
    "Coinbase": 3,
    "Bitget": 4,
    "Bybit": 5,
    "OKX": 6,
    "Huobi": 7,
    "KuCoin": 8,
    "Coinbase Pro": 9,
    # Wallets
    "MetaMask": 20,
    "Phantom": 21,
    "Rabby": 22,
    "TrustWallet": 23,
    # DeFi / DEX
    "Uniswap": 30,
    "PancakeSwap": 31,
    "SushiSwap": 32,
    "Curve": 33,
    "DeFi": 34,
    # Hardware / cold storage
    "Ledger": 40,
    "Trezor": 41,
    "Cold Storage": 42,
    # Fallbacks / generic
    "Portfolio": 50,
    "CoinTracking": 51,
    "Demo Wallet": 52,
    "Unknown": 60,
    "Manually": 61,
}

_CANONICAL_CASE = {k.lower(): k for k in _EXCHANGE_PRIORITY.keys()}


def normalize_exchange_name(raw: str | None) -> str:
    """Normalize common variations (case + suffixes like " Balance")."""
    if not raw:
        return "Unknown"
    s = str(raw).strip()
    if s.endswith(" Balance"):
        s = s[:-8].strip()
    # unify common wallet spellings
    aliases = {
        "cointracking": "CoinTracking",
        "cointracking balance": "CoinTracking",
        "metamask": "MetaMask",
        "pancakeswap": "PancakeSwap",
        "sushiswap": "SushiSwap",
        "kucoin": "KuCoin",
        "okx": "OKX",
        "trezor": "Trezor",
        "ledger live": "Ledger",
    }
    low = s.lower()
    if low in aliases:
        return aliases[low]
    # canonicalize to known casing if we have it
    return _CANONICAL_CASE.get(low, s.title())


def get_exchange_priority(raw: str | None) -> int:
    name = normalize_exchange_name(raw)
    return _EXCHANGE_PRIORITY.get(name, 100)


def format_exec_hint(location: str, action_type: str) -> str:
    """Return a short execution hint based on preferred venue class and action.

    Examples:
      - Sell on Binance
      - Sell on Uniswap (DeFi)
      - Buy on Ledger (manual)
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
    else:  # buy
        if p < 15:
            return f"Buy on {loc}"
        elif p < 30:
            return f"Buy on {loc} (DApp)"
        elif p < 40:
            return f"Buy on {loc} (DeFi)"
        else:
            return f"Buy on {loc} (manual)"

