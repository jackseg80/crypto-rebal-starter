#!/usr/bin/env python3
"""
Script pour analyser les catégories d'Ethereum
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_eth_categories():
    from services.coingecko import coingecko_service
    
    print("Debug Categories Ethereum")
    print("=" * 30)
    
    # Récupérer métadonnées ETH
    eth_metadata = await coingecko_service._get_coin_metadata('ethereum')
    if not eth_metadata:
        print("Impossible de récupérer les métadonnées Ethereum")
        return
    
    categories = eth_metadata.get('categories', [])
    print(f"Categories Ethereum ({len(categories)}):")
    
    for i, category in enumerate(categories):
        print(f"  {i+1}. '{category}'")
        
        # Vérifier si cette catégorie est dans notre mapping
        if category in coingecko_service.category_mapping:
            mapped_group = coingecko_service.category_mapping[category]
            print(f"      -> MAPS TO: {mapped_group}")
        else:
            print(f"      -> No mapping")
    
    print(f"\nOrdre de vérification dans classify_symbol:")
    print(f"1. coin_id check: 'ethereum' -> 'ETH' (should work)")
    print(f"2. categories loop: first match wins")
    
    # Test manuel de la classification
    result = await coingecko_service.classify_symbol('ETH')
    print(f"\nClassification result: ETH -> {result}")

if __name__ == "__main__":
    asyncio.run(debug_eth_categories())