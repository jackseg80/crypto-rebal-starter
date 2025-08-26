#!/usr/bin/env python3
"""
Debug la fonction enhanced
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_enhanced():
    from services.taxonomy import auto_classify_symbol_enhanced, auto_classify_symbol
    
    print("Debug Enhanced Classification")
    print("=" * 35)
    
    test_symbols = ['ETH', 'BTC', 'DOGE', 'LINK']
    
    for symbol in test_symbols:
        print(f"\nTesting {symbol}:")
        
        # Test regex seul
        regex_result = auto_classify_symbol(symbol)
        print(f"  Regex only: {symbol} -> {regex_result}")
        
        # Test enhanced
        enhanced_result = await auto_classify_symbol_enhanced(symbol, use_coingecko=True)
        print(f"  Enhanced: {symbol} -> {enhanced_result}")
        
        # Test CoinGecko direct
        from services.coingecko import coingecko_service
        coingecko_result = await coingecko_service.classify_symbol(symbol)
        print(f"  CoinGecko direct: {symbol} -> {coingecko_result}")

if __name__ == "__main__":
    asyncio.run(debug_enhanced())