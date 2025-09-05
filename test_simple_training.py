#!/usr/bin/env python3
"""
Simplified test for ML training data preparation
"""

import sys
import os
import pandas as pd
import numpy as np

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.ml.data_pipeline import MLDataPipeline

def test_simplified_training():
    print("Testing simplified training data preparation...")
    
    pipeline = MLDataPipeline()
    
    # Get portfolio assets
    assets = pipeline.fetch_portfolio_assets(source="cointracking", min_usd=50)
    print(f"Assets: {assets[:3]}")
    
    if len(assets) > 0:
        symbol = assets[0]
        print(f"Testing with {symbol}")
        
        # Get raw price data
        price_data = pipeline.fetch_price_data(symbol, days=180)
        if price_data is not None:
            print(f"Raw price data: {len(price_data)} records")
            
            # Simplified feature creation (bypassing CryptoFeatureEngineer)
            df = price_data.copy()
            
            # Add basic features (with smaller windows)
            df['returns'] = df['close'].pct_change()
            df['volatility'] = df['returns'].rolling(5).std() * np.sqrt(365)  # Reduced window
            df['sma_5'] = df['close'].rolling(5).mean()  # Reduced window
            df['sma_10'] = df['close'].rolling(10).mean()  # Reduced window
            
            # Add simple targets (1 day horizon only)
            df['target_return_1d'] = df['close'].shift(-1) / df['close'] - 1
            
            # Drop NaN
            df_clean = df.dropna()
            
            print(f"After feature engineering: {len(df_clean)} records")
            print(f"Columns: {list(df_clean.columns)}")
            
            if len(df_clean) >= 30:
                print("✅ Successfully created training data!")
            else:
                print("❌ Still insufficient data after simplification")
        
        else:
            print("No price data fetched")

def calculate_rsi(prices, window=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

if __name__ == "__main__":
    test_simplified_training()