"""
Endpoint principal pour le risk dashboard avec données réelles
"""

from fastapi import APIRouter
from datetime import datetime
import logging

from services.risk_management import risk_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["risk-dashboard"])

@router.get("/risk/dashboard")
async def real_risk_dashboard():
    """
    Endpoint principal utilisant le vrai portfolio depuis les CSV avec le système de risque réel
    """
    try:
        start_time = datetime.now()
        
        # Lire le vrai portfolio depuis les CSV - éviter import circulaire
        from api.main import resolve_current_balances, _to_rows
        
        # Récupérer les vraies données portfolio depuis CSV
        res = await resolve_current_balances(source="cointracking")
        logger.info(f"🔍 resolve_current_balances result: {len(res.get('items', []))} items")
        rows = _to_rows(res.get("items", []))
        logger.info(f"🔍 _to_rows result: {len(rows)} rows")
        # Filtrer min_usd = 1.0
        items = [r for r in rows if float(r.get("value_usd") or 0.0) >= 1.0]
        logger.info(f"🔍 After filtering >= 1.0: {len(items)} items")
        
        if not items:
            logger.warning("❌ Aucun holding trouvé dans le portfolio CSV")
            logger.info(f"🔍 Debug info - res keys: {list(res.keys())}, source_used: {res.get('source_used')}")
            return {
                "success": False,
                "message": "Aucun holding trouvé dans le portfolio après filtrage"
            }
        
        # Convertir au format attendu par le risk manager
        real_holdings = []
        for item in items:
            symbol = item.get("symbol", "").upper()
            value_usd = float(item.get("value_usd", 0))
            balance = float(item.get("amount", 0))
            
            if value_usd > 0:  # Filtrer les holdings avec valeur positive
                real_holdings.append({
                    "symbol": symbol,
                    "balance": balance,
                    "value_usd": value_usd
                })
        
        if not real_holdings:
            logger.warning("❌ Aucun holding avec valeur positive")
            return {
                "success": False,
                "message": "Aucun holding avec valeur positive trouvé"
            }
        
        logger.info(f"📊 Calcul risque avec VRAI portfolio: {len(real_holdings)} assets, ${sum(h['value_usd'] for h in real_holdings):,.0f}")
        
        # Calcul en parallèle de toutes les métriques avec le VRAI portfolio
        import asyncio
        
        risk_metrics_task = risk_manager.calculate_portfolio_risk_metrics(
            holdings=real_holdings, 
            price_history_days=30
        )
        correlation_task = risk_manager.calculate_correlation_matrix(
            holdings=real_holdings, 
            lookback_days=30
        )
        
        risk_metrics, correlation_matrix = await asyncio.gather(
            risk_metrics_task,
            correlation_task
        )
        
        # Construction de la réponse dashboard avec vraies données
        dashboard_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "real_data": True,  # Vraies données
            "portfolio_summary": {
                "total_value": sum(h["value_usd"] for h in real_holdings),
                "num_assets": len(real_holdings),
                "confidence_level": risk_metrics.confidence_level
            },
            "risk_metrics": {
                "var_95_1d": risk_metrics.var_95_1d,
                "var_99_1d": risk_metrics.var_99_1d,
                "cvar_95_1d": risk_metrics.cvar_95_1d,
                "cvar_99_1d": risk_metrics.cvar_99_1d,
                "volatility_annualized": risk_metrics.volatility_annualized,
                "sharpe_ratio": risk_metrics.sharpe_ratio,
                "sortino_ratio": risk_metrics.sortino_ratio,
                "calmar_ratio": risk_metrics.calmar_ratio,
                "max_drawdown": risk_metrics.max_drawdown,
                "max_drawdown_duration_days": risk_metrics.max_drawdown_duration_days,
                "current_drawdown": risk_metrics.current_drawdown,
                "ulcer_index": risk_metrics.ulcer_index,
                "skewness": risk_metrics.skewness,
                "kurtosis": risk_metrics.kurtosis,
                "overall_risk_level": risk_metrics.overall_risk_level.value,
                "risk_score": risk_metrics.risk_score,
                "calculation_date": risk_metrics.calculation_date.isoformat(),
                "data_points": risk_metrics.data_points,
                "confidence_level": risk_metrics.confidence_level
            },
            "correlation_metrics": {
                "diversification_ratio": correlation_matrix.diversification_ratio,
                "effective_assets": correlation_matrix.effective_assets,
                "top_correlations": _get_top_correlations(correlation_matrix.correlations, 5)
            },
            "real_holdings": real_holdings  # Inclure pour debug
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        dashboard_data["calculation_time"] = calculation_time
        
        logger.info(f"✅ VRAI dashboard calculé en {calculation_time}")
        
        return dashboard_data
        
    except Exception as e:
        logger.error(f"❌ Erreur VRAI dashboard risque: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Erreur lors du calcul avec portfolio réel: {str(e)}"
        }

def _get_top_correlations(correlations: dict, top_n: int = 5) -> list:
    """Extrait les top N corrélations entre assets (excluant self-correlations)"""
    
    if not correlations:
        return []
    
    correlation_pairs = []
    
    for asset1, corr_dict in correlations.items():
        for asset2, correlation in corr_dict.items():
            if asset1 != asset2 and correlation != 1.0:  # Exclure self-correlation
                # Éviter les doublons (A-B et B-A)
                pair = tuple(sorted([asset1, asset2]))
                correlation_pairs.append({
                    "asset1": pair[0],
                    "asset2": pair[1], 
                    "correlation": correlation
                })
    
    # Supprimer doublons et trier par corrélation absolue
    seen = set()
    unique_pairs = []
    for pair in correlation_pairs:
        key = (pair["asset1"], pair["asset2"])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)
    
    unique_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return unique_pairs[:top_n]