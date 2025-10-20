"""
Request logging middleware (development only).

Extracted from api/main.py (lines 453-473) as part of refactoring effort.
Provides lightweight request tracing for debugging.
"""

import logging
from time import monotonic
from fastapi import Request
from fastapi.responses import Response
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def request_logger_middleware(request: Request, call_next) -> Response:
    """
    Lightweight request tracer for development/debugging.

    Activated when:
    - Debug mode enabled
    - Log level is DEBUG
    - X-Debug-Trace: 1 header present

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response (unchanged)
    """
    trace_header = request.headers.get("x-debug-trace", "0")
    log_level = settings.logging.log_level

    do_trace = (
        settings.is_debug_enabled() or
        log_level == "DEBUG" or
        trace_header == "1"
    )

    start = monotonic() if do_trace else 0
    response = None

    try:
        response = await call_next(request)
        return response
    finally:
        if do_trace:
            duration_ms = int((monotonic() - start) * 1000)
            status_code = getattr(response, "status_code", "?") if response else "error"
            logger.info(
                "%s %s -> %s (%d ms)",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
