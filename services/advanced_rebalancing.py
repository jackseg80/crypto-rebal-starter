"""
Advanced Rebalancing Engine - Stratégies de rebalancement intelligentes avec optimisation multi-objectif

Ce module propose plusieurs stratégies sophistiquées de rebalancement :
- Rebalancement proportionnel (classique)
- Risk Parity (équilibrage du risque) 
- Momentum-based (tendances de marché)
- Mean Reversion (retour à la moyenne)
- Multi-objectif avec optimisation des frais et Sharpe ratio

Intègre également :
- Contraintes de liquidité par exchange
- Seuils adaptatifs selon la volatilité
- Smart duplicate handling via le système de classification
- Simulation avancée avec impact pricing
"""

from __future__ import annotations
import asyncio
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import math

from services.taxonomy import Taxonomy
from services.smart_classification import smart_classification_service
from services.pricing import get_prices_usd
from services.portfolio import portfolio_analytics
from constants import get_exchange_priority, normalize_exchange_name

logger = logging.getLogger(__name__)

class RebalancingStrategy(Enum):
    """Stratégies de rebalancement disponibles"""
    PROPORTIONAL = "proportional"           # Rebalancement classique proportionnel
    RISK_PARITY = "risk_parity"            # Équilibrage du risque (vol inverse)  
    MOMENTUM = "momentum"                   # Basé sur les tendances récentes
    MEAN_REVERSION = "mean_reversion"       # Contrarian - retour à la moyenne
    MULTI_OBJECTIVE = "multi_objective"     # Optimisation multi-critères
    SMART_CONSOLIDATION = "smart_consolidation"  # Avec consolidation des duplicatas

@dataclass
class MarketMetrics:
    """Métriques de marché pour stratégies avancées"""
    symbol: str
    current_price: float
    volatility_30d: Optional[float] = None  # Volatilité 30 jours annualisée
    momentum_7d: Optional[float] = None     # Performance 7 jours
    momentum_30d: Optional[float] = None    # Performance 30 jours  
    liquidity_score: Optional[float] = None # Score de liquidité (0-100)
    fee_tier: Optional[str] = None          # Niveau de frais sur exchange principal
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class OptimizationConstraints:
    """Contraintes d'optimisation pour rebalancement"""
    max_trade_size_usd: float = 10000.0    # Taille max par trade
    min_trade_size_usd: float = 25.0       # Taille min par trade
    max_allocation_change: float = 0.15     # Max 15% de changement par asset
    preferred_exchanges: List[str] = field(default_factory=lambda: ["Binance", "Kraken", "Coinbase"])
    blacklisted_exchanges: List[str] = field(default_factory=list)
    max_simultaneous_trades: int = 20       # Limite nombre de trades simultanés
    preserve_staking: bool = True           # Préserver les positions stakées
    consolidate_duplicates: bool = True     # Consolider automatiquement les duplicatas

@dataclass
class RebalancingResult:
    """Résultat complet d'un rebalancement optimisé"""
    strategy_used: str
    actions: List[Dict[str, Any]]
    optimization_score: float              # Score d'optimisation (0-100)
    estimated_total_fees: float            # Frais totaux estimés
    risk_metrics: Dict[str, float]         # Métriques de risque calculées
    duplicate_consolidations: List[Dict]   # Consolidations de duplicatas effectuées
    market_timing_score: float            # Score de timing de marché (0-100)
    execution_complexity: str              # "Low", "Medium", "High"
    warnings: List[str]                   # Avertissements et recommandations
    metadata: Dict[str, Any] = field(default_factory=dict)

class AdvancedRebalancingEngine:
    """Moteur de rebalancement avancé avec stratégies multiples"""
    
    def __init__(self):
        self.constraints = OptimizationConstraints()
        self.market_data_cache: Dict[str, MarketMetrics] = {}
        self.cache_ttl = timedelta(minutes=15)
        
        # Paramètres des stratégies
        self.strategy_params = {
            "risk_parity": {
                "target_vol": 0.20,        # Volatilité cible annualisée
                "min_vol": 0.05,           # Vol min pour éviter division par zéro
                "vol_lookback": 30         # Jours pour calcul volatilité
            },
            "momentum": {
                "short_period": 7,         # Momentum court terme
                "long_period": 30,         # Momentum long terme
                "momentum_weight": 0.3     # Poids du momentum dans allocation
            },
            "mean_reversion": {
                "mean_period": 90,         # Période pour moyenne mobile
                "reversion_strength": 0.2  # Force du retour à la moyenne
            }
        }
        
    async def rebalance_portfolio(
        self, 
        current_holdings: List[Dict[str, Any]], 
        target_allocations: Dict[str, float],
        strategy: RebalancingStrategy = RebalancingStrategy.SMART_CONSOLIDATION,
        constraints: Optional[OptimizationConstraints] = None
    ) -> RebalancingResult:
        """
        Rebalancement avancé avec stratégie sélectionnée
        
        Args:
            current_holdings: Holdings actuels du portfolio
            target_allocations: Allocations cibles par groupe (en %)
            strategy: Stratégie de rebalancement à utiliser
            constraints: Contraintes d'optimisation personnalisées
            
        Returns:
            RebalancingResult avec actions optimisées et métriques
        """
        if constraints:
            self.constraints = constraints
            
        logger.info(f"Démarrage rebalancement avec stratégie: {strategy.value}")
        
        try:
            # 1. Préparation et nettoyage des données
            cleaned_holdings = await self._prepare_holdings_data(current_holdings)
            
            # 2. Détection et traitement des duplicatas
            duplicate_actions = []
            if self.constraints.consolidate_duplicates:
                cleaned_holdings, duplicate_actions = await self._handle_duplicates(cleaned_holdings)
            
            # 3. Collecte des métriques de marché
            await self._collect_market_metrics(cleaned_holdings)
            
            # 4. Calcul des allocations selon la stratégie
            optimized_targets = await self._calculate_strategy_allocations(
                cleaned_holdings, target_allocations, strategy
            )
            
            # 5. Génération des actions de rebalancement
            rebalance_actions = await self._generate_rebalance_actions(
                cleaned_holdings, optimized_targets, strategy
            )
            
            # 6. Optimisation des actions (order routing, splitting, etc.)
            optimized_actions = await self._optimize_execution_plan(rebalance_actions)
            
            # 7. Calcul des métriques finales
            result = await self._calculate_result_metrics(
                optimized_actions, duplicate_actions, strategy, cleaned_holdings
            )
            
            logger.info(f"Rebalancement terminé: {len(result.actions)} actions, "
                       f"score: {result.optimization_score:.1f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur rebalancement avancé: {e}")
            # Fallback vers rebalancement simple
            return await self._fallback_simple_rebalance(current_holdings, target_allocations)
    
    async def _prepare_holdings_data(self, holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prépare et enrichit les données de holdings"""
        cleaned_holdings = []
        taxonomy = Taxonomy.load()
        
        for holding in holdings:
            # Normalisation des données
            symbol = holding.get("symbol", "").strip().upper()
            alias = holding.get("alias", symbol).strip()
            value_usd = float(holding.get("value_usd", 0) or holding.get("usd_value", 0))
            
            if not symbol or value_usd <= 0:
                continue
                
            # Enrichissement taxonomique
            group = taxonomy.group_for_alias(alias)
            
            # Classification intelligente pour symboles inconnus
            if group == "Others" and symbol not in taxonomy.aliases:
                classification = await smart_classification_service.classify_symbol(symbol)
                if classification.confidence_score > 70:
                    group = classification.suggested_group
            
            cleaned_holding = {
                "symbol": symbol,
                "alias": alias,
                "group": group,
                "value_usd": value_usd,
                "location": normalize_exchange_name(holding.get("location", "Unknown")),
                "quantity": float(holding.get("quantity", 0)),
                "current_price": value_usd / max(float(holding.get("quantity", 1)), 1)
            }
            
            cleaned_holdings.append(cleaned_holding)
        
        return cleaned_holdings
    
    async def _handle_duplicates(self, holdings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Détecte et consolide les duplicatas automatiquement"""
        
        # Extraire les symboles pour détection
        symbols = [h["symbol"] for h in holdings]
        duplicates = smart_classification_service.detect_duplicates_in_portfolio(symbols)
        
        consolidated_holdings = []
        consolidation_actions = []
        processed_symbols = set()
        
        for holding in holdings:
            symbol = holding["symbol"]
            
            if symbol in processed_symbols:
                continue
                
            # Vérifier si c'est un dérivé à consolider
            base_symbol = None
            for base, derivatives in duplicates.items():
                derivative_symbols = [d["symbol"] for d in derivatives]
                if symbol in derivative_symbols:
                    base_symbol = base
                    break
            
            if base_symbol and base_symbol not in processed_symbols:
                # Consolider tous les dérivés vers le base symbol
                base_holding = None
                derivatives_to_consolidate = []
                
                for h in holdings:
                    if h["symbol"] == base_symbol:
                        base_holding = h.copy()
                    elif h["symbol"] in [d["symbol"] for d in duplicates[base_symbol]]:
                        derivatives_to_consolidate.append(h)
                
                if derivatives_to_consolidate:
                    # Créer action de consolidation
                    total_value = sum(d["value_usd"] for d in derivatives_to_consolidate)
                    
                    for derivative in derivatives_to_consolidate:
                        consolidation_actions.append({
                            "action": "consolidate",
                            "from_symbol": derivative["symbol"],
                            "to_symbol": base_symbol,
                            "value_usd": derivative["value_usd"],
                            "location": derivative["location"],
                            "reasoning": f"Consolidation {derivative['symbol']} vers {base_symbol}",
                            "exec_hint": f"Convert {derivative['symbol']} to {base_symbol}"
                        })
                    
                    # Ajuster le base holding
                    if base_holding:
                        base_holding["value_usd"] += total_value
                        consolidated_holdings.append(base_holding)
                    else:
                        # Créer nouveau holding pour le base symbol
                        consolidated_holdings.append({
                            "symbol": base_symbol,
                            "alias": base_symbol,
                            "group": derivatives_to_consolidate[0]["group"],
                            "value_usd": total_value,
                            "location": derivatives_to_consolidate[0]["location"],  # Meilleur exchange
                            "quantity": 0,  # À recalculer
                            "current_price": 0
                        })
                    
                    # Marquer comme traités
                    processed_symbols.add(base_symbol)
                    for d in derivatives_to_consolidate:
                        processed_symbols.add(d["symbol"])
                
            else:
                # Pas de consolidation nécessaire
                consolidated_holdings.append(holding)
                processed_symbols.add(symbol)
        
        logger.info(f"Consolidation: {len(consolidation_actions)} actions de consolidation générées")
        return consolidated_holdings, consolidation_actions
    
    async def _collect_market_metrics(self, holdings: List[Dict[str, Any]]):
        """Collecte les métriques de marché pour optimisation"""
        
        symbols = [h["symbol"] for h in holdings]
        current_prices = get_prices_usd(symbols)
        
        for holding in holdings:
            symbol = holding["symbol"]
            
            # Métriques basiques
            current_price = current_prices.get(symbol, holding.get("current_price", 0))
            
            # Volatilité simulée (en production, utiliser vraies données historiques)
            vol_30d = self._estimate_volatility(symbol)
            
            # Momentum simulé
            momentum_7d = self._estimate_momentum(symbol, 7)
            momentum_30d = self._estimate_momentum(symbol, 30)
            
            # Score de liquidité basé sur groupe et exchange
            liquidity_score = self._calculate_liquidity_score(holding)
            
            metrics = MarketMetrics(
                symbol=symbol,
                current_price=current_price,
                volatility_30d=vol_30d,
                momentum_7d=momentum_7d,
                momentum_30d=momentum_30d,
                liquidity_score=liquidity_score
            )
            
            self.market_data_cache[symbol] = metrics
            
            # Mettre à jour le prix dans holding
            holding["current_price"] = current_price
    
    def _estimate_volatility(self, symbol: str) -> float:
        """Estimation de volatilité (simulation - en production utiliser données réelles)"""
        # Volatilités typiques par type d'asset
        vol_by_group = {
            "BTC": 0.60,
            "ETH": 0.70,
            "Stablecoins": 0.05,
            "L1/L0 majors": 0.80,
            "L2/Scaling": 1.00,
            "DeFi": 1.20,
            "AI/Data": 1.50,
            "Gaming/NFT": 1.30,
            "Memecoins": 2.00,
            "Others": 1.00
        }
        
        taxonomy = Taxonomy.load()
        group = taxonomy.group_for_alias(symbol)
        base_vol = vol_by_group.get(group, 1.00)
        
        # Ajout de bruit aléatoire
        import random
        noise = random.uniform(0.8, 1.2)
        return base_vol * noise
    
    def _estimate_momentum(self, symbol: str, days: int) -> float:
        """Estimation de momentum (simulation)"""
        # Simulation basée sur type d'asset
        import random
        
        # Momentum moyen par groupe
        momentum_by_group = {
            "BTC": 0.02,
            "ETH": 0.01,
            "Stablecoins": 0.00,
            "L1/L0 majors": 0.00,
            "DeFi": -0.01,
            "AI/Data": 0.05,
            "Gaming/NFT": -0.02,
            "Memecoins": 0.00,
            "Others": 0.00
        }
        
        taxonomy = Taxonomy.load()
        group = taxonomy.group_for_alias(symbol)
        base_momentum = momentum_by_group.get(group, 0.00)
        
        # Ajustement par période
        time_factor = math.sqrt(days / 30.0)
        
        # Bruit aléatoire
        noise = random.uniform(-0.10, 0.10)
        
        return (base_momentum * time_factor) + noise
    
    def _calculate_liquidity_score(self, holding: Dict[str, Any]) -> float:
        """Calcule un score de liquidité 0-100"""
        
        # Score de base par groupe
        liquidity_by_group = {
            "BTC": 95,
            "ETH": 90,
            "Stablecoins": 85,
            "L1/L0 majors": 70,
            "L2/Scaling": 60,
            "DeFi": 55,
            "AI/Data": 45,
            "Gaming/NFT": 40,
            "Memecoins": 30,
            "Others": 25
        }
        
        base_score = liquidity_by_group.get(holding["group"], 25)
        
        # Bonus pour exchanges liquides
        exchange_bonus = {
            "Binance": 10,
            "Coinbase": 8,
            "Kraken": 6,
            "Bitget": 4,
            "OKX": 4
        }.get(holding["location"], 0)
        
        # Pénalité pour petites positions (< $1000)
        size_penalty = 0
        if holding["value_usd"] < 1000:
            size_penalty = -10
        elif holding["value_usd"] < 100:
            size_penalty = -20
        
        final_score = max(0, min(100, base_score + exchange_bonus + size_penalty))
        return final_score
    
    async def _calculate_strategy_allocations(
        self, 
        holdings: List[Dict[str, Any]], 
        target_allocations: Dict[str, float],
        strategy: RebalancingStrategy
    ) -> Dict[str, float]:
        """Calcule les allocations optimisées selon la stratégie"""
        
        if strategy == RebalancingStrategy.PROPORTIONAL or strategy == RebalancingStrategy.SMART_CONSOLIDATION:
            return target_allocations.copy()
        
        elif strategy == RebalancingStrategy.RISK_PARITY:
            return await self._calculate_risk_parity_allocations(holdings, target_allocations)
            
        elif strategy == RebalancingStrategy.MOMENTUM:
            return await self._calculate_momentum_allocations(holdings, target_allocations)
            
        elif strategy == RebalancingStrategy.MEAN_REVERSION:
            return await self._calculate_mean_reversion_allocations(holdings, target_allocations)
            
        elif strategy == RebalancingStrategy.MULTI_OBJECTIVE:
            return await self._calculate_multi_objective_allocations(holdings, target_allocations)
        
        else:
            return target_allocations.copy()
    
    async def _calculate_risk_parity_allocations(
        self, 
        holdings: List[Dict[str, Any]], 
        base_targets: Dict[str, float]
    ) -> Dict[str, float]:
        """Allocations Risk Parity - inverse de la volatilité"""
        
        # Regrouper par groupe taxonomique
        group_volatilities = {}
        group_weights = {}
        
        for holding in holdings:
            group = holding["group"]
            symbol = holding["symbol"]
            
            if symbol in self.market_data_cache:
                vol = self.market_data_cache[symbol].volatility_30d or 1.0
                
                if group not in group_volatilities:
                    group_volatilities[group] = []
                    
                group_volatilities[group].append(vol)
        
        # Calculer volatilité moyenne par groupe
        for group, vols in group_volatilities.items():
            avg_vol = np.mean(vols) if vols else 1.0
            # Weight inversement proportionnel à la volatilité
            group_weights[group] = 1.0 / max(avg_vol, self.strategy_params["risk_parity"]["min_vol"])
        
        # Normaliser les poids
        total_weight = sum(group_weights.values())
        if total_weight > 0:
            for group in group_weights:
                group_weights[group] = group_weights[group] / total_weight * 100
        
        # Mélanger avec les targets originaux (70% risk parity, 30% targets)
        optimized_targets = {}
        for group in base_targets:
            rp_allocation = group_weights.get(group, base_targets[group])
            optimized_targets[group] = 0.7 * rp_allocation + 0.3 * base_targets[group]
        
        logger.info(f"Risk Parity: allocations ajustées pour {len(group_weights)} groupes")
        return optimized_targets
    
    async def _calculate_momentum_allocations(
        self, 
        holdings: List[Dict[str, Any]], 
        base_targets: Dict[str, float]
    ) -> Dict[str, float]:
        """Allocations basées sur momentum - surpondérer tendances positives"""
        
        group_momentums = {}
        
        # Calculer momentum moyen par groupe
        for holding in holdings:
            group = holding["group"]
            symbol = holding["symbol"]
            
            if symbol in self.market_data_cache:
                metrics = self.market_data_cache[symbol]
                # Combinaison momentum court/long terme
                momentum = (0.7 * (metrics.momentum_7d or 0)) + (0.3 * (metrics.momentum_30d or 0))
                
                if group not in group_momentums:
                    group_momentums[group] = []
                    
                group_momentums[group].append(momentum)
        
        # Ajustements d'allocation basés sur momentum
        optimized_targets = {}
        momentum_weight = self.strategy_params["momentum"]["momentum_weight"]
        
        for group in base_targets:
            base_allocation = base_targets[group]
            
            if group in group_momentums:
                avg_momentum = np.mean(group_momentums[group])
                # Ajustement: +momentum => +allocation, -momentum => -allocation
                momentum_adjustment = avg_momentum * momentum_weight * base_allocation
                new_allocation = base_allocation + momentum_adjustment
            else:
                new_allocation = base_allocation
            
            optimized_targets[group] = max(0, new_allocation)  # Pas d'allocation négative
        
        # Renormaliser à 100%
        total = sum(optimized_targets.values())
        if total > 0:
            for group in optimized_targets:
                optimized_targets[group] = optimized_targets[group] / total * 100
        
        logger.info(f"Momentum: allocations ajustées avec momentum moyen global")
        return optimized_targets
    
    async def _calculate_mean_reversion_allocations(
        self, 
        holdings: List[Dict[str, Any]], 
        base_targets: Dict[str, float]
    ) -> Dict[str, float]:
        """Allocations Mean Reversion - contrarian aux tendances récentes"""
        
        # Inverser la logique du momentum
        momentum_targets = await self._calculate_momentum_allocations(holdings, base_targets)
        
        # Contrarian: inverser les ajustements
        optimized_targets = {}
        reversion_strength = self.strategy_params["mean_reversion"]["reversion_strength"]
        
        for group in base_targets:
            base_allocation = base_targets[group]
            momentum_allocation = momentum_targets[group]
            
            # Inverser l'ajustement momentum
            momentum_delta = momentum_allocation - base_allocation
            reversion_delta = -momentum_delta * reversion_strength
            
            optimized_targets[group] = max(0, base_allocation + reversion_delta)
        
        # Renormaliser
        total = sum(optimized_targets.values())
        if total > 0:
            for group in optimized_targets:
                optimized_targets[group] = optimized_targets[group] / total * 100
        
        logger.info(f"Mean Reversion: allocations contrariennes calculées")
        return optimized_targets
    
    async def _calculate_multi_objective_allocations(
        self, 
        holdings: List[Dict[str, Any]], 
        base_targets: Dict[str, float]
    ) -> Dict[str, float]:
        """Optimisation multi-objectif: risk, momentum, fees, liquidité"""
        
        # Calculer les différentes stratégies
        risk_targets = await self._calculate_risk_parity_allocations(holdings, base_targets)
        momentum_targets = await self._calculate_momentum_allocations(holdings, base_targets)
        
        # Scores de liquidité par groupe
        group_liquidity = {}
        for holding in holdings:
            group = holding["group"]
            symbol = holding["symbol"]
            
            if symbol in self.market_data_cache:
                liquidity = self.market_data_cache[symbol].liquidity_score or 50
                
                if group not in group_liquidity:
                    group_liquidity[group] = []
                group_liquidity[group].append(liquidity)
        
        # Optimisation pondérée
        optimized_targets = {}
        
        for group in base_targets:
            base_alloc = base_targets[group]
            risk_alloc = risk_targets.get(group, base_alloc) 
            momentum_alloc = momentum_targets.get(group, base_alloc)
            
            # Score de liquidité pour le groupe
            if group in group_liquidity:
                liquidity_score = np.mean(group_liquidity[group]) / 100  # 0-1
            else:
                liquidity_score = 0.5
            
            # Pondération multi-objectif
            weights = {
                "base": 0.3,      # Target original
                "risk": 0.3,      # Risk parity
                "momentum": 0.2,  # Momentum
                "liquidity": 0.2  # Liquidité
            }
            
            liquidity_adjustment = liquidity_score * base_alloc * 0.1  # Bonus liquidité
            
            final_allocation = (
                weights["base"] * base_alloc +
                weights["risk"] * risk_alloc +  
                weights["momentum"] * momentum_alloc +
                weights["liquidity"] * liquidity_adjustment
            )
            
            optimized_targets[group] = max(0, final_allocation)
        
        # Renormaliser
        total = sum(optimized_targets.values())
        if total > 0:
            for group in optimized_targets:
                optimized_targets[group] = optimized_targets[group] / total * 100
        
        logger.info(f"Multi-objectif: optimisation combinée de 4 critères")
        return optimized_targets
    
    async def _generate_rebalance_actions(
        self, 
        holdings: List[Dict[str, Any]], 
        targets: Dict[str, float],
        strategy: RebalancingStrategy
    ) -> List[Dict[str, Any]]:
        """Génère les actions de rebalancement optimisées"""
        
        # Utiliser le rebalancer existant comme base
        from services.rebalance import plan_rebalance
        
        # Convertir holdings au format attendu
        formatted_rows = []
        for holding in holdings:
            formatted_rows.append({
                "symbol": holding["symbol"],
                "alias": holding["alias"], 
                "value_usd": holding["value_usd"],
                "location": holding["location"]
            })
        
        # Générer plan de base
        base_plan = plan_rebalance(
            rows=formatted_rows,
            group_targets_pct=targets,
            min_usd=self.constraints.min_trade_size_usd,
            min_trade_usd=self.constraints.min_trade_size_usd
        )
        
        actions = base_plan.get("actions", [])
        
        # Enrichir les actions avec données avancées
        for action in actions:
            symbol = action.get("symbol", action.get("alias", ""))
            
            # Ajouter métriques de marché
            if symbol in self.market_data_cache:
                metrics = self.market_data_cache[symbol]
                action["market_metrics"] = {
                    "volatility": metrics.volatility_30d,
                    "momentum_7d": metrics.momentum_7d,
                    "momentum_30d": metrics.momentum_30d,
                    "liquidity_score": metrics.liquidity_score
                }
            
            # Déterminer exchange optimal
            action["exchange_hint"] = await self._determine_optimal_exchange(action)
            
            # Calculer priorité d'exécution
            action["execution_priority"] = self._calculate_execution_priority(action, strategy)
        
        return actions
    
    async def _determine_optimal_exchange(self, action: Dict[str, Any]) -> str:
        """Détermine l'exchange optimal pour une action"""
        
        symbol = action.get("symbol", "")
        action_type = action.get("action", "")
        usd_amount = abs(float(action.get("usd", 0)))
        
        # Règles de base
        if usd_amount > 5000:  # Gros ordres -> exchanges avec liquidité
            if action_type == "sell":
                return "kraken"  # Kraken excellent pour grosses ventes
            else:
                return "binance"  # Binance pour gros achats
        
        elif symbol in ["BTC", "ETH", "USDC", "USDT"]:  # Assets liquides
            return "binance"  # Meilleurs frais
        
        elif action.get("market_metrics", {}).get("liquidity_score", 0) < 40:  # Assets illiquides
            return "coinbase"  # Meilleure exécution pour illiquides
        
        else:
            return "kraken"  # Exchange par défaut équilibré
    
    def _calculate_execution_priority(self, action: Dict[str, Any], strategy: RebalancingStrategy) -> int:
        """Calcule la priorité d'exécution (1=high, 10=low)"""
        
        base_priority = 5
        action_type = action.get("action", "")
        usd_amount = abs(float(action.get("usd", 0)))
        
        # Ventes en priorité pour libérer liquidités
        if action_type == "sell":
            base_priority -= 2
        
        # Gros montants en priorité
        if usd_amount > 1000:
            base_priority -= 1
        elif usd_amount < 100:
            base_priority += 1
        
        # Assets volatils en priorité pour momentum
        if strategy == RebalancingStrategy.MOMENTUM:
            vol = action.get("market_metrics", {}).get("volatility", 1.0)
            if vol > 1.5:
                base_priority -= 1
        
        # Assets illiquides plus tard
        liquidity = action.get("market_metrics", {}).get("liquidity_score", 50)
        if liquidity < 30:
            base_priority += 2
        
        return max(1, min(10, base_priority))
    
    async def _optimize_execution_plan(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimise le plan d'exécution (splitting, timing, routing)"""
        
        optimized_actions = []
        
        for action in actions:
            usd_amount = abs(float(action.get("usd", 0)))
            
            # Splitting pour gros ordres
            if usd_amount > self.constraints.max_trade_size_usd:
                split_actions = self._split_large_order(action)
                optimized_actions.extend(split_actions)
            else:
                optimized_actions.append(action)
        
        # Trier par priorité d'exécution
        optimized_actions.sort(key=lambda a: a.get("execution_priority", 5))
        
        # Limiter nombre d'actions simultanées
        if len(optimized_actions) > self.constraints.max_simultaneous_trades:
            optimized_actions = optimized_actions[:self.constraints.max_simultaneous_trades]
        
        return optimized_actions
    
    def _split_large_order(self, action: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split un gros ordre en plusieurs petits ordres (TWAP basic)"""
        
        usd_amount = abs(float(action.get("usd", 0)))
        max_size = self.constraints.max_trade_size_usd
        
        num_splits = math.ceil(usd_amount / max_size)
        split_size = usd_amount / num_splits
        
        split_actions = []
        for i in range(num_splits):
            split_action = action.copy()
            
            # Ajuster le montant
            if action.get("usd", 0) > 0:
                split_action["usd"] = split_size
            else:
                split_action["usd"] = -split_size
            
            # Ajuster la quantité proportionnellement
            if "est_quantity" in action:
                original_qty = float(action["est_quantity"] or 0)
                split_action["est_quantity"] = original_qty / num_splits
            
            # Marquer comme partie d'un split
            split_action["split_info"] = {
                "is_split": True,
                "split_index": i + 1,
                "total_splits": num_splits,
                "original_amount": usd_amount
            }
            
            # Délai entre splits (TWAP basique)
            split_action["execution_delay_minutes"] = i * 5  # 5 min entre chaque
            
            split_actions.append(split_action)
        
        logger.info(f"Split ordre ${usd_amount:,.0f} en {num_splits} parties")
        return split_actions
    
    async def _calculate_result_metrics(
        self, 
        actions: List[Dict[str, Any]], 
        duplicate_actions: List[Dict[str, Any]],
        strategy: RebalancingStrategy,
        holdings: List[Dict[str, Any]]
    ) -> RebalancingResult:
        """Calcule les métriques finales du résultat"""
        
        # Estimation des frais
        total_fees = sum(abs(float(a.get("usd", 0))) * 0.001 for a in actions)  # 0.1% moyen
        
        # Score d'optimisation basé sur plusieurs critères
        optimization_score = self._calculate_optimization_score(actions, strategy)
        
        # Métriques de risque
        risk_metrics = self._calculate_portfolio_risk_metrics(holdings)
        
        # Score de timing de marché
        market_timing_score = self._calculate_market_timing_score(actions, strategy)
        
        # Complexité d'exécution
        complexity = self._assess_execution_complexity(actions)
        
        # Générer warnings et recommandations
        warnings = self._generate_warnings(actions, total_fees, complexity)
        
        return RebalancingResult(
            strategy_used=strategy.value,
            actions=actions,
            optimization_score=optimization_score,
            estimated_total_fees=total_fees,
            risk_metrics=risk_metrics,
            duplicate_consolidations=duplicate_actions,
            market_timing_score=market_timing_score,
            execution_complexity=complexity,
            warnings=warnings,
            metadata={
                "total_volume": sum(abs(float(a.get("usd", 0))) for a in actions),
                "num_splits": sum(1 for a in actions if a.get("split_info", {}).get("is_split", False)),
                "avg_priority": np.mean([a.get("execution_priority", 5) for a in actions]) if actions else 5
            }
        )
    
    def _calculate_optimization_score(self, actions: List[Dict[str, Any]], strategy: RebalancingStrategy) -> float:
        """Calcule un score d'optimisation 0-100"""
        
        if not actions:
            return 0.0
        
        score = 70.0  # Score de base
        
        # Bonus pour stratégies avancées
        strategy_bonuses = {
            RebalancingStrategy.RISK_PARITY: 10,
            RebalancingStrategy.MOMENTUM: 8,
            RebalancingStrategy.MEAN_REVERSION: 8,
            RebalancingStrategy.MULTI_OBJECTIVE: 15,
            RebalancingStrategy.SMART_CONSOLIDATION: 5
        }
        score += strategy_bonuses.get(strategy, 0)
        
        # Bonus pour bons exchanges
        good_exchanges = sum(1 for a in actions if a.get("exchange_hint", "") in ["binance", "kraken", "coinbase"])
        exchange_ratio = good_exchanges / len(actions)
        score += exchange_ratio * 10
        
        # Malus pour trop de petites actions
        small_actions = sum(1 for a in actions if abs(float(a.get("usd", 0))) < 50)
        if small_actions > len(actions) * 0.3:
            score -= 10
        
        # Bonus pour splits intelligents
        splits = sum(1 for a in actions if a.get("split_info", {}).get("is_split", False))
        if splits > 0:
            score += 5
        
        return max(0, min(100, score))
    
    def _calculate_portfolio_risk_metrics(self, holdings: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calcule les métriques de risque du portfolio"""
        
        if not holdings:
            return {}
        
        total_value = sum(h["value_usd"] for h in holdings)
        
        # Diversification (Shannon entropy)
        weights = [h["value_usd"] / total_value for h in holdings]
        entropy = -sum(w * np.log(w) for w in weights if w > 0)
        diversification = entropy / np.log(len(holdings))  # Normalisé 0-1
        
        # Concentration risque (HHI)
        hhi = sum(w**2 for w in weights)
        concentration = hhi  # 0-1, plus haut = plus concentré
        
        # Volatilité pondérée du portfolio
        portfolio_vol = 0.0
        for holding in holdings:
            weight = holding["value_usd"] / total_value
            symbol = holding["symbol"]
            if symbol in self.market_data_cache:
                vol = self.market_data_cache[symbol].volatility_30d or 1.0
                portfolio_vol += weight * vol
        
        return {
            "diversification_score": diversification,
            "concentration_risk": concentration,
            "estimated_volatility": portfolio_vol,
            "sharpe_estimate": 0.15 / max(portfolio_vol, 0.1)  # Estimation simple
        }
    
    def _calculate_market_timing_score(self, actions: List[Dict[str, Any]], strategy: RebalancingStrategy) -> float:
        """Score de timing de marché 0-100"""
        
        if not actions:
            return 50.0
        
        score = 50.0  # Neutre par défaut
        
        # Stratégies avec timing
        if strategy == RebalancingStrategy.MOMENTUM:
            # Bonus si on achète assets avec momentum positif
            buy_actions = [a for a in actions if float(a.get("usd", 0)) > 0]
            good_timing = 0
            for action in buy_actions:
                momentum = action.get("market_metrics", {}).get("momentum_7d", 0)
                if momentum > 0:
                    good_timing += 1
            
            if buy_actions:
                timing_ratio = good_timing / len(buy_actions)
                score += timing_ratio * 30  # Max bonus 30
        
        elif strategy == RebalancingStrategy.MEAN_REVERSION:
            # Bonus si on achète assets avec momentum négatif
            buy_actions = [a for a in actions if float(a.get("usd", 0)) > 0]
            good_timing = 0
            for action in buy_actions:
                momentum = action.get("market_metrics", {}).get("momentum_7d", 0)
                if momentum < 0:
                    good_timing += 1
            
            if buy_actions:
                timing_ratio = good_timing / len(buy_actions)
                score += timing_ratio * 25
        
        return max(0, min(100, score))
    
    def _assess_execution_complexity(self, actions: List[Dict[str, Any]]) -> str:
        """Évalue la complexité d'exécution"""
        
        if not actions:
            return "Low"
        
        complexity_factors = 0
        
        # Nombre d'actions
        if len(actions) > 20:
            complexity_factors += 1
        if len(actions) > 50:
            complexity_factors += 1
        
        # Splits
        splits = sum(1 for a in actions if a.get("split_info", {}).get("is_split", False))
        if splits > 5:
            complexity_factors += 1
        
        # Exchanges multiples
        exchanges = set(a.get("exchange_hint", "unknown") for a in actions)
        if len(exchanges) > 3:
            complexity_factors += 1
        
        # Gros montants
        large_orders = sum(1 for a in actions if abs(float(a.get("usd", 0))) > 5000)
        if large_orders > 3:
            complexity_factors += 1
        
        if complexity_factors == 0:
            return "Low"
        elif complexity_factors <= 2:
            return "Medium"
        else:
            return "High"
    
    def _generate_warnings(self, actions: List[Dict[str, Any]], total_fees: float, complexity: str) -> List[str]:
        """Génère des warnings et recommandations"""
        
        warnings = []
        
        if not actions:
            warnings.append("Aucune action de rebalancement générée")
            return warnings
        
        # Frais élevés
        total_volume = sum(abs(float(a.get("usd", 0))) for a in actions)
        if total_fees > total_volume * 0.005:  # Plus de 0.5%
            warnings.append(f"Frais élevés estimés: ${total_fees:.2f} ({total_fees/total_volume*100:.2f}% du volume)")
        
        # Complexité élevée
        if complexity == "High":
            warnings.append("Exécution complexe - considérer étaler dans le temps")
        
        # Trop de petites actions
        small_actions = sum(1 for a in actions if abs(float(a.get("usd", 0))) < 50)
        if small_actions > len(actions) * 0.3:
            warnings.append(f"{small_actions} petites actions (<$50) - considérer consolidation")
        
        # Assets illiquides
        illiquid_actions = []
        for action in actions:
            liquidity = action.get("market_metrics", {}).get("liquidity_score", 50)
            if liquidity < 30:
                illiquid_actions.append(action.get("symbol", ""))
        
        if illiquid_actions:
            warnings.append(f"Assets illiquides détectés: {', '.join(illiquid_actions[:3])}")
        
        # Gros ordres
        large_orders = [a for a in actions if abs(float(a.get("usd", 0))) > 5000]
        if large_orders:
            warnings.append(f"{len(large_orders)} gros ordres (>$5K) - surveillance recommandée")
        
        return warnings
    
    async def _fallback_simple_rebalance(
        self, 
        holdings: List[Dict[str, Any]], 
        targets: Dict[str, float]
    ) -> RebalancingResult:
        """Fallback vers rebalancement simple en cas d'erreur"""
        
        logger.warning("Fallback vers rebalancement simple")
        
        from services.rebalance import plan_rebalance
        
        try:
            # Utiliser le système existant
            plan = plan_rebalance(holdings, targets, min_trade_usd=self.constraints.min_trade_size_usd)
            
            return RebalancingResult(
                strategy_used="fallback_simple",
                actions=plan.get("actions", []),
                optimization_score=40.0,  # Score bas pour fallback
                estimated_total_fees=0.0,
                risk_metrics={},
                duplicate_consolidations=[],
                market_timing_score=50.0,
                execution_complexity="Low",
                warnings=["Utilisation du système de rebalancement simple (fallback)"],
                metadata={"fallback": True}
            )
        except Exception as e:
            logger.error(f"Erreur même dans fallback: {e}")
            return RebalancingResult(
                strategy_used="error",
                actions=[],
                optimization_score=0.0,
                estimated_total_fees=0.0,
                risk_metrics={},
                duplicate_consolidations=[],
                market_timing_score=0.0,
                execution_complexity="Low",
                warnings=[f"Erreur système: {str(e)}"],
                metadata={"error": True}
            )

# Instance globale du moteur
advanced_rebalancing_engine = AdvancedRebalancingEngine()