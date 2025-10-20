"""
CSV parsing and generation helpers for balance data.

Extracted from api/main.py (lines 480-551, 940-953) as part of Phase 3 refactoring.
Handles flexible CSV parsing with multiple column name variants and CSV export.
"""

import csv
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def load_csv_balances(csv_file_path: str) -> List[Dict[str, Any]]:
    """
    Parse CSV balance file with flexible column detection.

    Supports multiple CSV formats with various column name conventions:
    - Symbol: Ticker, Currency, Coin, Symbol, Asset
    - Amount: Amount, Qty, Quantity
    - Value: "Value in USD", "Value (USD)", "USD Value", "Current Value (USD)", value_usd
    - Location: Exchange, Location, Wallet

    Args:
        csv_file_path: Path to CSV file to parse

    Returns:
        List of balance dicts with normalized keys:
        [{
            "symbol": str (uppercased),
            "alias": str,
            "amount": float,
            "value_usd": float,
            "location": str
        }]

    Notes:
        - Uses UTF-8-sig encoding to handle BOM
        - Auto-detects CSV dialect (delimiter: , or ;)
        - Filters out rows with missing symbol, zero amount, or zero value
        - Handles commas in numeric values (e.g., "1,234.56")
    """
    items = []
    if not os.path.exists(csv_file_path):
        return items

    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig', newline='') as f:
            # Auto-detect CSV dialect
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except Exception:
                # Fallback to comma delimiter
                class _Dialect:
                    delimiter = ","
                dialect = _Dialect()

            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                # Normalize keys and values (strip whitespace)
                normalized_row = {
                    (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                    for k, v in row.items()
                }

                # Extract symbol (multiple column name variants)
                symbol = None
                for key in ("Ticker", "Currency", "Coin", "Symbol", "Asset"):
                    if key in normalized_row and normalized_row[key]:
                        symbol = normalized_row[key].upper().strip()
                        break

                # Extract amount (multiple column name variants)
                amount = 0.0
                for key in ("Amount", "amount", "Qty", "Quantity", "quantity"):
                    if key in normalized_row and normalized_row[key]:
                        try:
                            # Handle comma as decimal separator
                            amount = float(str(normalized_row[key]).replace(",", "."))
                            break
                        except ValueError:
                            continue

                # Extract USD value (multiple column name variants)
                value_usd = 0.0
                for key in ("Value in USD", "Value (USD)", "USD Value", "Current Value (USD)", "value_usd", "Value", "value"):
                    if key in normalized_row and normalized_row[key]:
                        try:
                            # Handle comma as decimal separator
                            value_usd = float(str(normalized_row[key]).replace(",", "."))
                            break
                        except ValueError:
                            continue

                # Extract location (multiple column name variants)
                location = "CoinTracking"
                for key in ("Exchange", "exchange", "Location", "location", "Wallet", "wallet"):
                    if key in normalized_row and normalized_row[key]:
                        location = normalized_row[key].strip()
                        break

                # Only add valid rows (with symbol, positive amount and value)
                if symbol and amount > 0 and value_usd > 0:
                    items.append({
                        "symbol": symbol,
                        "alias": symbol,
                        "amount": amount,
                        "value_usd": value_usd,
                        "location": location
                    })

    except Exception as e:
        logger.error(f"Error parsing CSV file {csv_file_path}: {e}")

    return items


def to_csv(actions: List[Dict[str, Any]]) -> str:
    """
    Generate CSV string from rebalancing actions.

    Args:
        actions: List of action dicts with keys:
            - group: str (optional)
            - alias: str (optional)
            - symbol: str
            - action: str ("BUY" or "SELL")
            - usd: float (negative for sells, positive for buys)
            - est_quantity: float (optional)
            - price_used: float (optional)
            - exec_hint: str (optional)

    Returns:
        CSV string with header and one row per action

    Format:
        group,alias,symbol,action,usd,est_quantity,price_used,exec_hint
        DEGEN,PEPE,PEPE,SELL,-1234.56,12345678.90,0.0001,Binance: SELL 12345678.90 PEPE

    Notes:
        - USD values formatted to 2 decimal places
        - Empty fields for missing optional values
        - exec_hint provides human-readable execution guidance
    """
    lines = ["group,alias,symbol,action,usd,est_quantity,price_used,exec_hint"]
    for a in actions or []:
        lines.append("{},{},{},{},{:.2f},{},{},{}".format(
            a.get("group", ""),
            a.get("alias", ""),
            a.get("symbol", ""),
            a.get("action", ""),
            float(a.get("usd") or 0.0),
            ("" if a.get("est_quantity") is None else f"{a.get('est_quantity')}"),
            ("" if a.get("price_used") is None else f"{a.get('price_used')}"),
            a.get("exec_hint", "")
        ))
    return "\n".join(lines)
