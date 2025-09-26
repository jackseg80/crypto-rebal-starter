#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portfolio Monitoring API - Endpoints pour surveiller les performances du portefeuille

Ce module fournit:
- Métriques de performance du portefeuille
- Alertes sur déviations d'allocation
- Historique des rééquilibrages
- Analytics de performance des stratégies
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
import os
import logging
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Router pour les endpoints portfolio monitoring
router = APIRouter(prefix="/api/portfolio", tags=["portfolio-monitoring"])

USE_MOCK_MONITORING = os.getenv("USE_MOCK_MONITORING", "true").lower() == "true"

# Chemins de stockage des données
DATA_DIR = Path("data/monitoring")
PORTFOLIO_METRICS_FILE = DATA_DIR / "portfolio_metrics.json"
REBALANCE_HISTORY_FILE = Path("data/rebalance_history.json")
ALERTS_FILE = DATA_DIR / "portfolio_alerts.json"

# Assurer que les répertoires existent
DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_json_file(file_path: Path, default: Any = None):
    """Charger un fichier JSON avec gestion d'erreur"""
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading {file_path}: {e}")
    return default or {}

def save_json_file(file_path: Path, data: Any):
    """Sauvegarder un fichier JSON"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")

def get_mock_portfolio_data():
    """Générer des données de portefeuille simulées pour développement"""
    now = datetime.now(timezone.utc)
    
    return {
        "total_value": 433032.21,
        "change_24h": 2.34,
        "change_7d": -5.67,
        "last_update": now.isoformat(),
        "assets": {
            "Bitcoin": {
                "current_allocation": 45.2,
                "target_allocation": 40.0,
                "deviation": 5.2,
                "value_usd": 195571.48,
                "change_24h": 3.1
            },
            "Ethereum": {
                "current_allocation": 28.1,
                "target_allocation": 30.0,
                "deviation": -1.9,
                "value_usd": 121683.03,
                "change_24h": 1.8
            },
            "Altcoins": {
                "current_allocation": 26.7,
                "target_allocation": 30.0,
                "deviation": -3.3,
                "value_usd": 115777.70,
                "change_24h": 1.9
            }
        },
        "performance_metrics": {
            "sharpe_ratio": 1.42,
            "max_drawdown": -12.3,
            "volatility": 45.6,
            "total_return_7d": -5.67,
            "total_return_30d": 12.34
        }
    }

@router.get("/metrics")
async def get_portfolio_metrics():
    """Obtenir les métriques actuelles du portefeuille"""
    try:
        if USE_MOCK_MONITORING:
            # Pour le développement, utiliser des données simulées
            mock_data = get_mock_portfolio_data()
        else:
            # TODO: Remettre ici la collecte réelle via les services (history_manager, data_router, etc.)
            mock_data = get_mock_portfolio_data()  # fallback temporaire
        
        # Calculer les déviations maximales
        max_deviation = max([
            abs(asset["deviation"]) 
            for asset in mock_data["assets"].values()
        ])
        
        # Détermine le statut global
        status = "healthy"
        if max_deviation > 10:
            status = "critical"
        elif max_deviation > 5:
            status = "warning"
        
        response = {
            **mock_data,
            "max_deviation": max_deviation,
            "portfolio_status": status,
            "last_rebalance": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Sauvegarder les métriques
        save_json_file(PORTFOLIO_METRICS_FILE, response)
        
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"Error getting portfolio metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_portfolio_alerts(
    active_only: bool = Query(True, description="Retourner seulement les alertes actives"),
    limit: int = Query(20, ge=1, le=100, description="Nombre maximum d'alertes")
):
    """Obtenir les alertes de portefeuille"""
    try:
        # Générer des alertes simulées basées sur les métriques actuelles
        portfolio_data = get_mock_portfolio_data()
        alerts = []
        
        now = datetime.now(timezone.utc)
        
        # Alertes de déviation
        for asset_name, asset_data in portfolio_data["assets"].items():
            deviation = abs(asset_data["deviation"])
            if deviation > 5:
                alert_type = "critical" if deviation > 10 else "warning"
                alerts.append({
                    "id": f"deviation-{asset_name.lower()}",
                    "type": alert_type,
                    "category": "allocation_deviation",
                    "title": f"Déviation d'allocation - {asset_name}",
                    "message": f"{asset_name} dévie de {deviation:.1f}% de l'allocation cible ({asset_data['target_allocation']}%)",
                    "asset": asset_name,
                    "deviation": asset_data["deviation"],
                    "current_allocation": asset_data["current_allocation"],
                    "target_allocation": asset_data["target_allocation"],
                    "timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "resolved": False
                })
        
        # Alerte de performance si nécessaire
        if portfolio_data["change_24h"] < -10:
            alerts.append({
                "id": "performance-decline",
                "type": "warning",
                "category": "performance",
                "title": "Baisse de performance significative",
                "message": f"Le portefeuille a baissé de {abs(portfolio_data['change_24h']):.1f}% dans les dernières 24h",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "resolved": False
            })
        
        # Filtrer si seulement les alertes actives
        if active_only:
            alerts = [a for a in alerts if not a.get("resolved", False)]
        
        # Limiter le nombre d'alertes
        alerts = alerts[:limit]
        
        # Sauvegarder les alertes
        alerts_data = {
            "alerts": alerts,
            "last_updated": now.isoformat(),
            "total_active": len([a for a in alerts if not a.get("resolved", False)])
        }
        save_json_file(ALERTS_FILE, alerts_data)
        
        return JSONResponse({
            "alerts": alerts,
            "total": len(alerts),
            "active_count": len([a for a in alerts if not a.get("resolved", False)]),
            "timestamp": now.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting portfolio alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rebalance-history")
async def get_rebalance_history(
    days: int = Query(30, ge=1, le=365, description="Nombre de jours d'historique"),
    limit: int = Query(50, ge=1, le=200, description="Nombre maximum d'entrées")
):
    """Obtenir l'historique des rééquilibrages"""
    try:
        # Charger l'historique existant
        history_data = load_json_file(REBALANCE_HISTORY_FILE, {"rebalances": []})
        
        # Si pas d'historique, générer des exemples
        if not history_data.get("rebalances"):
            now = datetime.now(timezone.utc)
            mock_history = []
            
            # Générer quelques rééquilibrages simulés
            for i in range(5):
                mock_history.append({
                    "id": f"rebalance_{i+1}",
                    "timestamp": (now - timedelta(days=i*7, hours=i*2)).isoformat(),
                    "strategy": ["Conservative", "Balanced", "Aggressive", "Strategic (Dynamic)", "Macro"][i],
                    "total_value_before": 420000 + (i * 5000),
                    "total_value_after": 425000 + (i * 5000),
                    "actions_count": 3 + i,
                    "status": "completed",
                    "duration_seconds": 45 + (i * 10),
                    "assets_rebalanced": ["Bitcoin", "Ethereum", "Altcoins"][:2+i],
                    "performance_24h": [1.2, -0.8, 2.1, 0.5, -1.1][i]
                })
            
            history_data = {"rebalances": mock_history}
            save_json_file(REBALANCE_HISTORY_FILE, history_data)
        
        # Filtrer par période
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered_history = []
        
        for rebalance in history_data.get("rebalances", []):
            try:
                rebalance_time = datetime.fromisoformat(rebalance["timestamp"].replace('Z', '+00:00'))
                if rebalance_time > cutoff:
                    filtered_history.append(rebalance)
            except (ValueError, KeyError):
                continue  # Skip invalid entries
        
        # Trier par date décroissante et limiter
        filtered_history.sort(key=lambda x: x["timestamp"], reverse=True)
        filtered_history = filtered_history[:limit]
        
        # Calculer des statistiques
        if filtered_history:
            total_rebalances = len(filtered_history)
            successful_rebalances = len([r for r in filtered_history if r.get("status") == "completed"])
            avg_duration = sum([r.get("duration_seconds", 0) for r in filtered_history]) / total_rebalances
            avg_performance = sum([r.get("performance_24h", 0) for r in filtered_history]) / total_rebalances
        else:
            total_rebalances = successful_rebalances = avg_duration = avg_performance = 0
        
        return JSONResponse({
            "rebalances": filtered_history,
            "statistics": {
                "total_rebalances": total_rebalances,
                "successful_rebalances": successful_rebalances,
                "success_rate": round((successful_rebalances / total_rebalances * 100), 2) if total_rebalances > 0 else 0,
                "average_duration_seconds": round(avg_duration, 2),
                "average_performance_24h": round(avg_performance, 2)
            },
            "period_days": days,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting rebalance history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_analytics(
    period_days: int = Query(30, ge=1, le=365, description="Période d'analyse en jours")
):
    """Obtenir les analytics de performance"""
    try:
        now = datetime.now(timezone.utc)
        
        # Générer des données de performance simulées
        performance_data = []
        for i in range(period_days):
            date = now - timedelta(days=period_days - i)
            
            # Simuler une valeur de portefeuille avec tendance et volatilité
            base_value = 400000
            trend = i * 50  # Tendance légèrement haussière
            volatility = 5000 * (0.5 - (i % 7) / 7)  # Volatilité hebdomadaire
            daily_value = base_value + trend + volatility
            
            performance_data.append({
                "date": date.date().isoformat(),
                "portfolio_value": round(daily_value, 2),
                "daily_return": round(((daily_value - base_value) / base_value) * 100, 3) if i > 0 else 0,
                "benchmark_return": round((i * 0.05), 3)  # Benchmark fictif
            })
        
        # Calculer les métriques de performance
        if len(performance_data) > 1:
            total_return = ((performance_data[-1]["portfolio_value"] - performance_data[0]["portfolio_value"]) 
                          / performance_data[0]["portfolio_value"]) * 100
            
            daily_returns = [p["daily_return"] for p in performance_data[1:]]
            volatility = (sum([(r - sum(daily_returns)/len(daily_returns))**2 for r in daily_returns]) 
                         / len(daily_returns))**0.5 if daily_returns else 0
            
            max_value = max([p["portfolio_value"] for p in performance_data])
            current_value = performance_data[-1]["portfolio_value"]
            max_drawdown = ((max_value - current_value) / max_value) * 100 if max_value > 0 else 0
            
            avg_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
            sharpe_ratio = (avg_return / volatility) if volatility > 0 else 0
        else:
            total_return = volatility = max_drawdown = sharpe_ratio = 0
        
        metrics = {
            "total_return": round(total_return, 2),
            "volatility": round(volatility, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "best_day": round(max(daily_returns, default=0), 2),
            "worst_day": round(min(daily_returns, default=0), 2)
        }
        
        return JSONResponse({
            "performance_data": performance_data,
            "metrics": metrics,
            "period_days": period_days,
            "timestamp": now.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REMOVED: Duplicate alert resolution endpoint - use /api/alerts/resolve/{alert_id} instead
# Alert management should be centralized in alerts_endpoints.py

@router.get("/strategy-performance")
async def get_strategy_performance(
    days: int = Query(90, ge=7, le=365, description="Période d'analyse en jours")
):
    """Analyser les performances par stratégie de rééquilibrage"""
    try:
        # Charger l'historique des rééquilibrages
        history_data = load_json_file(REBALANCE_HISTORY_FILE, {"rebalances": []})
        rebalances = history_data.get("rebalances", [])
        
        if not rebalances:
            return JSONResponse({
                "message": "No rebalancing history available",
                "strategies": {},
                "period_days": days
            })
        
        # Filtrer par période
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered_rebalances = []
        
        for rebalance in rebalances:
            try:
                rebalance_time = datetime.fromisoformat(rebalance["timestamp"].replace('Z', '+00:00'))
                if rebalance_time > cutoff:
                    filtered_rebalances.append(rebalance)
            except (ValueError, KeyError):
                continue
        
        # Analyser par stratégie
        strategy_stats = {}
        for rebalance in filtered_rebalances:
            strategy = rebalance.get("strategy", "Unknown")
            
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    "total_rebalances": 0,
                    "successful_rebalances": 0,
                    "total_duration": 0,
                    "performance_24h_sum": 0,
                    "performance_values": []
                }
            
            stats = strategy_stats[strategy]
            stats["total_rebalances"] += 1
            
            if rebalance.get("status") == "completed":
                stats["successful_rebalances"] += 1
            
            stats["total_duration"] += rebalance.get("duration_seconds", 0)
            
            perf = rebalance.get("performance_24h", 0)
            stats["performance_24h_sum"] += perf
            stats["performance_values"].append(perf)
        
        # Calculer les métriques finales pour chaque stratégie
        for strategy, stats in strategy_stats.items():
            total = stats["total_rebalances"]
            if total > 0:
                stats["success_rate"] = round((stats["successful_rebalances"] / total) * 100, 2)
                stats["avg_duration"] = round(stats["total_duration"] / total, 2)
                stats["avg_performance_24h"] = round(stats["performance_24h_sum"] / total, 2)
                
                # Calculer volatilité des performances
                performances = stats["performance_values"]
                if len(performances) > 1:
                    avg_perf = stats["avg_performance_24h"]
                    variance = sum([(p - avg_perf)**2 for p in performances]) / len(performances)
                    stats["performance_volatility"] = round(variance**0.5, 2)
                else:
                    stats["performance_volatility"] = 0
                
                # Score de qualité composite
                quality_score = (
                    (stats["success_rate"] / 100) * 0.4 +  # 40% pour le taux de succès
                    max(0, min(1, stats["avg_performance_24h"] / 5)) * 0.4 +  # 40% pour la performance
                    max(0, min(1, 1 - stats["performance_volatility"] / 10)) * 0.2  # 20% pour la stabilité
                )
                stats["quality_score"] = round(quality_score * 100, 1)
            
            # Nettoyer les données temporaires
            del stats["performance_24h_sum"]
            del stats["total_duration"]
            del stats["performance_values"]
        
        return JSONResponse({
            "strategies": strategy_stats,
            "period_days": days,
            "total_rebalances_analyzed": len(filtered_rebalances),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-summary")
async def get_dashboard_summary():
    """Résumé complet pour le dashboard de monitoring"""
    try:
        # Obtenir toutes les données nécessaires
        portfolio_data = get_mock_portfolio_data()
        
        # Alertes actives
        alerts_data = load_json_file(ALERTS_FILE, {"alerts": []})
        active_alerts = [a for a in alerts_data.get("alerts", []) if not a.get("resolved", False)]
        
        # Historique récent des rééquilibrages
        history_data = load_json_file(REBALANCE_HISTORY_FILE, {"rebalances": []})
        recent_rebalances = sorted(
            history_data.get("rebalances", []),
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:5]
        
        # Statut global
        max_deviation = max([abs(asset["deviation"]) for asset in portfolio_data["assets"].values()])
        
        global_status = "healthy"
        if len(active_alerts) > 2 or max_deviation > 10:
            global_status = "critical"
        elif len(active_alerts) > 0 or max_deviation > 5:
            global_status = "warning"
        
        return JSONResponse({
            "global_status": global_status,
            "portfolio": {
                "total_value": portfolio_data["total_value"],
                "change_24h": portfolio_data["change_24h"],
                "max_deviation": max_deviation,
                "last_update": portfolio_data["last_update"]
            },
            "alerts": {
                "active_count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a.get("type") == "critical"]),
                "latest": active_alerts[:3]  # Dernières 3 alertes
            },
            "rebalancing": {
                "last_rebalance": recent_rebalances[0] if recent_rebalances else None,
                "recent_count": len(recent_rebalances),
                "success_rate": round(
                    len([r for r in recent_rebalances if r.get("status") == "completed"]) / len(recent_rebalances) * 100, 1
                ) if recent_rebalances else 0
            },
            "system": {
                "monitoring_active": True,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "uptime": "99.2%"  # Simulé
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))