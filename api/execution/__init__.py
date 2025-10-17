"""
Module d'execution - Endpoints pour la gestion des plans d'execution et de la gouvernance

Ce module fournit les endpoints FastAPI pour:
- Validation des plans d'execution
- Execution et monitoring des plans
- Gestion de la gouvernance et des politiques
- Gestion des signaux ML
"""

from .validation_endpoints import router as validation_router
from .execution_endpoints import router as execution_router
from .monitoring_endpoints import router as monitoring_router
from .governance_endpoints import router as governance_router
from .signals_endpoints import router as signals_router

# Export tous les routers pour inclusion dans main.py
__all__ = [
    "validation_router",
    "execution_router",
    "monitoring_router",
    "governance_router",
    "signals_router"
]
