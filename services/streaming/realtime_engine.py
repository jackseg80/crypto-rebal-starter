"""
Phase 3B - Real-time Streaming Engine
Provides WebSocket connections, Redis Streams event processing, and live data feeds
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

# Optional Redis import for graceful degradation
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types d'événements dans les streams Redis"""
    PRICE_UPDATE = "price_update"
    RISK_ALERT = "risk_alert" 
    VAR_BREACH = "var_breach"
    STRESS_TEST = "stress_test"
    PORTFOLIO_UPDATE = "portfolio_update"
    MARKET_DATA = "market_data"
    CORRELATION_SPIKE = "correlation_spike"
    SYSTEM_STATUS = "system_status"


class SubscriptionType(str, Enum):
    """Types de souscriptions WebSocket"""
    ALL = "all"
    RISK_ALERTS = "risk_alerts"
    PRICE_FEEDS = "price_feeds"
    PORTFOLIO = "portfolio"
    SYSTEM = "system"


@dataclass
class StreamEvent:
    """Événement dans le système de streaming"""
    event_type: StreamEventType
    timestamp: datetime
    data: Dict[str, Any]
    source: str = "realtime_engine"
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
            "correlation_id": self.correlation_id
        }


class WebSocketManager:
    """Gestionnaire de connexions WebSocket pour données temps réel"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[SubscriptionType]] = {}
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Ajouter une nouvelle connexion WebSocket"""
        await websocket.accept()
        
        async with self._lock:
            self.active_connections.add(websocket)
            self.subscriptions[websocket] = {SubscriptionType.ALL}  # Default subscription
            self.connection_metadata[websocket] = {
                "client_id": client_id or f"client_{int(time.time())}",
                "connected_at": datetime.now(),
                "last_ping": datetime.now(),
                "message_count": 0
            }
        
        log.info(f"WebSocket connected: {client_id}, total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Supprimer une connexion WebSocket"""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                client_id = self.connection_metadata.get(websocket, {}).get("client_id", "unknown")
                del self.subscriptions[websocket]
                del self.connection_metadata[websocket]
                
                log.info(f"WebSocket disconnected: {client_id}, remaining: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, subscription_types: List[SubscriptionType]):
        """Modifier les souscriptions d'une connexion"""
        async with self._lock:
            if websocket in self.subscriptions:
                self.subscriptions[websocket] = set(subscription_types)
                client_id = self.connection_metadata.get(websocket, {}).get("client_id", "unknown")
                log.debug(f"Updated subscriptions for {client_id}: {subscription_types}")
    
    async def broadcast_event(self, event: StreamEvent, target_subscription: SubscriptionType = None):
        """Diffuser un événement à toutes les connexions concernées"""
        if not self.active_connections:
            return
        
        message = json.dumps(event.to_dict())
        disconnected = []
        
        async with self._lock:
            for websocket in self.active_connections.copy():
                try:
                    # Vérifier si la connexion est intéressée par cet événement
                    subscriptions = self.subscriptions.get(websocket, {SubscriptionType.ALL})
                    
                    if (SubscriptionType.ALL in subscriptions or
                        target_subscription in subscriptions or
                        target_subscription is None):
                        
                        await websocket.send_text(message)
                        
                        # Mettre à jour les métadonnées
                        if websocket in self.connection_metadata:
                            self.connection_metadata[websocket]["message_count"] += 1
                            self.connection_metadata[websocket]["last_ping"] = datetime.now()
                
                except WebSocketDisconnect:
                    disconnected.append(websocket)
                except Exception as e:
                    log.warning(f"Failed to send message to WebSocket: {e}")
                    disconnected.append(websocket)
        
        # Nettoyer les connexions fermées
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def send_to_client(self, client_id: str, event: StreamEvent) -> bool:
        """Envoyer un événement à un client spécifique"""
        async with self._lock:
            for websocket, metadata in self.connection_metadata.items():
                if metadata.get("client_id") == client_id:
                    try:
                        message = json.dumps(event.to_dict())
                        await websocket.send_text(message)
                        metadata["message_count"] += 1
                        return True
                    except Exception as e:
                        log.warning(f"Failed to send to client {client_id}: {e}")
                        return False
        return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Statistiques des connexions actives"""
        now = datetime.now()
        stats = {
            "total_connections": len(self.active_connections),
            "connections": []
        }
        
        for websocket, metadata in self.connection_metadata.items():
            connection_time = (now - metadata["connected_at"]).total_seconds()
            last_activity = (now - metadata["last_ping"]).total_seconds()
            
            stats["connections"].append({
                "client_id": metadata["client_id"],
                "connected_duration": connection_time,
                "last_activity_seconds": last_activity,
                "messages_sent": metadata["message_count"],
                "subscriptions": list(self.subscriptions.get(websocket, set()))
            })
        
        return stats


class RedisStreamManager:
    """Gestionnaire de Redis Streams pour processing d'événements haute performance"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.stream_consumers: Dict[str, Callable] = {}
        self.running = False
        self._consumer_tasks: List[asyncio.Task] = []
        
        # Configuration des streams
        self.streams_config = {
            "risk_events": {"maxlen": 10000, "consumer_group": "risk_processors"},
            "market_data": {"maxlen": 50000, "consumer_group": "market_processors"}, 
            "alerts": {"maxlen": 5000, "consumer_group": "alert_processors"},
            "portfolio_updates": {"maxlen": 1000, "consumer_group": "portfolio_processors"}
        }
    
    async def initialize(self):
        """Initialiser la connexion Redis et créer les streams"""
        if not REDIS_AVAILABLE:
            log.warning("Redis not available, RedisStreamManager running in fallback mode")
            return False
            
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            
            # Créer les streams et consumer groups
            for stream_name, config in self.streams_config.items():
                try:
                    # Créer le consumer group (ignore si existe déjà)
                    await self.redis_client.xgroup_create(
                        stream_name, config["consumer_group"], id="0", mkstream=True
                    )
                except redis.RedisError as e:
                    if "BUSYGROUP" not in str(e):
                        log.warning(f"Failed to create consumer group for {stream_name}: {e}")
            
            log.info("Redis Streams initialized successfully")
            return True
            
        except Exception as e:
            log.error(f"Failed to initialize Redis Streams: {e}")
            return False
    
    async def publish_event(self, stream_name: str, event: StreamEvent) -> str:
        """Publier un événement dans un stream Redis"""
        if not self.redis_client:
            log.debug("Redis not available, skipping stream publish")
            return "no_redis_fallback"
        
        try:
            event_data = {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
                "correlation_id": event.correlation_id or "",
                "data": json.dumps(event.data)
            }
            
            message_id = await self.redis_client.xadd(
                stream_name, event_data, 
                maxlen=self.streams_config.get(stream_name, {}).get("maxlen", 10000)
            )
            
            log.debug(f"Published event {event.event_type} to stream {stream_name}: {message_id}")
            return message_id
            
        except Exception as e:
            log.error(f"Failed to publish event to stream {stream_name}: {e}")
            raise
    
    def register_consumer(self, stream_name: str, consumer_func: Callable):
        """Enregistrer un consumer pour un stream"""
        self.stream_consumers[stream_name] = consumer_func
        log.info(f"Registered consumer for stream: {stream_name}")
    
    async def start_consumers(self):
        """Démarrer tous les consumers enregistrés"""
        if not self.redis_client:
            log.debug("Redis not available, skipping consumer start")
            return
            
        self.running = True
        
        for stream_name, consumer_func in self.stream_consumers.items():
            task = asyncio.create_task(
                self._consumer_loop(stream_name, consumer_func)
            )
            self._consumer_tasks.append(task)
        
        log.info(f"Started {len(self._consumer_tasks)} Redis Stream consumers")
    
    async def stop_consumers(self):
        """Arrêter tous les consumers"""
        self.running = False
        
        for task in self._consumer_tasks:
            task.cancel()
        
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
        
        self._consumer_tasks.clear()
        log.info("Stopped all Redis Stream consumers")
    
    async def _consumer_loop(self, stream_name: str, consumer_func: Callable):
        """Loop principal d'un consumer Redis Stream"""
        if not self.redis_client:
            log.debug(f"Redis not available, consumer loop for {stream_name} exiting")
            return
            
        consumer_group = self.streams_config[stream_name]["consumer_group"]
        consumer_name = f"consumer_{int(time.time())}"
        
        log.info(f"Starting consumer {consumer_name} for stream {stream_name}")
        
        try:
            while self.running:
                try:
                    # Lire les messages du stream
                    messages = await self.redis_client.xreadgroup(
                        consumer_group, consumer_name,
                        {stream_name: ">"}, 
                        count=10, block=1000  # Block for 1 second
                    )
                    
                    for stream, stream_messages in messages:
                        for message_id, fields in stream_messages:
                            try:
                                # Reconstruire l'événement
                                event_data = json.loads(fields.get("data", "{}"))
                                event = StreamEvent(
                                    event_type=StreamEventType(fields["event_type"]),
                                    timestamp=datetime.fromisoformat(fields["timestamp"]),
                                    data=event_data,
                                    source=fields["source"],
                                    correlation_id=fields.get("correlation_id") or None
                                )
                                
                                # Traiter l'événement
                                await consumer_func(event)
                                
                                # Acknowledger le message
                                await self.redis_client.xack(stream_name, consumer_group, message_id)
                                
                            except Exception as e:
                                log.error(f"Error processing message {message_id}: {e}")
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"Consumer error for stream {stream_name}: {e}")
                    await asyncio.sleep(5)  # Retry delay
        
        finally:
            log.info(f"Consumer {consumer_name} for stream {stream_name} stopped")
    
    async def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Informations sur un stream Redis"""
        if not self.redis_client:
            return {}
        
        try:
            info = await self.redis_client.xinfo_stream(stream_name)
            return {
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "groups": await self.redis_client.xinfo_groups(stream_name)
            }
        except Exception as e:
            log.warning(f"Failed to get info for stream {stream_name}: {e}")
            return {}
    
    async def cleanup(self):
        """Nettoyer les ressources"""
        await self.stop_consumers()
        if self.redis_client:
            await self.redis_client.aclose()


class RealtimeEngine:
    """Moteur principal de streaming temps réel - Phase 3B"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.websocket_manager = WebSocketManager()
        self.redis_manager = RedisStreamManager(redis_url)
        self.running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Métriques de performance
        self.metrics = {
            "events_processed": 0,
            "websocket_messages_sent": 0,
            "redis_events_published": 0,
            "start_time": None,
            "last_activity": None
        }
    
    async def initialize(self):
        """Initialiser le moteur de streaming"""
        log.info("Initializing RealtimeEngine...")
        
        # Initialiser Redis Streams (optionnel)
        redis_initialized = await self.redis_manager.initialize()
        if not redis_initialized:
            log.warning("Redis Streams not available - running in WebSocket-only mode")
        else:
            # Enregistrer les consumers par défaut seulement si Redis est disponible
            self.redis_manager.register_consumer("risk_events", self._handle_risk_event)
            self.redis_manager.register_consumer("alerts", self._handle_alert_event)
            self.redis_manager.register_consumer("market_data", self._handle_market_data)
            self.redis_manager.register_consumer("portfolio_updates", self._handle_portfolio_update)
        
        self.metrics["start_time"] = datetime.now()
        log.info("RealtimeEngine initialized successfully")
    
    async def start(self):
        """Démarrer le moteur de streaming"""
        if self.running:
            return
        
        self.running = True
        
        # Démarrer les consumers Redis
        await self.redis_manager.start_consumers()
        
        # Démarrer le heartbeat
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        log.info("RealtimeEngine started")
    
    async def stop(self):
        """Arrêter le moteur de streaming"""
        if not self.running:
            return
        
        self.running = False
        
        # Arrêter le heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Arrêter Redis Streams
        await self.redis_manager.cleanup()
        
        log.info("RealtimeEngine stopped")
    
    async def publish_risk_event(self, event_type: StreamEventType, data: Dict[str, Any], 
                                source: str = "risk_engine") -> str:
        """Publier un événement de risque"""
        event = StreamEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
            source=source
        )
        
        # Publier dans Redis Stream
        message_id = await self.redis_manager.publish_event("risk_events", event)
        
        # Diffuser via WebSocket
        await self.websocket_manager.broadcast_event(event, SubscriptionType.RISK_ALERTS)
        
        self.metrics["redis_events_published"] += 1
        self.metrics["websocket_messages_sent"] += len(self.websocket_manager.active_connections)
        self.metrics["last_activity"] = datetime.now()
        
        return message_id
    
    async def publish_market_data(self, data: Dict[str, Any]) -> str:
        """Publier des données de marché"""
        event = StreamEvent(
            event_type=StreamEventType.MARKET_DATA,
            timestamp=datetime.now(),
            data=data,
            source="market_feed"
        )
        
        message_id = await self.redis_manager.publish_event("market_data", event)
        await self.websocket_manager.broadcast_event(event, SubscriptionType.PRICE_FEEDS)
        
        self.metrics["redis_events_published"] += 1
        self.metrics["websocket_messages_sent"] += len(self.websocket_manager.active_connections)
        
        return message_id
    
    async def connect_websocket(self, websocket: WebSocket, client_id: str = None):
        """Connecter un client WebSocket"""
        await self.websocket_manager.connect(websocket, client_id)
    
    async def disconnect_websocket(self, websocket: WebSocket):
        """Déconnecter un client WebSocket"""
        await self.websocket_manager.disconnect(websocket)
    
    async def update_subscriptions(self, websocket: WebSocket, subscriptions: List[SubscriptionType]):
        """Mettre à jour les souscriptions d'un client"""
        await self.websocket_manager.subscribe(websocket, subscriptions)
    
    async def _handle_risk_event(self, event: StreamEvent):
        """Handler pour les événements de risque"""
        log.debug(f"Processing risk event: {event.event_type}")
        self.metrics["events_processed"] += 1
        
        # Logique de traitement spécifique aux événements de risque
        if event.event_type == StreamEventType.VAR_BREACH:
            # Traitement spécial pour les dépassements VaR
            await self._process_var_breach(event)
        elif event.event_type == StreamEventType.STRESS_TEST:
            # Traitement des résultats de stress test
            await self._process_stress_test(event)
    
    async def _handle_alert_event(self, event: StreamEvent):
        """Handler pour les alertes"""
        log.debug(f"Processing alert event: {event.event_type}")
        self.metrics["events_processed"] += 1
        
        # Diffuser l'alerte vers tous les clients intéressés
        await self.websocket_manager.broadcast_event(event, SubscriptionType.RISK_ALERTS)
    
    async def _handle_market_data(self, event: StreamEvent):
        """Handler pour les données de marché"""
        self.metrics["events_processed"] += 1
        
        # Traitement des données de marché en temps réel
        # Peut déclencher des calculs de risque si nécessaire
        pass
    
    async def _handle_portfolio_update(self, event: StreamEvent):
        """Handler pour les mises à jour de portefeuille"""
        log.debug(f"Processing portfolio update: {event.data}")
        self.metrics["events_processed"] += 1
        
        # Diffuser vers les clients intéressés par le portfolio
        await self.websocket_manager.broadcast_event(event, SubscriptionType.PORTFOLIO)
    
    async def _process_var_breach(self, event: StreamEvent):
        """Traitement spécialisé pour dépassement VaR"""
        breach_data = event.data
        log.warning(f"VaR breach detected: {breach_data}")
        
        # Ici on pourrait déclencher des actions automatiques:
        # - Notifications d'urgence
        # - Ajustements automatiques de position
        # - Escalade vers système de gouvernance
    
    async def _process_stress_test(self, event: StreamEvent):
        """Traitement des résultats de stress test"""
        stress_data = event.data
        log.info(f"Stress test result: {stress_data}")
    
    async def _heartbeat_loop(self):
        """Loop de heartbeat pour maintenir les connexions actives"""
        while self.running:
            try:
                # Envoyer un heartbeat aux connexions WebSocket
                heartbeat_event = StreamEvent(
                    event_type=StreamEventType.SYSTEM_STATUS,
                    timestamp=datetime.now(),
                    data={
                        "status": "healthy",
                        "connections": len(self.websocket_manager.active_connections),
                        "events_processed": self.metrics["events_processed"]
                    },
                    source="realtime_engine"
                )
                
                await self.websocket_manager.broadcast_event(heartbeat_event, SubscriptionType.SYSTEM)
                
                # Attendre 30 secondes
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Heartbeat error: {e}")
                await asyncio.sleep(10)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métriques de performance du moteur"""
        uptime = (datetime.now() - self.metrics["start_time"]).total_seconds() if self.metrics["start_time"] else 0
        
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "websocket_connections": len(self.websocket_manager.active_connections),
            "events_per_second": self.metrics["events_processed"] / max(uptime, 1),
            "connection_stats": self.websocket_manager.get_connection_stats()
        }


# Factory function pour créer le moteur
def create_realtime_engine(config: Dict[str, Any] = None) -> RealtimeEngine:
    """Factory pour créer une instance du moteur de streaming"""
    redis_url = "redis://localhost:6379"
    
    if config:
        redis_url = config.get("redis_url", redis_url)
    
    return RealtimeEngine(redis_url=redis_url)


# Singleton global pour l'application
_global_engine: Optional[RealtimeEngine] = None

async def get_realtime_engine() -> RealtimeEngine:
    """Récupérer l'instance globale du moteur de streaming"""
    global _global_engine
    
    if _global_engine is None:
        _global_engine = create_realtime_engine()
        await _global_engine.initialize()
    
    return _global_engine