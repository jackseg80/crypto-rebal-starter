"""
Exceptions personnalisées pour l'API crypto-rebalancer
"""
from typing import Any, Optional
from fastapi import HTTPException


class CryptoRebalancerException(Exception):
    """Exception de base pour l'application"""
    def __init__(self, message: str, details: Optional[Any] = None):
        self.message = message
        self.details = details
        super().__init__(message)


class APIException(CryptoRebalancerException):
    """Exception pour les erreurs d'API externe"""
    def __init__(self, service: str, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} API Error: {message}", details)


class ValidationException(CryptoRebalancerException):
    """Exception pour les erreurs de validation"""
    def __init__(self, field: str, message: str, value: Optional[Any] = None):
        self.field = field
        self.value = value
        super().__init__(f"Validation error on {field}: {message}", {"field": field, "value": value})


class ConfigurationException(CryptoRebalancerException):
    """Exception pour les erreurs de configuration"""
    pass


class TradingException(CryptoRebalancerException):
    """Exception pour les erreurs de trading/rebalancing"""
    def __init__(self, operation: str, message: str, details: Optional[Any] = None):
        self.operation = operation
        super().__init__(f"Trading error in {operation}: {message}", details)


class DataException(CryptoRebalancerException):
    """Exception pour les erreurs de données"""
    def __init__(self, source: str, message: str, details: Optional[Any] = None):
        self.source = source
        super().__init__(f"Data error from {source}: {message}", details)


# Convertisseurs pour FastAPI
def create_http_exception(exc: CryptoRebalancerException, status_code: int = 400) -> HTTPException:
    """Convertit une exception personnalisée en HTTPException"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )


# Codes d'erreur standards
class ErrorCodes:
    # API Errors (500-599)
    API_UNAVAILABLE = 500
    API_TIMEOUT = 503
    API_RATE_LIMIT = 429
    
    # Validation Errors (400-499)
    INVALID_INPUT = 400
    MISSING_PARAMETER = 422
    INVALID_FORMAT = 400
    
    # Configuration Errors (500-599)
    MISSING_CONFIG = 500
    INVALID_CONFIG = 500
    
    # Trading Errors (400-499)
    INSUFFICIENT_BALANCE = 400
    INVALID_SYMBOL = 400
    MARKET_CLOSED = 400
    
    # Data Errors (500-599)
    DATA_NOT_FOUND = 404
    DATA_CORRUPT = 500