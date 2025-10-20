"""
Unit tests for api.utils.formatters module.

Tests standard API response formatters and legacy formatters.
"""
import pytest
from datetime import datetime
from fastapi.responses import JSONResponse

from api.utils.formatters import (
    success_response,
    error_response,
    paginated_response,
    legacy_response,
    StandardResponse
)


class TestSuccessResponse:
    """Tests for success_response()"""

    def test_success_response_basic(self):
        """Test basic success response with data only"""
        data = {"balance": 1000, "currency": "USD"}
        response = success_response(data)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        # Parse body
        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is True
        assert body["data"] == data
        assert body["meta"] == {}
        assert "timestamp" in body
        # Verify timestamp is ISO 8601 format
        datetime.fromisoformat(body["timestamp"])

    def test_success_response_with_meta(self):
        """Test success response with metadata"""
        data = [1, 2, 3]
        meta = {"count": 3, "source": "test"}
        response = success_response(data, meta=meta)

        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is True
        assert body["data"] == data
        assert body["meta"] == meta

    def test_success_response_custom_status_code(self):
        """Test success response with custom status code"""
        data = {"created": True}
        response = success_response(data, status_code=201)

        assert response.status_code == 201

        import json
        body = json.loads(response.body.decode())
        assert body["ok"] is True

    def test_success_response_empty_data(self):
        """Test success response with empty data"""
        response = success_response([])

        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is True
        assert body["data"] == []


class TestErrorResponse:
    """Tests for error_response()"""

    def test_error_response_basic(self):
        """Test basic error response"""
        response = error_response("Something went wrong")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is False
        assert body["error"] == "Something went wrong"
        assert body["details"] == {}
        assert "timestamp" in body

    def test_error_response_with_code(self):
        """Test error response with custom status code"""
        response = error_response("Not found", code=404)

        assert response.status_code == 404

        import json
        body = json.loads(response.body.decode())
        assert body["ok"] is False
        assert body["error"] == "Not found"

    def test_error_response_with_details(self):
        """Test error response with details"""
        details = {"field": "email", "reason": "invalid format"}
        response = error_response("Validation failed", code=400, details=details)

        assert response.status_code == 400

        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is False
        assert body["error"] == "Validation failed"
        assert body["details"] == details


class TestPaginatedResponse:
    """Tests for paginated_response()"""

    def test_paginated_response_basic(self):
        """Test basic paginated response"""
        items = [1, 2, 3, 4, 5]
        response = paginated_response(items=items, total=100, page=1, page_size=5)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        import json
        body = json.loads(response.body.decode())

        assert body["ok"] is True
        assert body["data"] == items
        assert "pagination" in body["meta"]

        pagination = body["meta"]["pagination"]
        assert pagination["total"] == 100
        assert pagination["page"] == 1
        assert pagination["page_size"] == 5
        assert pagination["total_pages"] == 20
        assert pagination["has_next"] is True
        assert pagination["has_prev"] is False

    def test_paginated_response_last_page(self):
        """Test paginated response on last page"""
        items = [96, 97, 98, 99, 100]
        response = paginated_response(items=items, total=100, page=20, page_size=5)

        import json
        body = json.loads(response.body.decode())

        pagination = body["meta"]["pagination"]
        assert pagination["has_next"] is False
        assert pagination["has_prev"] is True

    def test_paginated_response_middle_page(self):
        """Test paginated response on middle page"""
        items = [11, 12, 13, 14, 15]
        response = paginated_response(items=items, total=100, page=3, page_size=5)

        import json
        body = json.loads(response.body.decode())

        pagination = body["meta"]["pagination"]
        assert pagination["has_next"] is True
        assert pagination["has_prev"] is True

    def test_paginated_response_with_extra_meta(self):
        """Test paginated response with additional metadata"""
        items = [1, 2, 3]
        extra_meta = {"source": "test", "cached": True}
        response = paginated_response(
            items=items,
            total=100,
            page=1,
            page_size=3,
            meta=extra_meta
        )

        import json
        body = json.loads(response.body.decode())

        assert "pagination" in body["meta"]
        assert body["meta"]["source"] == "test"
        assert body["meta"]["cached"] is True

    def test_paginated_response_total_pages_calculation(self):
        """Test ceiling division for total_pages"""
        # 100 items, 7 per page = 15 pages (ceiling of 100/7 = 14.28)
        response = paginated_response(items=[], total=100, page=1, page_size=7)

        import json
        body = json.loads(response.body.decode())

        pagination = body["meta"]["pagination"]
        assert pagination["total_pages"] == 15  # ceil(100/7) = 15


class TestLegacyResponse:
    """Tests for legacy_response()"""

    def test_legacy_response_basic(self):
        """Test basic legacy response"""
        items = [{"symbol": "BTC", "balance": 1.5}]
        response = legacy_response("cointracking", items)

        assert isinstance(response, dict)
        assert response["source_used"] == "cointracking"
        assert response["items"] == items
        assert "warnings" not in response
        assert "error" not in response

    def test_legacy_response_with_warnings(self):
        """Test legacy response with warnings"""
        items = [{"symbol": "ETH"}]
        warnings = ["Data is stale", "Some prices missing"]
        response = legacy_response("saxobank", items, warnings=warnings)

        assert response["source_used"] == "saxobank"
        assert response["items"] == items
        assert response["warnings"] == warnings

    def test_legacy_response_with_error(self):
        """Test legacy response with error"""
        items = []
        response = legacy_response("cointracking_api", items, error="API timeout")

        assert response["source_used"] == "cointracking_api"
        assert response["items"] == []
        assert response["error"] == "API timeout"

    def test_legacy_response_with_warnings_and_error(self):
        """Test legacy response with both warnings and error"""
        items = []
        warnings = ["Fallback data used"]
        response = legacy_response(
            "stub_conservative",
            items,
            warnings=warnings,
            error="No real data available"
        )

        assert response["source_used"] == "stub_conservative"
        assert response["warnings"] == warnings
        assert response["error"] == "No real data available"


class TestStandardResponseModel:
    """Tests for StandardResponse Pydantic model"""

    def test_standard_response_model_success(self):
        """Test StandardResponse model for success case"""
        response = StandardResponse(
            ok=True,
            data={"balance": 1000},
            meta={"currency": "USD"},
            timestamp="2025-10-20T10:30:00"
        )

        assert response.ok is True
        assert response.data == {"balance": 1000}
        assert response.meta == {"currency": "USD"}
        assert response.error is None
        assert response.details is None

    def test_standard_response_model_error(self):
        """Test StandardResponse model for error case"""
        response = StandardResponse(
            ok=False,
            error="Not found",
            details={"user_id": "invalid"},
            timestamp="2025-10-20T10:30:00"
        )

        assert response.ok is False
        assert response.error == "Not found"
        assert response.details == {"user_id": "invalid"}
        assert response.data is None
        assert response.meta is None
