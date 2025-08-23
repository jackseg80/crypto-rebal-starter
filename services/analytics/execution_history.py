#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execution History Service - Gestion historique et analytics des exécutions

Ce module gère l'historique complet des exécutions avec:
- Persistance des sessions d'exécution
- Analytics de performance et coûts
- Visualisations et tendances
- Export de données et reporting
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class ExecutionSession:
    """Session d'exécution complète"""
    id: str
    timestamp: str
    exchange: str
    total_orders: int
    successful_orders: int
    failed_orders: int
    total_volume_usd: float
    total_fees: float
    avg_slippage_bps: float
    avg_execution_time_ms: float
    orders: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @property
    def success_rate(self) -> float:
        return (self.successful_orders / self.total_orders * 100) if self.total_orders > 0 else 0
    
    @property
    def avg_order_size_usd(self) -> float:
        return self.total_volume_usd / self.successful_orders if self.successful_orders > 0 else 0

@dataclass
class PerformanceMetrics:
    """Métriques de performance agrégées"""
    period_start: str
    period_end: str
    total_sessions: int
    total_orders: int
    total_volume_usd: float
    total_fees: float
    avg_success_rate: float
    avg_execution_time: float
    avg_slippage_bps: float
    exchanges_used: List[str]
    top_symbols: List[Dict[str, Any]]
    cost_breakdown: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ExecutionHistoryService:
    """Service de gestion de l'historique d'exécution"""
    
    def __init__(self):
        self.storage_path = Path("data/execution_history")
        self.storage_path.mkdir(exist_ok=True)
        
        # Cache en mémoire pour les données récentes
        self.recent_sessions: List[ExecutionSession] = []
        self.cache_duration_hours = 24
        
        # Configuration analytics
        self.analytics_config = {
            "retention_days": 90,
            "aggregation_intervals": ["1d", "7d", "30d"],
            "performance_thresholds": {
                "excellent_success_rate": 95.0,
                "good_success_rate": 90.0,
                "acceptable_slippage": 50.0,  # bps
                "fast_execution": 1000.0,     # ms
            }
        }
        
        # Charger les sessions récentes au démarrage
        self._load_recent_sessions()
        
    def _load_recent_sessions(self):
        """Charger les sessions récentes en mémoire"""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.cache_duration_hours)
            
            # Lister les fichiers de session des dernières 48h
            for day_offset in range(3):  # 3 jours pour être sûr
                date = datetime.now() - timedelta(days=day_offset)
                date_str = date.strftime("%Y-%m-%d")
                session_file = self.storage_path / f"sessions_{date_str}.json"
                
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            daily_sessions = json.load(f)
                        
                        for session_data in daily_sessions:
                            session_time = datetime.fromisoformat(session_data["timestamp"].replace('Z', '+00:00'))
                            if session_time > cutoff:
                                session = ExecutionSession(**session_data)
                                self.recent_sessions.append(session)
                                
                    except Exception as e:
                        logger.warning(f"Error loading session file {session_file}: {e}")
                        
            # Trier par timestamp décroissant
            self.recent_sessions.sort(key=lambda x: x.timestamp, reverse=True)
            logger.info(f"Loaded {len(self.recent_sessions)} recent sessions")
            
        except Exception as e:
            logger.error(f"Error loading recent sessions: {e}")
            self.recent_sessions = []
    
    async def record_execution_session(self, orders: List[Dict[str, Any]], 
                                     exchange: str, metadata: Dict[str, Any] = None) -> str:
        """Enregistrer une session d'exécution"""
        try:
            session_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Analyser les ordres
            successful_orders = [o for o in orders if o.get("status") == "success"]
            failed_orders = [o for o in orders if o.get("status") in ["failed", "error", "rejected"]]
            
            # Calculer métriques
            total_volume = sum(float(o.get("filled_usd", 0)) for o in successful_orders)
            total_fees = sum(float(o.get("fees", 0)) for o in successful_orders)
            
            # Slippage moyen (si disponible)
            slippages = [
                float(o.get("exchange_data", {}).get("slippage_bps", 0)) 
                for o in successful_orders 
                if o.get("exchange_data", {}).get("slippage_bps") is not None
            ]
            avg_slippage = statistics.mean(slippages) if slippages else 0.0
            
            # Temps d'exécution (approximatif basé sur latence simulée)
            execution_times = [
                float(o.get("exchange_data", {}).get("latency_ms", 100)) 
                for o in successful_orders 
                if o.get("exchange_data", {}).get("latency_ms") is not None
            ]
            avg_execution_time = statistics.mean(execution_times) if execution_times else 100.0
            
            # Créer session
            session = ExecutionSession(
                id=session_id,
                timestamp=timestamp,
                exchange=exchange,
                total_orders=len(orders),
                successful_orders=len(successful_orders),
                failed_orders=len(failed_orders),
                total_volume_usd=total_volume,
                total_fees=total_fees,
                avg_slippage_bps=avg_slippage,
                avg_execution_time_ms=avg_execution_time,
                orders=orders,
                metadata=metadata or {}
            )
            
            # Ajouter au cache
            self.recent_sessions.insert(0, session)
            
            # Limiter le cache
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.cache_duration_hours)
            self.recent_sessions = [
                s for s in self.recent_sessions 
                if datetime.fromisoformat(s.timestamp.replace('Z', '+00:00')) > cutoff
            ]
            
            # Persister sur disque
            await self._persist_session(session)
            
            logger.info(f"Recorded execution session {session_id}: {len(orders)} orders, {total_volume:.2f} USD volume")
            return session_id
            
        except Exception as e:
            logger.error(f"Error recording execution session: {e}")
            return None
    
    async def _persist_session(self, session: ExecutionSession):
        """Persister une session sur disque"""
        try:
            # Organiser par jour
            session_date = datetime.fromisoformat(session.timestamp.replace('Z', '+00:00'))
            date_str = session_date.strftime("%Y-%m-%d")
            session_file = self.storage_path / f"sessions_{date_str}.json"
            
            # Lire sessions existantes du jour
            daily_sessions = []
            if session_file.exists():
                try:
                    with open(session_file, 'r') as f:
                        daily_sessions = json.load(f)
                except:
                    daily_sessions = []
            
            # Ajouter nouvelle session
            daily_sessions.append(session.to_dict())
            
            # Limiter à 1000 sessions par jour
            if len(daily_sessions) > 1000:
                daily_sessions = daily_sessions[-1000:]
            
            # Sauvegarder
            with open(session_file, 'w') as f:
                json.dump(daily_sessions, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error persisting session: {e}")
    
    def get_recent_sessions(self, limit: int = 50, exchange: str = None) -> List[Dict[str, Any]]:
        """Obtenir les sessions récentes"""
        sessions = self.recent_sessions
        
        if exchange:
            sessions = [s for s in sessions if s.exchange == exchange]
            
        limited_sessions = sessions[:limit]
        return [s.to_dict() for s in limited_sessions]
    
    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir une session spécifique par ID"""
        for session in self.recent_sessions:
            if session.id == session_id:
                return session.to_dict()
        
        # Si pas en cache, chercher sur disque (implémentation basique)
        # TODO: Optimiser avec index si nécessaire
        return None
    
    async def get_performance_metrics(self, period_days: int = 30, 
                                    exchange: str = None) -> PerformanceMetrics:
        """Calculer les métriques de performance sur une période"""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=period_days)
            
            # Récupérer sessions de la période
            sessions = await self._get_sessions_in_period(start_time, end_time, exchange)
            
            if not sessions:
                return PerformanceMetrics(
                    period_start=start_time.isoformat(),
                    period_end=end_time.isoformat(),
                    total_sessions=0,
                    total_orders=0,
                    total_volume_usd=0,
                    total_fees=0,
                    avg_success_rate=0,
                    avg_execution_time=0,
                    avg_slippage_bps=0,
                    exchanges_used=[],
                    top_symbols=[],
                    cost_breakdown={}
                )
            
            # Calculer métriques agrégées
            total_orders = sum(s.total_orders for s in sessions)
            total_volume = sum(s.total_volume_usd for s in sessions)
            total_fees = sum(s.total_fees for s in sessions)
            
            success_rates = [s.success_rate for s in sessions]
            avg_success_rate = statistics.mean(success_rates) if success_rates else 0
            
            execution_times = [s.avg_execution_time_ms for s in sessions]
            avg_execution_time = statistics.mean(execution_times) if execution_times else 0
            
            slippages = [s.avg_slippage_bps for s in sessions if s.avg_slippage_bps > 0]
            avg_slippage = statistics.mean(slippages) if slippages else 0
            
            # Exchanges utilisés
            exchanges_used = list(set(s.exchange for s in sessions))
            
            # Top symboles
            symbol_stats = defaultdict(lambda: {"count": 0, "volume": 0})
            for session in sessions:
                for order in session.orders:
                    if order.get("status") == "success":
                        symbol = order.get("symbol", "")
                        volume = float(order.get("filled_usd", 0))
                        symbol_stats[symbol]["count"] += 1
                        symbol_stats[symbol]["volume"] += volume
            
            top_symbols = sorted(
                [{"symbol": k, "count": v["count"], "volume": v["volume"]} 
                 for k, v in symbol_stats.items()],
                key=lambda x: x["volume"],
                reverse=True
            )[:10]
            
            # Répartition des coûts
            cost_breakdown = {
                "trading_fees": total_fees,
                "slippage_cost": total_volume * (avg_slippage / 10000) if avg_slippage > 0 else 0,
                "total_cost": 0
            }
            cost_breakdown["total_cost"] = cost_breakdown["trading_fees"] + cost_breakdown["slippage_cost"]
            
            return PerformanceMetrics(
                period_start=start_time.isoformat(),
                period_end=end_time.isoformat(),
                total_sessions=len(sessions),
                total_orders=total_orders,
                total_volume_usd=total_volume,
                total_fees=total_fees,
                avg_success_rate=avg_success_rate,
                avg_execution_time=avg_execution_time,
                avg_slippage_bps=avg_slippage,
                exchanges_used=exchanges_used,
                top_symbols=top_symbols,
                cost_breakdown=cost_breakdown
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return PerformanceMetrics(
                period_start=start_time.isoformat() if 'start_time' in locals() else "",
                period_end=end_time.isoformat() if 'end_time' in locals() else "",
                total_sessions=0,
                total_orders=0,
                total_volume_usd=0,
                total_fees=0,
                avg_success_rate=0,
                avg_execution_time=0,
                avg_slippage_bps=0,
                exchanges_used=[],
                top_symbols=[],
                cost_breakdown={}
            )
    
    async def _get_sessions_in_period(self, start_time: datetime, end_time: datetime, 
                                    exchange: str = None) -> List[ExecutionSession]:
        """Récupérer toutes les sessions dans une période"""
        sessions = []
        
        # D'abord les sessions en cache
        for session in self.recent_sessions:
            session_time = datetime.fromisoformat(session.timestamp.replace('Z', '+00:00'))
            if start_time <= session_time <= end_time:
                if not exchange or session.exchange == exchange:
                    sessions.append(session)
        
        # Ensuite charger depuis le disque si nécessaire
        # (pour les périodes plus anciennes que le cache)
        cache_start = datetime.now(timezone.utc) - timedelta(hours=self.cache_duration_hours)
        
        if start_time < cache_start:
            # Charger depuis les fichiers historiques
            current_date = start_time.date()
            end_date = min(end_time.date(), cache_start.date())
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                session_file = self.storage_path / f"sessions_{date_str}.json"
                
                if session_file.exists():
                    try:
                        with open(session_file, 'r') as f:
                            daily_sessions = json.load(f)
                        
                        for session_data in daily_sessions:
                            session_time = datetime.fromisoformat(session_data["timestamp"].replace('Z', '+00:00'))
                            if start_time <= session_time <= end_time:
                                if not exchange or session_data.get("exchange") == exchange:
                                    session = ExecutionSession(**session_data)
                                    # Éviter les doublons avec le cache
                                    if not any(s.id == session.id for s in sessions):
                                        sessions.append(session)
                                        
                    except Exception as e:
                        logger.warning(f"Error loading historical session file {session_file}: {e}")
                
                current_date += timedelta(days=1)
        
        return sessions
    
    async def get_execution_trends(self, days: int = 30, interval: str = "daily") -> Dict[str, Any]:
        """Analyser les tendances d'exécution"""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            sessions = await self._get_sessions_in_period(start_time, end_time)
            
            if not sessions:
                return {"message": "No execution data available for trend analysis"}
            
            # Grouper par intervalle
            if interval == "daily":
                interval_delta = timedelta(days=1)
            elif interval == "weekly":
                interval_delta = timedelta(weeks=1)
            elif interval == "hourly":
                interval_delta = timedelta(hours=1)
            else:
                interval_delta = timedelta(days=1)
            
            # Créer buckets temporels
            buckets = []
            current_time = start_time
            while current_time < end_time:
                bucket_end = min(current_time + interval_delta, end_time)
                buckets.append({
                    "start": current_time,
                    "end": bucket_end,
                    "sessions": [],
                    "label": current_time.strftime("%Y-%m-%d" if interval == "daily" else "%Y-%m-%d %H:00")
                })
                current_time = bucket_end
            
            # Assigner sessions aux buckets
            for session in sessions:
                session_time = datetime.fromisoformat(session.timestamp.replace('Z', '+00:00'))
                for bucket in buckets:
                    if bucket["start"] <= session_time < bucket["end"]:
                        bucket["sessions"].append(session)
                        break
            
            # Calculer métriques par bucket
            trend_data = []
            for bucket in buckets:
                bucket_sessions = bucket["sessions"]
                
                if bucket_sessions:
                    total_volume = sum(s.total_volume_usd for s in bucket_sessions)
                    total_orders = sum(s.total_orders for s in bucket_sessions)
                    avg_success_rate = statistics.mean([s.success_rate for s in bucket_sessions])
                    avg_slippage = statistics.mean([s.avg_slippage_bps for s in bucket_sessions if s.avg_slippage_bps > 0])
                    total_fees = sum(s.total_fees for s in bucket_sessions)
                else:
                    total_volume = 0
                    total_orders = 0
                    avg_success_rate = 0
                    avg_slippage = 0
                    total_fees = 0
                
                trend_data.append({
                    "period": bucket["label"],
                    "sessions_count": len(bucket_sessions),
                    "total_volume": total_volume,
                    "total_orders": total_orders,
                    "success_rate": avg_success_rate,
                    "avg_slippage_bps": avg_slippage,
                    "total_fees": total_fees,
                    "cost_ratio": (total_fees / total_volume * 100) if total_volume > 0 else 0
                })
            
            # Analyser tendances générales
            volumes = [d["total_volume"] for d in trend_data if d["total_volume"] > 0]
            success_rates = [d["success_rate"] for d in trend_data if d["success_rate"] > 0]
            
            volume_trend = "stable"
            success_trend = "stable"
            
            if len(volumes) >= 3:
                first_half = volumes[:len(volumes)//2]
                second_half = volumes[len(volumes)//2:]
                
                if statistics.mean(second_half) > statistics.mean(first_half) * 1.1:
                    volume_trend = "increasing"
                elif statistics.mean(second_half) < statistics.mean(first_half) * 0.9:
                    volume_trend = "decreasing"
            
            if len(success_rates) >= 3:
                first_half = success_rates[:len(success_rates)//2]
                second_half = success_rates[len(success_rates)//2:]
                
                if statistics.mean(second_half) > statistics.mean(first_half) + 2:
                    success_trend = "improving"
                elif statistics.mean(second_half) < statistics.mean(first_half) - 2:
                    success_trend = "degrading"
            
            return {
                "period_days": days,
                "interval": interval,
                "data_points": trend_data,
                "trends": {
                    "volume_trend": volume_trend,
                    "success_trend": success_trend,
                    "total_sessions": len(sessions),
                    "avg_daily_volume": sum(volumes) / len(volumes) if volumes else 0,
                    "overall_success_rate": statistics.mean(success_rates) if success_rates else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing execution trends: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_data(self):
        """Nettoyer les anciennes données selon la politique de rétention"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.analytics_config["retention_days"])
            deleted_files = 0
            
            # Supprimer les fichiers anciens
            for session_file in self.storage_path.glob("sessions_*.json"):
                try:
                    # Extraire la date du nom de fichier
                    date_str = session_file.stem.split('_', 1)[1]
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    if file_date.date() < cutoff_date.date():
                        session_file.unlink()
                        deleted_files += 1
                        
                except Exception as e:
                    logger.warning(f"Error processing file {session_file}: {e}")
            
            logger.info(f"Cleaned up {deleted_files} old execution history files")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé des statistiques"""
        try:
            if not self.recent_sessions:
                return {"message": "No recent execution data"}
            
            # Stats globales récentes (cache)
            total_sessions = len(self.recent_sessions)
            total_orders = sum(s.total_orders for s in self.recent_sessions)
            total_volume = sum(s.total_volume_usd for s in self.recent_sessions)
            total_fees = sum(s.total_fees for s in self.recent_sessions)
            
            success_rates = [s.success_rate for s in self.recent_sessions]
            avg_success_rate = statistics.mean(success_rates) if success_rates else 0
            
            # Exchange breakdown
            exchange_stats = defaultdict(lambda: {"sessions": 0, "volume": 0})
            for session in self.recent_sessions:
                exchange_stats[session.exchange]["sessions"] += 1
                exchange_stats[session.exchange]["volume"] += session.total_volume_usd
            
            # Performance rating
            thresholds = self.analytics_config["performance_thresholds"]
            if avg_success_rate >= thresholds["excellent_success_rate"]:
                performance_rating = "excellent"
            elif avg_success_rate >= thresholds["good_success_rate"]:
                performance_rating = "good"
            else:
                performance_rating = "needs_improvement"
            
            return {
                "total_sessions": total_sessions,
                "total_orders": total_orders,
                "total_volume_usd": total_volume,
                "total_fees": total_fees,
                "avg_success_rate": avg_success_rate,
                "performance_rating": performance_rating,
                "exchanges": dict(exchange_stats),
                "cache_period_hours": self.cache_duration_hours,
                "last_session": self.recent_sessions[0].timestamp if self.recent_sessions else None
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics summary: {e}")
            return {"error": str(e)}

# Instance globale
execution_history = ExecutionHistoryService()