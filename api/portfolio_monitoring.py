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

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
import os
import logging
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

# Import services pour données réelles
from services.portfolio import portfolio_analytics

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

async def get_real_portfolio_data(source: str = "cointracking", user_id: str = "demo") -> Dict[str, Any]:
    """
    Récupérer les vraies données de portefeuille via les services

    Args:
        source: Source de données (cointracking, cointracking_api, etc.)
        user_id: ID utilisateur pour isolation multi-tenant

    Returns:
        Dict avec métriques de portfolio réelles
    """
    try:
        # Import local pour éviter imports circulaires
        from api.main import resolve_current_balances
        from api.services.utils import to_rows

        # 1. Récupérer les balances actuelles
        res = await resolve_current_balances(source=source, user_id=user_id)
        items = res.get("items", [])

        if not items:
            logger.warning(f"No portfolio items found for user={user_id}, source={source}")
            return _get_empty_portfolio_data()

        # 2. Calculer métriques de base avec portfolio_analytics
        balances_data = {"items": items}
        metrics = portfolio_analytics.calculate_portfolio_metrics(balances_data)

        # 3. Calculer métriques de performance (P&L)
        perf_metrics = portfolio_analytics.calculate_performance_metrics(
            current_data=metrics,
            user_id=user_id,
            source=source,
            anchor="prev_snapshot",
            window="24h"
        )

        perf_metrics_7d = portfolio_analytics.calculate_performance_metrics(
            current_data=metrics,
            user_id=user_id,
            source=source,
            anchor="prev_snapshot",
            window="7d"
        )

        # 4. Construire structure par asset avec allocations
        total_value = metrics["total_value_usd"]
        assets_by_group = {}

        for item in items:
            group = item.get("group", "Others")
            value = item.get("value_usd", 0) or item.get("usd_value", 0)

            if group not in assets_by_group:
                assets_by_group[group] = {
                    "current_allocation": 0.0,
                    "target_allocation": 0.0,  # TODO: Récupérer depuis config user
                    "deviation": 0.0,
                    "value_usd": 0.0,
                    "change_24h": 0.0  # TODO: Calculer depuis historique prix
                }

            assets_by_group[group]["value_usd"] += value

        # Calculer allocations en %
        for group, data in assets_by_group.items():
            data["current_allocation"] = (data["value_usd"] / total_value * 100) if total_value > 0 else 0
            # Pour l'instant, target = current (pas de système de targets configurables)
            # TODO: Récupérer targets depuis Strategy API ou config user
            data["target_allocation"] = data["current_allocation"]
            data["deviation"] = data["current_allocation"] - data["target_allocation"]

        # 5. Métriques de performance globales
        change_24h = perf_metrics.get("percentage_change", 0.0) if perf_metrics.get("performance_available") else 0.0
        change_7d = perf_metrics_7d.get("percentage_change", 0.0) if perf_metrics_7d.get("performance_available") else 0.0

        # 6. Retourner structure compatible
        return {
            "total_value": total_value,
            "change_24h": change_24h,
            "change_7d": change_7d,
            "last_update": datetime.now(timezone.utc).isoformat(),
            "assets": assets_by_group,
            "performance_metrics": {
                "sharpe_ratio": 0.0,  # TODO: Calculer depuis risk_manager
                "max_drawdown": 0.0,  # TODO: Calculer depuis historique
                "volatility": 0.0,    # TODO: Calculer depuis historique
                "total_return_7d": change_7d,
                "total_return_30d": 0.0  # TODO: Calculer
            },
            "metadata": {
                "source": source,
                "user_id": user_id,
                "asset_count": metrics["asset_count"],
                "group_count": metrics["group_count"],
                "diversity_score": metrics["diversity_score"]
            }
        }

    except Exception as e:
        logger.error(f"Error fetching real portfolio data for user={user_id}, source={source}: {e}")
        # Fallback sur données vides plutôt que mock
        return _get_empty_portfolio_data()


def _get_empty_portfolio_data() -> Dict[str, Any]:
    """Retourne une structure de portfolio vide"""
    return {
        "total_value": 0.0,
        "change_24h": 0.0,
        "change_7d": 0.0,
        "last_update": datetime.now(timezone.utc).isoformat(),
        "assets": {},
        "performance_metrics": {
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "total_return_7d": 0.0,
            "total_return_30d": 0.0
        },
        "metadata": {
            "source": "none",
            "user_id": "unknown",
            "asset_count": 0,
            "group_count": 0,
            "diversity_score": 0
        }
    }


def get_mock_portfolio_data():
    """
    DEPRECATED: Générer des données de portefeuille simulées pour développement
    Utilisé uniquement comme fallback si USE_MOCK_MONITORING=true
    """
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
async def get_portfolio_metrics(
    source: str = Query("cointracking", description="Source de données (cointracking, cointracking_api, etc.)"),
    user_id: str = Query("demo", description="ID utilisateur pour isolation multi-tenant")
):
    """
    Obtenir les métriques actuelles du portefeuille

    Args:
        source: Source de données (cointracking, cointracking_api, saxobank, etc.)
        user_id: ID utilisateur (demo, jack, donato, etc.)

    Returns:
        Métriques complètes du portfolio avec allocations et déviations
    """
    try:
        # Récupérer les vraies données ou mock selon config
        if USE_MOCK_MONITORING:
            logger.info("Using MOCK data for portfolio metrics (USE_MOCK_MONITORING=true)")
            portfolio_data = get_mock_portfolio_data()
        else:
            logger.info(f"Using REAL data for portfolio metrics (user={user_id}, source={source})")
            portfolio_data = await get_real_portfolio_data(source=source, user_id=user_id)

        # Calculer les déviations maximales
        if portfolio_data["assets"]:
            max_deviation = max([
                abs(asset["deviation"])
                for asset in portfolio_data["assets"].values()
            ])
        else:
            max_deviation = 0.0

        # Détermine le statut global
        status = "healthy"
        if max_deviation > 10:
            status = "critical"
        elif max_deviation > 5:
            status = "warning"

        response = {
            **portfolio_data,
            "max_deviation": max_deviation,
            "portfolio_status": status,
            "last_rebalance": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),  # TODO: Récupérer vraie dernière rebal
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Sauvegarder les métriques
        save_json_file(PORTFOLIO_METRICS_FILE, response)

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Error getting portfolio metrics for user={user_id}, source={source}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts")
async def get_portfolio_alerts(
    source: str = Query("cointracking", description="Source de données"),
    user_id: str = Query("demo", description="ID utilisateur"),
    active_only: bool = Query(True, description="Retourner seulement les alertes actives"),
    limit: int = Query(20, ge=1, le=100, description="Nombre maximum d'alertes")
):
    """
    Obtenir les alertes de portefeuille basées sur les vraies déviations d'allocation

    Args:
        source: Source de données
        user_id: ID utilisateur
        active_only: Retourner seulement les alertes actives
        limit: Nombre maximum d'alertes à retourner

    Returns:
        Liste d'alertes avec déviations, performance, etc.
    """
    try:
        # Récupérer les données réelles ou mock
        if USE_MOCK_MONITORING:
            portfolio_data = get_mock_portfolio_data()
        else:
            portfolio_data = await get_real_portfolio_data(source=source, user_id=user_id)

        alerts = []
        now = datetime.now(timezone.utc)

        # Alertes de déviation d'allocation
        for asset_name, asset_data in portfolio_data["assets"].items():
            deviation = abs(asset_data["deviation"])
            if deviation > 5:  # Seuil de 5% pour générer une alerte
                alert_type = "critical" if deviation > 10 else "warning"
                alerts.append({
                    "id": f"deviation-{asset_name.lower()}-{user_id}",
                    "type": alert_type,
                    "category": "allocation_deviation",
                    "title": f"Déviation d'allocation - {asset_name}",
                    "message": f"{asset_name} dévie de {deviation:.1f}% de l'allocation cible ({asset_data['target_allocation']:.1f}%)",
                    "asset": asset_name,
                    "deviation": asset_data["deviation"],
                    "current_allocation": asset_data["current_allocation"],
                    "target_allocation": asset_data["target_allocation"],
                    "timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "resolved": False,
                    "user_id": user_id,
                    "source": source
                })

        # Alerte de performance si baisse significative
        if portfolio_data["change_24h"] < -10:
            alerts.append({
                "id": f"performance-decline-{user_id}",
                "type": "warning",
                "category": "performance",
                "title": "Baisse de performance significative",
                "message": f"Le portefeuille a baissé de {abs(portfolio_data['change_24h']):.1f}% dans les dernières 24h",
                "timestamp": (now - timedelta(hours=1)).isoformat(),
                "resolved": False,
                "user_id": user_id,
                "source": source
            })

        # Alerte de hausse exceptionnelle
        if portfolio_data["change_24h"] > 15:
            alerts.append({
                "id": f"performance-surge-{user_id}",
                "type": "info",
                "category": "performance",
                "title": "Hausse de performance exceptionnelle",
                "message": f"Le portefeuille a progressé de {portfolio_data['change_24h']:.1f}% dans les dernières 24h",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
                "resolved": False,
                "user_id": user_id,
                "source": source
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
            "total_active": len([a for a in alerts if not a.get("resolved", False)]),
            "user_id": user_id,
            "source": source
        }
        save_json_file(ALERTS_FILE, alerts_data)

        return JSONResponse({
            "alerts": alerts,
            "total": len(alerts),
            "active_count": len([a for a in alerts if not a.get("resolved", False)]),
            "timestamp": now.isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting portfolio alerts for user={user_id}, source={source}: {e}")
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
    source: str = Query("cointracking", description="Source de données"),
    user_id: str = Query("demo", description="ID utilisateur"),
    period_days: int = Query(30, ge=1, le=365, description="Période d'analyse en jours")
):
    """
    Obtenir les analytics de performance basés sur l'historique réel du portfolio

    Args:
        source: Source de données
        user_id: ID utilisateur
        period_days: Nombre de jours d'historique à analyser

    Returns:
        Données de performance avec métriques calculées depuis snapshots historiques
    """
    try:
        now = datetime.now(timezone.utc)

        # Charger l'historique réel du portfolio
        historical_data = portfolio_analytics._load_historical_data(user_id=user_id, source=source)

        if not historical_data:
            # Pas de données historiques disponibles
            return JSONResponse({
                "performance_data": [],
                "metrics": {
                    "total_return": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "best_day": 0.0,
                    "worst_day": 0.0
                },
                "period_days": period_days,
                "message": f"Pas de données historiques disponibles pour user={user_id}, source={source}",
                "timestamp": now.isoformat()
            })

        # Filtrer les derniers X jours
        cutoff_date = now - timedelta(days=period_days)
        filtered_data = [
            entry for entry in historical_data
            if datetime.fromisoformat(entry.get("date", "")) >= cutoff_date
        ]

        if len(filtered_data) < 2:
            return JSONResponse({
                "performance_data": [],
                "metrics": {
                    "total_return": 0.0,
                    "volatility": 0.0,
                    "max_drawdown": 0.0,
                    "sharpe_ratio": 0.0,
                    "best_day": 0.0,
                    "worst_day": 0.0
                },
                "period_days": period_days,
                "message": f"Pas assez de données historiques (minimum 2 snapshots requis, trouvé {len(filtered_data)})",
                "timestamp": now.isoformat()
            })

        # Construire les données de performance
        performance_data = []
        daily_returns = []
        max_value_seen = 0.0
        drawdowns = []

        for i, entry in enumerate(filtered_data):
            value = entry.get("total_value_usd", 0.0)
            date_str = entry.get("date", "")

            # Calculer le return quotidien
            if i > 0:
                prev_value = filtered_data[i-1].get("total_value_usd", 0.0)
                if prev_value > 0:
                    daily_return = ((value - prev_value) / prev_value) * 100
                    daily_returns.append(daily_return)
                else:
                    daily_return = 0.0
            else:
                daily_return = 0.0

            # Calculer le drawdown actuel
            max_value_seen = max(max_value_seen, value)
            if max_value_seen > 0:
                drawdown = ((max_value_seen - value) / max_value_seen) * 100
                drawdowns.append(drawdown)

            performance_data.append({
                "date": datetime.fromisoformat(date_str).date().isoformat(),
                "portfolio_value": round(value, 2),
                "daily_return": round(daily_return, 3),
                "drawdown": round(drawdown if i > 0 else 0.0, 3)
            })

        # Calculer les métriques globales
        if len(filtered_data) > 1:
            first_value = filtered_data[0].get("total_value_usd", 0.0)
            last_value = filtered_data[-1].get("total_value_usd", 0.0)

            total_return = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0.0

            # Volatilité (écart-type des returns quotidiens)
            if len(daily_returns) > 1:
                avg_return = sum(daily_returns) / len(daily_returns)
                variance = sum([(r - avg_return)**2 for r in daily_returns]) / len(daily_returns)
                volatility = variance**0.5
                # Annualiser la volatilité (sqrt(365))
                volatility_annualized = volatility * (365**0.5)
            else:
                avg_return = 0.0
                volatility = 0.0
                volatility_annualized = 0.0

            # Max drawdown
            max_drawdown = max(drawdowns) if drawdowns else 0.0

            # Sharpe ratio simplifié (assume risk-free rate = 0)
            if volatility > 0:
                sharpe_ratio = avg_return / volatility
            else:
                sharpe_ratio = 0.0

            best_day = max(daily_returns, default=0.0)
            worst_day = min(daily_returns, default=0.0)
        else:
            total_return = volatility = volatility_annualized = max_drawdown = sharpe_ratio = 0.0
            best_day = worst_day = 0.0

        metrics = {
            "total_return": round(total_return, 2),
            "volatility": round(volatility, 2),
            "volatility_annualized": round(volatility_annualized, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "best_day": round(best_day, 2),
            "worst_day": round(worst_day, 2),
            "data_points": len(filtered_data)
        }

        return JSONResponse({
            "performance_data": performance_data,
            "metrics": metrics,
            "period_days": period_days,
            "timestamp": now.isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting performance analytics for user={user_id}, source={source}: {e}")
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
async def get_dashboard_summary(
    source: str = Query("cointracking", description="Source de données"),
    user_id: str = Query("demo", description="ID utilisateur")
):
    """
    Résumé complet pour le dashboard de monitoring

    Args:
        source: Source de données
        user_id: ID utilisateur

    Returns:
        Vue agrégée du statut global, portfolio, alertes, rebalancing
    """
    try:
        # Obtenir les données réelles du portfolio
        if USE_MOCK_MONITORING:
            portfolio_data = get_mock_portfolio_data()
        else:
            portfolio_data = await get_real_portfolio_data(source=source, user_id=user_id)

        # Alertes actives pour cet utilisateur
        alerts_data = load_json_file(ALERTS_FILE, {"alerts": []})
        active_alerts = [
            a for a in alerts_data.get("alerts", [])
            if not a.get("resolved", False)
            and a.get("user_id") == user_id
            and a.get("source") == source
        ]

        # Historique récent des rééquilibrages
        history_data = load_json_file(REBALANCE_HISTORY_FILE, {"rebalances": []})
        recent_rebalances = sorted(
            history_data.get("rebalances", []),
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )[:5]

        # Statut global basé sur déviations et alertes
        if portfolio_data["assets"]:
            max_deviation = max([abs(asset["deviation"]) for asset in portfolio_data["assets"].values()])
        else:
            max_deviation = 0.0

        global_status = "healthy"
        if len(active_alerts) > 2 or max_deviation > 10:
            global_status = "critical"
        elif len(active_alerts) > 0 or max_deviation > 5:
            global_status = "warning"

        # Métriques de performance si disponibles
        perf_available = portfolio_data.get("metadata", {}).get("asset_count", 0) > 0

        return JSONResponse({
            "global_status": global_status,
            "portfolio": {
                "total_value": portfolio_data["total_value"],
                "change_24h": portfolio_data["change_24h"],
                "change_7d": portfolio_data["change_7d"],
                "max_deviation": max_deviation,
                "last_update": portfolio_data["last_update"],
                "asset_count": portfolio_data.get("metadata", {}).get("asset_count", 0),
                "diversity_score": portfolio_data.get("metadata", {}).get("diversity_score", 0)
            },
            "alerts": {
                "active_count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a.get("type") == "critical"]),
                "warning_count": len([a for a in active_alerts if a.get("type") == "warning"]),
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
                "data_source": source,
                "user_id": user_id,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "performance_available": perf_available
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting dashboard summary for user={user_id}, source={source}: {e}")
        raise HTTPException(status_code=500, detail=str(e))