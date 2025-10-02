"""
API Endpoints pour le système de gestion des risques avancé
Fournit les métriques VaR/CVaR, corrélation, stress tests et monitoring temps réel
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends
from api.deps import get_active_user
from pydantic import BaseModel

from services.risk_management import risk_manager, RiskMetrics, CorrelationMatrix, StressTestResult, StressScenario, PerformanceAttribution, BacktestResult, RiskAlert, AlertSeverity, AlertCategory
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk-management"])
COMPUTE_ON_STUB_SOURCES = (os.getenv("COMPUTE_ON_STUB_SOURCES", "false").strip().lower() == "true")

# ===== Helper: Risk Score V2 (feature-flagged) =====
def _calculate_risk_score_v2(
    risk_metrics,
    exposure_by_group: Dict[str, float],
    group_risk_index: float,
    balances: List[Dict[str, Any]],
    correlation_metrics
) -> Tuple[float, Dict[str, Any]]:
    """Compute Risk Score V2 with VaR/CVaR + structure + GRI.
    Returns (score, breakdown dict).
    """
    def clamp(x, a, b):
        return max(a, min(b, x))

    score = 50.0
    breakdown: Dict[str, float] = {}

    # VaR/CVaR (positive values)
    var95 = float(getattr(risk_metrics, 'var_95_1d', 0.0) or 0.0)
    cvar95 = float(getattr(risk_metrics, 'cvar_95_1d', 0.0) or 0.0)
    d_var = -5.0 if var95 < 0.04 else (0.0 if var95 <= 0.08 else 5.0)
    d_cvar = -3.0 if cvar95 < 0.06 else (0.0 if cvar95 <= 0.12 else 3.0)
    score += d_var + d_cvar
    breakdown['var95'] = d_var
    breakdown['cvar95'] = d_cvar

    # Drawdown (use absolute)
    max_dd = abs(float(getattr(risk_metrics, 'max_drawdown', 0.0) or 0.0))
    if max_dd < 0.15:
        d_dd = -10.0
    elif max_dd <= 0.30:
        d_dd = 0.0
    elif max_dd <= 0.50:
        d_dd = 10.0
    else:
        d_dd = 20.0
    score += d_dd
    breakdown['drawdown'] = d_dd

    # Volatility annualized
    vol = float(getattr(risk_metrics, 'volatility_annualized', 0.0) or 0.0)
    d_vol = -5.0 if vol < 0.30 else (0.0 if vol <= 0.60 else 10.0)
    score += d_vol
    breakdown['volatility'] = d_vol

    # Sharpe/Sortino (use the worse)
    sharpe = float(getattr(risk_metrics, 'sharpe_ratio', 0.0) or 0.0)
    sortino = float(getattr(risk_metrics, 'sortino_ratio', sharpe) or sharpe)
    perf_ratio = min(sharpe, sortino)
    if perf_ratio < 0.5:
        d_perf = 10.0
    elif perf_ratio <= 1.0:
        d_perf = 0.0
    elif perf_ratio <= 1.5:
        d_perf = -5.0
    else:
        d_perf = -10.0
    score += d_perf
    breakdown['risk_adjusted_perf'] = d_perf

    # Structure: stables share from exposure_by_group
    stables_share = float(exposure_by_group.get('Stablecoins', 0.0) or 0.0)
    if stables_share >= 0.20:
        d_stables = -5.0
    elif stables_share >= 0.10:
        d_stables = -2.0
    elif stables_share < 0.05:
        d_stables = 3.0
    else:
        d_stables = 0.0
    score += d_stables
    breakdown['stables'] = d_stables

    # Concentration: Top5 and HHI
    try:
        total = sum(float(h.get('value_usd', 0.0) or 0.0) for h in balances)
        weights = []
        if total > 0:
            weights = sorted([(float(h.get('value_usd', 0.0))/total) for h in balances if float(h.get('value_usd', 0.0)) > 0], reverse=True)
        top5 = sum(weights[:5]) if weights else 0.0
        hhi = sum(w*w for w in weights)
    except Exception:
        top5 = 0.0
        hhi = 0.0
    d_conc = 0.0
    if top5 > 0.80:
        d_conc += 5.0
    elif hhi > 0.20:
        d_conc += 3.0
    score += d_conc
    breakdown['concentration'] = d_conc

    # Diversification via diversification_ratio
    div_ratio = float(getattr(correlation_metrics, 'diversification_ratio', 1.0) or 1.0)
    d_div = 0.0 if div_ratio > 0.7 else (3.0 if div_ratio >= 0.4 else 6.0)
    score += d_div
    breakdown['diversification'] = d_div

    # Group Risk Index
    d_gri = min(10.0, max(0.0, (float(group_risk_index) - 4.0) * 2.0))
    score += d_gri
    breakdown['gri'] = d_gri

    score = clamp(score, 0.0, 100.0)
    return score, breakdown

class RiskMetricsResponse(BaseModel):
    """Réponse pour les métriques de risque"""
    success: bool
    risk_metrics: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    calculation_time: Optional[str] = None

class CorrelationResponse(BaseModel):
    """Réponse pour la matrice de corrélation"""
    success: bool
    correlation_matrix: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    calculation_time: Optional[str] = None

class StressTestResponse(BaseModel):
    """Réponse pour les stress tests"""
    success: bool
    stress_test_result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    calculation_time: Optional[str] = None

class CustomStressRequest(BaseModel):
    """Requête pour stress test personnalisé"""
    asset_shocks: Dict[str, float]  # symbol/group -> shock percentage
    scenario_name: Optional[str] = "Custom Scenario"
    scenario_description: Optional[str] = "User-defined stress scenario"

class BacktestRequest(BaseModel):
    """Requête pour backtest de stratégie"""
    strategy_name: str
    target_allocations: Dict[str, float]  # groupe -> allocation (ex: {"BTC": 0.4, "ETH": 0.3, "DeFi": 0.3})
    backtest_days: Optional[int] = 180
    rebalance_frequency_days: Optional[int] = 30
    transaction_cost_pct: Optional[float] = 0.001  # 0.1%

@router.get("/status")
async def get_risk_system_status():
    """
    Statut du système de gestion des risques
    """
    try:
        status = risk_manager.get_system_status()
        return {
            "success": True,
            "system_status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting risk system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=RiskMetricsResponse)
async def get_portfolio_risk_metrics(
    price_history_days: int = Query(30, ge=10, le=365, description="Nombre de jours d'historique"),
    user: str = Depends(get_active_user)
):
    """
    Calcule les métriques de risque complètes du portfolio
    
    Inclut:
    - VaR/CVaR à 95% et 99%
    - Ratios Sharpe, Sortino, Calmar
    - Maximum Drawdown et Ulcer Index
    - Skewness et Kurtosis
    - Niveau de risque global
    """
    try:
        start_time = datetime.now()
        
        # Import des balances via le système unifié (même source que /balances/current)
        from api.unified_data import get_unified_filtered_balances
        
        # Récupération des holdings actuels via le système unifié
        balances_response = await get_unified_filtered_balances(source="cointracking", min_usd=1.0, user_id=user)
        src_used = (balances_response or {}).get('source_used', '')
        if (src_used.startswith('stub') or src_used == 'none') and not COMPUTE_ON_STUB_SOURCES:
            return RiskMetricsResponse(success=False, message="No real data: stub source in use")
        balances = balances_response.get('items', [])
        if not balances or len(balances) == 0:
            return RiskMetricsResponse(
                success=False,
                message="Aucun holding trouvé dans le portfolio via le système unifié"
            )
        
        # Calcul des métriques de risque
        risk_metrics = await risk_manager.calculate_portfolio_risk_metrics(
            holdings=balances,
            price_history_days=price_history_days
        )
        
        # Conversion en dictionnaire pour API
        metrics_dict = {
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
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        
        return RiskMetricsResponse(
            success=True,
            risk_metrics=metrics_dict,
            calculation_time=calculation_time
        )
        
    except Exception as e:
        logger.error(f"Erreur calcul métriques risque: {e}")
        return RiskMetricsResponse(
            success=False,
            message=f"Erreur lors du calcul: {str(e)}"
        )

@router.get("/correlation", response_model=CorrelationResponse)
async def get_correlation_matrix(
    lookback_days: int = Query(30, ge=10, le=365, description="Nombre de jours pour calcul corrélation"),
    source: str = Query("cointracking", description="Source de données: stub_balanced, cointracking, ou cointracking_api"),
    user: str = Depends(get_active_user)
):
    """
    Calcule la matrice de corrélation temps réel entre assets
    
    Inclut:
    - Corrélations pairwise entre tous les assets
    - Analyse en composantes principales (PCA)
    - Ratio de diversification
    - Nombre effectif d'assets indépendants
    """
    try:
        start_time = datetime.now()
        
        # Import des balances via le système unifié (même source que /balances/current)
        from api.unified_data import get_unified_filtered_balances
        
        # Récupération des holdings actuels via le système unifié
        balances_response = await get_unified_filtered_balances(source=source, min_usd=1.0, user_id=user)
        src_used = (balances_response or {}).get('source_used', '')
        if (src_used.startswith('stub') or src_used == 'none') and not COMPUTE_ON_STUB_SOURCES:
            return CorrelationResponse(success=False, message="No real data: stub source in use")
        balances = balances_response.get('items', [])
        logger.info(f"🔍 Correlation endpoint: received {len(balances)} holdings from unified data source='{source}'")
        
        if not balances or len(balances) == 0:
            logger.warning(f"❌ No holdings found for correlation calculation with source='{source}'")
            return CorrelationResponse(
                success=False,
                message=f"Aucun holding trouvé dans le portfolio via le système unifié (source: {source})"
            )
        
        # Calcul de la matrice de corrélation
        corr_matrix = await risk_manager.calculate_correlation_matrix(
            holdings=balances,
            lookback_days=lookback_days
        )
        
        # Conversion en dictionnaire pour API
        correlation_dict = {
            "correlations": corr_matrix.correlations,
            "eigen_values": corr_matrix.eigen_values,
            "eigen_vectors": corr_matrix.eigen_vectors,
            "principal_components": corr_matrix.principal_components,
            "diversification_ratio": corr_matrix.diversification_ratio,
            "effective_assets": corr_matrix.effective_assets,
            "last_updated": corr_matrix.last_updated.isoformat()
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        
        return CorrelationResponse(
            success=True,
            correlation_matrix=correlation_dict,
            calculation_time=calculation_time
        )
        
    except Exception as e:
        logger.error(f"Erreur calcul matrice corrélation: {e}")
        return CorrelationResponse(
            success=False,
            message=f"Erreur lors du calcul: {str(e)}"
        )

@router.get("/stress-test/{scenario}", response_model=StressTestResponse)
async def run_predefined_stress_test(
    scenario: str,
):
    """
    Exécute un stress test basé sur des scénarios crypto historiques
    
    Scénarios disponibles:
    - bear_2018: Crash crypto 2018 (BTC -84%, Altcoins -95%)
    - covid_2020: Crash COVID Mars 2020 (BTC -50% en 2 semaines)
    - luna_2022: Effondrement Terra Luna (contagion DeFi)
    - ftx_2022: Bankruptcy FTX (crise de liquidité)
    """
    try:
        start_time = datetime.now()
        
        # Validation du scénario
        scenario_mapping = {
            "bear_2018": StressScenario.BEAR_MARKET_2018,
            "covid_2020": StressScenario.COVID_CRASH_2020,
            "luna_2022": StressScenario.LUNA_COLLAPSE_2022,
            "ftx_2022": StressScenario.FTX_COLLAPSE_2022
        }
        
        if scenario not in scenario_mapping:
            available_scenarios = list(scenario_mapping.keys())
            return StressTestResponse(
                success=False,
                message=f"Scénario invalide. Scénarios disponibles: {available_scenarios}"
            )
        
        # Import des balances CoinTracking
        from connectors.cointracking_api import get_current_balances
        
        # Récupération des holdings actuels
        balances_response = await get_current_balances()
        balances = balances_response.get('items', []) if isinstance(balances_response, dict) else balances_response
        if not balances or len(balances) == 0:
            return StressTestResponse(
                success=False,
                message="Aucun holding trouvé dans le portfolio"
            )
        
        # Exécution du stress test
        stress_scenario = scenario_mapping[scenario]
        stress_result = await risk_manager.run_stress_test(
            holdings=balances,
            scenario=stress_scenario
        )
        
        # Conversion en dictionnaire pour API
        result_dict = {
            "scenario_name": stress_result.scenario_name,
            "scenario_description": stress_result.scenario_description,
            "portfolio_loss_pct": stress_result.portfolio_loss_pct,
            "portfolio_loss_usd": stress_result.portfolio_loss_usd,
            "worst_performing_assets": stress_result.worst_performing_assets,
            "best_performing_assets": stress_result.best_performing_assets,
            "var_breach": stress_result.var_breach,
            "recovery_time_estimate_days": stress_result.recovery_time_estimate_days,
            "risk_contribution": stress_result.risk_contribution
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        
        return StressTestResponse(
            success=True,
            stress_test_result=result_dict,
            calculation_time=calculation_time
        )
        
    except Exception as e:
        logger.error(f"Erreur stress test: {e}")
        return StressTestResponse(
            success=False,
            message=f"Erreur lors du stress test: {str(e)}"
        )

@router.post("/stress-test/custom", response_model=StressTestResponse)
async def run_custom_stress_test(
    request: CustomStressRequest
):
    """
    Exécute un stress test personnalisé avec shocks définis par l'utilisateur
    
    Permet de définir des shocks spécifiques par asset ou groupe d'assets
    """
    try:
        start_time = datetime.now()
        
        # Validation des shocks
        if not request.asset_shocks:
            return StressTestResponse(
                success=False,
                message="Au moins un shock d'asset doit être défini"
            )
        
        # Import des balances CoinTracking
        from connectors.cointracking_api import get_current_balances
        
        # Récupération des holdings actuels
        balances = await get_current_balances()
        if not balances or len(balances) == 0:
            return StressTestResponse(
                success=False,
                message="Aucun holding trouvé dans le portfolio"
            )
        
        # Exécution du stress test personnalisé
        stress_result = await risk_manager.run_stress_test(
            holdings=balances,
            scenario=StressScenario.CUSTOM_SCENARIO,
            custom_shocks=request.asset_shocks
        )
        
        # Mise à jour du nom et description
        stress_result.scenario_name = request.scenario_name
        stress_result.scenario_description = request.scenario_description
        
        # Conversion en dictionnaire pour API
        result_dict = {
            "scenario_name": stress_result.scenario_name,
            "scenario_description": stress_result.scenario_description,
            "portfolio_loss_pct": stress_result.portfolio_loss_pct,
            "portfolio_loss_usd": stress_result.portfolio_loss_usd,
            "worst_performing_assets": stress_result.worst_performing_assets,
            "best_performing_assets": stress_result.best_performing_assets,
            "var_breach": stress_result.var_breach,
            "recovery_time_estimate_days": stress_result.recovery_time_estimate_days,
            "risk_contribution": stress_result.risk_contribution
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        
        return StressTestResponse(
            success=True,
            stress_test_result=result_dict,
            calculation_time=calculation_time
        )
        
    except Exception as e:
        logger.error(f"Erreur stress test personnalisé: {e}")
        return StressTestResponse(
            success=False,
            message=f"Erreur lors du stress test: {str(e)}"
        )

@router.get("/dashboard")
async def get_risk_dashboard(
    source: str = Query("cointracking", description="Source de données: cointracking ou cointracking_api"),
    pricing: str = Query("local", description="Source de prix: local ou coingecko"),
    min_usd: float = Query(1.0, description="Seuil minimum en USD"),
    price_history_days: int = Query(30, ge=10, le=365, description="Fenêtre d'historique pour métriques (jours)"),
    lookback_days: int = Query(30, ge=10, le=365, description="Fenêtre pour corrélations (jours)"),
    user_id: Optional[str] = Query(None, description="User ID (optionnel, prioritaire sur X-User header)"),
    user_header: str = Depends(get_active_user)
):
    """
    Endpoint pour dashboard de risque temps réel
    Combine toutes les métriques de risque en une seule réponse
    """
    try:
        start_time = datetime.now()

        # Déterminer user effectif : Query param prioritaire, sinon header
        effective_user = user_id or user_header

        # Récupération unifiée des balances (supporte stub | cointracking | cointracking_api)
        from api.unified_data import get_unified_filtered_balances
        unified = await get_unified_filtered_balances(source=source, min_usd=min_usd, user_id=effective_user)
        balances = unified.get("items", [])
        source_used = unified.get("source_used", source)
        
        items_count = len(balances)
        
        if not balances or len(balances) == 0:
            return {
                "success": False,
                "message": "Aucun holding trouvé dans le portfolio après filtrage"
            }
        
        # NOUVEAU: Utiliser le service centralisé de métriques pour garantir la cohérence
        from services.portfolio_metrics import portfolio_metrics_service
        from services.price_history import get_cached_history
        import pandas as pd
        
        logger.info(f"🎯 Using centralized metrics service for {len(balances)} assets over {price_history_days} days")
        
        # Récupérer les données de prix historiques
        price_data = {}
        for balance in balances:
            symbol = balance.get('symbol', '').upper()
            if symbol:
                try:
                    prices = get_cached_history(symbol, days=price_history_days)
                    if prices and len(prices) > 10:
                        timestamps = [pd.Timestamp.fromtimestamp(p[0]) for p in prices]
                        values = [p[1] for p in prices]
                        price_data[symbol] = pd.Series(values, index=timestamps)
                except Exception as e:
                    logger.warning(f"Failed to get price data for {symbol}: {e}")
        
        if len(price_data) < 2:
            return {
                "success": False,
                "message": "Insufficient price data for metrics calculation"
            }
        
        # Créer DataFrame des prix
        price_df = pd.DataFrame(price_data).fillna(method='ffill').dropna()
        
        # Calculer les métriques avec le service centralisé
        risk_metrics = portfolio_metrics_service.calculate_portfolio_metrics(
            price_data=price_df,
            balances=balances,
            confidence_level=0.95
        )
        
        # Calculer les métriques de corrélation
        correlation_metrics = portfolio_metrics_service.calculate_correlation_metrics(
            price_data=price_df,
            min_correlation_threshold=0.7
        )

        # Exposition par groupes (via Taxonomy) + Group Risk Index (GRI)
        total_value = sum(float(h.get("value_usd", 0.0)) for h in balances) or 0.0
        from services.taxonomy import Taxonomy
        taxonomy = Taxonomy.load()
        exposure_by_group = {}
        if total_value > 0:
            for h in balances:
                symbol = str(h.get('symbol', '')).upper()
                group = taxonomy.group_for_alias(symbol)
                w = float(h.get('value_usd', 0.0)) / total_value
                exposure_by_group[group] = exposure_by_group.get(group, 0.0) + w

        # Barème de risque par groupe (0-10), simple et explicable
        GROUP_RISK_LEVELS = {
            'Stablecoins': 0,
            'BTC': 2,
            'ETH': 3,
            'L2/Scaling': 5,
            'DeFi': 5,
            'AI/Data': 5,
            'SOL': 6,
            'L1/L0 majors': 6,
            'Gaming/NFT': 6,
            'Others': 7,
            'Memecoins': 9,
        }
        if exposure_by_group:
            gri_raw = 0.0
            for g, w in exposure_by_group.items():
                level = GROUP_RISK_LEVELS.get(g, 6)  # défaut modéré si inconnu
                gri_raw += w * level
            group_risk_index = max(0.0, min(10.0, gri_raw))
        else:
            group_risk_index = 0.0

        # Construction de la réponse dashboard avec métriques centralisées
        
        # ✅ Utiliser le Risk Score autoritaire du service (docs/RISK_SEMANTICS.md)
        # Le service calcule déjà risk_score (robustesse 0-100) et overall_risk_level (enum)
        # avec la sémantique correcte : score élevé = robuste = risque faible
        risk_score_authoritative = risk_metrics.risk_score
        overall_risk_level = getattr(risk_metrics.overall_risk_level, "value", str(risk_metrics.overall_risk_level))

        # Calculer le Risk Score Structural (avec intégration GRI + concentration + structure)
        risk_score_result = _calculate_risk_score_v2(
            risk_metrics=risk_metrics,
            exposure_by_group=exposure_by_group,
            group_risk_index=group_risk_index,
            balances=balances,
            correlation_metrics=correlation_metrics
        )
        risk_score_structural = risk_score_result[0]  # Score structurel
        structural_breakdown = risk_score_result[1]   # Détail contributions
        
        dashboard_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "portfolio_summary": {
                "total_value": sum(h.get("value_usd", 0) for h in balances),
                "num_assets": len(balances),
                "confidence_level": risk_metrics.confidence_level
            },
            "risk_metrics": {
                # ⚡ MÉTRIQUES CENTRALISÉES - Cohérentes avec tous les modules
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
                # ✅ Scores et niveau autoritaires (source de vérité)
                "overall_risk_level": overall_risk_level,
                "risk_score": risk_score_authoritative,        # Autoritaire (VaR + Sharpe + DD + Vol)
                "risk_score_structural": risk_score_structural,  # Structurel (+ GRI + Concentration)
                "structural_breakdown": structural_breakdown,    # Détail contributions (audit)
                # Exposition par groupes et indice GRI (0-10)
                "exposure_by_group": exposure_by_group,
                "group_risk_index": group_risk_index,
                "calculation_date": risk_metrics.calculation_date.isoformat(),
                "data_points": risk_metrics.data_points,
                "confidence_level": risk_metrics.confidence_level,
                # ✅ Metadata fenêtres temporelles (traçabilité)
                "window_used": {
                    "price_history_days": price_history_days,
                    "lookback_days": lookback_days,
                    "actual_data_points": risk_metrics.data_points
                }
            },
            "correlation_metrics": {
                "diversification_ratio": correlation_metrics.diversification_ratio,
                "effective_assets": correlation_metrics.effective_assets,
                "top_correlations": correlation_metrics.top_correlations
            },
            "alerts": _generate_centralized_risk_alerts(risk_metrics, correlation_metrics)
        }
        
        logger.info(f"✅ Centralized metrics calculated: Sharpe={risk_metrics.sharpe_ratio:.2f}, Vol={risk_metrics.volatility_annualized:.2f}, MaxDD={risk_metrics.max_drawdown:.2%}, RiskScore={risk_score_authoritative:.1f}, RiskStructural={risk_score_structural:.1f}")

        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        dashboard_data["calculation_time"] = calculation_time

        # Add normalized metadata for frontend traceability
        import hashlib
        taxonomy_version = "v2"  # Current taxonomy version
        # Simple hash based on groups used for consistency checking
        groups_hash = hashlib.md5(",".join(sorted(exposure_by_group.keys())).encode()).hexdigest()[:8]

        dashboard_data["meta"] = {
            "user_id": effective_user,
            "source_id": source_used,
            "taxonomy_version": taxonomy_version,
            "taxonomy_hash": groups_hash,
            "generated_at": datetime.now().isoformat(),
            "correlation_id": f"risk-{effective_user}-{int(datetime.now().timestamp())}"
        }

        # Log metadata for traceability
        logger.info(f"🏷️ Risk dashboard metadata: user={effective_user}, source={source_used}, taxonomy={taxonomy_version}:{groups_hash}")

        return dashboard_data
        
    except Exception as e:
        logger.error(f"Erreur dashboard risque: {e}")
        return {
            "success": False,
            "message": f"Erreur lors du calcul dashboard: {str(e)}"
        }

def _generate_centralized_risk_alerts(risk_metrics, correlation_metrics) -> List[Dict[str, Any]]:
    """Génère les alertes de risque basées sur les métriques centralisées"""
    alerts = []
    
    # Alert sur Sharpe ratio faible
    if risk_metrics.sharpe_ratio < 0.5:
        alerts.append({
            "level": "high" if risk_metrics.sharpe_ratio < 0 else "medium",
            "type": "performance_alert",
            "message": f"Sharpe ratio faible: {risk_metrics.sharpe_ratio:.2f}",
            "recommendation": "Optimiser la sélection d'actifs ou réduire la volatilité"
        })
    
    # Alert sur drawdown élevé
    if abs(risk_metrics.max_drawdown) > 0.4:
        alerts.append({
            "level": "high",
            "type": "drawdown_alert", 
            "message": f"Drawdown maximum élevé: {risk_metrics.max_drawdown:.1%}",
            "recommendation": "Considérer la diversification ou des stratégies de protection"
        })
    
    # Alert sur diversification
    if correlation_metrics.diversification_ratio < 0.6:
        alerts.append({
            "level": "medium",
            "type": "correlation_alert",
            "message": f"Faible diversification: ratio {correlation_metrics.diversification_ratio:.2f}",
            "recommendation": "Ajouter des assets moins corrélés"
        })
    
    # Alert sur volatilité excessive
    if risk_metrics.volatility_annualized > 0.8:
        alerts.append({
            "level": "high",
            "type": "volatility_alert",
            "message": f"Volatilité très élevée: {risk_metrics.volatility_annualized:.1%}",
            "recommendation": "Augmenter la part de stablecoins ou assets moins volatils"
        })
    
    return alerts

def _get_top_correlations(correlations: Dict[str, Dict[str, float]], top_n: int = 5) -> List[Dict[str, Any]]:
    """Extrait les top N corrélations entre assets (excluant self-correlations)"""
    
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

@router.get("/attribution")
async def get_performance_attribution(
    analysis_days: int = Query(30, ge=7, le=365, description="Période d'analyse en jours")
):
    """
    Calcule l'attribution de performance détaillée du portfolio
    
    Décompose la performance totale en:
    - Contributions individuelles par asset
    - Contributions agrégées par groupe d'assets  
    - Effets d'allocation, sélection et interaction
    - Analyse comparative vs benchmark equal-weight
    """
    try:
        start_time = datetime.now()
        
        # Import des balances CoinTracking
        from connectors.cointracking_api import get_current_balances
        
        # Récupération des holdings actuels
        balances_response = await get_current_balances()
        if not balances_response or not isinstance(balances_response, dict):
            return {
                "success": False,
                "message": "Erreur lors de la récupération des données CoinTracking"
            }
        
        balances = balances_response.get('items', [])
        if not balances or len(balances) == 0:
            return {
                "success": False,
                "message": "Aucun holding trouvé dans le portfolio"
            }
        
        # Calcul de l'attribution de performance
        attribution = await risk_manager.calculate_performance_attribution(
            holdings=balances,
            analysis_days=analysis_days
        )
        
        # Conversion en dictionnaire pour API
        attribution_dict = {
            "success": True,
            "period_analysis": {
                "total_return_pct": attribution.total_return,
                "total_return_usd": attribution.total_return_usd,
                "period_start": attribution.period_start.isoformat(),
                "period_end": attribution.period_end.isoformat(),
                "analysis_days": attribution.analysis_period_days,
                "benchmark_used": attribution.benchmark_used
            },
            "asset_contributions": attribution.asset_contributions,
            "group_contributions": attribution.group_contributions,
            "attribution_effects": {
                "selection_effect": attribution.selection_effect,
                "allocation_effect": attribution.allocation_effect,
                "interaction_effect": attribution.interaction_effect,
                "total_active_return": attribution.selection_effect + attribution.allocation_effect + attribution.interaction_effect
            },
            "top_contributors": sorted(
                attribution.asset_contributions, 
                key=lambda x: x["contribution_pct"], 
                reverse=True
            )[:5],
            "bottom_contributors": sorted(
                attribution.asset_contributions,
                key=lambda x: x["contribution_pct"]
            )[:5]
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        attribution_dict["calculation_time"] = calculation_time
        
        return attribution_dict
        
    except Exception as e:
        logger.error(f"Erreur calcul attribution performance: {e}")
        return {
            "success": False,
            "message": f"Erreur lors du calcul: {str(e)}"
        }

@router.post("/backtest")
async def run_strategy_backtest(
    request: BacktestRequest
):
    """
    Exécute un backtest d'une stratégie d'allocation personnalisée
    
    Simule la performance d'une stratégie sur données historiques avec:
    - Rebalancing périodique selon la fréquence spécifiée
    - Coûts de transaction réalistes
    - Comparaison vs benchmark equal-weight
    - Métriques de performance complètes
    
    Exemple d'allocations:
    ```json
    {
        "strategy_name": "BTC Heavy",
        "target_allocations": {
            "BTC": 0.5,
            "ETH": 0.3,
            "DeFi": 0.2
        }
    }
    ```
    """
    try:
        start_time = datetime.now()
        
        # Validation des allocations
        total_allocation = sum(request.target_allocations.values())
        if abs(total_allocation - 1.0) > 0.01:
            return {
                "success": False,
                "message": f"Les allocations doivent sommer à 100% (actuellement {total_allocation:.1%})"
            }
        
        # Exécution du backtest
        backtest_result = await risk_manager.run_strategy_backtest(
            strategy_name=request.strategy_name,
            target_allocations=request.target_allocations,
            backtest_days=request.backtest_days,
            rebalance_frequency_days=request.rebalance_frequency_days,
            transaction_cost_pct=request.transaction_cost_pct
        )
        
        # Conversion en dictionnaire pour API
        result_dict = {
            "success": True,
            "strategy_info": {
                "strategy_name": backtest_result.strategy_name,
                "strategy_description": backtest_result.strategy_description,
                "backtest_period": {
                    "start_date": backtest_result.backtest_start.isoformat(),
                    "end_date": backtest_result.backtest_end.isoformat(),
                    "total_days": backtest_result.backtest_days
                }
            },
            "performance_metrics": {
                "total_return": backtest_result.total_return,
                "annualized_return": backtest_result.annualized_return,
                "volatility": backtest_result.volatility,
                "sharpe_ratio": backtest_result.sharpe_ratio,
                "max_drawdown": backtest_result.max_drawdown,
                "sortino_ratio": backtest_result.sortino_ratio,
                "calmar_ratio": backtest_result.calmar_ratio
            },
            "benchmark_comparison": {
                "benchmark_return": backtest_result.benchmark_return,
                "active_return": backtest_result.active_return,
                "information_ratio": backtest_result.information_ratio,
                "tracking_error": backtest_result.tracking_error
            },
            "risk_metrics": {
                "var_95": backtest_result.var_95,
                "downside_deviation": backtest_result.downside_deviation
            },
            "trading_statistics": {
                "num_rebalances": backtest_result.num_rebalances,
                "avg_turnover": backtest_result.avg_turnover,
                "total_costs": backtest_result.total_costs,
                "rebalance_frequency_days": request.rebalance_frequency_days,
                "transaction_cost_pct": request.transaction_cost_pct
            },
            "performance_chart": {
                "dates": [d.isoformat() for d in backtest_result.dates],
                "portfolio_values": backtest_result.portfolio_values,
                "benchmark_values": backtest_result.benchmark_values,
                "rebalancing_dates": [d.isoformat() for d in backtest_result.rebalancing_dates]
            }
        }
        
        end_time = datetime.now()
        calculation_time = f"{(end_time - start_time).total_seconds():.2f}s"
        result_dict["calculation_time"] = calculation_time
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Erreur backtest: {e}")
        return {
            "success": False,
            "message": f"Erreur lors du backtest: {str(e)}"
        }

@router.get("/alerts")
async def get_risk_alerts(
    severity_filter: Optional[str] = Query(None, description="Filtrer par sévérité (info/low/medium/high/critical)")
):
    """
    Récupère les alertes de risque actives
    
    Retourne toutes les alertes intelligentes générées par le système,
    incluant les dépassements de seuils, problèmes de performance,
    concentration excessive, etc.
    """
    try:
        # Import des balances CoinTracking
        from connectors.cointracking_api import get_current_balances
        
        # Récupération des holdings actuels
        balances_response = await get_current_balances()
        if not balances_response or not isinstance(balances_response, dict):
            return {
                "success": False,
                "message": "Erreur lors de la récupération des données CoinTracking"
            }
        
        balances = balances_response.get('items', [])
        if not balances or len(balances) == 0:
            return {
                "success": False,
                "message": "Aucun holding trouvé dans le portfolio"
            }
        
        # Génération des alertes intelligentes
        alerts = await risk_manager.generate_intelligent_alerts(holdings=balances)
        
        # Filtrage par sévérité si demandé
        severity_enum = None
        if severity_filter:
            try:
                severity_enum = AlertSeverity(severity_filter.lower())
            except ValueError:
                return {
                    "success": False,
                    "message": f"Sévérité invalide. Options: {[s.value for s in AlertSeverity]}"
                }
        
        # Récupération des alertes actives
        active_alerts = risk_manager.alert_system.get_active_alerts(severity_enum)
        
        # Conversion en dictionnaire pour API
        alerts_data = []
        for alert in active_alerts:
            alerts_data.append({
                "id": alert.id,
                "severity": alert.severity.value,
                "category": alert.category.value,
                "title": alert.title,
                "message": alert.message,
                "recommendation": alert.recommendation,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "affected_assets": alert.affected_assets,
                "created_at": alert.created_at.isoformat(),
                "trigger_count": alert.trigger_count,
                "is_active": alert.is_active
            })
        
        return {
            "success": True,
            "alerts": alerts_data,
            "summary": {
                "total_alerts": len(alerts_data),
                "critical": len([a for a in alerts_data if a["severity"] == "critical"]),
                "high": len([a for a in alerts_data if a["severity"] == "high"]),
                "medium": len([a for a in alerts_data if a["severity"] == "medium"]),
                "low": len([a for a in alerts_data if a["severity"] == "low"]),
                "info": len([a for a in alerts_data if a["severity"] == "info"])
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération alertes: {e}")
        return {
            "success": False,
            "message": f"Erreur lors de la récupération: {str(e)}"
        }

# REMOVED: Duplicate alert resolution endpoint - use /api/alerts/resolve/{alert_id} instead
# Alert management should be centralized in alerts_endpoints.py

@router.get("/alerts/history")
async def get_alerts_history(
    limit: int = Query(50, ge=1, le=500, description="Nombre d'alertes à retourner")
):
    """
    Récupère l'historique des alertes
    
    Retourne les alertes passées (résolues et expirées) pour analyse historique.
    """
    try:
        # Récupération de l'historique
        history = risk_manager.alert_system.alert_history[-limit:]
        
        # Conversion en dictionnaire pour API
        history_data = []
        for alert in reversed(history):  # Plus récentes en premier
            history_data.append({
                "id": alert.id,
                "severity": alert.severity.value,
                "category": alert.category.value,
                "title": alert.title,
                "message": alert.message,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "affected_assets": alert.affected_assets,
                "created_at": alert.created_at.isoformat(),
                "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
                "is_active": alert.is_active,
                "resolution_note": alert.resolution_note,
                "trigger_count": alert.trigger_count
            })
        
        return {
            "success": True,
            "history": history_data,
            "total_history_size": len(risk_manager.alert_system.alert_history),
            "returned_count": len(history_data)
        }
        
    except Exception as e:
        logger.error(f"Erreur historique alertes: {e}")
        return {
            "success": False,
            "message": f"Erreur lors de la récupération: {str(e)}"
        }

def _generate_risk_alerts(risk_metrics: RiskMetrics, correlation_matrix: CorrelationMatrix) -> List[Dict[str, Any]]:
    """Génère des alertes de risque intelligentes"""
    
    alerts = []
    
    # Alert VaR élevé
    if risk_metrics.var_95_1d > 0.15:  # VaR > 15%
        alerts.append({
            "level": "high",
            "type": "var_alert",
            "message": f"VaR 95% élevé: {risk_metrics.var_95_1d:.1%} (seuil: 15%)",
            "recommendation": "Considérer réduire l'exposition aux assets volatils"
        })
    
    # Alert volatilité excessive
    if risk_metrics.volatility_annualized > 0.80:  # Volatilité > 80%
        alerts.append({
            "level": "medium",
            "type": "volatility_alert", 
            "message": f"Volatilité élevée: {risk_metrics.volatility_annualized:.1%}",
            "recommendation": "Rééquilibrer vers des assets moins volatils"
        })
    
    # Alert drawdown actuel
    if risk_metrics.current_drawdown > 0.20:  # Drawdown > 20%
        alerts.append({
            "level": "high",
            "type": "drawdown_alert",
            "message": f"Drawdown actuel important: {risk_metrics.current_drawdown:.1%}",
            "recommendation": "Surveiller de près et considérer stop-loss"
        })
    
    # Alert corrélation excessive (manque de diversification)
    # Harmonisé avec l'UI: bon ≥0.7, limité 0.4–0.7, faible <0.4
    try:
        dr = float(correlation_matrix.diversification_ratio)
        if dr < 0.4:
            alerts.append({
                "level": "high",
                "type": "correlation_alert",
                "message": f"Très faible diversification: ratio {dr:.2f}",
                "recommendation": "Réduire l'exposition aux actifs fortement corrélés; ajouter des actifs décorrélés"
            })
        elif dr < 0.7:
            alerts.append({
                "level": "medium",
                "type": "correlation_alert",
                "message": f"Faible diversification: ratio {dr:.2f}",
                "recommendation": "Ajouter des assets moins corrélés"
            })
    except Exception:
        pass
    
    # Alert Sharpe ratio négatif
    if risk_metrics.sharpe_ratio < 0:
        alerts.append({
            "level": "medium",
            "type": "performance_alert",
            "message": f"Sharpe ratio négatif: {risk_metrics.sharpe_ratio:.2f}",
            "recommendation": "Revoir la stratégie d'allocation"
        })
    
    return alerts
