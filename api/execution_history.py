#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Execution History - Endpoints pour l'historique et analytics des exécutions

Ce module fournit les endpoints API pour:
- Consulter l'historique des exécutions
- Analytics de performance et coûts
- Visualisations et tendances
- Export de données
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone, timedelta
import json
import io

from services.analytics.execution_history import execution_history
from services.execution.exchange_adapter import exchange_registry

logger = logging.getLogger(__name__)

# Router pour les endpoints execution history
router = APIRouter(prefix="/api/execution/history", tags=["execution-history"])

@router.get("/sessions")
async def get_recent_sessions(
    limit: int = Query(50, ge=1, le=500, description="Number of sessions to return"),
    exchange: Optional[str] = Query(None, description="Filter by exchange"),
    days: int = Query(7, ge=1, le=90, description="Days of history to include")
):
    """Obtenir l'historique des sessions d'exécution"""
    try:
        # Retourner des données simulées pour le développement
        mock_sessions = [
            {
                "id": f"session_{i}",
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                "exchange": "binance" if i % 2 == 0 else "kraken",
                "total_orders": 5 + (i % 10),
                "successful_orders": 4 + (i % 8),
                "failed_orders": i % 3,
                "total_volume_usd": 1000 + (i * 250),
                "total_fees": 2.5 + (i * 0.1),
                "avg_slippage_bps": 15 + (i % 20),
                "avg_execution_time_ms": 150 + (i * 10)
            }
            for i in range(min(limit, 20))
        ]
        
        sessions = mock_sessions
        #sessions = execution_history.get_recent_sessions(limit=limit, exchange=exchange)
        
        # Filtrer par période si spécifié
        if days < 7:  # Si moins de 7 jours, filtrer plus précisément
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            sessions = [
                s for s in sessions 
                if datetime.fromisoformat(s["timestamp"].replace('Z', '+00:00')) > cutoff
            ]
        
        # Statistiques rapides
        if sessions:
            total_volume = sum(s.get("total_volume_usd", 0) for s in sessions)
            total_fees = sum(s.get("total_fees", 0) for s in sessions)
            avg_success_rate = sum(
                (s.get("successful_orders", 0) / s.get("total_orders", 1) * 100) 
                for s in sessions
            ) / len(sessions)
        else:
            total_volume = total_fees = avg_success_rate = 0
        
        return JSONResponse({
            "sessions": sessions,
            "metadata": {
                "total_returned": len(sessions),
                "limit": limit,
                "exchange_filter": exchange,
                "period_days": days,
                "quick_stats": {
                    "total_volume_usd": total_volume,
                    "total_fees": total_fees,
                    "avg_success_rate": avg_success_rate
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting recent sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Obtenir les détails complets d'une session"""
    try:
        session = execution_history.get_session_by_id(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Enrichir avec des analytics spécifiques à la session
        orders = session.get("orders", [])
        successful_orders = [o for o in orders if o.get("status") == "success"]
        failed_orders = [o for o in orders if o.get("status") in ["failed", "error", "rejected"]]
        
        # Répartition par symbole
        symbol_breakdown = {}
        for order in successful_orders:
            symbol = order.get("symbol", "Unknown")
            if symbol not in symbol_breakdown:
                symbol_breakdown[symbol] = {
                    "count": 0,
                    "volume": 0,
                    "fees": 0,
                    "avg_price": 0
                }
            
            symbol_breakdown[symbol]["count"] += 1
            symbol_breakdown[symbol]["volume"] += float(order.get("filled_usd", 0))
            symbol_breakdown[symbol]["fees"] += float(order.get("fees", 0))
            
            # Prix moyen pondéré
            if order.get("avg_price"):
                symbol_breakdown[symbol]["avg_price"] = order.get("avg_price")
        
        # Coûts détaillés
        total_fees = sum(float(o.get("fees", 0)) for o in successful_orders)
        total_volume = sum(float(o.get("filled_usd", 0)) for o in successful_orders)
        
        # Estimation du slippage cost
        avg_slippage_bps = session.get("avg_slippage_bps", 0)
        slippage_cost = total_volume * (avg_slippage_bps / 10000) if avg_slippage_bps > 0 else 0
        
        enhanced_session = {
            **session,
            "analytics": {
                "symbol_breakdown": symbol_breakdown,
                "cost_analysis": {
                    "trading_fees": total_fees,
                    "slippage_cost": slippage_cost,
                    "total_cost": total_fees + slippage_cost,
                    "cost_percentage": ((total_fees + slippage_cost) / total_volume * 100) if total_volume > 0 else 0
                },
                "timing_analysis": {
                    "successful_orders": len(successful_orders),
                    "failed_orders": len(failed_orders),
                    "success_rate": (len(successful_orders) / len(orders) * 100) if orders else 0,
                    "avg_order_size": total_volume / len(successful_orders) if successful_orders else 0
                }
            }
        }
        
        return JSONResponse(enhanced_session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance")
async def get_performance_metrics(
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    exchange: Optional[str] = Query(None, description="Filter by specific exchange")
):
    """Obtenir les métriques de performance sur une période"""
    try:
        # Données simulées pour le développement
        mock_metrics = {
            "period_days": period_days,
            "total_sessions": 45 + (period_days // 10),
            "avg_success_rate": 91.2,
            "total_volume_usd": 25000 + (period_days * 100),
            "total_fees": 85.4,
            "avg_slippage_bps": 22.5,
            "avg_execution_time_ms": 180.2
        }
        
        metrics = mock_metrics
        
        # Code original commenté pour le développement  
        # metrics = await execution_history.get_performance_metrics(
        #     period_days=period_days, 
        #     exchange=exchange
        # )
        
        # Ajouter des benchmarks et ratings
        performance_rating = "excellent"
        recommendations = []
        
        if metrics["avg_success_rate"] < 90:
            performance_rating = "needs_improvement"
            recommendations.append("Consider reviewing order validation logic")
            
        if metrics["avg_slippage_bps"] > 100:  # > 1%
            recommendations.append("High slippage detected - consider smaller order sizes")
            
        if metrics["total_fees"] / metrics["total_volume_usd"] > 0.01:  # > 1%
            recommendations.append("Consider optimizing for lower fee structures")
        
        enhanced_metrics = {
            **metrics,
            "performance_rating": performance_rating,
            "recommendations": recommendations,
            "benchmarks": {
                "target_success_rate": 95.0,
                "target_slippage_bps": 50.0,
                "target_fee_ratio": 0.005  # 0.5%
            }
        }
        
        return JSONResponse(enhanced_metrics)
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends")
async def get_execution_trends(
    days: int = Query(30, ge=7, le=90, description="Period for trend analysis"),
    interval: str = Query("daily", regex="^(hourly|daily|weekly)$", description="Aggregation interval"),
    exchange: Optional[str] = Query(None, description="Filter by exchange")
):
    """Analyser les tendances d'exécution"""
    try:
        # Appliquer le filtrage par exchange si spécifié
        trends = await execution_history.get_execution_trends(
            days=days, 
            interval=interval, 
            exchange_filter=exchange
        )
        
        if "error" in trends:
            raise HTTPException(status_code=500, detail=trends["error"])
        
        # Ajouter des insights automatiques
        insights = []
        
        if "trends" in trends:
            trend_data = trends["trends"]
            
            if trend_data.get("volume_trend") == "increasing":
                insights.append("📈 Trading volume is increasing - good activity level")
            elif trend_data.get("volume_trend") == "decreasing":
                insights.append("📉 Trading volume is decreasing - consider market conditions")
            
            if trend_data.get("success_trend") == "improving":
                insights.append("✅ Success rate is improving - execution quality getting better")
            elif trend_data.get("success_trend") == "degrading":
                insights.append("⚠️ Success rate is degrading - review execution strategy")
                
            overall_success = trend_data.get("overall_success_rate", 0)
            if overall_success >= 95:
                insights.append("🎯 Excellent overall success rate")
            elif overall_success >= 90:
                insights.append("👍 Good overall success rate")
            else:
                insights.append("🔧 Success rate needs improvement")
        
        enhanced_trends = {
            **trends,
            "insights": insights,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return JSONResponse(enhanced_trends)
        
    except Exception as e:
        logger.error(f"Error getting execution trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_execution_statistics():
    """Obtenir les statistiques générales d'exécution"""
    try:
        stats = execution_history.get_statistics_summary()
        
        # Enrichir avec informations système
        enhanced_stats = {
            **stats,
            "system_info": {
                "available_exchanges": list(exchange_registry.adapters.keys()) if exchange_registry.adapters else [],
                "cache_status": "active" if execution_history.recent_sessions else "empty",
                "retention_policy": f"{execution_history.analytics_config['retention_days']} days",
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return JSONResponse(enhanced_stats)
        
    except Exception as e:
        logger.error(f"Error getting execution statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/sessions")
async def export_sessions_csv(
    days: int = Query(30, ge=1, le=365, description="Days of history to export"),
    exchange: Optional[str] = Query(None, description="Filter by exchange")
):
    """Exporter l'historique des sessions en CSV"""
    try:
        sessions = execution_history.get_recent_sessions(limit=1000, exchange=exchange)
        
        # Filtrer par période
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered_sessions = [
            s for s in sessions 
            if datetime.fromisoformat(s["timestamp"].replace('Z', '+00:00')) > cutoff
        ]
        
        # Générer CSV
        csv_lines = [
            "session_id,timestamp,exchange,total_orders,successful_orders,failed_orders,success_rate,total_volume_usd,total_fees,avg_slippage_bps,avg_execution_time_ms"
        ]
        
        for session in filtered_sessions:
            success_rate = (session.get("successful_orders", 0) / session.get("total_orders", 1) * 100) if session.get("total_orders", 0) > 0 else 0
            
            csv_lines.append(
                f"{session.get('id', '')},{session.get('timestamp', '')},"
                f"{session.get('exchange', '')},{session.get('total_orders', 0)},"
                f"{session.get('successful_orders', 0)},{session.get('failed_orders', 0)},"
                f"{success_rate:.2f},{session.get('total_volume_usd', 0):.2f},"
                f"{session.get('total_fees', 0):.4f},{session.get('avg_slippage_bps', 0):.2f},"
                f"{session.get('avg_execution_time_ms', 0):.2f}"
            )
        
        csv_content = "\n".join(csv_lines)
        
        # Créer la réponse streaming
        def generate_csv():
            yield csv_content
        
        filename = f"execution_sessions_{days}days_{datetime.now().strftime('%Y%m%d')}.csv"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers=headers
        )
        
    except Exception as e:
        logger.error(f"Error exporting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/record")
async def record_execution_session(
    session_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Enregistrer une nouvelle session d'exécution (usage interne)"""
    try:
        orders = session_data.get("orders", [])
        exchange = session_data.get("exchange", "unknown")
        metadata = session_data.get("metadata", {})
        
        if not orders:
            raise HTTPException(status_code=400, detail="No orders provided")
        
        # Enregistrer en arrière-plan
        background_tasks.add_task(
            execution_history.record_execution_session,
            orders, exchange, metadata
        )
        
        return JSONResponse({
            "message": "Session recording initiated",
            "orders_count": len(orders),
            "exchange": exchange,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-data")
async def get_dashboard_data():
    """Obtenir toutes les données nécessaires pour le dashboard d'historique"""
    try:
        # Données simulées pour le développement
        mock_recent_sessions = [
            {
                "id": f"session_{i}",
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=i*2)).isoformat(),
                "exchange": "binance" if i % 2 == 0 else "kraken",
                "total_orders": 5 + (i % 8),
                "successful_orders": 4 + (i % 7),
                "failed_orders": i % 2,
                "total_volume_usd": 1500 + (i * 300),
                "total_fees": 3.2 + (i * 0.15),
                "avg_slippage_bps": 12 + (i % 25),
                "avg_execution_time_ms": 140 + (i * 15)
            }
            for i in range(10)
        ]
        
        mock_stats = {
            "total_sessions": 245,
            "total_successful_sessions": 220,
            "total_failed_sessions": 25,
            "overall_success_rate": 89.8,
            "total_volume_usd": 125000,
            "total_fees": 420.5,
            "avg_session_time": 45.2
        }
        
        mock_metrics_7d = {
            "period_days": 7,
            "total_sessions": 28,
            "avg_success_rate": 92.5,
            "total_volume_usd": 15000,
            "total_fees": 52.3,
            "avg_slippage_bps": 18.5
        }
        
        mock_metrics_30d = {
            "period_days": 30,
            "total_sessions": 120,
            "avg_success_rate": 90.1,
            "total_volume_usd": 65000,
            "total_fees": 215.8,
            "avg_slippage_bps": 22.1
        }
        
        mock_trends = {
            "trends": {
                "volume_trend": "increasing",
                "success_trend": "improving", 
                "overall_success_rate": 91.2
            },
            "daily_metrics": []
        }
        
        recent_sessions = mock_recent_sessions
        stats = mock_stats
        metrics_7d = mock_metrics_7d
        metrics_30d = mock_metrics_30d  
        trends = mock_trends
        
        # Code original commenté pour le développement
        # recent_sessions = execution_history.get_recent_sessions(limit=20)
        # stats = execution_history.get_statistics_summary()
        # metrics_7d = await execution_history.get_performance_metrics(period_days=7)
        # metrics_30d = await execution_history.get_performance_metrics(period_days=30)
        # trends = await execution_history.get_execution_trends(days=14, interval="daily")
        
        dashboard_data = {
            "recent_sessions": recent_sessions[:10],  # Dernières 10 sessions
            "statistics": stats,
            "performance": {
                "last_7_days": metrics_7d,
                "last_30_days": metrics_30d
            },
            "trends": trends,
            "refresh_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return JSONResponse(dashboard_data)
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_data(background_tasks: BackgroundTasks):
    """Nettoyer les anciennes données (maintenance)"""
    try:
        background_tasks.add_task(execution_history.cleanup_old_data)
        
        return JSONResponse({
            "message": "Cleanup initiated",
            "retention_days": execution_history.analytics_config["retention_days"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error initiating cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))