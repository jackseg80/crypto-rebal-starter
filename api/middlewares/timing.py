"""
Request timing middleware.

Extracted from api/main.py (lines 362-392) as part of refactoring effort.
Provides request timing and structured JSON logging.
"""

import json
import logging
import time
from time import monotonic
from fastapi import Request
from fastapi.responses import Response
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def request_timing_middleware(request: Request, call_next) -> Response:
    """
    Add request timing and structured logging.

    Measures request processing time and logs requests in JSON format.
    Adds X-Process-Time header to responses.

    Logging behavior:
    - Development: Log all requests
    - Production: Log only errors (4xx/5xx) or slow requests (>1s)

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response with X-Process-Time header added
    """
    start_time = monotonic()

    response = await call_next(request)

    # Calculate processing time
    process_time = monotonic() - start_time

    # Structured JSON log record
    log_record = {
        "ts": time.time(),
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(process_time * 1000, 2),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "")
    }

    # Log based on environment and response status
    if settings.is_debug_enabled():
        # Development: log everything
        logger.info(json.dumps(log_record, ensure_ascii=False))
    else:
        # Production: log only important requests or errors
        if response.status_code >= 400 or process_time > 1.0:
            logger.info(json.dumps(log_record, ensure_ascii=False))

    # Add timing header
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    return response
