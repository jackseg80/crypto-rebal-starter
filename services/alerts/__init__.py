"""
Services d'alertes prédictives pour le Decision Engine

Ce module implémente un système d'alertes discipliné qui:
- Consomme les signaux ML existants sans créer de 4ème logique
- Respecte l'architecture single-writer (propose, n'exécute pas)
- Intègre anti-bruit robuste (hystérésis, rate-limit, dedup)
- Supporte escalade automatique et snooze intelligent
"""

from .alert_engine import AlertEngine
from .alert_types import AlertType, AlertSeverity
from .alert_storage import AlertStorage

__all__ = ["AlertEngine", "AlertType", "AlertSeverity", "AlertStorage"]