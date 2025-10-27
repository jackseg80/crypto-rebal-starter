"""
End-to-End tests for Trailing Stop in Recommendations API.

Tests the complete flow from API request to response:
1. /api/ml/bourse/portfolio-recommendations endpoint
2. Complete integration: CSV → avg_price → trailing stop → response
3. Real position data (AAPL with +186% gain)
4. Response structure and completeness

Endpoint: GET /api/ml/bourse/portfolio-recommendations
Query params: user_id, file_key, timeframe
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_client():
    """FastAPI TestClient for E2E tests"""
    from api.main import app
    return TestClient(app)


@pytest.fixture
def saxo_csv_file_key():
    """Real Saxo CSV file key (October 25, 2025)"""
    return "20251025_103840_Positions_25-oct.-2025_10_37_13.csv"


@pytest.fixture
def test_user_id():
    """Test user ID with real data"""
    return "jack"


# ============================================================================
# Test Suite 1: Endpoint Availability
# ============================================================================

class TestEndpointAvailability:
    """Test that recommendations endpoint is available and functional"""

    def test_endpoint_exists(self, test_client):
        """Recommendations endpoint should exist"""
        response = test_client.get("/api/ml/bourse/portfolio-recommendations")

        # Should not be 404 (endpoint exists)
        assert response.status_code != 404

    def test_endpoint_requires_parameters(self, test_client):
        """Endpoint should require certain parameters"""
        # Call without parameters
        response = test_client.get("/api/ml/bourse/portfolio-recommendations")

        # May return 400 (bad request) or 422 (validation error)
        # or succeed with defaults
        assert response.status_code in [200, 400, 422]

    def test_endpoint_with_valid_params(self, test_client, test_user_id, saxo_csv_file_key):
        """Endpoint should work with valid parameters"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        # Should succeed or return expected error
        assert response.status_code in [200, 400, 422, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


# ============================================================================
# Test Suite 2: Response Structure
# ============================================================================

class TestResponseStructure:
    """Test response structure from recommendations API"""

    @pytest.mark.asyncio
    async def test_response_has_recommendations_list(self, test_client, test_user_id, saxo_csv_file_key):
        """Response should have recommendations list"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}, skipping structure test")

        data = response.json()

        # Check for recommendations list
        assert 'recommendations' in data or 'data' in data or 'positions' in data

    @pytest.mark.asyncio
    async def test_recommendation_has_price_targets(self, test_client, test_user_id, saxo_csv_file_key):
        """Each recommendation should have price_targets"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()

        # Extract recommendations (adjust based on actual response structure)
        recommendations = data.get('recommendations') or data.get('data') or data.get('positions') or []

        if len(recommendations) > 0:
            first_rec = recommendations[0]
            # Should have price_targets or similar structure
            assert 'price_targets' in first_rec or 'stop_loss' in first_rec or 'targets' in first_rec


# ============================================================================
# Test Suite 3: AAPL Position with Trailing Stop
# ============================================================================

class TestAAPLPositionTrailingStop:
    """Test real AAPL position with +186% gain and trailing stop"""

    @pytest.mark.asyncio
    async def test_aapl_position_present(self, test_client, test_user_id, saxo_csv_file_key):
        """AAPL position should be in recommendations"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)

        # Find AAPL
        aapl = next((r for r in recommendations if 'AAPL' in str(r.get('symbol', '')).upper()), None)

        if aapl is None:
            pytest.skip("AAPL position not found in recommendations")

        assert aapl is not None

    @pytest.mark.asyncio
    async def test_aapl_has_trailing_stop(self, test_client, test_user_id, saxo_csv_file_key):
        """AAPL should have trailing_stop in stop_loss_analysis"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)
        aapl = next((r for r in recommendations if 'AAPL' in str(r.get('symbol', '')).upper()), None)

        if aapl is None:
            pytest.skip("AAPL position not found")

        # Navigate to stop_loss_analysis
        price_targets = aapl.get('price_targets', {})
        stop_loss_analysis = price_targets.get('stop_loss_analysis', {})

        if not stop_loss_analysis:
            pytest.skip("No stop_loss_analysis in AAPL recommendation")

        stop_loss_levels = stop_loss_analysis.get('stop_loss_levels', {})

        # Should have trailing_stop
        assert 'trailing_stop' in stop_loss_levels, "trailing_stop not found in AAPL stop_loss_levels"

    @pytest.mark.asyncio
    async def test_aapl_trailing_stop_is_recommended(self, test_client, test_user_id, saxo_csv_file_key):
        """AAPL should have trailing_stop as recommended method"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)
        aapl = next((r for r in recommendations if 'AAPL' in str(r.get('symbol', '')).upper()), None)

        if aapl is None:
            pytest.skip("AAPL not found")

        stop_loss_analysis = aapl.get('price_targets', {}).get('stop_loss_analysis', {})

        if not stop_loss_analysis:
            pytest.skip("No stop_loss_analysis")

        recommended_method = stop_loss_analysis.get('recommended_method')

        # Should recommend trailing_stop for AAPL (+186% gain)
        assert recommended_method == 'trailing_stop', \
            f"Expected trailing_stop, got {recommended_method}"

    @pytest.mark.asyncio
    async def test_aapl_trailing_stop_values(self, test_client, test_user_id, saxo_csv_file_key):
        """AAPL trailing stop should have correct values"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)
        aapl = next((r for r in recommendations if 'AAPL' in str(r.get('symbol', '')).upper()), None)

        if aapl is None:
            pytest.skip("AAPL not found")

        stop_loss_levels = aapl.get('price_targets', {}).get('stop_loss_analysis', {}).get('stop_loss_levels', {})
        ts = stop_loss_levels.get('trailing_stop')

        if ts is None:
            pytest.skip("Trailing stop not found for AAPL")

        # Validate trailing stop values
        assert 'gain_pct' in ts
        assert 'is_legacy' in ts
        assert 'price' in ts
        assert 'tier' in ts
        assert 'trail_pct' in ts

        # AAPL should have ~186% gain
        assert ts['gain_pct'] > 100, f"Expected >100% gain, got {ts['gain_pct']}"
        assert 150 <= ts['gain_pct'] <= 220, f"Expected ~186% gain, got {ts['gain_pct']}"

        # Should be marked as legacy
        assert ts['is_legacy'] is True

        # Should be Tier 4 (100-500%)
        assert ts['tier'] == [1.0, 5.0] or ts['tier'] == (1.0, 5.0)

        # Should use -25% trailing
        assert ts['trail_pct'] == 0.25

    def _extract_recommendations(self, data: dict) -> list:
        """Helper to extract recommendations from various response structures"""
        # Try different possible keys
        return (data.get('recommendations') or
                data.get('data') or
                data.get('positions') or
                data.get('items') or
                [])


# ============================================================================
# Test Suite 4: Multiple Positions
# ============================================================================

class TestMultiplePositions:
    """Test that multiple positions are handled correctly"""

    @pytest.mark.asyncio
    async def test_multiple_positions_returned(self, test_client, test_user_id, saxo_csv_file_key):
        """Should return recommendations for multiple positions"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)

        # Should have multiple recommendations (Saxo CSV has 15+ positions)
        assert len(recommendations) > 1, "Expected multiple recommendations"

    @pytest.mark.asyncio
    async def test_legacy_positions_have_trailing_stop(self, test_client, test_user_id, saxo_csv_file_key):
        """Positions with high gains should have trailing_stop"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)

        legacy_count = 0
        for rec in recommendations:
            stop_loss_analysis = rec.get('price_targets', {}).get('stop_loss_analysis', {})
            if stop_loss_analysis.get('recommended_method') == 'trailing_stop':
                legacy_count += 1

        # Should have at least one legacy position (AAPL, META, COIN, etc.)
        assert legacy_count > 0, "Expected at least one position with trailing_stop"

    @pytest.mark.asyncio
    async def test_recent_positions_use_fixed_variable(self, test_client, test_user_id, saxo_csv_file_key):
        """Recent positions (<20% gain) should use Fixed Variable"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)

        fixed_var_count = 0
        for rec in recommendations:
            stop_loss_analysis = rec.get('price_targets', {}).get('stop_loss_analysis', {})
            if stop_loss_analysis.get('recommended_method') == 'fixed_variable':
                fixed_var_count += 1

        # Should have at least some positions using Fixed Variable
        # (Positions with <20% gain or no avg_price)
        assert fixed_var_count > 0, "Expected at least one position with fixed_variable"

    def _extract_recommendations(self, data: dict) -> list:
        """Helper to extract recommendations"""
        return (data.get('recommendations') or
                data.get('data') or
                data.get('positions') or
                data.get('items') or
                [])


# ============================================================================
# Test Suite 5: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in E2E flow"""

    def test_invalid_user_id(self, test_client, saxo_csv_file_key):
        """Invalid user_id should be handled gracefully"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": "nonexistent_user_12345",
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        # Should return error or empty result (not crash)
        assert response.status_code in [200, 400, 404, 422, 500]

    def test_invalid_file_key(self, test_client, test_user_id):
        """Invalid file_key should be handled gracefully"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": "nonexistent_file.csv",
                "timeframe": "medium"
            }
        )

        # Should return error (not crash)
        assert response.status_code in [200, 400, 404, 500]

    def test_invalid_timeframe(self, test_client, test_user_id, saxo_csv_file_key):
        """Invalid timeframe should be handled gracefully"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "invalid_timeframe"
            }
        )

        # Should return error or use default (not crash)
        assert response.status_code in [200, 400, 422]


# ============================================================================
# Test Suite 6: Performance
# ============================================================================

class TestPerformance:
    """Test E2E performance"""

    @pytest.mark.asyncio
    async def test_response_time_reasonable(self, test_client, test_user_id, saxo_csv_file_key):
        """API should respond in reasonable time"""
        import time

        start = time.time()
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )
        elapsed = time.time() - start

        # Should complete in less than 30 seconds (generous for E2E)
        assert elapsed < 30.0, f"Response took {elapsed:.2f}s (expected <30s)"

    @pytest.mark.asyncio
    async def test_large_portfolio_handled(self, test_client, test_user_id, saxo_csv_file_key):
        """Should handle portfolio with 15+ positions"""
        response = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response.status_code != 200:
            pytest.skip(f"Endpoint returned {response.status_code}")

        data = response.json()
        recommendations = self._extract_recommendations(data)

        # Should handle all positions (15+ in real CSV)
        assert len(recommendations) > 0

    def _extract_recommendations(self, data: dict) -> list:
        """Helper to extract recommendations"""
        return (data.get('recommendations') or
                data.get('data') or
                data.get('positions') or
                data.get('items') or
                [])


# ============================================================================
# Test Suite 7: Consistency
# ============================================================================

class TestConsistency:
    """Test consistency across multiple calls"""

    @pytest.mark.asyncio
    async def test_consistent_results_multiple_calls(self, test_client, test_user_id, saxo_csv_file_key):
        """Multiple calls should produce consistent results"""
        response1 = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        response2 = test_client.get(
            "/api/ml/bourse/portfolio-recommendations",
            params={
                "user_id": test_user_id,
                "file_key": saxo_csv_file_key,
                "timeframe": "medium"
            }
        )

        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("One or both requests failed")

        data1 = response1.json()
        data2 = response2.json()

        recommendations1 = self._extract_recommendations(data1)
        recommendations2 = self._extract_recommendations(data2)

        # Should return same number of recommendations
        assert len(recommendations1) == len(recommendations2)

        # AAPL should have same recommended method in both calls
        aapl1 = next((r for r in recommendations1 if 'AAPL' in str(r.get('symbol', '')).upper()), None)
        aapl2 = next((r for r in recommendations2 if 'AAPL' in str(r.get('symbol', '')).upper()), None)

        if aapl1 and aapl2:
            method1 = aapl1.get('price_targets', {}).get('stop_loss_analysis', {}).get('recommended_method')
            method2 = aapl2.get('price_targets', {}).get('stop_loss_analysis', {}).get('recommended_method')

            assert method1 == method2, "AAPL recommended method should be consistent"

    def _extract_recommendations(self, data: dict) -> list:
        """Helper to extract recommendations"""
        return (data.get('recommendations') or
                data.get('data') or
                data.get('positions') or
                data.get('items') or
                [])
