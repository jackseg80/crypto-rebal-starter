"""
Endpoint principal pour le risk dashboard avec données réelles
"""

from fastapi import APIRouter, Query, Depends
from api.deps import get_active_user
from datetime import datetime
import logging

from services.risk_management import risk_manager

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 60
COVERAGE_THRESHOLD = 0.70
MIN_POINTS_FOR_METRICS = 30

router = APIRouter(prefix="/api/risk", tags=["risk-management"])

@router.get("/dashboard")
async def real_risk_dashboard(
    source: str = Query("cointracking", description="Source des données (stub|cointracking|cointracking_api)"),
    min_usd: float = Query(1.0, description="Seuil minimal en USD par asset"),
    price_history_days: int = Query(365, description="Nombre de jours d'historique prix"),
    lookback_days: int = Query(90, description="Fenêtre de lookback pour corrélations"),
    user: str = Depends(get_active_user)
):
    """
    Endpoint principal utilisant le vrai portfolio depuis les CSV avec le système de risque réel
    """
    try:
        start_time = datetime.now()
        
        # Lire le vrai portfolio depuis les CSV - éviter import circulaire
        from services.balance_service import balance_service
        from api.services.utils import to_rows

        # Récupérer les données de portfolio selon la source demandée (stub/CSV/CT-API)
        res = await balance_service.resolve_current_balances(source=source, user_id=user)
        logger.info(f"🔍 resolve_current_balances result: {len(res.get('items', []))} items")
        rows = to_rows(res.get("items", []))
        logger.info(f"🔍 to_rows result: {len(rows)} rows")
        # Filtrer selon min_usd demandé
        items = [r for r in rows if float(r.get("value_usd") or 0.0) >= float(min_usd or 0.0)]
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
            
            if value_usd > 0:
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
        
        logger.info(
            "📊 Calcul risque avec VRAI portfolio: %s assets, $%s",
            len(real_holdings),
            f"{sum(h['value_usd'] for h in real_holdings):,.0f}"
        )
        
        from services.portfolio_metrics import portfolio_metrics_service
        from services.price_history import get_cached_history
        import pandas as pd

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

        async def build_low_quality_dashboard(reason: str, data_quality: Dict[str, Any]):
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
            dashboard_data["quality"] = "low"
            dashboard_data["warning"] = reason
            dashboard_data["data_quality"] = data_quality
            logger.info(
                "✅ Dashboard (fallback risk_manager) calculé en %s — %s",
                calculation_time,
                reason
            )
            return dashboard_data

        data_quality: Dict[str, Any] = {
            "coverage": {},
            "raw_symbol_count": len(price_data)
        }

        if not price_data:
            data_quality["reason"] = "no_price_data"
            return await build_low_quality_dashboard(
                "No price history available for holdings",
                data_quality
            )

        price_df = pd.DataFrame(price_data).sort_index().ffill()
        price_df = price_df.dropna(how="all")

        coverage_details: Dict[str, Dict[str, Any]] = {}
        filtered_symbols: List[str] = []

        for symbol in price_df.columns:
            series = price_df[symbol]
            total_rows = len(series)
            valid_rows = int(series.notna().sum())
            coverage_ratio = (valid_rows / total_rows) if total_rows else 0.0
            cleaned = series.dropna()
            history_days = int((cleaned.index[-1] - cleaned.index[0]).days) if len(cleaned) > 1 else 0

            coverage_details[symbol] = {
                "coverage_ratio": round(coverage_ratio, 4),
                "history_days": history_days,
                "data_points": valid_rows
            }

            if history_days >= MIN_HISTORY_DAYS and coverage_ratio >= COVERAGE_THRESHOLD:
                filtered_symbols.append(symbol)

        data_quality["coverage"] = coverage_details
        data_quality["filtered_symbols"] = filtered_symbols

        filtered_holdings = [
            h for h in real_holdings if (h.get("symbol") or "").upper() in filtered_symbols
        ]

        if filtered_symbols:
            filtered_df = price_df[filtered_symbols].dropna()
        else:
            filtered_df = pd.DataFrame()

        effective_points = int(filtered_df.shape[0]) if not filtered_df.empty else 0
        data_quality["effective_points"] = effective_points

        if not filtered_symbols:
            data_quality["reason"] = "no_symbol_meets_threshold"
            return await build_low_quality_dashboard(
                "Insufficient price coverage after filtering",
                data_quality
            )

        if not filtered_holdings:
            data_quality["reason"] = "no_holdings_after_filter"
            return await build_low_quality_dashboard(
                "No holdings remain after aligning price data",
                data_quality
            )

        if effective_points < MIN_POINTS_FOR_METRICS:
            data_quality["reason"] = "not_enough_points"
            return await build_low_quality_dashboard(
                "Time series too short for robust metrics",
                data_quality
            )

        centralized_metrics = portfolio_metrics_service.calculate_portfolio_metrics(
            price_data=filtered_df,
            balances=filtered_holdings,
            confidence_level=0.95
        )
        corr_metrics = portfolio_metrics_service.calculate_correlation_metrics(filtered_df)

        dashboard_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "real_data": True,
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
                "overall_risk_level": "medium",
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
            "real_holdings": real_holdings
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        dashboard_data["calculation_time"] = calculation_time
        dashboard_data["quality"] = "ok"
        dashboard_data["data_quality"] = data_quality
        
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
