"""
Centralized Error Handling System
==================================

Provides decorators and utilities for consistent error handling across the application.

Patterns:
---------
1. API Endpoints: Graceful degradation with fallback responses
2. Services: Silent failures with logging (continue execution)
3. Storage: Cascade fallback (Redis → File → Memory)
4. Critical: Log and re-raise (for debugging)

Usage:
------
```python
from shared.error_handlers import handle_api_errors, handle_service_errors

@handle_api_errors(fallback={"success": False, "data": []})
async def my_endpoint():
    # Endpoint code
    pass

@handle_service_errors(silent=True)
def my_service_method(self):
    # Service code that should continue even on errors
    pass
```
"""

from functools import wraps
from typing import Callable, Any, Dict, Optional, Union
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

# ===========================
# 1. API Endpoint Handler
# ===========================

def handle_api_errors(
    fallback: Optional[Dict[str, Any]] = None,
    log_level: str = "error",
    include_traceback: bool = False,
    reraise_http_errors: bool = True
):
    """
    Decorator for API endpoints with graceful degradation

    Returns fallback response on errors instead of raising exceptions.
    Always returns {"success": bool, "error": str, ...fallback}

    Args:
        fallback: Default response to return on error (merged with error info)
        log_level: Logging level for errors ("error", "warning", "critical")
        include_traceback: Whether to include full traceback in logs
        reraise_http_errors: Re-raise HTTPException (FastAPI) - default True

    Example:
        @handle_api_errors(fallback={"data": [], "count": 0})
        async def get_items():
            items = fetch_items()  # May raise
            return {"success": True, "data": items, "count": len(items)}

        # On error, returns:
        # {"success": False, "error": "...", "data": [], "count": 0}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Re-raise HTTPException for FastAPI
                if reraise_http_errors and _is_http_exception(e):
                    raise
                # Handle specific exceptions
                if isinstance(e, (FileNotFoundError, PermissionError)):
                    _log(log_level, f"File access error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"File access error: {e}", fallback)
                elif isinstance(e, (ValueError, TypeError, KeyError)):
                    _log(log_level, f"Data validation error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Invalid data: {e}", fallback)
                elif isinstance(e, (AttributeError, ImportError)):
                    _log(log_level, f"Module/attribute error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Configuration error: {e}", fallback)
                elif isinstance(e, RuntimeError):
                    _log(log_level, f"Runtime error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Operation failed: {e}", fallback)
                else:
                    _log("critical", f"Unexpected error in {func.__name__}: {e}", exc_info=True)
                    return _build_error_response(f"Unexpected error: {e}", fallback)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Re-raise HTTPException for FastAPI
                if reraise_http_errors and _is_http_exception(e):
                    raise
                # Handle specific exceptions
                if isinstance(e, (FileNotFoundError, PermissionError)):
                    _log(log_level, f"File access error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"File access error: {e}", fallback)
                elif isinstance(e, (ValueError, TypeError, KeyError)):
                    _log(log_level, f"Data validation error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Invalid data: {e}", fallback)
                elif isinstance(e, (AttributeError, ImportError)):
                    _log(log_level, f"Module/attribute error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Configuration error: {e}", fallback)
                elif isinstance(e, RuntimeError):
                    _log(log_level, f"Runtime error in {func.__name__}: {e}", include_traceback)
                    return _build_error_response(f"Operation failed: {e}", fallback)
                else:
                    _log("critical", f"Unexpected error in {func.__name__}: {e}", exc_info=True)
                    return _build_error_response(f"Unexpected error: {e}", fallback)

        # Return appropriate wrapper based on function type
        import inspect
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


def _is_http_exception(exc: Exception) -> bool:
    """Check if exception is FastAPI HTTPException"""
    exc_type_name = type(exc).__name__
    return exc_type_name == "HTTPException" or "HTTPException" in str(type(exc).__bases__)


def _build_error_response(error_msg: str, fallback: Optional[Dict] = None) -> Dict[str, Any]:
    """Build standardized error response"""
    response = {
        "success": False,
        "error": error_msg,
        "timestamp": datetime.now().isoformat()
    }
    if fallback:
        response.update(fallback)
    return response


# ===========================
# 2. Service Method Handler
# ===========================

def handle_service_errors(
    silent: bool = False,
    default_return: Any = None,
    log_level: str = "warning"
):
    """
    Decorator for service methods that should continue on errors

    Logs errors but doesn't raise. Useful for:
    - Optional feature checks (hasattr, getattr)
    - Degraded mode operations
    - Non-critical calculations

    Args:
        silent: If True, suppresses exception (returns default_return)
        default_return: Value to return on error if silent=True
        log_level: Logging level for errors

    Example:
        @handle_service_errors(silent=True, default_return=None)
        def get_optional_feature(self):
            # Check optional attribute
            return self.signals.blended_score  # May raise AttributeError

        # Returns None if attribute missing, no exception raised
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AttributeError as e:
                _log(log_level, f"Attribute not found in {func.__name__}: {e}")
                if silent:
                    return default_return
                raise
            except (ValueError, TypeError) as e:
                _log(log_level, f"Invalid value in {func.__name__}: {e}")
                if silent:
                    return default_return
                raise
            except Exception as e:
                _log("error", f"Error in {func.__name__}: {e}", exc_info=True)
                if silent:
                    return default_return
                raise

        return wrapper

    return decorator


# ===========================
# 3. Storage Operation Handler
# ===========================

def handle_storage_errors(
    operation: str = "storage",
    reraise: bool = False
):
    """
    Decorator for storage operations (Redis, File, Database)

    Handles storage-specific exceptions gracefully.

    Args:
        operation: Name of operation for logging
        reraise: Whether to re-raise exceptions after logging

    Example:
        @handle_storage_errors(operation="redis_write")
        def write_to_redis(self, key, value):
            self.redis.set(key, value)
            return True

        # Catches redis.RedisError, logs it, returns False
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ImportError as e:
                # Redis/storage module not available
                logger.warning(f"{operation} module not available: {e}")
                if reraise:
                    raise
                return False
            except (FileNotFoundError, PermissionError, IOError) as e:
                logger.error(f"{operation} file access error in {func.__name__}: {e}")
                if reraise:
                    raise
                return False
            except Exception as e:
                # Catch redis.RedisError, json.JSONDecodeError, etc.
                if "redis" in str(type(e)).lower():
                    logger.error(f"{operation} Redis error in {func.__name__}: {e}")
                elif "json" in str(type(e)).lower():
                    logger.error(f"{operation} JSON error in {func.__name__}: {e}")
                else:
                    logger.error(f"{operation} storage error in {func.__name__}: {e}", exc_info=True)

                if reraise:
                    raise
                return False

        return wrapper

    return decorator


# ===========================
# 4. Critical Path Handler
# ===========================

def handle_critical_errors(
    context: str = "",
    always_reraise: bool = True
):
    """
    Decorator for critical paths that MUST NOT fail silently

    Logs with CRITICAL level and re-raises by default.
    Use for:
    - Startup initialization
    - Database connections
    - Configuration loading

    Args:
        context: Additional context for error message
        always_reraise: Always re-raise exceptions (default: True)

    Example:
        @handle_critical_errors(context="app_startup")
        def initialize_database():
            # Critical initialization
            db.connect()

        # Logs CRITICAL and re-raises any exception
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"CRITICAL ERROR in {func.__name__}"
                if context:
                    error_msg += f" ({context})"
                error_msg += f": {e}"

                logger.critical(error_msg, exc_info=True)

                if always_reraise:
                    raise
                return None

        return wrapper

    return decorator


# ===========================
# Utilities
# ===========================

def _log(level: str, message: str, include_traceback: bool = False, exc_info: bool = False):
    """Internal logging helper"""
    log_func = getattr(logger, level.lower(), logger.error)

    if include_traceback or exc_info:
        log_func(message, exc_info=True)
    else:
        log_func(message)


# ===========================
# Context Manager for Blocks
# ===========================

class suppress_errors:
    """
    Context manager to suppress errors in code blocks

    Example:
        with suppress_errors(log_level="warning"):
            risky_operation()
            another_risky_operation()
        # Continues even if operations fail
    """
    def __init__(self, log_level: str = "warning", return_value: Any = None):
        self.log_level = log_level
        self.return_value = return_value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            _log(self.log_level, f"Suppressed error: {exc_val}")
            return True  # Suppress exception
        return False
