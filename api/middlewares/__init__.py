"""
Modularized middlewares extracted from api/main.py.

This package contains HTTP middlewares organized by responsibility for better
maintainability and testability.

Extracted from api/main.py (lines 266-488) as part of refactoring to reduce
file size from 1,603 → <500 lines.

Note: The original api/middleware.py file contains RateLimitMiddleware and
ErrorHandlingMiddleware which remain separate to avoid migration complexity.
"""

from .security import add_security_headers_middleware
from .timing import request_timing_middleware
from .logging import request_logger_middleware
from .cache import no_cache_dev_middleware

__all__ = [
    "add_security_headers_middleware",
    "request_timing_middleware",
    "request_logger_middleware",
    "no_cache_dev_middleware",
]
