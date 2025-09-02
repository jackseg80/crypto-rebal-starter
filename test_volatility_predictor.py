"""
Test script for Volatility Predictor
Quick validation of the LSTM-based volatility prediction system
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ml.models.volatility_predictor import VolatilityPredictor
from services.ml.data_pipeline import MLDataPipeline

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_synthetic_crypto_data(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    Generate synthetic crypto price data for testing
    """
    logger.info(f"Generating {days} days of synthetic data for {symbol}")
    
    # Base parameters for different cryptos
    base_configs = {
        'BTC': {'price': 45000, 'volatility': 0.05, 'trend': 0.0002},
        'ETH': {'price': 3000, 'volatility': 0.06, 'trend': 0.0001},
        'SOL': {'price': 100, 'volatility': 0.08, 'trend': 0.0003},
        'ADA': {'price': 0.5, 'volatility': 0.07, 'trend': 0.0001}
    }
    
    config = base_configs.get(symbol, {'price': 100, 'volatility': 0.06, 'trend': 0.0002})
    
    # Generate dates
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate price series with random walk + trend
    np.random.seed(42 + hash(symbol) % 1000)  # Reproducible but different per symbol
    
    returns = np.random.normal(
        config['trend'], 
        config['volatility'], 
        size=days
    )
    
    # Add some crypto-specific patterns
    # Weekend dips
    weekend_mask = pd.Series(dates).dt.dayofweek >= 5
    returns[weekend_mask] *= 0.8
    
    # Periodic volatility clustering
    volatility_cycle = np.sin(np.arange(days) / 30) * 0.02 + 1
    returns *= volatility_cycle
    
    # Calculate prices
    prices = config['price'] * np.cumprod(1 + returns)
    
    # Generate OHLCV data
    data = []
    for i, (date, close_price) in enumerate(zip(dates, prices)):
        # Simple OHLC approximation
        daily_vol = abs(returns[i]) * close_price
        high = close_price + np.random.uniform(0, daily_vol * 0.5)
        low = close_price - np.random.uniform(0, daily_vol * 0.5)
        open_price = prices[i-1] if i > 0 else close_price
        
        # Volume approximation (higher volume on high volatility days)
        volume = 1000000 * (1 + abs(returns[i]) * 10) * np.random.uniform(0.5, 2.0)
        
        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=dates)
    logger.info(f"Generated synthetic data for {symbol}: {len(df)} days")
    return df

def test_volatility_predictor():
    """
    Test the Volatility Predictor with synthetic data
    """
    logger.info("Starting Volatility Predictor Test")
    
    try:
        # Initialize components
        predictor = VolatilityPredictor(model_dir="test_models")
        
        # Test with BTC synthetic data
        symbol = "BTC"
        logger.info(f"Testing with {symbol}")
        
        # Generate synthetic data
        price_data = generate_synthetic_crypto_data(symbol, days=500)
        
        logger.info(f"Price data shape: {price_data.shape}")
        logger.info(f"Price range: ${price_data['close'].min():.2f} - ${price_data['close'].max():.2f}")
        
        # Test feature preparation
        logger.info("Testing feature preparation...")
        features_df = predictor.prepare_features(price_data, symbol)
        logger.info(f"Features prepared: {features_df.shape[1]} features, {features_df.shape[0]} samples")
        
        # Test model training (with smaller parameters for quick test)
        logger.info("Testing model training...")
        predictor.epochs = 5  # Reduce epochs for quick test
        predictor.early_stopping_patience = 3
        
        training_metadata = predictor.train_model(symbol, price_data, validation_split=0.2)
        
        logger.info("Training completed!")
        logger.info(f"Training samples: {training_metadata['train_samples']}")
        logger.info(f"Validation loss: {training_metadata['best_val_loss']:.6f}")
        
        # Test prediction
        logger.info("Testing prediction...")
        
        # Use recent data for prediction
        recent_data = price_data.iloc[-365:]  # Last year
        prediction_result = predictor.predict_volatility(symbol, recent_data)
        
        logger.info("Prediction completed!")
        logger.info(f"Current volatility: {prediction_result['current_realized_volatility']:.2%}")
        
        for horizon, pred in prediction_result['predictions'].items():
            logger.info(f"{horizon} prediction: {pred['predicted_volatility']:.2%} "
                       f"(CI: {pred['confidence_interval']['lower']:.2%} - {pred['confidence_interval']['upper']:.2%})")
        
        # Test model status
        status = predictor.get_model_status()
        logger.info(f"Models loaded: {status['models_loaded']}")
        logger.info(f"Available models: {status['symbols']}")
        
        logger.info("✅ All tests passed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_data_pipeline():
    """
    Test the ML Data Pipeline
    """
    logger.info("Testing ML Data Pipeline")
    
    try:
        pipeline = MLDataPipeline()
        
        # Test synthetic data generation and validation
        symbol = "ETH"
        price_data = generate_synthetic_crypto_data(symbol, days=300)
        
        # Test data validation and cleaning
        cleaned_data = pipeline._validate_and_clean_data(price_data, symbol)
        logger.info(f"Data validation: {len(price_data)} -> {len(cleaned_data)} samples")
        
        # Test feature and target preparation
        prepared_data = pipeline._prepare_features_and_targets(cleaned_data, symbol, [1, 7, 30])
        logger.info(f"Feature preparation: {prepared_data.shape[1]} columns, {prepared_data.shape[0]} samples")
        
        # Check for target columns
        target_cols = [col for col in prepared_data.columns if col.startswith('target_')]
        logger.info(f"Target columns: {len(target_cols)} - {target_cols[:3]}...")
        
        logger.info("✅ Data Pipeline test passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Data Pipeline test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("VOLATILITY PREDICTOR TEST SUITE")
    logger.info("="*60)
    
    success = True
    
    # Test Data Pipeline
    logger.info("\n" + "="*40)
    logger.info("TEST 1: ML Data Pipeline")
    logger.info("="*40)
    success &= test_data_pipeline()
    
    # Test Volatility Predictor
    logger.info("\n" + "="*40)
    logger.info("TEST 2: Volatility Predictor")  
    logger.info("="*40)
    success &= test_volatility_predictor()
    
    # Final result
    logger.info("\n" + "="*60)
    if success:
        logger.info("🎉 ALL TESTS PASSED! Volatility Predictor is ready.")
    else:
        logger.info("❌ Some tests failed. Check logs above.")
    logger.info("="*60)
    
    sys.exit(0 if success else 1)