#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Error Handling Utilities - Utilitaires pour gestion d'erreur

Ce module fournit des fonctions utilitaires pour remplacer
les try/except génériques par une gestion d'erreur spécifique.
"""

import logging
from typing import Any, Optional, Callable, TypeVar, Union
from functools import wraps

from .exceptions import (
    CryptoRebalancerException, 
    convert_standard_exception,
    APIException,
    NetworkException,
    DataException,
    PricingException,
    ExchangeException,
    TimeoutException
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

def safe_import(module_name: str, package: str = None, fallback_module: str = None) -> Any:
    """Import sécurisé avec fallback"""
    try:
        if package:
            module = __import__(f"{package}.{module_name}", fromlist=[module_name])
        else:
            module = __import__(module_name)
        logger.debug(f"Successfully imported {module_name}")
        return module
    except ImportError as e:
        logger.warning(f"Could not import {module_name}: {e}")
        
        if fallback_module:
            try:
                fallback = __import__(fallback_module)
                logger.info(f"Using fallback import {fallback_module}")
                return fallback
            except ImportError as fallback_error:
                logger.error(f"Fallback import {fallback_module} also failed: {fallback_error}")
        
        logger.error(f"All import attempts failed for {module_name}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error importing {module_name}: {e}")
        return None

def safe_call(
    func: Callable[[], T], 
    default: T = None, 
    context: str = None,
    expected_exceptions: tuple = None,
    log_level: str = "warning"
) -> T:
    """Exécution sécurisée d'une fonction avec gestion d'erreur spécifique"""
    try:
        return func()
    except Exception as e:
        # Gestion spécifique selon le type d'exception attendue
        if expected_exceptions and isinstance(e, expected_exceptions):
            getattr(logger, log_level)(f"Expected exception in {context or 'safe_call'}: {e}")
        else:
            # Conversion en exception personnalisée pour logging approprié
            converted = convert_standard_exception(e, context)
            getattr(logger, log_level)(f"Exception in {context or 'safe_call'}: {converted}")
        
        return default

async def safe_call_async(
    func: Callable[[], T], 
    default: T = None, 
    context: str = None,
    expected_exceptions: tuple = None,
    log_level: str = "warning"
) -> T:
    """Version async de safe_call"""
    try:
        return await func()
    except Exception as e:
        if expected_exceptions and isinstance(e, expected_exceptions):
            getattr(logger, log_level)(f"Expected exception in {context or 'safe_call_async'}: {e}")
        else:
            converted = convert_standard_exception(e, context)
            getattr(logger, log_level)(f"Exception in {context or 'safe_call_async'}: {converted}")
        
        return default

def safe_get_data(
    data_source: Callable[[], Any], 
    fallback: Any = None,
    context: str = None
) -> Any:
    """Récupération sécurisée de données avec fallback"""
    try:
        result = data_source()
        if result is None:
            logger.info(f"Data source returned None for {context}")
            return fallback
        return result
    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"Data retrieval error for {context}: {e}")
        return fallback
    except Exception as e:
        converted = convert_standard_exception(e, f"data retrieval for {context}")
        logger.error(f"Unexpected error in data retrieval: {converted}")
        return fallback

def safe_api_call(
    api_func: Callable[[], T], 
    api_name: str,
    default: T = None,
    retry_count: int = 0
) -> T:
    """Appel API sécurisé avec gestion des erreurs spécifiques"""
    for attempt in range(retry_count + 1):
        try:
            result = api_func()
            if result is not None:
                return result
            logger.warning(f"API {api_name} returned None (attempt {attempt + 1})")
        except Exception as e:
            if attempt < retry_count:
                logger.warning(f"API {api_name} failed (attempt {attempt + 1}/{retry_count + 1}): {e}")
                continue
            else:
                # Dernier essai, logger l'erreur appropriée
                if isinstance(e, (ConnectionError, OSError)):
                    raise NetworkException(f"Network error calling {api_name}: {str(e)}", cause=e)
                elif isinstance(e, TimeoutError):
                    raise TimeoutException(f"API call to {api_name}", 30, cause=e)
                else:
                    raise APIException(f"API call to {api_name} failed: {str(e)}", api_name, cause=e)
    
    return default

def safe_pricing_operation(
    operation: Callable[[], T], 
    symbol: str = None,
    source: str = None,
    default: T = None
) -> T:
    """Opération de pricing sécurisée"""
    try:
        return operation()
    except Exception as e:
        # Conversion spécifique pour les erreurs de pricing
        if isinstance(e, (ValueError, KeyError)):
            raise PricingException(
                f"Invalid pricing data for {symbol or 'unknown symbol'}", 
                symbol=symbol, 
                source=source, 
                cause=e
            )
        elif isinstance(e, (ConnectionError, OSError)):
            raise NetworkException(f"Network error fetching price for {symbol}: {str(e)}", cause=e)
        else:
            raise PricingException(
                f"Pricing operation failed: {str(e)}", 
                symbol=symbol, 
                source=source, 
                cause=e
            )

def error_handler(
    error_type: str = "generic",
    context: str = None,
    reraise: bool = True,
    default_return: Any = None
):
    """Décorateur pour gestion d'erreur spécifique par type"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CryptoRebalancerException:
                # Les exceptions personnalisées passent directement
                if reraise:
                    raise
                return default_return
            except Exception as e:
                # Conversion selon le type d'erreur attendu
                converted = convert_standard_exception(e, context or func.__name__)
                
                if reraise:
                    raise converted
                else:
                    logger.error(f"Handled exception in {func.__name__}: {converted}")
                    return default_return
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except CryptoRebalancerException:
                if reraise:
                    raise
                return default_return
            except Exception as e:
                converted = convert_standard_exception(e, context or func.__name__)
                
                if reraise:
                    raise converted
                else:
                    logger.error(f"Handled exception in {func.__name__}: {converted}")
                    return default_return
        
        # Retourner la version appropriée selon si c'est async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator

# Fonctions utilitaires spécifiques aux patterns du code existant
def safe_price_fetch(fetch_func: Callable[[], dict], symbols: list, source: str = "unknown") -> dict:
    """Récupération sécurisée des prix"""
    try:
        result = fetch_func()
        if not result or not isinstance(result, dict):
            logger.warning(f"Invalid price data format from {source}")
            return {}
        
        # Valider les données de prix
        valid_prices = {}
        for symbol, price in result.items():
            try:
                if price is not None and float(price) > 0:
                    valid_prices[symbol] = float(price)
                else:
                    logger.debug(f"Invalid price for {symbol}: {price}")
            except (ValueError, TypeError):
                logger.debug(f"Could not convert price for {symbol}: {price}")
        
        return valid_prices
        
    except Exception as e:
        raise PricingException(f"Price fetch failed from {source}: {str(e)}", source=source, cause=e)

def safe_exchange_operation(
    operation: Callable[[], T], 
    exchange: str,
    operation_type: str = "operation"
) -> T:
    """Opération d'exchange sécurisée"""
    try:
        return operation()
    except Exception as e:
        if isinstance(e, (ConnectionError, OSError)):
            raise ExchangeException(f"Connection error to {exchange}: {str(e)}", exchange, cause=e)
        elif isinstance(e, TimeoutError):
            raise TimeoutException(f"{operation_type} on {exchange}", 30, cause=e)
        else:
            raise ExchangeException(f"{operation_type} failed on {exchange}: {str(e)}", exchange, cause=e)