#!/usr/bin/env python3
"""
Test with ultra-minimal feature engineering to identify the problem
"""

import sys
import os
import pandas as pd
import numpy as np

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.ml.data_pipeline import MLDataPipeline

def test_minimal_features():
    print("Testing minimal feature engineering...")
    
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
            
            # Ultra-minimal features (no rolling windows > 5)
            df = price_data.copy()
            
            # Only basic features
            df['returns'] = df['close'].pct_change()
            df['ma_3'] = df['close'].rolling(3).mean()
            df['ma_5'] = df['close'].rolling(5).mean()
            
            # Simple target (1 day only)
            df['target_return_1d'] = df['close'].shift(-1) / df['close'] - 1
            
            print(f"Before dropna: {len(df)} records")
            
            # Drop NaN
            df_clean = df.dropna()
            
            print(f"After minimal features + dropna: {len(df_clean)} records")
            print(f"Columns: {list(df_clean.columns)}")
            
            # Check for inf values
            inf_count = np.isinf(df_clean.select_dtypes(include=[np.number])).sum().sum()
            print(f"Infinite values: {inf_count}")
            
            # Check for any remaining NaN
            nan_count = df_clean.isna().sum().sum()
            print(f"Remaining NaN values: {nan_count}")
            
            if len(df_clean) > 5:
                print("✅ Minimal features work!")
                return True
            else:
                print("❌ Even minimal features fail")
                return False
        
        else:
            print("No price data fetched")
            return False

if __name__ == "__main__":
    test_minimal_features()