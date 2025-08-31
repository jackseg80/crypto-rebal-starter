"""
Price utility functions for converting between formats
"""

import pandas as pd
from typing import List, Tuple, Dict, Optional
from datetime import datetime

def price_history_to_series(price_history: List[Tuple[int, float]], symbol: str) -> pd.Series:
    """
    Convert price history list to pandas Series
    
    Args:
        price_history: List of (timestamp, price) tuples
        symbol: Asset symbol for series name
        
    Returns:
        pandas Series with datetime index and prices
    """
    
    if not price_history:
        return pd.Series(dtype=float, name=symbol)
    
    # Convert timestamps to datetime and prices to float
    timestamps = [datetime.fromtimestamp(ts) for ts, _ in price_history]
    prices = [float(price) for _, price in price_history]
    
    # Create series
    series = pd.Series(prices, index=pd.DatetimeIndex(timestamps), name=symbol)
    
    # Remove duplicates and sort
    series = series[~series.index.duplicated(keep='last')].sort_index()
    
    return series

def price_history_to_dataframe(price_data: Dict[str, List[Tuple[int, float]]]) -> pd.DataFrame:
    """
    Convert dictionary of price histories to pandas DataFrame
    
    Args:
        price_data: Dict of symbol -> List[Tuple[timestamp, price]]
        
    Returns:
        pandas DataFrame with datetime index and asset columns
    """
    
    if not price_data:
        return pd.DataFrame()
    
    # Convert each price history to series
    series_list = []
    for symbol, history in price_data.items():
        if history:  # Skip empty histories
            series = price_history_to_series(history, symbol)
            if not series.empty:
                series_list.append(series)
    
    if not series_list:
        return pd.DataFrame()
    
    # Combine all series into DataFrame
    df = pd.concat(series_list, axis=1)
    
    # Forward fill missing values and drop any remaining NaN
    df = df.fillna(method='ffill').dropna()
    
    return df

def validate_price_data(df: pd.DataFrame, min_days: int = 30) -> bool:
    """
    Validate price DataFrame has sufficient data
    
    Args:
        df: Price DataFrame
        min_days: Minimum required days
        
    Returns:
        True if data is sufficient
    """
    
    if df.empty:
        return False
        
    if len(df) < min_days:
        return False
        
    if df.columns.empty:
        return False
        
    # Check for too many NaN values
    nan_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
    if nan_ratio > 0.2:  # More than 20% NaN
        return False
        
    return True

def resample_to_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample price data to daily frequency (using last price of day)
    
    Args:
        df: Price DataFrame with any frequency
        
    Returns:
        Daily resampled DataFrame
    """
    
    if df.empty:
        return df
        
    # Resample to daily using last price
    daily_df = df.resample('D').last()
    
    # Forward fill weekends/holidays
    daily_df = daily_df.fillna(method='ffill')
    
    return daily_df

def calculate_returns_dataframe(df: pd.DataFrame, periods: int = 1) -> pd.DataFrame:
    """
    Calculate returns for all assets in DataFrame
    
    Args:
        df: Price DataFrame
        periods: Number of periods for return calculation
        
    Returns:
        Returns DataFrame
    """
    
    if df.empty:
        return df
        
    returns = df.pct_change(periods=periods)
    
    return returns