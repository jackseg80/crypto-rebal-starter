"""
Security headers middleware.

Extracted from api/main.py (lines 266-360) as part of refactoring effort.
Provides Content Security Policy and other security headers.
"""

import logging
from fastapi import Request
from fastapi.responses import Response
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def add_security_headers_middleware(request: Request, call_next) -> Response:
    """
    Add security headers to all HTTP responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: SAMEORIGIN
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    - Content-Security-Policy: (configurable via settings)
    - Strict-Transport-Security: (HTTPS only, production only)

    Args:
        request: FastAPI Request object
        call_next: Next middleware/endpoint in chain

    Returns:
        Response with security headers added
    """
    response = await call_next(request)

    # Essential security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Additional security headers
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    # Cache control for APIs (prevent caching sensitive data)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    # HSTS (HTTP Strict Transport Security) - production only
    is_production = settings.environment == "production"
    is_https = request.url.scheme == "https"
    if is_production and is_https:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

    # Content Security Policy via configuration
    try:
        _add_csp_headers(response, request)
    except Exception as e:
        # Don't block response on CSP config errors
        logger.warning(f"Failed to set CSP headers: {e}")

    # Debug headers (development only)
    if settings.is_debug_enabled():
        response.headers["X-Debug-Mode"] = "enabled"
        response.headers["X-App-Version"] = "1.0.0"

    return response


def _add_csp_headers(response: Response, request: Request) -> None:
    """
    Add Content Security Policy headers.

    Args:
        response: Response object to add headers to
        request: Request object (for path-based CSP rules)
    """
    sec = settings.security

    def _join(srcs):
        return " ".join(srcs or [])

    # Build CSP directives
    default_src = "'self'"
    script_src_list = list(sec.csp_script_src or [])
    style_src_list = list(sec.csp_style_src or [])
    img_src_list = list(sec.csp_img_src or [])
    connect_src_list = list(sec.csp_connect_src or [])
    font_src_list = list(getattr(sec, 'csp_font_src', ["'self'"]))
    media_src_list = list(getattr(sec, 'csp_media_src', ["'self'"]))

    # Development: allow http/https for local testing
    if settings.is_debug_enabled():
        for token in ("http:", "https:"):
            if token not in connect_src_list:
                connect_src_list.append(token)

    script_src = _join(script_src_list)
    style_src = _join(style_src_list)
    img_src = _join(img_src_list)
    connect_src = _join(connect_src_list)
    font_src = _join(font_src_list)
    media_src = _join(media_src_list)

    # Development: relax CSP for docs/redoc and static files
    path = request.url.path
    is_docs = path in ("/docs", "/redoc", "/openapi.json")
    is_static = str(path).startswith("/static/")

    if settings.is_debug_enabled() and (is_docs or is_static):
        if getattr(sec, 'csp_allow_inline_dev', True):
            if "'unsafe-inline'" not in script_src:
                script_src = (script_src + " 'unsafe-inline'").strip()
            if "'unsafe-eval'" not in script_src:
                script_src = (script_src + " 'unsafe-eval'").strip()
            if "'unsafe-inline'" not in style_src:
                style_src = (style_src + " 'unsafe-inline'").strip()

    # Frame ancestors
    frame_ancestors = _join(getattr(sec, 'csp_frame_ancestors', ["'self'"]))
    if not settings.is_debug_enabled() and not str(request.url.path).startswith("/static/"):
        # Production: prevent embedding non-static pages
        frame_ancestors = "'none'"

    # Complete CSP with all directives
    csp = (
        f"default-src {default_src}; "
        f"script-src {script_src}; "
        f"style-src {style_src}; "
        f"img-src {img_src}; "
        f"connect-src {connect_src}; "
        f"font-src {font_src}; "
        f"media-src {media_src}; "
        f"frame-ancestors {frame_ancestors}; "
        f"base-uri 'self'; "
        f"form-action 'self'; "
        f"object-src 'none'; "
        f"frame-src 'self'; "
        f"manifest-src 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
