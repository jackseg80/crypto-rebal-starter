"""
Phase 3C - Human-in-the-loop Decision System
Provides human oversight and intervention capabilities for critical ML decisions
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json

from .explainable_ai import DecisionExplanation, ExplainableAIEngine

log = logging.getLogger(__name__)


class DecisionStatus(str, Enum):
    """Status d'une décision en attente"""
    PENDING = "pending"           # En attente de review humaine
    APPROVED = "approved"         # Approuvée par humain
    REJECTED = "rejected"         # Rejetée par humain
    MODIFIED = "modified"         # Modifiée par humain
    TIMEOUT = "timeout"           # Timeout - décision automatique
    AUTO_APPROVED = "auto_approved"  # Approuvée automatiquement (confiance élevée)


class InterventionType(str, Enum):
    """Types d'intervention humaine"""
    APPROVAL_REQUIRED = "approval_required"      # Approbation requise
    REVIEW_REQUESTED = "review_requested"        # Review demandée
    OVERRIDE_AVAILABLE = "override_available"    # Override possible
    CONSULTATION = "consultation"                # Consultation recommandée
    EMERGENCY_HALT = "emergency_halt"           # Arrêt d'urgence


class UrgencyLevel(str, Enum):
    """Niveaux d'urgence pour les interventions"""
    CRITICAL = "critical"     # < 5 minutes
    HIGH = "high"            # < 15 minutes  
    MEDIUM = "medium"        # < 1 heure
    LOW = "low"              # < 24 heures


@dataclass
class HumanDecisionRequest:
    """Demande de décision humaine"""
    request_id: str
    decision_type: str
    original_decision: Any
    explanation: DecisionExplanation
    intervention_type: InterventionType
    urgency_level: UrgencyLevel
    
    # Context
    context: Dict[str, Any]
    risk_level: float
    potential_impact: str
    
    # Timing
    created_at: datetime
    expires_at: datetime
    timeout_action: str  # "approve", "reject", "maintain_status"
    
    # Status tracking
    status: DecisionStatus = DecisionStatus.PENDING
    human_decision: Optional[Any] = None
    human_feedback: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "intervention_type": self.intervention_type.value,
            "urgency_level": self.urgency_level.value,
            "status": self.status.value
        }


@dataclass
class HumanFeedback:
    """Feedback humain sur une décision"""
    feedback_id: str
    request_id: str
    decision_quality: int  # 1-5 scale
    explanation_clarity: int  # 1-5 scale
    confidence_in_ai: int  # 1-5 scale
    
    feedback_text: str
    suggestions: List[str]
    would_decide_differently: bool
    
    provided_by: str
    timestamp: datetime


class DecisionQueue:
    """Queue des décisions en attente d'intervention humaine"""
    
    def __init__(self):
        self.pending_requests: Dict[str, HumanDecisionRequest] = {}
        self.completed_requests: Dict[str, HumanDecisionRequest] = {}
        self.subscribers: List[Callable[[HumanDecisionRequest], None]] = []
        self._lock = asyncio.Lock()
    
    async def add_request(self, request: HumanDecisionRequest):
        """Ajouter une demande à la queue"""
        async with self._lock:
            self.pending_requests[request.request_id] = request
            log.info(f"Added decision request {request.request_id} to queue - {request.urgency_level.value} priority")
            
            # Notifier les subscribers
            for subscriber in self.subscribers:
                try:
                    await subscriber(request)
                except Exception as e:
                    log.error(f"Error notifying subscriber: {e}")
    
    async def process_decision(self, 
                             request_id: str,
                             human_decision: Any,
                             decided_by: str,
                             feedback: str = None) -> bool:
        """Traiter une décision humaine"""
        async with self._lock:
            if request_id not in self.pending_requests:
                log.warning(f"Decision request {request_id} not found in pending queue")
                return False
            
            request = self.pending_requests[request_id]
            
            # Mettre à jour le statut
            if human_decision == request.original_decision:
                request.status = DecisionStatus.APPROVED
            elif human_decision is None:
                request.status = DecisionStatus.REJECTED
            else:
                request.status = DecisionStatus.MODIFIED
            
            request.human_decision = human_decision
            request.human_feedback = feedback
            request.decided_by = decided_by
            request.decided_at = datetime.now()
            
            # Déplacer vers completed
            self.completed_requests[request_id] = request
            del self.pending_requests[request_id]
            
            log.info(f"Processed decision {request_id}: {request.status.value} by {decided_by}")
            return True
    
    async def check_timeouts(self):
        """Vérifier et traiter les timeouts"""
        async with self._lock:
            now = datetime.now()
            expired_requests = []
            
            for request_id, request in self.pending_requests.items():
                if now > request.expires_at:
                    expired_requests.append(request)
            
            for request in expired_requests:
                # Appliquer l'action de timeout
                if request.timeout_action == "approve":
                    request.status = DecisionStatus.AUTO_APPROVED
                    request.human_decision = request.original_decision
                elif request.timeout_action == "reject":
                    request.status = DecisionStatus.TIMEOUT
                    request.human_decision = None
                else:
                    request.status = DecisionStatus.TIMEOUT
                    request.human_decision = request.original_decision
                
                request.decided_at = now
                request.decided_by = "system_timeout"
                
                # Déplacer vers completed
                self.completed_requests[request.request_id] = request
                del self.pending_requests[request.request_id]
                
                log.warning(f"Decision {request.request_id} timed out - applied {request.timeout_action}")
    
    def get_pending_requests(self, urgency_filter: UrgencyLevel = None) -> List[HumanDecisionRequest]:
        """Récupérer les demandes en attente"""
        requests = list(self.pending_requests.values())
        
        if urgency_filter:
            requests = [r for r in requests if r.urgency_level == urgency_filter]
        
        # Trier par urgence et date de création
        urgency_order = {UrgencyLevel.CRITICAL: 0, UrgencyLevel.HIGH: 1, 
                        UrgencyLevel.MEDIUM: 2, UrgencyLevel.LOW: 3}
        
        requests.sort(key=lambda r: (urgency_order[r.urgency_level], r.created_at))
        return requests
    
    def subscribe(self, callback: Callable[[HumanDecisionRequest], None]):
        """S'abonner aux nouvelles demandes"""
        self.subscribers.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Statistiques de la queue"""
        pending_count = len(self.pending_requests)
        completed_count = len(self.completed_requests)
        
        # Répartition par urgence
        urgency_breakdown = {}
        for urgency in UrgencyLevel:
            count = len([r for r in self.pending_requests.values() if r.urgency_level == urgency])
            urgency_breakdown[urgency.value] = count
        
        return {
            "pending_requests": pending_count,
            "completed_requests": completed_count,
            "total_requests": pending_count + completed_count,
            "urgency_breakdown": urgency_breakdown,
            "oldest_pending": min([r.created_at for r in self.pending_requests.values()], default=None)
        }


class HumanInTheLoopEngine:
    """
    Moteur principal Human-in-the-loop
    Orchestration des décisions nécessitant une intervention humaine
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.decision_queue = DecisionQueue()
        self.feedback_store: Dict[str, HumanFeedback] = {}
        
        # Configuration des seuils d'intervention
        self.intervention_thresholds = self.config.get("intervention_thresholds", {
            "confidence_threshold": 0.7,        # En dessous -> intervention requise
            "risk_threshold": 0.8,              # Au dessus -> intervention requise
            "critical_decisions": ["freeze", "emergency_halt"],  # Toujours intervention
            "auto_approve_threshold": 0.95      # Au dessus -> auto-approve
        })
        
        # Configuration des timeouts par urgence
        self.timeout_config = self.config.get("timeout_config", {
            UrgencyLevel.CRITICAL: timedelta(minutes=5),
            UrgencyLevel.HIGH: timedelta(minutes=15),
            UrgencyLevel.MEDIUM: timedelta(hours=1),
            UrgencyLevel.LOW: timedelta(hours=24)
        })
        
        # Tâche de monitoring des timeouts
        self.timeout_task: Optional[asyncio.Task] = None
        self.running = False
        
        log.info("HumanInTheLoop Engine initialized")
    
    async def start(self):
        """Démarrer le moteur Human-in-the-loop"""
        if self.running:
            return
        
        self.running = True
        
        # Démarrer le monitoring des timeouts
        self.timeout_task = asyncio.create_task(self._timeout_monitor())
        
        log.info("HumanInTheLoop Engine started")
    
    async def stop(self):
        """Arrêter le moteur"""
        if not self.running:
            return
        
        self.running = False
        
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass
        
        log.info("HumanInTheLoop Engine stopped")
    
    async def request_human_decision(self,
                                   decision_type: str,
                                   original_decision: Any,
                                   explanation: DecisionExplanation,
                                   context: Dict[str, Any] = None,
                                   timeout_action: str = "approve") -> HumanDecisionRequest:
        """
        Demander une intervention humaine pour une décision
        
        Args:
            decision_type: Type de décision (alert_action, portfolio_change, etc.)
            original_decision: Décision originale du ML
            explanation: Explication de la décision
            context: Contexte additionnel
            timeout_action: Action en cas de timeout
            
        Returns:
            HumanDecisionRequest créée
        """
        
        # Déterminer le type d'intervention et l'urgence
        intervention_type, urgency_level = self._determine_intervention_requirements(
            decision_type, original_decision, explanation, context
        )
        
        # Vérifier si intervention automatique possible
        if self._should_auto_approve(explanation, context):
            log.info(f"Auto-approving decision {decision_type} due to high confidence")
            # Retourner une request déjà approuvée
            auto_request = self._create_auto_approved_request(
                decision_type, original_decision, explanation, context
            )
            return auto_request
        
        # Créer la demande d'intervention
        request_id = f"HIL-{int(datetime.now().timestamp())}-{str(uuid.uuid4())[:8]}"
        
        # Calculer le timeout
        timeout_delta = self.timeout_config.get(urgency_level, timedelta(hours=1))
        expires_at = datetime.now() + timeout_delta
        
        # Évaluer l'impact potentiel
        potential_impact = self._assess_potential_impact(decision_type, original_decision, context)
        risk_level = explanation.confidence if hasattr(explanation, 'confidence') else 0.5
        
        request = HumanDecisionRequest(
            request_id=request_id,
            decision_type=decision_type,
            original_decision=original_decision,
            explanation=explanation,
            intervention_type=intervention_type,
            urgency_level=urgency_level,
            context=context or {},
            risk_level=risk_level,
            potential_impact=potential_impact,
            created_at=datetime.now(),
            expires_at=expires_at,
            timeout_action=timeout_action
        )
        
        # Ajouter à la queue
        await self.decision_queue.add_request(request)
        
        return request
    
    async def provide_decision(self,
                             request_id: str,
                             human_decision: Any,
                             decided_by: str,
                             feedback: str = None) -> bool:
        """Fournir une décision humaine"""
        return await self.decision_queue.process_decision(
            request_id, human_decision, decided_by, feedback
        )
    
    async def wait_for_decision(self, 
                              request: HumanDecisionRequest,
                              polling_interval: float = 1.0) -> Any:
        """
        Attendre la décision humaine (avec timeout)
        
        Args:
            request: Demande de décision
            polling_interval: Intervalle de polling en secondes
            
        Returns:
            Décision finale (humaine ou par timeout)
        """
        
        while request.status == DecisionStatus.PENDING:
            # Vérifier si la décision est terminée
            completed_request = self.decision_queue.completed_requests.get(request.request_id)
            if completed_request:
                return completed_request.human_decision
            
            # Vérifier timeout manuel
            if datetime.now() > request.expires_at:
                log.warning(f"Decision {request.request_id} timed out during wait")
                break
            
            # Attendre avant le prochain check
            await asyncio.sleep(polling_interval)
        
        # Si on arrive ici, soit timeout soit décision prise
        final_request = (self.decision_queue.completed_requests.get(request.request_id) or 
                        self.decision_queue.pending_requests.get(request.request_id))
        
        if final_request:
            return final_request.human_decision or final_request.original_decision
        
        return request.original_decision  # Fallback
    
    async def submit_feedback(self,
                            request_id: str,
                            quality_rating: int,
                            clarity_rating: int,
                            confidence_rating: int,
                            feedback_text: str,
                            suggestions: List[str] = None,
                            would_decide_differently: bool = False,
                            provided_by: str = "anonymous") -> str:
        """Soumettre un feedback sur une décision"""
        
        feedback_id = f"FB-{int(datetime.now().timestamp())}-{str(uuid.uuid4())[:8]}"
        
        feedback = HumanFeedback(
            feedback_id=feedback_id,
            request_id=request_id,
            decision_quality=quality_rating,
            explanation_clarity=clarity_rating,
            confidence_in_ai=confidence_rating,
            feedback_text=feedback_text,
            suggestions=suggestions or [],
            would_decide_differently=would_decide_differently,
            provided_by=provided_by,
            timestamp=datetime.now()
        )
        
        self.feedback_store[feedback_id] = feedback
        
        log.info(f"Received feedback {feedback_id} for request {request_id}")
        return feedback_id
    
    def _determine_intervention_requirements(self,
                                           decision_type: str,
                                           decision: Any,
                                           explanation: DecisionExplanation,
                                           context: Dict[str, Any] = None) -> Tuple[InterventionType, UrgencyLevel]:
        """Détermine le type d'intervention et l'urgence requis"""
        
        context = context or {}
        confidence = explanation.confidence if hasattr(explanation, 'confidence') else 0.5
        
        # Décisions critiques -> toujours intervention
        if decision_type in self.intervention_thresholds["critical_decisions"]:
            return InterventionType.APPROVAL_REQUIRED, UrgencyLevel.CRITICAL
        
        # Décisions avec risque élevé
        risk_level = context.get("risk_level", 0.0)
        if risk_level > self.intervention_thresholds["risk_threshold"]:
            return InterventionType.APPROVAL_REQUIRED, UrgencyLevel.HIGH
        
        # Décisions avec faible confiance
        if confidence < self.intervention_thresholds["confidence_threshold"]:
            if confidence < 0.5:
                return InterventionType.APPROVAL_REQUIRED, UrgencyLevel.MEDIUM
            else:
                return InterventionType.REVIEW_REQUESTED, UrgencyLevel.MEDIUM
        
        # Décisions avec impact financier important
        potential_loss = context.get("potential_financial_impact", 0)
        if potential_loss > 10000:  # > $10k
            return InterventionType.APPROVAL_REQUIRED, UrgencyLevel.HIGH
        elif potential_loss > 1000:  # > $1k
            return InterventionType.REVIEW_REQUESTED, UrgencyLevel.MEDIUM
        
        # Par défaut - consultation
        return InterventionType.CONSULTATION, UrgencyLevel.LOW
    
    def _should_auto_approve(self, 
                           explanation: DecisionExplanation,
                           context: Dict[str, Any] = None) -> bool:
        """Détermine si une décision peut être auto-approuvée"""
        
        confidence = explanation.confidence if hasattr(explanation, 'confidence') else 0.5
        context = context or {}
        
        # Confiance très élevée + risque faible
        if (confidence > self.intervention_thresholds["auto_approve_threshold"] and
            context.get("risk_level", 0.0) < 0.3):
            return True
        
        return False
    
    def _create_auto_approved_request(self,
                                    decision_type: str,
                                    decision: Any,
                                    explanation: DecisionExplanation,
                                    context: Dict[str, Any]) -> HumanDecisionRequest:
        """Crée une request pré-approuvée"""
        
        request_id = f"HIL-AUTO-{int(datetime.now().timestamp())}"
        now = datetime.now()
        
        request = HumanDecisionRequest(
            request_id=request_id,
            decision_type=decision_type,
            original_decision=decision,
            explanation=explanation,
            intervention_type=InterventionType.CONSULTATION,
            urgency_level=UrgencyLevel.LOW,
            context=context,
            risk_level=0.2,
            potential_impact="Minimal - auto-approved",
            created_at=now,
            expires_at=now + timedelta(seconds=1),  # Expire immediately
            timeout_action="approve",
            status=DecisionStatus.AUTO_APPROVED,
            human_decision=decision,
            decided_by="auto_approval_system",
            decided_at=now
        )
        
        return request
    
    def _assess_potential_impact(self,
                               decision_type: str,
                               decision: Any,
                               context: Dict[str, Any]) -> str:
        """Évalue l'impact potentiel d'une décision"""
        
        context = context or {}
        
        impact_assessments = {
            "portfolio_freeze": "Arrêt immédiat des opérations - Impact critique sur la liquidité",
            "position_reduction": f"Réduction de position - Impact modéré sur les revenus",
            "risk_limit_change": "Modification des limites de risque - Impact sur l'exposition",
            "alert_escalation": "Escalade d'alerte - Nécessite attention immédiate",
            "emergency_halt": "Arrêt d'urgence - Impact critique sur toutes les opérations"
        }
        
        base_impact = impact_assessments.get(decision_type, "Impact indéterminé")
        
        # Enrichir avec le contexte financier
        financial_impact = context.get("potential_financial_impact", 0)
        if financial_impact > 10000:
            base_impact += f" - Exposition financière: ${financial_impact:,.0f}"
        
        return base_impact
    
    async def _timeout_monitor(self):
        """Monitor des timeouts en arrière-plan"""
        while self.running:
            try:
                await self.decision_queue.check_timeouts()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in timeout monitor: {e}")
                await asyncio.sleep(60)  # Longer delay on error
    
    # API Methods pour l'interface web
    
    def get_pending_decisions(self, urgency_filter: UrgencyLevel = None) -> List[Dict[str, Any]]:
        """API: Récupérer les décisions en attente"""
        requests = self.decision_queue.get_pending_requests(urgency_filter)
        return [request.to_dict() for request in requests]
    
    def get_decision_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """API: Historique des décisions"""
        completed = list(self.decision_queue.completed_requests.values())
        completed.sort(key=lambda r: r.decided_at or r.created_at, reverse=True)
        
        return [request.to_dict() for request in completed[:limit]]
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """API: Statistiques pour le dashboard"""
        queue_stats = self.decision_queue.get_stats()
        
        # Statistiques de feedback
        feedback_count = len(self.feedback_store)
        avg_quality = 0
        if self.feedback_store:
            avg_quality = sum(f.decision_quality for f in self.feedback_store.values()) / feedback_count
        
        return {
            **queue_stats,
            "feedback_submissions": feedback_count,
            "average_decision_quality": avg_quality,
            "engine_running": self.running,
            "auto_approval_enabled": self.intervention_thresholds["auto_approve_threshold"] < 1.0
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métriques détaillées du moteur"""
        return {
            "running": self.running,
            "pending_requests": len(self.decision_queue.pending_requests),
            "completed_requests": len(self.decision_queue.completed_requests),
            "feedback_count": len(self.feedback_store),
            "intervention_thresholds": self.intervention_thresholds,
            "timeout_config": {k.value: v.total_seconds() for k, v in self.timeout_config.items()}
        }


# Factory function
def create_human_loop_engine(config: Dict[str, Any] = None) -> HumanInTheLoopEngine:
    """Factory pour créer une instance du moteur Human-in-the-loop"""
    return HumanInTheLoopEngine(config)


# Singleton global
_global_human_loop_engine: Optional[HumanInTheLoopEngine] = None

async def get_human_loop_engine(config: Dict[str, Any] = None) -> HumanInTheLoopEngine:
    """Récupère l'instance globale du moteur Human-in-the-loop"""
    global _global_human_loop_engine
    
    if _global_human_loop_engine is None:
        _global_human_loop_engine = create_human_loop_engine(config)
        await _global_human_loop_engine.start()
    
    return _global_human_loop_engine