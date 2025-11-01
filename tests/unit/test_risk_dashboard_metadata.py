"""
Tests unitaires pour valider les corrections des incohérences de données de wallet
- Test des métadonnées normalisées dans /api/risk/dashboard
- Test de cohérence user/source
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from datetime import datetime

client = TestClient(app)


def test_risk_dashboard_with_metadata(test_user_id):
    """Test que /api/risk/dashboard retourne des métadonnées normalisées"""

    response = client.get(
        "/api/risk/dashboard",
        headers={"X-User": test_user_id},
        params={
            "source": "csv_0",
            "min_usd": 1.0,
            "price_history_days": 30,
            "lookback_days": 30
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["success"] is True
    assert "meta" in data, "Response should contain meta field"

    meta = data["meta"]
    assert meta["user_id"] == test_user_id, f"Expected user_id='{test_user_id}', got '{meta.get('user_id')}'"
    assert meta["source_id"] in ["csv_0", "cointracking"], f"Expected valid source_id, got '{meta.get('source_id')}'"
    assert meta["taxonomy_version"] == "v2", f"Expected taxonomy_version='v2', got '{meta.get('taxonomy_version')}'"
    assert "taxonomy_hash" in meta, "meta should contain taxonomy_hash"
    assert len(meta["taxonomy_hash"]) == 8, "taxonomy_hash should be 8 characters"
    assert "generated_at" in meta, "meta should contain generated_at timestamp"
    assert "correlation_id" in meta, "meta should contain correlation_id"

    # Validate timestamp format
    try:
        datetime.fromisoformat(meta["generated_at"].replace('Z', '+00:00'))
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {meta['generated_at']}")


def test_risk_dashboard_different_users(test_user_id):
    """Test que différents users donnent des données différentes"""
    # Generate second user_id for isolation test
    import uuid
    test_user_id_2 = f"test_user2_{uuid.uuid4().hex[:8]}"

    # Request for user 1
    response_user1 = client.get(
        "/api/risk/dashboard",
        headers={"X-User": test_user_id},
        params={"source": "cointracking", "min_usd": 1.0}
    )

    # Request for user 2
    response_user2 = client.get(
        "/api/risk/dashboard",
        headers={"X-User": test_user_id_2},
        params={"source": "cointracking", "min_usd": 1.0}
    )

    assert response_user1.status_code == 200
    assert response_user2.status_code == 200

    data_user1 = response_user1.json()
    data_user2 = response_user2.json()

    assert data_user1["meta"]["user_id"] == test_user_id
    assert data_user2["meta"]["user_id"] == test_user_id_2

    # Les données devraient être différentes (sauf si même portfolio)
    # Au minimum, les timestamps/correlation_id doivent être différents
    assert data_user1["meta"]["correlation_id"] != data_user2["meta"]["correlation_id"]


def test_risk_dashboard_groups_consistency(test_user_id):
    """Test que les groupes d'assets sont cohérents avec la taxonomie standard"""

    response = client.get(
        "/api/risk/dashboard",
        headers={"X-User": test_user_id},
        params={"source": "cointracking", "min_usd": 1.0}
    )

    assert response.status_code == 200
    data = response.json()

    if "risk_metrics" in data and "exposure_by_group" in data["risk_metrics"]:
        exposure_groups = data["risk_metrics"]["exposure_by_group"]

        # Vérifier qu'aucun groupe "LARGE" n'apparaît
        assert "LARGE" not in exposure_groups, "Group 'LARGE' should not appear in response"

        # Vérifier que la somme des expositions ≈ 100%
        if exposure_groups:
            total_exposure = sum(exposure_groups.values())
            assert 0.95 <= total_exposure <= 1.05, f"Total exposure should be ~100%, got {total_exposure*100:.1f}%"

        # Vérifier que les groupes standards sont présents si portfolio non vide
        standard_groups = ["BTC", "ETH", "L1/L0 majors", "Stablecoins"]
        present_standard_groups = [g for g in standard_groups if g in exposure_groups]

        if exposure_groups:  # Si portfolio non vide
            assert len(present_standard_groups) > 0, f"At least one standard group should be present. Found: {list(exposure_groups.keys())}"


def test_risk_dashboard_cache_invalidation_headers(test_user_id):
    """Test que les headers sont correctement utilisés pour éviter les incohérences"""

    # Test sans header X-User (devrait fonctionner avec fallback)
    response_no_header = client.get("/api/risk/dashboard")

    # Test avec header X-User
    response_with_header = client.get(
        "/api/risk/dashboard",
        headers={"X-User": test_user_id}
    )

    assert response_no_header.status_code == 200
    assert response_with_header.status_code == 200

    data_no_header = response_no_header.json()
    data_with_header = response_with_header.json()

    # Les deux devraient avoir des métadonnées
    assert "meta" in data_no_header
    assert "meta" in data_with_header

    # Le user_id devrait être cohérent
    assert data_with_header["meta"]["user_id"] == test_user_id
    # Sans header, devrait fallback sur 'demo' ou autre default
    assert data_no_header["meta"]["user_id"] in ["demo", "default"]


if __name__ == "__main__":
    # Run individual tests
    test_risk_dashboard_with_metadata()
    test_risk_dashboard_different_users()
    test_risk_dashboard_groups_consistency()
    test_risk_dashboard_cache_invalidation_headers()
    print("✅ All risk dashboard metadata tests passed!")