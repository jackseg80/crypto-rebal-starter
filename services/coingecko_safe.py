"""
Safe CoinGecko service without aiohttp - no CTRL+C blocking
"""

class SafeCoinGeckoService:
    """Safe mock CoinGecko service"""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.api_key = None
        
    async def get_symbol_to_id_mapping(self):
        return {}
    
    async def get_coin_categories(self):
        return {}
    
    async def get_coin_metadata(self, coin_id: str):
        return {
            "id": coin_id,
            "symbol": coin_id.upper(),
            "name": coin_id.title(),
            "categories": [],
            "description": {"en": "Safe mode - no aiohttp"},
            "market_cap_rank": None
        }

# Safe instance
coingecko_service = SafeCoinGeckoService()

def get_coingecko_service():
    return coingecko_service