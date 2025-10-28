"""
Strategy Registry - Templates de stratégies configurables

Convertit les "blended strategies" frontend en templates backend :
- Templates prédéfinis (Conservative, Balanced, Aggressive)  
- Combinaison configurable cycle/regime/signals
- Génération de suggestions d'allocation
- Cache intelligent avec hot-reload
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from services.execution.score_registry import get_score_registry
from services.execution.phase_engine import get_phase_engine, Phase


log = logging.getLogger(__name__)


class StrategyTemplate(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced" 
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


@dataclass
class StrategyWeights:
    """Poids des composants pour une stratégie"""
    cycle: float = 0.3
    onchain: float = 0.35
    risk_adjusted: float = 0.25
    sentiment: float = 0.1
    
    def normalize(self):
        """Normalise les poids pour qu'ils somment à 1.0"""
        total = self.cycle + self.onchain + self.risk_adjusted + self.sentiment
        if total > 0:
            self.cycle /= total
            self.onchain /= total  
            self.risk_adjusted /= total
            self.sentiment /= total


@dataclass
class AllocationTarget:
    """Target d'allocation pour un asset"""
    symbol: str
    weight: float
    rationale: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class StrategyConfig:
    """Configuration complète d'une stratégie"""
    name: str
    template: StrategyTemplate
    weights: StrategyWeights
    risk_budget: Dict[str, float]  # {"volatility": 0.15, "correlation": 0.8}
    phase_adjustments: Dict[str, float]  # {"btc": 0.9, "alt": 1.2}  
    confidence_threshold: float = 0.5
    rebalance_threshold_pct: float = 0.05
    description: Optional[str] = None


@dataclass 
class StrategyResult:
    """Résultat du calcul de stratégie"""
    decision_score: float
    confidence: float
    targets: List[AllocationTarget]
    rationale: List[str]
    policy_hint: str  # "Slow", "Normal", "Aggressive"
    generated_at: datetime
    strategy_used: str


class StrategyRegistry:
    """Registry central des stratégies avec templates configurables"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/strategy_templates.json")
        self.templates: Dict[str, StrategyConfig] = {}
        self.config_loaded_at: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)
        self._last_result_cache: Dict[str, Tuple[StrategyResult, datetime]] = {}
        
        # Dépendances injectées
        self.score_registry = get_score_registry()
        self.phase_engine = get_phase_engine()
        
        # Templates par défaut en fallback
        self.fallback_templates = self._create_fallback_templates()
    
    def _create_fallback_templates(self) -> Dict[str, StrategyConfig]:
        """Crée les templates par défaut inspirés du frontend"""
        return {
            "conservative": StrategyConfig(
                name="Conservative",
                template=StrategyTemplate.CONSERVATIVE,
                weights=StrategyWeights(cycle=0.2, onchain=0.3, risk_adjusted=0.4, sentiment=0.1),
                risk_budget={"volatility": 0.12, "correlation": 0.7, "var_95_pct": 0.03},
                phase_adjustments={"btc": 1.1, "eth": 1.0, "large": 0.9, "alt": 0.8},
                confidence_threshold=0.6,
                rebalance_threshold_pct=0.08,
                description="Favorise la stabilité et la préservation du capital"
            ),
            "balanced": StrategyConfig(
                name="Balanced", 
                template=StrategyTemplate.BALANCED,
                weights=StrategyWeights(cycle=0.3, onchain=0.35, risk_adjusted=0.25, sentiment=0.1),
                risk_budget={"volatility": 0.18, "correlation": 0.8, "var_95_pct": 0.05},
                phase_adjustments={"btc": 1.0, "eth": 1.0, "large": 1.0, "alt": 1.0},
                confidence_threshold=0.5,
                rebalance_threshold_pct=0.05,
                description="Équilibre entre croissance et sécurité (défaut frontend)"
            ),
            "aggressive": StrategyConfig(
                name="Aggressive",
                template=StrategyTemplate.AGGRESSIVE,
                weights=StrategyWeights(cycle=0.35, onchain=0.4, risk_adjusted=0.15, sentiment=0.1),
                risk_budget={"volatility": 0.25, "correlation": 0.85, "var_95_pct": 0.08},
                phase_adjustments={"btc": 0.9, "eth": 1.1, "large": 1.2, "alt": 1.3},
                confidence_threshold=0.4,
                rebalance_threshold_pct=0.03,
                description="Maximise l'alpha avec tolérance aux fluctuations"
            )
        }
    
    async def load_templates(self) -> bool:
        """Charge les templates depuis le fichier config"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Parser les templates
                templates = {}
                for template_id, data in config_data.get('templates', {}).items():
                    try:
                        weights = StrategyWeights(**data['weights'])
                        weights.normalize()
                        
                        templates[template_id] = StrategyConfig(
                            name=data['name'],
                            template=StrategyTemplate(data.get('template', 'custom')),
                            weights=weights,
                            risk_budget=data['risk_budget'],
                            phase_adjustments=data['phase_adjustments'],
                            confidence_threshold=data.get('confidence_threshold', 0.5),
                            rebalance_threshold_pct=data.get('rebalance_threshold_pct', 0.05),
                            description=data.get('description')
                        )
                    except Exception as e:
                        log.warning(f"Template {template_id} invalide, ignoré: {e}")
                        continue
                
                self.templates = templates
                log.info(f"Templates chargés: {list(templates.keys())}")
            else:
                # Créer fichier par défaut
                await self._create_default_config()
                self.templates = self.fallback_templates.copy()
                log.info("Config par défaut créée")
            
            self.config_loaded_at = datetime.now()
            return True
            
        except Exception as e:
            log.error(f"Erreur chargement templates: {e}")
            self.templates = self.fallback_templates.copy()
            return False
    
    async def _create_default_config(self):
        """Crée le fichier de config par défaut"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = {
            "templates": {},
            "version": "1.0",
            "last_updated": datetime.now().isoformat()
        }
        
        # Convertir templates par défaut en JSON
        for template_id, template_config in self.fallback_templates.items():
            config["templates"][template_id] = {
                "name": template_config.name,
                "template": template_config.template.value,
                "weights": {
                    "cycle": template_config.weights.cycle,
                    "onchain": template_config.weights.onchain,
                    "risk_adjusted": template_config.weights.risk_adjusted,
                    "sentiment": template_config.weights.sentiment
                },
                "risk_budget": template_config.risk_budget,
                "phase_adjustments": template_config.phase_adjustments,
                "confidence_threshold": template_config.confidence_threshold,
                "rebalance_threshold_pct": template_config.rebalance_threshold_pct,
                "description": template_config.description
            }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    async def calculate_strategy(
        self,
        template_id: str = "balanced",
        custom_weights: Optional[Dict[str, float]] = None,
        force_refresh: bool = False
    ) -> StrategyResult:
        """Calcule la stratégie selon le template (équivalent calculateIntelligentDecisionIndex)"""
        
        # Cache check
        cache_key = f"{template_id}:{json.dumps(custom_weights, sort_keys=True) if custom_weights else ''}"
        if not force_refresh and cache_key in self._last_result_cache:
            cached_result, cached_at = self._last_result_cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                return cached_result
        
        # Charger templates si nécessaire
        if not self.templates or not self.config_loaded_at:
            await self.load_templates()
        
        # Obtenir template
        strategy_config = self.templates.get(template_id, self.templates["balanced"])
        
        # Override des poids si fournis
        if custom_weights:
            strategy_config.weights = StrategyWeights(**custom_weights)
            strategy_config.weights.normalize()
        
        try:
            # 1. Obtenir les scores des composants
            scores = await self.score_registry.calculate_canonical_score()
            phase_state = await self.phase_engine.get_current_phase()
            
            # 2. Convertir vers les métriques frontend (simulation)
            cycle_score = self._simulate_cycle_score(phase_state)
            onchain_score = scores.decision  # Utilise le score canonique
            risk_score = scores.components.risk  # ✅ Direct (0-100, plus haut = plus robuste)
            sentiment_score = scores.components.sentiment
            
            # 3. Calcul pondéré comme dans calculateIntelligentDecisionIndex
            w = strategy_config.weights
            raw_decision_score = (
                cycle_score * w.cycle +
                onchain_score * w.onchain +
                risk_score * w.risk_adjusted +
                sentiment_score * w.sentiment
            )
            
            # 4. Ajustement par phase
            phase_factor = strategy_config.phase_adjustments.get(phase_state.phase_now.value, 1.0)
            adjusted_score = raw_decision_score * phase_factor
            final_score = max(0.0, min(100.0, adjusted_score))
            
            # 5. Calcul de confiance (similaire au frontend)
            confidence = self._calculate_confidence(scores, phase_state, strategy_config)
            
            # 6. Génération des targets d'allocation
            targets = self._generate_allocation_targets(final_score, phase_state, strategy_config)
            
            # 7. Policy hint
            policy_hint = self._determine_policy_hint(final_score, confidence, scores.contradiction)
            
            # 8. Rationale
            rationale = self._generate_rationale(
                final_score, strategy_config, phase_state, scores
            )
            
            result = StrategyResult(
                decision_score=final_score,
                confidence=confidence,
                targets=targets,
                rationale=rationale,
                policy_hint=policy_hint,
                generated_at=datetime.now(),
                strategy_used=strategy_config.name
            )
            
            # Cache le résultat
            self._last_result_cache[cache_key] = (result, datetime.now())
            
            return result
            
        except Exception as e:
            log.exception(f"Erreur calcul stratégie {template_id}")
            # Fallback sécurisé
            return StrategyResult(
                decision_score=50.0,
                confidence=0.1,
                targets=[AllocationTarget("BTC", 0.6, "Fallback safety")],
                rationale=["Erreur calcul - mode sécurisé"],
                policy_hint="Slow",
                generated_at=datetime.now(),
                strategy_used="Fallback"
            )
    
    def _simulate_cycle_score(self, phase_state) -> float:
        """Simule un cycle score basé sur la phase (compatibilité frontend)"""
        phase_scores = {
            Phase.BTC: 40.0,      # Accumulation/début cycle
            Phase.ETH: 60.0,      # Transition positive  
            Phase.LARGE: 75.0,    # Bull run confirmé
            Phase.ALT: 85.0       # Alt season/euphorie
        }
        return phase_scores.get(phase_state.phase_now, 50.0)
    
    def _calculate_confidence(self, scores, phase_state, strategy_config) -> float:
        """Calcule la confiance totale (similaire frontend)"""
        # Confiance basée sur les composants
        base_confidence = scores.confidence
        phase_confidence = phase_state.confidence
        
        # Ajustement par contradictions (comme dans le frontend)
        contradiction_penalty = min(scores.contradiction * 0.15, 0.15)
        
        # Confiance agrégée
        confidence = (base_confidence * 0.5 + phase_confidence * 0.3 + 0.2) - contradiction_penalty
        
        return max(0.1, min(0.95, confidence))
    
    def _generate_allocation_targets(
        self, decision_score: float, phase_state, strategy_config: StrategyConfig
    ) -> List[AllocationTarget]:
        """Génère les targets d'allocation basés sur score et phase"""
        
        targets = []
        
        # Allocation de base selon le score
        if decision_score < 30:
            # Conservateur - majorité BTC/stables
            targets.extend([
                AllocationTarget("BTC", 0.4, "Score bas - sécurité"),
                AllocationTarget("ETH", 0.2, "Diversification"),  
                AllocationTarget("USDC", 0.4, "Préservation capital")
            ])
        elif decision_score < 60:
            # Modéré
            targets.extend([
                AllocationTarget("BTC", 0.35, "Base solide"),
                AllocationTarget("ETH", 0.25, "Growth potential"),
                AllocationTarget("L1/L0 majors", 0.2, "Diversification"), 
                AllocationTarget("USDC", 0.2, "Buffer")
            ])
        else:
            # Agressif - suivre la phase
            phase = phase_state.phase_now
            if phase == Phase.BTC:
                targets.extend([
                    AllocationTarget("BTC", 0.5, f"Phase {phase.value}"),
                    AllocationTarget("ETH", 0.3, "Prêt transition"),
                    AllocationTarget("L1/L0 majors", 0.2, "Opportuniste")
                ])
            elif phase == Phase.ETH:
                targets.extend([
                    AllocationTarget("BTC", 0.3, "Base"),
                    AllocationTarget("ETH", 0.4, f"Phase {phase.value}"),
                    AllocationTarget("L1/L0 majors", 0.3, "Rotation")
                ])
            elif phase == Phase.LARGE:
                targets.extend([
                    AllocationTarget("BTC", 0.25, "Base"),
                    AllocationTarget("ETH", 0.25, "Co-leader"),
                    AllocationTarget("L1/L0 majors", 0.5, f"Phase {phase.value}")
                ])
            else:  # ALT
                targets.extend([
                    AllocationTarget("BTC", 0.2, "Base"),
                    AllocationTarget("ETH", 0.2, "Bridge"),
                    AllocationTarget("L1/L0 majors", 0.3, "Large caps"),
                    AllocationTarget("ALT", 0.3, f"Phase {phase.value}")
                ])
        
        # Normaliser les poids
        total_weight = sum(t.weight for t in targets)
        if total_weight > 0:
            for target in targets:
                target.weight = target.weight / total_weight
        
        return targets
    
    def _determine_policy_hint(self, score: float, confidence: float, contradiction: float) -> str:
        """Détermine le policy hint pour l'exécution"""
        
        # Si contradictions élevées ou confiance faible -> Slow
        if contradiction > 0.6 or confidence < 0.4:
            return "Slow"
        
        # Score et confiance élevés -> Aggressive
        if score > 75 and confidence > 0.7:
            return "Aggressive"
        
        return "Normal"
    
    def _generate_rationale(
        self, score: float, strategy_config: StrategyConfig, 
        phase_state, scores
    ) -> List[str]:
        """Génère l'explication de la décision"""
        
        rationale = []
        
        # Template utilisé
        rationale.append(f"Stratégie {strategy_config.name}")
        
        # Score principal
        if score > 70:
            rationale.append("Score élevé - momentum favorable")
        elif score < 40:
            rationale.append("Score bas - prudence recommandée")
        else:
            rationale.append("Score modéré - approche équilibrée")
        
        # Phase de marché
        phase = phase_state.phase_now.value
        rationale.append(f"Phase {phase} détectée ({phase_state.confidence:.1%} confiance)")
        
        # Contradictions
        if scores.contradiction > 0.5:
            rationale.append("Signaux contradictoires - réduction confiance")
        
        return rationale
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Retourne la liste des templates disponibles"""
        if not self.templates:
            return {}
        
        return {
            template_id: {
                "name": config.name,
                "description": config.description,
                "template": config.template.value,
                "risk_level": self._assess_risk_level(config)
            }
            for template_id, config in self.templates.items()
        }
    
    def _assess_risk_level(self, config: StrategyConfig) -> str:
        """Évalue le niveau de risque d'un template"""
        risk_score = (
            config.weights.cycle * 0.3 +
            config.weights.onchain * 0.3 + 
            (1.0 - config.weights.risk_adjusted) * 0.4
        )
        
        if risk_score < 0.4:
            return "low"
        elif risk_score < 0.7:
            return "medium"
        else:
            return "high"
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check du Strategy Registry"""
        return {
            "status": "healthy" if self.templates else "degraded",
            "templates_loaded": len(self.templates),
            "config_loaded_at": self.config_loaded_at.isoformat() if self.config_loaded_at else None,
            "cache_size": len(self._last_result_cache),
            "timestamp": datetime.now().isoformat()
        }


# Singleton
_strategy_registry: Optional[StrategyRegistry] = None

def get_strategy_registry() -> StrategyRegistry:
    """Obtient l'instance singleton du Strategy Registry"""
    global _strategy_registry
    if _strategy_registry is None:
        _strategy_registry = StrategyRegistry()
    return _strategy_registry