"""
Smart Taxonomy API Endpoints - API d'apprentissage et gestion intelligente de la taxonomie

Expose les fonctionnalités du système de classification intelligente via REST API :
- Classification automatique avec scoring de confiance
- Détection de duplicatas et dérivés
- API d'apprentissage avec feedback humain
- Statistiques et métriques de performance
"""

from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, List, Any, Optional
import asyncio
import logging
from datetime import datetime

from services.smart_classification import smart_classification_service, ClassificationResult
from services.taxonomy import Taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/taxonomy", tags=["smart_taxonomy"])

@router.post("/classify")
async def classify_symbols(
    symbols: List[str] = Body(..., description="Liste des symboles à classifier"),
    confidence_threshold: float = Query(50.0, ge=0, le=100, description="Seuil minimum de confiance"),
    use_cache: bool = Query(True, description="Utiliser le cache de résultats")
):
    """
    Classification intelligente de symboles avec scoring de confiance
    
    **Fonctionnalités:**
    - Classification multi-méthodes (manuel, patterns, CoinGecko, dérivés)
    - Scoring de confiance de 0 à 100%
    - Cache intelligent avec TTL
    - Détection de dérivés (WBTC→BTC, STETH→ETH)
    
    **Exemple:**
    ```json
    {
        "symbols": ["WBTC", "UNKNOWN_TOKEN", "STETH", "DOGE"],
        "confidence_threshold": 70.0
    }
    ```
    """
    try:
        if not symbols:
            raise HTTPException(status_code=400, detail="Liste de symboles vide")
        
        # Validation des symboles
        clean_symbols = [s.strip().upper() for s in symbols if s and s.strip()]
        if not clean_symbols:
            raise HTTPException(status_code=400, detail="Aucun symbole valide fourni")
        
        if len(clean_symbols) > 100:
            raise HTTPException(status_code=400, detail="Trop de symboles (max 100)")
        
        # Classification batch
        results = await smart_classification_service.classify_symbols_batch(
            clean_symbols, confidence_threshold
        )
        
        # Formatage des résultats
        formatted_results = {}
        for symbol, classification in results.items():
            formatted_results[symbol] = {
                "suggested_group": classification.suggested_group,
                "confidence_score": classification.confidence_score,
                "method": classification.method,
                "reasoning": classification.reasoning,
                "base_symbol": classification.base_symbol,
                "metadata": classification.metadata,
                "classified_at": classification.classified_at.isoformat()
            }
        
        # Symboles non classifiés (sous le seuil)
        all_symbols = set(clean_symbols)
        classified_symbols = set(results.keys())
        unclassified = list(all_symbols - classified_symbols)
        
        return {
            "classified_count": len(formatted_results),
            "unclassified_count": len(unclassified),
            "confidence_threshold": confidence_threshold,
            "results": formatted_results,
            "unclassified_symbols": unclassified,
            "processing_info": {
                "cache_used": use_cache,
                "batch_size": len(clean_symbols),
                "success_rate": f"{len(formatted_results)}/{len(clean_symbols)}"
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur classification batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/duplicates")
async def detect_portfolio_duplicates(
    symbols: List[str] = Query(..., description="Symboles du portfolio à analyser")
):
    """
    Détection de doublons et dérivés dans un portfolio
    
    **Détecte:**
    - Tokens wrappés (WBTC/BTC, WETH/ETH)
    - Tokens stakés (STETH/ETH, JITOSOL/SOL)
    - Variants et dérivés connus
    
    **Exemple:**
    ```
    GET /taxonomy/duplicates?symbols=BTC&symbols=WBTC&symbols=ETH&symbols=STETH
    ```
    
    **Réponse:**
    ```json
    {
        "BTC": [{"symbol": "WBTC", "type": "wrapped", "confidence": 95}],
        "ETH": [{"symbol": "STETH", "type": "staked", "confidence": 92}]
    }
    ```
    """
    try:
        if not symbols:
            raise HTTPException(status_code=400, detail="Aucun symbole fourni")
        
        duplicates = smart_classification_service.detect_duplicates_in_portfolio(symbols)
        
        # Enrichissement avec informations taxonomie
        enriched_duplicates = {}
        taxonomy = Taxonomy.load()
        
        for base_symbol, derivatives in duplicates.items():
            base_group = taxonomy.group_for_alias(base_symbol)
            
            enriched_duplicates[base_symbol] = {
                "base_group": base_group,
                "derivatives": derivatives,
                "consolidation_suggestion": {
                    "action": "consider_consolidation",
                    "reasoning": f"Multiple dérivés de {base_symbol} détectés, considérer consolidation vers {base_symbol}",
                    "impact": f"Simplification portfolio, groupe {base_group}"
                }
            }
        
        # Calcul du score de complexité du portfolio
        total_symbols = len(symbols)
        unique_bases = len(set(symbols) - set().union(*[
            [d["symbol"] for d in derivs] 
            for derivs in duplicates.values()
        ]))
        complexity_score = (total_symbols - unique_bases) / total_symbols * 100 if total_symbols > 0 else 0
        
        return {
            "duplicates_found": len(duplicates),
            "total_symbols_analyzed": total_symbols,
            "duplicates": enriched_duplicates,
            "portfolio_analysis": {
                "complexity_score": round(complexity_score, 1),
                "complexity_level": "High" if complexity_score > 30 else "Medium" if complexity_score > 10 else "Low",
                "consolidation_potential": f"{len(duplicates)} groupes de consolidation identifiés"
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur détection doublons: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/learn") 
async def human_feedback_learning(
    feedback_data: Dict[str, Any] = Body(...)
):
    """
    API d'apprentissage - Feedback humain pour améliorer la classification
    
    **Format du feedback:**
    ```json
    {
        "symbol": "CUSTOM_TOKEN",
        "human_classification": "DeFi", 
        "confidence": 90,
        "reasoning": "Token de gouvernance pour protocol XYZ",
        "metadata": {
            "source": "manual_review",
            "reviewer": "analyst_1"
        }
    }
    ```
    
    **Actions:**
    - Mise à jour de la taxonomie persistante
    - Apprentissage des patterns nouveaux
    - Amélioration continue du système
    """
    try:
        # Validation des données de feedback
        required_fields = ["symbol", "human_classification"]
        for field in required_fields:
            if field not in feedback_data:
                raise HTTPException(status_code=400, detail=f"Champ requis manquant: {field}")
        
        symbol = feedback_data["symbol"].strip().upper()
        human_group = feedback_data["human_classification"].strip()
        confidence = float(feedback_data.get("confidence", 95.0))
        reasoning = feedback_data.get("reasoning", f"Classification manuelle par utilisateur")
        metadata = feedback_data.get("metadata", {})
        
        # Validation du groupe
        taxonomy = Taxonomy.load()
        valid_groups = taxonomy.groups_order
        if human_group not in valid_groups:
            raise HTTPException(
                status_code=400, 
                detail=f"Groupe invalide. Groupes valides: {valid_groups}"
            )
        
        # Vérifier s'il y a conflit avec classification automatique
        existing_result = await smart_classification_service.classify_symbol(symbol, use_cache=True)
        conflict_detected = (
            existing_result.suggested_group != human_group and 
            existing_result.confidence_score > 70
        )
        
        # Mise à jour de la taxonomie persistante
        taxonomy.aliases[symbol] = human_group
        taxonomy.save()
        
        # Invalider le cache pour forcer nouvelle classification
        if symbol in smart_classification_service._classification_cache:
            del smart_classification_service._classification_cache[symbol]
        
        # Créer un résultat d'apprentissage
        learning_result = ClassificationResult(
            symbol=symbol,
            suggested_group=human_group,
            confidence_score=confidence,
            method="learning",
            reasoning=reasoning,
            metadata={**metadata, "learned_from_human": True},
            classified_at=datetime.now()
        )
        
        # Mettre en cache le nouveau résultat
        smart_classification_service._cache_result(learning_result)
        
        response = {
            "success": True,
            "symbol": symbol,
            "learned_classification": human_group,
            "confidence": confidence,
            "previous_classification": {
                "group": existing_result.suggested_group,
                "confidence": existing_result.confidence_score,
                "method": existing_result.method
            } if existing_result else None,
            "conflict_detected": conflict_detected,
            "actions_taken": [
                "Taxonomie mise à jour",
                "Cache invalidé", 
                "Nouveau résultat mis en cache"
            ]
        }
        
        if conflict_detected:
            response["conflict_info"] = {
                "message": f"Conflit détecté: classification auto suggérait {existing_result.suggested_group} "
                          f"(confiance {existing_result.confidence_score}%) vs humain {human_group}",
                "recommendation": "Classification humaine appliquée, vérifier si pattern peut être amélioré"
            }
        
        logger.info(f"Apprentissage appliqué: {symbol} → {human_group} (conflit: {conflict_detected})")
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Erreur validation: {e}")
    except Exception as e:
        logger.error(f"Erreur apprentissage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_classification_stats():
    """
    Statistiques du système de classification intelligente
    
    **Métriques incluses:**
    - Performance de classification par méthode
    - Distribution de confiance
    - Statistiques de cache
    - Mappings de dérivés disponibles
    """
    try:
        stats = smart_classification_service.get_classification_stats()
        
        # Enrichir avec informations taxonomie
        taxonomy = Taxonomy.load()
        
        # Analyser la distribution actuelle des groupes
        group_distribution = {}
        for alias, group in taxonomy.aliases.items():
            group_distribution[group] = group_distribution.get(group, 0) + 1
        
        return {
            "classification_engine": stats,
            "taxonomy_stats": {
                "total_aliases": len(taxonomy.aliases),
                "total_groups": len(taxonomy.groups_order),
                "groups": taxonomy.groups_order,
                "group_distribution": group_distribution
            },
            "system_health": {
                "cache_hit_potential": f"{stats['cache_stats']['cached_symbols']} symboles en cache",
                "derivative_coverage": f"{stats['derivative_mappings']['total_mappings']} dérivés mappés",
                "pattern_coverage": f"{sum(stats['advanced_patterns'].values())} patterns actifs",
                "learning_adoption": f"{stats['classification_performance']['method_counts'].get('learning', 0)} classifications apprises"
            },
            "recommendations": [
                "Réviser les classifications à faible confiance" if stats['classification_performance']['confidence_distribution']['low'] > 10 else None,
                "Considérer ajouter plus de patterns pour AI/Data" if stats['advanced_patterns']['ai_data'] < 5 else None,
                "Cache performant, continuer utilisation" if stats['cache_stats']['cached_symbols'] > 50 else "Augmenter utilisation cache"
            ]
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_classification_cache():
    """Vide le cache de classification (maintenance)"""
    try:
        smart_classification_service.clear_cache()
        return {
            "success": True,
            "message": "Cache de classification vidé",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur vidage cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggest-improvements")
async def suggest_taxonomy_improvements(
    min_confidence: float = Query(30.0, description="Seuil minimum de confiance pour suggestions")
):
    """
    Suggestions d'améliorations pour la taxonomie basées sur l'analyse des classifications
    
    **Analyse:**
    - Symboles avec faible confiance
    - Patterns manquants détectés
    - Conflits potentiels
    - Recommandations d'enrichissement
    """
    try:
        # Analyser le cache pour trouver des améliorations potentielles
        cache = smart_classification_service._classification_cache
        
        low_confidence_symbols = []
        pattern_gaps = []
        coingecko_fallbacks = []
        
        for symbol, result in cache.items():
            if result.confidence_score < min_confidence:
                low_confidence_symbols.append({
                    "symbol": symbol,
                    "current_group": result.suggested_group,
                    "confidence": result.confidence_score,
                    "method": result.method,
                    "reasoning": result.reasoning
                })
            
            if result.method == "coingecko" and result.confidence_score < 80:
                coingecko_fallbacks.append({
                    "symbol": symbol,
                    "group": result.suggested_group,
                    "confidence": result.confidence_score
                })
        
        # Suggestions d'amélioration
        suggestions = []
        
        if low_confidence_symbols:
            suggestions.append({
                "type": "low_confidence_review",
                "priority": "high",
                "count": len(low_confidence_symbols),
                "description": f"{len(low_confidence_symbols)} symboles avec confiance < {min_confidence}%",
                "action": "Révision manuelle recommandée",
                "symbols": low_confidence_symbols[:10]  # Top 10
            })
        
        if coingecko_fallbacks:
            suggestions.append({
                "type": "pattern_enhancement",
                "priority": "medium", 
                "count": len(coingecko_fallbacks),
                "description": f"{len(coingecko_fallbacks)} symboles dépendent de CoinGecko avec confiance modérée",
                "action": "Ajouter patterns spécifiques pour éviter dépendance API externe",
                "symbols": coingecko_fallbacks[:5]
            })
        
        # Vérifier les groupes sous-représentés
        taxonomy = Taxonomy.load()
        group_counts = {}
        for alias, group in taxonomy.aliases.items():
            group_counts[group] = group_counts.get(group, 0) + 1
        
        small_groups = [(group, count) for group, count in group_counts.items() if count < 5]
        if small_groups:
            suggestions.append({
                "type": "group_expansion",
                "priority": "low",
                "description": f"{len(small_groups)} groupes avec peu de symboles",
                "action": "Enrichir ces groupes ou fusionner avec d'autres",
                "groups": small_groups
            })
        
        return {
            "analysis_timestamp": datetime.now().isoformat(),
            "analyzed_symbols": len(cache),
            "suggestions_count": len(suggestions),
            "suggestions": suggestions,
            "health_score": max(0, 100 - len(low_confidence_symbols) * 2 - len(coingecko_fallbacks)),
            "next_actions": [
                "Réviser symboles faible confiance" if low_confidence_symbols else "Système stable",
                "Ajouter patterns manquants" if coingecko_fallbacks else "Patterns suffisants",
                "Enrichir groupes sous-représentés" if small_groups else "Distribution équilibrée"
            ]
        }
        
    except Exception as e:
        logger.error(f"Erreur suggestions amélioration: {e}")
        raise HTTPException(status_code=500, detail=str(e))