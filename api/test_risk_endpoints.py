"""
Endpoints de test pour le système de risque avec données mockées
Utilise le cache d'historique réel mais avec un portfolio de test
"""

from fastapi import APIRouter
from datetime import datetime
import logging

from services.risk_management import risk_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test", tags=["test-risk"])

@router.get("/risk/dashboard")
async def real_risk_dashboard(source: str = "cointracking", min_usd: float = 1.0):
    """
    Endpoint utilisant le vrai portfolio avec le système de risque réel
    Supporte les sources: stub, cointracking, cointracking_api
    """
    try:
        start_time = datetime.now()
        
        # Lire le portfolio selon la source demandée
        from api.unified_data import get_unified_filtered_balances
        
        # Récupérer les données portfolio selon la source configurée
        portfolio_data = await get_unified_filtered_balances(source=source, min_usd=min_usd)
        logger.info(f"🔍 Risk calculation using source: {source}")
        items = portfolio_data.get("items", [])
        
        if not items:
            logger.warning("❌ Aucun holding trouvé dans le portfolio CSV")
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

        # Calcul parallèle avec garde-fous sur la corrélation (cas stub/peu de données)
        try:
            risk_metrics, correlation_matrix = await asyncio.gather(
                risk_metrics_task,
                correlation_task
            )
        except Exception as corr_err:
            logger.error(f"Erreur calcul corrélation (fallback vide): {corr_err}")
            # Refait calcul des métriques seules si nécessaire
            try:
                risk_metrics = await risk_manager.calculate_portfolio_risk_metrics(
                    holdings=real_holdings,
                    price_history_days=30
                )
            except Exception:
                # Garder un objet basique si même le calcul risque échoue
                class _RM: pass
                risk_metrics = _RM()
                risk_metrics.var_95_1d = 0.0
                risk_metrics.var_99_1d = 0.0
                risk_metrics.cvar_95_1d = 0.0
                risk_metrics.cvar_99_1d = 0.0
                risk_metrics.volatility_annualized = 0.0
                risk_metrics.sharpe_ratio = 0.0
                risk_metrics.sortino_ratio = 0.0
                risk_metrics.calmar_ratio = 0.0
                risk_metrics.max_drawdown = 0.0
                risk_metrics.max_drawdown_duration_days = 0
                risk_metrics.current_drawdown = 0.0
                risk_metrics.ulcer_index = 0.0
                risk_metrics.skewness = 0.0
                risk_metrics.kurtosis = 0.0
                risk_metrics.overall_risk_level = type('L', (), {'value': 'unknown'})()
                risk_metrics.risk_score = 0.0
                from datetime import datetime as _dt
                risk_metrics.calculation_date = _dt.now()
                risk_metrics.data_points = 0
                risk_metrics.confidence_level = 0.0

            from services.risk_management import CorrelationMatrix
            correlation_matrix = CorrelationMatrix()
        
        # Construction de la réponse dashboard avec vraies données
        dashboard_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "real_data": True,  # Vraies données au lieu de test_mode
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
