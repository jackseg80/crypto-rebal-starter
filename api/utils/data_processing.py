"""
Data processing utilities
"""
import re
from typing import List, Dict, Any

def normalize_location(label: str) -> str:
    """Normalize location label for consistent mapping"""
    if not label:
        return ""
    
    # Convert to lowercase and remove extra spaces
    normalized = re.sub(r'\s+', ' ', label.strip().lower())
    
    # Common normalizations
    normalizations = {
        'binance': 'binance',
        'binance.com': 'binance', 
        'binance spot': 'binance',
        'kraken': 'kraken',
        'kraken.com': 'kraken',
        'coinbase': 'coinbase',
        'coinbase pro': 'coinbase',
        'metamask': 'metamask',
        'ledger': 'ledger',
        'trezor': 'trezor'
    }
    
    return normalizations.get(normalized, normalized)

def classify_location(loc: str) -> int:
    """
    Classify location by priority for portfolio allocation
    Returns priority level (lower = higher priority)
    """
    loc_lower = loc.lower() if loc else ""
    
    if any(x in loc_lower for x in ['binance', 'kraken', 'coinbase']):
        return 1  # High priority - major exchanges
    elif any(x in loc_lower for x in ['metamask', 'wallet']):
        return 2  # Medium priority - wallets
    elif any(x in loc_lower for x in ['ledger', 'trezor', 'hardware']):
        return 3  # Lower priority - hardware wallets
    else:
        return 4  # Lowest priority - unknown/other

def pick_primary_location_for_symbol(symbol: str, detailed_holdings: Dict) -> str:
    """Select the best location for a given symbol based on holdings and priority"""
    if symbol not in detailed_holdings:
        return "unknown"
    
    locations = detailed_holdings[symbol]
    if not locations:
        return "unknown"
    
    # Sort by priority (lower number = higher priority) and balance
    sorted_locations = sorted(
        locations.items(),
        key=lambda x: (classify_location(x[0]), -x[1])  # Priority first, then balance desc
    )
    
    return sorted_locations[0][0] if sorted_locations else "unknown"

def to_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert raw portfolio data to standardized row format"""
    rows = []
    for item in raw:
        if not isinstance(item, dict):
            continue
            
        row = {
            'symbol': item.get('symbol', '').upper(),
            'balance': float(item.get('balance', 0)),
            'value_usd': float(item.get('value_usd', 0)),
            'location': normalize_location(item.get('location', 'unknown')),
            'price_usd': float(item.get('price_usd', 0))
        }
        
        if row['balance'] > 0 and row['value_usd'] > 0:
            rows.append(row)
    
    return rows

def calculate_price_deviation(local_price: float, market_price: float) -> float:
    """Calculate percentage deviation between local and market price"""
    if market_price == 0:
        return 0.0
    return abs(local_price - market_price) / market_price * 100

def parse_min_usd(raw: str | None, default: float = 1.0) -> float:
    """Parse minimum USD value from string with fallback"""
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except (ValueError, TypeError):
        return default

def get_data_age_minutes(source_used: str) -> float:
    """Get estimated data age in minutes based on source"""
    age_mapping = {
        'cointracking': 5.0,  # CoinTracking data is usually ~5 minutes old
        'binance': 1.0,       # Binance API is near real-time
        'kraken': 2.0,        # Kraken API ~2 minutes
        'local': 10.0,        # Local cache might be older
        'fallback': 15.0      # Fallback data could be quite old
    }
    return age_mapping.get(source_used.lower(), 10.0)