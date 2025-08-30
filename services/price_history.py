"""
Historical Price Data Management - Système de cache d'historique OHLCV

Ce module gère le téléchargement et le cache local des données de prix historiques
pour éviter les limitations de quota des APIs et accélérer les calculs de métriques de risque.

Fonctionnalités:
- Téléchargement d'historique via Binance API (gratuite) avec fallbacks
- Cache local format JSON minimal [timestamp, close]
- Gestion des alias symboles réutilisant services/pricing.py
- Rate limiting intelligent et gestion d'erreurs robuste
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from urllib.error import URLError
import httpx
import re

# Réutiliser la configuration existante
from services.pricing import SYMBOL_ALIAS, FIAT_STABLE_FIXED

logger = logging.getLogger(__name__)

# Configuration
PRICE_HISTORY_DIR = "data/price_history"
LAST_UPDATE_FILE = os.path.join(PRICE_HISTORY_DIR, "last_update.json")
MAX_CONCURRENT_REQUESTS = 8  # Rate limiting Binance
BINANCE_REQUEST_DELAY = 0.1  # 100ms entre requêtes
CACHE_TTL_HOURS = 1  # TTL pour invalidation cache

# Fournisseurs d'historique par ordre de priorité
HISTORY_PROVIDERS = ["binance", "kraken", "bitget", "coincap"]

# Mapping symboles Binance (différent de CoinGecko)
BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT", 
    "SOL": "SOLUSDT",
    "AAVE": "AAVEUSDT",
    "LINK": "LINKUSDT",
    "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "DOT": "DOTUSDT",
    "AVAX": "AVAXUSDT",
    "NEAR": "NEARUSDT",
    "BCH": "BCHUSDT",
    "XLM": "XLMUSDT",
    "LTC": "LTCUSDT",
    "TRX": "TRXUSDT",
    "VET": "VETUSDT",
    "XTZ": "XTZUSDT",
    "ETC": "ETCUSDT",
    "XNO": "NANOUSDT",  # Nano sur Binance
    "ICP": "ICPUSDT",
    "BNB": "BNBUSDT",
    "CRO": "CROUSDT",
    "SUSHI": "SUSHIUSDT",
    "UNI": "UNIUSDT",
    "COMP": "COMPUSDT",
    "YFI": "YFIUSDT",
    "ZRX": "ZRXUSDT",
    "SHIB": "SHIBUSDT",
    "PEPE": "PEPEUSDT",
    "BONK": "BONKUSDT",
    "XMR": "XMRUSDT",
    "MANA": "MANAUSDT",
    "SAND": "SANDUSDT",
    "CHZ": "CHZUSDT",
    "XRP": "XRPUSDT",
    "INJ": "INJUSDT",
    "PAXG": "PAXGUSDT",
    "CAKE": "CAKEUSDT",
    "BAT": "BATUSDT",
    "ZEC": "ZECUSDT",
    "POL": "POLUSDT",  # Ex-MATIC
    "THETA": "THETAUSDT",
    "DYDX": "DYDXUSDT",
    "GNO": "GNOUSDT",
    "KSM": "KSMUSDT",
    "ALGO": "ALGOUSDT",
    "GHST": "GHSTUSDT",
    "BNT": "BNTUSDT",
    "GRT": "GRTUSDT",
    "QTUM": "QTUMUSDT",
    "IOTA": "IOTAUSDT",
    "KAVA": "KAVAUSDT",
    "ZIL": "ZILUSDT",
    "ANKR": "ANKRUSDT",
    "LRC": "LRCUSDT",
    "KNC": "KNCUSDT",
    "FIL": "FILUSDT",
    "IMX": "IMXUSDT",
    "RPL": "RPLUSDT",
    "HBAR": "HBARUSDT",
}

class PriceHistory:
    """Gestionnaire de cache d'historique de prix"""
    
    def __init__(self):
        self._ensure_data_dir()
        self._load_last_update()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
    def _ensure_data_dir(self):
        """Créer le répertoire de données si nécessaire"""
        os.makedirs(PRICE_HISTORY_DIR, exist_ok=True)
        
    def _load_last_update(self):
        """Charger les timestamps de dernière mise à jour"""
        try:
            if os.path.exists(LAST_UPDATE_FILE):
                with open(LAST_UPDATE_FILE, 'r', encoding='utf-8') as f:
                    self._last_update = json.load(f)
            else:
                self._last_update = {}
        except Exception as e:
            logger.warning(f"Erreur chargement last_update: {e}")
            self._last_update = {}
            
    def _save_last_update(self):
        """Sauvegarder les timestamps de dernière mise à jour"""
        try:
            with open(LAST_UPDATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._last_update, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur sauvegarde last_update: {e}")
            
    def _get_history_file_path(self, symbol: str) -> str:
        """Obtenir le chemin du fichier d'historique pour un symbole"""
        return os.path.join(PRICE_HISTORY_DIR, f"{symbol}_1d.json")
        
    def _resolve_symbol(self, symbol: str) -> str:
        """Résoudre un symbole via les alias (réutilise pricing.py)"""
        if not symbol:
            return symbol
        symbol = symbol.upper()
        base = SYMBOL_ALIAS.get(symbol, symbol)
        # CoinTracking variantes (ex: SOL2 -> SOL, TAO6 -> TAO)
        # Ne pas toucher aux symboles commençant par un chiffre (ex: 1INCH)
        if re.search(r"\d+$", base) and not re.match(r"^\d", base):
            base2 = re.sub(r"\d+$", "", base)
            base = SYMBOL_ALIAS.get(base2, base2)
        return base
        
    def _is_stablecoin(self, symbol: str) -> bool:
        """Vérifier si c'est une stablecoin"""
        return symbol.upper() in FIAT_STABLE_FIXED
        
    async def _download_binance_history(self, symbol: str, days: int = 365) -> List[Tuple[int, float]]:
        """Télécharger l'historique depuis Binance API (1d klines) avec gestion robuste des bornes.

        - Pour <=1000 jours, on demande simplement `limit=days` (sans start/end) pour obtenir les N derniers jours.
        - Pour >1000 jours, on pagine en remontant dans le temps jusqu'à couvrir `days`.
        """

        # Vérifier si le symbole est supporté par Binance
        binance_pair = BINANCE_SYMBOLS.get(symbol)
        if not binance_pair:
            logger.debug(f"Symbole {symbol} non supporté par Binance")
            return []

        url = "https://api.binance.com/api/v3/klines"

        async def fetch(params: Dict[str, int | str]) -> List[List[Union[int, str, float]]]:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                return r.json()  # type: ignore

        history: List[Tuple[int, float]] = []

        try:
            # Cas simple: on veut N derniers jours (<=1000)
            if days <= 1000:
                params = {
                    "symbol": binance_pair,
                    "interval": "1d",
                    "limit": days,
                }
                data = await fetch(params)
                for kline in data:
                    ts = int(kline[0]) // 1000
                    close_price = float(kline[4])
                    history.append((ts, close_price))
                # Trier et dédupliquer au cas où
                history = sorted(list({ts: (ts, px) for ts, px in history}.values()))
                logger.info(f"✅ Téléchargé {len(history)} points pour {symbol} (<=1000)")
                await asyncio.sleep(BINANCE_REQUEST_DELAY)
                return history

            # Pagination pour >1000 jours
            remaining = days
            end_time_ms = int(time.time() * 1000)
            while remaining > 0:
                limit = 1000 if remaining > 1000 else remaining
                params = {
                    "symbol": binance_pair,
                    "interval": "1d",
                    "endTime": end_time_ms,
                    "limit": limit,
                }
                data = await fetch(params)

                if not data:
                    break

                batch: List[Tuple[int, float]] = []
                for kline in data:
                    ts = int(kline[0]) // 1000
                    close_price = float(kline[4])
                    batch.append((ts, close_price))

                # Ajouter et avancer la fenêtre
                history.extend(batch)
                history = sorted(list({ts: (ts, px) for ts, px in history}.values()))

                # Prochaine page: fixer end_time_ms au début du batch récupéré - 1ms
                first_ts_ms = int(data[0][0])
                end_time_ms = first_ts_ms - 1
                remaining = days - len(history)

                # Protection rate limit
                await asyncio.sleep(BINANCE_REQUEST_DELAY)

                # Éviter boucles infinies si Binance ne renvoie plus rien
                if len(batch) == 0:
                    break

            # Ne garder que les `days` plus récents
            history = sorted(history)[-days:]
            logger.info(f"✅ Téléchargé {len(history)} points pour {symbol} (>1000)")
            return history

        except Exception as e:
            logger.warning(f"Erreur téléchargement Binance {symbol}: {e}")
            return []
                
    async def _download_kraken_history(self, symbol: str, days: int = 365) -> List[Tuple[int, float]]:
        """Télécharger l'historique depuis Kraken (OHLC 1d).

        Kraken requiert un mapping de paires; nous couvrons les majors et tentons des fallbacks.
        """

        # Mapping minimal des paires Kraken (USD)
        KRAKEN_PAIRS = {
            "BTC": "XXBTZUSD",
            "XBT": "XXBTZUSD",
            "ETH": "XETHZUSD",
            "SOL": "SOLUSD",
            "ADA": "ADAUSD",
            "DOT": "DOTUSD",
            "LINK": "LINKUSD",
            "AVAX": "AVAXUSD",
            "BNB": "BNBUSD",
            "XRP": "XRPUSD",
            "LTC": "LTCUSD",
            "BCH": "BCHUSD",
        }

        resolved = self._resolve_symbol(symbol)
        candidates = [
            KRAKEN_PAIRS.get(resolved),
            f"{resolved}USD",
            f"{resolved}USDT",
        ]
        pair = next((p for p in candidates if p), None)
        if not pair:
            return []

        since = int(time.time()) - days * 24 * 60 * 60

        url = "https://api.kraken.com/0/public/OHLC"
        params = {"pair": pair, "interval": 1440, "since": since}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                data = r.json()

            result = data.get("result") or {}
            # La clé de résultat peut être le nom de la paire demandée ou un alias renvoyé par Kraken
            series = None
            for k, v in result.items():
                if k.lower() == "last":
                    continue
                if isinstance(v, list):
                    series = v
                    break
            if not series:
                return []

            history: List[Tuple[int, float]] = []
            for row in series:
                # Format: [time, open, high, low, close, vwap, volume, count]
                ts = int(row[0])  # seconds
                close_price = float(row[4])
                history.append((ts, close_price))

            history = sorted(history)[-days:]
            logger.info(f"✅ Kraken: {resolved} -> {len(history)} points")
            await asyncio.sleep(BINANCE_REQUEST_DELAY)
            return history
        except Exception as e:
            logger.debug(f"Kraken fallback échec pour {symbol}: {e}")
            return []

    async def _download_bitget_history(self, symbol: str, days: int = 365) -> List[Tuple[int, float]]:
        """Télécharger l'historique depuis Bitget (1day candles).

        API publique v2: /api/v2/market/candles?symbol=BTCUSDT&granularity=1day
        Supporte limit et endTime en ms. On gère <=1000 et pagination >1000.
        """

        pair = f"{symbol.upper()}USDT"
        url = "https://api.bitget.com/api/v2/market/candles"

        async def fetch(limit: int, end_time_ms: Optional[int] = None) -> List[List[str]]:
            params: Dict[str, str] = {
                "symbol": pair,
                "granularity": "1day",
                "limit": str(limit),
            }
            if end_time_ms is not None:
                params["endTime"] = str(end_time_ms)
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    return []
                obj = r.json()
                data = obj.get("data") if isinstance(obj, dict) else None
                return data or []

        history: List[Tuple[int, float]] = []
        try:
            if days <= 1000:
                data = await fetch(days)
                for row in data:
                    # Format: [ts(ms), open, high, low, close, volume] (strings)
                    ts = int(row[0]) // 1000
                    close_price = float(row[4])
                    history.append((ts, close_price))
                history = sorted(list({ts: (ts, px) for ts, px in history}.values()))
                if history:
                    logger.info(f"✅ Bitget: {symbol} -> {len(history)} points (<=1000)")
                await asyncio.sleep(BINANCE_REQUEST_DELAY)
                return history

            # >1000: pagination avec endTime
            remaining = days
            end_time_ms = int(time.time() * 1000)
            while remaining > 0:
                limit = 1000 if remaining > 1000 else remaining
                data = await fetch(limit, end_time_ms)
                if not data:
                    break
                batch: List[Tuple[int, float]] = []
                for row in data:
                    ts = int(row[0]) // 1000
                    close_price = float(row[4])
                    batch.append((ts, close_price))
                history.extend(batch)
                history = sorted(list({ts: (ts, px) for ts, px in history}.values()))
                # endTime prochain = début du batch - 1ms
                first_ts_ms = int(data[0][0])
                end_time_ms = first_ts_ms - 1
                remaining = days - len(history)
                await asyncio.sleep(BINANCE_REQUEST_DELAY)
                if len(batch) == 0:
                    break

            history = sorted(history)[-days:]
            if history:
                logger.info(f"✅ Bitget: {symbol} -> {len(history)} points (>1000)")
            return history
        except Exception as e:
            logger.debug(f"Bitget fallback échec pour {symbol}: {e}")
            return []
        
    async def _generate_stable_history(self, symbol: str, days: int = 365) -> List[Tuple[int, float]]:
        """Générer un historique stable pour les stablecoins"""
        history = []
        now = int(time.time())
        
        for i in range(days):
            timestamp = now - (i * 24 * 60 * 60)  # i jours avant
            # Prix stable 1.0 avec très petit bruit pour éviter corrélation singulière
            price = 1.0 + (i % 7 - 3) * 0.001  # Bruit ±0.003
            history.append((timestamp, price))
            
        return sorted(history)  # Trier par timestamp croissant
        
    async def download_historical_data(self, symbol: str, days: int = 365, force_refresh: bool = False) -> bool:
        """
        Télécharger et stocker l'historique de prix pour un symbole
        
        Args:
            symbol: Symbole à télécharger
            days: Nombre de jours d'historique
            force_refresh: Forcer le re-téléchargement même si déjà en cache
            
        Returns:
            bool: True si succès, False sinon
        """
        
        # Résoudre le symbole via les alias
        resolved_symbol = self._resolve_symbol(symbol)
        file_path = self._get_history_file_path(resolved_symbol)
        
        # Vérifier si déjà en cache et récent (sauf si force_refresh)
        if not force_refresh and os.path.exists(file_path):
            last_update = self._last_update.get(resolved_symbol, 0)
            if time.time() - last_update < CACHE_TTL_HOURS * 3600:
                logger.debug(f"Cache valide pour {resolved_symbol}")
                return True
                
        logger.info(f"Téléchargement historique {resolved_symbol} ({days}j)...")
        
        # Cas spécial: stablecoins
        if self._is_stablecoin(resolved_symbol):
            history = await self._generate_stable_history(resolved_symbol, days)
        else:
            # Essayer les providers dans l'ordre
            history = []
            for provider in HISTORY_PROVIDERS:
                if provider == "binance":
                    history = await self._download_binance_history(resolved_symbol, days)
                elif provider == "kraken":
                    history = await self._download_kraken_history(resolved_symbol, days)
                elif provider == "bitget":
                    history = await self._download_bitget_history(resolved_symbol, days)
                
                if history:
                    break
                    
        if not history:
            logger.error(f"❌ Échec téléchargement {resolved_symbol}")
            return False
            
        # Sauvegarder l'historique
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f)
                
            # Mettre à jour le timestamp
            self._last_update[resolved_symbol] = int(time.time())
            self._save_last_update()
            
            logger.info(f"✅ Sauvegardé {len(history)} points pour {resolved_symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde {resolved_symbol}: {e}")
            return False
            
    def get_cached_history(self, symbol: str, days: Optional[int] = None) -> Optional[List[Tuple[int, float]]]:
        """
        Récupérer l'historique en cache local
        
        Args:
            symbol: Symbole à récupérer
            days: Nombre de jours max (None = tout)
            
        Returns:
            Liste de (timestamp, prix) ou None si pas en cache
        """
        
        resolved_symbol = self._resolve_symbol(symbol)
        file_path = self._get_history_file_path(resolved_symbol)
        
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                
            # Filtrer par nombre de jours si demandé
            if days:
                cutoff_time = int(time.time()) - (days * 24 * 60 * 60)
                history = [(ts, price) for ts, price in history if ts >= cutoff_time]
                
            return history
            
        except Exception as e:
            logger.error(f"Erreur lecture {resolved_symbol}: {e}")
            return None
            
    def get_symbols_with_cache(self) -> List[str]:
        """Obtenir la liste des symboles ayant un cache disponible"""
        symbols = []
        
        if not os.path.exists(PRICE_HISTORY_DIR):
            return symbols
            
        for file_name in os.listdir(PRICE_HISTORY_DIR):
            if file_name.endswith("_1d.json"):
                symbol = file_name.replace("_1d.json", "")
                symbols.append(symbol)
                
        return sorted(symbols)
        
    async def update_daily_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Mise à jour quotidienne des prix (ajouter les dernières bougies)
        
        Args:
            symbols: Liste de symboles à mettre à jour (None = tous)
            
        Returns:
            Dict[symbol, success] indiquant le succès pour chaque symbole
        """
        
        if symbols is None:
            symbols = self.get_symbols_with_cache()

        results: Dict[str, bool] = {}

        logger.info(f"Mise à jour quotidienne de {len(symbols)} symboles...")

        async def _update_one(sym: str) -> bool:
            try:
                resolved = self._resolve_symbol(sym)
                file_path = self._get_history_file_path(resolved)

                # Si pas de cache existant, télécharger une petite fenêtre initiale
                if not os.path.exists(file_path):
                    return await self.download_historical_data(resolved, days=7, force_refresh=True)

                # Charger l'existant complet
                existing = self.get_cached_history(resolved) or []
                last_ts = existing[-1][0] if existing else 0

                # Récupérer récents points (7 jours) via providers
                if self._is_stablecoin(resolved):
                    new_part = await self._generate_stable_history(resolved, days=7)
                else:
                    new_part: List[Tuple[int, float]] = []
                    for provider in HISTORY_PROVIDERS:
                        if provider == "binance":
                            new_part = await self._download_binance_history(resolved, days=7)
                        elif provider == "kraken":
                            new_part = await self._download_kraken_history(resolved, days=7)
                        elif provider == "bitget":
                            new_part = await self._download_bitget_history(resolved, days=7)
                        if new_part:
                            break

                if not new_part:
                    logger.debug(f"Aucune nouvelle donnée pour {resolved}")
                    return True

                # Fusionner sans écraser l'historique
                merged: Dict[int, Tuple[int, float]] = {ts: (ts, px) for ts, px in existing}
                for ts, px in new_part:
                    if ts > last_ts:
                        merged[ts] = (ts, px)
                    else:
                        # Même si ts <= last_ts, on peut rafraîchir la valeur
                        merged[ts] = (ts, px)

                combined = sorted(merged.values())

                # Sauvegarder
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(combined, f)
                self._last_update[resolved] = int(time.time())
                self._save_last_update()
                return True
            except Exception as e:
                logger.error(f"Erreur MAJ {sym}: {e}")
                return False

        # Traiter par lots (rate limit)
        batch_size = MAX_CONCURRENT_REQUESTS
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            # Lancer en parallèle
            tasks = [ _update_one(sym) for sym in batch ]
            # Attendre et collecter
            results_batch = await asyncio.gather(*tasks, return_exceptions=True)
            for sym, res in zip(batch, results_batch):
                results[sym] = (res is True)
            await asyncio.sleep(BINANCE_REQUEST_DELAY)

        successful = sum(1 for success in results.values() if success)
        logger.info(f"✅ Mis à jour {successful}/{len(symbols)} symboles")

        return results


# Instance globale
price_history = PriceHistory()


# API publique
async def download_historical_data(symbol: str, days: int = 365, force_refresh: bool = False) -> bool:
    """Download historical price data for a symbol"""
    return await price_history.download_historical_data(symbol, days, force_refresh)


def get_cached_history(symbol: str, days: Optional[int] = None) -> Optional[List[Tuple[int, float]]]:
    """Get cached historical price data"""
    return price_history.get_cached_history(symbol, days)


def get_symbols_with_cache() -> List[str]:
    """Get list of symbols with cached data"""
    return price_history.get_symbols_with_cache()


async def update_daily_prices(symbols: Optional[List[str]] = None) -> Dict[str, bool]:
    """Update daily prices for symbols"""
    return await price_history.update_daily_prices(symbols)


def calculate_returns(history: List[Tuple[int, float]], log_returns: bool = True) -> List[float]:
    """
    Calculer les rendements depuis un historique de prix
    
    Args:
        history: Liste de (timestamp, prix)
        log_returns: Utiliser les log-returns (recommandé)
        
    Returns:
        Liste des rendements (un de moins que les prix)
    """
    
    if len(history) < 2:
        return []
        
    prices = [price for _, price in sorted(history)]
    returns = []
    
    for i in range(1, len(prices)):
        if prices[i-1] <= 0 or prices[i] <= 0:
            continue  # Skip invalid prices
            
        if log_returns:
            ret = math.log(prices[i] / prices[i-1])
        else:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            
        returns.append(ret)
        
    return returns


# Import math pour les log returns
import math
