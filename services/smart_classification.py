"""
Smart Coin Classification System - Classification intelligente avec scoring de confiance
et détection de duplicatas/dérivés crypto.

Ce module améliore considérablement le système de taxonomie existant avec :
- Classification avec scoring de confiance (0-100%)
- Détection intelligente de duplicatas et dérivés (WBTC/BTC, WETH/ETH)
- Patterns sophistiqués pour auto-classification
- Support enrichissement CoinGecko avec fallback gracieux
- API d'apprentissage pour feedback humain
"""

from __future__ import annotations
import re
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from services.taxonomy import Taxonomy, auto_classify_symbol
from services.coingecko import coingecko_service

logger = logging.getLogger(__name__)

@dataclass
class ClassificationResult:
    """Résultat d'une classification avec métadonnées"""
    symbol: str
    suggested_group: str
    confidence_score: float  # 0-100
    method: str             # "manual", "pattern", "coingecko", "derivative", "learning"
    base_symbol: Optional[str] = None  # Pour les dérivés: WBTC -> BTC
    reasoning: str = ""     # Explication humaine de la classification
    metadata: Dict[str, Any] = field(default_factory=dict)
    classified_at: datetime = field(default_factory=datetime.now)

@dataclass  
class DerivativeMapping:
    """Mapping pour dérivés et tokens wrappés"""
    derivative: str         # WBTC, STETH, etc.
    base_symbol: str       # BTC, ETH, etc.
    derivative_type: str   # "wrapped", "staked", "synthetic", "tokenized"
    confidence: float      # Confiance dans ce mapping
    description: str       # Description du dérivé

class SmartClassificationService:
    """Service de classification intelligente des cryptomonnaies"""
    
    def __init__(self):
        # Cache des résultats
        self._classification_cache: Dict[str, ClassificationResult] = {}
        self._cache_ttl = timedelta(hours=24)
        
        # Mappings de dérivés connus
        self.derivative_mappings = self._build_derivative_mappings()
        
        # Patterns avancés pour classification
        self.advanced_patterns = self._build_advanced_patterns()
        
        # Statistiques
        self.classification_stats = {
            "total_classified": 0,
            "method_counts": {"manual": 0, "pattern": 0, "coingecko": 0, "derivative": 0, "learning": 0},
            "confidence_distribution": {"high": 0, "medium": 0, "low": 0}  # high: 80+, medium: 50+, low: <50
        }
        
    def _build_derivative_mappings(self) -> Dict[str, DerivativeMapping]:
        """Construit les mappings des dérivés et tokens wrappés"""
        mappings = {}
        
        # Bitcoin dérivés
        btc_derivatives = [
            ("WBTC", "wrapped", 95, "Wrapped Bitcoin sur Ethereum"),
            ("TBTC", "tokenized", 90, "tBTC - Bitcoin tokenisé par Threshold"),
            ("RENBTC", "wrapped", 85, "renBTC - Bitcoin wrapped via Ren Protocol"),
            ("SBTC", "synthetic", 80, "Synthetic Bitcoin"),
            ("BTCB", "wrapped", 85, "Bitcoin BEP20 sur Binance Smart Chain"),
        ]
        
        for deriv, deriv_type, conf, desc in btc_derivatives:
            mappings[deriv] = DerivativeMapping(deriv, "BTC", deriv_type, conf, desc)
        
        # Ethereum dérivés  
        eth_derivatives = [
            ("WETH", "wrapped", 95, "Wrapped Ether"),
            ("STETH", "staked", 92, "Lido Staked Ether"),
            ("WSTETH", "wrapped", 90, "Wrapped Lido Staked Ether"),
            ("RETH", "staked", 88, "Rocket Pool Staked Ether"),
            ("SETH", "staked", 80, "Staked Ether générique"),
            ("CBETH", "staked", 85, "Coinbase Wrapped Staked ETH"),
            ("ANKETR", "staked", 75, "Ankr Staked Ether"),
        ]
        
        for deriv, deriv_type, conf, desc in eth_derivatives:
            mappings[deriv] = DerivativeMapping(deriv, "ETH", deriv_type, conf, desc)
            
        # Solana dérivés
        sol_derivatives = [
            ("JUPSOL", "staked", 85, "Jupiter Staked SOL"),
            ("JITOSOL", "staked", 85, "Jito Staked SOL"),
            ("MSOL", "staked", 80, "Marinade Staked SOL"),
            ("SCNSOL", "staked", 75, "Socean Staked SOL"),
        ]
        
        for deriv, deriv_type, conf, desc in sol_derivatives:
            mappings[deriv] = DerivativeMapping(deriv, "SOL", deriv_type, conf, desc)
            
        # Autres dérivés majeurs
        other_derivatives = [
            ("WMATIC", "MATIC", "wrapped", 90, "Wrapped MATIC"),
            ("WAVAX", "AVAX", "wrapped", 90, "Wrapped AVAX"), 
            ("WBNB", "BNB", "wrapped", 90, "Wrapped BNB"),
            ("WFTM", "FTM", "wrapped", 85, "Wrapped Fantom"),
            ("WONE", "ONE", "wrapped", 85, "Wrapped Harmony ONE"),
        ]
        
        for deriv, base, deriv_type, conf, desc in other_derivatives:
            mappings[deriv] = DerivativeMapping(deriv, base, deriv_type, conf, desc)
            
        return mappings
        
    def _build_advanced_patterns(self) -> Dict[str, List[Tuple[str, str, float]]]:
        """Patterns avancés pour classification automatique"""
        return {
            # Stablecoins - patterns très spécifiques
            "stablecoins": [
                (r"^USD[CT]?$", "Stablecoins", 95),           # USDC, USDT, USD
                (r"^.*USD[CT]$", "Stablecoins", 90),          # AUSD, BUSD, GUSD
                (r"^.*DAI$", "Stablecoins", 85),              # DAI, FRAXDAI
                (r"^(TUSD|BUSD|GUSD|USDD|FRAX)$", "Stablecoins", 90),
                (r"^(EUR|GBP|JPY|CNY)[CT]?$", "Stablecoins", 85),  # Stables fiat
                (r".*STABLE.*", "Stablecoins", 75),           # Générique
            ],
            
            # Layer 2 / Scaling - patterns étendus
            "l2_scaling": [
                (r"^(ARB|ARBITRUM).*", "L2/Scaling", 90),
                (r"^OP$", "L2/Scaling", 95),                  # Optimism
                (r"^MATIC.*|.*MATIC.*", "L2/Scaling", 90),    # Polygon ecosystem
                (r"^POL.*", "L2/Scaling", 85),                # POL tokens
                (r"^STRK.*", "L2/Scaling", 85),               # Starknet
                (r"^(IMX|LRC|METIS)$", "L2/Scaling", 85),     # Autres L2 connus
                (r".*LAYER.*2.*|.*L2.*", "L2/Scaling", 70),   # Générique L2
            ],
            
            # Memecoins - détection sophistiquée
            "memecoins": [
                (r"^(DOGE|SHIB|PEPE|BONK|WIF|FLOKI).*", "Memecoins", 90),
                (r".*DOGE.*|.*SHIBA.*|.*INU.*", "Memecoins", 85),
                (r".*PEPE.*|.*BONK.*|.*WIF.*", "Memecoins", 80),
                (r".*MEME.*|.*MOON.*|.*SAFE.*", "Memecoins", 75),
                (r".*BABY.*|.*MINI.*|.*MICRO.*", "Memecoins", 70),  # Baby/Mini coins
                (r".*ELON.*|.*MARS.*|.*ROCKET.*", "Memecoins", 65), # Elon-themed
            ],
            
            # AI/Data tokens - patterns étendus  
            "ai_data": [
                (r"^(FET|RENDER|TAO|OCEAN|GRT|WLD).*", "AI/Data", 90),
                (r".*AI.*|.*GPT.*|.*CHAT.*", "AI/Data", 80),
                (r".*DATA.*|.*ORACLE.*|.*GRAPH.*", "AI/Data", 75),
                (r".*NEURAL.*|.*MACHINE.*|.*LEARNING.*", "AI/Data", 70),
            ],
            
            # Gaming/NFT - patterns élargis
            "gaming_nft": [
                (r"^(AXS|SAND|MANA|ENJ|GALA|CHZ|FLOW).*", "Gaming/NFT", 90),
                (r".*GAME.*|.*GAMING.*|.*PLAY.*", "Gaming/NFT", 80),
                (r".*NFT.*|.*COLLECTIBLE.*", "Gaming/NFT", 85),
                (r".*METAVERSE.*|.*VIRTUAL.*", "Gaming/NFT", 75),
                (r".*LAND.*|.*WORLD.*", "Gaming/NFT", 70),      # Virtual worlds
            ],
            
            # DeFi - patterns sophistiqués
            "defi": [
                (r"^(UNI|AAVE|COMP|MKR|SNX|CRV|SUSHI|1INCH|YFI|LDO).*", "DeFi", 90),
                (r".*SWAP.*|.*DEX.*|.*AMM.*", "DeFi", 85),
                (r".*FARM.*|.*YIELD.*|.*VAULT.*", "DeFi", 80),
                (r".*LEND.*|.*BORROW.*|.*LOAN.*", "DeFi", 75),
                (r".*LIQUIDITY.*|.*LP.*", "DeFi", 70),
            ]
        }
    
    async def classify_symbol(self, symbol: str, use_cache: bool = True) -> ClassificationResult:
        """
        Classification intelligente d'un symbole avec scoring de confiance
        
        Args:
            symbol: Symbole à classifier
            use_cache: Utiliser le cache de résultats
            
        Returns:
            ClassificationResult avec groupe suggéré et confiance
        """
        if not symbol or not symbol.strip():
            return ClassificationResult(
                symbol="", 
                suggested_group="Others", 
                confidence_score=0,
                method="error",
                reasoning="Symbole vide"
            )
            
        symbol = symbol.upper().strip()
        
        # 1. Vérifier le cache
        if use_cache and symbol in self._classification_cache:
            cached_result = self._classification_cache[symbol]
            if datetime.now() - cached_result.classified_at < self._cache_ttl:
                return cached_result
        
        # 2. Classification manuelle prioritaire (taxonomie existante)
        taxonomy = Taxonomy.load()
        if symbol in taxonomy.aliases:
            result = ClassificationResult(
                symbol=symbol,
                suggested_group=taxonomy.aliases[symbol],
                confidence_score=100.0,
                method="manual",
                reasoning=f"Classification manuelle confirmée dans taxonomie"
            )
            self._cache_result(result)
            return result
        
        # 3. Dérivés et tokens wrappés
        if symbol in self.derivative_mappings:
            derivative = self.derivative_mappings[symbol]
            base_group = taxonomy.group_for_alias(derivative.base_symbol)
            result = ClassificationResult(
                symbol=symbol,
                suggested_group=base_group,
                confidence_score=derivative.confidence,
                method="derivative",
                base_symbol=derivative.base_symbol,
                reasoning=f"Dérivé {derivative.derivative_type} de {derivative.base_symbol}: {derivative.description}",
                metadata={"derivative_type": derivative.derivative_type, "base_symbol": derivative.base_symbol}
            )
            self._cache_result(result)
            return result
        
        # 4. Classification par patterns avancés
        pattern_result = self._classify_by_advanced_patterns(symbol)
        if pattern_result.confidence_score >= 70:  # Seuil de confiance pour patterns
            self._cache_result(pattern_result)
            return pattern_result
        
        # 5. CoinGecko enrichissement (si disponible)
        try:
            coingecko_group = await coingecko_service.classify_symbol(symbol)
            if coingecko_group and coingecko_group != "Others":
                result = ClassificationResult(
                    symbol=symbol,
                    suggested_group=coingecko_group,
                    confidence_score=75.0,  # Confiance modérée pour CoinGecko
                    method="coingecko",
                    reasoning=f"Classification via métadonnées CoinGecko",
                    metadata={"source": "coingecko_api"}
                )
                self._cache_result(result)
                return result
        except Exception as e:
            logger.debug(f"Erreur CoinGecko pour {symbol}: {e}")
        
        # 6. Fallback vers patterns avec seuil plus bas
        if pattern_result.confidence_score > 0:
            self._cache_result(pattern_result)
            return pattern_result
        
        # 7. Fallback final
        result = ClassificationResult(
            symbol=symbol,
            suggested_group="Others",
            confidence_score=10.0,  # Très faible confiance
            method="fallback",
            reasoning="Aucune classification trouvée, groupe par défaut"
        )
        self._cache_result(result)
        return result
    
    def _classify_by_advanced_patterns(self, symbol: str) -> ClassificationResult:
        """Classification par patterns avancés avec scoring"""
        best_match = None
        best_confidence = 0.0
        best_group = "Others"
        best_reasoning = ""
        
        for group_key, patterns in self.advanced_patterns.items():
            group_name = self._group_key_to_name(group_key)
            
            for pattern, target_group, base_confidence in patterns:
                try:
                    if re.match(pattern, symbol, re.IGNORECASE):
                        # Ajustement de confiance selon la spécificité
                        confidence = self._adjust_confidence_by_pattern_specificity(
                            pattern, symbol, base_confidence
                        )
                        
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_group = target_group
                            best_reasoning = f"Pattern match: {pattern} → {target_group} (confiance: {confidence}%)"
                            
                except re.error as e:
                    logger.warning(f"Erreur regex pattern {pattern}: {e}")
                    continue
        
        return ClassificationResult(
            symbol=symbol,
            suggested_group=best_group,
            confidence_score=best_confidence,
            method="pattern",
            reasoning=best_reasoning,
            metadata={"pattern_matched": True}
        )
    
    def _adjust_confidence_by_pattern_specificity(self, pattern: str, symbol: str, base_confidence: float) -> float:
        """Ajuste la confiance selon la spécificité du pattern"""
        
        # Patterns très spécifiques (exact match) -> confiance plus élevée
        if pattern.startswith("^") and pattern.endswith("$") and len(pattern) < 20:
            return min(base_confidence + 5, 95)
        
        # Patterns génériques (.*) -> confiance plus faible  
        if ".*" in pattern or pattern.count(".") > 2:
            return max(base_confidence - 10, 20)
        
        # Patterns avec plusieurs alternatives -> confiance modérée
        if "|" in pattern:
            return base_confidence
            
        # Longueur du symbole vs pattern
        if len(symbol) <= 5 and len(pattern) > 10:  # Pattern complexe pour symbole simple
            return max(base_confidence - 5, 30)
            
        return base_confidence
    
    def _group_key_to_name(self, group_key: str) -> str:
        """Convertit une clé de groupe en nom de groupe taxonomie"""
        mapping = {
            "stablecoins": "Stablecoins",
            "l2_scaling": "L2/Scaling", 
            "memecoins": "Memecoins",
            "ai_data": "AI/Data",
            "gaming_nft": "Gaming/NFT",
            "defi": "DeFi"
        }
        return mapping.get(group_key, "Others")
    
    def _cache_result(self, result: ClassificationResult):
        """Met en cache un résultat de classification"""
        self._classification_cache[result.symbol] = result
        
        # Mettre à jour les stats
        self.classification_stats["total_classified"] += 1
        self.classification_stats["method_counts"][result.method] = \
            self.classification_stats["method_counts"].get(result.method, 0) + 1
            
        # Distribution de confiance
        if result.confidence_score >= 80:
            self.classification_stats["confidence_distribution"]["high"] += 1
        elif result.confidence_score >= 50:
            self.classification_stats["confidence_distribution"]["medium"] += 1
        else:
            self.classification_stats["confidence_distribution"]["low"] += 1
    
    async def classify_symbols_batch(self, symbols: List[str], 
                                   confidence_threshold: float = 50.0) -> Dict[str, ClassificationResult]:
        """
        Classification en lot avec seuil de confiance
        
        Args:
            symbols: Liste des symboles à classifier
            confidence_threshold: Seuil minimum de confiance
            
        Returns:
            Dict avec résultats de classification
        """
        results = {}
        
        # Traitement concurrent mais limité pour éviter spam API
        semaphore = asyncio.Semaphore(10)  # Max 10 requêtes parallèles
        
        async def classify_single(symbol: str) -> Tuple[str, ClassificationResult]:
            async with semaphore:
                result = await self.classify_symbol(symbol)
                await asyncio.sleep(0.05)  # Petit délai anti-spam
                return symbol, result
        
        # Exécution parallèle  
        tasks = [classify_single(symbol) for symbol in symbols if symbol and symbol.strip()]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traitement des résultats
        for result in completed_results:
            if isinstance(result, Exception):
                logger.error(f"Erreur classification batch: {result}")
                continue
            
            symbol, classification = result
            
            # Filtrer par seuil de confiance
            if classification.confidence_score >= confidence_threshold:
                results[symbol] = classification
        
        return results
    
    def detect_duplicates_in_portfolio(self, symbols: List[str]) -> Dict[str, List[str]]:
        """
        Détecte les doublons potentiels dans un portfolio
        
        Args:
            symbols: Liste des symboles du portfolio
            
        Returns:
            Dict groupant les potentiels doublons: {base_symbol: [derivatives]}
        """
        duplicates = {}
        
        for symbol in symbols:
            symbol = symbol.upper().strip()
            
            # Vérifier si c'est un dérivé connu
            if symbol in self.derivative_mappings:
                derivative = self.derivative_mappings[symbol]
                base = derivative.base_symbol
                
                if base not in duplicates:
                    duplicates[base] = []
                
                duplicates[base].append({
                    "symbol": symbol,
                    "type": derivative.derivative_type,
                    "confidence": derivative.confidence,
                    "description": derivative.description
                })
        
        # Garder seulement les groupes avec plus d'un élément
        return {base: derivs for base, derivs in duplicates.items() if len(derivs) > 0}
    
    def get_classification_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de classification"""
        cache_size = len(self._classification_cache)
        derivative_count = len(self.derivative_mappings)
        
        return {
            "cache_stats": {
                "cached_symbols": cache_size,
                "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600
            },
            "derivative_mappings": {
                "total_mappings": derivative_count,
                "by_base": {
                    base: len([d for d in self.derivative_mappings.values() if d.base_symbol == base])
                    for base in set(d.base_symbol for d in self.derivative_mappings.values())
                }
            },
            "classification_performance": self.classification_stats,
            "advanced_patterns": {
                group: len(patterns) for group, patterns in self.advanced_patterns.items()
            }
        }
    
    def clear_cache(self):
        """Vide le cache de classification"""
        self._classification_cache.clear()
        logger.info("Cache de classification vidé")

# Instance globale du service
smart_classification_service = SmartClassificationService()