"""
Phase 3B WebSocket API Endpoints - Real-time Streaming
Provides WebSocket connections for live data feeds, risk alerts, and system monitoring
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import os
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging
from datetime import datetime

from services.streaming.realtime_engine import (
    get_realtime_engine, RealtimeEngine, SubscriptionType, 
    StreamEventType, StreamEvent
)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])
DEBUG_SIM = os.getenv("DEBUG_SIMULATION", "false").lower() == "true"
log = logging.getLogger(__name__)



# Response Models
class RealtimeStatusResponse(BaseModel):
    status: str = Field(..., description="Status du système temps réel")
    connections: int = Field(..., description="Nombre de connexions WebSocket actives")
    uptime_seconds: float = Field(..., description="Temps de fonctionnement en secondes")
    events_processed: int = Field(..., description="Nombre d'événements traités")
    events_per_second: float = Field(..., description="Taux de traitement d'événements")
    redis_status: str = Field(..., description="Status de Redis Streams")
    timestamp: datetime = Field(..., description="Timestamp de la réponse")

class WsStatusResponse(BaseModel):
    status: str = Field(..., description="Status message")

class StreamStatsResponse(BaseModel):
    stream_name: str
    length: int = Field(..., description="Nombre de messages dans le stream")
    consumers: int = Field(..., description="Nombre de consumers actifs")
    last_activity: Optional[datetime] = Field(None, description="Dernière activité")

class PublishEventRequest(BaseModel):
    event_type: str = Field(..., description="Type d'événement")
    data: Dict[str, Any] = Field(..., description="Données de l'événement")
    source: str = Field(default="api", description="Source de l'événement")

# WebSocket endpoint principal
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Identifiant client"),
    subscriptions: Optional[str] = Query("all", description="Souscriptions (comma-separated)")
):
    """
    WebSocket endpoint principal pour streaming temps réel
    
    Paramètres:
    - client_id: Identifiant unique du client (optionnel)
    - subscriptions: Types de souscriptions séparées par virgule (all, risk_alerts, price_feeds, portfolio, system)
    
    Événements reçus:
    - subscribe: Changer les souscriptions
    - ping: Heartbeat du client
    
    Événements envoyés:
    - Événements de risque (VAR_BREACH, STRESS_TEST, etc.)
    - Données de marché
    - Mises à jour de portfolio
    - Status système
    """
    engine = await get_realtime_engine()
    
    try:
        # Connecter le client
        await engine.connect_websocket(websocket, client_id)
        
        # Configurer les souscriptions initiales
        if subscriptions and subscriptions != "all":
            subscription_list = []
            for sub in subscriptions.split(","):
                sub = sub.strip().lower()
                if sub in ["risk_alerts", "price_feeds", "portfolio", "system"]:
                    subscription_list.append(SubscriptionType(sub))
            
            if subscription_list:
                await engine.update_subscriptions(websocket, subscription_list)
        
        # Envoyer message de bienvenue
        welcome_event = StreamEvent(
            event_type=StreamEventType.SYSTEM_STATUS,
            timestamp=datetime.now(),
            data={
                "message": "Connected to realtime stream",
                "client_id": client_id,
                "subscriptions": subscriptions
            },
            source="websocket_api"
        )
        
        await websocket.send_text(json.dumps(welcome_event.to_dict()))
        
        # Loop d'écoute des messages du client
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Traiter les commandes du client
                command = message.get("command")
                
                if command == "subscribe":
                    # Changer les souscriptions
                    new_subs = message.get("subscriptions", [])
                    subscription_list = []
                    for sub in new_subs:
                        if sub in ["all", "risk_alerts", "price_feeds", "portfolio", "system"]:
                            subscription_list.append(SubscriptionType(sub))
                    
                    await engine.update_subscriptions(websocket, subscription_list)
                    
                    # Confirmer le changement
                    response = {
                        "command": "subscribe_ack",
                        "subscriptions": new_subs,
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_text(json.dumps(response))
                
                elif command == "ping":
                    # Heartbeat du client
                    pong = {
                        "command": "pong",
                        "timestamp": datetime.now().isoformat(),
                        "server_time": datetime.now().isoformat()
                    }
                    await websocket.send_text(json.dumps(pong))
                
                elif command == "get_stats":
                    # Envoyer les statistiques
                    stats = engine.get_metrics()
                    response = {
                        "command": "stats",
                        "data": stats,
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_text(json.dumps(response))
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # Message mal formé, ignorer
                pass
            except Exception as e:
                log.warning(f"Error processing WebSocket message: {e}")
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"WebSocket error: {e}")
    finally:
        await engine.disconnect_websocket(websocket)

# REST endpoints pour monitoring et contrôle
@router.get("/status", response_model=RealtimeStatusResponse)
async def get_realtime_status(
    engine: RealtimeEngine = Depends(get_realtime_engine)
):
    """Status du système de streaming temps réel"""
    try:
        metrics = engine.get_metrics()
        
        return RealtimeStatusResponse(
            status="healthy" if engine.running else "stopped",
            connections=metrics["connection_stats"]["total_connections"],
            uptime_seconds=metrics["uptime_seconds"],
            events_processed=metrics["events_processed"],
            events_per_second=metrics["events_per_second"],
            redis_status="connected" if engine.redis_manager.redis_client else "disconnected",
            timestamp=datetime.now()
        )
        
    except Exception as e:
        log.error(f"Failed to get realtime status: {e}")
        raise HTTPException(500, "failed_to_get_status")

@router.get("/connections")
async def get_connection_stats(
    engine: RealtimeEngine = Depends(get_realtime_engine)
):
    """Statistiques détaillées des connexions WebSocket"""
    try:
        return engine.websocket_manager.get_connection_stats()
    except Exception as e:
        log.error(f"Failed to get connection stats: {e}")
        raise HTTPException(500, "failed_to_get_connections")

@router.get("/streams/{stream_name}/info", response_model=StreamStatsResponse)
async def get_stream_info(
    stream_name: str,
    engine: RealtimeEngine = Depends(get_realtime_engine)
):
    """Informations sur un Redis Stream spécifique"""
    try:
        info = await engine.redis_manager.get_stream_info(stream_name)
        
        if not info:
            raise HTTPException(404, f"Stream '{stream_name}' not found")
        
        return StreamStatsResponse(
            stream_name=stream_name,
            length=info.get("length", 0),
            consumers=len(info.get("groups", [])),
            last_activity=datetime.now()  # Approximation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get stream info for {stream_name}: {e}")
        raise HTTPException(500, "failed_to_get_stream_info")

# REMOVED: Dangerous debug endpoints /publish and /broadcast
# These endpoints allowed arbitrary event publishing and could spam clients
# They have been removed for production security
# 
# Former functionality:
# - POST /api/realtime/publish -> allowed publishing arbitrary events to all subscribers
# - POST /api/realtime/broadcast -> allowed broadcasting arbitrary messages to all clients
# 
# These operations should only be performed by internal system components,
# not exposed via public API endpoints.

@router.get("/demo")
@router.post("/dev/simulate", response_model=WsStatusResponse)
async def dev_simulate_event(kind: str = "risk_alert"):
    """
    Endpoint DEV-ONLY pour simuler un évènement. Protégé par DEBUG_SIM.
    """
    if not DEBUG_SIM:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Simulation disabled")
    # TODO: brancher ici le vrai broadcaster si disponible
    log.info(f"[DEV] Simulated event published: kind={kind}")
    return WsStatusResponse(status=f"simulated:{kind}")

async def get_demo_page():
    """Page de démonstration WebSocket pour tester le streaming"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Phase 3B - Real-time Streaming Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .status.connected { background-color: #d4edda; border: 1px solid #c3e6cb; }
            .status.disconnected { background-color: #f8d7da; border: 1px solid #f5c6cb; }
            .controls { margin: 20px 0; }
            .controls input, .controls select, .controls button { 
                margin: 5px; padding: 8px; 
            }
            .events { 
                height: 400px; overflow-y: auto; border: 1px solid #ddd; 
                padding: 10px; background: #f8f9fa; 
            }
            .event { 
                margin: 5px 0; padding: 8px; border-left: 3px solid #007bff;
                background: white; font-size: 12px;
            }
            .event.risk_alert { border-left-color: #dc3545; }
            .event.market_data { border-left-color: #28a745; }
            .event.system_status { border-left-color: #6c757d; }
            .stats { display: flex; gap: 20px; margin: 20px 0; }
            .stat { padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔄 Phase 3B - Real-time Streaming Demo</h1>
            
            <div id="status" class="status disconnected">
                Status: Disconnected
            </div>
            
            <div class="controls">
                <input type="text" id="clientId" placeholder="Client ID (optional)" value="demo_client">
                <select id="subscriptions">
                    <option value="all">All Events</option>
                    <option value="risk_alerts">Risk Alerts Only</option>
                    <option value="price_feeds">Price Feeds Only</option>
                    <option value="portfolio">Portfolio Only</option>
                    <option value="system">System Only</option>
                </select>
                <button onclick="connect()">Connect</button>
                <button onclick="disconnect()">Disconnect</button>
                <button onclick="sendPing()">Ping</button>
                <button onclick="getStats()">Get Stats</button>
                <button onclick="clearEvents()">Clear Events</button>
            </div>
            
            <div class="stats">
                <div class="stat">
                    <strong>Messages Received:</strong> <span id="messageCount">0</span>
                </div>
                <div class="stat">
                    <strong>Connection Time:</strong> <span id="connectionTime">-</span>
                </div>
                <div class="stat">
                    <strong>Last Event:</strong> <span id="lastEvent">-</span>
                </div>
            </div>
            
            <h3>Live Events Stream</h3>
            <div id="events" class="events"></div>
            
            <div class="controls">
                <h4>Test Events (for debugging)</h4>
                <p style="color:#6c757d; font-size:12px;">
                  Simulation is disabled in this build (dangerous endpoints removed). Append <code>?simulate=1</code> to URL to enable demo buttons.
                </p>
                <button onclick="simulateRiskAlert()">Simulate Risk Alert</button>
                <button onclick="simulateMarketData()">Simulate Market Data</button>
                <button onclick="simulateVarBreach()">Simulate VaR Breach</button>
            </div>
        </div>

        <script>
            let ws = null;
            let messageCount = 0;
            let connectionTime = null;
            const enableSim = new URLSearchParams(window.location.search).get('simulate') === '1';
            
            function connect() {
                if (ws) {
                    disconnect();
                }
                
                const clientId = document.getElementById('clientId').value;
                const subscriptions = document.getElementById('subscriptions').value;
                
                const wsUrl = `ws://localhost:8000/api/realtime/ws?client_id=${clientId}&subscriptions=${subscriptions}`;
                
                ws = new WebSocket(wsUrl);
                
                ws.onopen = function(event) {
                    connectionTime = new Date();
                    updateStatus('Connected', 'connected');
                    updateConnectionTime();
                };
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    addEvent(data);
                    messageCount++;
                    document.getElementById('messageCount').textContent = messageCount;
                    document.getElementById('lastEvent').textContent = new Date().toLocaleTimeString();
                };
                
                ws.onclose = function(event) {
                    updateStatus('Disconnected', 'disconnected');
                    connectionTime = null;
                    updateConnectionTime();
                };
                
                ws.onerror = function(error) {
                    updateStatus('Error: ' + error, 'disconnected');
                };
            }
            
            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }
            
            function sendPing() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({command: 'ping'}));
                }
            }
            
            function getStats() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({command: 'get_stats'}));
                }
            }
            
            function updateStatus(message, className) {
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = 'Status: ' + message;
                statusDiv.className = 'status ' + className;
            }
            
            function updateConnectionTime() {
                if (connectionTime) {
                    const elapsed = Math.floor((new Date() - connectionTime) / 1000);
                    document.getElementById('connectionTime').textContent = elapsed + 's';
                } else {
                    document.getElementById('connectionTime').textContent = '-';
                }
                setTimeout(updateConnectionTime, 1000);
            }
            
            function addEvent(data) {
                const eventsDiv = document.getElementById('events');
                const eventDiv = document.createElement('div');
                
                let eventClass = 'event';
                if (data.event_type) {
                    if (data.event_type.includes('risk') || data.event_type.includes('alert')) {
                        eventClass += ' risk_alert';
                    } else if (data.event_type === 'market_data') {
                        eventClass += ' market_data';
                    } else if (data.event_type === 'system_status') {
                        eventClass += ' system_status';
                    }
                }
                
                eventDiv.className = eventClass;
                eventDiv.innerHTML = `
                    <strong>${data.event_type || data.command || 'message'}:</strong> 
                    ${JSON.stringify(data.data || data, null, 2)}
                    <br><small>${data.timestamp || new Date().toISOString()}</small>
                `;
                
                eventsDiv.insertBefore(eventDiv, eventsDiv.firstChild);
                
                // Limiter à 50 événements
                while (eventsDiv.children.length > 50) {
                    eventsDiv.removeChild(eventsDiv.lastChild);
                }
            }
            
            function clearEvents() {
                document.getElementById('events').innerHTML = '';
                messageCount = 0;
                document.getElementById('messageCount').textContent = '0';
            }
            
            // Fonctions de simulation pour tests
            async function simulateRiskAlert() {
                if (!enableSim) { alert('Simulation disabled. Append ?simulate=1'); return; }
                console.warn('Publish endpoint removed; simulation is a no-op.');
            }
            
            async function simulateMarketData() {
                if (!enableSim) { alert('Simulation disabled. Append ?simulate=1'); return; }
                console.warn('Publish endpoint removed; simulation is a no-op.');
            }
            
            async function simulateVarBreach() {
                if (!enableSim) { alert('Simulation disabled. Append ?simulate=1'); return; }
                console.warn('Publish endpoint removed; simulation is a no-op.');
            }
            
            // Auto-connect on page load
            setTimeout(connect, 500);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/start")
async def start_realtime_engine(
    engine: RealtimeEngine = Depends(get_realtime_engine)
):
    """Démarrer le moteur de streaming (pour tests/management)"""
    try:
        if not engine.running:
            await engine.start()
            return {"success": True, "message": "Realtime engine started"}
        else:
            return {"success": True, "message": "Realtime engine already running"}
    except Exception as e:
        log.error(f"Failed to start realtime engine: {e}")
        raise HTTPException(500, "failed_to_start_engine")

@router.post("/stop")
async def stop_realtime_engine(
    engine: RealtimeEngine = Depends(get_realtime_engine)
):
    """Arrêter le moteur de streaming (pour tests/management)"""
    try:
        if engine.running:
            await engine.stop()
            return {"success": True, "message": "Realtime engine stopped"}
        else:
            return {"success": True, "message": "Realtime engine already stopped"}
    except Exception as e:
        log.error(f"Failed to stop realtime engine: {e}")
        raise HTTPException(500, "failed_to_stop_engine")
