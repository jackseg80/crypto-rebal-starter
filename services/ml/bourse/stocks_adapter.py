"""
Stocks ML Adapter - Reuses existing crypto ML infrastructure for stock market analytics.

This adapter wraps existing ML models (VolatilityPredictor, RegimeDetector, CorrelationForecaster)
and adapts them for traditional stock market analysis.

Key principle: REUSE, don't rebuild!
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import os

from services.ml.bourse.data_sources import StocksDataSource


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types to Python native types for JSON serialization.

    This prevents Pydantic serialization errors with numpy.float32, numpy.int64, etc.
    """
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj
from services.ml.feature_engineering import CryptoFeatureEngineer
from services.ml.models.volatility_predictor import VolatilityPredictor
from services.ml.models.regime_detector import RegimeDetector
from services.ml.models.correlation_forecaster import CorrelationForecaster

logger = logging.getLogger(__name__)


class StocksMLAdapter:
    """
    Adapter to reuse crypto ML models for stock market analysis.

    Provides high-level interface for:
    - Volatility forecasting (1d, 7d, 30d)
    - Market regime detection (Bull/Bear/Sideways)
    - Multi-stock correlation forecasting
    - Technical signals aggregation
    """

    # Stock market regimes (adapted from crypto regimes)
    STOCK_REGIMES = {
        0: "Bear Market",        # Down trend, high fear
        1: "Consolidation",      # Sideways, low volume
        2: "Bull Market",        # Up trend, positive momentum
        3: "Distribution"        # Topping, high volatility
    }

    def __init__(self, models_dir: str = "models/stocks"):
        """
        Initialize stocks ML adapter.

        Args:
            models_dir: Directory to store trained stock models
        """
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)

        # Data source
        self.data_source = StocksDataSource()

        # Feature engineering (100% reusable from crypto)
        self.feature_engineer = CryptoFeatureEngineer()

        # ML models (reused from crypto infrastructure)
        self.volatility_predictor = VolatilityPredictor(
            model_dir=os.path.join(models_dir, "volatility")
        )
        self.regime_detector = RegimeDetector(
            model_dir=os.path.join(models_dir, "regime")
        )
        self.correlation_forecaster = CorrelationForecaster(
            model_dir=os.path.join(models_dir, "correlation")
        )

        logger.info(f"StocksMLAdapter initialized with models_dir={models_dir}")

    async def predict_volatility(
        self,
        symbol: str,
        lookback_days: int = 365,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Predict future volatility for a stock.

        Args:
            symbol: Stock ticker (e.g., "AAPL")
            lookback_days: Days of history to use
            confidence_level: Confidence interval level

        Returns:
            Dict with predictions for 1d, 7d, 30d horizons
        """
        try:
            # Fetch OHLCV data
            ohlcv_data = await self.data_source.get_ohlcv_data(
                symbol=symbol,
                lookback_days=lookback_days
            )

            if len(ohlcv_data) < 30:
                raise ValueError(f"Insufficient data for {symbol}: only {len(ohlcv_data)} days")

            # Check if model exists for this symbol, train if needed
            model_file = os.path.join(self.models_dir, "volatility", f"{symbol}_model.keras")
            if not os.path.exists(model_file):
                logger.info(f"Training volatility model for {symbol}...")
                # Train model on historical data
                training_metadata = self.volatility_predictor.train_model(
                    symbol=symbol,
                    price_data=ohlcv_data,
                    validation_split=0.2
                )
                logger.info(f"Model trained. Metrics: {training_metadata.get('metrics', {})}")

            # Predict volatility
            prediction = self.volatility_predictor.predict_volatility(
                symbol=symbol,
                recent_data=ohlcv_data,
                confidence_level=confidence_level
            )

            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'predictions': prediction.get('predictions', {}),
                'model_type': 'LSTM',
                'lookback_days': lookback_days,
                'confidence_level': confidence_level
            }

            # Convert all numpy types to Python native types
            return convert_numpy_types(result)

        except Exception as e:
            logger.error(f"Error predicting volatility for {symbol}: {e}")
            # Fallback to historical volatility
            return await self._fallback_historical_volatility(symbol, ohlcv_data)

    async def _fallback_historical_volatility(
        self,
        symbol: str,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Fallback to simple historical volatility if ML model fails."""
        returns = self.data_source.calculate_returns(ohlcv_data)

        vol_30d = returns.tail(30).std() * np.sqrt(252)  # Annualized
        vol_90d = returns.tail(90).std() * np.sqrt(252)

        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'predictions': {
                '1d': {
                    'predicted_volatility': vol_30d,
                    'confidence_interval': {'lower': vol_30d * 0.8, 'upper': vol_30d * 1.2}
                },
                '7d': {
                    'predicted_volatility': vol_30d,
                    'confidence_interval': {'lower': vol_30d * 0.8, 'upper': vol_30d * 1.2}
                },
                '30d': {
                    'predicted_volatility': vol_90d,
                    'confidence_interval': {'lower': vol_90d * 0.8, 'upper': vol_90d * 1.2}
                }
            },
            'model_type': 'historical_fallback',
            'note': 'Using historical volatility (ML model unavailable)'
        }

        return convert_numpy_types(result)

    async def detect_market_regime(
        self,
        benchmark: str = "SPY",
        lookback_days: int = 1825  # 5 years for full market cycles
    ) -> Dict[str, Any]:
        """
        Detect current market regime (Bull/Bear/Consolidation/Distribution).

        Args:
            benchmark: Market benchmark ticker (default: SPY)
            lookback_days: Days of history

        Returns:
            Dict with regime prediction and probabilities
        """
        try:
            # Fetch multiple benchmarks for better regime detection
            # Use major market indices for comprehensive view
            benchmarks_to_fetch = [benchmark, "QQQ", "IWM", "DIA"]
            multi_asset_data = {}

            for ticker in benchmarks_to_fetch:
                try:
                    data = await self.data_source.get_benchmark_data(
                        benchmark=ticker,
                        lookback_days=lookback_days
                    )
                    if len(data) >= 60:
                        multi_asset_data[ticker] = data
                        logger.debug(f"Fetched {len(data)} days for {ticker}")
                except Exception as e:
                    logger.warning(f"Failed to fetch {ticker}: {e}")

            if not multi_asset_data:
                raise ValueError("Could not fetch any benchmark data")

            if len(multi_asset_data) < 2:
                logger.warning(f"Only {len(multi_asset_data)} benchmarks available, using single-asset mode")

            # Check if model exists, train if needed
            model_file = os.path.join(self.models_dir, "regime", "regime_neural_best.pth")
            model_needs_training = not os.path.exists(model_file)

            if model_needs_training:
                logger.info(f"Training regime detection model with {len(multi_asset_data)} assets...")
                training_metadata = self.regime_detector.train_model(multi_asset_data)
                logger.info(f"Regime model trained. Val accuracy: {training_metadata.get('final_val_accuracy', 'N/A')}")

            # Predict regime (with auto-retry if model fails to load)
            try:
                prediction = self.regime_detector.predict_regime(
                    multi_asset_data,
                    return_probabilities=True
                )
            except Exception as predict_error:
                # Model exists but failed to load/predict - retrain
                if not model_needs_training:
                    logger.warning(f"Model prediction failed ({predict_error}), retraining...")
                    training_metadata = self.regime_detector.train_model(multi_asset_data)
                    logger.info(f"Regime model retrained. Val accuracy: {training_metadata.get('final_val_accuracy', 'N/A')}")
                    # Retry prediction
                    prediction = self.regime_detector.predict_regime(
                        multi_asset_data,
                        return_probabilities=True
                    )
                else:
                    # Already tried training, still failed
                    raise

            # Adapt regime names for stocks
            regime_id = prediction.get('predicted_regime', 1)
            regime_name = self.STOCK_REGIMES.get(regime_id, "Unknown")

            # Map probabilities to stock regime names
            regime_probs_raw = prediction.get('regime_probabilities', {})

            # Mapping from crypto regime names to stock regime names (by index)
            # crypto: 0=Accumulation, 1=Expansion, 2=Euphoria, 3=Distribution
            # stock:  0=Bear Market, 1=Consolidation, 2=Bull Market, 3=Distribution
            crypto_to_stock_names = {
                'Accumulation': 'Bear Market',
                'Expansion': 'Consolidation',
                'Euphoria': 'Bull Market',
                'Distribution': 'Distribution'
            }

            # Convert probabilities dict
            if isinstance(regime_probs_raw, dict):
                regime_probs = {}
                for crypto_name, prob in regime_probs_raw.items():
                    stock_name = crypto_to_stock_names.get(crypto_name, crypto_name)
                    regime_probs[stock_name] = float(prob)
            else:
                # It's an array/list - map by index
                regime_probs = {
                    self.STOCK_REGIMES.get(i, f"State{i}"): float(prob)
                    for i, prob in enumerate(regime_probs_raw)
                }

            result = {
                'current_regime': regime_name,
                'regime_id': regime_id,
                'confidence': prediction.get('confidence', 0.5),
                'regime_probabilities': regime_probs,
                'benchmark': benchmark,
                'timestamp': datetime.now().isoformat(),
                'characteristics': self._get_regime_characteristics(regime_name)
            }

            # Convert all numpy types to Python native types
            return convert_numpy_types(result)

        except Exception as e:
            logger.error(f"Error detecting market regime: {e}")
            # Fallback to simple trend analysis
            # Use benchmark data if available, otherwise fetch it
            benchmark_data = multi_asset_data.get(benchmark) if 'multi_asset_data' in locals() else None
            if benchmark_data is None:
                try:
                    benchmark_data = await self.data_source.get_benchmark_data(
                        benchmark=benchmark,
                        lookback_days=lookback_days
                    )
                except Exception:
                    benchmark_data = pd.DataFrame()
            return await self._fallback_regime_detection(benchmark, benchmark_data)

    def _get_regime_characteristics(self, regime_name: str) -> Dict[str, str]:
        """Get characteristics for a given regime."""
        characteristics = {
            "Bear Market": {
                "trend": "downward",
                "volatility": "high",
                "sentiment": "fearful"
            },
            "Consolidation": {
                "trend": "sideways",
                "volatility": "low",
                "sentiment": "neutral"
            },
            "Bull Market": {
                "trend": "upward",
                "volatility": "moderate",
                "sentiment": "optimistic"
            },
            "Distribution": {
                "trend": "topping",
                "volatility": "high",
                "sentiment": "cautious"
            }
        }
        return characteristics.get(regime_name, {"trend": "unknown", "volatility": "unknown", "sentiment": "unknown"})

    async def _fallback_regime_detection(
        self,
        symbol: str,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Fallback regime detection using simple trend analysis."""
        if len(ohlcv_data) < 60:
            return {
                'current_regime': 'Unknown',
                'confidence': 0.0,
                'note': 'Insufficient data for regime detection'
            }

        # Calculate moving averages
        close_prices = ohlcv_data['close']
        ma_50 = close_prices.rolling(50).mean()
        ma_200 = close_prices.rolling(200).mean() if len(close_prices) >= 200 else ma_50

        current_price = close_prices.iloc[-1]
        current_ma50 = ma_50.iloc[-1]
        current_ma200 = ma_200.iloc[-1]

        # Simple regime classification
        if current_price > current_ma50 > current_ma200:
            regime = "Bull Market"
            confidence = 0.7
        elif current_price < current_ma50 < current_ma200:
            regime = "Bear Market"
            confidence = 0.7
        elif abs(current_price - current_ma50) / current_ma50 < 0.02:
            regime = "Consolidation"
            confidence = 0.6
        else:
            regime = "Distribution"
            confidence = 0.5

        result = {
            'current_regime': regime,
            'confidence': confidence,
            'regime_probabilities': {regime: confidence},
            'benchmark': symbol,
            'timestamp': datetime.now().isoformat(),
            'characteristics': self._get_regime_characteristics(regime),
            'model_type': 'moving_average_fallback',
            'note': 'Using MA-based regime detection (ML model unavailable)'
        }

        return convert_numpy_types(result)

    async def forecast_correlations(
        self,
        symbols: List[str],
        lookback_days: int = 365,
        horizons: List[int] = [1, 7, 30]
    ) -> Dict[str, Any]:
        """
        Forecast correlations between multiple stocks.

        Args:
            symbols: List of stock tickers
            lookback_days: Days of history
            horizons: Forecast horizons in days

        Returns:
            Dict with correlation matrices for each horizon
        """
        try:
            # Fetch multi-asset data
            multi_asset_data = await self.data_source.get_multi_asset_data(
                symbols=symbols,
                lookback_days=lookback_days
            )

            if len(multi_asset_data) < 2:
                raise ValueError("Need at least 2 stocks for correlation analysis")

            # Check if model exists, train if needed
            model_file = os.path.join(self.models_dir, "correlation", "transformer_model.keras")
            if not os.path.exists(model_file):
                logger.info("Training correlation forecaster...")
                training_metadata = self.correlation_forecaster.train_model(
                    multi_asset_data,
                    validation_split=0.2
                )
                logger.info(f"Correlation model trained. Metrics: {training_metadata.get('metrics', {})}")

            # Predict correlations
            predictions = await self.correlation_forecaster.predict_correlations(
                multi_asset_data,
                horizons=horizons
            )

            result = {
                'symbols': list(multi_asset_data.keys()),
                'predictions': predictions.get('predictions', {}),
                'timestamp': datetime.now().isoformat(),
                'horizons': horizons,
                'model_type': 'Transformer'
            }

            return convert_numpy_types(result)

        except Exception as e:
            logger.error(f"Error forecasting correlations: {e}")
            # Fallback to historical correlations
            return await self._fallback_historical_correlations(symbols, multi_asset_data, horizons)

    async def _fallback_historical_correlations(
        self,
        symbols: List[str],
        multi_asset_data: Dict[str, pd.DataFrame],
        horizons: List[int]
    ) -> Dict[str, Any]:
        """Fallback to historical correlation if ML model fails."""
        returns_df = self.data_source.get_multi_asset_returns(multi_asset_data)

        if len(returns_df) < 30:
            return {
                'symbols': symbols,
                'predictions': {},
                'note': 'Insufficient data for correlation analysis'
            }

        # Calculate historical correlation
        corr_matrix = returns_df.corr()

        # Same correlation for all horizons (simple fallback)
        predictions = {}
        for horizon in horizons:
            predictions[f'{horizon}d'] = {
                'correlation_matrix': corr_matrix.to_dict(),
                'avg_correlation': corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()
            }

        result = {
            'symbols': list(multi_asset_data.keys()),
            'predictions': predictions,
            'timestamp': datetime.now().isoformat(),
            'model_type': 'historical_fallback',
            'note': 'Using historical correlation (ML model unavailable)'
        }

        return convert_numpy_types(result)

    async def generate_signals(
        self,
        symbol: str,
        lookback_days: int = 365
    ) -> Dict[str, Any]:
        """
        Generate aggregated ML signals for a stock.

        Combines:
        - Volatility forecast
        - Market regime
        - Technical indicators

        Returns:
            Dict with overall signal strength and components
        """
        try:
            # Fetch OHLCV data
            ohlcv_data = await self.data_source.get_ohlcv_data(
                symbol=symbol,
                lookback_days=lookback_days
            )

            # Generate technical features
            features_df = self.feature_engineer.create_feature_set(ohlcv_data, symbol=symbol)

            # Get latest features
            latest_features = features_df.iloc[-1]

            # Calculate signal components
            rsi_signal = self._rsi_to_signal(latest_features.get('rsi_14', 50))
            macd_signal = self._macd_to_signal(
                latest_features.get('macd', 0),
                latest_features.get('macd_signal', 0)
            )
            bb_signal = self._bollinger_to_signal(
                latest_features.get('bb_position', 0.5)
            )

            # Aggregate signals (simple weighted average)
            overall_signal = (
                0.4 * rsi_signal +
                0.3 * macd_signal +
                0.3 * bb_signal
            )

            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'overall_signal': overall_signal,
                'confidence': 0.75,
                'signals': {
                    'rsi': {'value': rsi_signal, 'weight': 0.4},
                    'macd': {'value': macd_signal, 'weight': 0.3},
                    'bollinger': {'value': bb_signal, 'weight': 0.3}
                },
                'recommendation': self._signal_to_recommendation(overall_signal),
                'technical_indicators': {
                    'rsi_14': latest_features.get('rsi_14', 50),
                    'macd': latest_features.get('macd', 0),
                    'macd_signal': latest_features.get('macd_signal', 0),
                    'bb_position': latest_features.get('bb_position', 0.5)
                }
            }

            return convert_numpy_types(result)

        except Exception as e:
            logger.error(f"Error generating signals for {symbol}: {e}")
            result = {
                'symbol': symbol,
                'error': str(e),
                'overall_signal': 0.0,
                'confidence': 0.0
            }

            return convert_numpy_types(result)

    def _rsi_to_signal(self, rsi: float) -> float:
        """Convert RSI to signal (-1 to +1)."""
        if rsi > 70:
            return -0.5  # Overbought (bearish)
        elif rsi < 30:
            return 0.5  # Oversold (bullish)
        else:
            return (50 - rsi) / 50  # Linear scaling

    def _macd_to_signal(self, macd: float, macd_signal: float) -> float:
        """Convert MACD to signal (-1 to +1)."""
        diff = macd - macd_signal
        # Normalize to [-1, 1] range
        return np.tanh(diff * 10)

    def _bollinger_to_signal(self, bb_position: float) -> float:
        """Convert Bollinger Band position to signal (-1 to +1)."""
        # bb_position: 0 = lower band, 0.5 = middle, 1 = upper band
        if bb_position > 0.9:
            return -0.5  # Near upper band (overbought)
        elif bb_position < 0.1:
            return 0.5  # Near lower band (oversold)
        else:
            return (0.5 - bb_position) * 2  # Linear scaling

    def _signal_to_recommendation(self, signal: float) -> str:
        """Convert signal to recommendation."""
        if signal > 0.3:
            return "bullish"
        elif signal < -0.3:
            return "bearish"
        else:
            return "neutral"
