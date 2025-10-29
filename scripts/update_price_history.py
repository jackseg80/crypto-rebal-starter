#!/usr/bin/env python3
"""
Mise à jour quotidienne du cache d'historique de prix

Ce script met à jour les données de prix pour tous les symboles en cache
en téléchargeant seulement les dernières données (optimisé pour usage quotidien).

Usage:
    python scripts/update_price_history.py
    python scripts/update_price_history.py --symbols BTC ETH
    
Recommandé en cron job: 0 9 * * * /path/to/update_price_history.py
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from services.price_history import price_history

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def update_all_symbols(symbols: list[str] = None) -> dict[str, bool]:
    """Mettre à jour l'historique pour tous les symboles ou une liste spécifique"""
    
    if symbols is None:
        symbols = price_history.get_symbols_with_cache()
        source = "cache"
    else:
        symbols = [s.upper() for s in symbols]
        source = "spécifiés"
        
    if not symbols:
        logger.warning("Aucun symbole à mettre à jour")
        return {}
        
    logger.info(f"🔄 Mise à jour de {len(symbols)} symboles ({source})")
    logger.debug(f"Symboles: {symbols}")
    
    # Lancer la mise à jour
    start_time = datetime.now()
    results = await price_history.update_daily_prices(symbols)
    duration = datetime.now() - start_time
    
    # Statistiques
    total = len(results)
    success = sum(1 for r in results.values() if r)
    failed = total - success
    
    logger.info("=" * 50)
    logger.info("RÉSUMÉ MISE À JOUR")
    logger.info("=" * 50)
    logger.info(f"⏱️  Durée: {duration.total_seconds():.1f}s")
    logger.info(f"📊 Total: {total}")
    logger.info(f"✅ Succès: {success}")
    logger.info(f"❌ Échecs: {failed}")
    
    if failed > 0:
        failed_symbols = [sym for sym, res in results.items() if not res]
        logger.warning(f"⚠️  Échecs: {failed_symbols}")
    else:
        logger.info("🎉 Tous les symboles mis à jour avec succès!")
        
    return results

def check_cache_freshness() -> dict[str, int]:
    """Vérifier la fraîcheur du cache"""
    
    symbols = price_history.get_symbols_with_cache()
    if not symbols:
        return {}
        
    freshness = {}
    now = datetime.now()
    
    for symbol in symbols:
        try:
            last_update = price_history._last_update.get(symbol, 0)
            age_hours = (now.timestamp() - last_update) / 3600
            freshness[symbol] = int(age_hours)
        except Exception as e:
            logger.debug(f"Failed to get freshness for {symbol}: {e}")
            freshness[symbol] = 999  # Très ancien
            
    return freshness

def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(
        description="Mise à jour quotidienne du cache d'historique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/update_price_history.py                     # Tous les symboles
  python scripts/update_price_history.py --symbols BTC ETH   # Symboles spécifiques
  python scripts/update_price_history.py --check-freshness   # Vérifier fraîcheur seulement
        """
    )
    
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Symboles spécifiques à mettre à jour (défaut: tous)"
    )
    
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Vérifier seulement la fraîcheur du cache"
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
    
    logger.info("🔄 Mise à jour cache d'historique de prix")
    
    async def run():
        try:
            # Mode vérification de fraîcheur seulement
            if args.check_freshness:
                logger.info("🔍 Vérification de la fraîcheur du cache...")
                freshness = check_cache_freshness()
                
                if not freshness:
                    logger.info("📭 Aucun cache trouvé")
                    return 0
                    
                logger.info(f"📊 État du cache ({len(freshness)} symboles):")
                
                fresh = []  # < 24h
                stale = []  # 24h-48h
                old = []    # > 48h
                
                for symbol, age_hours in freshness.items():
                    if age_hours < 24:
                        fresh.append(f"{symbol}({age_hours}h)")
                    elif age_hours < 48:
                        stale.append(f"{symbol}({age_hours}h)")
                    else:
                        old.append(f"{symbol}({age_hours}h)")
                        
                if fresh:
                    logger.info(f"✅ Frais (<24h): {fresh}")
                if stale:
                    logger.info(f"⚠️  Anciens (24-48h): {stale}")
                if old:
                    logger.info(f"❌ Très anciens (>48h): {old}")
                    
                return 0
                
            # Mode mise à jour normale
            results = await update_all_symbols(args.symbols)
            
            # Code de retour basé sur le succès
            if not results:
                return 1  # Aucune donnée
            elif all(results.values()):
                return 0  # Tout OK
            else:
                return 2  # Succès partiel
                
        except KeyboardInterrupt:
            logger.info("❌ Interrompu par l'utilisateur")
            return 130
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
            return 1
            
    # Lancer le script async
    exit_code = asyncio.run(run())
    
    if exit_code == 0:
        logger.info("✅ Mise à jour terminée avec succès")
    elif exit_code == 2:
        logger.warning("⚠️  Mise à jour terminée avec quelques échecs")
    else:
        logger.error("❌ Mise à jour échouée")
        
    sys.exit(exit_code)

if __name__ == "__main__":
    main()