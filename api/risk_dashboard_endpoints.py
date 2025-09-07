"""
Endpoint principal pour le risk dashboard avec données réelles
"""

from fastapi import APIRouter, Query
from datetime import datetime
import logging

from services.risk_management import risk_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["risk-dashboard"])

@router.get("/risk/dashboard")
async def real_risk_dashboard(
    min_usd: float = Query(1.0, description="Seuil minimal en USD par asset"),
    price_history_days: int = Query(365, description="Nombre de jours d'historique prix"),
    lookback_days: int = Query(90, description="Fenêtre de lookback pour corrélations")
):
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
        
        # Utiliser le service centralisé pour garantir la cohérence des calculs
        from services.portfolio_metrics import portfolio_metrics_service
        from services.price_history import get_cached_history
        import pandas as pd

        # Construire le DataFrame de prix à partir du cache (mêmes règles que l'Advanced Analytics)
        price_data = {}
        for h in real_holdings:
            symbol = (h.get("symbol") or "").upper()
            if not symbol or float(h.get("value_usd") or 0.0) < float(min_usd):
                continue
            try:
                prices = get_cached_history(symbol, days=price_history_days + 10)
                if prices and len(prices) >= 2:
                    timestamps = [pd.Timestamp.fromtimestamp(p[0]) for p in prices]
                    values = [p[1] for p in prices]
                    price_data[symbol] = pd.Series(values, index=timestamps)
            except Exception:
                continue

        if len(price_data) < 2:
            logger.warning("❌ Données de prix insuffisantes pour le calcul centralisé")
            # Fallback vers l'ancien gestionnaire si nécessaire
            import asyncio
            risk_metrics_task = risk_manager.calculate_portfolio_risk_metrics(
                holdings=real_holdings,
                price_history_days=min(price_history_days, 90)
            )
            correlation_task = risk_manager.calculate_correlation_matrix(
                holdings=real_holdings,
                lookback_days=lookback_days
            )
            risk_metrics, correlation_matrix = await asyncio.gather(
                risk_metrics_task,
                correlation_task
            )

            # Construction de la réponse dashboard (fallback)
            dashboard_data = {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "real_data": True,
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
                "real_holdings": real_holdings
            }

            end_time = datetime.now()
            calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
            dashboard_data["calculation_time"] = calculation_time
            logger.info(f"✅ Dashboard (fallback risk_manager) calculé en {calculation_time}")
            return dashboard_data

        price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()

        # Calculs centralisés
        centralized_metrics = portfolio_metrics_service.calculate_portfolio_metrics(
            price_data=price_df,
            balances=real_holdings,
            confidence_level=0.95
        )
        corr_metrics = portfolio_metrics_service.calculate_correlation_metrics(price_df)

        # Construction de la réponse dashboard alignée avec le service centralisé
        dashboard_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "real_data": True,  # Vraies données
            "portfolio_summary": {
                "total_value": sum(h["value_usd"] for h in real_holdings),
                "num_assets": len(real_holdings),
                "confidence_level": centralized_metrics.confidence_level
            },
            "risk_metrics": {
                "var_95_1d": centralized_metrics.var_95_1d,
                "var_99_1d": centralized_metrics.var_99_1d,
                "cvar_95_1d": centralized_metrics.cvar_95_1d,
                "cvar_99_1d": centralized_metrics.cvar_99_1d,
                "volatility_annualized": centralized_metrics.volatility_annualized,
                "sharpe_ratio": centralized_metrics.sharpe_ratio,
                "sortino_ratio": centralized_metrics.sortino_ratio,
                "calmar_ratio": centralized_metrics.calmar_ratio,
                "max_drawdown": centralized_metrics.max_drawdown,
                "max_drawdown_duration_days": centralized_metrics.max_drawdown_duration_days,
                "current_drawdown": centralized_metrics.current_drawdown,
                "ulcer_index": centralized_metrics.ulcer_index,
                "skewness": centralized_metrics.skewness,
                "kurtosis": centralized_metrics.kurtosis,
                "overall_risk_level": "medium",  # Non évalué par le service centralisé
                "risk_score": 0.0,
                "calculation_date": centralized_metrics.calculation_date.isoformat(),
                "data_points": centralized_metrics.data_points,
                "confidence_level": centralized_metrics.confidence_level
            },
            "correlation_metrics": {
                "diversification_ratio": corr_metrics.diversification_ratio,
                "effective_assets": corr_metrics.effective_assets,
                "top_correlations": corr_metrics.top_correlations
            },
            "real_holdings": real_holdings  # Inclure pour debug
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        dashboard_data["calculation_time"] = calculation_time
        
        logger.info(f"✅ VRAI dashboard (centralisé) calculé en {calculation_time}")
        
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
