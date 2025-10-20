"""
Module pour la gestion unifiée des données de portfolio
Assure la cohérence entre tous les endpoints
"""

from typing import Dict, Any


async def get_unified_filtered_balances(source: str = "cointracking", min_usd: float = 1.0, pricing: str = "local", user_id: str = "demo"):
    """
    Fonction helper unifiée utilisée par tous les endpoints pour garantir
    des données identiques avec le même filtrage.
    Retourne: {source_used: str, items: [...]}

    NOTE: Le paramètre pricing est ignoré pour l'instant car resolve_current_balances
    ne le supporte pas, mais on le garde pour compatibilité future.
    """
    # Import local pour éviter les imports circulaires
    from services.balance_service import balance_service
    from api.services.utils import to_rows

    # Appel direct avec source explicite
    res = await balance_service.resolve_current_balances(source, user_id)
    rows = [r for r in to_rows(res.get("items", [])) if float(r.get("value_usd") or 0.0) >= float(min_usd)]
    return {"source_used": res.get("source_used"), "items": rows}