"""
Instruments Registry - Enrichissement des métadonnées instruments (ISIN, ticker, nom, exchange)

Architecture:
- Catalog global partagé (data/catalogs/equities_catalog.json) pour instruments standards
- Catalog per-user (data/users/{user_id}/saxobank/instruments.json) pour instruments spécifiques
- Lazy-loading au premier appel avec cache en mémoire
- Validation ISIN complète avec regex

Performance:
- Chargement JSONs UNE FOIS au premier appel
- Cache en mémoire pour résolutions suivantes
- Pas de I/O répété

Multi-tenant:
- Lookup user-specific en priorité, puis global
- Isolation des données enrichies par user
"""

from __future__ import annotations
import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Paths
GLOBAL_CATALOG_PATH = Path("data/catalogs/equities_catalog.json")
GLOBAL_ISIN_MAP_PATH = Path("data/mappings/isin_ticker.json")

# Caches au niveau module (lazy-loaded)
_global_catalog_cache: Optional[Dict[str, Dict]] = None
_isin_to_ticker_cache: Optional[Dict[str, str]] = None
_ticker_to_isin_cache: Optional[Dict[str, str]] = None
_resolved_cache: Dict[str, Dict] = {}  # Cache des résolutions effectuées

# Regex ISIN valide: 2 lettres pays (ISO 3166) + 10 caractères alphanum
ISIN_PATTERN = re.compile(r'^[A-Z]{2}[A-Z0-9]{10}$')


def _ensure_loaded_global() -> None:
    """Lazy-load des catalogs globaux au premier appel."""
    global _global_catalog_cache, _isin_to_ticker_cache, _ticker_to_isin_cache

    if _global_catalog_cache is not None:
        return  # Déjà chargé

    # 1. Load global catalog
    if GLOBAL_CATALOG_PATH.exists():
        try:
            _global_catalog_cache = json.loads(GLOBAL_CATALOG_PATH.read_text(encoding="utf-8"))
            logger.info(f"[registry] Loaded {len(_global_catalog_cache)} instruments from global catalog")
        except Exception as e:
            logger.warning(f"[registry] Failed to load global catalog: {e}")
            _global_catalog_cache = {}
    else:
        GLOBAL_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        GLOBAL_CATALOG_PATH.write_text("{}", encoding="utf-8")
        _global_catalog_cache = {}
        logger.info("[registry] Created empty global catalog")

    # 2. Load ISIN mappings (forward + reverse)
    if GLOBAL_ISIN_MAP_PATH.exists():
        try:
            _isin_to_ticker_cache = json.loads(GLOBAL_ISIN_MAP_PATH.read_text(encoding="utf-8"))
            # Build reverse mapping
            _ticker_to_isin_cache = {v.upper(): k for k, v in _isin_to_ticker_cache.items()}
            logger.info(f"[registry] Loaded {len(_isin_to_ticker_cache)} ISIN→ticker mappings")
        except Exception as e:
            logger.warning(f"[registry] Failed to load ISIN mappings: {e}")
            _isin_to_ticker_cache = {}
            _ticker_to_isin_cache = {}
    else:
        GLOBAL_ISIN_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
        GLOBAL_ISIN_MAP_PATH.write_text("{}", encoding="utf-8")
        _isin_to_ticker_cache = {}
        _ticker_to_isin_cache = {}
        logger.info("[registry] Created empty ISIN mapping")


def _load_user_catalog(user_id: str) -> Dict[str, Dict]:
    """
    Load user-specific catalog if exists.

    Args:
        user_id: User identifier

    Returns:
        Dict mapping instrument_id → metadata (or empty dict)
    """
    user_catalog_path = Path(f"data/users/{user_id}/saxobank/instruments.json")

    if not user_catalog_path.exists():
        return {}

    try:
        user_catalog = json.loads(user_catalog_path.read_text(encoding="utf-8"))
        logger.debug(f"[registry] Loaded {len(user_catalog)} instruments from user {user_id} catalog")
        return user_catalog
    except Exception as e:
        logger.warning(f"[registry] Failed to load user {user_id} catalog: {e}")
        return {}


def _is_valid_isin(s: str) -> bool:
    """
    Check if string matches ISIN format.

    ISIN format: 2 letters (country code) + 10 alphanumeric characters
    Examples: IE00B4L5Y983 (Ireland), US0378331005 (USA), FR0000120271 (France)

    Args:
        s: String to validate

    Returns:
        True if valid ISIN format
    """
    return bool(ISIN_PATTERN.match(s.upper()))


def resolve(
    instrument_or_isin: str,
    fallback_symbol: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict:
    """
    Resolve instrument metadata from ISIN or ticker.

    Resolution order:
    1. User-specific catalog (if user_id provided)
    2. Global catalog
    3. ISIN → ticker mapping → global catalog
    4. Ticker → ISIN mapping → global catalog
    5. Fallback minimal record

    Args:
        instrument_or_isin: ISIN code or ticker symbol
        fallback_symbol: Fallback display symbol if not found
        user_id: Optional user ID for per-user catalog lookup

    Returns:
        Dict with keys: id, symbol, isin, name, exchange, asset_class, currency

    Example:
        >>> resolve("IE00B4L5Y983")
        {
            "id": "IWDA.AMS",
            "symbol": "IWDA.AMS",
            "isin": "IE00B4L5Y983",
            "name": "iShares Core MSCI World UCITS ETF",
            "exchange": "AMS",
            "asset_class": "ETF",
            "currency": "EUR"
        }
    """
    # Ensure global catalogs are loaded
    _ensure_loaded_global()

    key = instrument_or_isin.upper().strip()

    # Check resolved cache first (all users)
    cache_key = f"{user_id}:{key}" if user_id else key
    if cache_key in _resolved_cache:
        return _resolved_cache[cache_key]

    # 1) User-specific catalog (priority)
    if user_id:
        user_catalog = _load_user_catalog(user_id)
        if key in user_catalog:
            _resolved_cache[cache_key] = user_catalog[key]
            return _resolved_cache[cache_key]

    # 2) Global catalog direct lookup
    if key in _global_catalog_cache:
        _resolved_cache[cache_key] = _global_catalog_cache[key]
        return _resolved_cache[cache_key]

    # 3) ISIN → ticker → catalog
    if key in _isin_to_ticker_cache:
        ticker = _isin_to_ticker_cache[key]
        if ticker in _global_catalog_cache:
            _resolved_cache[cache_key] = _global_catalog_cache[ticker]
            return _resolved_cache[cache_key]

    # 4) Ticker → ISIN → catalog (reverse lookup)
    if key in _ticker_to_isin_cache:
        isin = _ticker_to_isin_cache[key]
        if isin in _global_catalog_cache:
            _resolved_cache[cache_key] = _global_catalog_cache[isin]
            return _resolved_cache[cache_key]

    # 5) Fallback: construct minimal record
    is_isin = _is_valid_isin(key)
    result = {
        "id": key,
        "symbol": fallback_symbol or key,
        "isin": key if is_isin else None,
        "name": fallback_symbol or key,
        "exchange": None,
        "asset_class": None,
        "currency": None,
    }
    _resolved_cache[cache_key] = result
    return result


def add_to_catalog(
    instrument_id: str,
    metadata: Dict,
    user_id: Optional[str] = None,
    persist: bool = True
) -> None:
    """
    Add or update instrument in catalog.

    Args:
        instrument_id: Instrument identifier (ISIN or ticker)
        metadata: Metadata dict with keys: symbol, isin, name, exchange, asset_class, currency
        user_id: If provided, save to user-specific catalog; otherwise global
        persist: If True, write to disk immediately
    """
    key = instrument_id.upper().strip()

    if user_id:
        # Save to user catalog
        user_catalog_path = Path(f"data/users/{user_id}/saxobank/instruments.json")
        user_catalog_path.parent.mkdir(parents=True, exist_ok=True)

        user_catalog = _load_user_catalog(user_id)
        user_catalog[key] = metadata

        if persist:
            try:
                user_catalog_path.write_text(json.dumps(user_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info(f"[registry] Persisted {key} to user {user_id} catalog")
            except Exception as e:
                logger.error(f"[registry] Failed to persist user catalog: {e}")
    else:
        # Save to global catalog
        _ensure_loaded_global()
        _global_catalog_cache[key] = metadata

        if persist:
            try:
                GLOBAL_CATALOG_PATH.write_text(
                    json.dumps(_global_catalog_cache, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                logger.info(f"[registry] Persisted {key} to global catalog")
            except Exception as e:
                logger.error(f"[registry] Failed to persist global catalog: {e}")

    # Invalidate cache for this key
    cache_key = f"{user_id}:{key}" if user_id else key
    _resolved_cache.pop(cache_key, None)


def clear_cache() -> None:
    """
    Clear in-memory caches (useful for tests or reload).
    Next resolve() call will reload from disk.
    """
    global _global_catalog_cache, _isin_to_ticker_cache, _ticker_to_isin_cache, _resolved_cache
    _global_catalog_cache = None
    _isin_to_ticker_cache = None
    _ticker_to_isin_cache = None
    _resolved_cache = {}
    logger.info("[registry] All caches cleared")
