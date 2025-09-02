"""
Test script for Correlation Forecaster
Quick validation of the Transformer-based correlation prediction system
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ml.models.correlation_forecaster import CorrelationForecaster
from services.ml.data_pipeline import MLDataPipeline

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_synthetic_multi_asset_data(symbols: list, days: int = 730) -> dict:
    """
    Generate synthetic multi-asset price data with realistic correlations
    """
    logger.info(f"Generating {days} days of synthetic data for {len(symbols)} assets")
    
    # Base parameters for different assets
    base_configs = {
        'BTC': {'price': 45000, 'volatility': 0.05, 'trend': 0.0002},
        'ETH': {'price': 3000, 'volatility': 0.06, 'trend': 0.0001},
        'SOL': {'price': 100, 'volatility': 0.08, 'trend': 0.0003},
        'ADA': {'price': 0.5, 'volatility': 0.07, 'trend': 0.0001},
        'AVAX': {'price': 30, 'volatility': 0.09, 'trend': 0.0002},
        'DOT': {'price': 8, 'volatility': 0.08, 'trend': 0.0001},
        'MATIC': {'price': 1.2, 'volatility': 0.10, 'trend': 0.0004},
        'LINK': {'price': 15, 'volatility': 0.07, 'trend': 0.0002}
    }
    
    # Generate correlated returns
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Create base correlation structure
    n_assets = len(symbols)
    base_correlation = 0.3 + 0.4 * np.random.rand()  # Random base correlation
    
    # Generate correlated random numbers
    correlation_matrix = np.full((n_assets, n_assets), base_correlation)
    np.fill_diagonal(correlation_matrix, 1.0)
    
    # Ensure positive semi-definite
    eigenvals, eigenvecs = np.linalg.eigh(correlation_matrix)
    eigenvals = np.maximum(eigenvals, 0.01)  # Ensure positive eigenvalues
    correlation_matrix = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
    
    # Generate correlated returns
    independent_returns = np.random.normal(0, 1, (days, n_assets))
    chol_decomp = np.linalg.cholesky(correlation_matrix)
    correlated_returns = independent_returns @ chol_decomp.T
    
    # Generate price data for each asset
    multi_asset_data = {}
    
    for i, symbol in enumerate(symbols):
        config = base_configs.get(symbol, {'price': 100, 'volatility': 0.06, 'trend': 0.0002})
        
        # Scale returns by asset-specific volatility and add trend
        returns = (correlated_returns[:, i] * config['volatility']) + config['trend']
        
        # Add time-varying volatility clustering
        volatility_cycle = 1 + 0.3 * np.sin(np.arange(days) / 30) * np.exp(-np.arange(days) / 365)
        returns *= volatility_cycle
        
        # Calculate prices
        prices = config['price'] * np.cumprod(1 + returns)
        
        # Generate OHLCV data
        data = []
        for j, (date, close_price) in enumerate(zip(dates, prices)):
            # Simple OHLC approximation
            daily_vol = abs(returns[j]) * close_price
            high = close_price + np.random.uniform(0, daily_vol * 0.3)
            low = close_price - np.random.uniform(0, daily_vol * 0.3)
            open_price = prices[j-1] if j > 0 else close_price
            
            # Volume approximation
            volume = 1000000 * (1 + abs(returns[j]) * 5) * np.random.uniform(0.7, 1.5)
            
            data.append({
                'open': max(open_price, 0.001),
                'high': max(high, close_price),
                'low': min(low, close_price),
                'close': max(close_price, 0.001),
                'volume': volume
            })
        
        df = pd.DataFrame(data, index=dates)
        multi_asset_data[symbol] = df
        logger.info(f"Generated {symbol}: {len(df)} days, price range ${df['close'].min():.2f}-${df['close'].max():.2f}")
    
    return multi_asset_data

def test_correlation_forecaster():
    """
    Test the Correlation Forecaster with synthetic multi-asset data
    """
    logger.info("Starting Correlation Forecaster Test")
    
    try:
        # Initialize components
        forecaster = CorrelationForecaster(model_dir="test_models/correlation")
        
        # Test assets
        test_symbols = ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX', 'DOT']
        logger.info(f"Testing with {len(test_symbols)} assets: {test_symbols}")
        
        # Generate synthetic multi-asset data
        multi_asset_data = generate_synthetic_multi_asset_data(test_symbols, days=800)
        
        logger.info(f"Multi-asset data generated for {len(multi_asset_data)} assets")
        
        # Test feature preparation
        logger.info("Testing multi-asset feature preparation...")
        features, targets, symbols = forecaster.prepare_multi_asset_features(
            multi_asset_data, 
            lookback_days=400
        )
        
        logger.info(f"Features prepared: {features.shape}")
        logger.info(f"Targets prepared: {targets.shape}")
        logger.info(f"Asset symbols: {symbols}")
        
        # Test model training (with reduced parameters for quick test)
        logger.info("Testing Transformer model training...")
        forecaster.config['n_layers'] = 3  # Reduce layers for quick test
        forecaster.config['d_model'] = 128  # Reduce model size
        forecaster.epochs = 5  # Reduce epochs
        forecaster.early_stopping_patience = 3
        
        training_results = forecaster.train_model(multi_asset_data, validation_split=0.2)
        
        logger.info("Training completed!")
        for horizon, result in training_results.items():
            logger.info(f"Horizon {horizon}d: {result['train_samples']} train, {result['val_samples']} val samples")
            logger.info(f"Best validation loss: {result['best_val_loss']:.6f}")
        
        # Test prediction
        logger.info("Testing correlation prediction...")
        
        # Use recent subset for prediction
        recent_data = {}
        for symbol, df in multi_asset_data.items():
            recent_data[symbol] = df.iloc[-200:]  # Last 200 days
        
        prediction_result = forecaster.predict_correlations(
            recent_data, 
            horizons=[1, 7, 30]
        )
        
        logger.info("Prediction completed!")
        
        if 'predictions' in prediction_result:
            for horizon, pred in prediction_result['predictions'].items():
                logger.info(f"Prediction for {horizon}:")
                logger.info(f"  Confidence score: {pred['confidence_score']:.3f}")
                logger.info(f"  Asset volatilities available: {len(pred['predicted_volatilities'])}")
                
                # Show sample correlations
                corr_matrix = pred['correlation_matrix']
                sample_pairs = [(symbols[0], symbols[1]), (symbols[1], symbols[2])]
                for asset1, asset2 in sample_pairs:
                    if asset1 in corr_matrix and asset2 in corr_matrix[asset1]:
                        corr = corr_matrix[asset1][asset2]
                        logger.info(f"  {asset1}-{asset2} correlation: {corr:.3f}")
        
        # Test correlation analysis
        logger.info("Testing correlation analysis...")
        
        analysis_result = forecaster.analyze_correlation_changes(
            recent_data,
            lookback_days=120
        )
        
        if 'error' not in analysis_result:
            logger.info("Correlation analysis completed!")
            
            # Show market correlation insights
            if 'market_correlation_level' in analysis_result:
                market_level = analysis_result['market_correlation_level']
                logger.info(f"Market correlation level: {market_level['current']:.3f} ({market_level['regime']})")
                logger.info(f"Market trend: {market_level['trend']}")
            
            # Show risk insights
            if 'risk_insights' in analysis_result:
                risk_insights = analysis_result['risk_insights']
                logger.info(f"Diversification benefit: {risk_insights['diversification_benefit']}")
                logger.info(f"Market stress indicator: {risk_insights['market_stress_indicator']}")
                logger.info(f"Portfolio risk level: {risk_insights['portfolio_risk_level']}")
        else:
            logger.warning(f"Correlation analysis failed: {analysis_result['error']}")
        
        # Test model status
        status = forecaster.get_model_status()
        logger.info(f"Models loaded: {status['models_loaded']}")
        logger.info(f"Available horizons: {status['available_horizons']}")
        logger.info(f"Asset symbols: {status['asset_symbols']}")
        
        logger.info("✅ All correlation forecaster tests passed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_multi_asset_pipeline():
    """
    Test the multi-asset data pipeline
    """
    logger.info("Testing Multi-Asset Data Pipeline")
    
    try:
        pipeline = MLDataPipeline()
        
        # Test with synthetic data
        test_symbols = ['BTC', 'ETH', 'SOL', 'ADA']
        multi_asset_data = generate_synthetic_multi_asset_data(test_symbols, days=300)
        
        # Test multi-asset data preparation
        returns_df = pipeline.prepare_multi_asset_data(test_symbols, days=300)
        
        if not returns_df.empty:
            logger.info(f"Multi-asset returns prepared: {returns_df.shape}")
            logger.info(f"Assets: {list(returns_df.columns)}")
            
            # Calculate and display correlation matrix
            correlation_matrix = returns_df.corr()
            logger.info("Sample correlations:")
            for i, asset1 in enumerate(returns_df.columns):
                for j, asset2 in enumerate(returns_df.columns):
                    if i < j:  # Upper triangular only
                        corr = correlation_matrix.loc[asset1, asset2]
                        logger.info(f"  {asset1}-{asset2}: {corr:.3f}")
            
            logger.info("✅ Multi-asset pipeline test passed!")
            return True
        else:
            logger.warning("❌ Multi-asset pipeline returned empty data")
            return False
        
    except Exception as e:
        logger.error(f"❌ Multi-asset pipeline test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("CORRELATION FORECASTER TEST SUITE")
    logger.info("="*60)
    
    success = True
    
    # Test Multi-Asset Pipeline
    logger.info("\n" + "="*40)
    logger.info("TEST 1: Multi-Asset Data Pipeline")
    logger.info("="*40)
    success &= test_multi_asset_pipeline()
    
    # Test Correlation Forecaster
    logger.info("\n" + "="*40)
    logger.info("TEST 2: Correlation Forecaster")
    logger.info("="*40)
    success &= test_correlation_forecaster()
    
    # Final result
    logger.info("\n" + "="*60)
    if success:
        logger.info("🎉 ALL TESTS PASSED! Correlation Forecaster is ready.")
    else:
        logger.info("❌ Some tests failed. Check logs above.")
    logger.info("="*60)
    
    sys.exit(0 if success else 1)