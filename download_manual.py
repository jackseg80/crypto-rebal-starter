#!/usr/bin/env python3
"""
Téléchargement manuel de cryptos spécifiques
"""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.price_history import price_history

# MODIFIEZ CETTE LISTE SELON VOS BESOINS
SYMBOLS_TO_DOWNLOAD = [
    "BTC", "ETH", "WSTETH", "RETH", "TBTC", 
    "USDT", "BNB", "XRP", "LINK", "DOGE",
    "USDC", "ADA", "SOL", "AVAX", "DOT"
]

DAYS = 365  # Modifiez selon vos besoins

async def download_manual():
    print(f"Téléchargement manuel de {len(SYMBOLS_TO_DOWNLOAD)} cryptos ({DAYS} jours chacune)...")
    
    for i, symbol in enumerate(SYMBOLS_TO_DOWNLOAD, 1):
        print(f"[{i}/{len(SYMBOLS_TO_DOWNLOAD)}] {symbol}...")
        try:
            await price_history.download_historical_data(symbol, days=DAYS)
            print(f"✅ {symbol}: OK")
        except Exception as e:
            print(f"❌ {symbol}: ÉCHEC - {e}")
        
        # Pause entre chaque téléchargement
        if i < len(SYMBOLS_TO_DOWNLOAD):
            await asyncio.sleep(0.5)
    
    print("Téléchargement manuel terminé !")

if __name__ == "__main__":
    asyncio.run(download_manual())