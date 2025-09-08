#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Middleware pour gestion d'erreur améliorée

Ce module fournit des middlewares pour une gestion d'erreur
centralisée et améliorée dans l'application FastAPI.
"""

import logging
import time
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    from shared.exceptions import (
        CryptoRebalancerException, 
        ErrorCode,
        APIException,
        NetworkException,
        PricingException,
        ExchangeException,
        DataException,
        TimeoutException,
        convert_standard_exception
    )
except ImportError:
    # Fallback si les modules ne sont pas disponibles
    logger.warning("Could not import custom exceptions, using basic error handling")
    CryptoRebalancerException = APIException = NetworkException = None
    PricingException = ExchangeException = DataException = TimeoutException = None
    ErrorCode = convert_standard_exception = None

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware pour gestion centralisée des erreurs"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Logger les requêtes lentes
            process_time = time.time() - start_time
            if process_time > 5.0:  # Plus de 5 secondes
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {process_time:.2f}s"
                )
            
            return response
            
        except HTTPException:
            # Les HTTPException de FastAPI passent directement
            raise
            
        except Exception as exc:
            # Conversion et gestion des autres exceptions
            process_time = time.time() - start_time
            
            # Logger l'erreur avec contexte
            logger.error(
                f"Error in {request.method} {request.url.path}: {str(exc)}",
                extra={
                    'method': request.method,
                    'path': str(request.url.path),
                    'query_params': dict(request.query_params),
                    'process_time': process_time,
                    'client_host': request.client.host if request.client else None
                },
                exc_info=True
            )
            
            # Conversion en exception personnalisée si disponible
            if convert_standard_exception:
                try:
                    custom_exc = convert_standard_exception(exc, f"{request.method} {request.url.path}")
                    return self._create_error_response(custom_exc, request)
                except Exception as conversion_error:
                    logger.error(f"Error converting exception: {conversion_error}")
            
            # Fallback vers réponse d'erreur générique
            return self._create_generic_error_response(exc, request)
    
    def _create_error_response(self, exc: 'CryptoRebalancerException', request: Request) -> JSONResponse:
        """Créer une réponse d'erreur structurée pour les exceptions personnalisées"""
        
        # Déterminer le code de statut HTTP
        if isinstance(exc, (NetworkException, TimeoutException)):
            status_code = 503  # Service Unavailable
        elif isinstance(exc, PricingException):
            status_code = 502  # Bad Gateway (source externe)
        elif isinstance(exc, DataException):
            status_code = 422  # Unprocessable Entity
        elif isinstance(exc, ExchangeException):
            status_code = 503  # Service Unavailable
        elif isinstance(exc, APIException):
            status_code = 502  # Bad Gateway
        else:
            status_code = 500  # Internal Server Error
        
        error_response = {
            "error": True,
            "message": exc.message,
            "error_code": exc.error_code.value if exc.error_code else "UNKNOWN_ERROR",
            "details": exc.details,
            "path": str(request.url.path),
            "method": request.method
        }
        
        # En mode debug, inclure plus de détails
        try:
            from config import get_settings
            if get_settings().is_debug_enabled():
                error_response["debug"] = {
                    "cause": str(exc.cause) if exc.cause else None,
                    "exception_type": type(exc).__name__
                }
        except Exception:
            pass  # Ignorer les erreurs de configuration en mode dégradé
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )
    
    def _create_generic_error_response(self, exc: Exception, request: Request) -> JSONResponse:
        """Créer une réponse d'erreur générique pour les exceptions non personnalisées"""
        
        # Déterminer le type d'erreur et le code de statut
        if isinstance(exc, (ConnectionError, OSError)):
            status_code = 503
            error_type = "NETWORK_ERROR"
        elif isinstance(exc, TimeoutError):
            status_code = 504
            error_type = "TIMEOUT_ERROR"
        elif isinstance(exc, (ValueError, TypeError, KeyError)):
            status_code = 422
            error_type = "DATA_ERROR"
        elif isinstance(exc, ImportError):
            status_code = 500
            error_type = "CONFIGURATION_ERROR"
        else:
            status_code = 500
            error_type = "INTERNAL_ERROR"
        
        error_response = {
            "error": True,
            "message": "An error occurred while processing your request",
            "error_code": error_type,
            "path": str(request.url.path),
            "method": request.method
        }
        
        # En mode debug, inclure plus de détails
        try:
            from config import get_settings
            if get_settings().is_debug_enabled():
                error_response["debug"] = {
                    "original_error": str(exc),
                    "exception_type": type(exc).__name__
                }
        except Exception:
            # En mode dégradé, toujours inclure quelques détails
            error_response["debug"] = {
                "original_error": str(exc),
                "exception_type": type(exc).__name__
            }
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logging des requêtes"""
    
    def __init__(self, app, log_level: str = "INFO"):
        super().__init__(app)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Logger la requête entrante
        if logger.isEnabledFor(self.log_level):
            logger.log(
                self.log_level,
                f"Request: {request.method} {request.url.path}",
                extra={
                    'method': request.method,
                    'path': str(request.url.path),
                    'query_params': dict(request.query_params),
                    'client_host': request.client.host if request.client else None
                }
            )
        
        try:
            response = await call_next(request)
        except Exception as exc:
            # Logger l'erreur et la relancer
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"({process_time:.3f}s): {str(exc)}"
            )
            raise
        
        # Logger la réponse
        process_time = time.time() - start_time
        if logger.isEnabledFor(self.log_level):
            logger.log(
                self.log_level,
                f"Response: {request.method} {request.url.path} "
                f"-> {response.status_code} ({process_time:.3f}s)"
            )
        
        # Ajouter le temps de traitement aux headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting simple en mémoire par IP.

    Utilise un compteur glissant par fenêtre (par défaut 1h) défini par:
      - settings.security.rate_limit_requests
      - settings.security.rate_limit_window_sec

    Ajoute les headers: X-RateLimit-Limit, X-RateLimit-Remaining, Retry-After (si bloqué)
    """

    def __init__(self, app):
        super().__init__(app)
        from config import get_settings
        s = get_settings().security
        self.limit = max(int(s.rate_limit_requests or 0), 0)
        self.window = max(int(s.rate_limit_window_sec or 3600), 1)
        # store: ip -> {"start": ts, "count": n}
        self._buckets = defaultdict(lambda: {"start": 0, "count": 0})
        # Paths exclus (statique/santé)
        self._exempt_prefixes = ("/static/", "/data/", "/health", "/healthz")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Pas de rate limit si disabled
        if self.limit <= 0:
            return await call_next(request)

        path = request.url.path or ""
        if any(path.startswith(p) for p in self._exempt_prefixes):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = int(time.time())
        bucket = self._buckets[ip]

        # Nouvelle fenêtre
        if bucket["start"] == 0 or now - bucket["start"] >= self.window:
            bucket["start"] = now
            bucket["count"] = 0

        bucket["count"] += 1
        remaining = max(self.limit - bucket["count"], 0)

        if bucket["count"] > self.limit:
            retry_after = self.window - (now - bucket["start"]) if bucket["start"] else self.window
            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "message": "Too Many Requests",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
