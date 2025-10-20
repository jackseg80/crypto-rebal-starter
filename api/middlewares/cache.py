"""
Cache control middleware for development.

Extracted from api/main.py (lines 475-488) as part of refactoring effort.
Disables browser caching for static files in development mode.
"""

import logging
from fastapi import Request
from fastapi.responses import Response
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def no_cache_dev_middleware(request: Request, call_next) -> Response:
    """
    Disable browser caching for static files in development.

    Prevents browser from caching HTML/CSS/JS files during development,
    ensuring latest changes are always loaded.

    Only active in DEBUG mode.

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response with no-cache headers added (if applicable)
    """
    response = await call_next(request)

    # Only in DEBUG mode, disable cache for static files
    if settings.is_debug_enabled() and request.url.path.startswith("/static"):
        # Check if it's an HTML, CSS or JS file
        if any(request.url.path.endswith(ext) for ext in [".html", ".css", ".js"]):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

    return response
