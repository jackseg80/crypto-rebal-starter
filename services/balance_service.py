"""
Balance Service - Centralized balance resolution logic.

This service extracts the resolve_current_balances logic from api/main.py
to break circular dependencies and improve separation of concerns.

Usage:
    from services.balance_service import balance_service

    result = await balance_service.resolve_current_balances(
        source="cointracking_api",
        user_id="demo"
    )
"""
import logging
from typing import Dict, Any, List
from pathlib import Path
import httpx

logger = logging.getLogger(__name__)

# Optional imports with graceful fallback
try:
    from connectors import cointracking as ct_file
except (ImportError, ModuleNotFoundError):
    ct_file = None


class BalanceService:
    """
    Service responsible for resolving current balance data from various sources.

    Supports multiple data sources:
    - cointracking_api: CoinTracking API with credentials
    - cointracking: CSV files (local)
    - stub_*: Demo data for testing

    Multi-tenant aware: Routes data per user_id using UserDataRouter.
    """

    def __init__(self, base_dir: Path = None):
        """
        Initialize BalanceService.

        Args:
            base_dir: Project root directory (defaults to current working directory)
        """
        self.base_dir = base_dir or Path.cwd()
        logger.info(f"BalanceService initialized with base_dir: {self.base_dir}")

    async def resolve_current_balances(
        self,
        source: str = "cointracking_api",
        user_id: str = "demo"
    ) -> Dict[str, Any]:
        """
        Resolve current balances from specified source.

        Args:
            source: Data source (cointracking_api, cointracking, auto, stub_*)
            user_id: User ID for multi-tenant isolation

        Returns:
            Dict with structure:
            {
                "source_used": str,
                "items": List[Dict],
                "warnings": List[str] (optional),
                "error": str (optional)
            }

        Items structure:
            {
                "symbol": str,
                "alias": str,
                "amount": float,
                "value_usd": float,
                "location": str
            }
        """
        from api.services.data_router import UserDataRouter
        from api.services.cointracking_helpers import pick_primary_location_for_symbol

        logger.info(f"Resolving balances for user '{user_id}' with source '{source}'")

        # Create data router for this user
        project_root = str(self.base_dir)
        data_router = UserDataRouter(project_root, user_id)

        # --- Stub sources: Use default stubs ---
        if source.startswith("stub"):
            logger.debug(f"Using stub source: {source}")
            return self._get_stub_data(source)

        # --- Determine effective source for user ---
        effective_source = data_router.get_effective_source()
        logger.info(f"🎯 Effective source for user '{user_id}': {effective_source}")

        # --- API Mode ---
        if effective_source == "cointracking_api" and source in ("cointracking_api", "auto"):
            api_result = await self._try_api_mode(data_router, user_id)
            if api_result:
                return api_result

        # --- CSV Mode ---
        if effective_source == "cointracking" and source in ("cointracking", "csv", "local", "auto"):
            csv_result = await self._try_csv_mode(data_router, user_id)
            if csv_result:
                return csv_result

        # --- Legacy fallback for backward compatibility ---
        if source == "cointracking_api":
            return await self._legacy_api_mode(user_id)

        if source == "cointracking":
            return await self._legacy_csv_mode()

        # --- Final fallback to CSV ---
        return await self._fallback_csv_mode()

    async def _try_api_mode(
        self,
        data_router,
        user_id: str
    ) -> Dict[str, Any] | None:
        """
        Try to load balances from CoinTracking API.

        Returns:
            Balance data dict if successful, None otherwise
        """
        try:
            credentials = data_router.get_api_credentials()
            api_key = credentials.get("api_key")
            api_secret = credentials.get("api_secret")

            if not (api_key and api_secret):
                logger.warning(f"No CoinTracking API credentials configured for user {user_id}")
                return None

            try:
                from connectors.cointracking_api import get_current_balances as _ctapi_bal

                # Pass API keys directly to connector
                api_result = await _ctapi_bal(api_key=api_key, api_secret=api_secret)
                items = []

                for r in api_result.get("items", []):
                    items.append({
                        "symbol": r.get("symbol"),
                        "alias": r.get("alias") or r.get("symbol"),
                        "amount": r.get("amount"),
                        "value_usd": r.get("value_usd"),
                        "location": r.get("location") or "CoinTracking",
                    })

                logger.debug(f"API mode successful for user {user_id}: {len(items)} items")
                return {"source_used": "cointracking_api", "items": items}

            except httpx.HTTPError as e:
                logger.error(f"CoinTracking API HTTP error for user {user_id}: {e}")
                return None
            except httpx.TimeoutException as e:
                logger.error(f"CoinTracking API timeout for user {user_id}: {e}")
                return None
            except (ValueError, KeyError) as e:
                logger.error(f"CoinTracking API data parsing error for user {user_id}: {e}")
                return None

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"API mode initialization failed for user {user_id}: {e}")
            return None

    async def _try_csv_mode(
        self,
        data_router,
        user_id: str
    ) -> Dict[str, Any] | None:
        """
        Try to load balances from CSV files.

        Returns:
            Balance data dict if successful, None otherwise
        """
        try:
            csv_file = data_router.get_most_recent_csv("balance")
            if not csv_file:
                logger.warning(f"No CSV files found for user {user_id}")
                return None

            from api.services.csv_helpers import load_csv_balances
            items = await load_csv_balances(csv_file)
            logger.debug(f"CSV mode successful for user {user_id}: {len(items)} items from {csv_file}")
            return {"source_used": "cointracking", "items": items}

        except FileNotFoundError as e:
            logger.error(f"CSV file not found for user {user_id}: {e}")
            return None
        except PermissionError as e:
            logger.error(f"Permission denied reading CSV for user {user_id}: {e}")
            return None
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"CSV parsing error for user {user_id}: {e}")
            return None

    def _get_stub_data(self, source: str) -> Dict[str, Any]:
        """
        Get demo stub data for testing.

        Args:
            source: stub_conservative, stub_shitcoins, or stub (balanced)

        Returns:
            Balance data dict with demo data
        """
        if source == "stub_conservative":
            # Conservative portfolio: 80% BTC, 15% ETH, 5% stables
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 3.2, "value_usd": 160000.0, "location": "Cold Storage"},
                {"symbol": "ETH", "alias": "ETH", "amount": 10.0, "value_usd": 30000.0, "location": "Ledger"},
                {"symbol": "USDC", "alias": "USDC", "amount": 10000.0, "value_usd": 10000.0, "location": "Coinbase"}
            ]
            return {
                "source_used": "stub_conservative",
                "items": demo_data,
                "warnings": ["Using demo stub dataset (conservative)."]
            }

        elif source == "stub_shitcoins":
            # Risky portfolio: lots of memecoins and altcoins
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 0.1, "value_usd": 5000.0, "location": "Binance"},
                {"symbol": "ETH", "alias": "ETH", "amount": 2.0, "value_usd": 6000.0, "location": "MetaMask"},
                {"symbol": "SHIB", "alias": "SHIB", "amount": 50000000.0, "value_usd": 15000.0, "location": "MetaMask"},
                {"symbol": "DOGE", "alias": "DOGE", "amount": 30000.0, "value_usd": 12000.0, "location": "Robinhood"},
                {"symbol": "PEPE", "alias": "PEPE", "amount": 100000000.0, "value_usd": 10000.0, "location": "MetaMask"},
                {"symbol": "BONK", "alias": "BONK", "amount": 5000000.0, "value_usd": 8000.0, "location": "Phantom"},
                {"symbol": "WIF", "alias": "WIF", "amount": 15000.0, "value_usd": 7500.0, "location": "Phantom"},
                {"symbol": "FLOKI", "alias": "FLOKI", "amount": 2000000.0, "value_usd": 6000.0, "location": "MetaMask"},
                {"symbol": "BABYDOGE", "alias": "BABYDOGE", "amount": 10000000000.0, "value_usd": 5000.0, "location": "PancakeSwap"},
                {"symbol": "SAFEMOON", "alias": "SAFEMOON", "amount": 5000000.0, "value_usd": 4500.0, "location": "Trust Wallet"},
                {"symbol": "CATGIRL", "alias": "CATGIRL", "amount": 100000000.0, "value_usd": 4000.0, "location": "MetaMask"},
                {"symbol": "DOGELON", "alias": "DOGELON", "amount": 50000000000.0, "value_usd": 3500.0, "location": "MetaMask"},
                {"symbol": "KISHU", "alias": "KISHU", "amount": 20000000000.0, "value_usd": 3000.0, "location": "MetaMask"},
                {"symbol": "AKITA", "alias": "AKITA", "amount": 1000000000.0, "value_usd": 2500.0, "location": "Uniswap"},
                {"symbol": "HOKK", "alias": "HOKK", "amount": 500000000000.0, "value_usd": 2000.0, "location": "MetaMask"},
                {"symbol": "FOMO", "alias": "FOMO", "amount": 50000000.0, "value_usd": 1800.0, "location": "PancakeSwap"},
                {"symbol": "CUMINU", "alias": "CUMINU", "amount": 100000000000.0, "value_usd": 1500.0, "location": "MetaMask"},
                {"symbol": "ELONGATE", "alias": "ELONGATE", "amount": 20000000000.0, "value_usd": 1200.0, "location": "PancakeSwap"},
                {"symbol": "MOONSHOT", "alias": "MOONSHOT", "amount": 5000000.0, "value_usd": 1000.0, "location": "DEX"},
                {"symbol": "USDT", "alias": "USDT", "amount": 5000.0, "value_usd": 5000.0, "location": "Binance"}
            ]
            return {
                "source_used": "stub_shitcoins",
                "items": demo_data,
                "warnings": ["Using demo stub dataset (high-risk)."]
            }

        else:  # stub or stub_balanced (default)
            # Balanced portfolio: mix of BTC, ETH, serious alts
            demo_data = [
                {"symbol": "BTC", "alias": "BTC", "amount": 2.5, "value_usd": 105000.0, "location": "Kraken"},
                {"symbol": "ETH", "alias": "ETH", "amount": 15.75, "value_usd": 47250.0, "location": "Binance"},
                {"symbol": "USDC", "alias": "USDC", "amount": 25000.0, "value_usd": 25000.0, "location": "Coinbase"},
                {"symbol": "SOL", "alias": "SOL", "amount": 180.0, "value_usd": 23400.0, "location": "Phantom"},
                {"symbol": "AVAX", "alias": "AVAX", "amount": 450.0, "value_usd": 13500.0, "location": "Ledger"},
                {"symbol": "MATIC", "alias": "MATIC", "amount": 12000.0, "value_usd": 9600.0, "location": "MetaMask"},
                {"symbol": "LINK", "alias": "LINK", "amount": 520.0, "value_usd": 7280.0, "location": "Binance"},
                {"symbol": "UNI", "alias": "UNI", "amount": 800.0, "value_usd": 6400.0, "location": "Uniswap"},
                {"symbol": "AAVE", "alias": "AAVE", "amount": 45.0, "value_usd": 5850.0, "location": "Aave"},
                {"symbol": "WBTC", "alias": "WBTC", "amount": 0.12, "value_usd": 5040.0, "location": "Ledger"},
                {"symbol": "WETH", "alias": "WETH", "amount": 1.8, "value_usd": 5400.0, "location": "MetaMask"},
                {"symbol": "USDT", "alias": "USDT", "amount": 8500.0, "value_usd": 8500.0, "location": "Binance"},
                {"symbol": "ADA", "alias": "ADA", "amount": 15000.0, "value_usd": 6750.0, "location": "Kraken"},
                {"symbol": "DOT", "alias": "DOT", "amount": 950.0, "value_usd": 4750.0, "location": "Polkadot"},
                {"symbol": "ATOM", "alias": "ATOM", "amount": 520.0, "value_usd": 4160.0, "location": "Keplr"},
                {"symbol": "FTM", "alias": "FTM", "amount": 8500.0, "value_usd": 3400.0, "location": "Fantom"},
                {"symbol": "ALGO", "alias": "ALGO", "amount": 12000.0, "value_usd": 3000.0, "location": "Pera"},
                {"symbol": "NEAR", "alias": "NEAR", "amount": 1200.0, "value_usd": 2880.0, "location": "Near Wallet"},
                {"symbol": "ICP", "alias": "ICP", "amount": 350.0, "value_usd": 2450.0, "location": "NNS"},
                {"symbol": "SAND", "alias": "SAND", "amount": 6000.0, "value_usd": 2400.0, "location": "Binance"},
                {"symbol": "MANA", "alias": "MANA", "amount": 5500.0, "value_usd": 2200.0, "location": "MetaMask"},
                {"symbol": "CRV", "alias": "CRV", "amount": 3500.0, "value_usd": 2100.0, "location": "Curve"},
                {"symbol": "COMP", "alias": "COMP", "amount": 45.0, "value_usd": 1980.0, "location": "Compound"}
            ]
            return {"source_used": source, "items": demo_data}

    async def _legacy_api_mode(self, user_id: str = "demo") -> Dict[str, Any]:
        """Legacy API mode for backward compatibility."""
        from api.services.cointracking_helpers import load_ctapi_exchanges, pick_primary_location_for_symbol
        from api.services.data_router import UserDataRouter

        try:
            # Load API credentials for user
            project_root = str(self.base_dir)
            data_router = UserDataRouter(project_root, user_id)
            credentials = data_router.get_api_credentials()
            api_key = credentials.get("api_key")
            api_secret = credentials.get("api_secret")
            logger.info(f"🔑 DEBUG: api_key='{api_key[:10] if api_key else None}...', api_secret='{api_secret[:10] if api_secret else None}...', len_key={len(api_key) if api_key else 0}, len_secret={len(api_secret) if api_secret else 0}")

            # 1) Load snapshot by exchange via CT-API
            snap = await load_ctapi_exchanges(min_usd=0.0, api_key=api_key, api_secret=api_secret)
            detailed = snap.get("detailed_holdings") or {}

            # 2) Per-coin view via CT-API
            if ct_file is not None:
                api_bal = await ct_file.get_current_balances("cointracking_api")
            else:
                from connectors.cointracking_api import get_current_balances as _ctapi_bal
                # Pass credentials explicitly
                api_bal = await _ctapi_bal(api_key=api_key, api_secret=api_secret)
            items = api_bal.get("items") or []

            # 3) For EACH coin, set location = primary exchange (max value_usd)
            out = []
            for it in items:
                sym = it.get("symbol")
                loc = pick_primary_location_for_symbol(sym, detailed)
                out.append({
                    "symbol": sym,
                    "alias": it.get("alias") or sym,
                    "amount": it.get("amount"),
                    "value_usd": it.get("value_usd"),
                    "location": loc or "CoinTracking",
                })

            if not out:
                return {"source_used": "cointracking_api", "items": [], "error": "no_items_from_api"}
            return {"source_used": "cointracking_api", "items": out}

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching CoinTracking API data: {e}")
            return {"source_used": "cointracking_api", "items": [], "error": f"HTTP error: {str(e)}"}
        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching CoinTracking API data: {e}")
            return {"source_used": "cointracking_api", "items": [], "error": f"Timeout: {str(e)}"}
        except (ValueError, KeyError) as e:
            logger.error(f"Data parsing error from CoinTracking API: {e}")
            return {"source_used": "cointracking_api", "items": [], "error": f"Parsing error: {str(e)}"}

    async def _legacy_csv_mode(self) -> Dict[str, Any]:
        """Legacy CSV mode for backward compatibility."""
        items = []
        try:
            if ct_file is not None:
                raw = await ct_file.get_current_balances("cointracking")
                for r in raw.get("items", []):
                    items.append({
                        "symbol": r.get("symbol"),
                        "alias": r.get("alias") or r.get("symbol"),
                        "amount": r.get("amount"),
                        "value_usd": r.get("value_usd"),
                        "location": r.get("location") or "CoinTracking",
                    })
            else:
                from connectors.cointracking import get_current_balances_from_csv as _csv_bal
                raw = _csv_bal()  # sync
                for r in raw.get("items", []):
                    items.append({
                        "symbol": r.get("symbol"),
                        "alias": r.get("alias") or r.get("symbol"),
                        "amount": r.get("amount"),
                        "value_usd": r.get("value_usd"),
                        "location": r.get("location") or "CoinTracking",
                    })
        except FileNotFoundError as e:
            logger.error(f"CSV file not found (source=cointracking): {e}")
        except PermissionError as e:
            logger.error(f"Permission denied reading CSV (source=cointracking): {e}")
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"CSV parsing error (source=cointracking): {e}")

        return {"source_used": "cointracking", "items": items}

    async def _fallback_csv_mode(self) -> Dict[str, Any]:
        """Final fallback to CSV if all else fails."""
        items = []
        try:
            if ct_file is not None:
                raw = await ct_file.get_current_balances("cointracking")
                for r in raw.get("items", []):
                    items.append({
                        "symbol": r.get("symbol"),
                        "alias": r.get("alias") or r.get("symbol"),
                        "amount": r.get("amount"),
                        "value_usd": r.get("value_usd"),
                        "location": r.get("location") or "CoinTracking",
                    })
            else:
                # Fallback: direct CSV read if facade unavailable
                from connectors.cointracking import get_current_balances_from_csv as _csv_bal
                raw = _csv_bal()  # sync
                for r in raw.get("items", []):
                    items.append({
                        "symbol": r.get("symbol"),
                        "alias": r.get("alias") or r.get("symbol"),
                        "amount": r.get("amount"),
                        "value_usd": r.get("value_usd"),
                        "location": r.get("location") or "CoinTracking",
                    })
        except FileNotFoundError as e:
            logger.error(f"CSV file not found (fallback): {e}")
        except PermissionError as e:
            logger.error(f"Permission denied reading CSV (fallback): {e}")
        except (ValueError, UnicodeDecodeError) as e:
            logger.error(f"CSV parsing error (fallback): {e}")

        return {"source_used": "cointracking", "items": items}


# ============================================================================
# Global singleton instance
# ============================================================================

# Create singleton instance with default base_dir
# This will be used by all consumers
balance_service = BalanceService()

logger.info("✅ BalanceService singleton created")
