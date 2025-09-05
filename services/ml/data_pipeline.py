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
        self.min_data_points = 5  # Minimum data points required (extremely low for testing)
        self.max_missing_ratio = 0.10  # Maximum 10% missing data allowed (more lenient)
        self.outlier_threshold = 5  # Standard deviations for outlier detection
        
        # Cache settings
        self.cache_ttl_hours = 6  # Cache TTL for processed data
    
    def fetch_portfolio_assets(self, source: str = "cointracking", 
                             min_usd: float = 100) -> List[str]:
        """
        Fetch current portfolio assets for ML training
        Supports multiple data sources: stub, cointracking (CSV), cointracking_api
        
        Args:
            source: Data source ('stub', 'cointracking', 'cointracking_api')
            min_usd: Minimum USD value threshold
            
        Returns:
            List of asset symbols
        """
        try:
            logger.info(f"Fetching portfolio assets from {source}")
            
            if source == "stub":
                # Return diversified test portfolio for development/testing
                return ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'MATIC', 'LINK', 'ATOM', 'NEAR']
            
            elif source == "cointracking":
                # Read from CSV files in data/raw directory
                return self._fetch_assets_from_csv(min_usd)
            
            elif source == "cointracking_api":
                # Fetch from CoinTracking API
                balances_response = get_current_balances(source="cointracking_api")
                if not balances_response or not balances_response.get("items"):
                    logger.warning("No API data found, falling back to CSV")
                    return self._fetch_assets_from_csv(min_usd)
                
                # Filter and extract symbols from API response
                portfolio_assets = []
                for item in balances_response["items"]:
                    if item.get("value_usd", 0) >= min_usd:
                        symbol = item.get("symbol", "").upper()
                        if symbol and symbol not in portfolio_assets:
                            portfolio_assets.append(symbol)
                
                logger.info(f"Found {len(portfolio_assets)} portfolio assets above ${min_usd} from API")
                return portfolio_assets[:20]  # Limit to top 20 for performance
            
            else:
                logger.warning(f"Unknown data source: {source}, using stub data")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
        except Exception as e:
            logger.error(f"Error fetching portfolio assets from {source}: {str(e)}")
            return ['BTC', 'ETH', 'SOL', 'ADA']  # Safe fallback
    
    def _fetch_assets_from_csv(self, min_usd: float) -> List[str]:
        """
        Fetch portfolio assets from CSV files in data/raw directory
        
        Args:
            min_usd: Minimum USD value threshold
            
        Returns:
            List of asset symbols from CSV data
        """
        try:
            import pandas as pd
            from pathlib import Path
            
            # Look for CSV files in data/raw directory
            data_dir = Path("data/raw")
            if not data_dir.exists():
                logger.warning("data/raw directory not found, using fallback assets")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
            # Try to find balance/portfolio CSV files
            csv_files = list(data_dir.glob("*balance*.csv")) + list(data_dir.glob("*portfolio*.csv"))
            if not csv_files:
                # Try any CSV file as fallback
                csv_files = list(data_dir.glob("*.csv"))
            
            if not csv_files:
                logger.warning("No CSV files found in data/raw, using fallback assets")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
            # Read the most recent CSV file
            csv_file = max(csv_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Reading portfolio data from: {csv_file}")
            
            df = pd.read_csv(csv_file)
            
            # Try to identify relevant columns (flexible column naming)
            symbol_col = None
            value_col = None
            
            for col in df.columns:
                col_lower = col.lower()
                if 'symbol' in col_lower or 'coin' in col_lower or 'currency' in col_lower:
                    symbol_col = col
                elif 'value' in col_lower and ('usd' in col_lower or '$' in col_lower):
                    value_col = col
                elif 'amount' in col_lower and 'usd' in col_lower:
                    value_col = col
            
            if symbol_col is None:
                # Try first text column as symbol
                text_cols = df.select_dtypes(include=['object']).columns
                if len(text_cols) > 0:
                    symbol_col = text_cols[0]
            
            if value_col is None:
                # Try to find any numeric column that could represent value
                numeric_cols = df.select_dtypes(include=['number']).columns
                for col in numeric_cols:
                    if 'value' in col.lower() or 'usd' in col.lower() or 'amount' in col.lower():
                        value_col = col
                        break
                if value_col is None and len(numeric_cols) > 0:
                    value_col = numeric_cols[-1]  # Take last numeric column
            
            if symbol_col is None:
                logger.warning("Could not identify symbol column in CSV")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
            # Extract assets
            portfolio_assets = []
            
            for _, row in df.iterrows():
                try:
                    symbol = str(row[symbol_col]).strip().upper()
                    
                    # Skip empty or invalid symbols
                    if not symbol or symbol in ['NAN', 'NONE', '']:
                        continue
                    
                    # Check value threshold if value column exists
                    if value_col is not None:
                        try:
                            value = float(row[value_col])
                            if value < min_usd:
                                continue
                        except (ValueError, TypeError):
                            # If we can't parse value, include the asset anyway
                            pass
                    
                    # Clean symbol and add if valid
                    symbol = symbol.replace(' ', '').replace('-', '')
                    if len(symbol) >= 2 and len(symbol) <= 10 and symbol.isalpha():
                        if symbol not in portfolio_assets:
                            portfolio_assets.append(symbol)
                
                except Exception as e:
                    logger.debug(f"Skipping row due to error: {e}")
                    continue
            
            if not portfolio_assets:
                logger.warning("No valid assets found in CSV, using fallback")
                return ['BTC', 'ETH', 'SOL', 'ADA']
            
            logger.info(f"Found {len(portfolio_assets)} assets from CSV: {portfolio_assets[:10]}")
            return portfolio_assets[:20]  # Limit for performance
            
        except Exception as e:
            logger.error(f"Error reading CSV files: {str(e)}")
            return ['BTC', 'ETH', 'SOL', 'ADA']
    
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
                            target_horizons: List[int] = [1, 3]) -> Dict[str, pd.DataFrame]:  # Reduced default horizons
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
                
                logger.info(f"After feature engineering for {symbol}: {len(prepared_df)} records (threshold: {self.min_data_points})")
                
                if len(prepared_df) < self.min_data_points:
                    logger.warning(f"Insufficient prepared data for {symbol}: {len(prepared_df)} < {self.min_data_points}")
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
        logger.info(f"Before feature engineering: {len(df)} records")
        features_df = feature_engineer.create_feature_set(df, symbol)
        logger.info(f"After feature engineering: {len(features_df)} records")
        
        # Add target variables for different horizons
        returns = features_df['close'].pct_change()
        
        for horizon in target_horizons:
            # Future volatility targets (fixed: use minimum 2 day window for std)
            vol_window = max(horizon, 2)  # Minimum 2 days for std calculation
            future_vol = returns.rolling(window=vol_window).std().shift(-horizon) * np.sqrt(365)
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