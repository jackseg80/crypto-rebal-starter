#!/usr/bin/env python3
"""
Téléchargement avec durées différentes selon l'importance
"""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.price_history import price_history

# Durées différentes selon l'importance
DOWNLOAD_PLAN = {
    # 5 ans pour les majors
    1825: ["BTC", "ETH"],
    
    # 3 ans pour les importants
    1095: ["WSTETH", "RETH", "TBTC", "USDT", "BNB"],
    
    # 1 an pour les autres
    365: ["XRP", "LINK", "DOGE", "USDC", "ADA", "SOL", "AVAX", "DOT", "UNI", "AAVE"]
}

async def download_by_importance():
    total = sum(len(symbols) for symbols in DOWNLOAD_PLAN.values())
    count = 0
    
    for days, symbols in DOWNLOAD_PLAN.items():
        print(f"\n=== Téléchargement {days} jours ===")
        for symbol in symbols:
            count += 1
            print(f"[{count}/{total}] {symbol} ({days}j)...")
            try:
                await price_history.download_historical_data(symbol, days=days)
                print(f"✅ {symbol}: OK")
            except Exception as e:
                print(f"❌ {symbol}: ÉCHEC - {e}")
            
            await asyncio.sleep(0.3)  # Pause courte
    
    print("\nTéléchargement par importance terminé !")

if __name__ == "__main__":
    asyncio.run(download_by_importance())