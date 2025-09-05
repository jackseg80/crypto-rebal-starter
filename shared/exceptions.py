#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exceptions personnalisées - Gestion d'erreur spécifique

Ce module définit les exceptions personnalisées pour une gestion
d'erreur précise et informative dans l'application.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class ErrorCode(Enum):
    """Codes d'erreur standardisés"""
    # Erreurs de configuration
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"
    
    # Erreurs d'API externe
    API_KEY_INVALID = "API_KEY_INVALID"
    API_RATE_LIMITED = "API_RATE_LIMITED"
    API_UNAVAILABLE = "API_UNAVAILABLE"
    API_TIMEOUT = "API_TIMEOUT"
    
    # Erreurs de données
    DATA_INVALID = "DATA_INVALID"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    DATA_STALE = "DATA_STALE"
    
    # Erreurs trading/exchange
    EXCHANGE_NOT_CONNECTED = "EXCHANGE_NOT_CONNECTED"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    ORDER_FAILED = "ORDER_FAILED"
    SYMBOL_NOT_SUPPORTED = "SYMBOL_NOT_SUPPORTED"
    
    # Erreurs de pricing
    PRICE_NOT_AVAILABLE = "PRICE_NOT_AVAILABLE"
    PRICE_SOURCE_ERROR = "PRICE_SOURCE_ERROR"
    
    # Erreurs système
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"

class CryptoRebalancerException(Exception):
    """Exception de base pour l'application crypto rebalancer"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
        
        # Logger l'exception
        logger.error(f"Exception: {error_code.value if error_code else 'UNKNOWN'} - {message}", 
                    extra={'details': details, 'cause': str(cause) if cause else None})

class ConfigurationError(CryptoRebalancerException):
    """Erreur de configuration"""
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(message, ErrorCode.CONFIG_INVALID, {'config_key': config_key}, **kwargs)

class APIException(CryptoRebalancerException):
    """Erreur d'API externe"""
    def __init__(self, message: str, api_name: str, status_code: int = None, **kwargs):
        super().__init__(message, ErrorCode.API_UNAVAILABLE, 
                        {'api_name': api_name, 'status_code': status_code}, **kwargs)

class RateLimitException(APIException):
    """Erreur de limite de taux API"""
    def __init__(self, api_name: str, retry_after: int = None, **kwargs):
        message = f"Rate limit exceeded for {api_name}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, api_name, **kwargs)
        self.error_code = ErrorCode.API_RATE_LIMITED
        self.retry_after = retry_after

class DataException(CryptoRebalancerException):
    """Erreur de données"""
    def __init__(self, message: str, data_source: str = None, **kwargs):
        super().__init__(message, ErrorCode.DATA_INVALID, {'data_source': data_source}, **kwargs)

class DataNotFoundException(DataException):
    """Données non trouvées"""
    def __init__(self, resource: str, identifier: str = None, **kwargs):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"
        super().__init__(message, **kwargs)
        self.error_code = ErrorCode.DATA_NOT_FOUND

class ExchangeException(CryptoRebalancerException):
    """Erreur d'exchange"""
    def __init__(self, message: str, exchange: str, **kwargs):
        super().__init__(message, ErrorCode.EXCHANGE_NOT_CONNECTED, {'exchange': exchange}, **kwargs)

class InsufficientBalanceException(ExchangeException):
    """Solde insuffisant"""
    def __init__(self, symbol: str, required: float, available: float, exchange: str, **kwargs):
        message = f"Insufficient balance for {symbol}. Required: {required}, Available: {available}"
        super().__init__(message, exchange, **kwargs)
        self.error_code = ErrorCode.INSUFFICIENT_BALANCE
        self.details.update({
            'symbol': symbol,
            'required': required,
            'available': available
        })

class PricingException(CryptoRebalancerException):
    """Erreur de pricing"""
    def __init__(self, message: str, symbol: str = None, source: str = None, **kwargs):
        super().__init__(message, ErrorCode.PRICE_NOT_AVAILABLE, 
                        {'symbol': symbol, 'source': source}, **kwargs)

class NetworkException(CryptoRebalancerException):
    """Erreur réseau"""
    def __init__(self, message: str, url: str = None, **kwargs):
        super().__init__(message, ErrorCode.NETWORK_ERROR, {'url': url}, **kwargs)

class TimeoutException(CryptoRebalancerException):
    """Erreur de timeout"""
    def __init__(self, operation: str, timeout_seconds: int, **kwargs):
        message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(message, ErrorCode.TIMEOUT_ERROR, 
                        {'operation': operation, 'timeout': timeout_seconds}, **kwargs)

# Fonction helper pour convertir des exceptions standards
def convert_standard_exception(exc: Exception, context: str = None) -> CryptoRebalancerException:
    """Convertir une exception standard en exception personnalisée"""
    
    if isinstance(exc, CryptoRebalancerException):
        return exc
    
    context_msg = f" during {context}" if context else ""
    
    # Erreurs réseau
    if isinstance(exc, (ConnectionError, OSError)):
        return NetworkException(f"Network error{context_msg}: {str(exc)}", cause=exc)
    
    # Timeouts
    if isinstance(exc, TimeoutError):
        return TimeoutException(context or "unknown operation", 30, cause=exc)
    
    # Erreurs d'import/configuration
    if isinstance(exc, ImportError):
        return ConfigurationError(f"Import error{context_msg}: {str(exc)}", cause=exc)
    
    # Erreurs de permission
    if isinstance(exc, PermissionError):
        return CryptoRebalancerException(
            f"Permission denied{context_msg}: {str(exc)}", 
            ErrorCode.PERMISSION_DENIED, 
            cause=exc
        )
    
    # Erreurs de données
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return DataException(f"Data error{context_msg}: {str(exc)}", cause=exc)
    
    # Autres erreurs génériques
    return CryptoRebalancerException(
        f"Unexpected error{context_msg}: {str(exc)}", 
        cause=exc
    )

# Décorateurs pour la gestion d'erreur
def handle_exceptions(context: str = None, reraise: bool = True):
    """Décorateur pour la gestion automatique d'exceptions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CryptoRebalancerException:
                if reraise:
                    raise
            except Exception as e:
                converted = convert_standard_exception(e, context or func.__name__)
                if reraise:
                    raise converted
                return converted
        return wrapper
    return decorator

async def handle_exceptions_async(context: str = None, reraise: bool = True):
    """Version async du décorateur de gestion d'exceptions"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CryptoRebalancerException:
                if reraise:
                    raise
            except Exception as e:
                converted = convert_standard_exception(e, context or func.__name__)
                if reraise:
                    raise converted
                return converted
        return wrapper
    return decorator