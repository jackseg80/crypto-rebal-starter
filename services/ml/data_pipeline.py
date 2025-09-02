"""
ML Data Pipeline for crypto portfolio management
Handles data ingestion, preprocessing, and preparation for ML models
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
from pathlib import Path
import joblib

from services.price_history import get_cached_history, get_symbols_with_cache
from connectors.cointracking_api import get_current_balances

logger = logging.getLogger(__name__)

class MLDataPipeline:
    """
    Data pipeline for ML models in crypto portfolio management
    Handles data fetching, preprocessing, and feature preparation
    """
    
    def __init__(self, cache_dir: str = "cache/ml_pipeline"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Data quality thresholds
        self.min_data_points = 100  # Minimum data points required
        self.max_missing_ratio = 0.05  # Maximum 5% missing data allowed
        self.outlier_threshold = 5  # Standard deviations for outlier detection
        
        # Cache settings
        self.cache_ttl_hours = 6  # Cache TTL for processed data
    
    def fetch_portfolio_assets(self, source: str = "cointracking", 
                             min_usd: float = 100) -> List[str]:
        """
        Fetch current portfolio assets for ML training
        
        Args:
            source: Data source
            min_usd: Minimum USD value threshold
            
        Returns:
            List of asset symbols
        """
        try:
            logger.info(f"Fetching portfolio assets from {source}")
            
            if source == "stub":
                # Return common crypto assets for testing
                return ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'MATIC', 'LINK']
            
            # Fetch current balances
            balances_response = get_current_balances(source=source)
            if not balances_response or not balances_response.get("items"):
                logger.warning("No portfolio data found, using default assets")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
            # Filter and extract symbols
            portfolio_assets = []
            for item in balances_response["items"]:
                if item.get("value_usd", 0) >= min_usd:
                    symbol = item.get("symbol", "").upper()
                    if symbol and symbol not in portfolio_assets:
                        portfolio_assets.append(symbol)
            
            logger.info(f"Found {len(portfolio_assets)} portfolio assets above ${min_usd}")
            return portfolio_assets[:20]  # Limit to top 20 for performance
            
        except Exception as e:
            logger.error(f"Error fetching portfolio assets: {str(e)}")
            return ['BTC', 'ETH', 'SOL', 'ADA']  # Fallback
    
    def fetch_price_data(self, symbol: str, days: int = 730) -> Optional[pd.DataFrame]:
        """
        Fetch and validate price data for a symbol
        
        Args:
            symbol: Asset symbol
            days: Number of days of history
            
        Returns:
            DataFrame with OHLCV data or None if insufficient data
        """
        try:
            # Try to get cached price history
            price_data = get_cached_history(symbol, days=days)
            
            if not price_data or len(price_data) < self.min_data_points:
                logger.warning(f"Insufficient price data for {symbol}: "
                              f"{len(price_data) if price_data else 0} points")
                return None
            
            # Convert to DataFrame if it's a list of tuples
            if isinstance(price_data, list):
                df = pd.DataFrame(price_data, columns=['timestamp', 'price'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
                df.set_index('timestamp', inplace=True)
                
                # Create OHLCV approximation from price data
                df = df.resample('1D').agg({
                    'price': ['first', 'max', 'min', 'last', 'count']
                }).fillna(method='ffill')
                
                df.columns = ['open', 'high', 'low', 'close', 'volume']
                df['volume'] = df['volume'] * df['close'] * 1000  # Approximate volume
                
            else:
                df = price_data.copy()
            
            # Ensure required columns exist
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    if col in ['open', 'high', 'low']:
                        df[col] = df['close']  # Approximate OHLC from close
                    elif col == 'volume':
                        df[col] = df['close'] * 1000  # Approximate volume
            
            # Data quality checks
            df = self._validate_and_clean_data(df, symbol)
            
            if len(df) < self.min_data_points:
                logger.warning(f"Insufficient clean data for {symbol}: {len(df)} points")
                return None
            
            logger.info(f"Price data fetched for {symbol}: {len(df)} days")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching price data for {symbol}: {str(e)}")
            return None
    
    def _validate_and_clean_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Validate and clean price data
        
        Args:
            df: Raw price DataFrame
            symbol: Asset symbol
            
        Returns:
            Cleaned DataFrame
        """
        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]
        
        # Sort by index
        df = df.sort_index()
        
        # Check for missing data
        missing_ratio = df.isnull().sum().max() / len(df)
        if missing_ratio > self.max_missing_ratio:
            logger.warning(f"High missing data ratio for {symbol}: {missing_ratio:.2%}")
        
        # Forward fill missing values
        df = df.fillna(method='ffill').dropna()
        
        # Remove outliers using z-score
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                df = df[z_scores < self.outlier_threshold]
        
        # Ensure OHLC relationships are valid
        df['high'] = np.maximum(df['high'], df[['open', 'close']].max(axis=1))
        df['low'] = np.minimum(df['low'], df[['open', 'close']].min(axis=1))
        
        # Ensure positive prices and volume
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = np.maximum(df[col], 0.001)  # Minimum price/volume
        
        return df
    
    def prepare_training_data(self, symbols: List[str], days: int = 730, 
                            target_horizons: List[int] = [1, 7, 30]) -> Dict[str, pd.DataFrame]:
        """
        Prepare training data for multiple assets
        
        Args:
            symbols: List of asset symbols
            days: Days of price history
            target_horizons: Prediction horizons in days
            
        Returns:
            Dictionary mapping symbols to prepared DataFrames
        """
        logger.info(f"Preparing training data for {len(symbols)} assets")
        
        training_data = {}
        successful_symbols = []
        
        for symbol in symbols:
            try:
                # Check cache first
                cache_key = f"training_data_{symbol}_{days}_{'-'.join(map(str, target_horizons))}"
                cache_file = self.cache_dir / f"{cache_key}.pkl"
                
                if cache_file.exists():
                    cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if datetime.now() - cache_time < timedelta(hours=self.cache_ttl_hours):
                        logger.info(f"Loading cached training data for {symbol}")
                        training_data[symbol] = joblib.load(cache_file)
                        successful_symbols.append(symbol)
                        continue
                
                # Fetch fresh data
                price_df = self.fetch_price_data(symbol, days)
                if price_df is None:
                    continue
                
                # Prepare features and targets
                prepared_df = self._prepare_features_and_targets(price_df, symbol, target_horizons)
                
                if len(prepared_df) < self.min_data_points:
                    logger.warning(f"Insufficient prepared data for {symbol}")
                    continue
                
                # Cache the prepared data
                joblib.dump(prepared_df, cache_file)
                
                training_data[symbol] = prepared_df
                successful_symbols.append(symbol)
                
                logger.info(f"Training data prepared for {symbol}: {len(prepared_df)} samples")
                
            except Exception as e:
                logger.error(f"Error preparing training data for {symbol}: {str(e)}")
                continue
        
        logger.info(f"Training data prepared for {len(successful_symbols)}/{len(symbols)} assets")
        return training_data
    
    def _prepare_features_and_targets(self, df: pd.DataFrame, symbol: str, 
                                    target_horizons: List[int]) -> pd.DataFrame:
        """
        Prepare features and target variables
        
        Args:
            df: Price DataFrame
            symbol: Asset symbol  
            target_horizons: Target prediction horizons
            
        Returns:
            DataFrame with features and targets
        """
        from .feature_engineering import CryptoFeatureEngineer
        
        # Initialize feature engineer
        feature_engineer = CryptoFeatureEngineer()
        
        # Create comprehensive feature set
        features_df = feature_engineer.create_feature_set(df, symbol)
        
        # Add target variables for different horizons
        returns = features_df['close'].pct_change()
        
        for horizon in target_horizons:
            # Future volatility targets
            future_vol = returns.rolling(window=horizon).std().shift(-horizon) * np.sqrt(365)
            features_df[f'target_volatility_{horizon}d'] = future_vol
            
            # Future return targets
            future_return = (features_df['close'].shift(-horizon) / features_df['close'] - 1)
            features_df[f'target_return_{horizon}d'] = future_return
            
            # Future regime targets (simplified)
            future_regime = (future_return > 0.02).astype(int)  # Bull if >2% gain
            features_df[f'target_regime_{horizon}d'] = future_regime
        
        # Remove rows with NaN targets
        features_df = features_df.dropna()
        
        return features_df
    
    def get_prediction_data(self, symbol: str, lookback_days: int = 365) -> Optional[pd.DataFrame]:
        """
        Get recent data for making predictions
        
        Args:
            symbol: Asset symbol
            lookback_days: Days of recent data
            
        Returns:
            Recent price data for prediction
        """
        try:
            return self.fetch_price_data(symbol, days=lookback_days)
        except Exception as e:
            logger.error(f"Error getting prediction data for {symbol}: {str(e)}")
            return None
    
    def prepare_multi_asset_data(self, symbols: List[str], days: int = 730) -> pd.DataFrame:
        """
        Prepare multi-asset correlation data
        
        Args:
            symbols: List of asset symbols
            days: Days of price history
            
        Returns:
            DataFrame with aligned price data for all assets
        """
        logger.info(f"Preparing multi-asset data for {len(symbols)} assets")
        
        price_data = {}
        
        # Fetch data for all symbols
        for symbol in symbols:
            df = self.fetch_price_data(symbol, days)
            if df is not None:
                price_data[symbol] = df['close']
        
        if not price_data:
            logger.error("No valid price data found for multi-asset analysis")
            return pd.DataFrame()
        
        # Align all data on common dates
        multi_asset_df = pd.DataFrame(price_data)
        multi_asset_df = multi_asset_df.dropna()
        
        # Calculate returns
        returns_df = multi_asset_df.pct_change().dropna()
        
        logger.info(f"Multi-asset data prepared: {len(multi_asset_df)} days, {len(returns_df.columns)} assets")
        return returns_df
    
    def get_data_quality_report(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Generate data quality report
        
        Args:
            data: Dictionary of prepared training data
            
        Returns:
            Data quality report
        """
        report = {
            'total_assets': len(data),
            'assets_with_data': [],
            'data_quality': {},
            'summary': {}
        }
        
        total_samples = 0
        
        for symbol, df in data.items():
            report['assets_with_data'].append(symbol)
            
            quality_metrics = {
                'samples': len(df),
                'features': len([col for col in df.columns if not col.startswith('target_')]),
                'targets': len([col for col in df.columns if col.startswith('target_')]),
                'missing_ratio': df.isnull().sum().max() / len(df),
                'date_range': {
                    'start': df.index.min().isoformat(),
                    'end': df.index.max().isoformat()
                }
            }
            
            report['data_quality'][symbol] = quality_metrics
            total_samples += quality_metrics['samples']
        
        # Summary statistics
        if data:
            sample_counts = [metrics['samples'] for metrics in report['data_quality'].values()]
            feature_counts = [metrics['features'] for metrics in report['data_quality'].values()]
            
            report['summary'] = {
                'avg_samples_per_asset': np.mean(sample_counts),
                'min_samples': np.min(sample_counts),
                'max_samples': np.max(sample_counts),
                'avg_features': np.mean(feature_counts),
                'total_samples': total_samples,
                'data_quality_score': np.mean([1 - metrics['missing_ratio'] for metrics in report['data_quality'].values()])
            }
        
        return report
    
    def clear_cache(self) -> int:
        """
        Clear cached training data
        
        Returns:
            Number of files cleared
        """
        cleared_files = 0
        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
                cleared_files += 1
            logger.info(f"Cleared {cleared_files} cache files")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
        
        return cleared_files