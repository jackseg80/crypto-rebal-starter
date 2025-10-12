"""
API Dependencies Module

Ce module contient les dépendances FastAPI réutilisables pour :
- Protection des endpoints (dev guards)
- Authentification et autorisation
- Validation des requêtes
- Middleware logic
"""

from api.dependencies.dev_guards import (
    require_dev_mode,
    require_debug_enabled,
    require_flag,
    require_simulation,
    require_alerts_test,
    dev_only,
)

__all__ = [
    "require_dev_mode",
    "require_debug_enabled",
    "require_flag",
    "require_simulation",
    "require_alerts_test",
    "dev_only",
]
