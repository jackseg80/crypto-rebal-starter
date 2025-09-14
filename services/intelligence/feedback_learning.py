"""
Phase 3C - Feedback Learning System
Learns from human corrections and feedback to improve ML decision quality over time
"""
import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
from pathlib import Path
from collections import defaultdict, deque

from .human_loop import HumanDecisionRequest, HumanFeedback, DecisionStatus
from .explainable_ai import DecisionExplanation, FeatureContribution

log = logging.getLogger(__name__)


class LearningPattern(str, Enum):
    """Types de patterns d'apprentissage détectés"""
    SYSTEMATIC_BIAS = "systematic_bias"           # Biais systématique dans les décisions
    FEATURE_IMPORTANCE_DRIFT = "feature_drift"   # Changement d'importance des features
    THRESHOLD_ADJUSTMENT = "threshold_adjustment" # Ajustement des seuils
    CONTEXT_DEPENDENCY = "context_dependency"     # Dépendance au contexte
    SEASONAL_PATTERN = "seasonal_pattern"         # Patterns saisonniers
    HUMAN_EXPERTISE = "human_expertise"           # Expertise humaine spécialisée


@dataclass
class LearningInsight:
    """Insight d'apprentissage depuis le feedback humain"""
    insight_id: str
    pattern_type: LearningPattern
    confidence: float
    impact_score: float
    
    # Description du pattern détecté
    description: str
    affected_features: List[str]
    recommended_adjustment: Dict[str, Any]
    
    # Evidence
    evidence_count: int
    examples: List[str]  # Request IDs d'exemple
    
    # Metadata
    discovered_at: datetime
    last_updated: datetime
    validation_score: float  # Score de validation sur nouvelles données


@dataclass 
class ModelAdjustmentSuggestion:
    """Suggestion d'ajustement de modèle basée sur le feedback"""
    suggestion_id: str
    model_name: str
    adjustment_type: str  # "threshold", "feature_weight", "bias_correction"
    
    current_value: Any
    suggested_value: Any
    confidence: float
    expected_improvement: float
    
    reasoning: str
    supporting_evidence: List[str]
    
    created_at: datetime
    status: str = "pending"  # "pending", "applied", "rejected"


class FeedbackAnalyzer:
    """Analyseur de feedback pour détecter les patterns d'apprentissage"""
    
    def __init__(self):
        self.decision_history: List[HumanDecisionRequest] = []
        self.feedback_history: List[HumanFeedback] = []
        self.learning_insights: Dict[str, LearningInsight] = {}
        
        # Buffers pour analyse en temps réel
        self.recent_decisions = deque(maxlen=100)
        self.feature_corrections = defaultdict(list)
        self.bias_tracking = defaultdict(list)
        
    def add_decision_outcome(self, decision: HumanDecisionRequest):
        """Ajouter le résultat d'une décision pour analyse"""
        self.decision_history.append(decision)
        self.recent_decisions.append(decision)
        
        # Analyser immédiatement si décision modifiée/rejetée
        if decision.status in [DecisionStatus.REJECTED, DecisionStatus.MODIFIED]:
            self._analyze_single_correction(decision)
    
    def add_feedback(self, feedback: HumanFeedback):
        """Ajouter du feedback pour analyse"""
        self.feedback_history.append(feedback)
    
    async def analyze_patterns(self) -> List[LearningInsight]:
        """Analyse complète des patterns dans le feedback"""
        insights = []
        
        # Analyser différents types de patterns
        insights.extend(await self._detect_systematic_bias())
        insights.extend(await self._detect_feature_importance_drift())  
        insights.extend(await self._detect_threshold_issues())
        insights.extend(await self._detect_context_dependencies())
        
        # Mettre à jour le cache d'insights
        for insight in insights:
            self.learning_insights[insight.insight_id] = insight
        
        return insights
    
    def _analyze_single_correction(self, decision: HumanDecisionRequest):
        """Analyse immédiate d'une correction humaine"""
        if not decision.explanation or not decision.explanation.feature_contributions:
            return
        
        # Tracker les corrections par feature
        for feature_contrib in decision.explanation.feature_contributions:
            correction_data = {
                "request_id": decision.request_id,
                "feature_name": feature_contrib.feature_name,
                "ai_contribution": feature_contrib.contribution,
                "ai_importance": feature_contrib.importance,
                "human_disagreed": decision.status == DecisionStatus.REJECTED,
                "human_modified": decision.status == DecisionStatus.MODIFIED,
                "timestamp": decision.decided_at or datetime.now()
            }
            
            self.feature_corrections[feature_contrib.feature_name].append(correction_data)
        
        # Tracker le biais général par type de décision
        bias_data = {
            "decision_type": decision.decision_type,
            "ai_confidence": decision.explanation.confidence,
            "human_disagreed": decision.status == DecisionStatus.REJECTED,
            "risk_level": decision.risk_level,
            "timestamp": decision.decided_at or datetime.now()
        }
        
        self.bias_tracking[decision.decision_type].append(bias_data)
    
    async def _detect_systematic_bias(self) -> List[LearningInsight]:
        """Détecte les biais systématiques dans les décisions"""
        insights = []
        
        # Analyser par type de décision
        for decision_type, bias_history in self.bias_tracking.items():
            if len(bias_history) < 5:  # Pas assez de données
                continue
            
            recent_history = [b for b in bias_history 
                            if b["timestamp"] > datetime.now() - timedelta(days=7)]
            
            if len(recent_history) < 3:
                continue
            
            # Calculer le taux de désaccord
            disagreement_rate = sum(1 for b in recent_history if b["human_disagreed"]) / len(recent_history)
            
            if disagreement_rate > 0.3:  # > 30% de désaccords
                insight = LearningInsight(
                    insight_id=f"bias-{decision_type}-{int(datetime.now().timestamp())}",
                    pattern_type=LearningPattern.SYSTEMATIC_BIAS,
                    confidence=min(1.0, disagreement_rate),
                    impact_score=disagreement_rate * 0.8,
                    description=f"Biais systématique détecté pour {decision_type}: {disagreement_rate:.1%} de désaccords humains",
                    affected_features=[decision_type],
                    recommended_adjustment={
                        "action": "reduce_confidence",
                        "factor": 0.8,
                        "add_human_review_threshold": 0.6
                    },
                    evidence_count=len(recent_history),
                    examples=[b["request_id"] for b in recent_history if "request_id" in b][:3],
                    discovered_at=datetime.now(),
                    last_updated=datetime.now(),
                    validation_score=0.0  # À calculer avec nouvelles données
                )
                
                insights.append(insight)
        
        return insights
    
    async def _detect_feature_importance_drift(self) -> List[LearningInsight]:
        """Détecte les changements d'importance des features"""
        insights = []
        
        for feature_name, corrections in self.feature_corrections.items():
            if len(corrections) < 5:
                continue
            
            # Analyser les corrections récentes vs anciennes
            recent = [c for c in corrections 
                     if c["timestamp"] > datetime.now() - timedelta(days=7)]
            older = [c for c in corrections 
                    if c["timestamp"] <= datetime.now() - timedelta(days=7)]
            
            if len(recent) < 3 or len(older) < 3:
                continue
            
            # Comparer les taux de correction
            recent_correction_rate = sum(1 for c in recent if c["human_disagreed"]) / len(recent)
            older_correction_rate = sum(1 for c in older if c["human_disagreed"]) / len(older)
            
            drift_magnitude = abs(recent_correction_rate - older_correction_rate)
            
            if drift_magnitude > 0.2:  # Changement significatif
                insight = LearningInsight(
                    insight_id=f"drift-{feature_name}-{int(datetime.now().timestamp())}",
                    pattern_type=LearningPattern.FEATURE_IMPORTANCE_DRIFT,
                    confidence=min(1.0, drift_magnitude * 2),
                    impact_score=drift_magnitude * 0.6,
                    description=f"Drift d'importance détecté pour {feature_name}: {drift_magnitude:.1%} de changement",
                    affected_features=[feature_name],
                    recommended_adjustment={
                        "action": "recalibrate_feature_weight",
                        "direction": "increase" if recent_correction_rate > older_correction_rate else "decrease",
                        "magnitude": drift_magnitude
                    },
                    evidence_count=len(recent),
                    examples=[c.get("request_id", "") for c in recent[:3]],
                    discovered_at=datetime.now(),
                    last_updated=datetime.now(),
                    validation_score=0.0
                )
                
                insights.append(insight)
        
        return insights
    
    async def _detect_threshold_issues(self) -> List[LearningInsight]:
        """Détecte les problèmes de seuils (trop restrictifs ou laxistes)"""
        insights = []
        
        # Analyser les décisions par niveau de confiance
        confidence_buckets = defaultdict(list)
        
        for decision in self.recent_decisions:
            if not decision.explanation:
                continue
                
            confidence = decision.explanation.confidence
            bucket = int(confidence * 10) / 10  # Buckets de 0.1
            
            correction_occurred = decision.status in [DecisionStatus.REJECTED, DecisionStatus.MODIFIED]
            confidence_buckets[bucket].append({
                "corrected": correction_occurred,
                "request_id": decision.request_id,
                "risk_level": decision.risk_level
            })
        
        # Détecter les seuils problématiques
        for confidence_level, decisions in confidence_buckets.items():
            if len(decisions) < 5:
                continue
            
            correction_rate = sum(1 for d in decisions if d["corrected"]) / len(decisions)
            
            # Seuil trop laxiste: haute confiance mais beaucoup de corrections
            if confidence_level > 0.8 and correction_rate > 0.2:
                insight = LearningInsight(
                    insight_id=f"threshold-high-{int(datetime.now().timestamp())}",
                    pattern_type=LearningPattern.THRESHOLD_ADJUSTMENT,
                    confidence=correction_rate,
                    impact_score=correction_rate * 0.7,
                    description=f"Seuil de confiance trop laxiste à {confidence_level:.1f}: {correction_rate:.1%} corrections",
                    affected_features=["confidence_threshold"],
                    recommended_adjustment={
                        "action": "increase_human_review_threshold",
                        "from": confidence_level,
                        "to": min(0.95, confidence_level + 0.1)
                    },
                    evidence_count=len(decisions),
                    examples=[d["request_id"] for d in decisions if d["corrected"]][:3],
                    discovered_at=datetime.now(),
                    last_updated=datetime.now(),
                    validation_score=0.0
                )
                insights.append(insight)
            
            # Seuil trop restrictif: faible confiance mais peu de corrections
            elif confidence_level < 0.5 and correction_rate < 0.1:
                insight = LearningInsight(
                    insight_id=f"threshold-low-{int(datetime.now().timestamp())}",
                    pattern_type=LearningPattern.THRESHOLD_ADJUSTMENT,
                    confidence=1.0 - correction_rate,
                    impact_score=(1.0 - correction_rate) * 0.5,
                    description=f"Seuil trop restrictif à {confidence_level:.1f}: seulement {correction_rate:.1%} corrections",
                    affected_features=["confidence_threshold"],
                    recommended_adjustment={
                        "action": "reduce_human_review_threshold", 
                        "from": confidence_level,
                        "to": max(0.3, confidence_level - 0.1)
                    },
                    evidence_count=len(decisions),
                    examples=[d["request_id"] for d in decisions][:3],
                    discovered_at=datetime.now(),
                    last_updated=datetime.now(),
                    validation_score=0.0
                )
                insights.append(insight)
        
        return insights
    
    async def _detect_context_dependencies(self) -> List[LearningInsight]:
        """Détecte les dépendances au contexte non capturées par le modèle"""
        insights = []
        
        # Grouper par contexte de marché
        context_groups = defaultdict(list)
        
        for decision in self.recent_decisions:
            if not decision.context:
                continue
            
            # Extraire le contexte de marché principal
            market_context = "normal"  # Default
            
            if decision.context.get("volatility", 0) > 0.05:
                market_context = "high_volatility"
            elif decision.context.get("correlation", 0.5) > 0.8:
                market_context = "high_correlation"
            elif decision.context.get("phase") in ["distribution", "markdown"]:
                market_context = "bearish_phase"
            
            correction_occurred = decision.status in [DecisionStatus.REJECTED, DecisionStatus.MODIFIED]
            context_groups[market_context].append({
                "corrected": correction_occurred,
                "confidence": decision.explanation.confidence if decision.explanation else 0.5,
                "request_id": decision.request_id
            })
        
        # Analyser les différences de performance par contexte
        baseline_performance = None
        for context, decisions in context_groups.items():
            if len(decisions) < 5:
                continue
            
            correction_rate = sum(1 for d in decisions if d["corrected"]) / len(decisions)
            avg_confidence = sum(d["confidence"] for d in decisions) / len(decisions)
            
            if context == "normal":
                baseline_performance = (correction_rate, avg_confidence)
                continue
            
            if baseline_performance:
                baseline_correction_rate, baseline_confidence = baseline_performance
                
                # Contexte avec performance significativement différente
                if abs(correction_rate - baseline_correction_rate) > 0.15:
                    insight = LearningInsight(
                        insight_id=f"context-{context}-{int(datetime.now().timestamp())}",
                        pattern_type=LearningPattern.CONTEXT_DEPENDENCY,
                        confidence=abs(correction_rate - baseline_correction_rate) * 2,
                        impact_score=abs(correction_rate - baseline_correction_rate) * 0.6,
                        description=f"Performance différente en contexte {context}: {correction_rate:.1%} vs {baseline_correction_rate:.1%} corrections",
                        affected_features=["market_context", context],
                        recommended_adjustment={
                            "action": "add_context_specific_model",
                            "context": context,
                            "adjustment_factor": correction_rate / max(baseline_correction_rate, 0.01)
                        },
                        evidence_count=len(decisions),
                        examples=[d["request_id"] for d in decisions if d["corrected"]][:3],
                        discovered_at=datetime.now(),
                        last_updated=datetime.now(),
                        validation_score=0.0
                    )
                    insights.append(insight)
        
        return insights


class FeedbackLearningEngine:
    """
    Moteur principal d'apprentissage par feedback
    Orchestre l'analyse du feedback et génère des suggestions d'amélioration
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.analyzer = FeedbackAnalyzer()
        self.model_suggestions: Dict[str, ModelAdjustmentSuggestion] = {}
        
        # Configuration d'apprentissage
        self.learning_config = self.config.get("learning_config", {
            "min_feedback_count": 10,           # Minimum de feedback avant apprentissage
            "insight_confidence_threshold": 0.6, # Seuil de confiance pour les insights
            "auto_apply_threshold": 0.8,        # Auto-appliquer les ajustements haute confiance
            "validation_window_days": 7,        # Fenêtre de validation des ajustements
        })
        
        # Métriques d'apprentissage
        self.learning_metrics = {
            "insights_generated": 0,
            "suggestions_created": 0,
            "suggestions_applied": 0,
            "model_improvements": 0,
            "last_learning_cycle": None
        }
        
        self.running = False
        self.learning_task: Optional[asyncio.Task] = None
        
        log.info("FeedbackLearning Engine initialized")
    
    async def start(self):
        """Démarrer le moteur d'apprentissage"""
        if self.running:
            return
        
        self.running = True
        
        # Démarrer le cycle d'apprentissage périodique
        self.learning_task = asyncio.create_task(self._learning_cycle())
        
        log.info("FeedbackLearning Engine started")
    
    async def stop(self):
        """Arrêter le moteur d'apprentissage"""
        if not self.running:
            return
        
        self.running = False
        
        if self.learning_task:
            self.learning_task.cancel()
            try:
                await self.learning_task
            except asyncio.CancelledError:
                pass
        
        log.info("FeedbackLearning Engine stopped")
    
    async def process_decision_outcome(self, decision: HumanDecisionRequest):
        """Traiter le résultat d'une décision pour apprentissage"""
        self.analyzer.add_decision_outcome(decision)
        
        # Apprentissage immédiat si décision critique corrigée
        if (decision.status in [DecisionStatus.REJECTED, DecisionStatus.MODIFIED] and
            decision.urgency_level.value in ["critical", "high"]):
            
            await self._trigger_immediate_learning(decision)
    
    async def process_feedback(self, feedback: HumanFeedback):
        """Traiter le feedback humain pour apprentissage"""
        self.analyzer.add_feedback(feedback)
        
        # Analyser si feedback très négatif
        if (feedback.decision_quality <= 2 or 
            feedback.confidence_in_ai <= 2 or
            feedback.would_decide_differently):
            
            log.info(f"Negative feedback received for {feedback.request_id} - triggering analysis")
    
    async def generate_model_improvements(self) -> List[ModelAdjustmentSuggestion]:
        """Générer des suggestions d'amélioration de modèle"""
        
        # Analyser les patterns d'apprentissage
        insights = await self.analyzer.analyze_patterns()
        high_confidence_insights = [i for i in insights if i.confidence >= self.learning_config["insight_confidence_threshold"]]
        
        suggestions = []
        
        for insight in high_confidence_insights:
            suggestion = await self._convert_insight_to_suggestion(insight)
            if suggestion:
                suggestions.append(suggestion)
                self.model_suggestions[suggestion.suggestion_id] = suggestion
        
        self.learning_metrics["suggestions_created"] += len(suggestions)
        
        log.info(f"Generated {len(suggestions)} model improvement suggestions")
        return suggestions
    
    async def _convert_insight_to_suggestion(self, insight: LearningInsight) -> Optional[ModelAdjustmentSuggestion]:
        """Convertit un insight en suggestion d'ajustement concret"""
        
        suggestion_id = f"SUGG-{int(datetime.now().timestamp())}-{insight.insight_id[-8:]}"
        
        if insight.pattern_type == LearningPattern.SYSTEMATIC_BIAS:
            return ModelAdjustmentSuggestion(
                suggestion_id=suggestion_id,
                model_name="risk_assessor",
                adjustment_type="bias_correction",
                current_value=1.0,
                suggested_value=insight.recommended_adjustment.get("factor", 0.8),
                confidence=insight.confidence,
                expected_improvement=insight.impact_score * 0.5,
                reasoning=f"Correction du biais systématique: {insight.description}",
                supporting_evidence=insight.examples,
                created_at=datetime.now()
            )
        
        elif insight.pattern_type == LearningPattern.THRESHOLD_ADJUSTMENT:
            adjustment = insight.recommended_adjustment
            return ModelAdjustmentSuggestion(
                suggestion_id=suggestion_id,
                model_name="decision_thresholds",
                adjustment_type="threshold",
                current_value=adjustment.get("from", 0.7),
                suggested_value=adjustment.get("to", 0.8),
                confidence=insight.confidence,
                expected_improvement=insight.impact_score * 0.7,
                reasoning=f"Ajustement de seuil: {insight.description}",
                supporting_evidence=insight.examples,
                created_at=datetime.now()
            )
        
        elif insight.pattern_type == LearningPattern.FEATURE_IMPORTANCE_DRIFT:
            adjustment = insight.recommended_adjustment
            weight_multiplier = 1.2 if adjustment.get("direction") == "increase" else 0.8
            
            return ModelAdjustmentSuggestion(
                suggestion_id=suggestion_id,
                model_name="feature_weights",
                adjustment_type="feature_weight",
                current_value=1.0,
                suggested_value=weight_multiplier,
                confidence=insight.confidence,
                expected_improvement=insight.impact_score * 0.6,
                reasoning=f"Ajustement d'importance de feature: {insight.description}",
                supporting_evidence=insight.examples,
                created_at=datetime.now()
            )
        
        return None
    
    async def _trigger_immediate_learning(self, decision: HumanDecisionRequest):
        """Déclenche un apprentissage immédiat pour une décision critique"""
        log.info(f"Triggering immediate learning for critical decision {decision.request_id}")
        
        # Analyse ciblée sur cette décision
        insights = await self.analyzer.analyze_patterns()
        
        # Générer des suggestions immédiates si applicable
        if insights:
            suggestions = await self.generate_model_improvements()
            
            # Auto-appliquer les suggestions haute confiance
            auto_applied = 0
            for suggestion in suggestions:
                if suggestion.confidence >= self.learning_config["auto_apply_threshold"]:
                    await self._apply_suggestion(suggestion)
                    auto_applied += 1
            
            if auto_applied > 0:
                log.info(f"Auto-applied {auto_applied} high-confidence improvements")
    
    async def _apply_suggestion(self, suggestion: ModelAdjustmentSuggestion):
        """Applique une suggestion d'amélioration"""
        # En production, ceci modifierait les paramètres du modèle ML
        # Pour MVP, on log et marque comme appliqué
        
        log.info(f"Applying suggestion {suggestion.suggestion_id}: {suggestion.reasoning}")
        
        suggestion.status = "applied"
        self.learning_metrics["suggestions_applied"] += 1
        self.learning_metrics["model_improvements"] += 1
    
    async def _learning_cycle(self):
        """Cycle d'apprentissage périodique"""
        while self.running:
            try:
                # Attendre 1 heure entre les cycles
                await asyncio.sleep(3600)
                
                if not self.running:
                    break
                
                # Vérifier si assez de feedback disponible
                if len(self.analyzer.feedback_history) < self.learning_config["min_feedback_count"]:
                    continue
                
                log.info("Starting periodic learning cycle")
                
                # Générer des améliorations
                suggestions = await self.generate_model_improvements()
                
                # Auto-appliquer les suggestions haute confiance
                auto_applied = 0
                for suggestion in suggestions:
                    if suggestion.confidence >= self.learning_config["auto_apply_threshold"]:
                        await self._apply_suggestion(suggestion)
                        auto_applied += 1
                
                self.learning_metrics["last_learning_cycle"] = datetime.now()
                self.learning_metrics["insights_generated"] += len(self.analyzer.learning_insights)
                
                log.info(f"Learning cycle completed: {len(suggestions)} suggestions, {auto_applied} auto-applied")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in learning cycle: {e}")
                await asyncio.sleep(1800)  # Wait 30 min on error
    
    # API Methods
    
    def get_learning_insights(self) -> List[Dict[str, Any]]:
        """API: Récupérer les insights d'apprentissage"""
        return [asdict(insight) for insight in self.analyzer.learning_insights.values()]
    
    def get_model_suggestions(self, status_filter: str = None) -> List[Dict[str, Any]]:
        """API: Récupérer les suggestions de modèle"""
        suggestions = list(self.model_suggestions.values())
        
        if status_filter:
            suggestions = [s for s in suggestions if s.status == status_filter]
        
        return [asdict(s) for s in suggestions]
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """API: Métriques d'apprentissage"""
        metrics = self.learning_metrics.copy()
        
        if metrics["last_learning_cycle"]:
            metrics["last_learning_cycle"] = metrics["last_learning_cycle"].isoformat()
        
        # Ajouter métriques d'analyse
        metrics.update({
            "total_decisions_analyzed": len(self.analyzer.decision_history),
            "total_feedback_received": len(self.analyzer.feedback_history),
            "active_insights": len(self.analyzer.learning_insights),
            "pending_suggestions": len([s for s in self.model_suggestions.values() if s.status == "pending"]),
        })
        
        return metrics
    
    def get_performance_trends(self) -> Dict[str, Any]:
        """API: Tendances de performance"""
        # Calculer les tendances basées sur le feedback récent
        recent_feedback = [f for f in self.analyzer.feedback_history 
                          if f.timestamp > datetime.now() - timedelta(days=7)]
        
        if not recent_feedback:
            return {"trend": "insufficient_data"}
        
        avg_quality = sum(f.decision_quality for f in recent_feedback) / len(recent_feedback)
        avg_clarity = sum(f.explanation_clarity for f in recent_feedback) / len(recent_feedback)
        avg_confidence = sum(f.confidence_in_ai for f in recent_feedback) / len(recent_feedback)
        
        return {
            "trend": "improving" if avg_quality > 3.5 else "stable" if avg_quality > 2.5 else "declining",
            "metrics": {
                "average_decision_quality": avg_quality,
                "average_explanation_clarity": avg_clarity, 
                "average_ai_confidence": avg_confidence,
                "feedback_count": len(recent_feedback)
            }
        }
    
    def get_feature_learning_status(self) -> Dict[str, Any]:
        """API: Status d'apprentissage par feature"""
        feature_status = {}
        
        for feature_name, corrections in self.analyzer.feature_corrections.items():
            if corrections:
                correction_rate = sum(1 for c in corrections if c["human_disagreed"]) / len(corrections)
                avg_importance = sum(c["ai_importance"] for c in corrections) / len(corrections)
                
                feature_status[feature_name] = {
                    "correction_rate": correction_rate,
                    "average_importance": avg_importance,
                    "total_corrections": len(corrections),
                    "learning_status": "needs_attention" if correction_rate > 0.3 else "stable"
                }
        
        return feature_status
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métriques complètes du moteur d'apprentissage"""
        return {
            "running": self.running,
            **self.get_learning_metrics(),
            "analyzer_stats": {
                "decision_history_size": len(self.analyzer.decision_history),
                "feedback_history_size": len(self.analyzer.feedback_history),
                "recent_decisions_buffer": len(self.analyzer.recent_decisions),
                "feature_corrections_tracked": len(self.analyzer.feature_corrections),
                "bias_types_tracked": len(self.analyzer.bias_tracking)
            }
        }


# Factory function
def create_feedback_learning_engine(config: Dict[str, Any] = None) -> FeedbackLearningEngine:
    """Factory pour créer une instance du moteur d'apprentissage"""
    return FeedbackLearningEngine(config)


# Singleton global
_global_learning_engine: Optional[FeedbackLearningEngine] = None

async def get_feedback_learning_engine(config: Dict[str, Any] = None) -> FeedbackLearningEngine:
    """Récupère l'instance globale du moteur d'apprentissage"""
    global _global_learning_engine
    
    if _global_learning_engine is None:
        _global_learning_engine = create_feedback_learning_engine(config)
        await _global_learning_engine.start()
    
    return _global_learning_engine