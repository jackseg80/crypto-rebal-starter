"""
ML endpoints for stock market (bourse) analytics.

Provides ML-powered predictions:
- Volatility forecasting (LSTM)
- Market regime detection (HMM + Neural Network)
- Correlation forecasting (Transformer)
- Technical signals aggregation
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from services.ml.bourse.stocks_adapter import StocksMLAdapter

logger = logging.getLogger(__name__)
router = APIRouter()

# Global adapter instance (shared across requests for performance)
stocks_ml_adapter = StocksMLAdapter(models_dir="models/stocks")


# Response Models
class VolatilityForecastResponse(BaseModel):
    """Response model for volatility forecast"""
    symbol: str
    timestamp: str
    predictions: Dict[str, Any]
    model_type: str
    lookback_days: int
    confidence_level: float
    note: Optional[str] = None


class RegimeDetectionResponse(BaseModel):
    """Response model for regime detection"""
    current_regime: str
    regime_id: Optional[int] = None
    confidence: float
    regime_probabilities: Dict[str, float]
    benchmark: str
    timestamp: str
    characteristics: Dict[str, str]
    model_type: Optional[str] = None
    note: Optional[str] = None


class CorrelationForecastResponse(BaseModel):
    """Response model for correlation forecast"""
    symbols: List[str]
    predictions: Dict[str, Any]
    timestamp: str
    horizons: List[int]
    model_type: str
    note: Optional[str] = None


class SignalsResponse(BaseModel):
    """Response model for ML signals"""
    symbol: str
    timestamp: str
    overall_signal: float
    confidence: float
    signals: Dict[str, Dict[str, float]]
    recommendation: str
    technical_indicators: Dict[str, float]
    error: Optional[str] = None


# Endpoints

@router.get("/api/ml/bourse/forecast", response_model=VolatilityForecastResponse)
async def forecast_volatility(
    symbol: str = Query("AAPL", description="Stock ticker symbol"),
    lookback_days: int = Query(365, ge=60, le=1825, description="Days of history to use"),
    confidence_level: float = Query(0.95, ge=0.8, le=0.99, description="Confidence interval level")
):
    """
    Forecast future volatility for a stock using LSTM model.

    Returns predictions for 1-day, 7-day, and 30-day horizons with confidence intervals.

    Example:
        GET /api/ml/bourse/forecast?symbol=AAPL&lookback_days=365&confidence_level=0.95
    """
    try:
        logger.info(f"Volatility forecast requested for {symbol} (lookback={lookback_days}d)")

        result = await stocks_ml_adapter.predict_volatility(
            symbol=symbol,
            lookback_days=lookback_days,
            confidence_level=confidence_level
        )

        return VolatilityForecastResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error in volatility forecast: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error forecasting volatility for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/api/ml/bourse/regime", response_model=RegimeDetectionResponse)
async def detect_regime(
    benchmark: str = Query("SPY", description="Market benchmark ticker"),
    lookback_days: int = Query(7300, ge=60, le=10950, description="Days of history (20 years default to capture 4-5 full market cycles, max 30 years)")
):
    """
    Detect current market regime (Bull/Bear/Consolidation/Distribution).

    Uses HMM + Neural Network hybrid model trained on market data.
    Default 5 years (1825 days) to capture full bull/bear cycles.

    Example:
        GET /api/ml/bourse/regime?benchmark=SPY&lookback_days=1825
    """
    try:
        logger.info(f"Market regime detection requested (benchmark={benchmark}, lookback={lookback_days}d)")

        result = await stocks_ml_adapter.detect_market_regime(
            benchmark=benchmark,
            lookback_days=lookback_days
        )

        return RegimeDetectionResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error in regime detection: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting market regime: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/api/ml/bourse/correlation", response_model=CorrelationForecastResponse)
async def forecast_correlation(
    symbols: str = Query("AAPL,MSFT,GOOGL", description="Comma-separated stock tickers"),
    lookback_days: int = Query(365, ge=90, le=1825, description="Days of history"),
    horizons: str = Query("1,7,30", description="Comma-separated forecast horizons (days)")
):
    """
    Forecast future correlations between multiple stocks using Transformer model.

    Returns correlation matrices for specified horizons.

    Example:
        GET /api/ml/bourse/correlation?symbols=AAPL,MSFT,GOOGL&horizons=1,7,30
    """
    try:
        # Parse comma-separated inputs
        symbols_list = [s.strip().upper() for s in symbols.split(',')]
        horizons_list = [int(h.strip()) for h in horizons.split(',')]

        if len(symbols_list) < 2:
            raise ValueError("Need at least 2 symbols for correlation analysis")

        logger.info(f"Correlation forecast requested for {len(symbols_list)} symbols")

        result = await stocks_ml_adapter.forecast_correlations(
            symbols=symbols_list,
            lookback_days=lookback_days,
            horizons=horizons_list
        )

        return CorrelationForecastResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error in correlation forecast: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error forecasting correlations: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/api/ml/bourse/signals", response_model=SignalsResponse)
async def generate_signals(
    symbol: str = Query("AAPL", description="Stock ticker symbol"),
    lookback_days: int = Query(365, ge=60, le=1825, description="Days of history")
):
    """
    Generate aggregated ML signals for a stock.

    Combines technical indicators (RSI, MACD, Bollinger Bands) into overall signal.

    Signal range: -1 (strong bearish) to +1 (strong bullish)

    Example:
        GET /api/ml/bourse/signals?symbol=AAPL&lookback_days=365
    """
    try:
        logger.info(f"ML signals requested for {symbol} (lookback={lookback_days}d)")

        result = await stocks_ml_adapter.generate_signals(
            symbol=symbol,
            lookback_days=lookback_days
        )

        return SignalsResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error in signal generation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/api/ml/bourse/dashboard")
async def get_ml_dashboard(
    symbol: str = Query("AAPL", description="Stock ticker symbol"),
    benchmark: str = Query("SPY", description="Market benchmark"),
    lookback_days: int = Query(365, ge=90, le=1825, description="Days of history")
):
    """
    Get comprehensive ML analytics dashboard for a stock.

    Combines all ML predictions into single response:
    - Volatility forecast
    - Market regime
    - Technical signals

    Example:
        GET /api/ml/bourse/dashboard?symbol=AAPL&benchmark=SPY&lookback_days=365
    """
    try:
        logger.info(f"ML dashboard requested for {symbol} (benchmark={benchmark})")

        # Fetch all predictions in parallel
        import asyncio

        volatility_task = stocks_ml_adapter.predict_volatility(symbol, lookback_days)
        regime_task = stocks_ml_adapter.detect_market_regime(benchmark, lookback_days)
        signals_task = stocks_ml_adapter.generate_signals(symbol, lookback_days)

        volatility, regime, signals = await asyncio.gather(
            volatility_task,
            regime_task,
            signals_task,
            return_exceptions=True
        )

        # Handle any exceptions
        if isinstance(volatility, Exception):
            logger.error(f"Volatility forecast failed: {volatility}")
            volatility = {'error': str(volatility)}

        if isinstance(regime, Exception):
            logger.error(f"Regime detection failed: {regime}")
            regime = {'error': str(regime)}

        if isinstance(signals, Exception):
            logger.error(f"Signal generation failed: {signals}")
            signals = {'error': str(signals)}

        return {
            'symbol': symbol,
            'benchmark': benchmark,
            'timestamp': datetime.now().isoformat(),
            'volatility_forecast': volatility,
            'market_regime': regime,
            'technical_signals': signals,
            'lookback_days': lookback_days
        }

    except Exception as e:
        logger.error(f"Error generating ML dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/api/ml/bourse/train")
async def train_models(
    symbols: str = Query("AAPL,MSFT,GOOGL", description="Comma-separated stock tickers"),
    lookback_days: int = Query(730, ge=365, le=3650, description="Training data period")
):
    """
    Train ML models on historical stock data.

    This endpoint trains:
    - Volatility predictor (LSTM)
    - Regime detector (HMM + NN)
    - Correlation forecaster (Transformer)

    Training can take several minutes.

    Example:
        POST /api/ml/bourse/train?symbols=AAPL,MSFT,GOOGL&lookback_days=730
    """
    try:
        symbols_list = [s.strip().upper() for s in symbols.split(',')]

        logger.info(f"Training ML models for {len(symbols_list)} symbols (lookback={lookback_days}d)")

        results = []

        for symbol in symbols_list:
            try:
                # Train volatility model
                vol_result = await stocks_ml_adapter.predict_volatility(
                    symbol=symbol,
                    lookback_days=lookback_days
                )
                results.append({
                    'symbol': symbol,
                    'model': 'volatility',
                    'status': 'success',
                    'model_type': vol_result.get('model_type', 'LSTM')
                })
            except Exception as e:
                logger.error(f"Failed to train volatility model for {symbol}: {e}")
                results.append({
                    'symbol': symbol,
                    'model': 'volatility',
                    'status': 'failed',
                    'error': str(e)
                })

        # Train regime detector (once, uses benchmark)
        try:
            regime_result = await stocks_ml_adapter.detect_market_regime(
                benchmark="SPY",
                lookback_days=lookback_days
            )
            results.append({
                'model': 'regime_detector',
                'status': 'success',
                'current_regime': regime_result.get('current_regime', 'Unknown')
            })
        except Exception as e:
            logger.error(f"Failed to train regime detector: {e}")
            results.append({
                'model': 'regime_detector',
                'status': 'failed',
                'error': str(e)
            })

        # Train correlation forecaster
        if len(symbols_list) >= 2:
            try:
                corr_result = await stocks_ml_adapter.forecast_correlations(
                    symbols=symbols_list,
                    lookback_days=lookback_days
                )
                results.append({
                    'model': 'correlation_forecaster',
                    'status': 'success',
                    'symbols': symbols_list
                })
            except Exception as e:
                logger.error(f"Failed to train correlation forecaster: {e}")
                results.append({
                    'model': 'correlation_forecaster',
                    'status': 'failed',
                    'error': str(e)
                })

        return {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'training_results': results,
            'lookback_days': lookback_days
        }

    except Exception as e:
        logger.error(f"Error training models: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/api/ml/bourse/model-info")
async def get_model_info(model_type: str = Query("regime", description="Model type (regime, volatility, correlation)")):
    """
    Retourne infos sur l'état d'un modèle ML.

    Utile pour debug et monitoring:
    - Âge du modèle
    - Dernière mise à jour
    - Besoin de réentraînement
    - Intervalle de réentraînement configuré

    Example:
        GET /api/ml/bourse/model-info?model_type=regime
    """
    try:
        from services.ml.bourse.training_scheduler import MLTrainingScheduler
        from pathlib import Path

        # Model paths configuration
        model_paths = {
            "regime": "models/stocks/regime/regime_neural_best.pth",
            "volatility": "models/stocks/volatility/volatility_model.pkl",
            "correlation": "models/stocks/correlation/correlation_model.pkl"
        }

        if model_type not in model_paths:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model_type. Must be one of: {', '.join(model_paths.keys())}"
            )

        model_path = Path(model_paths[model_type])
        info = MLTrainingScheduler.get_model_info(model_path)

        # Add training interval info
        interval = MLTrainingScheduler.TRAINING_INTERVALS.get(model_type, timedelta(days=7))

        return {
            "model_type": model_type,
            "model_path": str(model_path),
            "training_interval_days": interval.days,
            "training_interval_hours": interval.total_seconds() / 3600,
            **info,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model info for {model_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
