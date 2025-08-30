#!/usr/bin/env python3
"""
Script de debug pour analyser le problème CoinGecko
"""

import asyncio
import sys
import os

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_coingecko():
    from services.coingecko import coingecko_service
    
    print("Debug CoinGecko Service")
    print("=" * 40)
    
    # Vérifier la clé API
    print(f"API Key configurée: {bool(coingecko_service.api_key)}")
    if coingecko_service.api_key:
        print(f"API Key (premiers chars): {coingecko_service.api_key[:8]}...")
    
    # Tester le mapping symbol -> ID pour les cas problématiques
    symbol_mapping = await coingecko_service._get_symbol_to_id_mapping()
    
    test_symbols = ['BTC', 'ETH', 'SOL']
    print(f"\nMapping symboles vers IDs:")
    for symbol in test_symbols:
        coin_id = symbol_mapping.get(symbol.upper())
        print(f"  {symbol} -> {coin_id}")
    
    # Tester la classification directe
    print(f"\nTest de classification:")
    for symbol in test_symbols:
        result = await coingecko_service.classify_symbol(symbol)
        print(f"  {symbol} -> {result}")
    
    # Tester les métadonnées pour ETH
    print(f"\nMetadonnees ETH:")
    eth_metadata = await coingecko_service._get_coin_metadata('ethereum')
    if eth_metadata:
        print(f"  ID: {eth_metadata.get('id')}")
        print(f"  Name: {eth_metadata.get('name')}")
        print(f"  Symbol: {eth_metadata.get('symbol')}")
        categories = eth_metadata.get('categories', [])
        print(f"  Categories ({len(categories)}): {categories[:5]}...")  # Première 5
        
        # Vérifier notre mapping
        for category in categories[:5]:
            if category in coingecko_service.category_mapping:
                mapped_group = coingecko_service.category_mapping[category]
                print(f"    -> {category} maps to: {mapped_group}")
    
    # Stats du service
    stats = await coingecko_service.get_enrichment_stats()
    print(f"\nStats du service:")
    print(f"  Symbols cached: {stats['cache_stats']['symbols_cached']}")
    print(f"  Categories cached: {stats['cache_stats']['categories_cached']}")
    print(f"  Metadata cached: {stats['cache_stats']['metadata_cached']}")

if __name__ == "__main__":
    asyncio.run(debug_coingecko())