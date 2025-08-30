#!/usr/bin/env python3
"""
Initialisation du cache d'historique de prix

Ce script télécharge l'historique de prix (365 jours) pour tous les assets
présents dans le portfolio CoinTracking actuel.

Usage:
    python scripts/init_price_history.py
    python scripts/init_price_history.py --days 180 --force
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from services.price_history import price_history
from connectors.cointracking import get_current_balances as get_csv_balances

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_portfolio_symbols() -> set[str]:
    """Récupérer la liste des symboles du portfolio depuis le CSV"""
    
    logger.info("Récupération des symboles du portfolio depuis CSV...")
    
    try:
        # Récupérer les balances depuis CSV
        balances_response = await get_csv_balances()
        
        if not isinstance(balances_response, dict) or 'items' not in balances_response:
            logger.error("Réponse invalide du CSV CoinTracking")
            return set()
            
        balances = balances_response['items']
        
        # Extraire les symboles avec une valeur significative
        symbols = set()
        for balance in balances:
            symbol = balance.get('symbol', '').upper()
            value_usd = float(balance.get('value_usd', 0))
            
            if symbol and value_usd >= 1.0:  # Seuil minimum $1
                symbols.add(symbol)
                
        logger.info(f"✅ Trouvé {len(symbols)} symboles dans le portfolio")
        logger.debug(f"Symboles: {sorted(symbols)}")
        
        return symbols
        
    except Exception as e:
        logger.error(f"Erreur récupération portfolio: {e}")
        return set()

async def download_all_history(symbols: set[str], days: int = 365, force_refresh: bool = False):
    """Télécharger l'historique pour tous les symboles"""
    
    if not symbols:
        logger.warning("Aucun symbole à télécharger")
        return
        
    logger.info(f"Début téléchargement historique ({days} jours) pour {len(symbols)} symboles...")
    
    # Statistiques
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Traiter par lots pour éviter surcharge API
    batch_size = 8  # Respecter rate limits
    symbols_list = sorted(symbols)
    
    for i in range(0, len(symbols_list), batch_size):
        batch = symbols_list[i:i + batch_size]
        logger.info(f"Lot {i//batch_size + 1}/{(len(symbols_list) + batch_size - 1)//batch_size}: {batch}")
        
        # Lancer les téléchargements en parallèle pour ce lot
        tasks = []
        for symbol in batch:
            task = price_history.download_historical_data(symbol, days, force_refresh)
            tasks.append((symbol, task))
            
        # Attendre les résultats
        for symbol, task in tasks:
            try:
                success = await task
                if success:
                    success_count += 1
                    logger.info(f"✅ {symbol}: OK")
                else:
                    failed_count += 1
                    logger.warning(f"❌ {symbol}: ÉCHEC")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ {symbol}: ERREUR - {e}")
                
        # Pause entre lots
        if i + batch_size < len(symbols_list):
            await asyncio.sleep(2)  # 2s entre lots
            
    # Résumé final
    total = len(symbols)
    logger.info("=" * 60)
    logger.info("RÉSUMÉ INITIALISATION")
    logger.info("=" * 60)
    logger.info(f"📊 Total symboles: {total}")
    logger.info(f"✅ Succès: {success_count}")
    logger.info(f"❌ Échecs: {failed_count}")
    logger.info(f"⏸️  Ignorés: {skipped_count}")
    logger.info(f"📈 Taux de succès: {success_count/total*100:.1f}%")
    
    # Vérifier les symboles avec cache
    cached_symbols = price_history.get_symbols_with_cache()
    logger.info(f"💾 Symboles en cache: {len(cached_symbols)}")
    
    if failed_count > 0:
        failed_symbols = []
        for symbol in symbols:
            if symbol not in cached_symbols:
                failed_symbols.append(symbol)
                
        if failed_symbols:
            logger.warning(f"⚠️  Symboles sans cache: {failed_symbols}")
            logger.info("Astuce: Relancer le script avec --force pour réessayer")

def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(
        description="Initialiser le cache d'historique de prix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/init_price_history.py                    # 365 jours par défaut
  python scripts/init_price_history.py --days 180        # 180 jours
  python scripts/init_price_history.py --force           # Forcer re-téléchargement
  python scripts/init_price_history.py --symbols BTC ETH # Symboles spécifiques
        """
    )
    
    parser.add_argument(
        "--days", 
        type=int, 
        default=365,
        help="Nombre de jours d'historique à télécharger (défaut: 365)"
    )
    
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Forcer le re-téléchargement même si déjà en cache"
    )
    
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Symboles spécifiques à télécharger (défaut: tout le portfolio)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mode verbose (debug)"
    )
    
    args = parser.parse_args()
    
    # Configuration logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    logger.info("🚀 Initialisation du cache d'historique de prix")
    logger.info(f"📅 Période: {args.days} jours")
    logger.info(f"🔄 Force refresh: {args.force}")
    
    async def run():
        try:
            # Déterminer les symboles à traiter
            if args.symbols:
                symbols = set(s.upper() for s in args.symbols)
                logger.info(f"🎯 Symboles spécifiés: {sorted(symbols)}")
            else:
                symbols = await get_portfolio_symbols()
                
            if not symbols:
                logger.error("❌ Aucun symbole à traiter")
                return 1
                
            # Lancer le téléchargement
            await download_all_history(symbols, args.days, args.force)
            
            logger.info("🎉 Initialisation terminée!")
            return 0
            
        except KeyboardInterrupt:
            logger.info("❌ Interrupted par l'utilisateur")
            return 130
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
            return 1
            
    # Lancer le script async
    exit_code = asyncio.run(run())
    sys.exit(exit_code)

if __name__ == "__main__":
    main()