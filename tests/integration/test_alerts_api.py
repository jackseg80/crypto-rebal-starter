"""
Tests d'intégration pour les endpoints d'alertes - Phase 1
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock

# Import du test app
from api.main import app
from api.alerts_endpoints import initialize_alert_engine
from services.alerts.alert_engine import AlertEngine
from services.alerts.alert_types import Alert, AlertType, AlertSeverity


class TestAlertsAPI:
    
    @pytest.fixture
    def mock_alert_engine(self):
        """Mock AlertEngine pour tests API"""
        engine = Mock(spec=AlertEngine)
        
        # Mock alertes actives
        sample_alerts = [
            Alert(
                id="alert-1",
                alert_type=AlertType.VOL_Q90_CROSS,
                severity=AlertSeverity.S2,
                data={"current_value": 0.8, "threshold": 0.75},
                created_at=datetime.now()
            ),
            Alert(
                id="alert-2", 
                alert_type=AlertType.REGIME_FLIP,
                severity=AlertSeverity.S3,
                data={"confidence": 0.9},
                created_at=datetime.now() - timedelta(minutes=30),
                snooze_until=datetime.now() + timedelta(minutes=60)
            )
        ]
        
        engine.get_active_alerts.return_value = sample_alerts
        engine.acknowledge_alert = AsyncMock(return_value=True)
        engine.snooze_alert = AsyncMock(return_value=True)
        
        # Mock métriques
        engine.get_metrics.return_value = {
            "alert_engine": {
                "counters": {"alerts_emitted_total": {"VOL_Q90_CROSS:S2": 5}},
                "gauges": {"active_alerts_count": 2}
            },
            "storage": {"redis_available": False, "file_size_kb": 12},
            "host_info": {"host_id": "test-host", "is_scheduler": True}
        }
        
        # Mock config
        engine.config = {"metadata": {"config_version": "test-1.0"}}
        engine.config_file_path = "/test/config.json"
        engine._config_mtime = 1640995200.0
        engine._check_config_reload = Mock(return_value=True)
        
        # Mock storage
        mock_storage = Mock()
        mock_storage.ping = Mock(return_value=True)
        mock_storage.get_active_alerts = Mock(return_value=sample_alerts)
        engine.storage = mock_storage
        
        # Mock health check
        engine.is_scheduler = True
        engine.last_evaluation = datetime.now() - timedelta(minutes=1)
        engine.host_id = "test-host-123"
        
        return engine
    
    @pytest.fixture
    def client(self, mock_alert_engine):
        """Client de test avec mock engine"""
        initialize_alert_engine(mock_alert_engine)
        return TestClient(app)
    
    def test_get_active_alerts(self, client):
        """Test GET /api/alerts/active"""
        response = client.get("/api/alerts/active")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1  # Une alerte snoozée est filtrée par défaut
        assert data[0]["id"] == "alert-1"
        assert data[0]["alert_type"] == "VOL_Q90_CROSS"
        assert data[0]["severity"] == "S2"
        
        # Test avec filtre severity
        response = client.get("/api/alerts/active?severity_filter=S2")
        assert response.status_code == 200
        filtered_data = response.json()
        assert len(filtered_data) == 1
        assert filtered_data[0]["severity"] == "S2"
    
    def test_get_active_alerts_exclude_snoozed(self, client):
        """Test exclusion des alertes snoozées"""
        response = client.get("/api/alerts/active?include_snoozed=false")
        
        assert response.status_code == 200
        data = response.json()
        # Doit exclure alert-2 qui est snoozée
        assert len(data) == 1
        assert data[0]["id"] == "alert-1"
    
    def test_acknowledge_alert(self, client, mock_alert_engine):
        """Test POST /api/alerts/acknowledge/{alert_id}"""
        response = client.post("/api/alerts/acknowledge/alert-1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Alert alert-1 acknowledged" in data["message"]
        
        mock_alert_engine.acknowledge_alert.assert_called_once_with("alert-1", "system_user")
    
    def test_acknowledge_nonexistent_alert(self, client, mock_alert_engine):
        """Test acquittement alerte inexistante"""
        mock_alert_engine.acknowledge_alert.return_value = False
        
        response = client.post("/api/alerts/acknowledge/nonexistent")
        
        assert response.status_code == 404
    
    def test_snooze_alert(self, client, mock_alert_engine):
        """Test POST /api/alerts/snooze/{alert_id}"""
        snooze_request = {"minutes": 120}
        
        response = client.post(
            "/api/alerts/snooze/alert-1",
            json=snooze_request
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "snoozed for 120 minutes" in data["message"]
        
        mock_alert_engine.snooze_alert.assert_called_once_with("alert-1", 120)
    
    def test_snooze_validation(self, client):
        """Test validation des paramètres snooze"""
        # Minutes trop courtes
        response = client.post("/api/alerts/snooze/alert-1", json={"minutes": 1})
        assert response.status_code == 422
        
        # Minutes trop longues
        response = client.post("/api/alerts/snooze/alert-1", json={"minutes": 2000})
        assert response.status_code == 422
    
    def test_get_metrics(self, client):
        """Test GET /api/alerts/metrics"""
        response = client.get("/api/alerts/metrics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "alert_engine" in data
        assert "storage" in data
        assert "host_info" in data
        assert "timestamp" in data
        
        # Vérifier structure
        assert data["alert_engine"]["gauges"]["active_alerts_count"] == 2
        assert data["host_info"]["host_id"] == "test-host"
    
    def test_get_alert_types(self, client):
        """Test GET /api/alerts/types"""
        response = client.get("/api/alerts/types")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "alert_types" in data
        assert "severities" in data
        
        # Vérifier qu'on a les 6 types
        assert len(data["alert_types"]) == 6
        assert len(data["severities"]) == 3
        
        # Vérifier structure
        vol_type = next(t for t in data["alert_types"] if t["type"] == "VOL_Q90_CROSS")
        assert "description" in vol_type
    
    def test_config_reload(self, client, mock_alert_engine):
        """Test POST /api/alerts/config/reload"""
        response = client.post("/api/alerts/config/reload")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config_version"] == "test-1.0"
        
        mock_alert_engine._check_config_reload.assert_called_once()
    
    def test_get_current_config(self, client):
        """Test GET /api/alerts/config/current"""
        response = client.get("/api/alerts/config/current")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "config" in data
        assert "config_file_path" in data
        assert "last_modified" in data
        assert data["config_file_path"] == "/test/config.json"
    
    def test_health_check(self, client):
        """Test GET /api/alerts/health"""
        response = client.get("/api/alerts/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "components" in data
        assert data["components"]["scheduler"]["status"] == "healthy"
        assert data["components"]["storage"]["status"] == "healthy"
        assert data["host_id"] == "test-host-123"
    
    def test_prometheus_metrics(self, client):
        """Test GET /api/alerts/metrics/prometheus"""
        response = client.get("/api/alerts/metrics/prometheus")
        
        assert response.status_code == 200
        prometheus_text = response.content.decode()
        
        # Vérifier format Prometheus
        assert "# HELP crypto_rebal_alerts_total" in prometheus_text
        assert "# TYPE crypto_rebal_alerts_total counter" in prometheus_text
        assert 'crypto_rebal_alerts_total{type=\\"VOL_Q90_CROSS\\",severity=\\"S2\\"} 5' in prometheus_text
        assert "crypto_rebal_alerts_active_count 2" in prometheus_text
    
    def test_alert_history_pagination(self, client, mock_alert_engine):
        """Test GET /api/alerts/history avec pagination"""
        # Mock storage pour historique
        history_alerts = [
            Alert(
                id=f"alert-{i}",
                alert_type=AlertType.VOL_Q90_CROSS,
                severity=AlertSeverity.S1,
                data={"test": i},
                created_at=datetime.now() - timedelta(hours=i)
            ) for i in range(10)
        ]
        mock_alert_engine.storage.get_active_alerts.return_value = history_alerts
        
        response = client.get("/api/alerts/history?limit=5&offset=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["alerts"]) == 5
        assert data["pagination"]["limit"] == 5
        assert data["pagination"]["offset"] == 2
        assert data["pagination"]["total"] == 10
        assert data["pagination"]["has_next"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])