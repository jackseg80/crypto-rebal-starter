"""
Machine Learning services for crypto portfolio management
Advanced ML models for volatility prediction, regime detection, correlation forecasting, sentiment analysis, and automated rebalancing
"""

# Optional imports (require torch/heavy dependencies)
# These are imported only if explicitly needed
__all__ = []

try:
    from .models.volatility_predictor import VolatilityPredictor
    __all__.append('VolatilityPredictor')
except ImportError:
    pass

try:
    from .models.regime_detector import RegimeDetector
    __all__.append('RegimeDetector')
except ImportError:
    pass

try:
    from .models.correlation_forecaster import CorrelationForecaster
    __all__.append('CorrelationForecaster')
except ImportError:
    pass

try:
    from .models.sentiment_analyzer import SentimentAnalysisEngine
    __all__.append('SentimentAnalysisEngine')
except ImportError:
    pass

try:
    from .models.rebalancing_engine import RebalancingEngine
    __all__.append('RebalancingEngine')
except ImportError:
    pass

try:
    from .data_pipeline import MLDataPipeline
    __all__.append('MLDataPipeline')
except ImportError:
    pass

try:
    from .feature_engineering import CryptoFeatureEngineer
    __all__.append('CryptoFeatureEngineer')
except ImportError:
    pass