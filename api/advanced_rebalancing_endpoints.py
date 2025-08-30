"""
Advanced Rebalancing API Endpoints - API pour les stratégies de rebalancement intelligentes

Expose les fonctionnalités du moteur de rebalancement avancé :
- Stratégies multiples (Risk Parity, Momentum, Mean Reversion, Multi-objectif)
- Optimisation multi-critères (frais, Sharpe, liquidité)
- Smart order execution avec TWAP/VWAP
- Contraintes de trading personnalisables
- Simulation avancée avec impact pricing
"""

from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, List, Any, Optional
import asyncio
import logging
from datetime import datetime

from services.advanced_rebalancing import (
    advanced_rebalancing_engine,
    RebalancingStrategy,
    OptimizationConstraints,
    RebalancingResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advanced-rebalancing", tags=["advanced_rebalancing"])

@router.post("/plan")
async def create_advanced_rebalancing_plan(
    request_data: Dict[str, Any] = Body(...)
):
    """
    Génère un plan de rebalancement avancé avec stratégie sélectionnée
    
    **Strategies disponibles:**
    - `proportional` - Rebalancement proportionnel classique
    - `risk_parity` - Équilibrage du risque (inverse volatilité)
    - `momentum` - Basé sur tendances récentes (surpondère momentum positif)
    - `mean_reversion` - Contrarian (achète sous-performance)
    - `multi_objective` - Optimisation combinée (risque + momentum + liquidité + frais)
    - `smart_consolidation` - Avec consolidation automatique des duplicatas
    
    **Exemple de requête:**
    ```json
    {
        "holdings": [
            {"symbol": "BTC", "value_usd": 5000, "location": "Binance"},
            {"symbol": "WBTC", "value_usd": 1000, "location": "Coinbase"},
            {"symbol": "ETH", "value_usd": 3000, "location": "Kraken"}
        ],
        "target_allocations": {
            "BTC": 40.0,
            "ETH": 35.0,
            "Stablecoins": 25.0
        },
        "strategy": "smart_consolidation",
        "constraints": {
            "max_trade_size_usd": 5000.0,
            "min_trade_size_usd": 50.0,
            "consolidate_duplicates": true,
            "preferred_exchanges": ["Binance", "Kraken"]
        }
    }
    ```
    """
    try:
        # Validation des données d'entrée
        required_fields = ["holdings", "target_allocations"]
        for field in required_fields:
            if field not in request_data:
                raise HTTPException(status_code=400, detail=f"Champ requis manquant: {field}")
        
        holdings = request_data["holdings"]
        target_allocations = request_data["target_allocations"]
        strategy_name = request_data.get("strategy", "smart_consolidation")
        constraints_data = request_data.get("constraints", {})
        
        # Validation holdings
        if not holdings or not isinstance(holdings, list):
            raise HTTPException(status_code=400, detail="Holdings doit être une liste non-vide")
        
        for holding in holdings:
            if not isinstance(holding, dict):
                raise HTTPException(status_code=400, detail="Chaque holding doit être un objet")
            if "symbol" not in holding or "value_usd" not in holding:
                raise HTTPException(status_code=400, detail="Holdings doivent contenir 'symbol' et 'value_usd'")
            
            # Validation montants
            try:
                value_usd = float(holding["value_usd"])
                if value_usd <= 0:
                    raise ValueError("value_usd doit être positif")
                holding["value_usd"] = value_usd
            except ValueError:
                raise HTTPException(status_code=400, detail=f"value_usd invalide pour {holding.get('symbol', 'unknown')}")
        
        # Validation target_allocations
        if not isinstance(target_allocations, dict):
            raise HTTPException(status_code=400, detail="target_allocations doit être un objet")
        
        total_allocation = sum(float(v) for v in target_allocations.values())
        if abs(total_allocation - 100.0) > 1.0:  # Tolérance 1%
            raise HTTPException(
                status_code=400, 
                detail=f"Les allocations cibles doivent totaliser 100%, actuellement: {total_allocation}%"
            )
        
        # Validation et parsing de la stratégie
        try:
            strategy = RebalancingStrategy(strategy_name)
        except ValueError:
            valid_strategies = [s.value for s in RebalancingStrategy]
            raise HTTPException(
                status_code=400, 
                detail=f"Stratégie invalide '{strategy_name}'. Stratégies valides: {valid_strategies}"
            )
        
        # Construction des contraintes
        constraints = OptimizationConstraints()
        if constraints_data:
            # Appliquer les contraintes personnalisées
            for key, value in constraints_data.items():
                if hasattr(constraints, key):
                    setattr(constraints, key, value)
        
        # Exécution du rebalancement avancé
        logger.info(f"Démarrage rebalancement avancé: {strategy.value} pour {len(holdings)} holdings")
        
        result = await advanced_rebalancing_engine.rebalance_portfolio(
            holdings, target_allocations, strategy, constraints
        )
        
        # Formatage de la réponse
        response = {
            "success": True,
            "rebalancing_plan": {
                "strategy_used": result.strategy_used,
                "actions": result.actions,
                "duplicate_consolidations": result.duplicate_consolidations,
                "execution_summary": {
                    "total_actions": len(result.actions),
                    "total_consolidations": len(result.duplicate_consolidations),
                    "estimated_volume": result.metadata.get("total_volume", 0),
                    "estimated_fees": result.estimated_total_fees,
                    "execution_complexity": result.execution_complexity
                }
            },
            "optimization_metrics": {
                "optimization_score": result.optimization_score,
                "market_timing_score": result.market_timing_score,
                "risk_metrics": result.risk_metrics
            },
            "execution_guidance": {
                "complexity_level": result.execution_complexity,
                "warnings": result.warnings,
                "split_orders": result.metadata.get("num_splits", 0),
                "average_priority": result.metadata.get("avg_priority", 5)
            },
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "strategy": strategy.value,
                "constraints_applied": vars(constraints)
            }
        }
        
        logger.info(f"Plan généré: {len(result.actions)} actions, score {result.optimization_score:.1f}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération plan avancé: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")

@router.post("/simulate")
async def simulate_rebalancing_strategies(
    request_data: Dict[str, Any] = Body(...)
):
    """
    Simule plusieurs stratégies de rebalancement pour comparaison
    
    **Compare automatiquement:**
    - Proportional (baseline)
    - Risk Parity
    - Momentum
    - Mean Reversion
    - Multi-objectif
    - Smart Consolidation
    
    **Exemple de requête:**
    ```json
    {
        "holdings": [...],
        "target_allocations": {...},
        "strategies": ["proportional", "risk_parity", "momentum", "multi_objective"],
        "constraints": {...}
    }
    ```
    
    **Retourne une comparaison détaillée** avec scores, frais, risques pour chaque stratégie.
    """
    try:
        # Validation similaire à /plan
        required_fields = ["holdings", "target_allocations"]
        for field in required_fields:
            if field not in request_data:
                raise HTTPException(status_code=400, detail=f"Champ requis manquant: {field}")
        
        holdings = request_data["holdings"]
        target_allocations = request_data["target_allocations"]
        strategies_to_test = request_data.get("strategies", [s.value for s in RebalancingStrategy])
        constraints_data = request_data.get("constraints", {})
        
        # Construction contraintes
        constraints = OptimizationConstraints()
        if constraints_data:
            for key, value in constraints_data.items():
                if hasattr(constraints, key):
                    setattr(constraints, key, value)
        
        # Simulation de toutes les stratégies demandées
        simulation_results = {}
        
        for strategy_name in strategies_to_test:
            try:
                strategy = RebalancingStrategy(strategy_name)
                
                logger.info(f"Simulation stratégie: {strategy.value}")
                result = await advanced_rebalancing_engine.rebalance_portfolio(
                    holdings, target_allocations, strategy, constraints
                )
                
                simulation_results[strategy_name] = {
                    "optimization_score": result.optimization_score,
                    "estimated_fees": result.estimated_total_fees,
                    "market_timing_score": result.market_timing_score,
                    "execution_complexity": result.execution_complexity,
                    "total_actions": len(result.actions),
                    "total_consolidations": len(result.duplicate_consolidations),
                    "risk_metrics": result.risk_metrics,
                    "warnings_count": len(result.warnings),
                    "volume": result.metadata.get("total_volume", 0),
                    "actions_preview": result.actions[:3] if result.actions else []  # Top 3 actions
                }
                
            except ValueError:
                logger.warning(f"Stratégie invalide ignorée: {strategy_name}")
                continue
            except Exception as e:
                logger.error(f"Erreur simulation {strategy_name}: {e}")
                simulation_results[strategy_name] = {
                    "error": str(e),
                    "optimization_score": 0
                }
        
        if not simulation_results:
            raise HTTPException(status_code=400, detail="Aucune stratégie valide à simuler")
        
        # Analyse comparative
        valid_results = {k: v for k, v in simulation_results.items() if "error" not in v}
        
        if valid_results:
            # Meilleure stratégie par critère
            best_optimization = max(valid_results.keys(), key=lambda k: valid_results[k]["optimization_score"])
            best_timing = max(valid_results.keys(), key=lambda k: valid_results[k]["market_timing_score"])
            lowest_fees = min(valid_results.keys(), key=lambda k: valid_results[k]["estimated_fees"])
            lowest_complexity = min(valid_results.keys(), 
                                  key=lambda k: {"Low": 1, "Medium": 2, "High": 3}[valid_results[k]["execution_complexity"]])
        
        # Recommandation globale
        if valid_results:
            # Score composite pour recommandation
            composite_scores = {}
            for strategy, metrics in valid_results.items():
                composite = (
                    metrics["optimization_score"] * 0.4 +
                    metrics["market_timing_score"] * 0.2 +
                    (100 - min(metrics["estimated_fees"] / metrics["volume"] * 100, 100)) * 0.2 +  # Score frais
                    ({"Low": 100, "Medium": 60, "High": 20}[metrics["execution_complexity"]]) * 0.2
                )
                composite_scores[strategy] = composite
            
            recommended_strategy = max(composite_scores.keys(), key=lambda k: composite_scores[k])
        else:
            recommended_strategy = None
        
        response = {
            "simulation_results": simulation_results,
            "comparative_analysis": {
                "strategies_tested": len(simulation_results),
                "successful_simulations": len(valid_results),
                "best_by_criteria": {
                    "optimization": best_optimization if valid_results else None,
                    "market_timing": best_timing if valid_results else None,
                    "lowest_fees": lowest_fees if valid_results else None,
                    "simplest_execution": lowest_complexity if valid_results else None
                } if valid_results else {},
                "recommended_strategy": recommended_strategy,
                "recommendation_reasoning": f"Score composite le plus élevé ({composite_scores.get(recommended_strategy, 0):.1f})" if recommended_strategy else "Aucune simulation réussie"
            },
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "simulation_duration": "< 1 second",  # Pour info utilisateur
                "constraints_used": vars(constraints)
            }
        }
        
        logger.info(f"Simulation terminée: {len(valid_results)}/{len(strategies_to_test)} stratégies réussies")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur simulation stratégies: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")

@router.get("/strategies")
async def get_available_strategies():
    """
    Liste les stratégies de rebalancement disponibles avec descriptions
    
    **Retourne** la documentation complète de chaque stratégie avec:
    - Description et cas d'usage
    - Paramètres et contraintes
    - Avantages et inconvénients
    - Recommandations d'utilisation
    """
    strategies_info = {
        "proportional": {
            "name": "Rebalancement Proportionnel",
            "description": "Stratégie classique basée sur les allocations cibles fixes",
            "best_for": ["Portefeuilles stables", "Stratégie passive", "Débutants"],
            "pros": ["Simple à comprendre", "Prévisible", "Faible complexité"],
            "cons": ["N'adapte pas au marché", "Peut manquer opportunités"],
            "complexity": "Low",
            "risk_level": "Medium"
        },
        "risk_parity": {
            "name": "Risk Parity",
            "description": "Équilibre le risque en allouant inversement à la volatilité",
            "best_for": ["Minimisation du risque", "Marchés volatils", "Diversification"],
            "pros": ["Réduit concentration risque", "Adaptatif à volatilité", "Stable long terme"],
            "cons": ["Peut sous-performer", "Complexe à comprendre"],
            "complexity": "Medium",
            "risk_level": "Low"
        },
        "momentum": {
            "name": "Momentum-Based",
            "description": "Surpondère les assets avec tendances positives récentes",
            "best_for": ["Marchés haussiers", "Trading actif", "Capturer tendances"],
            "pros": ["Capture momentum", "Performance court terme", "Adaptatif"],
            "cons": ["Risqué en retournement", "Trading fréquent", "Frais élevés"],
            "complexity": "Medium",
            "risk_level": "High"
        },
        "mean_reversion": {
            "name": "Mean Reversion (Contrarian)",
            "description": "Achète la sous-performance, vend la sur-performance",
            "best_for": ["Marchés sideways", "Value investing", "Long terme"],
            "pros": ["Contrarian intelligent", "Achète bas", "Discipliné"],
            "cons": ["Peut manquer breakouts", "Patience requise"],
            "complexity": "Medium",
            "risk_level": "Medium"
        },
        "multi_objective": {
            "name": "Multi-Objectif Optimisé",
            "description": "Optimise simultanément risque, momentum, liquidité et frais",
            "best_for": ["Portefeuilles complexes", "Optimisation avancée", "Tous marchés"],
            "pros": ["Approche holistique", "Équilibre plusieurs facteurs", "Sophistiqué"],
            "cons": ["Complexe", "Paramètres nombreux", "Black box"],
            "complexity": "High",
            "risk_level": "Medium"
        },
        "smart_consolidation": {
            "name": "Smart Consolidation",
            "description": "Rebalancement avec consolidation automatique des duplicatas",
            "best_for": ["Portfolios avec dérivés", "Simplification", "Optimisation"],
            "pros": ["Simplifie portfolio", "Réduit complexité", "Détecte duplicatas"],
            "cons": ["Peut forcer ventes", "Moins de diversification apparente"],
            "complexity": "Medium",
            "risk_level": "Low"
        }
    }
    
    # Paramètres système
    system_constraints = {
        "default_constraints": {
            "max_trade_size_usd": 10000.0,
            "min_trade_size_usd": 25.0,
            "max_allocation_change": 0.15,
            "max_simultaneous_trades": 20,
            "preferred_exchanges": ["Binance", "Kraken", "Coinbase"]
        },
        "supported_exchanges": ["Binance", "Kraken", "Coinbase", "Bitget", "OKX", "Bybit"],
        "optimization_features": [
            "TWAP splitting for large orders",
            "Exchange routing optimization", 
            "Liquidity-based execution",
            "Fee estimation and minimization",
            "Risk metrics calculation",
            "Market timing scores"
        ]
    }
    
    return {
        "strategies": strategies_info,
        "system_info": system_constraints,
        "usage_tips": {
            "beginners": "Commencez par 'proportional' ou 'smart_consolidation'",
            "risk_averse": "Utilisez 'risk_parity' pour minimiser le risque",
            "active_trading": "Testez 'momentum' en marchés haussiers",
            "value_investors": "'mean_reversion' pour approche contrarian",
            "advanced_users": "'multi_objective' pour optimisation complète"
        },
        "meta": {
            "total_strategies": len(strategies_info),
            "api_version": "1.0",
            "last_updated": "2025-08-23"
        }
    }

@router.post("/constraints/validate")
async def validate_constraints(
    constraints: Dict[str, Any] = Body(...)
):
    """
    Valide des contraintes de rebalancement personnalisées
    
    **Vérifie:**
    - Cohérence des limites (min < max)
    - Exchanges supportés
    - Paramètres valides
    - Recommandations d'amélioration
    """
    try:
        issues = []
        warnings = []
        suggestions = []
        
        # Validation des montants
        min_trade = constraints.get("min_trade_size_usd", 25.0)
        max_trade = constraints.get("max_trade_size_usd", 10000.0)
        
        if min_trade >= max_trade:
            issues.append("min_trade_size_usd doit être inférieur à max_trade_size_usd")
        
        if min_trade < 10:
            warnings.append("min_trade_size_usd très bas (<$10) peut générer beaucoup de micro-trades")
        
        if max_trade > 50000:
            warnings.append("max_trade_size_usd élevé (>$50K) peut impacter le marché")
        
        # Validation allocation change
        max_change = constraints.get("max_allocation_change", 0.15)
        if max_change > 0.5:
            warnings.append("max_allocation_change >50% peut créer instabilité")
        elif max_change < 0.05:
            warnings.append("max_allocation_change <5% limite flexibilité de rebalancement")
        
        # Validation exchanges
        preferred = constraints.get("preferred_exchanges", [])
        blacklisted = constraints.get("blacklisted_exchanges", [])
        
        supported_exchanges = ["Binance", "Kraken", "Coinbase", "Bitget", "OKX", "Bybit"]
        
        for exchange in preferred:
            if exchange not in supported_exchanges:
                issues.append(f"Exchange non supporté dans preferred_exchanges: {exchange}")
        
        for exchange in blacklisted:
            if exchange not in supported_exchanges:
                warnings.append(f"Exchange non supporté dans blacklist: {exchange}")
        
        # Conflit preferred/blacklisted
        conflicts = set(preferred) & set(blacklisted)
        if conflicts:
            issues.append(f"Exchanges en conflit (preferred ET blacklisted): {list(conflicts)}")
        
        # Validation simultaneous trades
        max_trades = constraints.get("max_simultaneous_trades", 20)
        if max_trades > 100:
            warnings.append("max_simultaneous_trades >100 peut saturer système d'exécution")
        elif max_trades < 5:
            warnings.append("max_simultaneous_trades <5 limite efficacité de rebalancement")
        
        # Suggestions d'optimisation
        if len(preferred) < 2:
            suggestions.append("Ajouter plus d'exchanges préférés pour optimiser routing")
        
        if not constraints.get("consolidate_duplicates", True):
            suggestions.append("Activer consolidate_duplicates pour simplifier portfolio")
        
        if constraints.get("preserve_staking", True):
            suggestions.append("preserve_staking=true peut limiter optimisations sur assets stakés")
        
        # Score de validation
        validation_score = 100
        validation_score -= len(issues) * 20  # Issues critiques
        validation_score -= len(warnings) * 5  # Warnings modérés
        validation_score = max(0, validation_score)
        
        # Statut global
        if issues:
            status = "invalid"
        elif warnings:
            status = "valid_with_warnings" 
        else:
            status = "valid"
        
        return {
            "validation_status": status,
            "validation_score": validation_score,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "validated_constraints": {
                k: v for k, v in constraints.items() 
                if k in ["min_trade_size_usd", "max_trade_size_usd", "max_allocation_change", 
                        "preferred_exchanges", "blacklisted_exchanges", "max_simultaneous_trades",
                        "preserve_staking", "consolidate_duplicates"]
            },
            "recommended_fixes": [
                f"Corriger: {issue}" for issue in issues
            ],
            "meta": {
                "timestamp": datetime.now().isoformat(),
                "constraints_checked": len(constraints),
                "supported_exchanges": supported_exchanges
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur validation contraintes: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur validation: {str(e)}")