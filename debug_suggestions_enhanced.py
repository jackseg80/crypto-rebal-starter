#!/usr/bin/env python3
"""
Debug get_classification_suggestions_enhanced
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_suggestions():
    from services.taxonomy import get_classification_suggestions_enhanced
    
    print("Debug get_classification_suggestions_enhanced")
    print("=" * 45)
    
    test_symbols = ['BTC', 'ETH', 'SOL', 'DOGE', 'LINK']
    
    print(f"Testing symbols: {test_symbols}")
    
    suggestions = await get_classification_suggestions_enhanced(test_symbols, use_coingecko=True)
    
    print(f"Results:")
    for symbol, group in suggestions.items():
        print(f"  {symbol} -> {group}")

if __name__ == "__main__":
    asyncio.run(debug_suggestions())