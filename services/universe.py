# services/universe.py
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from math import exp

from connectors.coingecko import CoinMeta, get_connector
from services.taxonomy import Taxonomy

log = logging.getLogger(__name__)

@dataclass
class ScoredCoin:
    """Coin avec score calculé et raisons détaillées."""
    meta: CoinMeta
    score: float
    reasons: Dict[str, float]  # composantes du score pour debug

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": asdict(self.meta),
            "score": self.score,
            "reasons": self.reasons
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScoredCoin':
        meta_data = data["meta"]
        meta = CoinMeta(**meta_data)
        return cls(
            meta=meta,
            score=data["score"],
            reasons=data["reasons"]
        )


@dataclass
class UniverseCache:
    """Cache structure pour l'univers scoré."""
    timestamp: float
    last_success_at: float
    source: str  # "cache" | "live"
    ttl_seconds: int
    scored_by_group: Dict[str, List[ScoredCoin]]

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "last_success_at": self.last_success_at,
            "source": self.source,
            "ttl_seconds": self.ttl_seconds,
            "scored_by_group": {
                group: [coin.to_dict() for coin in coins]
                for group, coins in self.scored_by_group.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UniverseCache':
        scored_by_group = {}
        for group, coins_data in data.get("scored_by_group", {}).items():
            scored_by_group[group] = [ScoredCoin.from_dict(coin_data) for coin_data in coins_data]

        return cls(
            timestamp=data["timestamp"],
            last_success_at=data["last_success_at"],
            source=data["source"],
            ttl_seconds=data["ttl_seconds"],
            scored_by_group=scored_by_group
        )


class UniverseManager:
    """Gestionnaire de l'univers de coins avec scoring et cache."""

    def __init__(self, config_path: str = "config/universe.json"):
        self.config_path = config_path
        self.cache_path = os.path.join("data", "cache", "universe.json")
        self._config: Optional[Dict[str, Any]] = None
        self._taxonomy: Optional[Taxonomy] = None

    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration universe depuis config/universe.json."""
        if self._config is not None:
            return self._config

        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                    log.debug(f"Loaded universe config from {self.config_path}")
            else:
                log.warning(f"Universe config not found: {self.config_path}, using defaults")
                self._config = self._get_default_config()
        except Exception as e:
            log.error(f"Failed to load universe config: {e}, using defaults")
            self._config = self._get_default_config()

        return self._config

    def _get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut si le fichier n'existe pas."""
        return {
            "features": {
                "priority_allocation": True
            },
            "scoring": {
                "weights": {
                    "w_cap_rank_inv": 0.3,
                    "w_liquidity": 0.25,
                    "w_momentum": 0.2,
                    "w_internal": 0.1,
                    "w_risk": 0.15
                }
            },
            "allocation": {
                "top_n": 3,
                "decay": [0.5, 0.3, 0.2],
                "softmax_temp": 1.0,
                "distribution_mode": "decay"
            },
            "guardrails": {
                "min_liquidity_usd": 50000,
                "max_weight_per_coin": 0.4,
                "min_trade_usd_default": 25.0
            },
            "lists": {
                "global_blacklist": [],
                "global_whitelist": [],
                "pinned_by_group": {}
            },
            "cache": {
                "ttl_seconds": 3600,
                "mode": "prefer_cache"
            }
        }

    def _get_taxonomy(self) -> Taxonomy:
        """Retourne l'instance Taxonomy."""
        if self._taxonomy is None:
            self._taxonomy = Taxonomy()
        return self._taxonomy

    def _load_cache(self) -> Optional[UniverseCache]:
        """Charge le cache depuis le disque."""
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cache = UniverseCache.from_dict(data)
                    log.debug(f"Loaded universe cache from {self.cache_path}")
                    return cache
        except Exception as e:
            log.error(f"Failed to load universe cache: {e}")

        return None

    def _save_cache(self, cache: UniverseCache) -> None:
        """Sauvegarde le cache sur disque."""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache.to_dict(), f, indent=2)
            log.debug(f"Saved universe cache to {self.cache_path}")
        except Exception as e:
            log.error(f"Failed to save universe cache: {e}")

    def build_group_universe(self, groups: List[str], current_portfolio: List[Dict[str, Any]] = None) -> Dict[str, List[CoinMeta]]:
        """
        Construit l'univers de coins par groupe.

        Args:
            groups: Liste des groupes à analyser
            current_portfolio: Portfolio actuel pour extraire les symbols existants

        Returns:
            Dict[group, List[CoinMeta]]
        """
        if not groups:
            return {}

        # Extraire les symbols du portfolio courant par groupe
        portfolio_symbols: Dict[str, List[str]] = {}
        if current_portfolio:
            taxonomy = self._get_taxonomy()
            for item in current_portfolio:
                symbol = item.get("symbol", "").upper()
                alias = item.get("alias", symbol).upper()
                group = taxonomy.get_group(alias)

                if group in groups:
                    if group not in portfolio_symbols:
                        portfolio_symbols[group] = []
                    if alias not in portfolio_symbols[group]:
                        portfolio_symbols[group].append(alias)

        # Récupérer les données marché
        all_symbols = []
        for group_symbols in portfolio_symbols.values():
            all_symbols.extend(group_symbols)

        if not all_symbols:
            log.warning("No symbols found in current portfolio for requested groups")
            return {}

        connector = get_connector()
        market_data = connector.get_market_snapshot(all_symbols)

        # Organiser par groupe
        universe_by_group: Dict[str, List[CoinMeta]] = {}
        for group in groups:
            universe_by_group[group] = []
            group_symbols = portfolio_symbols.get(group, [])

            for symbol in group_symbols:
                if symbol in market_data:
                    coin_meta = market_data[symbol]
                    # Assurer que l'alias correspond au groupe
                    coin_meta.alias = symbol
                    universe_by_group[group].append(coin_meta)

        log.info(f"Built universe for {len(groups)} groups with {len(all_symbols)} total symbols")
        return universe_by_group

    def score_group_universe(self, universe: Dict[str, List[CoinMeta]]) -> Dict[str, List[ScoredCoin]]:
        """
        Score l'univers de coins par groupe selon la configuration.

        Returns:
            Dict[group, List[ScoredCoin]] triés par score décroissant
        """
        config = self._load_config()
        weights = config["scoring"]["weights"]
        guardrails = config["guardrails"]
        blacklist = set(config["lists"]["global_blacklist"])

        scored_by_group: Dict[str, List[ScoredCoin]] = {}

        for group, coins in universe.items():
            scored_coins: List[ScoredCoin] = []

            for coin in coins:
                # Skip blacklistés
                if coin.symbol.upper() in blacklist or coin.alias.upper() in blacklist:
                    continue

                # Calcul des composantes du score
                reasons = self._calculate_score_components(coin, weights, guardrails)
                total_score = sum(reasons.values())

                scored_coin = ScoredCoin(
                    meta=coin,
                    score=total_score,
                    reasons=reasons
                )
                scored_coins.append(scored_coin)

            # Tri par score décroissant
            scored_coins.sort(key=lambda x: x.score, reverse=True)
            scored_by_group[group] = scored_coins

        return scored_by_group

    def _calculate_score_components(self, coin: CoinMeta, weights: Dict[str, float], guardrails: Dict[str, float]) -> Dict[str, float]:
        """Calcule les composantes détaillées du score pour un coin."""
        reasons = {}

        # 1. Cap rank inverse (plus petit rank = meilleur)
        cap_rank_score = 0.0
        if coin.market_cap_rank:
            # Transformation logarithmique : rank 1 -> 1.0, rank 100 -> ~0.5, rank 1000 -> 0.0
            import math
            cap_rank_score = max(0.0, 1.0 - math.log10(coin.market_cap_rank) / 3.0)
        reasons["cap_rank_inv"] = cap_rank_score * weights.get("w_cap_rank_inv", 0.0)

        # 2. Liquidité (volume/mcap ratio)
        liquidity_score = 0.0
        if coin.liquidity_proxy:
            # Normalisation: ~0.1 (10%) = bon, >0.5 = excellent
            liquidity_score = min(1.0, coin.liquidity_proxy * 2.0)
        elif coin.volume_24h and coin.volume_24h >= guardrails.get("min_liquidity_usd", 50000):
            # Fallback basé sur volume absolu si pas de ratio
            liquidity_score = min(1.0, coin.volume_24h / 1_000_000)  # 1M volume = score 1.0
        reasons["liquidity"] = liquidity_score * weights.get("w_liquidity", 0.0)

        # 3. Momentum (combinaison 30d et 90d)
        momentum_score = 0.0
        if coin.price_change_30d is not None and coin.price_change_90d is not None:
            # Normalisation -50% -> 0.0, 0% -> 0.5, +100% -> 1.0
            mom_30 = max(0.0, min(1.0, (coin.price_change_30d + 50) / 150))
            mom_90 = max(0.0, min(1.0, (coin.price_change_90d + 50) / 150))
            momentum_score = (mom_30 * 0.6 + mom_90 * 0.4)  # Plus de poids sur 30d
        elif coin.price_change_30d is not None:
            momentum_score = max(0.0, min(1.0, (coin.price_change_30d + 50) / 150))
        reasons["momentum"] = momentum_score * weights.get("w_momentum", 0.0)

        # 4. Signaux internes (placeholder pour intégrations futures)
        internal_score = 0.5  # Neutre par défaut
        reasons["internal"] = internal_score * weights.get("w_internal", 0.0)

        # 5. Pénalités de risque
        risk_penalty = 0.0
        for flag in coin.risk_flags:
            if flag == "small_cap":
                risk_penalty += 0.3
            elif flag == "low_volume":
                risk_penalty += 0.4
            elif flag == "incomplete_data":
                risk_penalty += 0.2

        risk_penalty = min(1.0, risk_penalty)  # Cap à 1.0
        reasons["risk_penalty"] = -risk_penalty * weights.get("w_risk", 0.0)

        return reasons

    def get_universe_cached(self, groups: List[str], current_portfolio: List[Dict[str, Any]] = None,
                           ttl: int = None, mode: str = None) -> Optional[Dict[str, List[ScoredCoin]]]:
        """
        Récupère l'univers scoré avec gestion de cache.

        Args:
            groups: Groupes demandés
            current_portfolio: Portfolio actuel
            ttl: TTL custom (sinon config)
            mode: "prefer_cache" | "cache_only" | "live_only"

        Returns:
            Dict[group, List[ScoredCoin]] ou None si indisponible
        """
        config = self._load_config()

        # Vérifier si la feature est activée
        if not config.get("features", {}).get("priority_allocation", False):
            log.info("Priority allocation feature disabled in config")
            return None

        cache_config = config["cache"]
        effective_ttl = ttl or cache_config.get("ttl_seconds", 3600)
        effective_mode = mode or cache_config.get("mode", "prefer_cache")

        # Modes de cache
        if effective_mode == "live_only":
            return self._get_universe_live(groups, current_portfolio, effective_ttl)

        # Essayer le cache en premier
        cache = self._load_cache()
        if cache and not cache.is_expired():
            # Vérifier que tous les groupes demandés sont présents
            if all(group in cache.scored_by_group for group in groups):
                log.info(f"Using cached universe (age: {time.time() - cache.timestamp:.0f}s)")
                # Filtrer selon les groupes demandés
                filtered = {group: cache.scored_by_group[group] for group in groups}
                return filtered

        if effective_mode == "cache_only":
            log.warning("Cache-only mode but no valid cache found")
            return None

        # Mode prefer_cache : fallback vers live
        return self._get_universe_live(groups, current_portfolio, effective_ttl)

    def _get_universe_live(self, groups: List[str], current_portfolio: List[Dict[str, Any]], ttl: int) -> Optional[Dict[str, List[ScoredCoin]]]:
        """Récupère l'univers en live et met à jour le cache."""
        try:
            log.info("Fetching live universe data...")

            # 1. Construire l'univers
            universe = self.build_group_universe(groups, current_portfolio)
            if not universe:
                log.error("Failed to build universe")
                return None

            # 2. Scorer l'univers
            scored_universe = self.score_group_universe(universe)

            # 3. Sauvegarder en cache
            cache = UniverseCache(
                timestamp=time.time(),
                last_success_at=time.time(),
                source="live",
                ttl_seconds=ttl,
                scored_by_group=scored_universe
            )
            self._save_cache(cache)

            log.info(f"Successfully fetched and cached universe for {len(groups)} groups")
            return scored_universe

        except Exception as e:
            log.error(f"Failed to fetch live universe: {e}")
            return None


# Instance globale réutilisable
_global_manager: Optional[UniverseManager] = None

def get_universe_manager() -> UniverseManager:
    """Retourne l'instance globale du gestionnaire d'univers."""
    global _global_manager
    if _global_manager is None:
        _global_manager = UniverseManager()
    return _global_manager

def get_universe_cached(groups: List[str], current_portfolio: List[Dict[str, Any]] = None,
                       ttl: int = 3600, mode: str = "prefer_cache") -> Optional[Dict[str, List[ScoredCoin]]]:
    """
    Fonction utilitaire pour récupérer l'univers scoré.

    Returns:
        Dict[group, List[ScoredCoin]] triés par score, ou None si indisponible
    """
    manager = get_universe_manager()
    return manager.get_universe_cached(groups, current_portfolio, ttl, mode)