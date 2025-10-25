"""
Unit tests for shared/error_handlers.py

Tests all 4 handler types:
1. handle_api_errors - API endpoints with graceful fallbacks
2. handle_service_errors - Service methods with silent failures
3. handle_storage_errors - Storage operations with cascade fallback
4. handle_critical_errors - Critical paths that must not fail silently
"""

import pytest
import asyncio
from datetime import datetime
from shared.error_handlers import (
    handle_api_errors,
    handle_service_errors,
    handle_storage_errors,
    handle_critical_errors,
    suppress_errors
)


# ===========================
# 1. API Error Handler Tests
# ===========================

class TestHandleApiErrors:
    """Test handle_api_errors decorator"""

    def test_sync_success(self):
        """Test sync function succeeds normally"""
        @handle_api_errors(fallback={"data": []})
        def get_items():
            return {"success": True, "data": [1, 2, 3]}

        result = get_items()
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_async_success(self):
        """Test async function succeeds normally"""
        @handle_api_errors(fallback={"data": []})
        async def get_items_async():
            await asyncio.sleep(0.001)
            return {"success": True, "data": [1, 2, 3]}

        result = await get_items_async()
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    def test_file_not_found_error(self):
        """Test FileNotFoundError handling"""
        @handle_api_errors(fallback={"data": [], "count": 0})
        def load_file():
            raise FileNotFoundError("file.txt not found")

        result = load_file()
        assert result["success"] is False
        assert "File access error" in result["error"]
        assert result["data"] == []
        assert result["count"] == 0

    def test_value_error(self):
        """Test ValueError handling"""
        @handle_api_errors(fallback={"value": None})
        def parse_value():
            raise ValueError("Invalid format")

        result = parse_value()
        assert result["success"] is False
        assert "Invalid data" in result["error"]
        assert result["value"] is None

    def test_attribute_error(self):
        """Test AttributeError handling"""
        @handle_api_errors(fallback={"config": {}})
        def get_config():
            obj = object()
            return obj.missing_attribute

        result = get_config()
        assert result["success"] is False
        assert "Configuration error" in result["error"]
        assert result["config"] == {}

    def test_runtime_error(self):
        """Test RuntimeError handling"""
        @handle_api_errors(fallback={"status": "failed"})
        def run_operation():
            raise RuntimeError("Operation failed")

        result = run_operation()
        assert result["success"] is False
        assert "Operation failed" in result["error"]
        assert result["status"] == "failed"

    def test_unexpected_exception(self):
        """Test unexpected exception handling"""
        @handle_api_errors(fallback={"safe": True})
        def dangerous_operation():
            raise ConnectionError("Network issue")

        result = dangerous_operation()
        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert result["safe"] is True

    def test_no_fallback(self):
        """Test without fallback data"""
        @handle_api_errors()
        def failing_function():
            raise ValueError("Error")

        result = failing_function()
        assert result["success"] is False
        assert "error" in result
        assert "timestamp" in result


# ===========================
# 2. Service Error Handler Tests
# ===========================

class TestHandleServiceErrors:
    """Test handle_service_errors decorator"""

    def test_silent_success(self):
        """Test silent mode returns default on error"""
        @handle_service_errors(silent=True, default_return=None)
        def get_optional_value():
            raise AttributeError("Missing attribute")

        result = get_optional_value()
        assert result is None

    def test_silent_with_custom_default(self):
        """Test silent mode with custom default"""
        @handle_service_errors(silent=True, default_return={"default": True})
        def get_value():
            raise ValueError("Invalid")

        result = get_value()
        assert result == {"default": True}

    def test_non_silent_reraises(self):
        """Test non-silent mode re-raises exceptions"""
        @handle_service_errors(silent=False)
        def failing_function():
            raise RuntimeError("Critical error")

        with pytest.raises(RuntimeError, match="Critical error"):
            failing_function()

    def test_attribute_error_silent(self):
        """Test AttributeError in silent mode"""
        @handle_service_errors(silent=True, default_return=0)
        def check_attribute():
            obj = object()
            return obj.missing

        result = check_attribute()
        assert result == 0

    def test_value_error_silent(self):
        """Test ValueError in silent mode"""
        @handle_service_errors(silent=True, default_return=[])
        def parse_data():
            int("not_a_number")

        result = parse_data()
        assert result == []


# ===========================
# 3. Storage Error Handler Tests
# ===========================

class TestHandleStorageErrors:
    """Test handle_storage_errors decorator"""

    def test_success_returns_true(self):
        """Test successful storage operation"""
        @handle_storage_errors(operation="test_write")
        def write_data():
            return True

        result = write_data()
        assert result is True

    def test_file_not_found_returns_false(self):
        """Test FileNotFoundError returns False"""
        @handle_storage_errors(operation="file_read")
        def read_file():
            raise FileNotFoundError("file.json")

        result = read_file()
        assert result is False

    def test_permission_error_returns_false(self):
        """Test PermissionError returns False"""
        @handle_storage_errors(operation="file_write")
        def write_file():
            raise PermissionError("Access denied")

        result = write_file()
        assert result is False

    def test_io_error_returns_false(self):
        """Test IOError returns False"""
        @handle_storage_errors(operation="disk_write")
        def write_to_disk():
            raise IOError("Disk full")

        result = write_to_disk()
        assert result is False

    def test_import_error_returns_false(self):
        """Test ImportError (redis not available) returns False"""
        @handle_storage_errors(operation="redis_connect")
        def connect_redis():
            raise ImportError("redis module not found")

        result = connect_redis()
        assert result is False

    def test_reraise_mode(self):
        """Test reraise=True re-raises exceptions"""
        @handle_storage_errors(operation="critical_write", reraise=True)
        def critical_write():
            raise FileNotFoundError("Critical file missing")

        with pytest.raises(FileNotFoundError):
            critical_write()

    def test_generic_exception_returns_false(self):
        """Test generic Exception returns False"""
        @handle_storage_errors(operation="generic_op")
        def generic_operation():
            raise Exception("Something went wrong")

        result = generic_operation()
        assert result is False


# ===========================
# 4. Critical Error Handler Tests
# ===========================

class TestHandleCriticalErrors:
    """Test handle_critical_errors decorator"""

    def test_always_reraise_by_default(self):
        """Test critical errors always re-raise by default"""
        @handle_critical_errors(context="startup")
        def initialize():
            raise RuntimeError("Initialization failed")

        with pytest.raises(RuntimeError, match="Initialization failed"):
            initialize()

    def test_no_reraise_returns_none(self):
        """Test no reraise returns None"""
        @handle_critical_errors(context="optional_init", always_reraise=False)
        def optional_init():
            raise ValueError("Config error")

        result = optional_init()
        assert result is None

    def test_successful_execution(self):
        """Test successful execution returns normally"""
        @handle_critical_errors(context="test")
        def successful_function():
            return {"initialized": True}

        result = successful_function()
        assert result == {"initialized": True}


# ===========================
# 5. Context Manager Tests
# ===========================

class TestSuppressErrors:
    """Test suppress_errors context manager"""

    def test_suppresses_exception(self):
        """Test exception is suppressed"""
        with suppress_errors():
            raise ValueError("This should be suppressed")
        # No exception raised, test passes

    def test_allows_normal_execution(self):
        """Test normal execution continues"""
        result = None
        with suppress_errors():
            result = 42
        assert result == 42

    def test_custom_log_level(self):
        """Test custom log level doesn't crash"""
        with suppress_errors(log_level="critical"):
            raise RuntimeError("Critical error")
        # No exception raised, test passes


# ===========================
# Integration Tests
# ===========================

class TestIntegration:
    """Integration tests combining multiple handlers"""

    @pytest.mark.asyncio
    async def test_api_endpoint_with_storage(self):
        """Test API endpoint calling storage operations"""

        @handle_storage_errors(operation="cache_write")
        def write_to_cache(key, value):
            # Simulate storage failure
            raise IOError("Cache unavailable")

        @handle_api_errors(fallback={"cached": False})
        async def api_endpoint():
            await asyncio.sleep(0.001)
            success = write_to_cache("key", "value")
            if not success:
                return {"success": True, "cached": False, "note": "Cache unavailable"}
            return {"success": True, "cached": True}

        result = await api_endpoint()
        assert result["success"] is True
        assert result["cached"] is False

    def test_service_with_optional_features(self):
        """Test service checking optional features"""

        class MyService:
            @handle_service_errors(silent=True, default_return=None)
            def get_optional_score(self):
                # Attribute doesn't exist
                return self.signals.blended_score

            @handle_api_errors(fallback={"score": 0})
            def get_score_with_fallback(self):
                score = self.get_optional_score()
                if score is None:
                    return {"success": False, "score": 0, "note": "Score unavailable"}
                return {"success": True, "score": score}

        service = MyService()
        result = service.get_score_with_fallback()
        assert result["success"] is False
        assert result["score"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
