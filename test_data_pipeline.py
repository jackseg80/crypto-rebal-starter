#!/usr/bin/env python3
"""
Quick test script for ML data pipeline
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.ml.data_pipeline import MLDataPipeline

def test_pipeline():
    print("Testing ML Data Pipeline...")
    
    pipeline = MLDataPipeline()
    
    # Test CSV data source
    try:
        assets = pipeline.fetch_portfolio_assets(source="cointracking", min_usd=50)
        print(f"CSV Assets found: {assets}")
        
        if len(assets) > 0:
            # Test individual steps first
            print(f"Testing with first asset: {assets[0]}")
            
            try:
                # Test raw price data fetch
                price_data = pipeline.fetch_price_data(assets[0], days=180)
                if price_data is not None:
                    print(f"Raw price data: {len(price_data)} records")
                    print(f"Columns: {list(price_data.columns)}")
                else:
                    print("No raw price data fetched")
                
                # Test training data preparation for first asset only
                test_symbols = [assets[0]]  # Test with just first asset
                training_data = pipeline.prepare_training_data(test_symbols, days=180, target_horizons=[1])
                
                if training_data:
                    for symbol, data in training_data.items():
                        if data is not None and len(data) > 0:
                            print(f"Training data for {symbol}: {len(data)} records")
                            print(f"Date range: {data.index[0]} to {data.index[-1]}")
                            print(f"Columns: {list(data.columns)}")
                        else:
                            print(f"No training data for {symbol}")
                else:
                    print("No training data returned")
            except Exception as e:
                print(f"Error in testing: {e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"Error testing CSV pipeline: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline()