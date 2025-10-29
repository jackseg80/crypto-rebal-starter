"""
Phase Engine pour Rotation BTC → ETH → Large → Alt

Ce module gère les phases de rotation crypto avec :
- Détection de phase basée sur force relative et dominance
- Cache intelligent avec TTL court
- Persistance minimale avant changement de phase
- Probabilités et explications pour chaque phase
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import httpx
from pathlib import Path
import json

logger = logging.getLogger(__name__)

class Phase(Enum):
    """Phases de rotation crypto"""
    BTC = "btc"
    ETH = "eth" 
    LARGE = "large"
    ALT = "alt"

@dataclass
class PhaseSignals:
    """Signaux utilisés pour déterminer la phase"""
    btc_dominance: float = 0.0      # Dominance BTC %
    btc_dominance_delta_7d: float = 0.0  # Delta dominance 7j
    
    # Force relative (RS = Relative Strength)
    rs_eth_btc_7d: float = 1.0      # ETH vs BTC 7j
    rs_eth_btc_30d: float = 1.0     # ETH vs BTC 30j
    rs_large_btc_7d: float = 1.0    # Top 10-50 vs BTC 7j  
    rs_large_btc_30d: float = 1.0   # Top 10-50 vs BTC 30j
    rs_alt_btc_7d: float = 1.0      # Alt vs BTC 7j
    rs_alt_btc_30d: float = 1.0     # Alt vs BTC 30j
    
    # Breadth (largeur de marché)
    breadth_advance_decline: float = 0.5   # Ratio advance/decline
    breadth_new_highs: int = 0             # Nouveaux ATH récents
    
    # Volume et momentum 
    volume_concentration: float = 0.5      # Concentration volume top assets
    momentum_dispersion: float = 0.5       # Dispersion momentum cross-asset
    
    # Timestamp et qualité
    as_of: datetime = None
    quality_score: float = 1.0             # Score qualité données [0-1]

@dataclass  
class PhaseState:
    """État d'une phase avec probabilités et explications"""
    phase_now: Phase
    phase_probs: Dict[str, float]          # Probabilités de chaque phase
    confidence: float                      # Confiance globale [0-1]
    explain: List[str]                     # 2-3 explications principales
    next_likely: Optional[Phase] = None    # Phase suivante probable
    persistence_count: int = 0             # Nb observations consécutives
    last_change: Optional[datetime] = None # Dernier changement de phase
    signals: Optional[PhaseSignals] = None # Signaux ayant conduit à cette phase

class PhaseEngine:
    """
    Moteur de détection des phases de rotation crypto
    
    Logique :
    1. BTC : Dominance ↑ + RS autres actifs faible
    2. ETH : ETH/BTC fort + dominance BTC stable  
    3. LARGE : Top 10-50 surperforment + ETH/BTC modéré
    4. ALT : Breadth élevé + dispersion momentum + RS alt fort
    """
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip("/")
        
        # Cache avec TTL
        self._phase_cache: Optional[PhaseState] = None
        self._cache_updated_at: Optional[datetime] = None
        self._cache_ttl_seconds = 180  # 3 minutes
        
        # Persistance pour éviter les changements trop fréquents
        self._min_persistence_observations = 3
        self._phase_history: List[Tuple[Phase, datetime]] = []
        
        # Configuration des seuils
        self.thresholds = {
            'btc_dominance_trend': 0.5,      # % changement dominance significatif
            'rs_strength_threshold': 1.05,   # RS > 1.05 = surperformance
            'rs_weakness_threshold': 0.95,   # RS < 0.95 = sous-performance  
            'breadth_strong': 0.65,          # Breadth > 0.65 = marché large
            'confidence_min': 0.3,           # Confiance minimale
        }
        
        logger.info("PhaseEngine initialized with 3min cache TTL")
    
    async def get_current_phase(self, force_refresh: bool = False) -> PhaseState:
        """
        Retourne la phase actuelle avec cache intelligent
        """
        try:
            # Check cache validity
            now = datetime.now()
            cache_valid = (
                not force_refresh and 
                self._phase_cache and 
                self._cache_updated_at and
                (now - self._cache_updated_at).total_seconds() < self._cache_ttl_seconds
            )
            
            if cache_valid:
                logger.debug("Phase returned from cache")
                return self._phase_cache
            
            # Refresh phase detection
            signals = await self._fetch_phase_signals()
            phase_state = await self._detect_phase(signals)
            
            # Update cache
            self._phase_cache = phase_state
            self._cache_updated_at = now
            
            logger.debug(f"Phase detected: {phase_state.phase_now.value} (confidence: {phase_state.confidence:.2f})")
            return phase_state
            
        except Exception as e:
            logger.error(f"Error getting current phase: {e}")
            
            # Fallback à BTC phase avec faible confiance
            return PhaseState(
                phase_now=Phase.BTC,
                phase_probs={"btc": 1.0, "eth": 0.0, "large": 0.0, "alt": 0.0},
                confidence=0.1,
                explain=["Error fallback to BTC phase", f"Error: {str(e)[:50]}"],
                signals=PhaseSignals(as_of=datetime.now(), quality_score=0.0)
            )
    
    async def _fetch_phase_signals(self) -> PhaseSignals:
        """
        Récupère les signaux nécessaires pour la détection de phase
        Sources : CoinGecko API, endpoints internes, calculs dérivés
        """
        try:
            signals = PhaseSignals(as_of=datetime.now())

            # Réutiliser une seule session AsyncClient pour tous les appels (évite 3 handshakes SSL)
            async with httpx.AsyncClient() as client:
                # 1. Dominance BTC depuis CoinGecko global data
                try:
                    resp = await client.get(
                        "https://api.coingecko.com/api/v3/global",
                        timeout=5.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        btc_dominance = data.get("data", {}).get("market_cap_percentage", {}).get("btc", 0)
                        signals.btc_dominance = float(btc_dominance)
                        logger.debug(f"BTC dominance fetched: {btc_dominance:.1f}%")
                except Exception as e:
                    logger.warning(f"Failed to fetch BTC dominance: {e}, using fallback")
                    signals.btc_dominance = 45.0  # Fallback historique

                # 2. Force relative depuis notre API de prix
                try:
                    price_url = f"{self.api_base_url}/api/market/prices"
                    resp = await client.get(price_url, params={"days": 30}, timeout=8.0)

                    if resp.status_code == 200:
                        price_data = resp.json()
                        rs_signals = self._calculate_relative_strength(price_data)

                        signals.rs_eth_btc_7d = rs_signals.get('eth_btc_7d', 1.0)
                        signals.rs_eth_btc_30d = rs_signals.get('eth_btc_30d', 1.0)
                        signals.rs_large_btc_7d = rs_signals.get('large_btc_7d', 1.0)
                        signals.rs_large_btc_30d = rs_signals.get('large_btc_30d', 1.0)
                        signals.rs_alt_btc_7d = rs_signals.get('alt_btc_7d', 1.0)
                        signals.rs_alt_btc_30d = rs_signals.get('alt_btc_30d', 1.0)

                        logger.debug(f"Relative strength calculated: ETH/BTC 7d={signals.rs_eth_btc_7d:.3f}")
                except Exception as e:
                    logger.warning(f"Failed to fetch price data for RS calculation: {e}")

                # 3. Breadth et momentum depuis analytics endpoint
                try:
                    analytics_url = f"{self.api_base_url}/api/analytics/market-breadth"
                    resp = await client.get(analytics_url, timeout=5.0)

                    if resp.status_code == 200:
                        breadth_data = resp.json()
                        signals.breadth_advance_decline = breadth_data.get("advance_decline_ratio", 0.5)
                        signals.breadth_new_highs = breadth_data.get("new_highs_count", 0)
                        signals.volume_concentration = breadth_data.get("volume_concentration", 0.5)
                        signals.momentum_dispersion = breadth_data.get("momentum_dispersion", 0.5)
                except Exception as e:
                    logger.debug(f"Market breadth endpoint not available: {e}, using defaults")
            
            # Calculer dominance delta et quality score
            signals.btc_dominance_delta_7d = self._calculate_dominance_delta(signals.btc_dominance)
            signals.quality_score = self._assess_signal_quality(signals)
            
            logger.debug(f"Phase signals collected (quality: {signals.quality_score:.2f})")
            return signals
            
        except Exception as e:
            logger.error(f"Error fetching phase signals: {e}")
            return PhaseSignals(
                as_of=datetime.now(),
                quality_score=0.1,
                btc_dominance=45.0  # Fallback
            )
    
    def _calculate_relative_strength(self, price_data: Dict[str, Any]) -> Dict[str, float]:
        """Calcule la force relative entre actifs sur différentes périodes"""
        try:
            # Simulation des calculs RS basée sur les données de prix
            # Dans une vraie implémentation, on calculerait les performances relatives
            
            # Exemple de logique : ETH vs BTC performance
            btc_prices = price_data.get("BTC", {}).get("prices", [])
            eth_prices = price_data.get("ETH", {}).get("prices", [])
            
            rs_results = {}
            
            if len(btc_prices) >= 7 and len(eth_prices) >= 7:
                # RS 7 jours = (ETH_now/ETH_7d_ago) / (BTC_now/BTC_7d_ago)
                eth_7d_return = (eth_prices[-1] / eth_prices[-7]) - 1 if len(eth_prices) >= 7 else 0
                btc_7d_return = (btc_prices[-1] / btc_prices[-7]) - 1 if len(btc_prices) >= 7 else 0
                
                if btc_7d_return != 0:
                    rs_results['eth_btc_7d'] = (1 + eth_7d_return) / (1 + btc_7d_return)
                else:
                    rs_results['eth_btc_7d'] = 1.0
            
            # Simulation pour les autres assets (Large cap, Alt)
            rs_results.setdefault('eth_btc_7d', 1.0)
            rs_results.setdefault('eth_btc_30d', 1.0)
            rs_results.setdefault('large_btc_7d', 0.98)  # Large caps généralement plus faibles
            rs_results.setdefault('large_btc_30d', 0.97)
            rs_results.setdefault('alt_btc_7d', 1.02)   # Alts plus volatils
            rs_results.setdefault('alt_btc_30d', 1.01)
            
            return rs_results
            
        except Exception as e:
            logger.warning(f"RS calculation error: {e}")
            return {
                'eth_btc_7d': 1.0, 'eth_btc_30d': 1.0,
                'large_btc_7d': 1.0, 'large_btc_30d': 1.0, 
                'alt_btc_7d': 1.0, 'alt_btc_30d': 1.0
            }
    
    def _calculate_dominance_delta(self, current_dominance: float) -> float:
        """Calcule le changement de dominance BTC sur 7 jours"""
        # Simulation - dans une vraie implémentation on stockerait l'historique
        # Utiliser une variation aléatoire basée sur l'heure pour cohérence
        import time
        hour_seed = int(time.time() / 3600) % 100
        delta = (hour_seed - 50) * 0.1  # -5% à +5%
        return delta
    
    def _assess_signal_quality(self, signals: PhaseSignals) -> float:
        """Évalue la qualité des signaux collectés"""
        try:
            quality_factors = []
            
            # Facteur 1 : Fraîcheur des données
            age_minutes = (datetime.now() - signals.as_of).total_seconds() / 60
            freshness_score = max(0.0, 1.0 - (age_minutes / 30))  # Dégradé après 30min
            quality_factors.append(freshness_score)
            
            # Facteur 2 : Complétude des signaux
            completeness = 0.0
            if signals.btc_dominance > 0:
                completeness += 0.4
            if signals.rs_eth_btc_7d > 0:
                completeness += 0.3 
            if signals.breadth_advance_decline > 0:
                completeness += 0.3
            quality_factors.append(completeness)
            
            # Facteur 3 : Cohérence des signaux (pas de valeurs aberrantes)
            coherence = 1.0
            if signals.rs_eth_btc_7d > 3.0 or signals.rs_eth_btc_7d < 0.3:
                coherence *= 0.7  # RS trop extrême
            if signals.btc_dominance > 80 or signals.btc_dominance < 20:
                coherence *= 0.8  # Dominance aberrante
            quality_factors.append(coherence)
            
            # Score global = moyenne pondérée
            return sum(quality_factors) / len(quality_factors)

        except Exception as e:
            logger.warning(f"Error assessing signal quality: {e}, returning default")
            return 0.5
    
    async def _detect_phase(self, signals: PhaseSignals) -> PhaseState:
        """
        Logique principale de détection de phase
        """
        try:
            thresholds = self.thresholds
            
            # Calcul des probabilités pour chaque phase
            phase_scores = {
                Phase.BTC: self._calculate_btc_score(signals, thresholds),
                Phase.ETH: self._calculate_eth_score(signals, thresholds), 
                Phase.LARGE: self._calculate_large_score(signals, thresholds),
                Phase.ALT: self._calculate_alt_score(signals, thresholds)
            }
            
            # Normaliser les scores en probabilités
            total_score = sum(phase_scores.values())
            if total_score > 0:
                phase_probs = {phase.value: score/total_score for phase, score in phase_scores.items()}
            else:
                phase_probs = {"btc": 0.25, "eth": 0.25, "large": 0.25, "alt": 0.25}
            
            # Déterminer la phase dominante
            dominant_phase = max(phase_scores.keys(), key=lambda p: phase_scores[p])
            max_prob = phase_probs[dominant_phase.value]
            
            # Vérifier la persistance avant de changer de phase
            if self._phase_cache and self._phase_cache.phase_now != dominant_phase:
                persistence_count = 1
                if len(self._phase_history) >= self._min_persistence_observations:
                    recent_phases = [p for p, _ in self._phase_history[-self._min_persistence_observations:]]
                    if all(p == dominant_phase for p in recent_phases):
                        persistence_count = self._min_persistence_observations
                
                if persistence_count < self._min_persistence_observations:
                    logger.debug(f"Phase change {self._phase_cache.phase_now.value}→{dominant_phase.value} needs more persistence ({persistence_count}/{self._min_persistence_observations})")
                    dominant_phase = self._phase_cache.phase_now
                    # Réajuster les probabilities pour refléter l'incertitude
                    max_prob *= 0.8
            
            # Mise à jour de l'historique
            self._phase_history.append((dominant_phase, datetime.now()))
            if len(self._phase_history) > 10:
                self._phase_history = self._phase_history[-10:]
            
            # Génération des explications
            explanations = self._generate_explanations(dominant_phase, signals, phase_scores)
            
            # Phase suivante probable
            next_phase = self._predict_next_phase(dominant_phase, signals, phase_scores)
            
            # Confiance basée sur la qualité des signaux et la clarté de la détection
            confidence = min(1.0, max_prob * signals.quality_score * 1.2)
            confidence = max(thresholds['confidence_min'], confidence)
            
            return PhaseState(
                phase_now=dominant_phase,
                phase_probs=phase_probs,
                confidence=confidence,
                explain=explanations,
                next_likely=next_phase,
                persistence_count=self._phase_cache.persistence_count + 1 if self._phase_cache and self._phase_cache.phase_now == dominant_phase else 1,
                last_change=datetime.now() if not self._phase_cache or self._phase_cache.phase_now != dominant_phase else self._phase_cache.last_change,
                signals=signals
            )
            
        except Exception as e:
            logger.error(f"Phase detection error: {e}")
            return PhaseState(
                phase_now=Phase.BTC,
                phase_probs={"btc": 1.0, "eth": 0.0, "large": 0.0, "alt": 0.0},
                confidence=0.1,
                explain=["Error in phase detection", str(e)[:50]],
                signals=signals
            )
    
    def _calculate_btc_score(self, signals: PhaseSignals, thresholds: Dict) -> float:
        """Score pour phase BTC : dominance ↑ + autres assets faibles"""
        score = 0.0
        
        # Dominance BTC en hausse
        if signals.btc_dominance_delta_7d > thresholds['btc_dominance_trend']:
            score += 0.4
        
        # Force relative des autres assets faible  
        if signals.rs_eth_btc_7d < thresholds['rs_weakness_threshold']:
            score += 0.3
        if signals.rs_large_btc_7d < thresholds['rs_weakness_threshold']:
            score += 0.2
        if signals.rs_alt_btc_7d < thresholds['rs_weakness_threshold']:
            score += 0.1
        
        return score
    
    def _calculate_eth_score(self, signals: PhaseSignals, thresholds: Dict) -> float:
        """Score pour phase ETH : ETH/BTC fort + dominance BTC stable"""
        score = 0.0
        
        # ETH surperforme BTC
        if signals.rs_eth_btc_7d > thresholds['rs_strength_threshold']:
            score += 0.5
        if signals.rs_eth_btc_30d > thresholds['rs_strength_threshold']:
            score += 0.2
        
        # Dominance BTC stable (pas d'effondrement ni de montée forte)
        if abs(signals.btc_dominance_delta_7d) < thresholds['btc_dominance_trend']:
            score += 0.2
        
        # Large caps pas encore très forts (sinon ce serait LARGE phase)
        if signals.rs_large_btc_7d < thresholds['rs_strength_threshold']:
            score += 0.1
        
        return score
    
    def _calculate_large_score(self, signals: PhaseSignals, thresholds: Dict) -> float:
        """Score pour phase LARGE : Top 10-50 surperforment"""
        score = 0.0
        
        # Large caps surperforment BTC
        if signals.rs_large_btc_7d > thresholds['rs_strength_threshold']:
            score += 0.4
        if signals.rs_large_btc_30d > thresholds['rs_strength_threshold']:
            score += 0.2
        
        # ETH aussi solide (cohérent avec large caps)  
        if signals.rs_eth_btc_7d > 0.98:
            score += 0.2
        
        # Breadth modéré à fort
        if signals.breadth_advance_decline > 0.5:
            score += 0.2
        
        return score
    
    def _calculate_alt_score(self, signals: PhaseSignals, thresholds: Dict) -> float:
        """Score pour phase ALT : breadth élevé + momentum dispersé"""
        score = 0.0
        
        # Alts surperforment BTC
        if signals.rs_alt_btc_7d > thresholds['rs_strength_threshold']:
            score += 0.3
        
        # Breadth élevé (marché large)
        if signals.breadth_advance_decline > thresholds['breadth_strong']:
            score += 0.3
        
        # Momentum dispersé (pas de concentration)
        if signals.momentum_dispersion > 0.6:
            score += 0.2
        
        # Volume pas trop concentré sur BTC/ETH
        if signals.volume_concentration < 0.7:
            score += 0.2
        
        return score
    
    def _generate_explanations(self, phase: Phase, signals: PhaseSignals, scores: Dict[Phase, float]) -> List[str]:
        """Génère 2-3 explications pour la phase détectée"""
        explanations = []
        
        try:
            if phase == Phase.BTC:
                if signals.btc_dominance_delta_7d > 0:
                    explanations.append(f"Dominance BTC +{signals.btc_dominance_delta_7d:.1f}% (7j)")
                if signals.rs_eth_btc_7d < 0.95:
                    explanations.append(f"ETH sous-performe (RS={signals.rs_eth_btc_7d:.2f})")
            
            elif phase == Phase.ETH:
                if signals.rs_eth_btc_7d > 1.05:
                    explanations.append(f"ETH surperforme BTC (RS={signals.rs_eth_btc_7d:.2f})")
                if abs(signals.btc_dominance_delta_7d) < 1.0:
                    explanations.append("Dominance BTC stable")
            
            elif phase == Phase.LARGE:
                if signals.rs_large_btc_7d > 1.05:
                    explanations.append(f"Large caps fortes (RS={signals.rs_large_btc_7d:.2f})")
                if signals.breadth_advance_decline > 0.55:
                    explanations.append(f"Breadth positif ({signals.breadth_advance_decline:.0%})")
            
            elif phase == Phase.ALT:
                if signals.rs_alt_btc_7d > 1.05:
                    explanations.append(f"Alts surperforment (RS={signals.rs_alt_btc_7d:.2f})")
                if signals.breadth_advance_decline > 0.65:
                    explanations.append(f"Marché très large ({signals.breadth_advance_decline:.0%})")
            
            # Ajouter score de confiance si pertinent
            confidence_msg = f"Confiance {signals.quality_score:.0%}"
            if len(explanations) < 2:
                explanations.append(confidence_msg)
            
            # S'assurer qu'on a au moins 2 explications
            while len(explanations) < 2:
                explanations.append(f"Phase {phase.value.upper()} détectée")
            
            return explanations[:3]  # Max 3 explications
            
        except Exception as e:
            logger.warning(f"Error generating explanations: {e}")
            return [f"Phase {phase.value.upper()}", "Détection automatique"]
    
    def _predict_next_phase(self, current: Phase, signals: PhaseSignals, scores: Dict[Phase, float]) -> Optional[Phase]:
        """Prédit la phase suivante probable"""
        try:
            # Logique de transition typique : BTC → ETH → LARGE → ALT → BTC
            typical_sequence = {
                Phase.BTC: Phase.ETH,
                Phase.ETH: Phase.LARGE, 
                Phase.LARGE: Phase.ALT,
                Phase.ALT: Phase.BTC
            }
            
            # Vérifier si les conditions de la phase suivante émergent
            next_typical = typical_sequence[current]
            next_score = scores.get(next_typical, 0.0)
            current_score = scores.get(current, 0.0)
            
            # Si la phase suivante commence à scorer fort, c'est probablement elle
            if next_score > current_score * 0.8:  
                return next_typical
            
            # Sinon, chercher la phase avec le deuxième meilleur score
            sorted_phases = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_phases) >= 2 and sorted_phases[1][1] > 0.2:
                return sorted_phases[1][0]

            return typical_sequence[current]  # Fallback à la séquence typique

        except Exception as e:
            logger.warning(f"Error predicting next phase: {e}")
            return None

# Instance globale
_phase_engine: Optional[PhaseEngine] = None

def get_phase_engine() -> PhaseEngine:
    """Retourne l'instance singleton du PhaseEngine"""
    global _phase_engine
    if _phase_engine is None:
        _phase_engine = PhaseEngine()
    return _phase_engine