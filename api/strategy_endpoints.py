"""
Strategy Endpoints - API pour le Strategy Registry

Endpoints PR-B :
- GET /api/strategy/templates - Liste des templates disponibles
- POST /api/strategy/preview - Preview d'allocation selon template  
- GET /api/strategy/current - État stratégie courante
- POST /api/strategy/apply - Application template (future)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from services.execution.strategy_registry import get_strategy_registry, StrategyTemplate

router = APIRouter(prefix="/api/strategy", tags=["strategy"])
log = logging.getLogger(__name__)


# Models Pydantic pour API
class AllocationTargetResponse(BaseModel):
    symbol: str
    weight: float = Field(..., ge=0, le=1, description="Poids (0-1)")
    rationale: Optional[str] = Field(None, description="Justification allocation")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confiance allocation")


class StrategyResultResponse(BaseModel):
    decision_score: float = Field(..., ge=0, le=100, description="Score décisionnel 0-100")
    confidence: float = Field(..., ge=0, le=1, description="Confiance globale")
    targets: List[AllocationTargetResponse] = Field(..., description="Targets d'allocation")
    rationale: List[str] = Field(..., description="Explications décision")
    policy_hint: str = Field(..., description="Policy pour exécution: Slow/Normal/Aggressive")
    generated_at: datetime = Field(..., description="Timestamp génération")
    strategy_used: str = Field(..., description="Nom stratégie appliquée")


class TemplateInfoResponse(BaseModel):
    name: str
    description: Optional[str] = None
    template: str = Field(..., description="Type: conservative/balanced/aggressive/custom")
    risk_level: str = Field(..., description="Niveau risque: low/medium/high")


class TemplateWeightsRequest(BaseModel):
    cycle: float = Field(..., ge=0, le=1, description="Poids cycle")
    onchain: float = Field(..., ge=0, le=1, description="Poids onchain")
    risk_adjusted: float = Field(..., ge=0, le=1, description="Poids risk-adjusted")
    sentiment: float = Field(..., ge=0, le=1, description="Poids sentiment")


class PreviewRequest(BaseModel):
    template_id: str = Field(..., description="ID du template à utiliser")
    custom_weights: Optional[TemplateWeightsRequest] = Field(None, description="Poids custom optionnels")
    force_refresh: bool = Field(False, description="Forcer recalcul")


@router.get("/templates", response_model=Dict[str, TemplateInfoResponse])
async def get_strategy_templates():
    """Liste tous les templates de stratégie disponibles"""
    try:
        registry = get_strategy_registry()
        
        # Charger templates si nécessaire
        if not registry.templates:
            await registry.load_templates()
        
        templates = registry.get_available_templates()
        
        # Convertir au format API
        response = {}
        for template_id, info in templates.items():
            response[template_id] = TemplateInfoResponse(
                name=info['name'],
                description=info['description'],
                template=info['template'],
                risk_level=info['risk_level']
            )
        
        log.info(f"Templates retournés: {list(templates.keys())}")
        return response
        
    except Exception as e:
        log.exception("Erreur récupération templates")
        raise HTTPException(500, f"internal_error: {e}")


@router.post("/preview", response_model=StrategyResultResponse) 
async def preview_strategy(request: PreviewRequest):
    """Génère une preview d'allocation selon le template"""
    try:
        registry = get_strategy_registry()
        
        # Validation template_id
        if not registry.templates:
            await registry.load_templates()
            
        if request.template_id not in registry.templates:
            available = list(registry.templates.keys())
            raise HTTPException(400, f"Template inconnu: {request.template_id}. Disponibles: {available}")
        
        # Préparation custom_weights
        custom_weights = None
        if request.custom_weights:
            custom_weights = {
                "cycle": request.custom_weights.cycle,
                "onchain": request.custom_weights.onchain,
                "risk_adjusted": request.custom_weights.risk_adjusted,
                "sentiment": request.custom_weights.sentiment
            }
            
            # Validation somme ≈ 1.0
            total = sum(custom_weights.values())
            if not (0.95 <= total <= 1.05):
                raise HTTPException(400, f"Somme poids invalide: {total:.3f} (attendu ≈1.0)")
        
        # Calcul stratégie
        result = await registry.calculate_strategy(
            template_id=request.template_id,
            custom_weights=custom_weights,
            force_refresh=request.force_refresh
        )
        
        # Conversion vers response model
        targets = []
        for target in result.targets:
            targets.append(AllocationTargetResponse(
                symbol=target.symbol,
                weight=target.weight,
                rationale=target.rationale,
                confidence=target.confidence
            ))
        
        response = StrategyResultResponse(
            decision_score=result.decision_score,
            confidence=result.confidence,
            targets=targets,
            rationale=result.rationale,
            policy_hint=result.policy_hint,
            generated_at=result.generated_at,
            strategy_used=result.strategy_used
        )
        
        log.info(f"Preview {request.template_id}: score={result.decision_score:.1f}, targets={len(targets)}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Erreur preview stratégie {request.template_id}")
        raise HTTPException(500, f"strategy_error: {e}")


@router.get("/current", response_model=StrategyResultResponse)
async def get_current_strategy(template_id: str = Query("balanced", description="Template à utiliser")):
    """Retourne l'état stratégie courante (cache autorisé)"""
    try:
        registry = get_strategy_registry()
        
        # Utilisation du cache (force_refresh=False)
        result = await registry.calculate_strategy(
            template_id=template_id,
            force_refresh=False
        )
        
        # Conversion vers response
        targets = [
            AllocationTargetResponse(
                symbol=t.symbol,
                weight=t.weight,
                rationale=t.rationale,
                confidence=t.confidence
            ) for t in result.targets
        ]
        
        response = StrategyResultResponse(
            decision_score=result.decision_score,
            confidence=result.confidence,
            targets=targets,
            rationale=result.rationale,
            policy_hint=result.policy_hint,
            generated_at=result.generated_at,
            strategy_used=result.strategy_used
        )
        
        return response
        
    except Exception as e:
        log.exception(f"Erreur current strategy {template_id}")
        raise HTTPException(500, f"strategy_error: {e}")


@router.get("/health")
async def strategy_health():
    """Health check du Strategy Registry"""
    try:
        registry = get_strategy_registry()
        health = await registry.health_check()
        return health
    except Exception as e:
        log.exception("Health check strategy failed")
        raise HTTPException(500, f"health_error: {e}")


# Endpoint bonus: comparaison templates
@router.post("/compare")
async def compare_templates(
    template_ids: List[str] = Body(..., description="IDs templates à comparer", max_items=5)
):
    """Compare plusieurs templates côte à côte"""
    try:
        if len(template_ids) < 2:
            raise HTTPException(400, "Au moins 2 templates requis")
            
        registry = get_strategy_registry()
        
        comparisons = {}
        for template_id in template_ids:
            try:
                result = await registry.calculate_strategy(
                    template_id=template_id,
                    force_refresh=False
                )
                
                comparisons[template_id] = {
                    "decision_score": result.decision_score,
                    "confidence": result.confidence,
                    "policy_hint": result.policy_hint,
                    "targets_count": len(result.targets),
                    "strategy_name": result.strategy_used,
                    "primary_allocation": max(result.targets, key=lambda t: t.weight).symbol if result.targets else None
                }
            except Exception as e:
                comparisons[template_id] = {"error": str(e)}
        
        return {
            "comparisons": comparisons,
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erreur comparaison templates")
        raise HTTPException(500, f"compare_error: {e}")


# Endpoint d'administration (future extension)
@router.get("/admin/templates/{template_id}/weights")
async def get_template_weights(template_id: str):
    """Retourne les poids détaillés d'un template (admin)"""
    try:
        registry = get_strategy_registry()
        
        if not registry.templates:
            await registry.load_templates()
            
        if template_id not in registry.templates:
            raise HTTPException(404, f"Template non trouvé: {template_id}")
        
        config = registry.templates[template_id]
        
        return {
            "template_id": template_id,
            "name": config.name,
            "weights": {
                "cycle": config.weights.cycle,
                "onchain": config.weights.onchain,
                "risk_adjusted": config.weights.risk_adjusted,
                "sentiment": config.weights.sentiment
            },
            "risk_budget": config.risk_budget,
            "phase_adjustments": config.phase_adjustments,
            "confidence_threshold": config.confidence_threshold,
            "rebalance_threshold_pct": config.rebalance_threshold_pct
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.exception(f"Erreur admin template {template_id}")
        raise HTTPException(500, f"admin_error: {e}")