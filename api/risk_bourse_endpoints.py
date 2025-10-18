"""
Risk Management Endpoints pour Bourse/Saxo

Fournit les métriques de risque pour portfolios actions/ETF/obligations.
Utilise le nouveau BourseRiskCalculator avec support yfinance.

IMPORTANT: Multi-tenant strict - tous les endpoints acceptent user_id obligatoire.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field

from services.risk.bourse.calculator import BourseRiskCalculator
from api.deps import get_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk/bourse", tags=["risk-management-bourse"])


class RiskDashboardResponse(BaseModel):
    """Response model for bourse risk dashboard"""
    ok: bool
    coverage: float = Field(description="Coverage ratio (0.0-1.0)")
    positions_count: int
    total_value_usd: float
    risk: Dict[str, Any]
    asof: str
    user_id: str


@router.get("/dashboard", response_model=RiskDashboardResponse)
async def bourse_risk_dashboard(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo file to use"),
    min_usd: float = Query(1.0, ge=0.0, description="Minimum position value in USD"),
    lookback_days: int = Query(252, ge=30, le=730, description="Days of price history for metrics"),
    risk_free_rate: float = Query(0.03, ge=0.0, le=0.20, description="Annual risk-free rate"),
    var_method: str = Query("historical", description="VaR calculation method")
) -> RiskDashboardResponse:
    """
    Calculer les métriques de risque pour un portfolio Bourse/Saxo.

    Utilise le nouveau BourseRiskCalculator avec support yfinance pour données historiques.

    Args:
        user_id: ID utilisateur (isolation multi-tenant)
        file_key: Clé du fichier Saxo spécifique (optionnel)
        min_usd: Valeur minimum position USD à inclure
        lookback_days: Jours d'historique prix pour calculs
        risk_free_rate: Taux sans risque annuel pour Sharpe/Sortino
        var_method: Méthode VaR (historical|parametric|montecarlo)

    Returns:
        RiskDashboardResponse avec score + métriques complètes

    Example:
        GET /api/risk/bourse/dashboard?user_id=jack&file_key=portfolio.csv&min_usd=100&lookback_days=252
    """
    try:
        logger.info(f"[risk-bourse] Computing risk dashboard for user {user_id}")

        # 1) Récupérer positions Saxo via l'adaptateur
        # Importer ici pour éviter circulaire
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail

        # Lister les portfolios de l'utilisateur
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)

        if not portfolios:
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=0,
                total_value_usd=0.0,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": "No Saxo portfolios found for this user"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # Prendre le premier portfolio (ou filtrer selon besoin)
        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)

        positions = portfolio_data.get("positions", [])

        if not positions:
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=0,
                total_value_usd=0.0,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": "No positions found in portfolio"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # Filtrer par seuil minimum
        positions_filtered = [p for p in positions if p.get("market_value_usd", 0.0) >= min_usd]

        if not positions_filtered:
            total_value = sum(p.get("market_value_usd", 0.0) for p in positions)
            return RiskDashboardResponse(
                ok=True,
                coverage=0.0,
                positions_count=len(positions),
                total_value_usd=total_value,
                risk={
                    "score": 0,
                    "level": "N/A",
                    "metrics": {},
                    "message": f"All positions below ${min_usd} threshold"
                },
                asof=datetime.utcnow().isoformat(),
                user_id=user_id
            )

        # 2) Calculer risque avec BourseRiskCalculator
        calculator = BourseRiskCalculator(data_source="yahoo")

        risk_result = await calculator.calculate_portfolio_risk(
            positions=positions_filtered,
            benchmark="SPY",  # S&P500 par défaut
            lookback_days=lookback_days,
            risk_free_rate=risk_free_rate,
            var_method=var_method
        )

        # 3) Formater réponse
        total_value = risk_result["metadata"]["portfolio_value"]
        risk_score = risk_result["risk_score"]["risk_score"]
        risk_level = risk_result["risk_score"]["risk_level"]

        # Métriques détaillées
        metrics = risk_result["traditional_risk"]

        # Coverage (proxy basé sur disponibilité données)
        coverage = min(1.0, len(positions_filtered) / max(1, len(positions)))

        return RiskDashboardResponse(
            ok=True,
            coverage=coverage,
            positions_count=len(positions_filtered),
            total_value_usd=total_value,
            risk={
                "score": risk_score,
                "level": risk_level,
                "metrics": metrics
            },
            asof=datetime.utcnow().isoformat(),
            user_id=user_id
        )

    except Exception as e:
        logger.exception(f"[risk-bourse] Error computing risk dashboard for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Risk dashboard computation failed: {str(e)}"
        )


# Helper functions removed - now handled by BourseRiskCalculator


# ==================== ADVANCED ANALYTICS ENDPOINTS ====================

@router.get("/advanced/position-var")
async def get_position_var(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None, description="Specific Saxo file to use"),
    confidence_level: float = Query(0.95, ge=0.8, le=0.99),
    lookback_days: int = Query(252, ge=30, le=730)
):
    """
    Calculate position-level VaR (marginal & component VaR)

    Returns VaR contribution for each position in the portfolio.

    Example:
        GET /api/risk/bourse/advanced/position-var?user_id=jack&confidence_level=0.95
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.advanced_analytics import AdvancedRiskAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[position-var] Computing for user {user_id}")

        # Get portfolio data
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        if len(positions) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 positions for VaR decomposition")

        # Fetch historical returns for all positions
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=lookback_days + 30)

        positions_returns = {}
        portfolio_weights = {}
        total_value = sum(pos.get('market_value_usd', 0) for pos in positions)

        for pos in positions:
            ticker = pos.get('ticker') or pos.get('symbol')
            if not ticker:
                continue

            try:
                price_data = await data_fetcher.fetch_historical_prices(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date
                )

                if len(price_data) < 30:
                    continue

                # Calculate returns
                returns = price_data['close'].pct_change().dropna()
                positions_returns[ticker] = returns

                # Weight in portfolio
                weight = pos.get('market_value_usd', 0) / total_value if total_value > 0 else 0
                portfolio_weights[ticker] = weight

            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
                continue

        if len(positions_returns) < 2:
            raise HTTPException(status_code=400, detail="Insufficient data for position VaR")

        # Calculate position-level VaR
        analytics = AdvancedRiskAnalytics()
        result = analytics.calculate_position_var(
            positions_returns=positions_returns,
            portfolio_weights=portfolio_weights,
            confidence_level=confidence_level
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[position-var] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/advanced/correlation")
async def get_correlation_matrix(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    method: str = Query("pearson", description="Correlation method"),
    lookback_days: int = Query(252, ge=30, le=730)
):
    """
    Calculate correlation matrix between positions

    Returns correlation matrix with hierarchical clustering.

    Example:
        GET /api/risk/bourse/advanced/correlation?user_id=jack&method=pearson
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.advanced_analytics import AdvancedRiskAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[correlation] Computing for user {user_id}")

        # Get positions (similar to position-var)
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        # Fetch returns
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=lookback_days + 30)

        positions_returns = {}
        for pos in positions:
            ticker = pos.get('ticker') or pos.get('symbol')
            if not ticker:
                continue

            try:
                price_data = await data_fetcher.fetch_historical_prices(ticker, start_date, end_date)
                if len(price_data) >= 30:
                    returns = price_data['close'].pct_change().dropna()
                    positions_returns[ticker] = returns
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")

        if len(positions_returns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 positions")

        # Calculate correlation
        analytics = AdvancedRiskAnalytics()
        result = analytics.calculate_correlation_matrix(
            positions_returns=positions_returns,
            method=method
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[correlation] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advanced/stress-test")
async def run_stress_test(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    scenario: str = Query("market_crash", description="Stress scenario name"),
    market_shock: Optional[float] = Query(None, description="Market shock percentage for custom scenario"),
    custom_shocks: Optional[Dict[str, float]] = None
):
    """
    Run stress test on portfolio

    Scenarios: market_crash, market_rally, moderate_selloff, rate_hike, flash_crash, covid_crash, custom

    Example:
        POST /api/risk/bourse/advanced/stress-test?scenario=market_crash
        POST /api/risk/bourse/advanced/stress-test?scenario=custom&market_shock=-0.15
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.advanced_analytics import AdvancedRiskAnalytics

        logger.info(f"[stress-test] Running scenario '{scenario}' for user {user_id}")

        # Get positions
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        # Prepare positions data
        # Use market_value directly since Saxo positions don't separate price/quantity
        positions_data = {}
        for pos in positions:
            ticker = pos.get('ticker') or pos.get('symbol')
            if not ticker:
                continue

            market_value = pos.get('market_value_usd', 0)
            # Simulate price=1, quantity=market_value for stress test
            positions_data[ticker] = {
                'current_price': 1.0,
                'quantity': market_value
            }

        # Convert market_shock to custom_shocks if provided
        if scenario == 'custom' and market_shock is not None and custom_shocks is None:
            custom_shocks = {ticker: market_shock for ticker in positions_data.keys()}
            logger.info(f"[stress-test] Using market_shock={market_shock} for all positions")

        # Run stress test
        analytics = AdvancedRiskAnalytics()
        result = analytics.run_stress_test(
            positions_data=positions_data,
            scenario=scenario,
            custom_shocks=custom_shocks
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[stress-test] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/advanced/fx-exposure")
async def get_fx_exposure(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    base_currency: str = Query("USD", description="Base currency for reporting")
):
    """
    Analyze currency exposure in portfolio

    Returns FX exposure breakdown with hedging suggestions.

    Example:
        GET /api/risk/bourse/advanced/fx-exposure?user_id=jack&base_currency=USD
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.advanced_analytics import AdvancedRiskAnalytics

        logger.info(f"[fx-exposure] Analyzing for user {user_id}")

        # Get positions
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        # Analyze FX exposure
        analytics = AdvancedRiskAnalytics()
        result = analytics.analyze_fx_exposure(
            positions=positions,
            base_currency=base_currency
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[fx-exposure] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SPECIALIZED ANALYTICS ENDPOINTS ====================

@router.get("/specialized/earnings")
async def get_earnings_prediction(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    ticker: str = Query(..., description="Ticker to analyze"),
    lookback_days: int = Query(365, ge=30, le=1825)
):
    """
    Predict earnings impact on volatility

    Returns earnings predictions with alerts for upcoming earnings dates.

    Example:
        GET /api/risk/bourse/specialized/earnings?user_id=jack&ticker=AAPL
    """
    try:
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[earnings] Analyzing {ticker} for user {user_id}")

        # Fetch historical price data
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=lookback_days + 30)

        price_data = await data_fetcher.fetch_historical_prices(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date
        )

        if len(price_data) < 60:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {ticker}")

        # Analyze earnings impact
        # Note: earnings_dates would come from an API (e.g., yfinance, Financial Modeling Prep)
        # For now, we'll use None and the analyzer will provide generic estimates
        analytics = SpecializedBourseAnalytics()
        result = analytics.predict_earnings_impact(
            ticker=ticker,
            price_history=price_data,
            earnings_dates=None  # TODO: Integrate earnings calendar API
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[earnings] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/specialized/sector-rotation")
async def get_sector_rotation(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    lookback_days: int = Query(60, ge=30, le=180)
):
    """
    Detect sector rotation patterns

    Returns sector performance metrics with rotation signals.

    Example:
        GET /api/risk/bourse/specialized/sector-rotation?user_id=jack&lookback_days=60
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[sector-rotation] Analyzing for user {user_id}")

        # Get portfolio positions
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        # Fetch returns for all positions
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=lookback_days + 30)

        positions_returns = {}
        for pos in positions:
            ticker = pos.get('ticker') or pos.get('symbol')
            if not ticker:
                continue

            try:
                price_data = await data_fetcher.fetch_historical_prices(ticker, start_date, end_date)
                if len(price_data) >= 30:
                    returns = price_data['close'].pct_change().dropna()
                    positions_returns[ticker] = returns
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")

        if len(positions_returns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 positions")

        # Detect sector rotation
        analytics = SpecializedBourseAnalytics()
        result = analytics.detect_sector_rotation(
            positions_returns=positions_returns,
            lookback_days=lookback_days
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[sector-rotation] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/specialized/beta-forecast")
async def get_beta_forecast(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    ticker: str = Query(..., description="Ticker to analyze"),
    benchmark: str = Query("SPY", description="Benchmark ticker"),
    forecast_method: str = Query("ewma", description="Forecast method"),
    lookback_days: int = Query(252, ge=60, le=730)
):
    """
    Forecast dynamic beta vs benchmark

    Returns beta forecast with trend analysis.

    Example:
        GET /api/risk/bourse/specialized/beta-forecast?user_id=jack&ticker=AAPL&benchmark=SPY
    """
    try:
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[beta-forecast] Analyzing {ticker} vs {benchmark} for user {user_id}")

        # Fetch historical data
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=lookback_days + 30)

        # Get position and benchmark data
        position_data = await data_fetcher.fetch_historical_prices(ticker, start_date, end_date)
        benchmark_data = await data_fetcher.fetch_benchmark_prices(benchmark, start_date, end_date)

        if len(position_data) < 60 or len(benchmark_data) < 60:
            raise HTTPException(status_code=400, detail="Insufficient data")

        # Calculate returns
        position_returns = position_data['close'].pct_change().dropna()
        benchmark_returns = benchmark_data['close'].pct_change().dropna()

        # Forecast beta
        analytics = SpecializedBourseAnalytics()
        result = analytics.forecast_beta(
            position_returns=position_returns,
            benchmark_returns=benchmark_returns,
            forecast_method=forecast_method
        )

        return {
            "ok": True,
            "user_id": user_id,
            "ticker": ticker,
            "benchmark": benchmark,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[beta-forecast] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/specialized/dividends")
async def get_dividend_analysis(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    ticker: str = Query(..., description="Ticker to analyze")
):
    """
    Analyze dividend impact and yield

    Returns dividend analysis with yield and ex-dividend dates.

    Example:
        GET /api/risk/bourse/specialized/dividends?user_id=jack&ticker=AAPL
    """
    try:
        from services.risk.bourse.data_fetcher import BourseDataFetcher
        from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics
        from datetime import datetime, timedelta

        logger.info(f"[dividends] Analyzing {ticker} for user {user_id}")

        # Fetch historical price data
        data_fetcher = BourseDataFetcher()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=730)  # 2 years for dividend analysis

        price_data = await data_fetcher.fetch_historical_prices(ticker, start_date, end_date)

        if len(price_data) < 30:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {ticker}")

        # Get dividend data (if available from yfinance)
        dividends = None
        try:
            import yfinance as yf
            ticker_obj = yf.Ticker(ticker)
            dividends = ticker_obj.dividends
        except Exception as e:
            logger.warning(f"Could not fetch dividends for {ticker}: {e}")

        # Analyze dividends
        analytics = SpecializedBourseAnalytics()
        result = analytics.analyze_dividends(
            ticker=ticker,
            price_history=price_data,
            dividends=dividends
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[dividends] Error for {ticker}: {e}")
        # Return graceful fallback instead of crashing
        return {
            "ok": False,
            "user_id": user_id,
            "ticker": ticker,
            "error": str(e),
            "current_yield": 0.0,
            "annual_dividend": 0.0,
            "payout_frequency": "unknown",
            "next_ex_dividend_date": None,
            "days_until_ex_dividend": None,
            "avg_price_drop_ex_div": 0.0,
            "total_dividends_12m": 0.0,
            "dividend_growth_rate": 0.0,
            "has_dividend_data": False,
            "note": "Dividend data unavailable or error occurred"
        }


@router.get("/specialized/margin")
async def get_margin_monitoring(
    user_id: str = Depends(get_active_user),
    file_key: Optional[str] = Query(None),
    account_equity: Optional[float] = Query(None, description="Override account equity"),
    maintenance_margin_pct: float = Query(0.25, ge=0.10, le=0.50),
    initial_margin_pct: float = Query(0.50, ge=0.25, le=1.0)
):
    """
    Monitor margin requirements for leveraged positions

    Returns margin analysis with warnings and recommendations.

    Example:
        GET /api/risk/bourse/specialized/margin?user_id=jack&account_equity=100000
    """
    try:
        from adapters.saxo_adapter import list_portfolios_overview, get_portfolio_detail
        from services.risk.bourse.specialized_analytics import SpecializedBourseAnalytics

        logger.info(f"[margin] Monitoring for user {user_id}")

        # Get portfolio positions
        portfolios = list_portfolios_overview(user_id=user_id, file_key=file_key)
        if not portfolios:
            raise HTTPException(status_code=404, detail="No portfolios found")

        portfolio_id = portfolios[0].get("portfolio_id")
        portfolio_data = get_portfolio_detail(portfolio_id=portfolio_id, user_id=user_id, file_key=file_key)
        positions = portfolio_data.get("positions", [])

        # Calculate account equity if not provided
        if account_equity is None:
            account_equity = sum(pos.get('market_value_usd', 0) for pos in positions)

        # Monitor margin
        analytics = SpecializedBourseAnalytics()
        result = analytics.monitor_margin(
            positions=positions,
            account_equity=account_equity,
            maintenance_margin_pct=maintenance_margin_pct,
            initial_margin_pct=initial_margin_pct
        )

        return {
            "ok": True,
            "user_id": user_id,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[margin] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
